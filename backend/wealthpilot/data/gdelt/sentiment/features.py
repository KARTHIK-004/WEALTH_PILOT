"""Daily, theme-specific sentiment features from scored articles (S2, corrected in S2.2 and S2.3). Pure and offline; no model.

A feature row is the aggregate of the eligible article **records** of one theme in one forecast interval. The interval of origin
day ``d`` is ``(cutoff(previous trading day), cutoff(d)]`` using the existing ``session_calendar.cutoff_utc`` (16:00 New York,
13:00 on an early close the caller supplies), and an article belongs to it only by its **verified availability time**
(``availability.compute_availability``): never its page publication time. An article available after ``cutoff(d)`` cannot touch
the row for ``d``; one that is available exactly at the cutoff is inside it. The interval of an availability time is found with
the existing ``session_calendar.origin_for``, for slots and for articles alike (one rule, one implementation).

**Inputs are validated, never trusted.**

- ``articles``, ``trading_days`` and ``themes`` must be a ``list`` or ``tuple`` (a generator would be consumed by validation and
  then read as empty; a ``set`` has no order).
- The trading calendar must be plain ``date`` values, weekdays, not in the explicit ``market_holidays`` input, and must contain
  every expected trading day between its first and last entry. No holiday list is built in: it is an unapproved input.
- Each interval's source slots (``slots.SlotAccounting``, one per batch) must be exactly the 15-minute **nominal** batch grid of
  the interval: no missing, duplicate or unexpected slot (``slot_grid_mismatch``).

**Source accounting (S2.3).** A batch is accounted for in the interval of its *nominal* slot, by what the pipeline reports
(``slots.py`` documents each manifest count and contract C1). A slot in a non-final state makes its interval
``incomplete_source_accounting``. Every article record must reconcile with its batch (counts per batch and per theme, one
availability per batch); a mismatch is ``slot_article_mismatch`` with the batch and both numbers, never a repair.

**Delayed batches (the interval clock).** A batch is *covered* for its nominal interval only if it was available by that
interval's cutoff. A processed batch whose verified availability is later is **delayed**: it is not covered for its nominal
interval (point in time: it did not exist yet), it is counted there (``n_slots_delayed``, ``n_delayed_theme_rows``), and its
articles enter the interval that contains their availability time (``n_late_carried_in``). Every article that enters an
interval must belong to a reconciled batch, so a late article is never unaccounted-for. A delayed batch that carries rows of the
theme makes a day with no other news ``no_news = None`` (absence of news is not verified), never ``True``.

**Missing data is never neutral and never zero.** Every row has a ``coverage_status``: ``ok`` (at least one expected batch was available by the cutoff, and the accounting reconciles) or one of
``missing_source_batches``, ``no_expected_slots``, ``slot_grid_mismatch``, ``incomplete_source_accounting``, ``slot_article_mismatch``: every feature is ``None`` with a ``reason``.
**The configured coverage threshold is INFORMATIONAL** (owner decision, 2026-10-20, policy ``source_coverage_threshold`` applied provisionally and informationally): the row carries ``coverage``,
``coverage_threshold`` and ``coverage_threshold_met``, and a ratio below the threshold neither suppresses features nor makes the interval unusable. Every evidence-integrity rule still applies, independently
of the ratio: gaps (absent, delayed, near-empty, unknown-indicator slots) leave the interval ``undecided_policy``, so the result is not ``available`` and an empty theme is ``unverified_empty``, never no-news or neutral. With status ``ok`` and no candidate article the row is a **verified no-news day**
(``no_news = True``), unless delayed or duplicate-only evidence says otherwise (below).

``near_empty`` slots are **not counted as covered** (the existing ``coverage.interval_count`` semantics, unchanged and
unapproved); their number is exposed (``n_slots_near_empty``). ``coverage`` is source-slot coverage; ``scoring_coverage`` is
``n_scored / n_eligible``; there is no minimum scoring threshold.

**Uniqueness is not claimed.** ``n_eligible`` counts article records; ``n_distinct_stories`` counts distinct ``story_id`` values.
``dedup_status`` is ``unresolved_story_ids``, ``duplicates_only_unresolved`` (``no_news = None``), ``versions_kept_proposed``,
``duplicates_removed_proposed`` or ``none_found``. Duplicate statuses are trusted from the labels.

Rules in use are PROPOSED, not approved, so they are explicit inputs and not defaults, and every row carries
``rules_status = PROPOSED_NOT_APPROVED``: the deduplication policy, the coverage threshold (0.75 proposed), the early-close and
holiday calendars, the treatment of near-empty slots. Theme-specific calendars are BLOCKED on an approved forecast target.

**Shared completeness vocabulary (S2.8D).** Every row also carries the four distinct states of ``completeness.py``, produced by the SAME
transitions the orchestrator uses (``assess_interval``, ``theme_evidence``, ``result_availability``): ``source_completeness``,
``interval_usability``, ``theme_evidence`` (+ reasons) and ``result_availability``. ``no_news`` is true ONLY for
``verified_zero_records``, which needs a ``complete`` source, every near-empty indicator known false and nothing earlier unresolved: a
missing, rejected, non-final, absent or delayed batch, an explicitly near-empty slot or an unknown (NULL) indicator can never give it.
``earlier`` (``EarlierEvidence``) is required: unresolved or unexamined earlier-nominal batches (policy C-min) make the interval
incomplete. The provisional coverage threshold still decides whether features are computed (``coverage_status``) but never whether
zero is verified. A scoring result is ``available_test_only`` for the test-only scorer, ``scoring_not_performed`` without values.

Nothing here is connected to a forecasting model, the optimizer or a recommendation.
"""

