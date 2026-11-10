"""S2.8E: coverage accounting and near-empty plumbing on the shared completeness contract. Synthetic only; offline; no scorer.

The thresholds (0.75 primary, 0.50/0.90 sensitivity) and the detector parameters (14 days, 7 observations, 10%) are PROVISIONAL
configuration. These tests check the plumbing and that nothing here turns a ratio or a low count into a decision.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import completeness as cp
from wealthpilot.data.gdelt.sentiment import coverage_report as cr
from wealthpilot.data.gdelt.sentiment import near_empty as ne
from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment.completeness import NearEmpty, SlotAccount, SlotEvidence
from wealthpilot.data.gdelt.sentiment.policy import APPLIED_PROVISIONAL
from wealthpilot.data.gdelt.timeutil import format_batch_stamp, parse_batch_stamp

_spec = importlib.util.spec_from_file_location("_wp_orchestrator_world", Path(__file__).with_name("test_sentiment_orchestrator.py"))
_world = importlib.util.module_from_spec(_spec)                      # the shared synthetic world, loaded by path (tests are not a package)
sys.modules[_spec.name] = _world
_spec.loader.exec_module(_world)
CUT2, D2, D3, FV, IN_D2, IN_D2_B, LAST_D2, PRE, PRE_LATE, World, nominal = (
    _world.CUT2, _world.D2, _world.D3, _world.FV, _world.IN_D2, _world.IN_D2_B, _world.LAST_D2, _world.PRE, _world.PRE_LATE,
    _world.World, _world.nominal)

T = "20220302150000"
OBS_OK = ne.NearEmptyParams()


def acc(b: str, near: NearEmpty = NearEmpty.NOT_NEAR_EMPTY, kind: SlotAccount = SlotAccount.ACCOUNTED) -> SlotEvidence:
    return SlotEvidence(b, kind, near)


def na(b: str, kind: SlotAccount) -> SlotEvidence:
    return SlotEvidence(b, kind, NearEmpty.NOT_APPLICABLE)


def grid(n: int = 96) -> list[str]:
    start = nominal("20220302000000")
    return [format_batch_stamp(start + timedelta(minutes=15 * i)) for i in range(n)]


def stamps_before(batch: str, days: range) -> list[str]:
    return [format_batch_stamp(parse_batch_stamp(batch) - timedelta(days=k)) for k in days]


def baseline(values, batch: str = T, **kw) -> list[ne.BaselineObservation]:
    return [ne.BaselineObservation(s, v, **kw) for s, v in zip(stamps_before(batch, range(1, 15)), values)]


DECLARED = format_batch_stamp(parse_batch_stamp(T) - timedelta(days=14))      # exactly the start of the 14-day lookback


# ================================================================ Part B: coverage accounting (shared contract, pure)

def test_the_denominator_is_the_full_grid_and_a_full_interval_is_all_covered():
    b = cr.coverage_block([acc(s) for s in grid()])
    assert (b.n_expected, b.n_covered, b.ratio, b.n_excluded) == (96, 96, 1.0, 0)
    assert set(b.excluded_by_reason) == set(cr.EXCLUSION_REASONS) and not any(b.excluded_by_reason.values())
    assert (b.max_consecutive_missing_run, b.max_consecutive_uncovered_run, b.kind) == (0, 0, "source_slot_coverage")
    assert all(t.meets for t in b.thresholds) and [t.label for t in b.thresholds] == ["primary", "sensitivity", "sensitivity"]


def test_every_non_covered_slot_is_excluded_for_exactly_one_distinct_reason_and_still_counts_in_the_denominator():
    g = grid()
    s = [acc(x) for x in g]
    s[0], s[1], s[2], s[3] = na(g[0], SlotAccount.MISSING), na(g[1], SlotAccount.REJECTED), na(g[2], SlotAccount.NON_FINAL), na(g[3], SlotAccount.FINAL_ABSENT)
    s[10] = acc(g[10], kind=SlotAccount.ACCOUNTED_DELAYED)
    s[20], s[21] = acc(g[20], NearEmpty.NEAR_EMPTY), acc(g[21], NearEmpty.UNKNOWN)
    b = cr.coverage_block(s)
    assert b.excluded_by_reason == {"missing": 1, "rejected": 1, "non_final": 1, "final_absent": 1, "delayed_after_cutoff": 1,
                                    "near_empty": 1, "near_empty_unknown": 1}
    assert b.n_expected == 96 and b.n_covered == 89 and b.n_covered + b.n_excluded == b.n_expected          # nothing silently removed
    assert b.ratio == pytest.approx(89 / 96)


def test_the_two_longest_runs_are_measured_in_grid_order_whatever_the_input_order():
    g = grid()
    s = [acc(x) for x in g]
    for i in (4, 5, 6):
        s[i] = na(g[i], SlotAccount.MISSING)
    s[7] = acc(g[7], NearEmpty.NEAR_EMPTY)                       # uncovered but NOT missing: extends only the uncovered run
    s[30] = na(g[30], SlotAccount.FINAL_ABSENT)
    b = cr.coverage_block(list(reversed(s)))
    assert b.max_consecutive_missing_run == 3 and b.max_consecutive_uncovered_run == 4


def test_a_slot_list_that_would_shrink_or_blur_the_denominator_is_refused():
    with pytest.raises(cr.CoverageReportError):
        cr.coverage_block([acc(x) for x in grid(10)], expected_n=96)
    with pytest.raises(cr.CoverageReportError):
        cr.coverage_block([acc("20220302000000"), acc("20220302000000")])
    assert cr.coverage_block([]).ratio is None                     # no expected slot: no ratio, never 0 or 1


def test_thresholds_are_explicit_validated_and_marked_provisional():
    t = cr.CoverageThresholds()
    assert (t.primary, t.sensitivity, t.status) == (0.75, (0.50, 0.90), "PROVISIONAL_NOT_APPROVED")
    for bad in (dict(primary=0.0), dict(primary=1.5), dict(primary=0.75, sensitivity=(0.75,)), dict(primary=1)):
        with pytest.raises(cr.CoverageReportError):
            cr.CoverageThresholds(**bad)
    b = cr.coverage_block([acc(x) for x in grid()[:72]] + [na(x, SlotAccount.MISSING) for x in grid()[72:]], cr.CoverageThresholds(0.8, (0.7,)))
    assert [(r.threshold, r.meets) for r in b.thresholds] == [(0.8, False), (0.7, True)]           # 72/96 = 0.75
    assert cr.coverage_block([acc(x) for x in grid()[:72]] + [na(x, SlotAccount.MISSING) for x in grid()[72:]]).thresholds[0].meets   # 0.75 meets 0.75


def test_a_threshold_verdict_reaches_usability_only_through_an_applied_policy_status():
    g = grid()
    s = [acc(x) for x in g[:80]] + [acc(x, NearEmpty.NEAR_EMPTY) for x in g[80:]]       # 80/96 covered, 16 explicit near-empty
    t = cr.CoverageThresholds()
    b = cr.coverage_block(s, t)
    for status in ("UNRESOLVED_NOT_APPLIED", "SELECTED_PROVISIONAL_NOT_APPLIED", "SELECTED_NOT_APPLIED", "CALLER_SUPPLIED_NOT_APPROVED", APPLIED_PROVISIONAL, None):    # a provisional threshold is informational
        assert cr.coverage_rule_decision(b, t, status) is None
        assert cp.assess_interval(s, coverage_rule_met=cr.coverage_rule_decision(b, t, status)).usability is cp.IntervalUsability.UNDECIDED_POLICY
    assert cr.coverage_rule_decision(b, t, "APPLIED_APPROVED") is True                    # only a fully approved threshold can decide usability
    assert cp.assess_interval(s, coverage_rule_met=True).usability is cp.IntervalUsability.USABLE_UNDER_COVERAGE_RULE
    low = cr.coverage_block([acc(x) for x in g[:40]] + [acc(x, NearEmpty.NEAR_EMPTY) for x in g[40:]], t)
    assert cr.coverage_rule_decision(low, t, "APPLIED_APPROVED") is False


# ================================================================ Part C: the near-empty detector (pure)

def test_a_full_baseline_decides_near_empty_below_ten_percent_of_the_median_and_not_at_it():
    obs = baseline([100] * 14)
    low = ne.assess_near_empty(T, 9, obs, OBS_OK, baseline_declared_from=DECLARED)
    edge = ne.assess_near_empty(T, 10, obs, OBS_OK, baseline_declared_from=DECLARED)
    assert (low.state, low.reason, low.n_valid, low.baseline_median, low.threshold_rows) == (NearEmpty.NEAR_EMPTY, ne.BaselineReason.DECIDED, 14, 100.0, 10.0)
    assert edge.state is NearEmpty.NOT_NEAR_EMPTY and edge.params_status == "PROVISIONAL_NOT_APPROVED"
    assert ne.assess_near_empty(T, 0, obs, OBS_OK, baseline_declared_from=DECLARED).state is NearEmpty.NEAR_EMPTY
    assert ne.assess_near_empty(T, 0, baseline([0] * 14), OBS_OK, baseline_declared_from=DECLARED).state is NearEmpty.NOT_NEAR_EMPTY   # median 0: nothing is below it


def test_exactly_the_minimum_number_of_valid_observations_decides_and_one_fewer_does_not():
    seven = baseline([100] * 7 + [None] * 7)[:7]
    assert ne.assess_near_empty(T, 5, seven, OBS_OK, baseline_declared_from=DECLARED).state is NearEmpty.NEAR_EMPTY
    six = ne.assess_near_empty(T, 5, seven[:6], OBS_OK, baseline_declared_from=DECLARED)
    assert (six.state, six.reason, six.n_valid, six.n_absent) == (NearEmpty.UNKNOWN, ne.BaselineReason.INSUFFICIENT_BASELINE, 6, 8)


def test_without_baseline_evidence_the_state_is_unknown_never_false():
    a = ne.assess_near_empty(T, 5, [], OBS_OK)                                              # nothing declared
    assert (a.state, a.reason) == (NearEmpty.UNKNOWN, ne.BaselineReason.NO_BASELINE_DECLARED) and a.state is not NearEmpty.NOT_NEAR_EMPTY
    b = ne.assess_near_empty(T, 5, baseline([100] * 14), OBS_OK)                            # observations given but no declaration of completeness
    assert b.reason is ne.BaselineReason.NO_BASELINE_DECLARED and b.state is NearEmpty.UNKNOWN


def test_the_whole_lookback_must_start_inside_the_declared_evidence():
    later = format_batch_stamp(parse_batch_stamp(DECLARED) + timedelta(minutes=15))
    a = ne.assess_near_empty(T, 5, baseline([100] * 14), OBS_OK, baseline_declared_from=later)
    assert (a.state, a.reason) == (NearEmpty.UNKNOWN, ne.BaselineReason.LOOKBACK_NOT_AVAILABLE)
    assert ne.assess_near_empty(T, 5, baseline([100] * 14), OBS_OK, baseline_declared_from=DECLARED).state is NearEmpty.NEAR_EMPTY


def test_uncommitted_invalid_missing_and_duplicate_observations_are_never_used():
    vals = baseline([100] * 14)
    unc = [dataclasses.replace(o, committed=False) if i < 8 else o for i, o in enumerate(vals)]          # 6 committed, 8 not
    a = ne.assess_near_empty(T, 5, unc, OBS_OK, baseline_declared_from=DECLARED)
    assert (a.state, a.reason, a.n_valid, a.n_uncommitted) == (NearEmpty.UNKNOWN, ne.BaselineReason.BASELINE_NOT_COMMITTED, 6, 8)
    bad = [dataclasses.replace(o, valid=False) if i < 8 else o for i, o in enumerate(vals)]
    b = ne.assess_near_empty(T, 5, bad, OBS_OK, baseline_declared_from=DECLARED)
    assert (b.state, b.n_invalid, b.n_valid) == (NearEmpty.UNKNOWN, 8, 6)
    dup = vals[:7] + [vals[0]]                                                                       # a repeated stamp is ambiguous: dropped
    d = ne.assess_near_empty(T, 5, dup, OBS_OK, baseline_declared_from=DECLARED)
    assert d.state is NearEmpty.UNKNOWN and d.n_invalid == 1 and d.n_valid == 6
    neg = [ne.BaselineObservation(vals[0].batch_ts, -3)] + vals[1:8]
    assert ne.assess_near_empty(T, 5, neg, OBS_OK, baseline_declared_from=DECLARED).n_invalid == 1


def test_an_invalid_observed_count_is_unknown():
    for bad in (None, -1, True, 2.5):
        a = ne.assess_near_empty(T, bad, baseline([100] * 14), OBS_OK, baseline_declared_from=DECLARED)
        assert (a.state, a.reason) == (NearEmpty.UNKNOWN, ne.BaselineReason.OBSERVED_COUNT_INVALID)


def test_only_strictly_prior_observations_are_read_so_no_future_data_leaks_into_the_baseline():
    obs = baseline([100] * 14)
    base = ne.assess_near_empty(T, 5, obs, OBS_OK, baseline_declared_from=DECLARED)
    future = [ne.BaselineObservation(format_batch_stamp(parse_batch_stamp(T) + timedelta(days=k)), 1_000_000) for k in range(0, 8)]   # incl. the batch itself
    same_day = [ne.BaselineObservation(format_batch_stamp(parse_batch_stamp(T) - timedelta(minutes=15 * k)), 1_000_000) for k in range(1, 5)]   # other slots of the day
    assert ne.assess_near_empty(T, 5, obs + future + same_day, OBS_OK, baseline_declared_from=DECLARED) == base
    only_future = ne.assess_near_empty(T, 5, future, OBS_OK, baseline_declared_from=DECLARED)
    assert only_future.state is NearEmpty.UNKNOWN and only_future.n_valid == 0
    older = [ne.BaselineObservation(format_batch_stamp(parse_batch_stamp(T) - timedelta(days=15)), 1_000_000)]            # beyond the lookback
    assert ne.assess_near_empty(T, 5, obs + older, OBS_OK, baseline_declared_from=DECLARED) == base


def test_the_baseline_is_the_same_slot_of_day_only():
    other_slot = [ne.BaselineObservation(format_batch_stamp(parse_batch_stamp(T) - timedelta(days=k, minutes=15)), 100) for k in range(1, 15)]
    a = ne.assess_near_empty(T, 5, other_slot, OBS_OK, baseline_declared_from=DECLARED)
    assert a.state is NearEmpty.UNKNOWN and a.n_valid == 0 and a.n_absent == 14


def test_parameters_are_validated_and_provisional():
    assert (OBS_OK.lookback_days, OBS_OK.min_baseline_obs, OBS_OK.ratio, OBS_OK.status) == (14, 7, 0.10, "PROVISIONAL_NOT_APPROVED")
    for bad in (dict(lookback_days=0), dict(min_baseline_obs=0), dict(min_baseline_obs=15), dict(ratio=0.0), dict(ratio=1.0), dict(ratio=1)):
        with pytest.raises(ne.NearEmptyError):
            ne.NearEmptyParams(**bad)
    custom = ne.NearEmptyParams(lookback_days=3, min_baseline_obs=2, ratio=0.5)
    obs = baseline([100, 100, 100])
    decl = format_batch_stamp(parse_batch_stamp(T) - timedelta(days=3))
    assert ne.assess_near_empty(T, 49, obs, custom, baseline_declared_from=decl).state is NearEmpty.NEAR_EMPTY
    with pytest.raises(ne.NearEmptyError):
        ne.assess_near_empty("bad", 5, [], OBS_OK)


def test_the_observed_flag_and_the_derived_state_stay_distinct_and_null_is_never_false():
    f = ne.FlagComparison
    table = {(None, NearEmpty.UNKNOWN): f.BOTH_UNKNOWN, (None, NearEmpty.NEAR_EMPTY): f.DERIVED_ONLY, (None, NearEmpty.NOT_NEAR_EMPTY): f.DERIVED_ONLY,
             (True, NearEmpty.UNKNOWN): f.OBSERVED_ONLY, (False, NearEmpty.UNKNOWN): f.OBSERVED_ONLY,
             (True, NearEmpty.NEAR_EMPTY): f.AGREE, (False, NearEmpty.NOT_NEAR_EMPTY): f.AGREE,
             (True, NearEmpty.NOT_NEAR_EMPTY): f.DISAGREE, (False, NearEmpty.NEAR_EMPTY): f.DISAGREE,
             (None, NearEmpty.NOT_APPLICABLE): f.NOT_APPLICABLE, (False, NearEmpty.NOT_APPLICABLE): f.NOT_APPLICABLE}
    for (obs, der), want in table.items():
        assert ne.compare_flags(obs, der) is want, (obs, der)
    assert cp.near_empty_of(None) is NearEmpty.UNKNOWN and cp.near_empty_of(None) is not cp.near_empty_of(False)


def test_a_near_empty_slot_is_not_a_missing_slot():
    near = acc("20220302150000", NearEmpty.NEAR_EMPTY)
    assert near.account is SlotAccount.ACCOUNTED and cr.exclusion_reason(near) == "near_empty"
    assert cr.exclusion_reason(na("20220302150000", SlotAccount.MISSING)) == "missing"
    b = cr.coverage_block([acc(grid()[0], NearEmpty.NEAR_EMPTY)] + [acc(x) for x in grid()[1:]])
    assert b.max_consecutive_missing_run == 0 and b.excluded_by_reason["missing"] == 0 and b.excluded_by_reason["near_empty"] == 1


# ================================================================ Part D/E: through the orchestrator (real adapters, synthetic world)

def slot(r, b):
    return next(v for v in r.slots if v.batch_ts == b)


def test_the_report_carries_a_coverage_block_per_interval_on_the_full_grid():
    r = World().run()
    for d in (D2, D3):
        c = r.interval(d).coverage
        assert (c.n_expected, c.n_covered, c.ratio, c.n_excluded) == (96, 96, 1.0, 0) and c.thresholds[0].threshold == 0.75


def test_missing_rejected_non_final_and_absent_slots_are_separate_exclusions_and_the_interval_is_incomplete():
    g = [IN_D2, "20220302151500", IN_D2_B, "20220302154500"]
    w = World(drop_slots={g[0]}, state={g[1]: "absent", g[2]: "nonfinal"}, row_over={g[3]: {"rows_captured": 5}})
    r = w.run()
    c = r.interval(D2).coverage
    assert c.excluded_by_reason == {"missing": 1, "rejected": 1, "non_final": 1, "final_absent": 1, "delayed_after_cutoff": 0,
                                    "near_empty": 0, "near_empty_unknown": 0}
    assert (c.n_expected, c.n_covered, c.max_consecutive_missing_run) == (96, 92, 4)
    assert r.interval(D2).assessment.source is cp.SourceCompleteness.INCOMPLETE and r.interval(D3).coverage.n_covered == 96


def test_a_delayed_batch_is_judged_by_verified_availability_and_the_existing_cutoff_rule():
    r = World(avail={LAST_D2: CUT2, IN_D2: CUT2 + timedelta(seconds=1)}).run()
    c = r.interval(D2).coverage
    assert slot(r, LAST_D2).state == "reconciled" and slot(r, IN_D2).state == "delayed"                  # exactly at the cutoff is on time
    assert c.excluded_by_reason["delayed_after_cutoff"] == 1 and (c.n_expected, c.n_covered) == (96, 95)
    assert r.interval(D3).coverage.n_expected == 96                                                       # the delayed batch added nothing next door


def test_a_late_earlier_batch_never_changes_a_denominator_or_a_numerator():
    r = World({PRE: [{}]}, avail={PRE: PRE_LATE}).run()
    c = r.interval(D2).coverage
    assert r.interval(D2).n_earlier_arrivals == 1 and (c.n_expected, c.n_covered, c.ratio) == (96, 96, 1.0)


def test_explicit_near_empty_and_unknown_null_are_distinct_exclusions_and_neither_is_missing():
    r = World(row_over={IN_D2: {"near_empty_flag": 1}, IN_D2_B: {"near_empty_flag": None}}).run()
    c = r.interval(D2).coverage
    assert c.excluded_by_reason["near_empty"] == 1 and c.excluded_by_reason["near_empty_unknown"] == 1 and c.excluded_by_reason["missing"] == 0
    assert (slot(r, IN_D2).near_empty, slot(r, IN_D2_B).near_empty) == (True, None) and c.max_consecutive_missing_run == 0
    a = r.interval(D2).assessment
    assert (a.n_near_empty, a.n_near_empty_unknown, a.usability) == (1, 1, cp.IntervalUsability.UNDECIDED_POLICY)


def test_the_coverage_ratio_and_thresholds_never_turn_an_unverified_empty_theme_into_verified_no_news():
    def evidence(r):
        return {d: (i.no_news_basis, {t: e.evidence for t, e in i.theme_evidence.items()}) for d in (D2, D3) for i in [r.interval(d)]}
    for kw in (dict(drop_slots={IN_D2}), dict(row_over={IN_D2: {"near_empty_flag": None}}), dict(row_over={IN_D2: {"near_empty_flag": 1}}),
               dict(avail={IN_D2: CUT2 + timedelta(minutes=1)})):
        w = World(**kw)
        runs = [w.run(coverage_thresholds=cr.CoverageThresholds(p, s)) for p, s in ((0.75, (0.5, 0.9)), (0.99, (0.5,)), (0.10, (0.2,)), (1.0, (0.3,)))]
        assert all(evidence(x) == evidence(runs[0]) for x in runs), kw
        assert runs[0].interval(D2).coverage.ratio > 0.98                                                  # far above every threshold
        assert runs[0].interval(D2).no_news_basis["gold"].startswith("unverified_empty"), kw
        assert all(e.evidence == "unverified_empty" for e in runs[0].interval(D2).theme_evidence.values() if e.evidence != "has_records")
    full = World().run(coverage_thresholds=cr.CoverageThresholds(0.99, (0.5,)))
    assert full.interval(D2).no_news_basis["gold"] == "verified_complete_no_records"                      # only full evidence verifies


def test_below_threshold_coverage_with_the_policy_unapplied_is_undecided_not_unusable():
    flags = {b: {"near_empty_flag": 1} for b in World().batches[:60]}                              # 60 of D2's 96 slots explicitly near-empty
    r = World(row_over=flags).run()
    c, a = r.interval(D2).coverage, r.interval(D2).assessment
    assert c.ratio < 0.5 and not any(t.meets for t in c.thresholds)
    assert a.usability is cp.IntervalUsability.UNDECIDED_POLICY and a.source is cp.SourceCompleteness.COMPLETE        # source complete, usability undecided
    assert {e.result_availability for e in r.interval(D2).theme_evidence.values()} == {"blocked_by_policy"}


def test_a_usable_interval_is_still_not_scoreable_while_policies_are_unresolved():
    r = World({IN_D2: [{}]}).run()
    assert r.interval(D2).assessment.usability is cp.IntervalUsability.USABLE
    assert {e.result_availability for e in r.interval(D2).theme_evidence.values()} == {"blocked_by_policy"}
    assert r.policy_status["source_coverage_threshold"] == "APPLIED_PROVISIONAL" and r.policy_state().unresolved()
    assert r.policy_status["near_empty_slot_handling"] == "APPLIED_PROVISIONAL"


def test_source_coverage_is_a_separate_block_with_no_scoring_coverage_or_value_in_it():
    c = World().run().interval(D2).coverage
    assert c.kind == "source_slot_coverage"
    assert not [f.name for f in dataclasses.fields(c) if "scor" in f.name or "sentiment" in f.name or "feature" in f.name]
    assert not hasattr(World().run().interval(D2), "scoring_coverage")


# ---- derived near-empty through the orchestrator, with a synthetic 14-day baseline

def base_slot(b: str, ev: int, *, final: bool = True, fv: str = FV):
    if final:
        row = dict(batch_ts=b, existence="present_verified", fetch_status="fetched", parse_status="parsed_validated", commit_status="committed",
                   availability_status="verified", available_at_utc=format_utc(nominal(b) + timedelta(minutes=15)), near_empty_flag=0,
                   filter_version=fv, parser_version="gkg_parser_v1", rows_physical=ev + 12, rows_malformed=2, rows_date_mismatch=0,
                   rows_translated=0, rows_non_web=0, rows_english_valid=ev, rows_captured=0, rows_company_item=0, rows_dup_same_batch=0,
                   rows_audit_sample=1, availability_flags="", late_flag=0)
    else:
        row = dict(batch_ts=b, existence="available", fetch_status="in_progress", parse_status="pending", commit_status="pending",
                   availability_status="pending", available_at_utc=None)
    series = [dict(batch_ts=b, filter_version=fv, series=s, rows=0, rows_us_relevant=0, new_stories=None) for s in ("EQUITY_US", "RATES_US", "GOLD")]
    return row, series


def format_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def with_baseline(values, **kw):
    """A World (no lookback) plus 14 prior-day observations of the slot ``T``; returns (world, extra slot rows, extra series rows)."""
    rows, series = [], []
    for s, v in zip(stamps_before(T, range(1, 15)), values):
        if v is None:
            continue
        r_, s_ = base_slot(s, v, **kw)
        rows.append(r_)
        series += s_
    w = World(lookback=False)
    return w, w.slot_rows + rows, w.series_rows + series


def run_with(values, *, declared=DECLARED, observed_flag=0, **kw):
    w, rows, series = with_baseline(values, **kw)
    rows = [dict(r, near_empty_flag=observed_flag) if r["batch_ts"] == T else r for r in rows]
    return w.run(slot_rows=rows, series_rows=series, baseline_batches_from=declared)


def test_without_a_declared_baseline_every_derived_state_is_unknown_and_the_observed_flag_still_rules_coverage():
    r = World().run()
    v = slot(r, T)
    assert (v.near_empty, v.derived_near_empty, v.derived_reason, v.flag_comparison) == (False, "unknown", "no_baseline_evidence_declared", "observed_only")
    assert r.interval(D2).derived_near_empty == {"near_empty": 0, "not_near_empty": 0, "unknown": 96, "not_applicable": 0}
    assert r.interval(D2).coverage.n_covered == 96 and r.baseline_batches_from is None and r.n_baseline_rows == 0


def test_with_a_declared_committed_baseline_the_derived_state_is_decided_and_kept_apart_from_the_observed_flag():
    r = run_with([200] * 14)                                           # the slot has 10 english-valid rows against a median of 200: near-empty
    v = slot(r, T)
    assert (v.derived_near_empty, v.derived_reason) == ("near_empty", "decided")
    assert v.near_empty is False and v.flag_comparison == "disagree"   # the observed flag says not near-empty; neither is overwritten
    c = r.interval(D2).coverage
    assert c.excluded_by_reason["near_empty"] == 0 and c.n_covered == 96                  # coverage follows the observed flag only
    assert r.interval(D2).derived_near_empty["near_empty"] == 1
    assert r.n_baseline_rows >= 14


def test_a_null_observed_flag_with_a_decided_baseline_is_derived_only_and_still_unknown_for_coverage():
    r = run_with([50] * 14, observed_flag=None)
    v = slot(r, T)
    assert (v.derived_near_empty, v.flag_comparison, v.near_empty) == ("not_near_empty", "derived_only", None)
    assert r.interval(D2).coverage.excluded_by_reason["near_empty_unknown"] == 1                  # the derived state does not repair a NULL


def test_insufficient_uncommitted_and_missing_baselines_are_explicit_unknown_never_false():
    few = run_with([200] * 6 + [None] * 8)
    assert (slot(few, T).derived_near_empty, slot(few, T).derived_reason) == ("unknown", "insufficient_valid_baseline")
    unc = run_with([200] * 14, final=False)
    assert (slot(unc, T).derived_near_empty, slot(unc, T).derived_reason) == ("unknown", "baseline_not_committed")      # all 14 observed but none committed: not usable, and said so
    mixed_w, rows, series = with_baseline([200] * 14)
    stamps = stamps_before(T, range(1, 9))
    for i, rw in enumerate(rows):
        if rw["batch_ts"] in stamps:
            rows[i] = {**rw, "existence": "available", "fetch_status": "in_progress", "parse_status": "pending", "commit_status": "pending"}
    mixed = mixed_w.run(slot_rows=rows, series_rows=series, baseline_batches_from=DECLARED)
    assert (slot(mixed, T).derived_near_empty, slot(mixed, T).derived_reason) == ("unknown", "baseline_not_committed")
    late = run_with([200] * 14, declared=format_batch_stamp(parse_batch_stamp(DECLARED) + timedelta(minutes=15)))
    assert slot(late, T).derived_reason == "baseline_lookback_not_available"
    wrong = run_with([200] * 14, fv="other_filter_version")                  # rows of another filter version are never mixed in
    assert slot(wrong, T).derived_near_empty == "unknown"


def test_the_baseline_uses_only_prior_observations_even_when_later_ones_are_in_the_manifest():
    base = run_with([200] * 14)
    w, rows, series = with_baseline([200] * 14)
    # the same slot on the following days is in the window itself: change what it says, the earlier verdict must not move
    rows = [dict(r, rows_english_valid=10_000_000) if r["batch_ts"] in ("20220303150000",) else r for r in rows]
    assert slot(w.run(slot_rows=rows, series_rows=series, baseline_batches_from=DECLARED), T).derived_near_empty == slot(base, T).derived_near_empty


def test_the_baseline_declaration_is_validated_and_never_extends_the_window():
    w = World()
    for bad in ("garbage", "20220301211500", "20220305000000"):
        with pytest.raises(orc.OrchestratorError):
            w.run(baseline_batches_from=bad)
    r = w.run(baseline_batches_from="20220201000000")
    assert len(r.slots) == 192 and [i.origin_date for i in r.intervals] == [D2, D3]


def test_the_digest_binds_the_thresholds_the_detector_parameters_and_the_baseline_declaration():
    w = World()
    base = w.run()
    assert w.run().digest() == base.digest()
    assert w.run(coverage_thresholds=cr.CoverageThresholds(0.8)).digest() != base.digest()
    assert w.run(near_empty_params=ne.NearEmptyParams(min_baseline_obs=6)).digest() != base.digest()
    assert w.run(baseline_batches_from="20220201000000").digest() != base.digest()
    assert run_with([200] * 14).digest() != run_with([100] * 14).digest()


def test_c_min_behaviour_is_intact_with_the_new_fields_at_their_defaults():
    w = World({PRE: [{}]}, avail={PRE: PRE_LATE})
    r = w.run()
    assert r.interval(D2).status == "accounted_with_delayed" and r.earlier_batches_from == w.lookback_from
    assert w.run(earlier_batches_from=None).interval(D2).status == "incomplete_accounting"                 # no lookback: fail closed, unchanged
    assert w.run(earlier_batches_from=None).interval(D2).coverage.n_covered == 96                           # coverage is source-slot coverage only
