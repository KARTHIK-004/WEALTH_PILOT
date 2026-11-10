"""ADR-052 -- the whole offline pipeline (manifest gate -> split -> training -> temperature scaling -> metrics -> artifact -> the application's own loader) run with a FAKE trainer on invented data,
plus the command-line refusals and the candidate evaluation. No deep-learning package, no weights, no network: this proves the plumbing and the refusals, and measures NOTHING about real
accuracy. The two parts that need the real packages (`fine_tune_with_torch`, `TransformersBackend`) are exercised only against local random stand-ins in `test_transformer_standin.py`
(skipped where the packages are absent), and the safe-loading seam is in `test_transformer_training_seam.py`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from sentiment_fixtures import approved_manifest, fake_trainer, make_rows, manifest_dict, write_jsonl, write_manifest

from training.sentiment import evaluate_sentiment_model as evaluate
from training.sentiment import train_sentiment_transformer as train
from training.sentiment.artifacts import decide_validation
from training.sentiment.config import LABELS, MIN_TEST_SAMPLES_FOR_VALIDATED, REPO_ROOT
from training.sentiment.dataset import ManifestError, load_manifest
from wealthpilot.core import sentiment_model as sm

TARGETS = dict(target_precision=0.85, min_coverage=0.5, high_precision=0.95, high_min_coverage=0.2)


def run(tmp_path, manifest_raw, rows, *, trainer=None, version="sentiment-v1", base_model="finbert", fixture=True, **over):
    data = write_jsonl(tmp_path / "data.jsonl", rows)
    manifest = load_manifest(write_manifest(tmp_path / "manifest.json", manifest_raw), allow_development_fixture=fixture)
    return train.run_training(manifest=manifest, data_path=data, base_model=base_model, version=version, output_root=tmp_path / "out", trainer=trainer or fake_trainer(),
                              allow_development_fixture=fixture, **{**TARGETS, **over})


# ------------------------------------------------------------------------------------------------ a development fixture can never validate anything


def test_a_development_fixture_run_writes_an_unvalidated_artifact_with_the_reasons(tmp_path):
    result = run(tmp_path, manifest_dict(), make_rows(40, group_every=4))
    assert result["validation_status"] == "unvalidated"
    assert any("development fixture" in r for r in result["reasons_not_validated"]) and any("held-out test split has" in r for r in result["reasons_not_validated"])
    directory = Path(result["directory"])
    metadata = json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))
    for key in ("model_name", "model_version", "base_model", "dataset_id", "dataset_license", "training_timestamp", "preprocessing_version", "labels", "files", "seed", "library_versions", "calibration"):
        assert key in metadata, key
    assert metadata["validation_status"] == "unvalidated" and metadata["preprocessing_version"] == "sentiment_prep_v1" and metadata["seed"] == 42
    for name in ("model.safetensors", "config.json", "tokenizer_config.json", "label_map.json", "metrics.json", "confusion_matrix.json", "model_metadata.json"):
        assert (directory / name).is_file(), name
    assert json.loads((directory / "label_map.json").read_text(encoding="utf-8")) == {"positive": 0, "negative": 1, "neutral": 2}


def test_the_application_refuses_that_artifact_as_primary_even_though_it_verifies(tmp_path):
    result = run(tmp_path, manifest_dict(), make_rows(40, group_every=4))
    directory = Path(result["directory"])
    info = sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="finbert", max_tokens=128)          # structurally fine
    assert info.validation_status == "unvalidated"
    config = sm.SentimentModelConfig(enabled=True, name="finbert", path=str(directory), version="sentiment-v1", max_tokens=128)
    with pytest.raises(sm.ModelUnavailable) as refused:
        sm.load_model(config, backend_factory=lambda i, c: None, root=directory.parent)
    assert refused.value.reason == "not_validated"
    sm.clear_cache()


def test_the_metrics_file_has_the_per_class_matrix_and_calibration_numbers(tmp_path):
    result = run(tmp_path, manifest_dict(), make_rows(40, group_every=4))
    metrics = json.loads((Path(result["directory"]) / "metrics.json").read_text(encoding="utf-8"))
    test = metrics["test"]
    assert set(test["per_class"]) == set(LABELS) and test["confusion_matrix"]["labels"] == list(LABELS) and test["samples"] == sum(test["confusion_matrix"]["matrix"][i][j] for i in range(3) for j in range(3))
    assert 0.0 <= test["accuracy"] <= 1.0 and 0.0 <= test["macro_f1"] <= 1.0
    assert {"temperature", "ece_before", "ece_after", "reliability_after", "fitted_on"} <= set(metrics["calibration"]) and metrics["calibration"]["fitted_on"] == "validation split"
    dataset = metrics["dataset"]
    assert dataset["development_fixture"] is True and dataset["license"] and dataset["domain_note"] and dataset["limitations"] and dataset["seed"] == 42
    assert sum(dataset["splits"]["train"].values()) + sum(dataset["splits"]["validation"].values()) + sum(dataset["splits"]["test"].values()) == dataset["rows_kept"] == 120
    assert metrics["regression"]["available"] is False


def test_the_same_inputs_give_the_same_metrics_and_splits(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = run(tmp_path / "a", manifest_dict(), make_rows(40, group_every=4))
    b = run(tmp_path / "b", manifest_dict(), make_rows(40, group_every=4))
    ma, mb = (json.loads((Path(r["directory"]) / "metrics.json").read_text(encoding="utf-8")) for r in (a, b))
    assert ma == mb and a["temperature"] == b["temperature"]


# ------------------------------------------------------------------------------------------------ the validated path needs every piece of evidence


def test_a_complete_evidence_set_validates_and_the_loader_then_accepts_the_model(tmp_path):
    rows = make_rows(1000, group_every=2)                                              # 3000 invented rows -> a test split above the structural minimum
    result = run(tmp_path, approved_manifest(sample_count=3000), rows, fixture=False, trainer=fake_trainer(accuracy_noise=1.0))
    assert result["validation_status"] == "validated" and result["reasons_not_validated"] == []
    directory = Path(result["directory"])
    metadata = json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))
    assert metadata["validation"]["held_out_test"] is True and metadata["validation"]["duplicate_leakage_checked"] is True and metadata["validation"]["test_samples"] >= MIN_TEST_SAMPLES_FOR_VALIDATED
    calibration = metadata["calibration"]
    assert calibration["status"] == "calibrated" and calibration["temperature"] > 0 and 0 < calibration["min_confidence"] <= calibration["band_cutoffs"][1] <= 1
    config = sm.SentimentModelConfig(enabled=True, name="finbert", path=str(directory), version="sentiment-v1", max_tokens=128)
    model = sm.load_model(config, backend_factory=lambda i, c: type("B", (), {"predict": lambda self, t: sm.BackendOutput((3.0, 0.0, 0.0))})(), root=directory.parent)
    reading = model.interpret("I feel hopeful about my savings")
    assert reading.sentiment == "positive" and reading.calibrated and reading.abstain_below == pytest.approx(calibration["min_confidence"]) and reading.band_cutoffs == tuple(calibration["band_cutoffs"])
    sm.clear_cache()


def test_the_owners_targets_decide_whether_a_threshold_exists(tmp_path):
    rows = make_rows(1000, group_every=2)
    result = run(tmp_path, approved_manifest(sample_count=3000), rows, fixture=False, trainer=fake_trainer(accuracy_noise=4.0), target_precision=0.999, min_coverage=0.9)
    assert result["validation_status"] == "unvalidated" and any("abstention threshold" in r for r in result["reasons_not_validated"])


def test_validation_is_refused_for_each_missing_piece_of_evidence():
    ok = dict(test_samples=MIN_TEST_SAMPLES_FOR_VALIDATED, held_out_test=True, duplicate_leakage_checked=True, dataset_license="L", development_fixture=False, calibrated=True, threshold_found=True)
    assert decide_validation(**ok) == ("validated", [])
    for field, bad in (("test_samples", MIN_TEST_SAMPLES_FOR_VALIDATED - 1), ("held_out_test", False), ("duplicate_leakage_checked", False), ("dataset_license", " "), ("development_fixture", True),
                       ("calibrated", False), ("threshold_found", False)):
        status, reasons = decide_validation(**{**ok, field: bad})
        assert status == "unvalidated" and len(reasons) >= 1, field


# ------------------------------------------------------------------------------------------------ refusals


def test_an_unapproved_dataset_never_trains(tmp_path):
    with pytest.raises(ManifestError, match="not approved"):
        load_manifest(write_manifest(tmp_path / "m.json", manifest_dict(development_fixture=False, approved=False)))
    with pytest.raises(ManifestError, match="development fixture"):
        train.run_training(
            manifest=load_manifest(write_manifest(tmp_path / "m2.json", manifest_dict()), allow_development_fixture=True), data_path=write_jsonl(tmp_path / "d.jsonl", make_rows(40)), base_model="finbert",
            version="v", output_root=tmp_path / "o", trainer=fake_trainer(), **TARGETS)               # the same fixture without the explicit test-only allowance is refused


def test_only_a_documented_candidate_can_be_the_base_model(tmp_path):
    with pytest.raises(ManifestError):
        run(tmp_path, manifest_dict(), make_rows(40), base_model="some-random-model")
    with pytest.raises(ManifestError):
        run(tmp_path, manifest_dict(), make_rows(40), base_model="rules_baseline")


def test_the_command_line_refuses_without_the_packages_the_targets_or_with_regression(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(train.importlib.util, "find_spec", lambda name: None)
    assert train.main(["--check-environment"]) == 2 and json.loads(capsys.readouterr().out)["missing"] == list(train.REQUIRED_PACKAGES)
    assert train.main(["--with-regression"]) == 2 and "regression head is disabled" in capsys.readouterr().err
    assert train.main(["--manifest", "m.json"]) == 2 and "required arguments missing" in capsys.readouterr().err
    full = ["--manifest", str(tmp_path / "m.json"), "--data", "d.jsonl", "--base-model", "finbert", "--version", "v1", "--revision", "0123456789abcdef0123456789abcdef01234567",
            "--target-precision", "0.9", "--min-coverage", "0.5", "--high-precision", "0.95", "--high-min-coverage", "0.2"]       # the revision is a synthetic hash: nothing is resolved or downloaded
    assert train.main(full) == 2 and "packages are not installed" in capsys.readouterr().err
    monkeypatch.setattr(train.importlib.util, "find_spec", lambda name: object())
    assert train.main(["--check-environment"]) == 0
    write_manifest(tmp_path / "m.json", manifest_dict(development_fixture=False, approved=False))
    assert train.main(full) == 2 and "not approved" in capsys.readouterr().err


def test_importing_the_training_modules_loads_no_deep_learning_package_and_the_backend_never_imports_training():
    code = "import sys, training.sentiment.train_sentiment_transformer, training.sentiment.evaluate_sentiment_model; print(any(m.split('.')[0] in ('torch','transformers','tokenizers','safetensors') for m in sys.modules))"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO_ROOT, timeout=120, env={**__import__("os").environ, "PYTHONPATH": f"{REPO_ROOT}{__import__('os').pathsep}{REPO_ROOT / 'backend'}"})
    assert done.stdout.strip() == "False", done.stderr[-500:]
    for path in (REPO_ROOT / "backend" / "wealthpilot").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "training.sentiment" not in text and "from training import sentiment" not in text, path                      # nothing at request time can start training
    for path in (REPO_ROOT / "training" / "sentiment").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "wealthpilot.api" not in text and "fastapi" not in text, path.name


# ------------------------------------------------------------------------------------------------ evaluating the candidates on the held-out test split


def test_the_rules_baseline_is_evaluated_on_exactly_the_held_out_test_split(tmp_path, dev_data):
    data, manifest_path = dev_data
    manifest = load_manifest(manifest_path, allow_development_fixture=True)
    test, split = evaluate.test_split(manifest, data)
    assert split["test"] == {l: sum(1 for r in test if r.label == l) for l in LABELS} and len(test) == sum(split["test"].values())
    result = evaluate.evaluate_rules_baseline(test)
    assert result["candidate"] == "rules_baseline" and result["samples"] == len(test) and 0.0 <= result["coverage"] <= 1.0
    assert result["abstained"] == round((1 - result["coverage"]) * len(test)) and 0.0 <= result["strict_accuracy_abstention_counts_wrong"] <= 1.0
    train_run = run(tmp_path, manifest_dict(), make_rows(40, group_every=4))
    assert (tmp_path / "out").exists() and train_run["directory"]


def test_the_evaluation_command_writes_a_report_that_makes_no_selection(tmp_path, dev_data, monkeypatch):
    data, manifest_path = dev_data
    monkeypatch.setattr(evaluate, "load_manifest", lambda path: load_manifest(path, allow_development_fixture=True))
    out = tmp_path / "report.json"
    assert evaluate.main(["--manifest", str(manifest_path), "--data", str(data), "--candidate", "rules_baseline", "--output", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["selection"].startswith("not made here") and [c["candidate"] for c in report["candidates"]] == ["rules_baseline"] and report["dataset"]["domain_note"]


def test_a_model_trained_on_another_dataset_is_not_evaluated_on_this_one(tmp_path, dev_data):
    other = tmp_path / "other"
    other.mkdir()
    result = run(other, manifest_dict(dataset_id="another-dataset"), make_rows(40, group_every=4))
    data, manifest_path = dev_data
    manifest = load_manifest(manifest_path, allow_development_fixture=True)
    test, _ = evaluate.test_split(manifest, data)
    with pytest.raises(ManifestError, match="different dataset"):
        evaluate.evaluate_artifact(Path(result["directory"]), test, manifest)