from __future__ import annotations

import dataclasses
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from wealthpilot.data.gdelt.coverage import SlotSummary, interval_count
from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment import schema
from wealthpilot.data.gdelt.sentiment.completeness import (
    EarlierEvidence, IntervalAssessment, IntervalEarlier, SlotAccount, SlotEvidence, ThemeEvidence, assess_interval,
    incomplete_assessment, near_empty_of, result_availability, theme_evidence,
)
from wealthpilot.data.gdelt.sentiment.coverage_report import CoverageBlock, CoverageThresholds, coverage_block
from wealthpilot.data.gdelt.sentiment.policy import PolicyState, require_policies_applied
from wealthpilot.data.gdelt.sentiment.schema import ArticleRecord
from wealthpilot.data.gdelt.sentiment.slots import INCOMPLETE_STATES, SlotAccounting, reconcile_slot
from wealthpilot.data.gdelt.session_calendar import cutoff_utc, origin_for
from wealthpilot.data.gdelt.timeutil import SLOT, format_batch_stamp, require_utc, slot_grid

FEATURE_SCHEMA_VERSION = "s2_daily_v4"
RULES_STATUS = "PROPOSED_NOT_APPROVED"
PROPOSED_COVERAGE_THRESHOLD = 0.75                 # B2-H, PROPOSED
UPDATE_HANDLING = ("keep_all_versions",)           # the only handling implemented
_SHA = re.compile(r"^[0-9a-f]{64}$")
_MAX_DETAILS = 3


class SentimentFeatureError(GdeltToolError):
    code = "sentiment_feature_error"


@dataclass(frozen=True)
class DedupPolicy:
    """Which dedup statuses count as duplicates. ``UPDATE`` is not a duplicate: it is kept as a new version (existing policy)."""

    duplicate_statuses: frozenset[str]
    update_handling: str = "keep_all_versions"
    status: str = "PROPOSED_NOT_APPROVED"


PROPOSED_DEDUP_POLICY = DedupPolicy(frozenset({"DUP_SAME_BATCH", "SYNDICATED_SAME_BATCH", "REOBSERVATION", "SYNDICATED"}))
# OD-11c (owner decision): the PRIMARY counting unit is every eligible record, repeats included. No record is linked into a story (OD-11a) and nothing is removed as a duplicate. The status
# stays provisional. ``PROPOSED_DEDUP_POLICY`` above is the sensitivity comparison. Neither applies the ``deduplication_and_story_updates`` policy.
PRIMARY_DEDUP_POLICY = DedupPolicy(frozenset(), status="PROVISIONAL_OWNER_SELECTED")
PRIMARY_UNIT, SENSITIVITY_UNIT = "every_eligible_record", "proposed_dedup_policy"


