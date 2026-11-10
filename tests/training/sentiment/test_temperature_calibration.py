"""Tests for the D13 temperature calibration in `training/sentiment/metrics.py` (owner decision, 2026-10-29): temperature scaling fitted ONLY on the calibration split, applied to held-out predictions
only, 10 equal-width ECE bins reported strict and accepted-only, ECE report-only, descriptive-only below 20 scored examples. Every record here is invented: ids are opaque, there is no text, no model and
no real data."""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from training.sentiment import metrics as m
from training.sentiment.config import LABELS
from training.sentiment.metrics import (EvalRecord, EvaluationPolicy, EvidenceBasis, StatisticsPlan, apply_temperature, evaluation_report, fit_calibration_temperature,
                                        temperature_calibration_report)

PLAN, POLICY = StatisticsPlan.owner_approved(), EvaluationPolicy.owner_approved()
REAL_LOOKING = EvidenceBasis(True, False, False, True, True, True, True, True)           # a unit-level stand-in for approved real evidence: no such dataset exists
SYNTHETIC = EvidenceBasis(True, False, True, True, True, True, True, True)
SECRET = "SECRET-ID"


def probs(peak: str, high: float = 0.9) -> dict[str, float]:
    low = (1.0 - high) / 2
    return {label: (high if label == peak else low) for label in LABELS}


def overconfident(prefix: str, count: int, *, high: float = 0.9, abstain_every: int = 0) -> list[EvalRecord]:
    """Confident at `high` but right only two times in three."""
    out = []
    for i in range(count):
        truth = LABELS[i % 3]
        predicted = truth if i % 3 != 0 else LABELS[(i + 1) % 3]
        abstain = bool(abstain_every) and i % abstain_every == 0
        out.append(EvalRecord(f"{prefix}-{i:04d}", truth, None if abstain else predicted, probs(predicted, high)))
    return out


def fit(records, policy=POLICY):
    return fit_calibration_temperature(records, labels=LABELS, policy=policy)


def report(calibration, heldout, evidence=SYNTHETIC):
    return temperature_calibration_report(calibration, heldout, labels=LABELS, plan=PLAN, evidence=evidence, policy=POLICY)


# ------------------------------------------------------------------------------------------------------------------------------- the fit
def test_the_temperature_is_fitted_on_the_calibration_records_and_is_deterministic():
    first = fit(overconfident("cal", 60))
    assert first["status"] == "fitted" and first["reason"] is None and first["fit_split"] == "calibration"
    assert first["temperature"] > 1.0                                                           # overconfident: the fit cools it down
    assert first["nll_after"] < first["nll_before"] and first["scored"] == first["records"] == 60
    assert fit(overconfident("cal", 60)) == first and fit(list(reversed(overconfident("cal", 60)))) == first      # no random start, no dependence on the order of the records
    assert first["policy_version"] == "d13-temperature-v1" and first["method"] == "temperature_scaling_nll_on_log_probabilities"


def test_exactly_20_scored_examples_are_fitted_and_19_are_descriptive_only():
    twenty, nineteen = fit(overconfident("cal", 20)), fit(overconfident("cal", 19))
    assert twenty["status"] == "fitted" and twenty["temperature"] is not None
    assert nineteen["status"] == "descriptive_only" and nineteen["temperature"] is None and "fewer than 20 scored calibration examples" in nineteen["reason"]
    assert nineteen["scored"] == 19 and nineteen["min_scored"] == 20


def test_records_without_probabilities_are_counted_but_never_fitted_or_invented():
    mixed = overconfident("cal", 19) + [EvalRecord("cal-x", "positive", "positive", None)]
    assert fit(mixed)["scored"] == 19 and fit(mixed)["records"] == 20 and fit(mixed)["status"] == "descriptive_only"          # the label-only record is not a scored example
    nothing = fit([EvalRecord(f"c{i}", "positive", "positive") for i in range(40)])
    assert nothing["status"] == "unavailable" and nothing["temperature"] is None and "none is invented" in nothing["reason"]
    assert fit([])["status"] == "unavailable"


