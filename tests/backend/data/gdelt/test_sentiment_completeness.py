"""S2.8D: the shared completeness vocabulary (completeness.py). Pure and synthetic.

Four distinct concepts as explicit states: source completeness, interval usability, per-theme record evidence, result availability. The
tests enumerate the state space and check the invariants I1-I5 on every reachable combination.
"""

from __future__ import annotations

import dataclasses
import itertools
from datetime import date

import pytest

from wealthpilot.data.gdelt.sentiment import completeness as cp
from wealthpilot.data.gdelt.sentiment.completeness import (
    IntervalEarlier, IntervalUsability as U, NearEmpty as N, ResultAvailability as R, SlotAccount as A, SourceCompleteness as S,
    ThemeEvidence as T,
)

D2 = date(2022, 3, 2)


def ev(account: A, near: N | None = None, b: str = "20220302150000") -> cp.SlotEvidence:
    accounted = account in (A.ACCOUNTED, A.ACCOUNTED_DELAYED)
    return cp.SlotEvidence(b, account, (near or N.NOT_NEAR_EMPTY) if accounted else N.NOT_APPLICABLE)


def grid(*specials: cp.SlotEvidence, n: int = 6) -> list[cp.SlotEvidence]:
    return [ev(A.ACCOUNTED, b=f"2022030215{i:02d}00") for i in range(n)] + list(specials)


def test_the_four_concepts_are_four_separate_vocabularies():
    values = [{m.value for m in e} for e in (S, U, T, R)]
    assert all(len(v) >= 4 for v in values) and not set.intersection(*values)                       # no state name is shared or reused
    assert {m.value for m in A} == {"accounted", "accounted_delayed", "final_absent", "missing", "rejected", "non_final"}
    assert {m.value for m in N} == {"not_near_empty", "near_empty", "unknown", "not_applicable"}


def test_the_near_empty_indicator_applies_to_accounted_slots_only():
    for account in (A.FINAL_ABSENT, A.MISSING, A.REJECTED, A.NON_FINAL):
        with pytest.raises(cp.CompletenessError):
            cp.SlotEvidence("20220302150000", account, N.NOT_NEAR_EMPTY)
        assert cp.SlotEvidence("20220302150000", account).near_empty is N.NOT_APPLICABLE
    for account in (A.ACCOUNTED, A.ACCOUNTED_DELAYED):
        with pytest.raises(cp.CompletenessError):
            cp.SlotEvidence("20220302150000", account)                                                # an accounted slot must say which
    assert cp.near_empty_of(None) is N.UNKNOWN and cp.near_empty_of(True) is N.NEAR_EMPTY and cp.near_empty_of(False) is N.NOT_NEAR_EMPTY


@pytest.mark.parametrize("slots,earlier,rule,source,usability", [
    (grid(), IntervalEarlier(), None, S.COMPLETE, U.USABLE),
    (grid(ev(A.MISSING)), IntervalEarlier(), None, S.INCOMPLETE, U.UNUSABLE_INCOMPLETE),                 # a missing batch is not a valid empty one
    (grid(ev(A.REJECTED)), IntervalEarlier(), True, S.INCOMPLETE, U.UNUSABLE_INCOMPLETE),                # no rule can rescue a rejected batch
    (grid(ev(A.NON_FINAL)), IntervalEarlier(), None, S.INCOMPLETE, U.UNUSABLE_INCOMPLETE),
    (grid(ev(A.FINAL_ABSENT)), IntervalEarlier(), None, S.FINAL_GAPS, U.UNDECIDED_POLICY),
    (grid(ev(A.FINAL_ABSENT)), IntervalEarlier(), True, S.FINAL_GAPS, U.USABLE_UNDER_COVERAGE_RULE),
    (grid(ev(A.FINAL_ABSENT)), IntervalEarlier(), False, S.FINAL_GAPS, U.UNUSABLE_BELOW_COVERAGE_RULE),
    (grid(ev(A.ACCOUNTED_DELAYED)), IntervalEarlier(), None, S.COMPLETE_WITH_DELAYED, U.UNDECIDED_POLICY),
    (grid(ev(A.ACCOUNTED, N.NEAR_EMPTY)), IntervalEarlier(), None, S.COMPLETE, U.UNDECIDED_POLICY),         # near-empty is not missing, and not full evidence
    (grid(ev(A.ACCOUNTED, N.UNKNOWN)), IntervalEarlier(), None, S.COMPLETE, U.UNDECIDED_POLICY),            # unknown is neither complete evidence nor empty
    (grid(), IntervalEarlier(unresolved=("20220301100000",)), True, S.INCOMPLETE, U.UNUSABLE_INCOMPLETE),   # unresolved earlier batch (C-min)
    (grid(), IntervalEarlier(not_examined=True), True, S.INCOMPLETE, U.UNUSABLE_INCOMPLETE),
    (grid(), IntervalEarlier(reconciled=1), None, S.COMPLETE_WITH_DELAYED, U.UNDECIDED_POLICY),
])
def test_the_shared_state_transitions(slots, earlier, rule, source, usability):
    a = cp.assess_interval(slots, earlier, coverage_rule_met=rule)
    assert (a.source, a.usability) == (source, usability)
    assert a.n_expected == len(slots) and a.reasons or a.source is S.COMPLETE


