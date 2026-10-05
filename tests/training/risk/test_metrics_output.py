"""Tests that ModelEvaluation.to_dict() (what train.py writes into
models/metrics.json) is complete and JSON-serializable, and that
write_metrics_json() merges into (rather than clobbers) an existing file."""

import json

from training.risk.common import ModelEvaluation
from training.risk.train import write_metrics_json


def _sample_evaluation() -> ModelEvaluation:
    return ModelEvaluation(
        name="logistic_regression",
        best_params={"classifier__C": 1},
        macro_f1_per_fold=[0.3, 0.31, 0.29, 0.32, 0.30],
        per_class_recall={"Conservative": 0.7, "Income": 0.2, "Balanced": 0.3, "Aggressive": 0.5},
        confusion=[[1, 2], [3, 4]],
        confusion_labels=["Conservative", "Income"],
        calibration={"Conservative": {"prob_true": [0.1, 0.5], "prob_pred": [0.15, 0.55]}},
        fit_time_seconds=12.3,
        library_version="1.5.2",
        class_weight_strategy="class_weight='balanced'",
    )


def test_model_evaluation_to_dict_is_json_serializable():
    evaluation = _sample_evaluation()
    payload = evaluation.to_dict()
    # Must not raise -- every value must be a native JSON-compatible type,
    # not e.g. a numpy float32 or a numpy array.
    serialized = json.dumps(payload)
    reloaded = json.loads(serialized)
    assert reloaded["name"] == "logistic_regression"
    assert reloaded["macro_f1_mean"] == pytest_approx(0.304, abs=1e-9)


def test_write_metrics_json_merges_with_existing_content(tmp_path, monkeypatch):
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"other_module": {"foo": "bar"}}), encoding="utf-8")
    monkeypatch.setattr("training.risk.train.METRICS_PATH", metrics_path)

    evaluation = _sample_evaluation()
    results = {"logistic_regression": (evaluation, None)}

    write_metrics_json(
        results,
        best_name="logistic_regression",
        shap_result={"method": "none", "sample_size": 0, "per_class_mean_abs_shap": {}, "overall_feature_ranking": []},
        saved_paths={"logreg": "models/risk/logreg_v1.pkl"},
        training_population=200,
    )

    reloaded = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert reloaded["other_module"] == {"foo": "bar"}  # untouched
    assert reloaded["risk"]["best_model"] == "logistic_regression"
    assert reloaded["risk"]["training_population"] == 200
    assert reloaded["risk"]["models"]["logistic_regression"]["macro_f1_mean"] == pytest_approx(0.304, abs=1e-9)


def pytest_approx(value, **kwargs):
    import pytest

    return pytest.approx(value, **kwargs)
