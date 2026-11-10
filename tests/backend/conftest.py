"""Shared fixture for DB round-trip tests.

Binds a session to a single connection wrapped in an outer transaction that
is rolled back after every test, so the test suite never leaves rows behind
in TEST_DATABASE_URL and tests can run repeatedly without accumulating data.
Uses TEST_DATABASE_URL exclusively — never DATABASE_URL — so the test suite
can never touch development data.

A plain `connection.begin()` breaks the moment a test itself calls
`session.rollback()` (e.g. after catching an expected IntegrityError): the
Session's rollback also ends the connection's outer transaction, so the
fixture's own teardown rollback then warns "transaction already
deassociated from connection". The standard SQLAlchemy 2.0 fix is a SAVEPOINT
that gets restarted every time the Session ends its own transaction — see
https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
"""

import pytest
from sqlalchemy.orm import Session

from wealthpilot.config import get_settings
from wealthpilot.db.session import get_engine


@pytest.fixture()
def db_session():
    settings = get_settings()
    assert settings.test_database_url, "TEST_DATABASE_URL is not set — see .env.example"

    engine = get_engine(settings.test_database_url)
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
        engine.dispose()

# ----------------------------------------------------------------------------------------------------------------------------------
# Sentiment model service fixtures (ADR-052): a factory that writes a small, VALID artifact directory (a few bytes stand in for the weights; a fake backend stands in for the Transformer),
# which each test then breaks in exactly one way. Shared by tests/backend/core and tests/backend/api. Nothing needs a deep-learning package or the network.
# ----------------------------------------------------------------------------------------------------------------------------------

import hashlib
import json
from pathlib import Path

from wealthpilot.core import sentiment_model as sm

LABELS = ["positive", "negative", "neutral"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def _fresh_model_cache():
    sm.clear_cache()
    yield
    sm.clear_cache()


@pytest.fixture()
def artifact_root(tmp_path: Path) -> Path:
    root = tmp_path / "models" / "sentiment"
    root.mkdir(parents=True)
    return root


SYNTHETIC_REVISION = "0123456789abcdef0123456789abcdef01234567"      # a well-formed commit hash that names nothing: no real revision is ever used in a test
SYNTHETIC_TOKENIZER_REVISION = "fedcba9876543210fedcba9876543210fedcba98"
SYNTHETIC_VERSIONS = {"torch": "0.0-test", "transformers": "0.0-test", "tokenizers": "0.0-test", "safetensors": "0.0-test", "numpy": "0.0-test"}


def manifest_hash(files: dict) -> str:
    """The manifest hash, computed here INDEPENDENTLY of the code under test: SHA-256 of the canonical JSON of the `files` map."""
    import hashlib

    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def rewrite_metadata(directory: Path, change) -> None:
    """Edit an artifact's metadata the way a test needs and RECOMPUTE `manifest_sha256`, so the edit is not itself reported as a manifest mismatch."""
    path = directory / "model_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    change(metadata)
    if isinstance(metadata.get("files"), dict):
        metadata["manifest_sha256"] = manifest_hash(metadata["files"])
    path.write_text(json.dumps(metadata), encoding="utf-8")


@pytest.fixture()
def metadata_tools():
    """What a test needs to edit an artifact's metadata consistently: the independent manifest hash, a rewrite helper that recomputes it, and the synthetic revisions the factory uses."""
    from types import SimpleNamespace

    return SimpleNamespace(manifest_hash=manifest_hash, rewrite=rewrite_metadata, revision=SYNTHETIC_REVISION, tokenizer_revision=SYNTHETIC_TOKENIZER_REVISION, versions=dict(SYNTHETIC_VERSIONS))


@pytest.fixture()
def make_artifact(artifact_root: Path):
    def factory(name: str = "sentiment-v1", *, validated: bool = True, calibrated: bool = True, vocab_size: int = 1000, positions: int = 514, labels: list[str] | None = None,
                temperature: float = 2.0, min_confidence: float = 0.6, band_cutoffs=(0.6, 0.85), model_version: str = "sentiment-v1", model_name: str = "test-model",
                evidence: bool = True, regression: dict | None = None, test_samples: int = 500, tokenizer_length: int | None = None) -> Path:
        directory = artifact_root / name
        directory.mkdir(parents=True, exist_ok=True)
        labels = labels or list(LABELS)
        (directory / "model.safetensors").write_bytes(b"not real weights: a stand-in for tests")
        (directory / "config.json").write_text(json.dumps({"id2label": {str(i): l for i, l in enumerate(labels)}, "vocab_size": vocab_size, "max_position_embeddings": positions}), encoding="utf-8")
        (directory / "tokenizer_config.json").write_text(json.dumps({"model_max_length": 512}), encoding="utf-8")
        (directory / "label_map.json").write_text(json.dumps({l: i for i, l in enumerate(labels)}), encoding="utf-8")
        (directory / "metrics.json").write_text(json.dumps({"test": {"macro_f1": 0.8}}), encoding="utf-8")
        names = ["model.safetensors", "config.json", "tokenizer_config.json", "label_map.json", "metrics.json"]
        files = {n: sha(directory / n) for n in names}
        metadata = {
            "metadata_schema_version": 1,
            "model_name": model_name, "model_version": model_version, "base_model": "test/base", "base_model_revision": SYNTHETIC_REVISION, "base_model_license": "test",
            "dataset_id": "test-set", "dataset_license": "test licence",
            "training_timestamp": "2026-01-01T00:00:00+00:00", "preprocessing_version": "sentiment_prep_v1", "labels": labels, "library_versions": dict(SYNTHETIC_VERSIONS),
            "tokenizer": {"identifier": "test/base", "revision": SYNTHETIC_TOKENIZER_REVISION, "vocab_size": vocab_size,
                          "length": vocab_size if tokenizer_length is None else tokenizer_length, "files": []},
            "validation_status": "validated" if validated else "unvalidated",
            "validation": ({"dataset_id": "test-set", "dataset_license": "test licence", "test_samples": test_samples, "held_out_test": True, "duplicate_leakage_checked": True,
                            "macro_f1": 0.8, "metrics_file": "metrics.json"} if evidence else {}),
            "calibration": ({"status": "calibrated", "method": "temperature_scaling_on_validation_split", "temperature": temperature, "min_confidence": min_confidence,
                             "band_cutoffs": list(band_cutoffs)} if calibrated else {"status": "uncalibrated"}),
            "regression": regression or {"available": False, "validated": False},
            "files": files,
            "manifest_sha256": manifest_hash(files),
        }
        (directory / "model_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        return directory

    return factory


@pytest.fixture()
def config():
    def build(**over):
        base = dict(enabled=True, name="test-model", path="sentiment-v1", version="sentiment-v1", min_confidence=None, allow_fallback=True, max_tokens=128, device="cpu", timeout_seconds=2.0)
        base.update(over)
        return sm.SentimentModelConfig(**base)

    return build
