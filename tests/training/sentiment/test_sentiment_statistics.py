"""ADR-052 -- the offline EVALUATION STATISTICS in `training/sentiment/metrics.py`, checked against values worked out by hand on tiny invented label lists. No model, dataset, file, network or
user text is involved, and nothing here is evidence about any real classifier: the labels are made up to exercise the arithmetic, which is exactly why the code marks such data
`not_validation_evidence`."""

from __future__ import annotations

import dataclasses
import json
import math
import random

import pytest

from training.sentiment import metrics as m
from training.sentiment.metrics import (
    ABSTAINED,
    EvalRecord,
    EvaluationPolicy,
    EvidenceBasis,
    StatisticsPlan,
    agreement_report,
    calibration_report,
    cohen_kappa,
    compare_predictions,
    evaluate_predictions,
    evaluation_report,
    grouped_report,
    krippendorff_alpha_nominal,
    specific_agreement,
    wilson_interval,
)

LABELS = ("positive", "negative", "neutral")
PLAN = StatisticsPlan(0.95, 200, 42, 20, None, False)              # 200 resamples keep the suite fast; the proposed plan (2,000) is exercised once below
POLICY = EvaluationPolicy.owner_approved()


def basis(approved: bool, fixture: bool, synthetic: bool, complete: bool = False) -> EvidenceBasis:
    """An evidence basis whose five preparation checks (rubric frozen, hashes verified, independence attested, duplicates excluded, splits separate) are all `complete`."""
    return EvidenceBasis(approved, fixture, synthetic, complete, complete, complete, complete, complete)


STAND_IN = basis(False, True, True)


def records(pairs, **extra):
    return [EvalRecord(f"item-{i:04d}", truth, prediction, **extra) for i, (truth, prediction) in enumerate(pairs)]


def worked_example():
    """25 positive (all right); 20 negative (all right); 25 neutral: 5 called positive, 5 abstained, 15 right.  70 examples."""
    return records([("positive", "positive")] * 25 + [("negative", "negative")] * 20 + [("neutral", "positive")] * 5 + [("neutral", None)] * 5 + [("neutral", "neutral")] * 15)


def values(node, path=()):
    """Every numeric leaf of a report, with its path (to look for anything fabricated)."""
    if isinstance(node, dict):
        for key, child in node.items():
            yield from values(child, (*path, key))
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from values(child, (*path, i))
    else:
        yield path, node


