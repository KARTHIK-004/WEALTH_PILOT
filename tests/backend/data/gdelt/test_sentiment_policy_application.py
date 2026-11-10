"""The owner's policy-application decisions of 2026-10-20, as the live table now states them. Synthetic fixtures; nothing here validates a model or a hypothesis."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment import pipeline as pl
from wealthpilot.data.gdelt.sentiment.completeness import IntervalUsability
from wealthpilot.data.gdelt.sentiment.policy import APPLIED_APPROVED, PolicyBlockedError, PolicyState, REQUIRED_POLICIES, require_policies_applied


def load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(name))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


W = load("test_sentiment_orchestrator.py", "_wp_world_pa")
S = load("test_sentiment_scaffold.py", "_wp_scaffold_pa")
LIVE = PolicyState.from_mapping(orc.POLICY_STATUS)

EXPECTED = {
    "deduplication_and_story_updates": "APPLIED_PROVISIONAL",
    "cross_interval_story_uniqueness": "APPLIED_APPROVED",
    "source_coverage_threshold": "APPLIED_PROVISIONAL",
    "scoring_coverage_threshold": "APPLIED_APPROVED",
    "scorer_approval_and_polarity_validation": "UNRESOLVED_NOT_APPLIED",
    "near_empty_slot_handling": "APPLIED_PROVISIONAL",
    "holiday_and_early_close_calendars": "APPLIED_PROVISIONAL",
    "late_batch_strictness": "APPLIED_PROVISIONAL",
}


def test_the_live_table_states_exactly_the_owner_decisions():
    assert {n: orc.POLICY_STATUS[n] for n in REQUIRED_POLICIES} == EXPECTED
    assert [n for n, _ in LIVE.unresolved()] == ["scorer_approval_and_polarity_validation"]
    assert set(LIVE.provisional()) == {n for n, s in EXPECTED.items() if s == "APPLIED_PROVISIONAL"}          # provisional stays distinguishable from approved
    assert orc.POLICY_STATUS["theme_specific_calendars"] == "NOT_IMPLEMENTED" and orc.POLICY_STATUS["scoring"] == "NOT_PERFORMED"
    with pytest.raises(PolicyBlockedError, match="scorer_approval_and_polarity_validation"):
        require_policies_applied(LIVE)


def test_only_the_scorer_policy_blocks_downstream_use_and_it_stays_blocked_until_the_owner_resolves_it():
    g = pl.blocking_gates(LIVE)
    assert g["tone_derived"] == ("scorer_approval_and_polarity_validation=UNRESOLVED_NOT_APPLIED",)           # the all-eight gate is kept: not narrowed
    assert g["scoring"][0].startswith("scorer_approval_and_polarity_validation=")
    arts = [S.art(1, S.IN_D2)]
    with pytest.raises(PolicyBlockedError):
        S.aggregate(arts, S.DAYS, S.slots_for(arts), config=dataclasses.replace(S.CFG, policy=LIVE))        # features still refuse under the live table
    with_scorer = PolicyState.from_mapping({**orc.POLICY_STATUS, "scorer_approval_and_polarity_validation": APPLIED_APPROVED})       # TEST FIXTURE only
    assert S.aggregate(arts, S.DAYS, S.slots_for(arts), config=dataclasses.replace(S.CFG, policy=with_scorer))


def test_a_provisional_coverage_threshold_is_informational_and_never_decides_usability():
    flags = {b: {"near_empty_flag": 1} for b in W.World().batches[:60]}                       # 60 of 96 explicitly near-empty: ratio < 0.5
    r = W.World(row_over=flags).run()
    c, a = r.interval(W.D2).coverage, r.interval(W.D2).assessment
    assert c.ratio < 0.5 and not any(t.meets for t in c.thresholds)                          # the verdict is reported ...
    assert a.usability is IntervalUsability.UNDECIDED_POLICY                                 # ... but it neither blocks nor promotes the interval
    unknown = W.World(row_over={b: {"near_empty_flag": None} for b in W.World().batches[:2]}).run().interval(W.D2)
    assert unknown.assessment.usability is IntervalUsability.UNDECIDED_POLICY and unknown.no_news_basis["gold"].startswith("unverified_empty")   # unknown stays unknown
    assert {e.result_availability for e in r.interval(W.D2).theme_evidence.values()} == {"blocked_by_policy"}


def test_residual_limitations_are_part_of_every_result():
    declared = W.World().run()
    text = " | ".join(declared.residual_limitations())
    assert "caller-supplied and unverified" in text and "provisional and informational" in text and "unknown stays unknown" in text
    assert f"from {declared.earlier_batches_from} onward" in text and "could still arrive" in text            # the completeness limit of the declared lookback
    assert "no derived baseline evidence was declared" in text
    none = W.World(lookback=False).run()
    assert any("NOT examined" in x and "every interval is incomplete" in x for x in none.residual_limitations())
    base = W.World(lookback=False).run(baseline_batches_from="20220201000000")
    assert any("manifest rows from 20220201000000 onward" in x for x in base.residual_limitations())


def test_the_pipeline_carries_the_limitations_and_still_blocks_scoring_and_features():
    p = pl.run_pipeline(W.World().inputs())
    reasons = p.stage("accounting").reasons
    assert sum(r.startswith("limitation: ") for r in reasons) == 5
    assert p.stage("scoring").status is pl.StageStatus.BLOCKED_NO_SCORER
    assert p.stage("features").status is pl.StageStatus.BLOCKED_BY_POLICY and sum("=" in x for x in p.stage("features").reasons) == 1
    assert p.stage("tone_derived").status is pl.StageStatus.BLOCKED_BY_POLICY and p.tone_derived == ()
    assert p.stage("evaluation").status is pl.StageStatus.BLOCKED_NOT_APPROVED


def test_provenance_records_each_owner_decision():
    assert set(REQUIRED_POLICIES) <= set(orc.POLICY_PROVENANCE)
    assert "BLOCKED" in orc.POLICY_PROVENANCE["scorer_approval_and_polarity_validation"]
    assert "informationally" in orc.POLICY_PROVENANCE["source_coverage_threshold"] and "unverified" in orc.POLICY_PROVENANCE["holiday_and_early_close_calendars"]
    assert "report-only" in orc.POLICY_PROVENANCE["scoring_coverage_threshold"] and "no unique-story claim" in orc.POLICY_PROVENANCE["cross_interval_story_uniqueness"]
