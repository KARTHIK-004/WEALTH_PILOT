"""S2.8B (F6): the policy state is immutable and unresolved required policies block downstream use. Synthetic; offline.

There is no scorer and no ``ArticleRecord`` conversion yet, so the existing downstream boundary is ``features.aggregate_daily`` (feature
generation). The guard is also a standalone contract (``policy.require_policies_applied``).
"""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from wealthpilot.data.gdelt.sentiment import features as ft
from wealthpilot.data.gdelt.sentiment.completeness import EarlierEvidence
from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment import policy as pol
from wealthpilot.data.gdelt.sentiment import schema as sc

ALL_UNRESOLVED = {n: "UNRESOLVED_NOT_APPLIED" for n in pol.REQUIRED_POLICIES}
ALL_APPLIED = {n: pol.APPLIED_APPROVED for n in pol.REQUIRED_POLICIES}          # a TEST FIXTURE; production code never builds this
D1, D2 = date(2022, 3, 1), date(2022, 3, 2)


def aggregate(*args, **kwargs):
    kwargs.setdefault("earlier", EarlierEvidence.none_found())
    return ft.aggregate_daily(*args, **kwargs)


def config(state, **kw):
    return ft.SentimentConfig(coverage_threshold=0.75, early_closes=frozenset(), market_holidays=frozenset(),
                              dedup=ft.PROPOSED_DEDUP_POLICY, expected_model_id="AUDIT_NO_SCORER", expected_model_revision="r0",
                              expected_scorer_code_sha256="0" * 64, policy=state, **kw)


def test_the_policy_state_is_an_immutable_snapshot():
    state = pol.PolicyState.from_mapping(ALL_UNRESOLVED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.items = ()                                                                            # type: ignore[misc]
    assert isinstance(state.items, tuple) and state.items == tuple(sorted(state.items))
    with pytest.raises(TypeError):
        state.as_mapping()["scoring"] = "x"                                                          # type: ignore[index]
    with pytest.raises(pol.PolicyBlockedError):
        pol.PolicyState([("a", "b")])                                                                # type: ignore[arg-type]
    with pytest.raises(pol.PolicyBlockedError):
        pol.PolicyState((("b", "x"), ("a", "y")))                                                    # unsorted
    with pytest.raises(pol.PolicyBlockedError):
        pol.PolicyState.from_mapping([("a", "b")])                                                   # type: ignore[arg-type]


def test_mutating_the_original_mapping_cannot_bypass_the_guard():
    source = dict(ALL_UNRESOLVED)
    state = pol.PolicyState.from_mapping(source)
    source.update(ALL_APPLIED)                                                                       # flipped AFTER the snapshot
    assert state.status("source_coverage_threshold") == "UNRESOLVED_NOT_APPLIED"
    with pytest.raises(pol.PolicyBlockedError):
        pol.require_policies_applied(state)
    approved_source = dict(ALL_APPLIED)
    approved = pol.PolicyState.from_mapping(approved_source)
    approved_source["source_coverage_threshold"] = "UNRESOLVED_NOT_APPLIED"                         # the snapshot is also not weakened
    assert pol.require_policies_applied(approved) is approved
    with pytest.raises(pol.PolicyBlockedError, match="PolicyState is required"):
        pol.require_policies_applied(dict(ALL_APPLIED))                                              # a plain mapping is refused outright  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["UNRESOLVED_NOT_APPLIED", "SELECTED_NOT_APPLIED", "SELECTED_PROVISIONAL_NOT_APPLIED",
                                    "CALLER_SUPPLIED_NOT_APPROVED", "MINIMUM_POINT_IN_TIME_ONLY", "NOT_IMPLEMENTED", "approved", "",
                                    "SELECTED_APPLIED_LOOKBACK_UNDECIDED"])
def test_only_applied_statuses_unblock(status):
    state = pol.PolicyState.from_mapping({**ALL_APPLIED, "near_empty_slot_handling": status or "x"})
    with pytest.raises(pol.PolicyBlockedError, match="near_empty_slot_handling"):
        pol.require_policies_applied(state)


