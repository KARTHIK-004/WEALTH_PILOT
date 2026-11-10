"""The configured coverage threshold is INFORMATIONAL (owner decision 2026-10-20): it is reported, and it neither suppresses features nor decides usability. Every evidence-integrity rule still fails closed whatever the ratio.
Synthetic fixtures only."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment import pipeline as pl
from wealthpilot.data.gdelt.sentiment.completeness import EarlierEvidence, IntervalEarlier
from wealthpilot.data.gdelt.sentiment.policy import PolicyBlockedError, PolicyState

_spec = importlib.util.spec_from_file_location("_wp_scaffold_info", Path(__file__).with_name("test_sentiment_scaffold.py"))
S = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = S
_spec.loader.exec_module(S)

A = S.art(1, S.IN_D2)
I = S.grid(S.D1, S.D2).index(S.IN_D2)


def cfg(t):
    return dataclasses.replace(S.CFG, coverage_threshold=t)


def d2(rows, theme="equity_us"):
    return S.row(rows, S.D2, theme)


def VALUES(r):
    """Everything a consumer reads, except the informational threshold fields."""
    skip = {"coverage_threshold", "coverage_threshold_met", "coverage_report"}
    return {f.name: getattr(r, f.name) for f in dataclasses.fields(r) if f.name not in skip}


def with_absent(n, arts=(A,)):
    """First n slots final-absent; the article's own slot (index I) must stay processed."""
    assert n <= I
    return S.set_slots(S.slots_for(list(arts)), S.D2, range(n), S.absent)


# ================================================================ visibility

def test_the_configured_threshold_and_the_measurement_are_always_visible():
    r = d2(S.agg([A], slots=with_absent(40)))
    assert (r.coverage, r.coverage_threshold, r.coverage_threshold_met) == (pytest.approx(56 / 96), 0.75, False)
    primary = r.coverage_report.thresholds[0]
    assert (primary.label, primary.threshold, primary.meets) == ("primary", 0.75, False) and r.coverage_report.ratio == pytest.approx(56 / 96)
    ok = d2(S.agg([A]))
    assert (ok.coverage, ok.coverage_threshold_met) == (1.0, True)
    for t in (0.5, 0.9, 0.3, 1.0):                                                                 # a configured value equal to a sensitivity value must not break the report
        r = d2(S.agg([A], cfg=None, slots=with_absent(40), config=cfg(t)) if False else S.aggregate([A], S.DAYS, with_absent(40), config=cfg(t)))
        assert r.coverage_threshold == t and r.coverage_threshold_met is (56 / 96 >= t) and r.coverage_report.thresholds[0].threshold == t
        assert len({x.threshold for x in r.coverage_report.thresholds}) == len(r.coverage_report.thresholds)
    none = d2(S.agg([A], slots={k: v for k, v in S.slots_for([A]).items() if k != S.D2}))
    assert none.coverage is None and none.coverage_threshold_met is None and none.coverage_threshold == 0.75       # not measurable: not met-or-unmet, and not 0


# ================================================================ informational, not a gate

def test_low_coverage_alone_never_suppresses_features_and_insufficient_coverage_is_never_produced():
    for n in range(0, I + 1, 5):
        r = d2(S.agg([A], slots=with_absent(n)))
        assert r.coverage_status == "ok" and r.n_eligible == 1 and r.mean_net is not None, n
        assert r.coverage_threshold_met is ((96 - n) / 96 >= 0.75)


def test_the_threshold_value_changes_nothing_but_the_threshold_fields():
    slots = with_absent(40)
    base = d2(S.aggregate([A], S.DAYS, slots, config=cfg(0.75)))
    for t in (0.01, 0.5, 0.9, 1.0):
        other = d2(S.aggregate([A], S.DAYS, slots, config=cfg(t)))
        assert VALUES(other) == VALUES(base), t                                                    # same status, features, usability, availability, no_news
        assert other.coverage_threshold == t and other.coverage_threshold_met is (56 / 96 >= t)
    assert (base.interval_usability, base.result_availability, base.source_completeness) == ("undecided_policy", "unavailable", "final_gaps")


# ================================================================ integrity still fails closed, at the most permissive threshold