@dataclass(frozen=True)
class SentimentConfig:
    """Every rule that is not approved is an explicit input. There are no defaults to forget."""

    coverage_threshold: float
    early_closes: frozenset[date]
    market_holidays: frozenset[date]
    dedup: DedupPolicy
    expected_model_id: str
    expected_model_revision: str
    expected_scorer_code_sha256: str
    policy: PolicyState                    # the policy snapshot this run is made under; unresolved required policies block (S2.8B)
    allow_test_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.policy, PolicyState):
            raise SentimentFeatureError("policy must be a PolicyState (a snapshot; a plain mapping could change after the check)")
        if not (isinstance(self.coverage_threshold, float) and 0.0 < self.coverage_threshold <= 1.0):
            raise SentimentFeatureError("coverage_threshold must be a float in (0, 1]")
        check_calendar_inputs(self.early_closes, self.market_holidays)
        if not isinstance(self.dedup, DedupPolicy):
            raise SentimentFeatureError("dedup must be a DedupPolicy")
        if self.dedup.update_handling not in UPDATE_HANDLING:
            raise SentimentFeatureError(f"update handling {self.dedup.update_handling!r} is not implemented; only "
                                        f"{UPDATE_HANDLING} (anything else is an unapproved rule)")
        unknown = set(self.dedup.duplicate_statuses) - set(schema.DUP_STATUSES)
        if unknown or "ORIGINAL" in self.dedup.duplicate_statuses or "UPDATE" in self.dedup.duplicate_statuses:
            raise SentimentFeatureError("duplicate_statuses must be dedup statuses other than ORIGINAL and UPDATE")
        for name in ("expected_model_id", "expected_model_revision"):
            if not (isinstance(getattr(self, name), str) and getattr(self, name).strip()):
                raise SentimentFeatureError(f"{name} is required")
        if not (isinstance(self.expected_scorer_code_sha256, str) and _SHA.match(self.expected_scorer_code_sha256)):
            raise SentimentFeatureError("expected_scorer_code_sha256 must be a SHA-256")
        if not isinstance(self.allow_test_only, bool):
            raise SentimentFeatureError("allow_test_only must be a bool")
        if self.allow_test_only != (self.expected_model_id == schema.TEST_ONLY_MODEL_ID):
            raise SentimentFeatureError("the test-only fake scorer is allowed if and only if it is the expected model: "
                                        "a production config can never accept test-only records, and a test config can "
                                        "never mix them with a real model")


@dataclass(frozen=True)
class DailyFeatures:
    origin_date: date
    theme: str
    n_eligible: int | None                 # eligible article RECORDS (not established-unique stories)
    n_scored: int | None
    n_duplicates_removed: int | None
    n_invalid_text: int | None
    n_update_versions: int | None
    n_distinct_stories: int | None
    n_late_carried_in: int | None          # records of this theme from batches whose nominal slot is in an EARLIER interval
    coverage: float | None                 # SOURCE-SLOT coverage, as of the cutoff
    coverage_status: str
    n_slots_expected: int | None
    n_slots_covered: int | None
    n_slots_near_empty: int | None
    n_slots_delayed: int | None            # this interval's slots that became available only after its cutoff
    n_delayed_theme_rows: int | None       # series rows of this theme in those delayed slots (not available at the cutoff)
    scoring_coverage: float | None         # n_scored / n_eligible
    scoring_status: str
    dedup_status: str
    mean_p_pos: float | None
    mean_p_neg: float | None
    mean_net: float | None
    disp_net: float | None
    no_news: bool | None                   # True ONLY for ThemeEvidence.VERIFIED_ZERO_RECORDS; None whenever that is not established
    feature_cutoff_utc: datetime
    model_revision: str
    schema_version: str
    reason: str | None
    # the shared completeness vocabulary (completeness.py): four distinct concepts, as explicit states
    source_completeness: str               # SourceCompleteness
    interval_usability: str                # IntervalUsability
    theme_evidence: str                    # ThemeEvidence
    theme_evidence_reasons: str | None     # why a theme is unverified-empty
    result_availability: str               # ResultAvailability
    result_reason: str | None
    n_slots_near_empty_unknown: int | None     # processed slots whose near-empty indicator is NULL (unknown)
    rules_status: str = RULES_STATUS
    # REPORT-ONLY (S2.8I, OD-10 part 1): the shared ``coverage_report.CoverageBlock`` of this interval, computed from the same per-slot evidence.
    # No field, status, verdict or ``no_news`` reads it, and it uses the shared PROVISIONAL threshold defaults, not ``coverage_threshold``.
    # Since S2.8J (OD-10 part 2) both exclude a processed slot that fails reconciliation, so ``n_covered`` here equals ``n_slots_covered``;
    # they can still differ elsewhere (the block reports its own provisional thresholds). ``None`` when the interval's slots cannot be
    # listed (``no_expected_slots``, ``slot_grid_mismatch``).
    coverage_report: CoverageBlock | None = None
    # The configured (provisional, informational) coverage threshold and whether the measured coverage meets it. Never a gate: see the module docstring.
    coverage_threshold: float | None = None
    coverage_threshold_met: bool | None = None            # None when coverage could not be measured


@dataclass(frozen=True)
class _Day:
    status: str
    coverage: float | None
    reason: str | None
    n_expected: int | None = None
    n_covered: int | None = None
    n_near_empty: int | None = None
    n_delayed: int | None = None
    delayed_rows: Mapping[str, int] | None = None
    assessment: IntervalAssessment | None = None
    coverage_block: CoverageBlock | None = None            # report-only (S2.8I): never read by a gate
    threshold_met: bool | None = None                      # informational: measured coverage >= the configured threshold


def _materialize(value: Any, name: str) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    raise SentimentFeatureError(f"{name} must be a list or tuple, not {type(value).__name__}: a generator would be consumed by "
                                "validation and then read as empty (every day 'no news'), and a set has no order")


