"""ADR-052 -- the owner-approved evaluation POLICY (2026-10-29) in `training/sentiment/metrics.py`: `EvaluationPolicy`, `assess_against_policy` and the validation wording.

Everything here is invented label lists that exercise the gate logic. The `EvidenceBasis` flags are stated by the test (the code takes them as given), so the one scenario that reaches `validated` is a
LOGIC test of the gate arithmetic, not evidence about any classifier. The gates are evaluated and printed; nothing here enables, ranks or selects a model."""

from __future__ import annotations

import dataclasses

import pytest

from training.sentiment.metrics import (
    VALIDATION_WORDS,
    EvalRecord,
    EvaluationPolicy,
    EvidenceBasis,
    StatisticsPlan,
    agreement_report,
    assess_against_policy,
    calibration_report,
    evaluate_predictions,
    evaluation_report,
)

LABELS = ("positive", "negative", "neutral")
POLICY = EvaluationPolicy.owner_approved()
APPROVED_PLAN = StatisticsPlan.owner_approved()
HAND_PLAN = StatisticsPlan(0.95, 200, 42, 20, 75, False)          # fast; carries no approval, so only the gates that do not depend on the plan's approval are asserted with it
COMPLETE = EvidenceBasis(True, False, False, True, True, True, True, True)


def probabilities(top: str, confidence: float) -> dict[str, float]:
    rest = (1 - confidence) / 2
    return {label: (confidence if label == top else rest) for label in LABELS}


def scenario(*, correct: int = 92, wrong: int = 0, abstain: int = 8, per_class: int | None = None, classes: tuple[str, ...] = LABELS) -> list[EvalRecord]:
    """For every class: `correct` right answers, `wrong` answers given as the next class, `abstain` declined; `per_class` is checked against their sum."""
    assert per_class is None or per_class == correct + wrong + abstain
    out = []
    for c_index, label in enumerate(classes):
        other = classes[(c_index + 1) % len(classes)]
        for i in range(correct + wrong + abstain):
            if i < correct:
                prediction, top = label, label
            elif i < correct + wrong:
                prediction, top = other, other
            else:
                prediction, top = None, label
            out.append(EvalRecord(f"{label}-{i:04d}", label, prediction, probabilities(top, 0.9 if prediction else 0.5)))
    return out


def annotators(records: list[EvalRecord], flip_every: int = 10) -> dict[str, list[str]]:
    truth = [r.truth for r in sorted(records, key=lambda r: r.item_id)]
    second = [(LABELS[(LABELS.index(t) + 1) % 3] if i % flip_every == 0 else t) for i, t in enumerate(truth)]
    return {"annotator-a": truth, "annotator-b": second}


def run(records, *, plan=HAND_PLAN, evidence=COMPLETE, policy=POLICY, with_agreement=True, with_calibration=True):
    summary = evaluate_predictions(records, labels=LABELS, plan=plan, evidence=evidence)
    calibration = calibration_report(records, labels=LABELS, plan=plan, evidence=evidence, bins=policy.bins) if with_calibration else None
    agreement = agreement_report(annotators(records), labels=LABELS, plan=plan, policy=policy) if with_agreement else None
    return assess_against_policy(summary, policy=policy, calibration=calibration, agreement=agreement)


def gate(assessment: dict, name: str) -> dict:
    return next(g for g in assessment["gates"] if g["gate"] == name)


# ------------------------------------------------------------------------------------------------------------------------------- the policy object
def test_the_owner_approved_policy_holds_exactly_the_decided_values_and_none_is_an_explicit_choice():
    p = EvaluationPolicy.owner_approved()
    assert (p.primary_labels, p.reported_separately) == (LABELS, ("mixed", "uncertain"))
    assert (p.min_heldout, p.min_class_support, p.min_coverage, p.max_abstention, p.macro_f1_target, p.accepted_precision_target) == (300, 75, 0.70, 0.30, 0.80, 0.85)
    assert (p.per_class_recall_floor, p.agreement_floor, p.ece_ceiling) == (None, None, None)
    assert (p.min_calibration_sample, p.bins, p.primary_agreement, p.approved) == (20, 10, "COHEN_KAPPA", True)
    assert (p.macro_f1_deciding_view, p.lower_bound_rule, p.multi_label_agreement, p.kappa_interval) == ("strict", "NO_LOWER_BOUND_ACTIVATION_RULE", "DEFER_MULTI_LABEL_AGREEMENT", "NON_STRATIFIED_ITEM_BOOTSTRAP")
    described = p.describe()
    assert described["per_class_recall_floor"] == "NO_FLOOR" and described["agreement_floor"] == "NO_FLOOR" and described["ece_ceiling"] == "REPORT_ONLY"
    assert "no code reads them to enable, rank or select a model" in described["meaning"] and described["status"] == "approved by the owner (2026-10-29)"
    assert "activation cannot be recommended from a report" in described["meaning"] and described["lower_bound_rule"] == "NO_LOWER_BOUND_ACTIVATION_RULE"