def test_incomplete_or_unreconciled_evidence_fails_closed_whatever_the_ratio():
    loose = cfg(0.01)
    wrong = S.set_slots(S.slots_for([]), S.D2, range(3), lambda t: S.processed(t, rows=10, theme_rows={"equity_us": 10, "rates_us": 0, "gold": 0}))
    nonfinal = S.set_slots(S.slots_for([]), S.D2, [0], lambda t: S.sl.SlotAccounting(t, "in_progress"))
    cases = {
        "unreconciled": S.aggregate([], S.DAYS, wrong, config=loose),
        "non_final": S.aggregate([], S.DAYS, nonfinal, config=loose),
        "all_absent": S.aggregate([], S.DAYS, S.set_slots(S.slots_for([]), S.D2, range(96), S.absent), config=loose),
        "earlier_unresolved": S.aggregate([], S.DAYS, S.slots_for([]), config=loose, earlier=EarlierEvidence(True, ("20220301100000",))),
        "earlier_not_examined": S.ft.aggregate_daily([], S.DAYS, S.slots_for([]), config=loose, earlier=EarlierEvidence.not_examined()),
    }
    expected = {"unreconciled": "slot_article_mismatch", "non_final": "incomplete_source_accounting", "all_absent": "missing_source_batches",
                "earlier_unresolved": "incomplete_source_accounting", "earlier_not_examined": "incomplete_source_accounting"}
    for name, rows in cases.items():
        r = d2(rows)
        assert r.coverage_status == expected[name], name
        assert r.no_news is None and r.mean_net is None and r.mean_p_pos is None and r.n_eligible is None, name           # nothing computed, nothing neutral
        assert r.result_availability != "available", name


def test_a_processed_slot_with_no_reconciliation_result_fails_closed_at_any_threshold():
    slots = S.slots_for([])[S.D2]
    grid_ = [s.batch_ts for s in slots]
    cutoff = S.cutoff_utc(S.D2, S.CFG.early_closes)
    day = S.ft._assess_day(S.D2, slots, grid_, None, cutoff, {}, [], IntervalEarlier(), cfg(0.01))
    assert day.status == "slot_article_mismatch" and "no reconciliation result" in day.reason


def test_gaps_in_otherwise_valid_evidence_never_become_no_news_or_neutral_even_at_high_coverage():
    cases = {
        "delayed": S.set_slots(S.slots_for([]), S.D2, [5], lambda t: S.processed(t, at=S.verified(t) + timedelta(hours=30))),
        "unknown": S.set_slots(S.slots_for([]), S.D2, [5], lambda t: S.processed(t, near=None)),
        "near_empty": S.set_slots(S.slots_for([]), S.D2, [5], lambda t: S.processed(t, near=True)),
        "absent": S.set_slots(S.slots_for([]), S.D2, [5], S.absent),
    }
    for name, slots in cases.items():
        r = d2(S.aggregate([], S.DAYS, slots, config=cfg(0.5)))
        assert r.coverage >= 0.98 and r.coverage_threshold_met is True, name                        # 95/96: far above any threshold
        assert r.no_news is None and r.theme_evidence == "unverified_empty" and r.mean_net is None, name
        assert r.interval_usability == "undecided_policy" and r.result_availability != "available", name
    assert d2(S.agg([])).no_news is True                                                           # only full, verified evidence gives no-news


# ================================================================ nothing else moved

def test_no_policy_status_changed_and_the_remaining_gate_still_blocks_features():
    live = PolicyState.from_mapping(orc.POLICY_STATUS)
    assert [n for n, _ in live.unresolved()] == ["scorer_approval_and_polarity_validation"] and orc.POLICY_STATUS["source_coverage_threshold"] == "APPLIED_PROVISIONAL"
    with pytest.raises(PolicyBlockedError):
        S.aggregate([A], S.DAYS, S.slots_for([A]), config=dataclasses.replace(S.CFG, policy=live))
    assert pl.blocking_gates(live)["features"][0] == "scorer_approval_and_polarity_validation=UNRESOLVED_NOT_APPLIED"
    text = (S.PKG / "features.py").read_text(encoding="utf-8")
    assert "insufficient_coverage" not in text.split("def _assess_day")[1].split("def _row")[0] and "coverage_rule_met" not in text.split("def _assess_day")[1].split("def _row")[0]
