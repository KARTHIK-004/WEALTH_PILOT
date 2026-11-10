"""The local GDELT tone baseline: validation and provenance of GDELT's own tone columns. Pure, offline, deterministic; it loads no model and is separate from any title scorer.

**What these numbers are.** ``tone``, ``positive``, ``negative`` and ``polarity`` are GDELT's *document-level lexicon* values for the whole article. They are not sentiment of the headline, not a
probability, and not market direction (a rates or gold headline's "positive" tone can mean either for an asset). In the local sample every value is numeric, ``tone = positive − negative`` and
``polarity = positive + negative`` hold to about 1e-13 (the tolerance below is a validation tolerance, not a scientific parameter), and about a third of the rows are exactly zero everywhere, so **a zero
tone is not proof of neutrality**: it can mean no lexicon hit.

**Layers.**
1. *Raw + validation (implemented):* every observation keeps its raw strings and is exactly one of ``valid`` / ``missing`` (all four empty) / ``invalid`` (anything else wrong: partly empty, not
   numeric, not finite, out of range, or violating the two relations). Missing and invalid are never turned into zero or neutral.
2. *Counts (implemented):* per theme, how many records are valid / missing / invalid (every record counts: the primary counting unit), with how many valid ones are all-zero.
3. *Derived tone (owner-approved mapping, gated):* ``APPROVED_MAPPING`` (``gdelt_tone_mean_v0``) is approved strictly as a **labelled descriptive document-tone baseline**: the mean tone of the valid
   records, always reported with ``n_valid``, ``n_records`` and ``n_valid_all_zero``, plus the all-zero-excluded mean as a sensitivity variant. It is not title sentiment, not market direction and not a
   forecast target. The approval applies no other policy gate: ``derive_interval_tone`` still raises ``ToneMappingBlockedError`` for any unapproved mapping. It also refuses an incomplete interval and never yields a value
   from zero valid observations. It additionally requires every required policy to be applied (``policy``) and an interval that is ``USABLE`` or ``USABLE_UNDER_COVERAGE_RULE``: approving a
   mapping alone never unblocks a derived number while a policy gate or the interval's evidence is unresolved.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.completeness import IntervalAssessment, IntervalUsability
from wealthpilot.data.gdelt.sentiment.dayfile_adapter import CandidateRecord
from wealthpilot.data.gdelt.sentiment.policy import PolicyState, require_policies_applied
from wealthpilot.data.gdelt.sentiment.schema import THEMES

CONTRACT_VERSION = "gdelt_tone_raw_v1"
SCOPE = "document_level_lexicon_tone_not_title_sentiment_not_market_direction"
FIELDS = ("tone", "positive", "negative", "polarity")
RELATION_TOLERANCE = 1e-9                  # observed residual in the sample: <= 1e-13
SCORE_MAX = 100.0                          # positive / negative are percentage-like scores (structural bound; the sample maximum is far below it)


class ToneMappingBlockedError(GdeltToolError):
    code = "sentiment_tone_mapping_blocked"


class ToneBaselineError(GdeltToolError):
    code = "sentiment_tone_baseline_error"


@dataclass(frozen=True)
class ToneObservation:
    article_id: str
    batch_ts: str
    available_at_utc: datetime
    theme_flags: tuple[tuple[str, bool], ...]
    raw: tuple[str, str, str, str]
    status: str                            # valid | missing | invalid
    reasons: tuple[str, ...]
    values: tuple[float, float, float, float] | None     # (tone, positive, negative, polarity) only when valid
    contract_version: str = CONTRACT_VERSION
    scope: str = SCOPE

    @property
    def all_zero(self) -> bool:
        return self.values is not None and all(v == 0.0 for v in self.values)


def validate_raw(raw: Sequence[str]) -> tuple[str, tuple[str, ...], tuple[float, float, float, float] | None]:
    """Classify the four raw strings: ``(status, reasons, values)``."""
    if len(raw) != 4 or not all(isinstance(x, str) for x in raw):
        return "invalid", ("expected four raw strings",), None
    if all(x.strip() == "" for x in raw):
        return "missing", (), None
    empty = [n for n, x in zip(FIELDS, raw) if x.strip() == ""]
    if empty:
        return "invalid", (f"partly empty: {','.join(empty)}",), None
    vals: list[float] = []
    for name, x in zip(FIELDS, raw):
        try:
            v = float(x)
        except ValueError:
            return "invalid", (f"{name} is not numeric",), None
        if not math.isfinite(v):
            return "invalid", (f"{name} is not finite",), None
        vals.append(v)
    tone, pos, neg, pol = vals
    bad = []
    if not (0.0 <= pos <= SCORE_MAX and 0.0 <= neg <= SCORE_MAX):
        bad.append("positive/negative outside [0, 100]")
    if abs(tone - (pos - neg)) > RELATION_TOLERANCE:
        bad.append("tone != positive - negative")
    if abs(pol - (pos + neg)) > RELATION_TOLERANCE:
        bad.append("polarity != positive + negative")
    if bad:
        return "invalid", tuple(bad), None
    return "valid", (), (tone, pos, neg, pol)


def observe_tone(c: CandidateRecord) -> ToneObservation:
    status, reasons, values = validate_raw(c.tone_raw)
    return ToneObservation(c.article_id, c.batch_ts, c.available_at_utc, tuple(sorted(c.theme_flags.items())), tuple(c.tone_raw), status, reasons, values)


@dataclass(frozen=True)
class ToneCounts:
    theme: str
    n_records: int
    n_valid: int
    n_missing: int
    n_invalid: int
    n_valid_all_zero: int                  # valid and exactly zero everywhere: not evidence of neutrality
    valid_share: float | None              # n_valid / n_records; None when there are no records (never 0 or 1)


@dataclass(frozen=True)
class ToneIntervalSummary:
    origin_date: date
    counts: tuple[ToneCounts, ...]         # one per theme
    contract_version: str = CONTRACT_VERSION
    scope: str = SCOPE


def count_tone(observations: Sequence[ToneObservation], themes: Sequence[str] = THEMES) -> tuple[ToneCounts, ...]:
    out = []
    for t in themes:
        mine = [o for o in observations if dict(o.theme_flags).get(t)]
        n = len(mine)
        valid = [o for o in mine if o.status == "valid"]
        out.append(ToneCounts(t, n, len(valid), sum(o.status == "missing" for o in mine), sum(o.status == "invalid" for o in mine),
                              sum(o.all_zero for o in valid), len(valid) / n if n else None))
    return tuple(out)


@dataclass(frozen=True)
class ToneMapping:
    """A versioned contract for turning validated tone into one derived number per theme-interval. ``approved`` is the owner's decision, never inferred."""

    version: str
    aggregate: str                         # the only implemented aggregate: mean_tone_of_valid_records
    approved: bool
    status: str = "PROPOSED_NOT_APPROVED"