def test_approved_true_is_refused_for_any_other_value_and_every_field_is_required():
    base = dataclasses.asdict(POLICY)
    for tampered in (dict(min_heldout=299), dict(min_class_support=74), dict(min_coverage=0.69, max_abstention=0.31), dict(macro_f1_target=0.79), dict(accepted_precision_target=0.84),
                     dict(per_class_recall_floor=0.5), dict(agreement_floor=0.6), dict(ece_ceiling=0.1), dict(min_calibration_sample=19), dict(bins=9)):
        with pytest.raises(ValueError, match="approved=True"):
            EvaluationPolicy(**{**base, **tampered})
    EvaluationPolicy(**{**base, "macro_f1_target": 0.79, "approved": False})                  # a hand-built policy is allowed but carries no approval
    assert "NOT the owner-approved policy" in EvaluationPolicy(**{**base, "macro_f1_target": 0.79, "approved": False}).describe()["status"]
    with pytest.raises(TypeError):
        EvaluationPolicy(primary_labels=LABELS)                                              # no silent defaults


def test_maximum_abstention_must_be_the_derived_one_and_the_primary_statistic_must_be_cohens_kappa():
    base = dataclasses.asdict(POLICY)
    with pytest.raises(ValueError, match="1 - min_coverage"):
        EvaluationPolicy(**{**base, "max_abstention": 0.25, "approved": False})
    with pytest.raises(ValueError, match="COHEN_KAPPA"):
        EvaluationPolicy(**{**base, "primary_agreement": "KRIPPENDORFF_ALPHA", "approved": False})


# ------------------------------------------------------------------------------------------------------------------------------- the one scenario that reaches "validated" (logic test)
def test_everything_complete_and_every_gate_met_is_the_only_way_to_the_word_validated():
    records = scenario()
    summary = evaluate_predictions(records, labels=LABELS, plan=APPROVED_PLAN, evidence=COMPLETE)
    calibration = calibration_report(records, labels=LABELS, plan=APPROVED_PLAN, evidence=COMPLETE, bins=POLICY.bins)
    agreement = agreement_report(annotators(records), labels=LABELS, plan=APPROVED_PLAN, policy=POLICY)
    result = assess_against_policy(summary, policy=POLICY, calibration=calibration, agreement=agreement)
    assert result["validation"]["status"] == "validated" and result["validation"]["unmet_or_missing"] == []
    assert gate(result, "target:macro_f1:strict")["status"] == "met" and gate(result, "target:accepted_prediction_precision")["observed"] == 1.0
    assert gate(result, "coverage:minimum")["observed"] == pytest.approx(0.92) and gate(result, "coverage:maximum_abstention")["observed"] == pytest.approx(0.08)
    assert gate(result, "calibration")["status"] == "reported" and gate(result, "agreement")["status"] == "reported"
    assert gate(result, "floor:recall:positive")["status"] == "not_applicable"
    assert result["selection"].startswith("none") and "R14" in result["activation"]                     # even then: nothing is ranked, selected or enabled


@pytest.mark.parametrize("flag", ["dataset_approved", "rubric_frozen", "manifest_hashes_verified", "independence_attested", "duplicates_excluded", "splits_separate"])
def test_any_missing_evidence_condition_gives_not_validation_evidence(flag):
    evidence = dataclasses.replace(COMPLETE, **{flag: False})
    result = run(scenario(), evidence=evidence)
    assert result["validation"]["status"] == "not_validation_evidence" and gate(result, "evidence_basis")["status"] == "not_met"


@pytest.mark.parametrize("flag", ["development_fixture", "synthetic"])
def test_fixture_and_synthetic_data_give_not_validation_evidence(flag):
    assert run(scenario(), evidence=dataclasses.replace(COMPLETE, **{flag: True}))["validation"]["status"] == "not_validation_evidence"