def check_calendar_inputs(early_closes: Any, market_holidays: Any) -> None:
    """The early-close and holiday inputs must be frozensets of plain weekday dates that do not overlap (unapproved inputs)."""
    for name, value in (("early_closes", early_closes), ("market_holidays", market_holidays)):
        if not isinstance(value, frozenset) or any(type(d) is not date for d in value):
            raise SentimentFeatureError(f"{name} must be a frozenset of plain dates")
    if any(d.weekday() >= 5 for d in early_closes):
        raise SentimentFeatureError("early_closes must be weekdays")
    if early_closes & market_holidays:
        raise SentimentFeatureError("a date cannot be both an early close and a market holiday")


def interval_cutoffs(days: Sequence[date], early_closes: frozenset[date]) -> dict[date, datetime]:
    """Cutoff of every calendar day, from the existing ``session_calendar.cutoff_utc``."""
    return {d: cutoff_utc(d, early_closes) for d in days}


def nominal_grids(days: Sequence[date], cutoffs: Mapping[date, datetime]) -> dict[date, list[str]]:
    """Per origin day, the nominal 15-minute batch stamps of ``(cutoff(previous), cutoff(d)]`` (the interval's expected slots)."""
    return {days[i]: slot_grid(format_batch_stamp(cutoffs[days[i - 1]]), format_batch_stamp(cutoffs[days[i]] - SLOT))
            for i in range(1, len(days))}


def interval_locator(days: Sequence[date], early_closes: frozenset[date]) -> Callable[[datetime], date | None]:
    """Maps a verified availability time to its origin day with the existing ``origin_for``; the first day is a lower bound only."""
    day_list, memo = list(days), {}

    def interval_of(at: datetime) -> date | None:
        at = require_utc(at)
        if at not in memo:
            origin = origin_for(at, day_list, early_closes)
            memo[at] = None if origin is None or origin == day_list[0] else origin
        return memo[at]

    return interval_of


def check_calendar(days: tuple[Any, ...], market_holidays: frozenset[date]) -> None:
    if len(days) < 2:
        raise SentimentFeatureError("trading_days must contain at least two days")
    if any(type(d) is not date for d in days):
        raise SentimentFeatureError("trading_days must be plain date values (a datetime is refused)")
    if list(days) != sorted(set(days)):
        raise SentimentFeatureError("trading_days must be sorted and unique")
    for d in days:
        if d.weekday() >= 5:
            raise SentimentFeatureError(f"trading_days contains a weekend date {d}")
        if d in market_holidays:
            raise SentimentFeatureError(f"trading_days contains the market holiday {d}")
    expected, d = [], days[0]
    while d <= days[-1]:
        if d.weekday() < 5 and d not in market_holidays:
            expected.append(d)
        d += timedelta(days=1)
    if expected != list(days):
        missing = sorted(set(expected) - set(days))
        raise SentimentFeatureError(f"trading_days is missing expected trading days {[str(m) for m in missing[:5]]}: a skipped "
                                    "day would silently merge two intervals (list real holidays in market_holidays)")


def _grid_problem(slots: Sequence[SlotAccounting], expected_grid: Sequence[str]) -> str | None:
    counts = Counter(s.batch_ts for s in slots)
    expected = set(expected_grid)
    dup, missing, unexpected = (sorted(t for t, c in counts.items() if c > 1), sorted(expected - set(counts)),
                                sorted(set(counts) - expected))
    if dup or missing or unexpected:
        return (f"the interval has {len(expected_grid)} expected slots; missing {len(missing)}, duplicate {len(dup)}, "
                f"unexpected {len(unexpected)}")
    return None


def _evidence(s: SlotAccounting, cutoff: datetime, problems: Sequence[str]) -> SlotEvidence:
    """The shared per-slot evidence of one slot of this interval's grid (the same states the orchestrator uses)."""
    if s.state in INCOMPLETE_STATES:
        return SlotEvidence(s.batch_ts, SlotAccount.NON_FINAL, reasons=(s.state,))
    if not s.processed:
        return SlotEvidence(s.batch_ts, SlotAccount.FINAL_ABSENT, reasons=(s.state,))
    if problems:
        return SlotEvidence(s.batch_ts, SlotAccount.REJECTED, reasons=tuple(problems[:_MAX_DETAILS]))
    late = require_utc(s.available_at_utc) > cutoff                      # type: ignore[arg-type]
    return SlotEvidence(s.batch_ts, SlotAccount.ACCOUNTED_DELAYED if late else SlotAccount.ACCOUNTED, near_empty_of(s.near_empty))