MAPPING_LABEL = "descriptive_document_tone_baseline"
# Owner decision: approved ONLY as a labelled descriptive document-tone baseline. Not title sentiment, not market direction, not a forecast target.
APPROVED_MAPPING = ToneMapping("gdelt_tone_mean_v0", "mean_tone_of_valid_records", approved=True, status="OWNER_APPROVED_DESCRIPTIVE_BASELINE")


@dataclass(frozen=True)
class ToneDerived:
    origin_date: date
    theme: str
    status: str                            # computed | no_valid_observations | unavailable_incomplete_interval | unavailable_policy_undecided
    mean_tone: float | None                # None unless computed; never 0 for missing data
    n_valid: int
    n_records: int
    mapping_version: str
    n_valid_all_zero: int = 0                                  # reported alongside every mean: exact zeros are not evidence of neutrality
    mean_tone_excluding_all_zero: float | None = None          # SENSITIVITY variant; None when no valid record is non-zero
    label: str = MAPPING_LABEL
    scope: str = SCOPE


def derive_interval_tone(observations: Sequence[ToneObservation], origin_date: date, theme: str, mapping: ToneMapping,
                         assessment: IntervalAssessment, *, policy: PolicyState) -> ToneDerived:
    if not mapping.approved:
        raise ToneMappingBlockedError(f"tone mapping {mapping.version!r} is {mapping.status}: the derived polarity output is blocked until the owner approves a mapping")
    require_policies_applied(policy)                    # raises PolicyBlockedError while any required policy is unapplied
    if mapping.aggregate != "mean_tone_of_valid_records":
        raise ToneBaselineError(f"aggregate {mapping.aggregate!r} is not implemented")
    if theme not in THEMES:
        raise ToneBaselineError(f"unknown theme {theme!r}")
    c = count_tone(observations, (theme,))[0]
    if assessment.usability is IntervalUsability.UNDECIDED_POLICY:
        return ToneDerived(origin_date, theme, "unavailable_policy_undecided", None, c.n_valid, c.n_records, mapping.version, c.n_valid_all_zero)
    if assessment.usability not in (IntervalUsability.USABLE, IntervalUsability.USABLE_UNDER_COVERAGE_RULE):
        return ToneDerived(origin_date, theme, "unavailable_incomplete_interval", None, c.n_valid, c.n_records, mapping.version, c.n_valid_all_zero)
    valid = [o for o in observations if dict(o.theme_flags).get(theme) and o.status == "valid"]
    if not valid:
        return ToneDerived(origin_date, theme, "no_valid_observations", None, 0, c.n_records, mapping.version, 0)
    mean = math.fsum(o.values[0] for o in valid) / len(valid)          # type: ignore[index]
    nonzero = [o for o in valid if not o.all_zero]
    sens = math.fsum(o.values[0] for o in nonzero) / len(nonzero) if nonzero else None          # type: ignore[index]
    return ToneDerived(origin_date, theme, "computed", mean, len(valid), c.n_records, mapping.version, c.n_valid_all_zero, sens)