def test_a_hand_built_plan_or_policy_is_not_an_approval_and_stops_at_descriptive_only():
    result = run(scenario())                                                                      # the 200-resample plan is not the owner-approved one
    assert gate(result, "approved_policy_and_plan")["status"] == "not_met" and result["validation"]["status"] == "descriptive_only"
    hand_policy = dataclasses.replace(POLICY, macro_f1_target=0.79, approved=False)
    summary = evaluate_predictions(scenario(), labels=LABELS, plan=APPROVED_PLAN, evidence=COMPLETE)
    assert assess_against_policy(summary, policy=hand_policy, calibration=None, agreement=None)["validation"]["status"] == "descriptive_only"


# ------------------------------------------------------------------------------------------------------------------------------- support gates
def test_a_held_out_set_below_the_minimum_is_insufficient_support_even_when_every_class_is_large_enough():
    result = run(scenario(correct=92, abstain=7))                                                  # 3 x 99 = 297 < 300, each class 99 >= 75
    assert gate(result, "support:heldout_size")["status"] == "not_met" and gate(result, "support:class:positive")["status"] == "met"
    assert result["validation"]["status"] == "insufficient_support"
    assert gate(run(scenario(correct=92, abstain=8)), "support:heldout_size")["status"] == "met"          # exactly 300 passes: the boundary is inclusive


def test_a_primary_class_below_the_minimum_is_insufficient_support():
    records = scenario(correct=70, abstain=5)                                                      # 75 each is the boundary
    assert gate(run(records), "support:class:neutral")["status"] == "met"
    short = [r for r in records if not r.item_id.startswith("neutral-0074")]                       # neutral now has 74
    result = run(short)
    assert gate(result, "support:class:neutral")["status"] == "not_met" and gate(result, "support:class:neutral")["observed"] == 74
    assert result["validation"]["status"] == "insufficient_support"


def test_no_examples_is_insufficient_support_with_every_target_not_evaluable_and_no_value_invented():
    summary = evaluate_predictions([], labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE)
    result = assess_against_policy(summary, policy=POLICY, calibration=None, agreement=None)
    assert result["validation"]["status"] == "insufficient_support"
    for name in ("target:macro_f1:strict", "target:accepted_prediction_precision", "coverage:minimum", "coverage:maximum_abstention"):
        assert gate(result, name)["status"] == "not_evaluable" and gate(result, name)["observed"] is None and gate(result, name)["reason"]


# ------------------------------------------------------------------------------------------------------------------------------- target gates
def test_errors_that_push_macro_f1_and_precision_below_their_targets_are_not_met_and_the_word_is_descriptive_only():
    result = run(scenario(correct=72, wrong=20, abstain=8))
    assert gate(result, "target:accepted_prediction_precision")["status"] == "not_met" and gate(result, "target:macro_f1:strict")["status"] == "not_met"
    assert gate(result, "report:macro_f1:selective")["status"] == "reported" and gate(result, "report:macro_f1:selective")["observed"] < POLICY.macro_f1_target         # reported beside the strict view
    assert gate(result, "report:macro_f1:selective")["informational"] is True and result["validation"]["status"] == "descriptive_only"
    assert "target:macro_f1:strict: not_met" in result["validation"]["unmet_or_missing"]


def test_high_precision_reached_by_abstaining_is_not_enough_because_coverage_and_abstention_are_gated():
    result = run(scenario(correct=40, abstain=60))                                                 # precision 1.0, coverage 0.40
    assert gate(result, "target:accepted_prediction_precision")["status"] == "met" and gate(result, "target:accepted_prediction_precision")["observed"] == 1.0
    assert gate(result, "coverage:minimum")["status"] == "not_met" and gate(result, "coverage:maximum_abstention")["status"] == "not_met"
    assert gate(result, "target:macro_f1:strict")["status"] == "not_met"
    assert result["validation"]["status"] == "descriptive_only"


def test_the_coverage_and_abstention_boundaries_are_inclusive():
    at = run(scenario(correct=70, abstain=30))                                                     # coverage 0.70, abstention 0.30
    assert gate(at, "coverage:minimum")["status"] == "met" and gate(at, "coverage:maximum_abstention")["status"] == "met"
    below = run(scenario(correct=69, abstain=31))
    assert gate(below, "coverage:minimum")["status"] == "not_met" and gate(below, "coverage:maximum_abstention")["status"] == "not_met"