def test_explicit_near_empty_missing_and_unknown_stay_three_distinct_states():
    near = cp.assess_interval(grid(ev(A.ACCOUNTED, N.NEAR_EMPTY)))
    missing = cp.assess_interval(grid(ev(A.MISSING)))
    unknown = cp.assess_interval(grid(ev(A.ACCOUNTED, N.UNKNOWN)))
    assert (near.n_near_empty, near.n_near_empty_unknown, near.account_counts.get("missing", 0)) == (1, 0, 0)
    assert (missing.n_near_empty, missing.n_near_empty_unknown, missing.account_counts["missing"]) == (0, 0, 1)
    assert (unknown.n_near_empty, unknown.n_near_empty_unknown, unknown.account_counts.get("missing", 0)) == (0, 1, 0)
    assert len({near.source, missing.source}) == 2 and near.source is unknown.source                      # near-empty/unknown are complete-but-unvouched, missing is not


def test_theme_evidence_separates_records_verified_zero_and_unverified_empty():
    full = cp.assess_interval(grid())
    assert cp.theme_evidence(full, 3) == (T.HAS_RECORDS, ())
    assert cp.theme_evidence(full, 0) == (T.VERIFIED_ZERO_RECORDS, ())                                     # the only route to verified zero
    for slots, reason in ((grid(ev(A.MISSING)), "incomplete"), (grid(ev(A.FINAL_ABSENT)), "final_gaps"),
                          (grid(ev(A.ACCOUNTED_DELAYED)), "complete_with_delayed"), (grid(ev(A.ACCOUNTED, N.NEAR_EMPTY)), "near_empty_slots"),
                          (grid(ev(A.ACCOUNTED, N.UNKNOWN)), "near_empty_unknown")):
        e, reasons = cp.theme_evidence(cp.assess_interval(slots, coverage_rule_met=True), 0)
        assert e is T.UNVERIFIED_EMPTY and reason in reasons, reason                                      # even under an applied coverage rule
    e, reasons = cp.theme_evidence(full, 0, n_delayed_theme_rows=2)
    assert e is T.UNVERIFIED_EMPTY and "delayed_rows_exist" in reasons
    assert cp.theme_evidence(cp.assess_interval(grid(ev(A.MISSING))), 2)[0] is T.HAS_RECORDS               # records seen are still records


def test_result_availability_ordering_and_reasons():
    full = cp.assess_interval(grid())
    kw = dict(policy_blocked=False, scoring_performed=True)
    assert cp.result_availability(full, T.HAS_RECORDS, **kw)[0] is R.AVAILABLE
    assert cp.result_availability(full, T.HAS_RECORDS, test_only=True, **kw)[0] is R.AVAILABLE_TEST_ONLY
    assert cp.result_availability(full, T.HAS_RECORDS, policy_blocked=True, scoring_performed=False)[0] is R.BLOCKED_BY_POLICY   # policy wins
    assert cp.result_availability(full, T.HAS_RECORDS, policy_blocked=False, scoring_performed=False)[0] is R.SCORING_NOT_PERFORMED
    assert cp.result_availability(full, T.VERIFIED_ZERO_RECORDS, **kw)[0] is R.UNAVAILABLE                  # nothing to score is not a value
    assert cp.result_availability(full, T.UNVERIFIED_EMPTY, **kw)[0] is R.UNAVAILABLE
    gap = cp.assess_interval(grid(ev(A.FINAL_ABSENT)))                                                     # undecided policy
    assert cp.result_availability(gap, T.HAS_RECORDS, **kw)[0] is R.UNAVAILABLE
    assert cp.result_availability(cp.assess_interval(grid(ev(A.MISSING)), coverage_rule_met=True), T.HAS_RECORDS, **kw)[0] is R.UNAVAILABLE