def _assess_day(d: date, slots: Sequence[SlotAccounting] | None, expected_grid: Sequence[str], grid_problem: str | None,
                cutoff: datetime, verdict: Mapping[str, Sequence[str]], unaccounted: Sequence[str], early: IntervalEarlier,
                cfg: SentimentConfig) -> _Day:
    if not slots:
        return _Day("no_expected_slots", None, "no slot information for this interval",
                    assessment=incomplete_assessment("no slot information for this interval", earlier=early))
    n_exp = len(expected_grid)
    if grid_problem:
        return _Day("slot_grid_mismatch", None, grid_problem, n_exp, assessment=incomplete_assessment(grid_problem, n_expected=n_exp, earlier=early))
    evidence = [_evidence(s, cutoff, verdict.get(s.batch_ts, ())) for s in slots]
    sens = tuple(t for t in (0.50, 0.90) if t != cfg.coverage_threshold)
    report = coverage_block(evidence, CoverageThresholds(cfg.coverage_threshold, sens), expected_n=n_exp)      # report-only: no branch below reads it
    own_problems = [p for s in slots for p in verdict.get(s.batch_ts, ())]
    incomplete = [s for s in slots if s.state in INCOMPLETE_STATES]
    if incomplete:
        states = ", ".join(sorted({s.state for s in incomplete}))
        return _Day("incomplete_source_accounting", None, f"{len(incomplete)} slot(s) are not in a final state ({states}): the "
                    "interval cannot be accounted for", n_exp, assessment=assess_interval(evidence, early),
                    coverage_block=report)
    if early.not_examined or early.unresolved:                         # policy C-min: an earlier batch may sit in this interval
        a = assess_interval(evidence, early)
        return _Day("incomplete_source_accounting", None, "earlier-nominal batches are unresolved or were not examined: "
                    + "; ".join(a.reasons), n_exp, assessment=a, coverage_block=report)
    asof = [s.processed and require_utc(s.available_at_utc) <= cutoff for s in slots]      # type: ignore[arg-type]
    delayed = [s for s, ok in zip(slots, asof) if s.processed and not ok]
    # OD-10 part 2 (owner decision, S2.8J): a processed slot that fails reconciliation (``verdict``) is NOT covered. The denominator is unchanged.
    # The evidence is the reconciliation verdict itself; it is never inferred from a count or a favourable ratio.
    unreconciled = [s.batch_ts not in verdict or bool(verdict[s.batch_ts]) for s in slots]          # no verdict at all: fail closed
    covered_asof = [ok and not bad for ok, bad in zip(asof, unreconciled)]
    summaries = [SlotSummary(ok, s.near_empty if ok else None, s.rows_captured if ok else None) for s, ok in zip(slots, covered_asof)]
    obs = interval_count(summaries, cfg.coverage_threshold)
    n_cov = round((obs.coverage or 0.0) * len(summaries))
    # OD-13 (owner decision): aligned with the shared coverage block, which reports a near-empty indicator only for ACCOUNTED slots, so a processed
    # slot that fails reconciliation (or has no verdict) does not count here. Otherwise unchanged: processed, on time, flagged near-empty (True).
    near = sum(1 for s, ok in zip(slots, covered_asof) if ok and s.near_empty is True)
    # The threshold is INFORMATIONAL: no coverage rule is passed to the usability transition, so gaps leave the interval undecided (never usable-by-ratio, never unusable-by-ratio).
    a = assess_interval(evidence, early)
    met = None if obs.coverage is None else obs.coverage >= cfg.coverage_threshold
    common = dict(n_expected=n_exp, n_covered=n_cov, n_near_empty=near, n_delayed=len(delayed), assessment=a, coverage_block=report, threshold_met=met)
    note = f" ({len(delayed)} processed slot(s) became available only after the cutoff)" if delayed else ""
    if not any(asof):
        return _Day("missing_source_batches", obs.coverage, "no expected batch was available by the cutoff" + note, **common)
    no_verdict = [s.batch_ts for s in slots if s.processed and s.batch_ts not in verdict]          # a processed slot nobody reconciled: fail closed, whatever the ratio
    if own_problems or unaccounted or no_verdict:
        parts = list(own_problems[:_MAX_DETAILS])
        if no_verdict:
            parts.append(f"{len(no_verdict)} processed slot(s) have no reconciliation result: {', '.join(sorted(no_verdict)[:_MAX_DETAILS])}")
        if unaccounted:
            parts.append(f"{len(unaccounted)} batch(es) feed this interval without a reconciled source slot: "
                         f"{', '.join(sorted(unaccounted)[:_MAX_DETAILS])}")
        return _Day("slot_article_mismatch", obs.coverage, "; ".join(parts), **common)
    rows = {t: sum(s.theme_rows[t] for s in delayed) for t in schema.THEMES}            # type: ignore[index]
    return _Day("ok", obs.coverage, None, delayed_rows=rows, **common)