def test_an_abstention_that_carries_probabilities_is_a_scored_calibration_example():
    records = overconfident("cal", 20, abstain_every=4)
    assert sum(r.prediction is None for r in records) == 5 and fit(records)["scored"] == 20 and fit(records)["status"] == "fitted"


def test_a_well_calibrated_set_gets_a_temperature_near_one_and_an_underconfident_set_below_one():
    calibrated = []
    for i in range(300):                                                                          # 90% confident and right exactly nine times in ten
        truth = LABELS[i % 3]
        predicted = truth if i % 10 else LABELS[(i + 1) % 3]
        calibrated.append(EvalRecord(f"c{i}", truth, predicted, probs(predicted, 0.9)))
    assert 0.9 < fit(calibrated)["temperature"] < 1.1
    under = [EvalRecord(f"u{i}", LABELS[i % 3], LABELS[i % 3], probs(LABELS[i % 3], 0.5)) for i in range(60)]            # always right at 50% confidence
    assert fit(under)["temperature"] < 1.0


def test_a_probability_of_zero_stays_zero_and_the_fit_stays_finite():
    records = [EvalRecord(f"z{i}", LABELS[i % 3], LABELS[i % 3], {**{label: 0.0 for label in LABELS}, LABELS[i % 3]: 1.0}) for i in range(30)]
    result = fit(records)
    assert result["status"] == "fitted" and math.isfinite(result["temperature"])
    assert apply_temperature({"positive": 1.0, "negative": 0.0, "neutral": 0.0}, labels=LABELS, temperature=result["temperature"]) == {"positive": 1.0, "negative": 0.0, "neutral": 0.0}


# ------------------------------------------------------------------------------------------------------------------------------- isolation
def test_the_calibration_split_alone_decides_the_temperature_and_the_heldout_records_do_not():
    calibration = overconfident("cal", 60)
    first = report(calibration, overconfident("held", 60))
    second = report(calibration, overconfident("held", 90, high=0.6))                           # a completely different held-out set
    assert first["fit"] == second["fit"] and first["fit"]["temperature"] == fit(calibration)["temperature"]
    other = report(overconfident("cal", 60, high=0.7), overconfident("held", 60))
    assert other["fit"]["temperature"] != first["fit"]["temperature"]                           # a different calibration split gives a different temperature


def test_the_fit_function_is_only_ever_handed_the_calibration_records(monkeypatch):
    seen = []
    original = m.fit_temperature
    monkeypatch.setattr(m, "fit_temperature", lambda scores, truth: (seen.append(len(truth)), original(scores, truth))[1])
    report(overconfident("cal", 40), overconfident("held", 25))
    assert seen == [40]                                                                           # 40 calibration examples, never the 25 held-out ones


def test_overlapping_calibration_and_heldout_ids_are_refused():
    with pytest.raises(ValueError, match="must be disjoint"):
        report(overconfident("same", 30), overconfident("same", 30))


def test_the_temperature_is_applied_to_heldout_probabilities_only_and_never_changes_a_label():
    heldout = overconfident("held", 60, abstain_every=6)
    result = report(overconfident("cal", 60), heldout)
    assert result["status"] == "fitted_and_applied" and result["applied"] is True and result["labels_changed"] is False
    before, after = result["heldout_uncalibrated"], result["heldout_calibrated"]
    assert before["scored"] == after["scored"] == 60 and before["records"] == after["records"]
    assert after["strict"]["ece"] < before["strict"]["ece"]                                       # the overconfident set is cooled
    assert after["accepted_only"]["samples"] == before["accepted_only"]["samples"] == 50          # abstentions stay abstentions
    original = [(r.item_id, r.prediction) for r in heldout]
    report(overconfident("cal", 60), heldout)
    assert [(r.item_id, r.prediction) for r in heldout] == original and next(r for r in heldout if r.prediction).probabilities == probs(next(r for r in heldout if r.prediction).prediction)         # the inputs are not mutated


