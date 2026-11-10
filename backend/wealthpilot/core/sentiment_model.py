"""Local inference service for a PRETRAINED Transformer sentiment classifier (ADR-052). It implements the `SentimentModel` seam of `core/user_text_sentiment.py`.

NOTHING HERE TRAINS. Training is offline only (`training/sentiment/`). This module only verifies an artifact that training wrote, loads it lazily and runs inference on the CPU.
It is not a general-purpose language model and generates no text: it maps one short text to class probabilities (positive / negative / neutral) and, only when a VALIDATED
regression head exists, an intensity in [-1, 1].

State today: no artifact exists in the repository, no deep-learning package is installed in the project environment (`torch`, `transformers`, `tokenizers` and `safetensors` are NOT in
the approved stack), and the feature is switched off (`SENTIMENT_MODEL_ENABLED=false`). Every failure path below therefore ends in a fixed reason code and the rules baseline answering;
none is exercised against real weights. The real backend is exercised only against locally generated, randomly initialised stand-in models and hand-written tokenizer fixtures
(`tests/training/sentiment/test_transformer_standin.py`, skipped where the packages are absent).

Guarantees, each tested with a fake backend (no weights are needed to test the policy):
- the artifact directory must lie inside `models/sentiment/` (no arbitrary path, no symlink escape), must carry metadata whose SHA-256 list matches every file (corruption), must use
  `safetensors` weights (no pickle), a consistent label map / `config.json` / tokenizer vocabulary size, the length of the tokenizer it was written with (`tokenizer.length`, compared with
  the loaded tokenizer by `check_tokenizer_length` and never greater than `config.vocab_size`), a supported `metadata_schema_version`, its provenance (the base model and tokenizer
  identifiers with immutable 40-character revisions, the versions of torch / transformers / tokenizers / safetensors, a manifest hash that is recomputed), and a version equal to the
  configured one; an artifact written before these fields existed fails closed as `artifact_incompatible`;
- a model is PRIMARY only when its metadata says `validated` AND carries the evidence (held-out test set, duplicate-leakage check, licensed dataset, metrics) AND is calibrated
  (temperature scaling with a documented minimum confidence and band cut-offs). Anything else is `not_validated`: the rules baseline answers and the response says so;
- the raw softmax is never called calibrated: `confidence` exists only for a calibrated model, `class_probabilities` always say which kind they are;
- the text is only ever an argument: it is never logged, stored, put in an error, or sent anywhere; errors are fixed reason codes with no path, no text and no stack trace;
- inference has a hard wall-clock limit and a token limit; a late answer is discarded.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from wealthpilot.core.user_text_sentiment import FALLBACK_REASONS, ModelReading

ARTIFACT_ROOT = Path(__file__).resolve().parents[3] / "models" / "sentiment"
METADATA_FILE = "model_metadata.json"
LABEL_MAP_FILE = "label_map.json"
CONFIG_FILE = "config.json"
TOKENIZER_CONFIG_FILE = "tokenizer_config.json"
WEIGHTS_FILE = "model.safetensors"
MODEL_LABELS = ("positive", "negative", "neutral")
VALIDATED = "validated"
UNVALIDATED = "unvalidated"
CALIBRATED = "calibrated"
UNCALIBRATED = "uncalibrated"
METADATA_SCHEMA_VERSION = 1                       # the only metadata format this loader reads; an artifact without it, or with another number, is refused (no migration, no best-effort reading)
SUPPORTED_SCHEMA_VERSIONS = frozenset({METADATA_SCHEMA_VERSION})
REQUIRED_DEPENDENCIES = ("torch", "transformers", "tokenizers", "safetensors")      # versions recorded at training time (provenance only: the loader does not compare them with what is installed)
REQUIRED_METADATA = ("metadata_schema_version", "model_name", "model_version", "base_model", "base_model_revision", "base_model_license", "dataset_id", "dataset_license", "training_timestamp",
                     "preprocessing_version", "labels", "library_versions", "manifest_sha256", "files", "tokenizer", "validation_status", "calibration", "regression")
_COMMIT_HASH = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
VALIDATION_EVIDENCE = ("dataset_id", "dataset_license", "test_samples", "held_out_test", "duplicate_leakage_checked", "macro_f1", "metrics_file")
FAILURE_TTL_SECONDS = 30.0          # a failed load is not retried for this long, so a missing artifact does not cost a disk scan per request


class ModelUnavailable(Exception):
    """The model cannot be used. `reason` is one of the fixed `FALLBACK_REASONS`; the message is that code and nothing else (never text, a path or a stack trace)."""

    def __init__(self, reason: str) -> None:
        assert reason in FALLBACK_REASONS, reason
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SentimentModelConfig:
    """Everything the service needs, read from `Settings` by the caller (this module reads no environment and no settings)."""

    enabled: bool = False
    name: str = ""
    path: str = ""
    version: str = ""
    min_confidence: float | None = None
    allow_fallback: bool = True
    max_tokens: int | None = None
    device: str = "cpu"
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class ArtifactInfo:
    directory: Path
    model_name: str
    model_version: str
    labels: tuple[str, ...]              # in logit order
    validation_status: str
    calibration_status: str
    temperature: float | None
    min_confidence: float | None
    band_cutoffs: tuple[float, float] | None
    intensity_available: bool
    max_position_embeddings: int
    tokenizer_length: int                # len(tokenizer) recorded when the artifact was written; the loaded tokenizer must have exactly this length
    schema_version: int                  # `metadata_schema_version` (always a supported one: anything else is refused)
    base_model: str                      # the exact identifier of the base model the artifact was trained from
    base_model_revision: str             # its immutable 40-character lowercase commit hash
    tokenizer_identifier: str
    tokenizer_revision: str              # the tokenizer's immutable 40-character lowercase commit hash
    manifest_sha256: str                 # SHA-256 of the canonical JSON of the `files` map, recomputed and compared by the verifier
    dependency_versions: tuple[tuple[str, str], ...]      # (name, version) for torch, transformers, tokenizers and safetensors as recorded at training time


@dataclass(frozen=True)
class BackendOutput:
    logits: tuple[float, ...]
    intensity: float | None = None


class TextClassifierBackend(Protocol):
    def predict(self, text: str) -> BackendOutput: ...


@dataclass(frozen=True)
class ModelStatus:
    """What `GET /api/sentiment-model/status` reports. No path, no secret, no text."""

    enabled: bool
    state: str                            # disabled | ready | unavailable
    reason: str | None
    model_name: str | None
    model_version: str | None
    validation_status: str | None
    calibration_status: str | None
    intensity_available: bool
    fallback_enabled: bool
    dependencies_available: bool


def dependencies_available() -> bool:
    """True when the packages a Transformer backend needs can be imported. Importing is cheap and loads nothing; none of them is part of the approved stack."""
    import importlib.util

    return all(importlib.util.find_spec(name) is not None for name in ("torch", "transformers", "tokenizers", "safetensors"))


# ---------------------------------------------------------------------------------------------------------------------------- artifact verification


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ModelUnavailable("artifact_corrupt") from None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_artifact_directory(configured: str, root: Path = ARTIFACT_ROOT) -> Path:
    """The configured path, accepted only when it is a real directory strictly inside the approved artifact root and no component of it is a symbolic link. A relative path is
    relative to that root; `..` is normalised away before the check, so it cannot escape."""
    if not configured.strip():
        raise ModelUnavailable("artifact_missing")
    base = Path(os.path.abspath(root))
    candidate = Path(configured)
    candidate = Path(os.path.abspath(candidate if candidate.is_absolute() else base / candidate))
    try:
        relative = candidate.relative_to(base)
    except ValueError:
        raise ModelUnavailable("path_not_allowed") from None
    if not relative.parts:
        raise ModelUnavailable("path_not_allowed")
    current = base
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ModelUnavailable("path_not_allowed")
    if not current.is_dir():
        raise ModelUnavailable("artifact_missing")
    return current.resolve()


def _number(value: object, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not low <= float(value) <= high:
        raise ModelUnavailable("artifact_incompatible")
    return float(value)


def is_commit_hash(value: object) -> bool:
    """True only for an immutable revision: a full 40-character LOWERCASE hexadecimal commit hash (never a branch, a tag, a short hash or an empty value). The one definition used by the
    verifier and by the trainer, so the two cannot drift."""
    return isinstance(value, str) and _COMMIT_HASH.fullmatch(value) is not None


def manifest_sha256(files: dict) -> str:
    """SHA-256 of the canonical JSON of the `files` map (keys sorted, separators `,` and `:`, ASCII). One function for the writer and the verifier. It detects an inconsistent edit of the
    metadata; like the per-file hashes it cannot detect someone who rewrites the whole directory."""
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _provenance(metadata: dict) -> tuple[str, str, str, str, str, tuple[tuple[str, str], ...]]:
    """The provenance a trained artifact must carry (D8): the exact base model and its immutable revision, the tokenizer's identifier and immutable revision, the versions of torch,
    transformers, tokenizers and safetensors, and the manifest hash. Anything missing or malformed is `artifact_incompatible`; nothing is looked up or resolved, and no value is invented."""
    base_model, revision = metadata["base_model"], metadata["base_model_revision"]
    tokenizer, versions, manifest = metadata["tokenizer"], metadata["library_versions"], metadata["manifest_sha256"]
    if not (_text(base_model) and is_commit_hash(revision) and isinstance(tokenizer, dict) and _text(tokenizer.get("identifier")) and is_commit_hash(tokenizer.get("revision"))
            and isinstance(versions, dict) and all(_text(versions.get(name)) for name in REQUIRED_DEPENDENCIES) and isinstance(manifest, str) and _SHA256.fullmatch(manifest) is not None):
        raise ModelUnavailable("artifact_incompatible")
    return (base_model, revision, tokenizer["identifier"], tokenizer["revision"], manifest, tuple((name, versions[name]) for name in REQUIRED_DEPENDENCIES))


def check_tokenizer_fits_embeddings(tokenizer_length: object, vocab_size: object) -> None:
    """D9: a tokenizer longer than the model's embedding matrix can emit an id that has no row. `len(tokenizer) > config.vocab_size` is refused with `artifact_incompatible`; equality is NOT
    required (a padded embedding matrix, a tokenizer shorter than `vocab_size`, is valid). A missing or malformed value on either side is refused too. Runs before any inference."""
    if (isinstance(tokenizer_length, bool) or not isinstance(tokenizer_length, int) or isinstance(vocab_size, bool) or not isinstance(vocab_size, int)
            or tokenizer_length < 1 or vocab_size < 1 or tokenizer_length > vocab_size):
        raise ModelUnavailable("artifact_incompatible")


def verify_artifact(directory: Path, *, expected_version: str, expected_name: str, max_tokens: int) -> ArtifactInfo:
    """Raises `ModelUnavailable` with a fixed reason; returns what inference needs. Reads every listed file once to check its hash (done once per process, then cached)."""
    metadata = _read_json(directory / METADATA_FILE)
    if not isinstance(metadata, dict) or any(key not in metadata for key in REQUIRED_METADATA):
        raise ModelUnavailable("artifact_incompatible")           # includes an artifact written before the provenance fields existed: it fails closed
    schema = metadata["metadata_schema_version"]
    if isinstance(schema, bool) or not isinstance(schema, int) or schema not in SUPPORTED_SCHEMA_VERSIONS:
        raise ModelUnavailable("artifact_incompatible")           # an unknown (or newer, or non-integer) metadata format is never read on a best-effort basis
    base_model, base_revision, tokenizer_identifier, tokenizer_revision, recorded_manifest, dependency_versions = _provenance(metadata)
    if metadata["model_version"] != expected_version or not expected_version:
        raise ModelUnavailable("version_mismatch")
    if expected_name and metadata["model_name"] != expected_name:
        raise ModelUnavailable("artifact_incompatible")

    files = metadata["files"]
    if not isinstance(files, dict) or not all(name in files for name in (WEIGHTS_FILE, CONFIG_FILE, TOKENIZER_CONFIG_FILE, LABEL_MAP_FILE)):
        raise ModelUnavailable("artifact_incompatible")          # safetensors only: a pickle checkpoint is never loaded
    for relative, expected in files.items():
        target = (directory / relative).resolve()
        if directory not in target.parents or not isinstance(expected, str):
            raise ModelUnavailable("path_not_allowed")
        if not target.is_file():
            raise ModelUnavailable("artifact_corrupt")
        if _sha256(target) != expected:
            raise ModelUnavailable("artifact_corrupt")
    if manifest_sha256(files) != recorded_manifest:
        raise ModelUnavailable("artifact_corrupt")           # the metadata's own list of hashes was edited after the manifest hash was written

    label_map = _read_json(directory / LABEL_MAP_FILE)
    labels = metadata["labels"]
    if not (isinstance(label_map, dict) and isinstance(labels, list) and labels and set(labels) <= set(MODEL_LABELS) and len(set(labels)) == len(labels)
            and label_map == {label: index for index, label in enumerate(labels)}):
        raise ModelUnavailable("artifact_incompatible")
    config = _read_json(directory / CONFIG_FILE)
    tokenizer = metadata["tokenizer"]
    if not (isinstance(config, dict) and isinstance(tokenizer, dict) and config.get("id2label") and len(config["id2label"]) == len(labels)
            and [config["id2label"][str(i)] if str(i) in config["id2label"] else None for i in range(len(labels))] == labels):
        raise ModelUnavailable("artifact_incompatible")
    if config.get("vocab_size") != tokenizer.get("vocab_size") or not isinstance(tokenizer.get("vocab_size"), int):
        raise ModelUnavailable("artifact_incompatible")          # the tokenizer was built for a different vocabulary than the weights
    # the real length of the tokenizer the artifact was written with: `vocab_size` above is a number taken from config.json on both sides, so it cannot notice a tokenizer that lost its
    # vocabulary; this one is compared with the loaded tokenizer in `check_tokenizer_length`. It is NOT required to EQUAL `vocab_size` (a padded embedding matrix is valid), but it may not
    # EXCEED it (D9, `check_tokenizer_fits_embeddings`): a longer tokenizer can emit an id with no embedding row.
    tokenizer_length = tokenizer.get("length")
    if isinstance(tokenizer_length, bool) or not isinstance(tokenizer_length, int) or tokenizer_length < 1:
        raise ModelUnavailable("artifact_incompatible")          # missing or malformed: an artifact that cannot say which tokenizer it was written with is not used
    check_tokenizer_fits_embeddings(tokenizer_length, config.get("vocab_size"))
    positions = config.get("max_position_embeddings")
    if not isinstance(positions, int) or max_tokens < 1 or max_tokens + 2 > positions:
        raise ModelUnavailable("artifact_incompatible")

    validation = metadata["validation_status"]
    if validation not in (VALIDATED, UNVALIDATED):
        raise ModelUnavailable("artifact_incompatible")
    calibration = metadata["calibration"]
    if not isinstance(calibration, dict) or calibration.get("status") not in (CALIBRATED, UNCALIBRATED):
        raise ModelUnavailable("artifact_incompatible")
    temperature = min_confidence = cutoffs = None
    if calibration["status"] == CALIBRATED:
        temperature = _number(calibration.get("temperature"), 1e-3, 100.0)
        min_confidence = _number(calibration.get("min_confidence"), 1e-3, 1.0)
        raw = calibration.get("band_cutoffs")
        if not (isinstance(raw, list) and len(raw) == 2):
            raise ModelUnavailable("artifact_incompatible")
        cutoffs = (_number(raw[0], 1e-3, 1.0), _number(raw[1], 1e-3, 1.0))
        if cutoffs[0] > cutoffs[1]:
            raise ModelUnavailable("artifact_incompatible")
    if validation == VALIDATED:
        evidence = metadata.get("validation")
        if not (isinstance(evidence, dict) and all(key in evidence for key in VALIDATION_EVIDENCE) and evidence["held_out_test"] is True and evidence["duplicate_leakage_checked"] is True
                and isinstance(evidence["test_samples"], int) and evidence["test_samples"] > 0 and str(evidence["dataset_license"]).strip() and calibration["status"] == CALIBRATED
                and (directory / str(evidence["metrics_file"])).is_file()):
            raise ModelUnavailable("artifact_incompatible")      # "validated" is a claim that needs its evidence; without it the model is not used as primary
    regression = metadata["regression"]
    if not isinstance(regression, dict):
        raise ModelUnavailable("artifact_incompatible")
    intensity = bool(regression.get("available")) and bool(regression.get("validated"))
    return ArtifactInfo(directory, str(metadata["model_name"]), str(metadata["model_version"]), tuple(labels), validation, calibration["status"], temperature, min_confidence, cutoffs,
                        intensity, positions, tokenizer_length, schema, base_model, base_revision, tokenizer_identifier, tokenizer_revision, recorded_manifest, dependency_versions)


# ---------------------------------------------------------------------------------------------------------------------------- the real backend (needs packages that are NOT installed)


def check_tokenizer_length(expected: int, loaded: int) -> None:
    """The tokenizer that was just loaded must be the tokenizer the artifact was written with: its length must equal `tokenizer.length` from the metadata.

    This is the explicit integrity check for a tokenizer that silently lost (or gained) part of its vocabulary: every id would then be wrong while every other check still passes. It is
    deliberately NOT a comparison with `config.vocab_size`: a model may legitimately have a larger (padded) embedding matrix than its tokenizer. A mismatch is the repository-standard
    `artifact_incompatible` (a fixed code: no length, no path and no text leave this module)."""
    if isinstance(expected, bool) or not isinstance(expected, int) or isinstance(loaded, bool) or not isinstance(loaded, int) or expected != loaded:
        raise ModelUnavailable("artifact_incompatible")


class TransformersBackend:
    """Classification with `transformers` + `torch` on the CPU. Loads only from the verified local directory (`local_files_only`, no remote code, safetensors only) and refuses a
    tokenizer whose length differs from the one recorded in the artifact (`check_tokenizer_length`). The project environment has none of the packages, so this class is exercised only by
    the stand-in tests (locally generated, randomly initialised model; hand-written tokenizer), never against real weights (ADR-052)."""

    def __init__(self, directory: Path, *, max_tokens: int, device: str, labels: tuple[str, ...], tokenizer_length: int, threads: int | None = None) -> None:
        if device != "cpu":
            raise ModelUnavailable("invalid_configuration")        # CPU inference only; a GPU is never required
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            raise ModelUnavailable("dependencies_missing") from None
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False)
            self._model = AutoModelForSequenceClassification.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False, use_safetensors=True)
            self._model.eval()
            loaded_length = len(self._tokenizer)
            model_vocab_size = getattr(getattr(self._model, "config", None), "vocab_size", None)
        except Exception:  # noqa: BLE001 -- the library's message may include a path; only a fixed code leaves this module
            raise ModelUnavailable("load_failed") from None
        # outside the try: their explicit code must not be turned into load_failed. Both run here, in the constructor, so a bad tokenizer is refused before any text is ever seen.
        check_tokenizer_length(tokenizer_length, loaded_length)                 # the tokenizer is the one the artifact was written with
        check_tokenizer_fits_embeddings(loaded_length, model_vocab_size)        # D9: no id can fall outside the embedding matrix (shorter is fine, longer is refused)
        self._torch, self._max_tokens, self._labels = torch, max_tokens, labels
        if threads:                                                            # ADR-055: only when the owner configured a cap; None leaves torch's own default untouched
            torch.set_num_threads(int(threads))

    def predict(self, text: str) -> BackendOutput:
        encoded = self._tokenizer(text, truncation=True, max_length=self._max_tokens, return_tensors="pt")
        with self._torch.inference_mode():
            logits = self._model(**encoded).logits[0].tolist()
        return BackendOutput(tuple(float(v) for v in logits))


# ---------------------------------------------------------------------------------------------------------------------------- the model


def _softmax(values: list[float]) -> list[float]:
    peak = max(values)
    exps = [math.exp(v - peak) for v in values]
    total = sum(exps)
    return [e / total for e in exps]


_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sentiment-model")


class TrainedSentimentModel:
    """A verified artifact plus a backend. Implements the `SentimentModel` seam: `interpret(text) -> ModelReading`, or raises `ModelUnavailable` (a fixed reason, no text)."""

    def __init__(self, info: ArtifactInfo, backend: TextClassifierBackend, *, min_confidence: float | None = None, timeout_seconds: float = 5.0) -> None:
        self.info, self._backend, self._timeout = info, backend, timeout_seconds
        # a configured threshold can only RAISE the artifact's own calibrated minimum; for an uncalibrated model no threshold exists (and the model is never primary)
        self._threshold = None if info.calibration_status != CALIBRATED else max(info.min_confidence or 0.0, min_confidence or 0.0) or None

    def interpret(self, text: str) -> ModelReading:
        future = _EXECUTOR.submit(self._backend.predict, text)
        try:
            output = future.result(timeout=self._timeout)
        except FutureTimeout:
            future.cancel()
            raise ModelUnavailable("timeout") from None
        except ModelUnavailable:
            raise
        except Exception:  # noqa: BLE001 -- the backend's exception could carry the text; only a fixed code leaves
            raise ModelUnavailable("inference_failed") from None
        logits = list(output.logits) if isinstance(output, BackendOutput) else None
        if logits is None or len(logits) != len(self.info.labels) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) for v in logits):
            raise ModelUnavailable("invalid_output")
        scale = self.info.temperature if self.info.calibration_status == CALIBRATED and self.info.temperature else 1.0
        probabilities = _softmax([float(v) / scale for v in logits])
        best = max(range(len(probabilities)), key=probabilities.__getitem__)
        intensity = output.intensity if self.info.intensity_available else None
        if intensity is not None and not (isinstance(intensity, (int, float)) and math.isfinite(float(intensity)) and -1.0 <= float(intensity) <= 1.0):
            raise ModelUnavailable("invalid_output")
        calibrated = self.info.calibration_status == CALIBRATED
        return ModelReading(
            sentiment=self.info.labels[best], probability=probabilities[best], calibrated=calibrated, model_version=self.info.model_version, validation_status=self.info.validation_status,
            abstain_below=self._threshold, band_cutoffs=self.info.band_cutoffs if calibrated else None,
            class_probabilities={label: probabilities[i] for i, label in enumerate(self.info.labels)}, intensity=None if intensity is None else float(intensity), model_name=self.info.model_name)


# ---------------------------------------------------------------------------------------------------------------------------- loading, caching, status

_LOCK = threading.Lock()
_CACHE: dict[tuple, TrainedSentimentModel] = {}
_FAILURES: dict[tuple, tuple[float, str]] = {}
BackendFactory = Callable[[ArtifactInfo, "SentimentModelConfig"], TextClassifierBackend]


def _default_backend(info: ArtifactInfo, config: SentimentModelConfig) -> TextClassifierBackend:
    return TransformersBackend(info.directory, max_tokens=int(config.max_tokens or 0), device=config.device, labels=info.labels, tokenizer_length=info.tokenizer_length)


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
        _FAILURES.clear()


def load_model(config: SentimentModelConfig, *, backend_factory: BackendFactory | None = None, root: Path = ARTIFACT_ROOT) -> TrainedSentimentModel:
    """The configured, verified, cached model, or `ModelUnavailable(reason)`. A model that is not VALIDATED is refused (`not_validated`): it is never used as the primary reading."""
    if not config.enabled:
        raise ModelUnavailable("artifact_missing")
    key = (config.path, config.version, config.name, config.max_tokens, config.device, str(root), id(backend_factory))
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        failed = _FAILURES.get(key)
        if failed is not None and time.monotonic() - failed[0] < FAILURE_TTL_SECONDS:
            raise ModelUnavailable(failed[1])
        try:
            if not config.max_tokens or config.max_tokens < 1 or config.timeout_seconds <= 0 or config.device != "cpu":
                raise ModelUnavailable("invalid_configuration")
            if backend_factory is None and not dependencies_available():
                raise ModelUnavailable("dependencies_missing")
            info = verify_artifact(resolve_artifact_directory(config.path, root), expected_version=config.version, expected_name=config.name, max_tokens=config.max_tokens)
            if info.validation_status != VALIDATED:
                raise ModelUnavailable("not_validated")
            model = TrainedSentimentModel(info, (backend_factory or _default_backend)(info, config), min_confidence=config.min_confidence, timeout_seconds=config.timeout_seconds)
        except ModelUnavailable as exc:
            _FAILURES[key] = (time.monotonic(), exc.reason)
            raise
        _CACHE[key] = model
        return model


def model_status(config: SentimentModelConfig, *, backend_factory: BackendFactory | None = None, root: Path = ARTIFACT_ROOT) -> ModelStatus:
    deps = dependencies_available()
    if not config.enabled:
        return ModelStatus(False, "disabled", None, None, None, None, None, False, config.allow_fallback, deps)
    try:
        model = load_model(config, backend_factory=backend_factory, root=root)
    except ModelUnavailable as exc:
        return ModelStatus(True, "unavailable", exc.reason, None, None, None, None, False, config.allow_fallback, deps)
    info = model.info
    return ModelStatus(True, "ready", None, info.model_name, info.model_version, info.validation_status, info.calibration_status, info.intensity_available, config.allow_fallback, deps)


__all__ = ["ARTIFACT_ROOT", "ArtifactInfo", "BackendOutput", "ModelStatus", "ModelUnavailable", "SentimentModelConfig", "TextClassifierBackend", "TransformersBackend", "TrainedSentimentModel",
           "METADATA_SCHEMA_VERSION", "SUPPORTED_SCHEMA_VERSIONS", "check_tokenizer_fits_embeddings", "check_tokenizer_length", "clear_cache", "dependencies_available", "is_commit_hash",
           "load_model", "manifest_sha256", "model_status", "resolve_artifact_directory", "verify_artifact"]