def _row(d: date, theme: str, cutoff: datetime, cfg: SentimentConfig, day: _Day, *, n: tuple[int | None, ...] = (),
         scoring_coverage: float | None = None, scoring_status: str = "not_applicable", dedup_status: str = "not_applicable",
         means: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None),
         no_news: bool | None = None, reason: str | None = None, carried: int | None = None,
         theme_ev: ThemeEvidence = ThemeEvidence.NOT_EVALUATED, theme_reasons: tuple[str, ...] = (),
         scoring_performed: bool = False) -> DailyFeatures:
    counts = n or (None,) * 6
    a = day.assessment
    assert a is not None
    ra, rr = result_availability(a, theme_ev, policy_blocked=False, scoring_performed=scoring_performed or theme_ev is not ThemeEvidence.HAS_RECORDS,
                                 test_only=cfg.allow_test_only)
    return DailyFeatures(
        source_completeness=a.source.value, interval_usability=a.usability.value, theme_evidence=theme_ev.value,
        theme_evidence_reasons=", ".join(theme_reasons) or None, result_availability=ra.value, result_reason=rr or None,
        n_slots_near_empty_unknown=a.n_near_empty_unknown,
        origin_date=d, theme=theme, n_eligible=counts[0], n_scored=counts[1], n_duplicates_removed=counts[2],
        n_invalid_text=counts[3], n_update_versions=counts[4], n_distinct_stories=counts[5], n_late_carried_in=carried,
        coverage=day.coverage, coverage_status=day.status, n_slots_expected=day.n_expected, n_slots_covered=day.n_covered,
        n_slots_near_empty=day.n_near_empty, n_slots_delayed=day.n_delayed,
        n_delayed_theme_rows=None if day.delayed_rows is None else day.delayed_rows[theme],
        scoring_coverage=scoring_coverage, scoring_status=scoring_status, dedup_status=dedup_status, mean_p_pos=means[0],
        mean_p_neg=means[1], mean_net=means[2], disp_net=means[3], no_news=no_news, feature_cutoff_utc=cutoff,
        model_revision=cfg.expected_model_revision, schema_version=FEATURE_SCHEMA_VERSION, reason=reason,
        coverage_report=day.coverage_block, coverage_threshold=cfg.coverage_threshold, coverage_threshold_met=day.threshold_met)


