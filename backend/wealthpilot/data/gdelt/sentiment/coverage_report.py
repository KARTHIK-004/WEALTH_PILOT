"""Coverage accounting over the shared completeness contract (S2.8E). Pure and offline.

Three kinds of coverage are never merged: **source coverage** (this module: expected nominal slots), **record availability** (which
records exist, ``ThemeEvidence``) and **scoring coverage** (not computed here; its policy is unresolved).

Definitions
-----------
- The **denominator** is the expected nominal source slots of the interval, i.e. the full grid. It is never shrunk: a slot that is
  excluded from the numerator still counts in the denominator, and a late arrival of an EARLIER nominal batch adds nothing to it.
- A slot is **covered** only if it is accounted (processed, reconciled, valid) AND available by the applicable cutoff AND its observed
  near-empty flag is known to be false. Every other slot is excluded, for exactly one reason (``EXCLUSION_REASONS``): ``missing``,
  ``rejected``, ``non_final``, ``final_absent``, ``delayed_after_cutoff``, ``near_empty`` (explicit) or ``near_empty_unknown`` (NULL).
  Nominal-slot availability is judged by verified availability and the existing cutoff rules upstream (``SlotAccount``).
- ``max_consecutive_missing_run`` is the longest run, in grid order, of slots with no valid accounted evidence (missing, rejected,
  non-final or final-absent); ``max_consecutive_uncovered_run`` also counts delayed and near-empty slots.

The thresholds (0.75 primary; 0.50 and 0.90 sensitivity) are PROVISIONAL configuration. ``meets`` is a report, not a decision: a
ratio never turns an unverified empty theme into verified no-news (``theme_evidence`` ignores coverage), and
``coverage_rule_decision`` yields a verdict for the shared usability transition only while the policy status says the rule is applied.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.completeness import NearEmpty, SlotAccount, SlotEvidence

THRESHOLDS_STATUS = "PROVISIONAL_NOT_APPROVED"
EXCLUSION_REASONS = ("missing", "rejected", "non_final", "final_absent", "delayed_after_cutoff", "near_empty", "near_empty_unknown")
_NO_EVIDENCE = (SlotAccount.MISSING, SlotAccount.REJECTED, SlotAccount.NON_FINAL, SlotAccount.FINAL_ABSENT)


class CoverageReportError(GdeltToolError):
    code = "sentiment_coverage_report_error"


@dataclass(frozen=True)
class CoverageThresholds:
    """Explicit, PROVISIONAL threshold configuration. Not approved; it authorises nothing."""

    primary: float = 0.75
    sensitivity: tuple[float, ...] = (0.50, 0.90)
    status: str = THRESHOLDS_STATUS

    def __post_init__(self) -> None:
        values = (self.primary, *self.sensitivity)
        if not all(isinstance(v, float) and 0.0 < v <= 1.0 for v in values):
            raise CoverageReportError("every coverage threshold must be a float in (0, 1]")
        if len(set(values)) != len(values):
            raise CoverageReportError("coverage thresholds must be distinct")


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    label: str                                  # primary | sensitivity
    meets: bool                                 # ratio >= threshold: a report only
    status: str = THRESHOLDS_STATUS


@dataclass(frozen=True)
class CoverageBlock:
    n_expected: int                             # the denominator: the full expected grid
    n_covered: int                              # the numerator
    ratio: float | None                         # None only when there is no expected slot
    excluded_by_reason: Mapping[str, int] = field(default_factory=dict)       # every reason present, zeros included
    max_consecutive_missing_run: int = 0
    max_consecutive_uncovered_run: int = 0
    thresholds: tuple[ThresholdResult, ...] = ()
    kind: str = "source_slot_coverage"          # never record availability, never scoring coverage

    @property
    def n_excluded(self) -> int:
        return sum(self.excluded_by_reason.values())


def exclusion_reason(s: SlotEvidence) -> str | None:
    """``None`` for a covered slot, otherwise the single reason it is excluded."""
    if s.account is SlotAccount.ACCOUNTED:
        return {NearEmpty.NOT_NEAR_EMPTY: None, NearEmpty.NEAR_EMPTY: "near_empty", NearEmpty.UNKNOWN: "near_empty_unknown"}[s.near_empty]
    if s.account is SlotAccount.ACCOUNTED_DELAYED:
        return "delayed_after_cutoff"
    return s.account.value


def _longest(flags: Sequence[bool]) -> int:
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best


def coverage_block(slots: Sequence[SlotEvidence], thresholds: CoverageThresholds = CoverageThresholds(),
                   *, expected_n: int | None = None) -> CoverageBlock:
    """Numerator, denominator, ratio, exclusions by reason and longest runs, for slots given in any order (sorted by ``batch_ts``)."""
    if not isinstance(thresholds, CoverageThresholds):
        raise CoverageReportError("thresholds must be CoverageThresholds")
    ordered = sorted(slots, key=lambda s: s.batch_ts)
    if len({s.batch_ts for s in ordered}) != len(ordered):
        raise CoverageReportError("duplicate slot in the interval: the denominator would be ambiguous")
    if expected_n is not None and expected_n != len(ordered):
        raise CoverageReportError(f"the interval has {len(ordered)} slot(s) but {expected_n} are expected: the denominator is never shrunk")
    reasons = [exclusion_reason(s) for s in ordered]
    excluded = {r: sum(1 for x in reasons if x == r) for r in EXCLUSION_REASONS}
    n, covered = len(ordered), sum(1 for x in reasons if x is None)
    ratio = None if n == 0 else covered / n
    results: tuple[ThresholdResult, ...] = ()
    if ratio is not None:
        results = (ThresholdResult(thresholds.primary, "primary", ratio >= thresholds.primary),
                   *(ThresholdResult(t, "sensitivity", ratio >= t) for t in sorted(thresholds.sensitivity)))
    return CoverageBlock(n, covered, ratio, excluded, _longest([s.account in _NO_EVIDENCE for s in ordered]),
                         _longest([r is not None for r in reasons]), results)


def coverage_rule_decision(block: CoverageBlock, thresholds: CoverageThresholds, policy_status: str | None) -> bool | None:
    """The verdict for ``assess_interval(coverage_rule_met=...)``. ``None`` (undecided) unless the policy status is ``APPLIED_APPROVED``: a provisional threshold is INFORMATIONAL
    (owner decision, 2026-10-20): it is reported in the block but never decides usability, so unknown or near-empty evidence is never promoted to usable by a ratio."""
    if policy_status != "APPLIED_APPROVED" or block.ratio is None:
        return None
    return block.ratio >= thresholds.primary
