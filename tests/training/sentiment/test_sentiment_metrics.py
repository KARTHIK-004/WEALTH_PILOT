"""ADR-052 -- `training/sentiment/metrics.py`: classification metrics, calibration, abstention-threshold selection and regression metrics, checked against values worked out by hand."""

from __future__ import annotations

import math

import numpy as np
import pytest

from training.sentiment.metrics import (
    classification_report,
    confusion_matrix,
    expected_calibration_error,
    fit_temperature,
    regression_metrics,
    select_min_confidence,
    softmax,
)


def test_the_confusion_matrix_has_true_classes_as_rows():
    assert confusion_matrix([0, 0, 1, 2, 2, 2], [0, 1, 1, 2, 2, 0]) == [[1, 1, 0], [0, 1, 0], [1, 0, 2]]


def test_the_classification_report_matches_a_hand_computation():
    report = classification_report([0, 0, 1, 2, 2, 2], [0, 1, 1, 2, 2, 0])
    assert report["samples"] == 6 and report["accuracy"] == pytest.approx(4 / 6)
    positive, negative, neutral = (report["per_class"][k] for k in ("positive", "negative", "neutral"))
    assert (positive["precision"], positive["recall"], positive["support"]) == (pytest.approx(1 / 2), pytest.approx(1 / 2), 2)
    assert (negative["precision"], negative["recall"]) == (pytest.approx(1 / 2), pytest.approx(1.0))
    assert (neutral["precision"], neutral["recall"]) == (pytest.approx(1.0), pytest.approx(2 / 3))
    f1 = [2 * 0.5 * 0.5 / 1.0, 2 * 0.5 * 1.0 / 1.5, 2 * 1.0 * (2 / 3) / (1 + 2 / 3)]
    assert report["macro_f1"] == pytest.approx(sum(f1) / 3) and report["confusion_matrix"]["rows_are"] == "true"


def test_a_class_that_never_occurs_does_not_divide_by_zero():
    report = classification_report([0, 0, 1], [0, 0, 1])
    assert report["per_class"]["neutral"] == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0}


def test_softmax_rows_sum_to_one_and_temperature_flattens():
    logits = np.array([[2.0, 0.0, -1.0], [0.0, 0.0, 0.0]])
    p = softmax(logits)
    assert p.sum(axis=1) == pytest.approx([1.0, 1.0]) and p[1] == pytest.approx([1 / 3] * 3)
    assert softmax(logits, temperature=5.0)[0].max() < p[0].max()


def test_ece_is_zero_for_a_perfectly_calibrated_set_and_large_for_an_overconfident_one():
    calibrated = np.array([[0.75, 0.25, 0.0]] * 4)
    assert expected_calibration_error(calibrated, [0, 0, 0, 1])["ece"] == pytest.approx(0.0)           # 3 of 4 correct at confidence 0.75
    overconfident = np.array([[0.99, 0.01, 0.0]] * 4)
    result = expected_calibration_error(overconfident, [0, 1, 1, 1])
    assert result["ece"] == pytest.approx(abs(0.25 - 0.99)) and result["reliability"][0]["count"] == 4


def test_temperature_scaling_fixes_an_overconfident_model_and_leaves_a_calibrated_one_alone():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, size=600)
    logits = rng.normal(0, 1, size=(600, 3))
    wrong = rng.random(600) < 0.3                                                            # 30% of the examples carry a misleading, confident logit
    logits[np.arange(600), np.where(wrong, (y + 1) % 3, y)] += 6.0
    temperature = fit_temperature(logits, y)
    assert temperature > 1.5                                                                  # it must cool an overconfident model
    assert expected_calibration_error(softmax(logits, temperature), y)["ece"] < expected_calibration_error(softmax(logits), y)["ece"]
    honest = rng.normal(0, 1, size=(2000, 3))
    labels = np.array([rng.choice(3, p=p) for p in softmax(honest)])
    assert fit_temperature(honest, labels) == pytest.approx(1.0, abs=0.25)


def test_temperature_needs_examples():
    with pytest.raises(ValueError):
        fit_temperature(np.zeros((0, 3)), [])


def test_the_abstention_threshold_is_derived_from_the_owners_targets_never_invented():
    probabilities = np.array([[0.95, 0.03, 0.02]] * 6 + [[0.55, 0.40, 0.05]] * 4)
    y = [0] * 6 + [0, 1, 1, 1]                                                               # the six confident ones are right; of the four unsure ones only one is
    found = select_min_confidence(probabilities, y, target_precision=0.95, min_coverage=0.5)
    assert found["found"] is True and found["min_confidence"] == pytest.approx(0.95) and found["precision_at_threshold"] == 1.0 and found["coverage"] == pytest.approx(0.6)
    assert select_min_confidence(probabilities, y, target_precision=0.95, min_coverage=0.9)["found"] is False        # coverage target cannot be met at that precision
    assert select_min_confidence(probabilities, y, target_precision=1.0, min_coverage=0.1)["found"] is True
    lower = select_min_confidence(probabilities, y, target_precision=0.7, min_coverage=0.5)
    assert lower["min_confidence"] <= found["min_confidence"] and lower["precision_at_threshold"] >= 0.7


def test_regression_metrics_match_a_hand_computation_and_r2_is_null_when_the_target_is_constant():
    m = regression_metrics([0.0, 0.5, -0.5, 1.0], [0.1, 0.4, -0.7, 0.8])
    assert m["samples"] == 4 and m["mae"] == pytest.approx((0.1 + 0.1 + 0.2 + 0.2) / 4) and m["rmse"] == pytest.approx(math.sqrt((0.01 + 0.01 + 0.04 + 0.04) / 4))
    assert m["r2"] == pytest.approx(1 - 0.1 / 1.25) and m["bias"] == pytest.approx((0.1 - 0.1 - 0.2 - 0.2) / 4)
    assert regression_metrics([0.2, 0.2, 0.2], [0.1, 0.2, 0.3])["r2"] is None
    with pytest.raises(ValueError):
        regression_metrics([], [])
    with pytest.raises(ValueError):
        regression_metrics([0.1], [0.1, 0.2])
