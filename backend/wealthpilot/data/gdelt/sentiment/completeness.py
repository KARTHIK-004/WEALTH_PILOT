"""One shared completeness vocabulary for the sentiment pipeline (S2.8D). Pure and offline; used by both the orchestrator and the aggregator.

Four distinct concepts, each an explicit state (never a boolean, never derived from loosely related flags):

1. **Source completeness** (``SourceCompleteness``): have the interval's expected source slots been accounted for?
2. **Interval usability** (``IntervalUsability``): does the interval meet the evidence and policy conditions?
3. **Per-theme record evidence** (``ThemeEvidence``): what is known about the records of one theme in the interval?
4. **Result availability** (``ResultAvailability``): is a downstream result available, unavailable or blocked?

Per-slot evidence (``SlotEvidence``) keeps apart: fully accounted, delayed, missing, rejected, non-final and final-absent slots, and,
separately, whether a processed slot is explicitly near-empty, not near-empty, or **unknown** (a NULL indicator: neither "not near-empty"
nor "near-empty", and never evidence of completeness). Earlier-nominal batches under policy C-min arrive as ``IntervalEarlier``.

Invariants (``check_invariants`` states them; the tests enforce them):

- I1 ``VERIFIED_ZERO_RECORDS`` only when the source is ``COMPLETE``, no slot is near-empty or unknown, nothing earlier is unresolved and
  the interval is ``USABLE``. A missing, rejected, non-final, absent, delayed or near-empty slot, or an unknown indicator, can never
  produce it.
- I2 ``USABLE`` only for a ``COMPLETE`` source with every near-empty indicator known to be false.
- I3 an ``INCOMPLETE`` source is always ``UNUSABLE_INCOMPLETE``.
- I4 a result is ``AVAILABLE`` / ``AVAILABLE_TEST_ONLY`` only if no policy blocks, scoring was performed, the interval is usable under a
  rule or fully, and the theme has records. ``BLOCKED_BY_POLICY`` takes precedence over every other reason.
- I5 missing or incomplete evidence is never turned into a neutral or zero sentiment value: those states carry no value at all.

No coverage threshold, near-empty rule or late-batch length is decided here. A caller may pass ``coverage_rule_met`` (a rule the owner
has applied); without it any interval short of full evidence is ``UNDECIDED_POLICY``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from wealthpilot.data.gdelt.errors import GdeltToolError


class CompletenessError(GdeltToolError):
    code = "sentiment_completeness_error"


class SlotAccount(str, Enum):
    ACCOUNTED = "accounted"                    # processed, reconciled, available by the interval's cutoff
    ACCOUNTED_DELAYED = "accounted_delayed"    # processed, reconciled, available only after the cutoff
    FINAL_ABSENT = "final_absent"              # final absent/failed/invalid: it can never carry records
    MISSING = "missing"                        # no manifest row / no slot information
    REJECTED = "rejected"                      # row rejected, or processed but not reconciled (counts, day file, ids, versions)
    NON_FINAL = "non_final"                    # not in a final state yet


class NearEmpty(str, Enum):
    NOT_NEAR_EMPTY = "not_near_empty"
    NEAR_EMPTY = "near_empty"
    UNKNOWN = "unknown"                        # a NULL indicator: no causal baseline
    NOT_APPLICABLE = "not_applicable"          # the slot is not accounted, so the indicator says nothing


class SourceCompleteness(str, Enum):
    COMPLETE = "complete"
    COMPLETE_WITH_DELAYED = "complete_with_delayed"
    FINAL_GAPS = "final_gaps"
    INCOMPLETE = "incomplete"


class IntervalUsability(str, Enum):
    USABLE = "usable"                                          # full evidence: COMPLETE and every indicator known false
    USABLE_UNDER_COVERAGE_RULE = "usable_under_coverage_rule"  # short of full evidence, accepted by a rule the caller says is applied
    UNDECIDED_POLICY = "undecided_policy"                      # short of full evidence and no applied rule decides it
    UNUSABLE_BELOW_COVERAGE_RULE = "unusable_below_coverage_rule"
    UNUSABLE_INCOMPLETE = "unusable_incomplete"


class ThemeEvidence(str, Enum):
    HAS_RECORDS = "has_records"
    VERIFIED_ZERO_RECORDS = "verified_zero_records"
    UNVERIFIED_EMPTY = "unverified_empty"
    NOT_EVALUATED = "not_evaluated"            # the interval status prevented counting records at all


class ResultAvailability(str, Enum):
    AVAILABLE = "available"
    AVAILABLE_TEST_ONLY = "available_test_only"      # produced by the test-only fake scorer: never a research result
    UNAVAILABLE = "unavailable"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    SCORING_NOT_PERFORMED = "scoring_not_performed"


@dataclass(frozen=True)
class SlotEvidence:
    batch_ts: str
    account: SlotAccount
    near_empty: NearEmpty = NearEmpty.NOT_APPLICABLE
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        accounted = self.account in (SlotAccount.ACCOUNTED, SlotAccount.ACCOUNTED_DELAYED)
        if accounted == (self.near_empty is NearEmpty.NOT_APPLICABLE):
            raise CompletenessError(f"{self.batch_ts}: the near-empty indicator applies to accounted slots only "
                                    f"(account {self.account.value}, indicator {self.near_empty.value})")


def near_empty_of(flag: bool | None) -> NearEmpty:
    """``True`` near-empty, ``False`` not, ``None`` unknown. Never the other way round."""
    return NearEmpty.UNKNOWN if flag is None else (NearEmpty.NEAR_EMPTY if flag else NearEmpty.NOT_NEAR_EMPTY)


@dataclass(frozen=True)
class IntervalEarlier:
    """What is known about earlier-nominal batches (policy C-min) for ONE interval."""

    unresolved: tuple[str, ...] = ()           # batches that may arrive in this interval and are not accounted for
    not_examined: bool = False                 # no lookback was declared: nothing was looked for
    reconciled: int = 0                        # earlier batches accounted for whose records entered this interval


@dataclass(frozen=True)
class EarlierEvidence:
    """Earlier-nominal evidence for a whole window, in a form both the orchestrator and the aggregator accept."""

    examined: bool
    unresolved_window: tuple[str, ...] = ()                        # batches whose receiving interval cannot be known: every interval
    unresolved: tuple[tuple[date, tuple[str, ...]], ...] = ()      # (receiving interval, batches)
    reconciled: tuple[tuple[date, int], ...] = ()

    @classmethod
    def none_found(cls) -> "EarlierEvidence":
        """The lookback was examined and no earlier batch is in play (the caller asserts this)."""
        return cls(True)

    @classmethod
    def not_examined(cls) -> "EarlierEvidence":
        return cls(False)

    def for_interval(self, d: date) -> IntervalEarlier:
        mine = sorted({b for k, bs in self.unresolved if k == d for b in bs} | set(self.unresolved_window))
        return IntervalEarlier(tuple(mine), not self.examined, sum(n for k, n in self.reconciled if k == d))


@dataclass(frozen=True)
class IntervalAssessment:
    source: SourceCompleteness
    usability: IntervalUsability
    n_expected: int
    account_counts: Mapping[str, int]
    n_near_empty: int
    n_near_empty_unknown: int
    n_delayed: int
    earlier: IntervalEarlier
    reasons: tuple[str, ...]


def incomplete_assessment(reason: str, *, n_expected: int = 0, earlier: IntervalEarlier = IntervalEarlier()) -> IntervalAssessment:
    """An interval whose slots cannot even be listed (no slot information, a broken grid): incomplete by definition."""
    return IntervalAssessment(SourceCompleteness.INCOMPLETE, IntervalUsability.UNUSABLE_INCOMPLETE, n_expected, {}, 0, 0, 0, earlier, (reason,))


def assess_interval(slots: Sequence[SlotEvidence], earlier: IntervalEarlier = IntervalEarlier(), *,
                    coverage_rule_met: bool | None = None) -> IntervalAssessment:
    """The shared state transition from per-slot evidence to source completeness and usability."""
    counts = Counter(s.account for s in slots)
    near = sum(1 for s in slots if s.near_empty is NearEmpty.NEAR_EMPTY)
    unknown = sum(1 for s in slots if s.near_empty is NearEmpty.UNKNOWN)
    reasons: list[str] = []
    problems = [a for a in (SlotAccount.MISSING, SlotAccount.REJECTED, SlotAccount.NON_FINAL) if counts[a]]
    if problems or earlier.unresolved or earlier.not_examined:
        source = SourceCompleteness.INCOMPLETE
        reasons += [f"{counts[a]} slot(s) {a.value}" for a in problems]
        if earlier.not_examined:
            reasons.append("earlier batches not examined (no lookback evidence)")
        if earlier.unresolved:
            reasons.append(f"{len(earlier.unresolved)} unresolved earlier/late batch(es): {', '.join(earlier.unresolved[:3])}")
    elif counts[SlotAccount.FINAL_ABSENT]:
        source = SourceCompleteness.FINAL_GAPS
        reasons.append(f"{counts[SlotAccount.FINAL_ABSENT]} source batch(es) final-absent")
    elif counts[SlotAccount.ACCOUNTED_DELAYED] or earlier.reconciled:
        source = SourceCompleteness.COMPLETE_WITH_DELAYED
        if counts[SlotAccount.ACCOUNTED_DELAYED]:
            reasons.append(f"{counts[SlotAccount.ACCOUNTED_DELAYED]} batch(es) available only after the cutoff")
        if earlier.reconciled:
            reasons.append(f"{earlier.reconciled} earlier-nominal batch(es) arrived late inside this interval")
    else:
        source = SourceCompleteness.COMPLETE
    if near:
        reasons.append(f"{near} slot(s) explicitly near-empty")
    if unknown:
        reasons.append(f"{unknown} slot(s) with an unknown (NULL) near-empty indicator")
    if source is SourceCompleteness.INCOMPLETE:
        usability = IntervalUsability.UNUSABLE_INCOMPLETE
    elif source is SourceCompleteness.COMPLETE and not near and not unknown:
        usability = IntervalUsability.USABLE
    elif coverage_rule_met is True:
        usability = IntervalUsability.USABLE_UNDER_COVERAGE_RULE
    elif coverage_rule_met is False:
        usability = IntervalUsability.UNUSABLE_BELOW_COVERAGE_RULE
    else:
        usability = IntervalUsability.UNDECIDED_POLICY
    return IntervalAssessment(source, usability, len(slots), {a.value: counts[a] for a in SlotAccount if counts[a]}, near, unknown,
                              counts[SlotAccount.ACCOUNTED_DELAYED], earlier, tuple(reasons))


def theme_evidence(a: IntervalAssessment, n_records: int, n_delayed_theme_rows: int = 0) -> tuple[ThemeEvidence, tuple[str, ...]]:
    """What is known about one theme's records. ``n_records`` counts every trusted record of the theme (whatever its text or duplicate
    status): the existence of a record is evidence that the theme is not empty."""
    if n_records > 0:
        return ThemeEvidence.HAS_RECORDS, ()
    if a.usability is IntervalUsability.USABLE and not n_delayed_theme_rows:
        return ThemeEvidence.VERIFIED_ZERO_RECORDS, ()
    reasons: list[str] = []
    if a.source is not SourceCompleteness.COMPLETE:
        reasons.append(a.source.value)
    if a.n_near_empty:
        reasons.append("near_empty_slots")
    if a.n_near_empty_unknown:
        reasons.append("near_empty_unknown")
    if n_delayed_theme_rows:
        reasons.append("delayed_rows_exist")
    return ThemeEvidence.UNVERIFIED_EMPTY, tuple(reasons) or ("interval_not_usable",)


_USABLE = (IntervalUsability.USABLE, IntervalUsability.USABLE_UNDER_COVERAGE_RULE)


def result_availability(a: IntervalAssessment, ev: ThemeEvidence, *, policy_blocked: bool, scoring_performed: bool,
                        test_only: bool = False) -> tuple[ResultAvailability, str]:
    if policy_blocked:
        return ResultAvailability.BLOCKED_BY_POLICY, "a required research policy is unresolved"
    if not scoring_performed:
        return ResultAvailability.SCORING_NOT_PERFORMED, "no scoring was performed"
    if a.usability not in _USABLE:
        return ResultAvailability.UNAVAILABLE, f"interval is {a.usability.value}"
    if ev is not ThemeEvidence.HAS_RECORDS:
        return ResultAvailability.UNAVAILABLE, f"theme evidence is {ev.value}"
    return (ResultAvailability.AVAILABLE_TEST_ONLY, "produced by the test-only scorer") if test_only else (ResultAvailability.AVAILABLE, "")


def check_invariants(a: IntervalAssessment, ev: ThemeEvidence, ra: ResultAvailability | None = None) -> list[str]:
    """Every violated invariant I1-I4 (empty when the combination is allowed)."""
    out: list[str] = []
    clean = a.source is SourceCompleteness.COMPLETE and not a.n_near_empty and not a.n_near_empty_unknown and not a.earlier.unresolved \
        and not a.earlier.not_examined
    if ev is ThemeEvidence.VERIFIED_ZERO_RECORDS and not (clean and a.usability is IntervalUsability.USABLE):
        out.append("I1: verified zero records without full, usable evidence")
    if a.usability is IntervalUsability.USABLE and not clean:
        out.append("I2: usable without a complete source and known indicators")
    if a.source is SourceCompleteness.INCOMPLETE and a.usability is not IntervalUsability.UNUSABLE_INCOMPLETE:
        out.append("I3: an incomplete source that is not unusable")
    if ra in (ResultAvailability.AVAILABLE, ResultAvailability.AVAILABLE_TEST_ONLY) and (a.usability not in _USABLE or ev is not ThemeEvidence.HAS_RECORDS):
        out.append("I4: an available result without usable evidence and records")
    return out