def aggregate_daily(articles: Sequence[ArticleRecord], trading_days: Sequence[date],
                    slots_by_origin: Mapping[date, Sequence[SlotAccounting]], *, config: SentimentConfig, earlier: EarlierEvidence,
                    themes: Sequence[str] = schema.THEMES) -> list[DailyFeatures]:
    """One row per (origin day, theme) for every trading day after the first (a day needs its previous cutoff).

    ``articles``, ``trading_days`` and ``themes`` must be a list or tuple. ``slots_by_origin`` maps each origin day to the
    ``SlotAccounting`` of every batch in that interval's nominal grid. ``earlier`` is the earlier-nominal evidence of policy C-min
    (``EarlierEvidence``; ``WindowReport.earlier_evidence()`` produces it): it has no default, so an interval can never be
    accounted for without saying whether earlier batches were looked for. The input records are validated and never modified.
    Records of an earlier batch are not accepted here (their slots are not part of the grid): such a record is a mismatch.
    """
    if not isinstance(config, SentimentConfig):
        raise SentimentFeatureError("config must be a SentimentConfig")
    require_policies_applied(config.policy)          # fail closed: no feature while a required research policy is unresolved
    if not isinstance(earlier, EarlierEvidence):
        raise SentimentFeatureError("earlier must be an EarlierEvidence (the C-min evidence is required)")
    arts = _materialize(articles, "articles")
    days = _materialize(trading_days, "trading_days")
    theme_list = _materialize(themes, "themes")
    if not isinstance(slots_by_origin, Mapping):
        raise SentimentFeatureError("slots_by_origin must be a mapping of origin day to slots")
    check_calendar(days, config.market_holidays)
    if any(t not in schema.THEMES for t in theme_list) or len(set(theme_list)) != len(theme_list):
        raise SentimentFeatureError(f"themes must be unique and among {schema.THEMES}")
    extra = [k for k in slots_by_origin if k not in set(days[1:])]
    if extra:
        raise SentimentFeatureError(f"slots supplied for dates that are not an origin day of this calendar: {[str(k) for k in extra[:3]]}")
    for slots in slots_by_origin.values():
        if not isinstance(slots, (list, tuple)) or not all(isinstance(s, SlotAccounting) for s in slots):
            raise SentimentFeatureError("every origin day's slots must be a list or tuple of SlotAccounting")
    expected_provenance = (config.expected_model_id, config.expected_model_revision, config.expected_scorer_code_sha256)
    seen: set[str] = set()
    for a in arts:
        schema.validate(a, allow_test_only=config.allow_test_only)
        if a.article_id in seen:
            raise SentimentFeatureError(f"duplicate article_id {a.article_id!r}: the same record appears twice")
        seen.add(a.article_id)
        if (a.model_id, a.model_revision, a.scorer_code_sha256) != expected_provenance:
            raise SentimentFeatureError("an article was produced by a different model, revision or scorer code than the one "
                                        "expected (this includes unavailable records): sentiment from different scorers is "
                                        "never mixed")
    versions = {(s.filter_version, s.parser_version) for slots in slots_by_origin.values() for s in slots if s.processed}
    if len(versions) > 1:
        raise SentimentFeatureError(f"slots were produced by different filter/parser versions {sorted(versions)}: never mixed")

    cutoffs = interval_cutoffs(days, config.early_closes)
    interval_of = interval_locator(days, config.early_closes)
    grids = nominal_grids(days, cutoffs)
    grid_problem = {d: (_grid_problem(slots_by_origin[d], grids[d]) if slots_by_origin.get(d) else None) for d in grids}
    by_batch: dict[str, list[ArticleRecord]] = defaultdict(list)
    for a in arts:
        by_batch[a.batch_ts].append(a)
    source_of: dict[str, date] = {}                      # batch -> the interval of its nominal slot
    verdict: dict[str, list[str]] = {}                   # batch -> reconciliation problems
    for d in grids:
        slots = slots_by_origin.get(d)
        if slots and grid_problem[d] is None:
            for s in slots:
                source_of[s.batch_ts] = d
                verdict[s.batch_ts] = reconcile_slot(s, by_batch.get(s.batch_ts, ()))
    placed: dict[date, list[ArticleRecord]] = defaultdict(list)
    for a in arts:
        if a.availability_status == "verified" and a.available_at_utc is not None:
            origin = interval_of(a.available_at_utc)
            if origin is not None:
                placed[origin].append(a)

    slot_obj = {s.batch_ts: s for d in grids if grid_problem[d] is None for s in (slots_by_origin.get(d) or ())}
    inflow: dict[date, list[str]] = defaultdict(list)       # processed but unreconciled batches whose availability lands in ANOTHER interval
    for b, s in slot_obj.items():
        if s.processed and verdict.get(b):
            target = interval_of(s.available_at_utc)         # type: ignore[arg-type]
            if target is not None and target != source_of[b]:
                inflow[target].append(b)

    out: list[DailyFeatures] = []
    for i in range(1, len(days)):
        d, upper = days[i], cutoffs[days[i]]
        slots = slots_by_origin.get(d)
        unaccounted = sorted({a.batch_ts for a in placed[d] if a.batch_ts not in verdict or verdict[a.batch_ts]})
        base = earlier.for_interval(d)
        early = dataclasses.replace(base, unresolved=tuple(sorted(set(base.unresolved) | set(inflow[d]))))
        day = _assess_day(d, slots, grids[d], grid_problem[d], upper, verdict, unaccounted, early, config)
        for theme in theme_list:
            out.append(_theme_row(d, theme, upper, day, placed[d], source_of, config))
    return sorted(out, key=lambda r: (r.origin_date, r.theme))