def test_the_strict_view_decides_the_macro_f1_gate_and_is_never_above_the_selective_view_which_is_only_reported():
    for abstain in (0, 8, 25, 40):
        result = run(scenario(correct=100 - abstain - 5, wrong=5, abstain=abstain))
        assert gate(result, "target:macro_f1:strict")["observed"] <= gate(result, "report:macro_f1:selective")["observed"] + 1e-12
        assert gate(result, "report:macro_f1:selective")["informational"] is True and "target:macro_f1:selective" not in [g["gate"] for g in result["gates"]]
    # a selective view above the target cannot rescue a strict view below it
    strict_below = run(scenario(correct=66, wrong=0, abstain=34))
    assert gate(strict_below, "report:macro_f1:selective")["observed"] >= POLICY.macro_f1_target and gate(strict_below, "target:macro_f1:strict")["status"] == "not_met"


def test_a_per_class_recall_floor_is_evaluated_only_when_a_floor_exists():
    hand = dataclasses.replace(POLICY, per_class_recall_floor=0.95, approved=False)
    result = run(scenario(), policy=hand)
    assert gate(result, "floor:recall:positive")["status"] == "not_met" and gate(result, "floor:recall:positive")["observed"] == pytest.approx(0.92)
    assert gate(run(scenario()), "floor:recall:positive")["status"] == "not_applicable"


# ------------------------------------------------------------------------------------------------------------------------------- calibration and agreement gates
def test_calibration_is_report_only_descriptive_below_the_sample_and_not_evaluable_without_a_report():
    assert gate(run(scenario()), "calibration")["status"] == "reported"
    assert gate(run(scenario(), with_calibration=False), "calibration")["status"] == "not_evaluable"
    summary = evaluate_predictions(scenario(), labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE)
    few = calibration_report(scenario()[:19], labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE, bins=10)
    result = assess_against_policy(summary, policy=POLICY, calibration=few, agreement=None)
    assert gate(result, "calibration")["status"] == "descriptive_only" and gate(result, "calibration")["observed"] == 19
    no_scores = calibration_report([EvalRecord("a", "positive", "positive")], labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE, bins=10)
    assert gate(assess_against_policy(summary, policy=POLICY, calibration=no_scores, agreement=None), "calibration")["status"] == "not_evaluable"


def test_the_calibration_sample_boundary_is_inclusive_at_exactly_the_minimum():
    summary = evaluate_predictions(scenario(), labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE)
    exactly = calibration_report(scenario()[:20], labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE, bins=10)
    assert gate(assess_against_policy(summary, policy=POLICY, calibration=exactly, agreement=None), "calibration")["status"] == "reported"
    one_short = calibration_report(scenario()[:19], labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE, bins=10)
    assert gate(assess_against_policy(summary, policy=POLICY, calibration=one_short, agreement=None), "calibration")["status"] == "descriptive_only"


def test_an_ece_ceiling_is_evaluated_only_when_one_exists():
    hand = dataclasses.replace(POLICY, ece_ceiling=0.01, approved=False)
    result = run(scenario(), policy=hand)
    assert gate(result, "calibration")["status"] == "not_met"                                       # confidence 0.9 on 100% correct answers: ECE about 0.1
    assert gate(run(scenario()), "calibration")["required"] == "REPORT_ONLY"


def test_the_strict_and_accepted_only_calibration_views_stay_distinct():
    records = scenario(correct=90, abstain=10)
    report = calibration_report(records, labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE, bins=10)
    assert report["strict"]["samples"] == 300 and report["accepted_only"]["samples"] == 270
    assert report["views"]["strict"].startswith("every scored example") and "equal-width" in report["method"]
    assert report["strict"]["ece"] != report["accepted_only"]["ece"]                                # the abstained ones are scored at 0.5 confidence


def test_agreement_uses_cohens_kappa_as_primary_reports_secondary_statistics_and_defers_multi_label():
    records = scenario()
    report = agreement_report(annotators(records), labels=LABELS, plan=HAND_PLAN, policy=POLICY)
    assert report["primary_statistic"] == "COHEN_KAPPA" and report["agreement_floor"].startswith("NO_FLOOR")
    assert report["secondary_statistics"] == ["specific_agreement (per pair, per label)", "krippendorff_alpha"] and report["krippendorff_alpha"]["alpha"] is not None
    assert report["multi_label"]["status"] == "deferred" and "pre-adjudication" in report["basis"].lower()
    assert gate(run(records), "agreement")["status"] == "reported"
    assert gate(run(records, with_agreement=False), "agreement")["status"] == "not_evaluable"


