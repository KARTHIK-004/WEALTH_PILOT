"""Guards that nothing synthetic can be mistaken for real validation evidence (2026-10-30). Every fixture is generated inside a test from invented tokens and an invented register; no real manifest,
register, dataset or text exists in the repository; an agreement result alone, or a calibration result alone, can never produce `validated`; and synthetic data is `not_validation_evidence`."""
from __future__ import annotations

import json
import os
from pathlib import Path

from frozen_fixtures import build, perfect
from register_fixtures import valid_register

from training.sentiment.frozen_evaluation import evaluate_frozen
from training.sentiment.metrics import EvaluationPolicy, StatisticsPlan

ROOT = Path(__file__).resolve().parents[3]
POLICY = EvaluationPolicy.owner_approved()
FAST_PLAN = StatisticsPlan(0.95, 200, 42, 20, 75, False)
SKIP_DIRS = {".git", ".venv", "node_modules", "frontend", "tests", "__pycache__", ".pytest_cache", ".claude"}


def test_every_fixture_is_visibly_invented(tmp_path):
    for synthetic in (True, False):
        built = build(tmp_path / str(synthetic), synthetic=synthetic)
        m = built.manifest
        assert m["dataset_id"] == "invented-fixture" and m["license"].startswith("none: invented") and "invented tokens" in m["dataset_purpose"]
        assert m["provenance"]["source"] == "generated inside the test" and m["approved_by"] == "test"
        assert all(token.startswith("zq") for record in built.records for token in record["text"].split())
        register = json.loads(built.register_path.read_text(encoding="utf-8"))
        assert register["register_id"].startswith("invented-") and register["dataset_scope"] == "invented-fixture"
        assert not register["consent_wording"] or register["consent_wording"]["version"].startswith("invented-")


def test_a_report_on_a_fixture_names_the_invented_dataset_so_it_cannot_pass_as_real(tmp_path):
    frozen = build(tmp_path, train=270, calibration=90, heldout=300, synthetic=True).load()
    report = evaluate_frozen(frozen, perfect(frozen), plan=FAST_PLAN, policy=POLICY)
    assert report["manifest"]["dataset_id"] == "invented-fixture" and "invented tokens" in report["manifest"]["dataset_purpose"]
    assert report["assessment"]["validation"]["status"] == "not_validation_evidence"


def test_the_repository_holds_no_real_frozen_manifest_register_or_records_file():
    offenders = []
    for folder, directories, files in os.walk(ROOT):
        directories[:] = [d for d in directories if d not in SKIP_DIRS]
        for name in files:
            path = Path(folder) / name
            if path.suffix not in (".json", ".jsonl") or path.stat().st_size > 5_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if '"manifest_status": "FROZEN"' in text or '"manifest_status":"FROZEN"' in text or ('"de_identification_verifier_code"' in text and '"deletion_authorization"' in text):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []                                                                              # a FROZEN manifest or a participant register outside the tests would be a real-data artefact


def test_agreement_alone_never_produces_validated(tmp_path):
    for synthetic in (True, False):
        frozen = build(tmp_path / str(synthetic), train=270, calibration=90, heldout=300, synthetic=synthetic).load()
        report = evaluate_frozen(frozen, perfect(frozen), plan=FAST_PLAN, policy=POLICY)                   # perfect labels, strong annotator agreement, but labels-only
        agreement = next(g for g in report["assessment"]["gates"] if g["gate"] == "agreement")
        assert agreement["status"] == "reported" and report["agreement"]["primary_statistic"] == "COHEN_KAPPA"
        assert report["assessment"]["validation"]["status"] in ("descriptive_only", "not_validation_evidence") and report["assessment"]["validation"]["status"] != "validated"


def test_a_good_calibration_alone_never_produces_validated_on_synthetic_data(tmp_path):
    frozen = build(tmp_path, train=270, calibration=90, heldout=300, synthetic=True).load()
    confident = lambda split: {r.item_id: {label: (0.9 if label == r.label else 0.05) for label in ("positive", "negative", "neutral")} for r in frozen.records[split]}  # noqa: E731
    held = confident("heldout")
    report = evaluate_frozen(frozen, {k: max(v, key=v.get) for k, v in held.items()}, plan=FAST_PLAN, policy=POLICY, probabilities=held, calibration_probabilities=confident("calibration"))
    assert report["temperature_calibration"]["status"] == "fitted_and_applied" and report["assessment"]["validation"]["status"] == "not_validation_evidence"


def test_the_register_fixture_is_synthetic_by_default():
    register = valid_register()
    assert register["data_status"] == "synthetic" and register["consent_wording"] is None and register["register_id"].startswith("invented-")