# ------------------------------------------------------------------------------------------------------------------------------- apply_temperature
def test_apply_temperature_keeps_the_argmax_the_sum_and_moves_confidence_the_right_way():
    p = {"positive": 0.7, "negative": 0.2, "neutral": 0.1}
    identity = apply_temperature(p, labels=LABELS, temperature=1.0)
    assert all(abs(identity[k] - p[k]) < 1e-12 for k in p)
    cooler, sharper = apply_temperature(p, labels=LABELS, temperature=2.0), apply_temperature(p, labels=LABELS, temperature=0.5)
    for scaled in (identity, cooler, sharper):
        assert abs(sum(scaled.values()) - 1.0) < 1e-12 and max(scaled, key=scaled.get) == "positive"
    assert cooler["positive"] < 0.7 < sharper["positive"]
    tie = apply_temperature({"positive": 0.4, "negative": 0.4, "neutral": 0.2}, labels=LABELS, temperature=3.0)
    assert tie["positive"] == tie["negative"] > tie["neutral"]


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf"), 1, "1.0", None])
def test_an_invalid_temperature_is_refused(bad):
    with pytest.raises(ValueError, match="positive finite float"):
        apply_temperature({"positive": 0.7, "negative": 0.2, "neutral": 0.1}, labels=LABELS, temperature=bad)


# ------------------------------------------------------------------------------------------------------------------------------- bins
def calibration_blocks(records):
    return m.calibration_report(records, labels=LABELS, plan=PLAN, evidence=SYNTHETIC, bins=10)


def test_there_are_ten_equal_width_bins_with_the_documented_boundaries():
    block = calibration_blocks(overconfident("b", 30))["strict"]
    assert len(block["bins"]) == 10
    edges = [b["low"] for b in block["bins"]] + [block["bins"][-1]["high"]]
    assert edges == pytest.approx(list(np.linspace(0.0, 1.0, 11))) and POLICY.bins == 10


def test_a_confidence_exactly_on_a_boundary_belongs_to_the_bin_ending_there_and_one_belongs_to_the_last():
    records = [EvalRecord("a", "positive", "positive", {"positive": 0.5, "negative": 0.3, "neutral": 0.2}),
               EvalRecord("b", "positive", "positive", {"positive": 1.0, "negative": 0.0, "neutral": 0.0})]
    bins = calibration_blocks(records)["strict"]["bins"]
    assert bins[4]["count"] == 1 and bins[4]["high"] == pytest.approx(0.5) and bins[9]["count"] == 1 and sum(b["count"] for b in bins) == 2


def test_empty_bins_are_reported_with_none_not_zero_and_the_counts_add_up():
    bins = calibration_blocks(overconfident("e", 30))["strict"]["bins"]
    empty = [b for b in bins if b["count"] == 0]
    assert empty and all(b["accuracy"] is None and b["mean_confidence"] is None and b["accuracy_interval"] is None for b in empty)
    assert sum(b["count"] for b in bins) == 30


def test_strict_and_accepted_only_views_are_both_reported_and_abstentions_leave_only_the_accepted_view():
    block = calibration_blocks(overconfident("s", 40, abstain_every=4))
    assert block["strict"]["samples"] == 40 and block["accepted_only"]["samples"] == 30 and set(block["views"]) == {"strict", "accepted_only"}
    nobody = calibration_blocks([EvalRecord(f"n{i}", "positive", None, probs("positive")) for i in range(25)])
    assert nobody["strict"]["samples"] == 25 and nobody["accepted_only"] is None


def test_below_the_minimum_the_heldout_calibration_is_descriptive_only_and_exactly_the_minimum_is_supported():
    assert calibration_blocks(overconfident("h", 19))["status"] == "descriptive_only"
    assert calibration_blocks(overconfident("h", 20))["status"] == "supported"