def test_every_reachable_combination_satisfies_the_invariants():
    """Exhaustive: 6 slot accounts x 3 indicators (accounted only) x earlier cases x coverage rules x theme record counts x result inputs."""
    specials = [None] + [ev(A.MISSING), ev(A.REJECTED), ev(A.NON_FINAL), ev(A.FINAL_ABSENT)] + [ev(A.ACCOUNTED_DELAYED, n) for n in
                                                                                             (N.NOT_NEAR_EMPTY, N.NEAR_EMPTY, N.UNKNOWN)] \
        + [ev(A.ACCOUNTED, n) for n in (N.NEAR_EMPTY, N.UNKNOWN)]
    earliers = [IntervalEarlier(), IntervalEarlier(unresolved=("x",)), IntervalEarlier(not_examined=True), IntervalEarlier(reconciled=2)]
    checked = 0
    for spec_a, spec_b in itertools.product(specials, repeat=2):
        for early, rule, n_rec, delayed_rows in itertools.product(earliers, (None, True, False), (0, 1), (0, 1)):
            slots = grid(*[s for s in (spec_a, spec_b) if s is not None])
            a = cp.assess_interval(slots, early, coverage_rule_met=rule)
            e, _ = cp.theme_evidence(a, n_rec, delayed_rows)
            for blocked, scored, test_only in itertools.product((False, True), repeat=3):
                ra, _ = cp.result_availability(a, e, policy_blocked=blocked, scoring_performed=scored, test_only=test_only)
                assert cp.check_invariants(a, e, ra) == [], (a, e, ra)
                if blocked:
                    assert ra is R.BLOCKED_BY_POLICY
                if ra in (R.AVAILABLE, R.AVAILABLE_TEST_ONLY):
                    assert scored and not blocked and e is T.HAS_RECORDS and a.usability in (U.USABLE, U.USABLE_UNDER_COVERAGE_RULE)
            if e is T.VERIFIED_ZERO_RECORDS:                                                              # I1, stated independently of check_invariants
                assert a.source is S.COMPLETE and not a.n_near_empty and not a.n_near_empty_unknown and not a.earlier.unresolved \
                    and not a.earlier.not_examined and a.usability is U.USABLE
            if a.source is S.INCOMPLETE:                                                                  # I3
                assert a.usability is U.UNUSABLE_INCOMPLETE
            checked += 1
    assert checked > 3000


def test_check_invariants_detects_each_violation():
    full = cp.assess_interval(grid())
    gap = cp.assess_interval(grid(ev(A.MISSING)))
    near = cp.assess_interval(grid(ev(A.ACCOUNTED, N.UNKNOWN)))
    assert any("I1" in x for x in cp.check_invariants(gap, T.VERIFIED_ZERO_RECORDS))
    assert any("I1" in x for x in cp.check_invariants(near, T.VERIFIED_ZERO_RECORDS))
    assert any("I2" in x for x in cp.check_invariants(dataclasses.replace(near, usability=U.USABLE), T.UNVERIFIED_EMPTY))
    assert any("I3" in x for x in cp.check_invariants(dataclasses.replace(gap, usability=U.USABLE), T.UNVERIFIED_EMPTY))
    assert any("I4" in x for x in cp.check_invariants(near, T.HAS_RECORDS, R.AVAILABLE))
    assert any("I4" in x for x in cp.check_invariants(full, T.UNVERIFIED_EMPTY, R.AVAILABLE))
    assert cp.check_invariants(full, T.VERIFIED_ZERO_RECORDS, R.UNAVAILABLE) == []


def test_earlier_evidence_merges_window_wide_and_interval_specific_batches():
    e = cp.EarlierEvidence(True, ("20220301100000",), ((D2, ("20220301110000",)),), ((D2, 2),))
    mine, other = e.for_interval(D2), e.for_interval(date(2022, 3, 3))
    assert mine.unresolved == ("20220301100000", "20220301110000") and mine.reconciled == 2 and not mine.not_examined
    assert other.unresolved == ("20220301100000",) and other.reconciled == 0
    assert cp.EarlierEvidence.none_found().for_interval(D2) == IntervalEarlier()
    assert cp.EarlierEvidence.not_examined().for_interval(D2).not_examined is True


def test_no_state_carries_a_sentiment_value():
    for enum in (S, U, T, R, A, N):
        assert all(isinstance(m.value, str) for m in enum)
    fields = {f.name for f in dataclasses.fields(cp.IntervalAssessment)} | {f.name for f in dataclasses.fields(cp.SlotEvidence)}
    assert not {n for n in fields if "mean" in n or "p_pos" in n or "score" in n or "sentiment" in n}