def _theme_row(d: date, theme: str, cutoff: datetime, day: _Day, placed: Sequence[ArticleRecord],
               source_of: Mapping[str, date], cfg: SentimentConfig) -> DailyFeatures:
    if day.status != "ok":
        return _row(d, theme, cutoff, cfg, day, reason=day.reason)
    eligible: list[ArticleRecord] = []
    duplicates = invalid = carried = 0
    for a in placed:
        if not a.theme_flags[theme]:
            continue
        carried += int(source_of[a.batch_ts] != d)
        if a.text_status != "ok":
            invalid += 1
        elif a.dup_status in cfg.dedup.duplicate_statuses:
            duplicates += 1
        else:
            eligible.append(a)
    scored = [a for a in eligible if a.pred_label in schema.LABELS]
    n_update = sum(1 for a in eligible if a.dup_status == "UPDATE")
    stories = Counter(a.story_id for a in eligible)
    non_update = Counter(a.story_id for a in eligible if a.dup_status != "UPDATE")
    unresolved = any(c > 1 for c in non_update.values())
    if unresolved:
        dedup_status = "unresolved_story_ids"
    elif not eligible and duplicates and not invalid:
        dedup_status = "duplicates_only_unresolved"
    elif n_update:
        dedup_status = "versions_kept_proposed"
    elif duplicates:
        dedup_status = "duplicates_removed_proposed"
    else:
        dedup_status = "none_found"
    counts = (len(eligible), len(scored), duplicates, invalid, n_update, len(stories))
    if not eligible:
        scoring_status, scoring_coverage = "not_applicable", None
    elif not scored:
        scoring_status, scoring_coverage = "none_scored", 0.0
    else:
        scoring_status = "complete" if len(scored) == len(eligible) else "partial"
        scoring_coverage = len(scored) / len(eligible)
    delayed_rows = day.delayed_rows[theme] if day.delayed_rows is not None else 0
    delay_note = f"delayed_rows_not_available_at_cutoff_{delayed_rows}" if delayed_rows else None
    assert day.assessment is not None
    ev, ev_reasons = theme_evidence(day.assessment, len(eligible) + invalid + duplicates, delayed_rows)
    common: dict[str, Any] = dict(n=counts, scoring_coverage=scoring_coverage, scoring_status=scoring_status,
                                  dedup_status=dedup_status, carried=carried, theme_ev=ev, theme_reasons=ev_reasons,
                                  scoring_performed=bool(scored) or not (eligible or invalid or duplicates))

    def row(reason: str | None, no_news: bool | None, means=(None, None, None, None)) -> DailyFeatures:
        return _row(d, theme, cutoff, cfg, day, **common, no_news=no_news, means=means, reason=reason)

    if unresolved:
        return row("story_ids_with_several_non_update_records: the policy for them is unapproved", None)
    if not eligible:
        if invalid:
            return row("all_candidate_articles_have_invalid_text", False)
        if duplicates:
            return row("only_duplicate_articles: whether a re-observation counts as news is an unapproved policy", None)
        if delayed_rows:
            return row(f"delayed_availability: {delayed_rows} series row(s) of this theme in batches available only after the "
                       "cutoff, so the absence of news is not verified", None)
        if ev is ThemeEvidence.VERIFIED_ZERO_RECORDS:                    # the only way no_news can be true (invariant I1)
            return row("verified_no_news", True)
        return row(f"unverified_empty: {', '.join(ev_reasons)}: zero records are not verified, so this is not 'no news'", None)
    if not scored:
        return row(";".join(filter(None, ["no_scored_articles", delay_note])), False)
    n = len(scored)
    pos = math.fsum(a.p_positive for a in scored) / n            # type: ignore[misc]
    neg = math.fsum(a.p_negative for a in scored) / n            # type: ignore[misc]
    nets = [a.p_positive - a.p_negative for a in scored]          # type: ignore[operator]
    mean_net = math.fsum(nets) / n
    disp = math.sqrt(math.fsum((x - mean_net) ** 2 for x in nets) / (n - 1)) if n > 1 else None   # sample std, ddof=1
    notes: list[str] = []
    if scoring_status == "partial":
        notes.append(f"partially_scored_{len(scored)}_of_{len(eligible)}")
    if n_update:
        notes.append("update_versions_kept_under_proposed_policy")
    if n == 1:
        notes.append("single_article_dispersion_undefined")
    if delay_note:
        notes.append(delay_note)
    return row(";".join(notes) or None, False, (pos, neg, mean_net, disp))


@dataclass(frozen=True)
class CountingDifference:
    origin_date: date
    theme: str
    n_eligible_primary: int | None
    n_eligible_sensitivity: int | None
    n_removed_in_sensitivity: int | None       # records the sensitivity policy treats as duplicates (the primary counts them)


@dataclass(frozen=True)
class CountingComparison:
    """The primary counting unit (every eligible record) and the sensitivity comparison (the proposed dedup policy), reported side by side and never merged."""

    primary: tuple[DailyFeatures, ...]
    sensitivity: tuple[DailyFeatures, ...]
    primary_unit: str = PRIMARY_UNIT
    sensitivity_unit: str = SENSITIVITY_UNIT

    def differences(self) -> tuple[CountingDifference, ...]:
        return tuple(CountingDifference(p.origin_date, p.theme, p.n_eligible, q.n_eligible, q.n_duplicates_removed)
                     for p, q in zip(self.primary, self.sensitivity))


def aggregate_daily_with_sensitivity(articles: Sequence[ArticleRecord], trading_days: Sequence[date],
                                     slots_by_origin: Mapping[date, Sequence[SlotAccounting]], *, config: SentimentConfig, earlier: EarlierEvidence,
                                     themes: Sequence[str] = schema.THEMES) -> CountingComparison:
    """Run ``aggregate_daily`` twice: with every eligible record counted (primary) and with ``PROPOSED_DEDUP_POLICY`` (sensitivity). ``config.dedup`` is overridden for both runs;
    every other setting, including the policy guard, is the caller's and applies to both."""
    def run(dedup: DedupPolicy) -> tuple[DailyFeatures, ...]:
        return tuple(aggregate_daily(articles, trading_days, slots_by_origin, config=dataclasses.replace(config, dedup=dedup), earlier=earlier, themes=themes))

    return CountingComparison(run(PRIMARY_DEDUP_POLICY), run(PROPOSED_DEDUP_POLICY))