# ------------------------------------------------------------------------------------------------------------------------------- invalid probabilities
def broken(**probabilities):
    base = {"positive": 0.7, "negative": 0.2, "neutral": 0.1}
    base.update(probabilities)
    return [EvalRecord(SECRET, "positive", "positive", base)]


@pytest.mark.parametrize("probabilities", [{"positive": float("nan"), "negative": 0.2, "neutral": 0.1}, {"positive": float("inf"), "negative": 0.0, "neutral": 0.0},
                                           {"positive": -0.1, "negative": 0.6, "neutral": 0.5}, {"positive": 1.2, "negative": -0.1, "neutral": -0.1},
                                           {"positive": True, "negative": 0.0, "neutral": 0.0}, {"positive": "0.7", "negative": 0.2, "neutral": 0.1},
                                           {"positive": 0.7, "negative": 0.3}, {"positive": 0.7, "negative": 0.2, "neutral": 0.05, "mixed": 0.05}])
def test_invalid_nan_infinite_or_malformed_probabilities_are_refused_by_the_fit_and_the_report(probabilities):
    records = [EvalRecord(SECRET, "positive", None, probabilities)]
    for run in (lambda: fit(records * 1), lambda: report(overconfident("cal", 25), [EvalRecord(SECRET, "positive", None, probabilities)])):
        with pytest.raises(ValueError, match="exactly one finite value in") as caught:
            run()
        assert SECRET not in str(caught.value) and "nan" not in str(caught.value).lower().replace("finite", "")


def test_probabilities_that_do_not_sum_to_one_are_refused_and_the_tolerance_is_the_existing_one():
    for bad in ({"positive": 0.7, "negative": 0.2, "neutral": 0.2}, {"positive": 0.5, "negative": 0.2, "neutral": 0.1}):
        with pytest.raises(ValueError, match="must sum to 1") as caught:
            fit([EvalRecord(SECRET, "positive", None, bad)])
        assert SECRET not in str(caught.value) and "0.7" not in str(caught.value)
    assert m.PROBABILITY_SUM_TOLERANCE == 1e-3
    fit([EvalRecord("ok", "positive", None, {"positive": 0.7005, "negative": 0.2, "neutral": 0.1})])                           # within 1e-3: accepted


def test_a_predicted_label_that_is_not_the_most_probable_class_is_refused():
    with pytest.raises(ValueError, match="must be the most probable class") as caught:
        fit([EvalRecord(SECRET, "positive", "negative", {"positive": 0.7, "negative": 0.2, "neutral": 0.1})])
    assert SECRET not in str(caught.value)
    with pytest.raises(ValueError, match="must be the most probable class"):
        report(overconfident("cal", 25), [EvalRecord("h", "positive", "neutral", {"positive": 0.7, "negative": 0.2, "neutral": 0.1})])
    with pytest.raises(ValueError, match="must be the most probable class"):
        fit([EvalRecord("u", "positive", "mixed", {"positive": 0.7, "negative": 0.2, "neutral": 0.1})])
    fit([EvalRecord("tie", "positive", "negative", {"positive": 0.4, "negative": 0.4, "neutral": 0.2})])                   # a tie: either tied class is a most-probable class


def test_a_true_label_outside_the_evaluated_labels_is_refused_without_echoing_it():
    with pytest.raises(ValueError, match="true label is not one of the evaluated labels") as caught:
        fit([EvalRecord("x", "SECRET-LABEL", None, {"positive": 0.7, "negative": 0.2, "neutral": 0.1})])
    assert "SECRET-LABEL" not in str(caught.value)


# ------------------------------------------------------------------------------------------------------------------------------- labels-only candidates and the rules baseline
def test_a_labels_only_candidate_is_reported_as_nothing_to_calibrate_and_nothing_changes():
    labels_only = [EvalRecord(f"r{i}", LABELS[i % 3], LABELS[i % 3] if i % 7 else None) for i in range(40)]
    result = report([EvalRecord(f"c{i}", LABELS[i % 3], None) for i in range(40)], labels_only)
    assert result["status"] == "labels_only" and result["applied"] is False and result["heldout_calibrated"] is None and result["fit"]["status"] == "unavailable"
    assert "rules baseline" in result["reason"] and result["labels_changed"] is False and result["heldout_uncalibrated"]["status"] == "no_predictions"