def test_agreement_with_an_undefined_kappa_is_not_evaluable_and_a_floor_is_applied_only_when_one_exists():
    records = scenario()
    constant = {"annotator-a": ["positive"] * 20, "annotator-b": ["positive"] * 20}
    summary = evaluate_predictions(records, labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE)
    report = agreement_report(constant, labels=LABELS, plan=HAND_PLAN, policy=POLICY)
    assert gate(assess_against_policy(summary, policy=POLICY, calibration=None, agreement=report), "agreement")["status"] == "not_evaluable"
    hand = dataclasses.replace(POLICY, agreement_floor=0.99, approved=False)
    floored = assess_against_policy(summary, policy=hand, calibration=None, agreement=agreement_report(annotators(records), labels=LABELS, plan=HAND_PLAN, policy=hand))
    assert gate(floored, "agreement")["status"] == "not_met"


def test_an_agreement_report_that_does_not_use_the_approved_statistic_is_refused():
    summary = evaluate_predictions(scenario(), labels=LABELS, plan=HAND_PLAN, evidence=COMPLETE)
    report = agreement_report(annotators(scenario()), labels=LABELS, plan=HAND_PLAN, policy=POLICY)
    with pytest.raises(ValueError, match="approved primary statistic"):
        assess_against_policy(summary, policy=POLICY, calibration=None, agreement={**report, "primary_statistic": "KRIPPENDORFF_ALPHA"})


# ------------------------------------------------------------------------------------------------------------------------------- label set, wording, informational gates
def test_a_report_on_another_label_set_cannot_be_assessed_and_is_reported_as_secondary():
    five = ("positive", "negative", "neutral", "mixed", "uncertain")
    records = [EvalRecord(f"x-{i}", five[i % 5], five[i % 5]) for i in range(50)]
    summary = evaluate_predictions(records, labels=five, plan=HAND_PLAN, evidence=COMPLETE)
    with pytest.raises(ValueError, match="primary label set"):
        assess_against_policy(summary, policy=POLICY, calibration=None, agreement=None)
    report = evaluation_report(records, labels=five, plan=HAND_PLAN, evidence=COMPLETE, policy=POLICY)
    assert report["assessment"]["validation"]["status"] == "not_validation_evidence" and "secondary" in report["assessment"]["validation"]["reason"]


def test_the_wording_is_always_one_of_the_four_approved_words_and_the_informational_gates_say_what_is_not_approved():
    for records, evidence in ((scenario(), COMPLETE), (scenario(), dataclasses.replace(COMPLETE, synthetic=True)), (scenario(correct=40, abstain=60), COMPLETE), (scenario(correct=10, abstain=5), COMPLETE)):
        result = run(records, evidence=evidence)
        assert result["validation"]["status"] in VALIDATION_WORDS and result["validation"]["words"] == list(VALIDATION_WORDS)
    result = run(scenario())
    assert gate(result, "interval_lower_bound_rule")["status"] == "not_applicable" and gate(result, "interval_lower_bound_rule")["required"] == "NO_LOWER_BOUND_ACTIVATION_RULE"
    assert gate(result, "interval_lower_bound_rule")["informational"] is True and "never a gate" in gate(result, "interval_lower_bound_rule")["reason"]
    assert gate(result, "significance_testing")["required"] == "NOT_REQUIRED" and "no p-value" in gate(result, "significance_testing")["reason"]
    assert gate(result, "rules_baseline_comparison")["reason"] == "no winner is declared automatically"
    assert not any(g["informational"] for g in result["gates"] if g["gate"] in {"evidence_basis", "calibration", "agreement"})        # informational gates never count towards completeness


def test_the_assessment_is_deterministic_and_its_gates_keep_a_fixed_order():
    first, second = run(scenario()), run(list(reversed(scenario())))
    assert first == second
    names = [g["gate"] for g in first["gates"]]
    assert names[:2] == ["evidence_basis", "approved_policy_and_plan"] and names[2] == "support:heldout_size" and names[-3:] == ["interval_lower_bound_rule", "rules_baseline_comparison", "significance_testing"]
    assert names == [g["gate"] for g in second["gates"]]