# ------------------------------------------------------------------------------------------------------------------------------- perfect and imperfect predictions
def test_a_perfect_candidate_has_accuracy_and_macro_f1_of_one_and_degenerate_bootstrap_intervals():
    report = evaluate_predictions(records([("positive", "positive")] * 15 + [("negative", "negative")] * 15), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    strict = report["overall"]["strict"]
    assert strict["accuracy"]["value"] == 1.0 and strict["accuracy"]["interval"]["high"] == 1.0
    assert strict["macro_f1"]["value"] == 1.0 and (strict["macro_f1"]["interval"]["low"], strict["macro_f1"]["interval"]["high"]) == (1.0, 1.0)
    assert report["overall"]["coverage"]["abstained"] == 0 and report["status"] == "supported"          # 30 examples is at or above the minimum group support of 20


def test_the_worked_example_matches_a_hand_computation():
    report = evaluate_predictions(worked_example(), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    overall = report["overall"]
    assert report["samples"] == 70 and report["status"] == "supported"
    assert overall["strict"]["accuracy"]["value"] == pytest.approx(60 / 70)
    assert overall["strict"]["macro_f1"]["value"] == pytest.approx((50 / 55 + 1.0 + 30 / 40) / 3)            # abstentions are misses: neutral recall is 15/25
    assert overall["selective"]["accepted_precision"]["value"] == pytest.approx(60 / 65)
    assert overall["selective"]["macro_f1"]["value"] == pytest.approx((50 / 55 + 1.0 + 30 / 35) / 3)         # accepted predictions only: neutral support is 20
    per_class = report["per_class"]
    assert per_class["positive"]["precision"]["value"] == pytest.approx(25 / 30) and per_class["positive"]["recall"]["value"] == 1.0
    assert per_class["neutral"]["precision"]["value"] == 1.0 and per_class["neutral"]["recall"]["value"] == pytest.approx(15 / 25)
    assert per_class["neutral"]["precision"]["numerator"] == 15 and per_class["neutral"]["precision"]["denominator"] == 15
    assert report["confusion_matrix"]["columns"] == [*LABELS, ABSTAINED]
    assert report["confusion_matrix"]["matrix"] == [[25, 0, 0, 0], [0, 20, 0, 0], [5, 0, 15, 5]]


def test_intervals_surround_their_point_estimates_and_stay_inside_the_unit_interval():
    report = evaluate_predictions(worked_example(), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    nodes = [report["overall"]["strict"]["accuracy"], report["overall"]["strict"]["macro_f1"], report["overall"]["selective"]["accepted_precision"], report["overall"]["coverage"]["coverage"],
             *(report["per_class"][label][key] for label in LABELS for key in ("precision", "recall", "f1"))]
    for node in nodes:
        low, high = node["interval"]["low"], node["interval"]["high"]
        assert 0.0 <= low <= node["value"] <= high <= 1.0


# ------------------------------------------------------------------------------------------------------------------------------- abstentions
def test_abstention_is_a_miss_in_the_strict_view_and_invisible_in_the_selective_view_and_coverage_is_reported_beside_it():
    report = evaluate_predictions(worked_example(), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    coverage = report["overall"]["coverage"]
    assert (coverage["answered"], coverage["abstained"]) == (65, 5)
    assert coverage["coverage"]["value"] == pytest.approx(65 / 70) and coverage["abstention_rate"]["value"] == pytest.approx(5 / 70)
    assert report["overall"]["strict"]["accuracy"]["value"] < report["overall"]["selective"]["accepted_precision"]["value"]
    assert report["per_class"]["neutral"]["precision"]["denominator"] == 15          # an abstention is not a prediction, so precision does not move


def test_a_candidate_that_abstains_on_everything_has_no_accepted_precision_and_no_selective_macro_f1_rather_than_a_default():
    report = evaluate_predictions(records([("positive", None)] * 12 + [("negative", None)] * 12), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    selective = report["overall"]["selective"]
    assert selective["accepted_precision"]["value"] is None and selective["accepted_precision"]["unavailable_reason"]
    assert selective["macro_f1"]["value"] is None and selective["macro_f1"]["unavailable_reason"] == "the candidate answered nothing"
    assert report["overall"]["strict"]["accuracy"]["value"] == 0.0 and report["overall"]["coverage"]["coverage"]["value"] == 0.0


# ------------------------------------------------------------------------------------------------------------------------------- empty, one-class, undersized
def test_empty_input_is_no_data_and_contains_no_number():
    report = evaluate_predictions([], labels=LABELS, plan=PLAN, evidence=STAND_IN)
    assert report["status"] == "no_data" and report["samples"] == 0 and "overall" not in report and "per_class" not in report
    assert grouped_report([], labels=LABELS, plan=PLAN, evidence=STAND_IN)["groups"] == {}
    calibration = calibration_report([], labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)
    assert calibration["status"] == "no_predictions" and "strict" not in calibration and calibration["confidence_status"]["validated"] is False
    comparison = compare_predictions([], [], [], labels=LABELS, plan=PLAN, evidence=STAND_IN, first_name="model", second_name="rules")
    assert comparison["status"] == "no_data" and "difference_first_minus_second" not in comparison
    assert cohen_kappa([], [], LABELS)["kappa"] is None and cohen_kappa([], [], LABELS)["unavailable_reason"]


def test_a_one_class_sample_reports_accuracy_but_no_macro_f1():
    report = evaluate_predictions(records([("positive", "positive")] * 25), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    assert report["overall"]["strict"]["accuracy"]["value"] == 1.0
    macro = report["overall"]["strict"]["macro_f1"]
    assert macro["value"] is None and "fewer than two true classes" in macro["unavailable_reason"]
    assert report["per_class"]["negative"]["support"] == 0 and report["per_class"]["negative"]["recall"]["value"] is None and report["per_class"]["negative"]["recall"]["unavailable_reason"]


def test_a_class_never_true_and_never_predicted_has_no_f1_but_one_predicted_without_support_has_f1_zero():
    never = evaluate_predictions(records([("positive", "positive")] * 20 + [("negative", "negative")] * 20), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    assert never["per_class"]["neutral"]["f1"]["value"] is None
    wrong = evaluate_predictions(records([("positive", "positive")] * 20 + [("negative", "neutral")] * 20), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    assert wrong["per_class"]["neutral"]["f1"]["value"] == 0.0 and wrong["per_class"]["neutral"]["precision"]["value"] == 0.0


def test_the_minimum_support_boundary_is_inclusive_and_an_undersized_sample_has_no_intervals():
    at = evaluate_predictions(records([("positive", "positive")] * 10 + [("negative", "negative")] * 10), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    below = evaluate_predictions(records([("positive", "positive")] * 10 + [("negative", "negative")] * 9), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    assert at["status"] == "supported" and at["overall"]["strict"]["accuracy"]["interval"] is not None
    assert below["status"] == "descriptive_only" and below["interval_withheld_reason"]
    for node in (below["overall"]["strict"]["accuracy"], below["overall"]["strict"]["macro_f1"], below["per_class"]["positive"]["precision"], below["overall"]["coverage"]["coverage"]):
        assert node["interval"] is None and node["interval_withheld_reason"]
    assert below["overall"]["strict"]["accuracy"]["value"] == 1.0                      # the descriptive value itself is still reported


def test_group_support_is_reported_explicitly_and_a_required_but_absent_group_is_listed_as_no_data():
    recs = [EvalRecord(f"a-{i:03d}", "positive" if i % 2 else "negative", "positive" if i % 2 else "negative", groups={"topic": ("saving",) if i < 40 else ("saving", "debt"),
                                                                                                                       "difficulty": ("hard",) if i < 5 else ("easy",)}) for i in range(60)]
    report = grouped_report(recs, labels=LABELS, plan=PLAN, evidence=STAND_IN, required_groups={"language": ["unsupported"]})
    assert list(report["groups"]) == ["difficulty", "language", "topic"] and list(report["groups"]["topic"]) == ["debt", "saving"]
    assert report["groups"]["difficulty"]["hard"]["status"] == "descriptive_only" and report["groups"]["difficulty"]["hard"]["samples"] == 5
    assert report["groups"]["difficulty"]["easy"]["status"] == "supported"
    assert report["groups"]["topic"]["debt"]["samples"] == 20 and report["groups"]["topic"]["debt"]["status"] == "supported"          # exactly the minimum
    assert report["groups"]["topic"]["saving"]["samples"] == 60
    assert report["groups"]["language"]["unsupported"]["status"] == "no_data"
    assert report["groups_not_supported"] == ["difficulty=hard (descriptive_only, n=5)", "language=unsupported (no_data, n=0)"]
    assert report["groups"]["difficulty"]["hard"]["overall"]["strict"]["accuracy"]["interval"] is None


def test_a_bare_string_group_value_is_refused_instead_of_being_split_into_characters():
    with pytest.raises(ValueError, match="tuple of strings"):
        grouped_report([EvalRecord("x", "positive", "positive", groups={"topic": "saving"})], labels=LABELS, plan=PLAN, evidence=STAND_IN)


# ------------------------------------------------------------------------------------------------------------------------------- determinism and ordering
def test_the_report_is_identical_across_runs_and_independent_of_input_order():
    base = worked_example()
    shuffled = base[:]
    random.Random(7).shuffle(shuffled)
    first = json.dumps(evaluate_predictions(base, labels=LABELS, plan=PLAN, evidence=STAND_IN))
    assert first == json.dumps(evaluate_predictions(base, labels=LABELS, plan=PLAN, evidence=STAND_IN))
    assert first == json.dumps(evaluate_predictions(shuffled, labels=LABELS, plan=PLAN, evidence=STAND_IN))
    grouped = [dataclasses.replace(r, groups={"topic": ("saving", "debt"), "difficulty": ("hard",)}) for r in base]
    assert json.dumps(grouped_report(grouped, labels=LABELS, plan=PLAN, evidence=STAND_IN)) == json.dumps(grouped_report(grouped[::-1], labels=LABELS, plan=PLAN, evidence=STAND_IN))


def test_the_seed_changes_only_the_bootstrap_intervals_never_the_point_estimates():
    a = evaluate_predictions(worked_example(), labels=LABELS, plan=PLAN, evidence=STAND_IN)["overall"]["strict"]["macro_f1"]
    b = evaluate_predictions(worked_example(), labels=LABELS, plan=dataclasses.replace(PLAN, seed=7), evidence=STAND_IN)["overall"]["strict"]["macro_f1"]
    assert a["value"] == b["value"] and a["interval"] != b["interval"] and (a["interval"]["seed"], b["interval"]["seed"]) == (42, 7)


def test_duplicate_item_ids_and_unknown_labels_are_errors_not_silent_classes():
    with pytest.raises(ValueError, match="unique"):
        evaluate_predictions([EvalRecord("x", "positive", "positive"), EvalRecord("x", "negative", "negative")], labels=LABELS, plan=PLAN, evidence=STAND_IN)
    with pytest.raises(ValueError, match="true label"):
        evaluate_predictions([EvalRecord("x", "mixed", "positive")], labels=LABELS, plan=PLAN, evidence=STAND_IN)
    with pytest.raises(ValueError, match="predicted label"):
        evaluate_predictions([EvalRecord("x", "positive", "mixed")], labels=LABELS, plan=PLAN, evidence=STAND_IN)
    with pytest.raises(ValueError, match="labels"):
        evaluate_predictions([], labels=("positive", "positive"), plan=PLAN, evidence=STAND_IN)
    with pytest.raises(ValueError, match="labels"):
        evaluate_predictions([], labels=("positive", ABSTAINED), plan=PLAN, evidence=STAND_IN)


# ------------------------------------------------------------------------------------------------------------------------------- confidence-interval boundaries
def test_the_wilson_interval_matches_known_values_and_its_boundaries_are_exact():
    middle = wilson_interval(50, 100, 0.95)
    assert middle["low"] == pytest.approx(0.4038, abs=5e-4) and middle["high"] == pytest.approx(0.5962, abs=5e-4)
    all_right = wilson_interval(10, 10, 0.95)
    assert all_right["high"] == 1.0 and all_right["low"] == pytest.approx(0.7225, abs=5e-4)
    none_right = wilson_interval(0, 10, 0.95)
    assert none_right["low"] == 0.0 and none_right["high"] == pytest.approx(0.2775, abs=5e-4)
    assert wilson_interval(0, 0, 0.95) is None
    assert wilson_interval(3, 10, 0.99)["low"] < wilson_interval(3, 10, 0.90)["low"] < 0.3 < wilson_interval(3, 10, 0.90)["high"] < wilson_interval(3, 10, 0.99)["high"]
    for bad in ((-1, 5), (6, 5), (1, -1)):
        with pytest.raises(ValueError):
            wilson_interval(*bad, 0.95)


def test_the_plan_validates_every_choice_and_approved_is_refused_for_any_value_but_the_owners():
    approved = StatisticsPlan.owner_approved()
    assert (approved.confidence, approved.resamples, approved.seed, approved.min_group_support, approved.min_class_support, approved.approved) == (0.95, 2000, 42, 20, 75, True)
    described = approved.describe()
    assert described["status"] == "approved by the owner (2026-10-29)" and described["min_class_support"] == 75
    assert "non-stratified item bootstrap" in described["interval_methods"]["kappa"] and "stratified by true label" in described["interval_methods"]["f1_and_paired_differences"]
    hand_built = PLAN.describe()
    assert "NOT the owner-approved plan" in hand_built["status"] and "not set" in hand_built["min_class_support"]
    for bad in (dict(confidence=0.0), dict(confidence=1.0), dict(confidence=95), dict(resamples=10), dict(seed=True), dict(min_group_support=0), dict(min_class_support=0), dict(approved="yes")):
        with pytest.raises(ValueError):
            StatisticsPlan(**{**dataclasses.asdict(PLAN), **bad})
    for tampered in (dict(resamples=2001), dict(confidence=0.9), dict(min_class_support=74), dict(min_class_support=None), dict(seed=7), dict(min_group_support=19)):
        with pytest.raises(ValueError, match="approved=True"):
            StatisticsPlan(**{**dataclasses.asdict(approved), **tampered})
    full = evaluate_predictions(worked_example(), labels=LABELS, plan=approved, evidence=STAND_IN)
    assert full["plan"]["resamples"] == 2000 and full["overall"]["strict"]["macro_f1"]["interval"]["resamples"] == 2000


def test_an_undersized_class_is_flagged_only_when_a_class_threshold_is_set():
    unset = evaluate_predictions(worked_example(), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    assert all(entry["undersized"] is None for entry in unset["per_class"].values()) and "not set" in unset["plan"]["min_class_support"]
    flagged = evaluate_predictions(worked_example(), labels=LABELS, plan=dataclasses.replace(PLAN, min_class_support=22), evidence=STAND_IN)
    assert {label: entry["undersized"] for label, entry in flagged["per_class"].items()} == {"positive": False, "negative": True, "neutral": False}
    approved = evaluate_predictions(worked_example(), labels=LABELS, plan=StatisticsPlan.owner_approved(), evidence=STAND_IN)
    assert {label: entry["undersized"] for label, entry in approved["per_class"].items()} == {"positive": True, "negative": True, "neutral": True}          # 25, 20 and 25 are all below the approved 75


# ------------------------------------------------------------------------------------------------------------------------------- annotator agreement
def test_cohen_kappa_matches_the_textbook_hand_computation():
    first = ["positive"] * 20 + ["positive"] * 5 + ["negative"] * 10 + ["negative"] * 15
    second = ["positive"] * 20 + ["negative"] * 5 + ["positive"] * 10 + ["negative"] * 15
    result = cohen_kappa(first, second, LABELS)
    assert result["observed_agreement"] == pytest.approx(0.7) and result["expected_agreement"] == pytest.approx(0.5) and result["kappa"] == pytest.approx(0.4)
    assert cohen_kappa(["positive", "negative"], ["positive", "negative"], LABELS)["kappa"] == 1.0
    assert cohen_kappa(["positive", "negative"], ["negative", "positive"], LABELS)["kappa"] == -1.0


def test_kappa_is_undefined_not_defaulted_when_chance_agreement_is_one_and_unlabelled_items_are_excluded():
    same = cohen_kappa(["positive"] * 5, ["positive"] * 5, LABELS)
    assert same["kappa"] is None and "undefined" in same["unavailable_reason"] and same["observed_agreement"] == 1.0
    partial = cohen_kappa(["positive", None, "negative", "positive"], ["positive", "negative", None, "negative"], LABELS)
    assert (partial["items"], partial["compared"], partial["excluded_unlabelled"]) == (4, 2, 2)
    with pytest.raises(ValueError):
        cohen_kappa(["positive"], ["positive", "negative"], LABELS)
    with pytest.raises(ValueError, match="not one of the labels"):
        cohen_kappa(["mixed"], ["positive"], LABELS)


def test_krippendorff_alpha_matches_the_hand_computation_and_handles_missing_ratings():
    result = krippendorff_alpha_nominal([("positive", "positive"), ("positive", "negative"), ("negative", "negative")], LABELS)
    assert result["alpha"] == pytest.approx(1 - 10 / 18)
    assert krippendorff_alpha_nominal([("positive", "positive"), ("negative", "negative")], LABELS)["alpha"] == 1.0
    sparse = krippendorff_alpha_nominal([("positive", None), ("positive", "positive"), (None, None), ("negative", "negative"), ("positive", "negative", "negative")], LABELS)
    assert (sparse["units"], sparse["units_used"], sparse["units_excluded"]) == (5, 3, 2) and sparse["alpha"] is not None
    undefined = krippendorff_alpha_nominal([("positive", "positive")] * 4, LABELS)
    assert undefined["alpha"] is None and undefined["unavailable_reason"]
    assert krippendorff_alpha_nominal([], LABELS)["alpha"] is None


def test_specific_agreement_is_per_label_and_none_for_an_unused_label():
    result = specific_agreement(["positive", "positive", "negative", "negative"], ["positive", "negative", "negative", "negative"], LABELS)
    assert result["positive"]["agreement"] == pytest.approx(2 * 1 / 3) and result["negative"]["agreement"] == pytest.approx(2 * 2 / 5)
    assert result["neutral"]["agreement"] is None and result["neutral"]["unavailable_reason"]


def test_the_agreement_report_orders_pairs_by_name_withholds_intervals_when_small_and_refuses_unequal_ratings():
    a = ["positive", "negative"] * 15
    b = ["positive", "negative", "negative", "negative"] + ["positive", "negative"] * 13
    c = ["negative", "positive"] * 15
    report = agreement_report({"zed": a, "amy": b, "bob": c}, labels=LABELS, plan=PLAN, policy=POLICY)
    assert report["annotators"] == ["amy", "bob", "zed"] and list(report["pairs"]) == ["amy | bob", "amy | zed", "bob | zed"] and report["items"] == 30
    assert report["pairs"]["bob | zed"]["kappa"] == -1.0 and report["pairs"]["amy | zed"]["kappa_interval"]["low"] <= report["pairs"]["amy | zed"]["kappa"] <= report["pairs"]["amy | zed"]["kappa_interval"]["high"]
    assert report["krippendorff_alpha"]["units_used"] == 30
    small = agreement_report({"a": a[:10], "b": b[:10]}, labels=LABELS, plan=PLAN, policy=POLICY)
    assert small["pairs"]["a | b"]["kappa_interval"] is None and small["pairs"]["a | b"]["interval_withheld_reason"]
    with pytest.raises(ValueError, match="same items"):
        agreement_report({"a": a[:10], "b": b[:11]}, labels=LABELS, plan=PLAN, policy=POLICY)
    with pytest.raises(ValueError, match="two annotators"):
        agreement_report({"a": a}, labels=LABELS, plan=PLAN, policy=POLICY)
    assert json.dumps(report) == json.dumps(agreement_report({"bob": c, "amy": b, "zed": a}, labels=LABELS, plan=PLAN, policy=POLICY))


# ------------------------------------------------------------------------------------------------------------------------------- calibration
def scored(confidence, correct, truth="positive"):
    """A record whose top-class confidence is `confidence`; if not `correct`, the top class is the wrong one."""
    top = truth if correct else ("negative" if truth == "positive" else "positive")
    rest = (1 - confidence) / 2
    probabilities = {label: (confidence if label == top else rest) for label in LABELS}
    return probabilities, top


def calibration_records():
    out = []
    for i in range(10):
        probabilities, top = scored(0.9, correct=i < 8)                 # 10 at confidence 0.9, 8 right
        out.append(EvalRecord(f"c-{i:03d}", "positive", top, probabilities))
    for i in range(10):
        probabilities, top = scored(0.6, correct=i < 6)                 # 10 at confidence 0.6, 6 right
        out.append(EvalRecord(f"d-{i:03d}", "positive", top if i != 9 else None, probabilities))      # one of them abstained
    return out


def test_calibration_bins_and_ece_match_a_hand_computation():
    report = calibration_report(calibration_records(), labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)
    block = report["strict"]
    assert report["scored"] == 20 and block["samples"] == 20 and len(block["bins"]) == 10
    assert block["ece"] == pytest.approx(0.5 * abs(0.8 - 0.9) + 0.5 * abs(0.6 - 0.6))
    by_low = {round(b["low"], 1): b for b in block["bins"]}
    assert by_low[0.8]["count"] == 10 and by_low[0.8]["accuracy"] == pytest.approx(0.8) and by_low[0.5]["count"] == 10 and by_low[0.5]["accuracy"] == pytest.approx(0.6)
    assert by_low[0.0]["count"] == 0 and by_low[0.0]["accuracy"] is None and by_low[0.0]["mean_confidence"] is None
    assert sum(b["count"] / 20 * abs(b["accuracy"] - b["mean_confidence"]) for b in block["bins"] if b["count"]) == pytest.approx(block["ece"])
    assert all(b["sparse"] and b["accuracy_interval"] is None for b in block["bins"])                      # 10 per bin is below the minimum support of 20
    assert [b["low"] for b in block["bins"]] == sorted(b["low"] for b in block["bins"])


def test_calibration_over_accepted_predictions_only_and_a_well_supported_bin_gets_a_wilson_interval():
    report = calibration_report(calibration_records(), labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)
    assert report["accepted_only"]["samples"] == 19
    big = [EvalRecord(f"e-{i:03d}", "positive", scored(0.9, i < 27)[1], scored(0.9, i < 27)[0]) for i in range(30)]
    block = calibration_report(big, labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)["strict"]
    filled = next(b for b in block["bins"] if b["count"])
    assert not filled["sparse"] and filled["accuracy_interval"]["low"] < 0.9 < filled["accuracy_interval"]["high"] and block["ece"] == pytest.approx(0.0)


def test_a_perfectly_confident_and_correct_model_has_zero_ece_and_nothing_is_ever_called_validated():
    perfect = [EvalRecord(f"p-{i:03d}", "positive", "positive", {"positive": 1.0, "negative": 0.0, "neutral": 0.0}) for i in range(25)]
    report = calibration_report(perfect, labels=LABELS, plan=PLAN, evidence=basis(True, False, False, True), bins=10)
    assert report["strict"]["ece"] == 0.0 and report["confidence_status"]["validated"] is False and report["evidence"]["confidence_scores_validated"] is False


def test_calibration_with_no_probabilities_or_no_accepted_prediction_reports_that_instead_of_a_number():
    without = calibration_report([EvalRecord("a", "positive", "positive"), EvalRecord("b", "negative", None)], labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)
    assert without["status"] == "no_predictions" and without["without_probabilities"] == 2 and "strict" not in without
    only_abstained = [EvalRecord(f"x-{i}", "positive", None, scored(0.7, True)[0]) for i in range(5)]
    report = calibration_report(only_abstained, labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)
    assert report["strict"]["samples"] == 5 and report["accepted_only"] is None
    mixed = calibration_report([EvalRecord("a", "positive", "positive", scored(0.7, True)[0]), EvalRecord("b", "positive", "positive")], labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)
    assert (mixed["scored"], mixed["without_probabilities"]) == (1, 1)


def test_malformed_probabilities_are_errors_not_repaired():
    for bad in ({"positive": 0.5, "negative": 0.5}, {"positive": 0.9, "negative": 0.9, "neutral": 0.9}, {"positive": 1.5, "negative": -0.25, "neutral": -0.25}, {"positive": float("nan"), "negative": 0.5, "neutral": 0.5}):
        with pytest.raises(ValueError):
            calibration_report([EvalRecord("a", "positive", "positive", bad)], labels=LABELS, plan=PLAN, evidence=STAND_IN, bins=10)


# ------------------------------------------------------------------------------------------------------------------------------- rules versus model
def comparison_inputs():
    truth = ["positive"] * 20 + ["negative"] * 20
    wrong = {"positive": "negative", "negative": "positive"}
    model = [t if i < 35 else wrong[t] for i, t in enumerate(truth)]                    # right on items 0-34
    rules = [t if 10 <= i < 36 else (None if i % 2 else wrong[t]) for i, t in enumerate(truth)]       # right on items 10-35, abstains on odd wrong items
    return truth, model, rules


def test_the_comparison_reports_discordance_and_a_paired_difference_with_an_interval_and_no_winner():
    truth, model, rules = comparison_inputs()
    report = compare_predictions(truth, model, rules, labels=LABELS, plan=PLAN, evidence=STAND_IN, first_name="model", second_name="rules")
    assert report["samples"] == 40 and report["status"] == "supported"
    assert report["discordance"] == {"both_correct": 25, "only_model_correct": 10, "only_rules_correct": 1, "both_wrong_or_abstained": 4, "meaning": "an abstention is wrong"}
    difference = report["difference_first_minus_second"]
    assert difference["strict_accuracy"]["value"] == pytest.approx(35 / 40 - 26 / 40) and difference["coverage"]["value"] == pytest.approx(1.0 - 34 / 40 + 0.0, abs=0.2)
    assert difference["strict_accuracy"]["interval"]["low"] <= 0.225 <= difference["strict_accuracy"]["interval"]["high"]
    assert difference["strict_accuracy"]["interval_excludes_zero"] in (True, False)
    assert report["candidates"]["rules"]["overall"]["coverage"]["abstained"] == 7
    assert report["candidates"]["model"]["overall"]["coverage"]["abstained"] == 0
    forbidden = {"p_value", "pvalue", "significant", "winner", "better", "best", "rank"}
    assert not forbidden & {str(part).lower() for path, _ in values(report) for part in path}


def test_the_comparison_reverses_its_sign_with_the_candidates_and_is_deterministic():
    truth, model, rules = comparison_inputs()
    forward = compare_predictions(truth, model, rules, labels=LABELS, plan=PLAN, evidence=STAND_IN, first_name="model", second_name="rules")
    backward = compare_predictions(truth, rules, model, labels=LABELS, plan=PLAN, evidence=STAND_IN, first_name="rules", second_name="model")
    assert forward["difference_first_minus_second"]["strict_accuracy"]["value"] == pytest.approx(-backward["difference_first_minus_second"]["strict_accuracy"]["value"])
    assert json.dumps(forward) == json.dumps(compare_predictions(truth, model, rules, labels=LABELS, plan=PLAN, evidence=STAND_IN, first_name="model", second_name="rules"))
    with pytest.raises(ValueError, match="different names"):
        compare_predictions(truth, model, rules, labels=LABELS, plan=PLAN, evidence=STAND_IN, first_name="x", second_name="x")


def test_a_small_comparison_is_descriptive_only_with_no_difference_interval():
    small = compare_predictions(["positive", "negative"] * 5, ["positive", "negative"] * 5, [None, "negative"] * 5, labels=LABELS, plan=PLAN, evidence=STAND_IN, first_name="m", second_name="r")
    assert small["status"] == "descriptive_only"
    assert small["difference_first_minus_second"]["strict_accuracy"]["value"] == pytest.approx(0.5) and small["difference_first_minus_second"]["strict_accuracy"]["interval"] is None
    assert small["difference_first_minus_second"]["strict_accuracy"]["interval_withheld_reason"]


# ------------------------------------------------------------------------------------------------------------------------------- no fabricated evidence
@pytest.mark.parametrize("evidence,status", [(basis(False, False, False, True), "not_validation_evidence"), (basis(True, True, False, True), "not_validation_evidence"),
                                              (basis(True, False, True, True), "not_validation_evidence"), (basis(False, True, True, True), "not_validation_evidence"),
                                              (basis(True, False, False, False), "not_validation_evidence"), (basis(True, False, False, True), "eligible_for_owner_review")])
def test_only_a_fully_prepared_approved_non_fixture_non_synthetic_dataset_is_even_eligible_for_review(evidence, status):
    described = evidence.describe()
    assert described["status"] == status and described["validation_claimed"] is False and described["confidence_scores_validated"] is False and "R14" in described["activation"]
    assert bool(described["reasons"]) == (status == "not_validation_evidence")
    report = evaluate_predictions(worked_example(), labels=LABELS, plan=PLAN, evidence=evidence)
    assert report["evidence"] == described


def test_no_report_enables_ranks_or_selects_a_model_and_stand_in_data_is_never_called_validated():
    stand_in = evaluation_report(worked_example(), labels=LABELS, plan=PLAN, evidence=STAND_IN, policy=POLICY,
                                 agreement=agreement_report({"a": ["positive", "negative"] * 15, "b": ["positive", "negative"] * 15}, labels=LABELS, plan=PLAN, policy=POLICY))
    assert stand_in["assessment"]["validation"]["status"] == "not_validation_evidence"
    for report in (stand_in, agreement_report({"a": ["positive", "negative"] * 15, "b": ["positive", "negative"] * 15}, labels=LABELS, plan=PLAN, policy=POLICY)):
        for path, value in values(report):
            keys = {str(part).lower() for part in path}
            assert not keys & {"activate", "activation_ready", "approved_for_activation", "winner", "best", "rank", "p_value", "significant"}, path
            if keys & {"validated", "validation_claimed", "confidence_scores_validated"}:
                assert value is False, path


def test_every_unavailable_number_is_none_with_a_reason_and_never_nan_or_zero():
    report = evaluate_predictions(records([("positive", "positive")] * 12 + [("negative", None)] * 12), labels=LABELS, plan=PLAN, evidence=STAND_IN)
    for path, value in values(report):
        assert not (isinstance(value, float) and math.isnan(value)), path
    neutral = report["per_class"]["neutral"]
    assert neutral["precision"]["value"] is None and neutral["precision"]["unavailable_reason"] and neutral["recall"]["value"] is None and neutral["f1"]["value"] is None
    assert json.loads(json.dumps(report)) == report                                                           # plain JSON: no numpy scalars, no NaN


def test_the_module_adds_no_dependency_and_does_not_touch_the_network_or_files():
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(m.__file__).read_text(encoding="utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported <= {"__future__", "math", "dataclasses", "statistics", "typing", "numpy", "training"}, imported
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not {"open", "print", "socket", "requests", "urllib"} & names


def test_the_older_classification_report_is_unchanged_and_still_returns_zero_for_an_undefined_precision():
    old = m.classification_report([0, 0, 1], [0, 0, 0])
    assert old["per_class"]["negative"]["precision"] == 0.0 and old["samples"] == 3           # kept for the training pipeline; evidence reports use the new functions