def test_a_probability_bearing_candidate_with_too_few_calibration_examples_is_descriptive_only_and_nothing_is_applied():
    result = report(overconfident("cal", 19), overconfident("held", 60))
    assert result["status"] == "descriptive_only" and result["applied"] is False and result["heldout_calibrated"] is None and result["fit"]["temperature"] is None
    assert result["heldout_uncalibrated"]["status"] == "supported"                                  # the held-out view is still reported, uncalibrated


# ------------------------------------------------------------------------------------------------------------------------------- no validation, no recommendation
def test_the_calibration_report_never_validates_or_recommends_anything():
    result = report(overconfident("cal", 60), overconfident("held", 60), evidence=REAL_LOOKING)
    assert result["validated"] is False and result["activation_recommendation"].startswith("none") and "REPORT_ONLY" in result["ece_gate"]
    assert result["heldout_calibrated"]["confidence_status"]["validated"] is False and result["heldout_uncalibrated"]["confidence_status"]["validated"] is False
    text = json.dumps(result).lower()
    assert "recommend activation" not in text and "enable" not in text.replace("enabl", "") and SECRET.lower() not in text


def perfect_heldout(count_per_class: int = 100) -> list[EvalRecord]:
    return [EvalRecord(f"h{label}-{i:03d}", label, label, probs(label, 0.9)) for label in LABELS for i in range(count_per_class)]


def assessed(fit_result, evidence):
    held = perfect_heldout()
    return evaluation_report(held, labels=LABELS, plan=PLAN, evidence=evidence, policy=POLICY, calibration_fit=fit_result)


def test_a_fitted_temperature_adds_a_reported_gate_and_synthetic_evidence_still_cannot_be_validated():
    fitted = fit(overconfident("cal", 60))
    gate = next(g for g in assessed(fitted, SYNTHETIC)["assessment"]["gates"] if g["gate"] == "temperature_calibration")
    assert gate["status"] == "reported" and gate["observed"] == fitted["temperature"] and "not gated" in gate["reason"]
    assert assessed(fitted, SYNTHETIC)["assessment"]["validation"]["status"] == "not_validation_evidence"                  # synthetic evidence: never validated
    assert assessed(None, SYNTHETIC)["assessment"]["validation"]["status"] == "not_validation_evidence"


def test_without_a_usable_temperature_fit_the_candidate_is_descriptive_only_even_on_eligible_evidence():
    for unusable, status in ((fit(overconfident("cal", 19)), "descriptive_only"), (fit([]), "not_evaluable")):
        result = assessed(unusable, REAL_LOOKING)["assessment"]
        gate = next(g for g in result["gates"] if g["gate"] == "temperature_calibration")
        assert gate["status"] == status and result["validation"]["status"] == "descriptive_only"
    usable = assessed(fit(overconfident("cal", 60)), REAL_LOOKING)["assessment"]["validation"]["unmet_or_missing"]
    assert not any(entry.startswith("temperature_calibration") for entry in usable)                                           # a usable fit leaves that gate complete
    assert any(entry.startswith("temperature_calibration") for entry in assessed(fit([]), REAL_LOOKING)["assessment"]["validation"]["unmet_or_missing"])
    assert "activation_recommendation" in assessed(None, REAL_LOOKING)["assessment"] and assessed(None, REAL_LOOKING)["assessment"]["activation_recommendation"].startswith("none")


def test_the_existing_evaluation_report_is_unchanged_when_no_fit_is_supplied():
    gates = [g["gate"] for g in assessed(None, REAL_LOOKING)["assessment"]["gates"]]
    assert "temperature_calibration" not in gates
