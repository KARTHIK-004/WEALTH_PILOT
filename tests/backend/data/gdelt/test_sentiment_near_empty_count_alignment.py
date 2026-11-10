"""OD-13 (owner decision): ``n_slots_near_empty`` is aligned with the shared coverage block. A processed slot that fails reconciliation, or has no
reconciliation result, does not contribute. Nothing else may move: denominator, ``n_slots_covered``, coverage, status, ``no_news``, delayed and
unknown handling. Synthetic only; offline.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment.completeness import IntervalEarlier

_spec = importlib.util.spec_from_file_location("_wp_scaffold_world3", Path(__file__).with_name("test_sentiment_scaffold.py"))
S = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = S
_spec.loader.exec_module(S)

WRONG = dict(rows=10, theme_rows={"equity_us": 10, "rates_us": 0, "gold": 0})        # a reconciliation failure (rows_captured 10 but 0 records)


def d2(rows, theme="equity_us"):
    return S.row(rows, S.D2, theme)


def make(near_ok=(), near_bad=(), unknown=(), delayed=()):
    slots = S.slots_for([])
    slots = S.set_slots(slots, S.D2, near_ok, lambda t: S.processed(t, near=True))
    slots = S.set_slots(slots, S.D2, near_bad, lambda t: S.processed(t, near=True, **WRONG))
    slots = S.set_slots(slots, S.D2, unknown, lambda t: S.processed(t, near=None))
    slots = S.set_slots(slots, S.D2, delayed, lambda t: S.processed(t, at=S.verified(t) + timedelta(hours=30)))
    return slots


def test_a_reconciled_near_empty_slot_still_counts():
    r = d2(S.agg([], slots=make(near_ok=range(3))))
    assert r.n_slots_near_empty == 3 and r.coverage_report.excluded_by_reason["near_empty"] == 3
    assert r.n_slots_near_empty == r.coverage_report.excluded_by_reason["near_empty"]


def test_an_unreconciled_near_empty_slot_does_not_count_and_agrees_with_the_block():
    r = d2(S.agg([], slots=make(near_ok=[0, 1], near_bad=[2, 3, 4])))
    assert r.n_slots_near_empty == 2                                                      # before OD-13 this was 5
    e = r.coverage_report.excluded_by_reason
    assert (e["near_empty"], e["rejected"]) == (2, 3) and r.n_slots_near_empty == e["near_empty"]
    assert r.coverage_status == "slot_article_mismatch"


def test_a_slot_with_no_reconciliation_result_does_not_count():
    slots = make(near_ok=range(4))[S.D2]
    cutoff = S.cutoff_utc(S.D2, S.CFG.early_closes)
    grid_ = [s.batch_ts for s in slots]
    none = S.ft._assess_day(S.D2, slots, grid_, None, cutoff, {}, [], IntervalEarlier(), S.CFG)
    assert none.n_near_empty == 0 and none.n_covered == 0
    full = S.ft._assess_day(S.D2, slots, grid_, None, cutoff, {t: [] for t in grid_}, [], IntervalEarlier(), S.CFG)
    assert full.n_near_empty == 4 and full.n_covered == 92
    partial = {t: [] for t in grid_}
    del partial[grid_[0]]                                                                  # one near-empty slot without a verdict
    assert S.ft._assess_day(S.D2, slots, grid_, None, cutoff, partial, [], IntervalEarlier(), S.CFG).n_near_empty == 3


def test_the_denominator_covered_count_ratio_and_status_do_not_change_with_the_alignment():
    r = d2(S.agg([], slots=make(near_ok=[0, 1], near_bad=[2, 3, 4])))
    assert (r.n_slots_expected, r.n_slots_covered) == (96, 91)                              # 96 − 2 near-empty − 3 unreconciled (OD-10 part 2)
    assert r.coverage == pytest.approx(91 / 96) and r.coverage_report.n_covered == 91 and r.coverage_report.n_expected == 96
    assert r.no_news is None
    # near-empty alone (no unreconciled slot) behaves exactly as before
    before = d2(S.agg([], slots=make(near_ok=range(10))))
    assert (before.n_slots_near_empty, before.n_slots_covered, before.coverage_status) == (10, 86, "ok")


def test_unknown_near_empty_stays_unknown_and_is_never_false_or_no_news():
    r = d2(S.agg([], slots=make(near_ok=[0], unknown=[1, 2, 3], near_bad=[4])))
    assert r.n_slots_near_empty == 1 and r.n_slots_near_empty_unknown == 3
    e = r.coverage_report.excluded_by_reason
    assert (e["near_empty_unknown"], e["near_empty"], e["rejected"]) == (3, 1, 1)
    assert r.no_news is not True and r.theme_evidence != "verified_zero_records"
    allunknown = d2(S.agg([], slots=S.set_slots(S.slots_for([]), S.D2, range(96), lambda t: S.processed(t, near=None))))
    assert allunknown.n_slots_near_empty == 0 and allunknown.n_slots_near_empty_unknown == 96 and allunknown.no_news is not True


def test_delayed_and_absent_slots_keep_their_meanings_and_do_not_count_as_near_empty():
    r = d2(S.agg([], slots=make(near_ok=[0], delayed=[5])))
    assert (r.n_slots_near_empty, r.n_slots_delayed) == (1, 1)
    both = S.set_slots(S.set_slots(S.slots_for([]), S.D2, [0], lambda t: S.processed(t, near=True, at=S.verified(t) + timedelta(hours=30))), S.D2, [1], S.absent)
    b = d2(S.agg([], slots=both))
    assert (b.n_slots_near_empty, b.n_slots_delayed) == (0, 1) and b.coverage_report.excluded_by_reason["final_absent"] == 1


def test_other_intervals_and_themes_are_unaffected():
    rows = S.agg([], slots=make(near_ok=[0], near_bad=[1, 2]))
    assert {d2(rows, t).n_slots_near_empty for t in ("equity_us", "rates_us", "gold")} == {1}
    d3 = S.row(rows, S.D3)
    assert (d3.n_slots_near_empty, d3.n_slots_covered, d3.coverage_status, d3.no_news) == (0, 96, "ok", True)
