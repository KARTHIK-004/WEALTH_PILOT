"""Coverage and counts for a forecast interval, keeping missing distinct from zero.

This module produces *counts* only. It computes no sentiment. A count is a real zero only when the
interval is adequately covered; otherwise the value is ``None`` with a reason (CLAUDE.md section 12).
The coverage threshold is an input (0.75 is PROPOSED in B2-H, not approved).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

REASON_NO_SLOTS = "no_expected_slots"
REASON_BELOW_THRESHOLD = "gdelt_coverage_below_threshold"


@dataclass(frozen=True)
class SlotSummary:
    processed: bool              # committed, availability verified
    near_empty: bool | None      # None: no causal baseline yet
    series_rows: int | None      # member rows for the series; None if not processed


@dataclass(frozen=True)
class CountObservation:
    value: int | None
    coverage: float | None
    reason: str | None


def interval_count(
    slots: Sequence[SlotSummary], threshold: float, *, unknown_near_empty_is_covered: bool = False
) -> CountObservation:
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    if not slots:
        return CountObservation(None, None, REASON_NO_SLOTS)

    def covered(s: SlotSummary) -> bool:
        if not s.processed or s.series_rows is None:
            return False
        if s.near_empty is None:
            return unknown_near_empty_is_covered
        return not s.near_empty

    good = [s for s in slots if covered(s)]
    coverage = len(good) / len(slots)
    if coverage < threshold:
        return CountObservation(None, coverage, REASON_BELOW_THRESHOLD)
    return CountObservation(sum(s.series_rows or 0 for s in good), coverage, None)
