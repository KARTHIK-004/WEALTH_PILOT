"""Near-empty detector plumbing (S2.8E). Pure and offline: no database, file, network or clock.

The detector parameters are PROVISIONAL configuration (``PARAMS_STATUS``): previous 14 calendar days, at least 7 valid baseline
observations for the same slot of day, near-empty when ``rows_english_valid`` is below 10% of the baseline median. They are not
approved, and nothing here authorises scoring or features.

Two things are kept apart:

- the **observed flag** (``near_empty_flag`` in the manifest, set once at day commit by the collector): ``True``, ``False`` or
  ``None`` (NULL). It stays the flag the shared contract uses (``SlotEvidence``);
- the **derived assessment** (``assess_near_empty``): what this detector concludes from baseline observations the caller supplies.
  It never overrides the observed flag; ``compare_flags`` reports whether the two agree.

Rules the code enforces:

- the baseline uses only STRICTLY PRIOR observations of the same slot of day (batch time minus 1..``lookback_days`` days); an
  observation at or after the assessed batch is never read, so no future data can leak in and nothing is applied retroactively;
- only committed, valid observations count. An uncommitted, rejected or duplicated observation is counted, never used;
- the whole lookback must lie inside the evidence the caller declares (``baseline_declared_from``). Without that declaration, or with
  a lookback that starts before it, the result is ``UNKNOWN``: the repository's isolated sample has no contiguous baseline, and none
  is invented;
- too few valid observations, or an invalid observed count, is ``UNKNOWN``. ``UNKNOWN`` is never ``NOT_NEAR_EMPTY`` and is never
  evidence of completeness; an explicitly near-empty slot stays distinct from a missing one (a low count is not proof of missingness).
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from wealthpilot.data.gdelt.errors import GdeltToolError, InvalidTimestampError
from wealthpilot.data.gdelt.sentiment.completeness import NearEmpty
from wealthpilot.data.gdelt.timeutil import format_batch_stamp, parse_batch_stamp

PARAMS_STATUS = "PROVISIONAL_NOT_APPROVED"


class NearEmptyError(GdeltToolError):
    code = "sentiment_near_empty_error"


class BaselineReason(str, Enum):
    DECIDED = "decided"
    NO_BASELINE_DECLARED = "no_baseline_evidence_declared"
    LOOKBACK_NOT_AVAILABLE = "baseline_lookback_not_available"
    INSUFFICIENT_BASELINE = "insufficient_valid_baseline"
    BASELINE_NOT_COMMITTED = "baseline_not_committed"
    OBSERVED_COUNT_INVALID = "observed_count_invalid"
    NOT_APPLICABLE = "not_applicable"


class FlagComparison(str, Enum):
    AGREE = "agree"
    DISAGREE = "disagree"
    OBSERVED_ONLY = "observed_only"            # the flag is set, the detector cannot decide
    DERIVED_ONLY = "derived_only"              # the flag is NULL, the detector decides
    BOTH_UNKNOWN = "both_unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class NearEmptyParams:
    """PROVISIONAL defaults (``status``); the owner has not approved them."""

    lookback_days: int = 14
    min_baseline_obs: int = 7
    ratio: float = 0.10
    status: str = PARAMS_STATUS

    def __post_init__(self) -> None:
        if not (isinstance(self.lookback_days, int) and not isinstance(self.lookback_days, bool) and self.lookback_days >= 1):
            raise NearEmptyError("lookback_days must be an integer >= 1")
        if not (isinstance(self.min_baseline_obs, int) and not isinstance(self.min_baseline_obs, bool)
                and 1 <= self.min_baseline_obs <= self.lookback_days):
            raise NearEmptyError("min_baseline_obs must be an integer in [1, lookback_days]")
        if not (isinstance(self.ratio, float) and 0.0 < self.ratio < 1.0):
            raise NearEmptyError("ratio must be a float in (0, 1)")


@dataclass(frozen=True)
class BaselineObservation:
    """One manifest observation of ``rows_english_valid`` for a slot. ``committed`` False or ``valid`` False means it is never used."""

    batch_ts: str
    rows_english_valid: int | None
    committed: bool = True
    valid: bool = True


@dataclass(frozen=True)
class NearEmptyAssessment:
    state: NearEmpty                           # NEAR_EMPTY | NOT_NEAR_EMPTY | UNKNOWN (or NOT_APPLICABLE)
    reason: BaselineReason
    n_valid: int = 0
    n_uncommitted: int = 0
    n_invalid: int = 0                         # invalid or ambiguous (duplicate) observations
    n_absent: int = 0                          # lookback slots with no observation at all
    baseline_median: float | None = None
    threshold_rows: float | None = None
    params_status: str = PARAMS_STATUS


def _count(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def not_applicable() -> NearEmptyAssessment:
    return NearEmptyAssessment(NearEmpty.NOT_APPLICABLE, BaselineReason.NOT_APPLICABLE)


def assess_near_empty(batch_ts: str, rows_english_valid: int | None, observations: Sequence[BaselineObservation],
                      params: NearEmptyParams = NearEmptyParams(), *, baseline_declared_from: str | None = None) -> NearEmptyAssessment:
    """The detector's own conclusion for one accounted slot, from strictly prior committed observations only."""
    if not isinstance(params, NearEmptyParams):
        raise NearEmptyError("params must be NearEmptyParams")
    try:
        at = parse_batch_stamp(batch_ts)
        declared = None if baseline_declared_from is None else parse_batch_stamp(baseline_declared_from)
    except InvalidTimestampError as exc:
        raise NearEmptyError(str(exc)) from exc
    if not _count(rows_english_valid):
        return NearEmptyAssessment(NearEmpty.UNKNOWN, BaselineReason.OBSERVED_COUNT_INVALID)
    if declared is None:
        return NearEmptyAssessment(NearEmpty.UNKNOWN, BaselineReason.NO_BASELINE_DECLARED)
    if at - timedelta(days=params.lookback_days) < declared:
        return NearEmptyAssessment(NearEmpty.UNKNOWN, BaselineReason.LOOKBACK_NOT_AVAILABLE)
    by_stamp: dict[str, list[BaselineObservation]] = {}
    for o in observations:
        by_stamp.setdefault(o.batch_ts, []).append(o)
    values: list[int] = []
    uncommitted = invalid = absent = 0
    for k in range(1, params.lookback_days + 1):                         # strictly prior: k >= 1 day back, same slot of day
        rows = by_stamp.get(format_batch_stamp(at - timedelta(days=k)), [])
        if not rows:
            absent += 1
        elif len(rows) > 1:
            invalid += 1                                                  # ambiguous: never used
        elif not rows[0].valid:
            invalid += 1
        elif not rows[0].committed:
            uncommitted += 1                                              # not yet final: its count is not read at all
        elif not _count(rows[0].rows_english_valid):
            invalid += 1
        else:
            values.append(rows[0].rows_english_valid)                     # type: ignore[arg-type]
    base = dict(n_valid=len(values), n_uncommitted=uncommitted, n_invalid=invalid, n_absent=absent)
    if len(values) < params.min_baseline_obs:
        reason = (BaselineReason.BASELINE_NOT_COMMITTED if len(values) + uncommitted >= params.min_baseline_obs
                  else BaselineReason.INSUFFICIENT_BASELINE)
        return NearEmptyAssessment(NearEmpty.UNKNOWN, reason, **base)
    med = float(statistics.median(values))
    thr = params.ratio * med
    state = NearEmpty.NEAR_EMPTY if rows_english_valid < thr else NearEmpty.NOT_NEAR_EMPTY       # type: ignore[operator]
    return NearEmptyAssessment(state, BaselineReason.DECIDED, baseline_median=med, threshold_rows=thr, **base)


def compare_flags(observed: bool | None, derived: NearEmpty) -> FlagComparison:
    """Observed manifest flag versus the detector's derived state. Neither replaces the other; a NULL is never read as False."""
    if derived is NearEmpty.NOT_APPLICABLE:
        return FlagComparison.NOT_APPLICABLE
    if observed is None:
        return FlagComparison.BOTH_UNKNOWN if derived is NearEmpty.UNKNOWN else FlagComparison.DERIVED_ONLY
    if derived is NearEmpty.UNKNOWN:
        return FlagComparison.OBSERVED_ONLY
    return FlagComparison.AGREE if (derived is NearEmpty.NEAR_EMPTY) == observed else FlagComparison.DISAGREE


def derived_counts(states: Sequence[NearEmpty]) -> Mapping[str, int]:
    return {s.value: sum(1 for x in states if x is s) for s in NearEmpty}
