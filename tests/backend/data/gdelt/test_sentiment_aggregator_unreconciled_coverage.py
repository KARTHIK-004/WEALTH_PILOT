"""S2.8J: owner decision OD-10 part 2. A processed slot that fails reconciliation is excluded from the aggregator's coverage numerator.

Only the numerator (and the values that follow from it: ``coverage``, ``n_slots_covered``, and the status/reason when the ratio crosses the
configured threshold) changes. The denominator, the grid, ``no_news`` semantics, the shared block's vocabulary and every policy are untouched.
Synthetic only; offline.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import coverage_report as cr
from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment.completeness import SlotAccount

_spec = importlib.util.spec_from_file_location("_wp_scaffold_world2", Path(__file__).with_name("test_sentiment_scaffold.py"))
S = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = S
_spec.loader.exec_module(S)


def bad(slots, n):
    """The first ``n`` slots of D2 are processed with a wrong ``rows_captured`` (a reconciliation failure)."""
    return S.set_slots(slots, S.D2, range(n), lambda t: S.processed(t, rows=10, theme_rows={"equity_us": 10, "rates_us": 0, "gold": 0}))


def d2(rows, theme="equity_us"):
    return S.row(rows, S.D2, theme)


def test_unreconciled_slots_leave_the_numerator_and_the_denominator_stays_the_full_grid():
    for n in (1, 8, 24):
        r = d2(S.agg([], slots=bad(S.slots_for([]), n)))
        assert (r.n_slots_expected, r.n_slots_covered) == (96, 96 - n), n
        assert r.coverage == pytest.approx((96 - n) / 96)                              # the existing formula, only the numerator differs
        assert r.coverage_report.n_covered == r.n_slots_covered and r.coverage_report.n_expected == r.n_slots_expected
        assert r.coverage_report.excluded_by_reason["rejected"] == n


def test_status_stays_a_mismatch_while_the_ratio_meets_the_configured_threshold_and_never_becomes_ok():
    r = d2(S.agg([], slots=bad(S.slots_for([]), 24)))                                  # 72 / 96 = 0.75 meets the threshold exactly
    assert r.coverage_status == "slot_article_mismatch" and r.no_news is None and r.interval_usability == "unusable_incomplete"
    other = S.row(S.agg([], slots=bad(S.slots_for([]), 24)), S.D3)
    assert other.coverage_status == "ok" and other.n_slots_covered == 96                # the other interval is untouched


def test_enough_unreconciled_slots_cross_the_informational_threshold_but_the_mismatch_status_stays():
    r = d2(S.agg([], slots=bad(S.slots_for([]), 25)))                                  # 71 / 96 < 0.75
    assert r.coverage_status == "slot_article_mismatch" and "rows_captured 10 but 0" in r.reason                  # integrity, not ratio, decides
    assert (r.n_slots_covered, r.coverage_threshold_met) == (71, False) and r.no_news is None
    everything = d2(S.agg([], slots=bad(S.slots_for([]), 96)))
    assert (everything.n_slots_covered, everything.coverage, everything.coverage_status) == (0, 0.0, "slot_article_mismatch")
    assert everything.n_slots_delayed == 0 and everything.coverage_report.excluded_by_reason["rejected"] == 96   # rejected, not "missing"


def test_unreconciliation_does_not_leak_into_other_meanings():
    mixed = S.set_slots(S.slots_for([]), S.D2, range(2), S.absent)                      # 2 final-absent
    mixed = S.set_slots(mixed, S.D2, [2], lambda t: S.processed(t, near=True))           # 1 explicit near-empty
    mixed = S.set_slots(mixed, S.D2, [3], lambda t: S.processed(t, near=None))           # 1 unknown
    mixed = S.set_slots(mixed, S.D2, [4], lambda t: S.processed(t, at=S.verified(t) + timedelta(hours=30)))   # 1 delayed
    mixed = S.set_slots(mixed, S.D2, [5, 6], lambda t: S.processed(t, rows=7, theme_rows={"equity_us": 7, "rates_us": 0, "gold": 0}))
    r = d2(S.agg([], slots=mixed))
    assert (r.n_slots_covered, r.n_slots_near_empty, r.n_slots_delayed, r.n_slots_near_empty_unknown) == (96 - 2 - 1 - 1 - 1 - 2, 1, 1, 1)
    e = r.coverage_report.excluded_by_reason
    assert (e["final_absent"], e["near_empty"], e["near_empty_unknown"], e["delayed_after_cutoff"], e["rejected"], e["missing"]) == (2, 1, 1, 1, 2, 0)


def test_both_numerators_agree_across_scenarios_that_the_aggregator_can_classify():
    a = S.art(1, S.IN_D2)
    i = S.grid(S.D1, S.D2).index(S.IN_D2)
    base = S.slots_for([a])
    scenarios = [S.agg([a]), S.agg([]), d2_all(bad(S.slots_for([]), 8)), S.agg([a], slots=S.set_slots(base, S.D2, range(10), S.absent)),
                 S.agg([a], slots=S.set_slots(base, S.D2, [i], lambda t: S.processed(t, [a], rows=1000))),
                 S.agg([], slots=S.set_slots(S.slots_for([]), S.D2, range(96), lambda t: S.processed(t, near=None))),
                 S.agg([], slots=S.set_slots(S.slots_for([]), S.D2, range(10), lambda t: S.processed(t, near=True)))]
    for rows in scenarios:
        for r in rows:
            if r.coverage_report is not None and r.n_slots_covered is not None:
                assert r.coverage_report.n_covered == r.n_slots_covered and r.coverage_report.n_expected == r.n_slots_expected, r


def d2_all(slots):
    return S.agg([], slots=slots)


def test_a_processed_slot_with_no_reconciliation_verdict_fails_closed():
    slots = S.slots_for([])[S.D2]
    grid_ = [s.batch_ts for s in slots]
    cutoff = S.cutoff_utc(S.D2, S.CFG.early_closes)
    from wealthpilot.data.gdelt.sentiment.completeness import IntervalEarlier
    day = S.ft._assess_day(S.D2, slots, grid_, None, cutoff, {}, [], IntervalEarlier(), S.CFG)           # no verdict for any slot
    assert day.n_covered == 0 and day.n_expected == 96 and day.status == "slot_article_mismatch" and "no reconciliation result" in day.reason         # fails closed whatever the ratio
    ok = S.ft._assess_day(S.D2, slots, grid_, None, cutoff, {t: [] for t in grid_}, [], IntervalEarlier(), S.CFG)
    assert ok.n_covered == 96 and ok.status == "ok"


def test_reconciliation_is_never_inferred_from_a_count_or_a_favourable_ratio():
    a = S.art(1, S.IN_D2)
    i = S.grid(S.D1, S.D2).index(S.IN_D2)
    slots = S.set_slots(S.slots_for([a]), S.D2, [i], lambda t: S.processed(t, [a], rows=2, theme_rows={"equity_us": 2, "rates_us": 0, "gold": 0}))
    r = d2(S.agg([a], slots=slots))
    assert r.n_slots_covered == 95 and r.coverage == pytest.approx(95 / 96) and r.coverage_status == "slot_article_mismatch"   # 99% is not "reconciled"


def test_nothing_else_moved_policies_thresholds_and_the_block_vocabulary():
    assert [n for n, _ in orc.PolicyState.from_mapping(orc.POLICY_STATUS).unresolved()] == ["scorer_approval_and_polarity_validation"]
    assert orc.POLICY_STATUS["source_coverage_threshold"] == "APPLIED_PROVISIONAL"
    assert (S.CFG.coverage_threshold, cr.CoverageThresholds().primary, cr.EXCLUSION_REASONS) == (
        0.75, 0.75, ("missing", "rejected", "non_final", "final_absent", "delayed_after_cutoff", "near_empty", "near_empty_unknown"))
    assert SlotAccount.REJECTED.value == "rejected"
    text = (S.PKG / "features.py").read_text(encoding="utf-8")
    assert "coverage_rule_decision" not in text


def test_clean_days_are_byte_for_byte_what_they_were():
    r = d2(S.agg([S.art(1, S.IN_D2)]))
    assert (r.coverage, r.coverage_status, r.n_slots_covered) == (1.0, "ok", 96)
    empty = d2(S.agg([]))
    assert (empty.no_news, empty.reason, empty.coverage_report.ratio) == (True, "verified_no_news", 1.0)
    assert dataclasses.is_dataclass(r.coverage_report)