# ------------------------------------------------------------------------------------------------------------------------------- the decisions of the eighteenth brief (2026-10-29)
@pytest.mark.parametrize("field,value", [("macro_f1_deciding_view", "selective"), ("lower_bound_rule", "LOWER_BOUND_MUST_CLEAR_TARGET"), ("lower_bound_rule", "LOWER_BOUND_DESCRIPTIVE_ONLY"),
                                          ("multi_label_agreement", "JACCARD_PER_ITEM"), ("multi_label_agreement", "MICRO_MACRO_F1"), ("kappa_interval", "STRATIFY_BY_ADJUDICATED_CLASS"),
                                          ("kappa_interval", "STRATIFY_BY_ANNOTATOR_AGREEMENT")])
def test_only_the_approved_choice_of_each_newly_decided_option_is_accepted_even_for_a_hand_built_policy(field, value):
    with pytest.raises(ValueError, match="no other value is approved or implemented"):
        EvaluationPolicy(**{**dataclasses.asdict(POLICY), field: value, "approved": False})


def test_the_new_fields_are_required():
    base = dataclasses.asdict(POLICY)
    for name in ("macro_f1_deciding_view", "lower_bound_rule", "multi_label_agreement", "kappa_interval"):
        with pytest.raises(TypeError):
            EvaluationPolicy(**{k: v for k, v in base.items() if k != name})


def test_no_report_recommends_activation_and_a_validated_word_still_recommends_nothing():
    complete = scenario()
    summary = evaluate_predictions(complete, labels=LABELS, plan=APPROVED_PLAN, evidence=COMPLETE)
    calibration = calibration_report(complete, labels=LABELS, plan=APPROVED_PLAN, evidence=COMPLETE, bins=POLICY.bins)
    agreement = agreement_report(annotators(complete), labels=LABELS, plan=APPROVED_PLAN, policy=POLICY)
    validated = assess_against_policy(summary, policy=POLICY, calibration=calibration, agreement=agreement)
    assert validated["validation"]["status"] == "validated"
    assert validated["activation_recommendation"].startswith("none") and "NO_LOWER_BOUND_ACTIVATION_RULE" in validated["activation_recommendation"] and "R14" in validated["activation"]
    assert not any("lower" in g["gate"] and g["status"] in ("met", "not_met") for g in validated["gates"])                 # no interval bound is ever a gate
    for g in validated["gates"]:
        if g["gate"].startswith(("target:", "coverage:", "support:")):
            assert isinstance(g["observed"], (int, float))                                                               # the gates read point estimates and counts only


def test_a_point_estimate_that_passes_does_not_make_a_report_validated_when_any_other_condition_fails():
    for evidence in (dataclasses.replace(COMPLETE, rubric_frozen=False), dataclasses.replace(COMPLETE, synthetic=True)):
        assert run(scenario(), evidence=evidence)["validation"]["status"] == "not_validation_evidence"
    assert run(scenario())["validation"]["status"] == "descriptive_only"                                                  # all point gates met, but the plan in use is not the approved one
    assert run(scenario(), with_agreement=False, with_calibration=False)["validation"]["status"] == "descriptive_only"


def test_the_agreement_report_states_the_multi_label_and_kappa_interval_decisions():
    report = agreement_report(annotators(scenario()), labels=LABELS, plan=HAND_PLAN, policy=POLICY)
    assert report["multi_label"]["status"] == "deferred" and report["multi_label"]["decision"] == "DEFER_MULTI_LABEL_AGREEMENT" and "descriptive" in report["multi_label"]["reason"]
    assert report["kappa_interval_method"] == "NON_STRATIFIED_ITEM_BOOTSTRAP" and "non-stratified item bootstrap" in report["plan"]["interval_methods"]["kappa"]
    pair = next(iter(report["pairs"].values()))
    assert pair["kappa_interval"] is not None and pair["kappa_interval"]["method"] == "percentile_bootstrap"


def test_an_informational_gate_never_appears_among_the_unmet_or_missing_conditions_even_when_it_is_not_evaluable():
    result = run(scenario(correct=0, abstain=100))                                              # nothing answered: the selective view is undefined
    selective = gate(result, "report:macro_f1:selective")
    assert selective["status"] == "not_evaluable" and selective["informational"] is True and selective["observed"] is None
    assert not any(entry.startswith(("report:", "interval_lower_bound_rule", "rules_baseline_comparison", "significance_testing")) for entry in result["validation"]["unmet_or_missing"])
    assert "target:macro_f1:strict: not_met" in result["validation"]["unmet_or_missing"]       # the strict view still decides
