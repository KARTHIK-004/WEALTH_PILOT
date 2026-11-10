"""S2.8I: OD-10 part 1. The aggregator carries the shared ``CoverageBlock`` as a REPORT-ONLY field (``DailyFeatures.coverage_report``).

The block never drives a coverage value, status, ``no_news``, usability or the policy guard. Since S2.8J (owner decision OD-10 part 2) a processed
slot that fails reconciliation is excluded from the aggregator's numerator, so the two numerators agree on it (tests in
``test_sentiment_aggregator_unreconciled_coverage.py``). Synthetic only; offline; the scorer is the test-only fake.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import coverage_report as cr
from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment.policy import PolicyBlockedError, PolicyState

_spec = importlib.util.spec_from_file_location("_wp_scaffold_world", Path(__file__).with_name("test_sentiment_scaffold.py"))
S = importlib.util.module_from_spec(_spec)                         # the shared synthetic aggregator fixtures, loaded by path
sys.modules[_spec.name] = S
_spec.loader.exec_module(S)

# every DailyFeatures field that existed before S2.8I, in order: the new field must be the only addition
PRIOR_FIELDS = (
    "origin_date", "theme", "n_eligible", "n_scored", "n_duplicates_removed", "n_invalid_text", "n_update_versions", "n_distinct_stories",
    "n_late_carried_in", "coverage", "coverage_status", "n_slots_expected", "n_slots_covered", "n_slots_near_empty", "n_slots_delayed",
    "n_delayed_theme_rows", "scoring_coverage", "scoring_status", "dedup_status", "mean_p_pos", "mean_p_neg", "mean_net", "disp_net",
    "no_news", "feature_cutoff_utc", "model_revision", "schema_version", "reason", "source_completeness", "interval_usability",
    "theme_evidence", "theme_evidence_reasons", "result_availability", "result_reason", "n_slots_near_empty_unknown", "rules_status")


def existing(r):
    """Every field except the additive report-only one."""
    return {f.name: getattr(r, f.name) for f in dataclasses.fields(r) if f.name != "coverage_report"}


def wrong_rows(slots, n=8):
    return S.set_slots(slots, S.D2, range(n), lambda t: S.processed(t, rows=10, theme_rows={"equity_us": 10, "rates_us": 0, "gold": 0}))


# ---------------------------------------------------------------- the field

def test_the_report_only_field_is_the_only_new_field_and_has_a_default():
    names = tuple(f.name for f in dataclasses.fields(S.ft.DailyFeatures))
    assert set(names) - set(PRIOR_FIELDS) == {"coverage_report", "coverage_threshold", "coverage_threshold_met"} and set(PRIOR_FIELDS) <= set(names)
    fields = {f.name: f for f in dataclasses.fields(S.ft.DailyFeatures)}
    assert all(fields[n].default is None for n in ("coverage_report", "coverage_threshold", "coverage_threshold_met")) and names[-3:] == (
        "coverage_report", "coverage_threshold", "coverage_threshold_met")                  # defaulted and last: existing constructors keep working


def test_a_clean_reconciled_interval_carries_a_serialisable_block_and_unchanged_existing_values():
    a = S.art(1, S.IN_D2)
    r = S.row(S.agg([a]), S.D2)
    b = r.coverage_report
    assert isinstance(b, cr.CoverageBlock) and (b.n_expected, b.n_covered, b.ratio, b.kind) == (96, 96, 1.0, "source_slot_coverage")
    assert not any(b.excluded_by_reason.values()) and b.max_consecutive_missing_run == 0
    json.dumps(dataclasses.asdict(b))                                                # serialisable as it stands
    assert (r.coverage, r.coverage_status, r.n_slots_expected, r.n_slots_covered, r.n_slots_near_empty, r.n_slots_delayed) == (1.0, "ok", 96, 96, 0, 0)
    assert S.row(S.agg([]), S.D2).no_news is True and S.row(S.agg([]), S.D2).reason == "verified_no_news"


# ---------------------------------------------------------------- the known OD-10 part 2 divergence

def test_a_processed_but_unreconciled_slot_is_excluded_by_both_numerators_since_od10_part2():
    slots = wrong_rows(S.slots_for([]))
    r = S.row(S.agg([], slots=slots), S.D2)
    assert r.coverage_status == "slot_article_mismatch" and "rows_captured 10 but 0" in r.reason
    assert (r.n_slots_covered, r.n_slots_expected) == (88, 96) and r.coverage == pytest.approx(88 / 96)       # S2.8J: the 8 are not covered
    b = r.coverage_report
    assert (b.n_expected, b.n_covered, b.excluded_by_reason["rejected"]) == (96, 88, 8)     # the report-only block agrees
    assert b.n_covered + b.n_excluded == b.n_expected and b.max_consecutive_missing_run == 8
    assert r.no_news is None and r.interval_usability == "unusable_incomplete"              # unchanged, and not read from the block


def test_the_source_records_the_owner_decision_that_unreconciled_slots_are_excluded():
    text = (S.PKG / "features.py").read_text(encoding="utf-8")
    assert "OD-10 part 2" in text and "NOT covered" in text


# ---------------------------------------------------------------- missing and incomplete evidence

def test_absent_slots_are_reported_as_final_absent_and_existing_coverage_is_unchanged():
    a = S.art(1, S.IN_D2)
    r = S.row(S.agg([a], slots=S.set_slots(S.slots_for([a]), S.D2, range(60), S.absent)), S.D2)
    assert (r.coverage_status, r.coverage, r.n_slots_covered) == ("ok", pytest.approx(0.375), 36)             # the threshold is informational: features are computed
    assert (r.coverage_threshold, r.coverage_threshold_met) == (0.75, False) and r.interval_usability == "undecided_policy" and r.result_availability == "unavailable"
    b = r.coverage_report
    assert (b.n_covered, b.excluded_by_reason["final_absent"], b.max_consecutive_missing_run) == (36, 60, 60) and b.ratio == pytest.approx(0.375)
    assert r.no_news is not True                                                                      # there are records: not "no news"


def test_delayed_and_unknown_near_empty_slots_stay_distinct_in_the_block():
    delayed = S.set_slots(S.slots_for([]), S.D2, [5], lambda t: S.processed(t, at=S.verified(t) + timedelta(hours=30)))
    r = S.row(S.agg([], slots=delayed), S.D2)
    assert r.coverage_report.excluded_by_reason["delayed_after_cutoff"] == 1 and r.n_slots_delayed == 1 and r.no_news is not True
    unknown = S.set_slots(S.slots_for([]), S.D2, range(96), lambda t: S.processed(t, near=None))
    u = S.row(S.agg([], slots=unknown), S.D2)
    assert u.coverage_report.excluded_by_reason["near_empty_unknown"] == 96 and u.coverage_report.n_covered == 0
    assert u.coverage_status == "ok" and u.no_news is None and u.theme_evidence == "unverified_empty" and u.interval_usability == "undecided_policy"


def test_an_interval_whose_slots_cannot_be_listed_has_no_block_rather_than_an_invented_one():
    slots = S.slots_for([])
    del slots[S.D2]
    r = S.row(S.agg([S.art(1, S.IN_D2)], slots=slots), S.D2)
    assert r.coverage_status == "no_expected_slots" and r.coverage_report is None
    broken = S.slots_for([])
    broken[S.D2] = broken[S.D2][:-1]
    g = S.row(S.agg([], slots=broken), S.D2)
    assert g.coverage_status == "slot_grid_mismatch" and g.coverage_report is None


def test_earlier_batches_not_examined_still_blocks_and_a_perfect_ratio_never_makes_no_news():
    base = S.slots_for([])
    rows = S.ft.aggregate_daily([], S.DAYS, base, config=S.CFG, earlier=S.EarlierEvidence.not_examined())
    r = S.row(rows, S.D2)
    assert r.coverage_report.ratio == 1.0 and r.coverage_status == "incomplete_source_accounting"
    assert r.no_news is None and r.theme_evidence == "not_evaluated"                  # a perfect source ratio, but the lookback was not examined (existing behaviour)
    unresolved = S.row(S.agg([], earlier=S.EarlierEvidence(True, ("20220301100000",))), S.D2)
    assert unresolved.coverage_report.ratio == 1.0 and unresolved.no_news is None


# ---------------------------------------------------------------- the block never drives anything

def test_replacing_the_block_with_any_other_block_changes_no_existing_field(monkeypatch):
    scenarios = [S.agg([S.art(1, S.IN_D2)]), S.agg([], slots=wrong_rows(S.slots_for([]))), S.agg([])]
    bogus = cr.CoverageBlock(96, 0, 0.0, {k: 0 for k in cr.EXCLUSION_REASONS}, 96, 96, ())
    monkeypatch.setattr(S.ft, "coverage_block", lambda *a, **k: bogus)
    again = [S.agg([S.art(1, S.IN_D2)]), S.agg([], slots=wrong_rows(S.slots_for([]))), S.agg([])]
    for before, after in zip(scenarios, again):
        assert [existing(x) for x in before] == [existing(x) for x in after]
        assert all(x.coverage_report is bogus for x in after)


def test_the_unapplied_policy_guard_still_refuses_before_any_row_is_built():
    unapplied = PolicyState.from_mapping({n: "UNRESOLVED_NOT_APPLIED" for n in S.pol.REQUIRED_POLICIES})
    live = PolicyState.from_mapping(orc.POLICY_STATUS)
    with pytest.raises(PolicyBlockedError):                                                  # the live table still refuses: the scorer policy is unresolved
        S.aggregate([], S.DAYS, S.slots_for([]), config=dataclasses.replace(S.CFG, policy=live))
    cfg = dataclasses.replace(S.CFG, policy=unapplied)
    with pytest.raises(PolicyBlockedError):
        S.aggregate([], S.DAYS, S.slots_for([]), config=cfg)
    with pytest.raises(PolicyBlockedError):
        S.aggregate([S.art(1, S.IN_D2)], S.DAYS, wrong_rows(S.slots_for([])), config=cfg)
    assert len(unapplied.unresolved()) == 8


def test_no_coverage_verdict_function_is_called_by_the_aggregator():
    text = (S.PKG / "features.py").read_text(encoding="utf-8")
    assert "coverage_rule_decision" not in text and "unknown_near_empty_is_covered" not in text


# ---------------------------------------------------------------- determinism and compatibility

def test_equivalent_inputs_give_equal_blocks_in_a_stable_order():
    a = S.art(1, S.IN_D2)
    make = lambda: S.agg([a], slots=S.set_slots(S.slots_for([a]), S.D2, [3, 4, 5], S.absent))        # noqa: E731
    first, second = make(), make()
    assert [x.coverage_report for x in first] == [x.coverage_report for x in second] and first == second
    assert list(first[0].coverage_report.excluded_by_reason) == list(cr.EXCLUSION_REASONS)
    assert len({id(x.coverage_report) for x in first if x.origin_date == S.D2}) == 1                  # one block per interval, shared by its themes
    themes = {x.theme: x.coverage_report for x in first if x.origin_date == S.D2}
    assert len(set(map(repr, themes.values()))) == 1


def test_existing_fixtures_compare_exactly_with_and_without_the_report_field():
    a = S.art(1, S.IN_D2)
    for rows in (S.agg([a]), S.agg([]), S.agg([a], slots=S.set_slots(S.slots_for([a]), S.D2, range(24), S.absent))):
        stripped = [dataclasses.replace(r, coverage_report=None) for r in rows]
        assert [existing(r) for r in rows] == [existing(r) for r in stripped]
        assert all(r.coverage_report is not None for r in rows)