def test_a_missing_required_policy_blocks_and_the_error_names_every_unresolved_one():
    state = pol.PolicyState.from_mapping({k: v for k, v in ALL_APPLIED.items() if k != "late_batch_strictness"})
    with pytest.raises(pol.PolicyBlockedError, match="late_batch_strictness=None"):
        pol.require_policies_applied(state)
    with pytest.raises(pol.PolicyBlockedError, match=r"8 required policy decision"):
        pol.require_policies_applied(pol.PolicyState.from_mapping({}))
    assert len(pol.PolicyState.from_mapping(ALL_UNRESOLVED).unresolved()) == 8


def test_applied_provisional_passes_but_stays_visible():
    mixed = pol.PolicyState.from_mapping({**ALL_APPLIED, "source_coverage_threshold": pol.APPLIED_PROVISIONAL})
    assert pol.require_policies_applied(mixed).provisional() == ("source_coverage_threshold",)
    assert pol.PolicyState.from_mapping(ALL_APPLIED).provisional() == ()


def test_the_orchestrators_own_policy_status_is_immutable_and_blocks_every_required_policy():
    with pytest.raises(TypeError):
        orc.POLICY_STATUS["scoring"] = "PERFORMED"                                                   # type: ignore[index]
    state = pol.PolicyState.from_mapping(orc.POLICY_STATUS)
    assert {n for n, _ in state.unresolved()} == {"scorer_approval_and_polarity_validation"}         # the owner applied seven; the scorer policy stays blocked
    assert set(state.provisional()) == {"deduplication_and_story_updates", "source_coverage_threshold", "near_empty_slot_handling",
                                        "holiday_and_early_close_calendars", "late_batch_strictness"}      # provisional ones stay visible as provisional
    unapplied = pol.PolicyState.from_mapping({n: "UNRESOLVED_NOT_APPLIED" for n in pol.REQUIRED_POLICIES})
    assert len(unapplied.unresolved()) == 8
    with pytest.raises(pol.PolicyBlockedError):
        pol.require_policies_applied(state)
    assert orc.POLICY_STATUS["scoring"] == "NOT_PERFORMED" and orc.POLICY_STATUS["source_coverage_threshold"] == "APPLIED_PROVISIONAL"


def test_feature_generation_is_blocked_while_a_required_policy_is_unresolved():
    blocked = config(pol.PolicyState.from_mapping(orc.POLICY_STATUS))
    with pytest.raises(pol.PolicyBlockedError, match="not applied"):
        aggregate([], [D1, D2], {}, config=blocked)                                         # blocked before anything else is read
    with pytest.raises(pol.PolicyBlockedError):
        aggregate([], [D1, D2], {}, config=config(pol.PolicyState.from_mapping(ALL_UNRESOLVED)))
    ok = aggregate([], [D1, D2], {}, config=config(pol.PolicyState.from_mapping(ALL_APPLIED)))
    assert {r.coverage_status for r in ok} == {"no_expected_slots"}                                  # with an applied (test) state it proceeds as before


def test_a_config_refuses_a_plain_mapping_as_its_policy():
    with pytest.raises(ft.SentimentFeatureError, match="PolicyState"):
        config(dict(ALL_APPLIED))                                                                    # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ft.SentimentConfig(coverage_threshold=0.75, early_closes=frozenset(), market_holidays=frozenset(), dedup=ft.PROPOSED_DEDUP_POLICY,
                           expected_model_id="m", expected_model_revision="r", expected_scorer_code_sha256="0" * 64)   # no default policy


def test_the_guard_does_not_depend_on_a_scorer_or_records():
    assert "fake_scorer" not in pol.__dict__ and not hasattr(pol, "ArticleRecord")
    assert sc.TEST_ONLY_MODEL_ID not in open(pol.__file__, encoding="utf-8").read()
