"""Window orchestrator (S2.6): connects the manifest adapter, the day-file adapter and the interval rules across a window.
Pure and offline; it does no file, database or network access (the caller supplies rows and a day-file source). **No scoring.**

It returns a ``WindowReport``: per-batch states, per-interval accounting with the candidate records placed in each interval, issues,
day-file statuses and provenance. It does **not** create ``ArticleRecord`` objects, predictions, neutral values or daily features:
the candidate records are unscored, and the step from them to the aggregator is blocked on a scorer and a ``story_id`` policy.

Existing pieces it reuses (no second implementation): ``adapt_manifest``, ``adapt_day_file`` and ``find_duplicate_record_ids``;
``slots.reconcile_slot``; ``features.check_calendar`` / ``check_calendar_inputs`` / ``interval_cutoffs`` / ``nominal_grids`` /
``interval_locator`` (which wrap ``session_calendar.cutoff_utc`` / ``origin_for`` and ``timeutil.slot_grid``).

**Per-batch state** (``SlotView.state``)
``reconciled`` processed, day file valid, counts and availability reconcile, available by its interval's cutoff;
``delayed`` the same but available only after the cutoff of its nominal interval (its records enter the later interval);
``source_batch_absent`` a final failed/absent/invalid batch (no records are allowed for it);
``missing_manifest_slot`` no manifest row for an expected batch; ``slot_rejected`` the manifest adapter rejected the row;
``non_final_slot`` not in a final state; ``day_file_missing`` / ``day_file_invalid`` the processed batch's day file is absent or
untrusted; ``count_mismatch`` captured, per-theme or company-item counts, or availability, do not reconcile; ``duplicate_record_id`` a
record id of the batch is ambiguous; ``version_mismatch`` the window's processed batches come from more than one (filter, parser)
version, so none is trusted (a window-scope issue lists the versions). Records of a batch that is not ``reconciled`` or ``delayed`` are
never placed in an interval. A record with an invalid ``batch_ts`` is its own issue (``invalid_batch_ts``) and is counted apart: it is
never "out of window".

``WindowReport.policy_status`` is immutable and ``policy_state()`` gives a ``PolicyState`` snapshot for ``policy.require_policies_applied``;
every required policy is currently unapplied, so a guarded downstream step refuses. ``digest()`` binds the window, calendar inputs,
``min_chars``, observed versions, policy status, a canonical fingerprint of the in-window manifest rows, a fingerprint of every accepted
record (identifiers, timestamps, flags, raw and normalised title hashes, a URL hash, versions, source file and line) and all derived states.

**Interval status** (``IntervalAccounting.status``)
``accounted_complete`` every nominal slot is ``reconciled``; ``accounted_with_delayed`` all accounted, some ``delayed``;
``partial_source_accounting`` all processed slots reconcile but some are ``source_batch_absent`` (whether that is enough is the
unapproved coverage-threshold decision, so no verdict is given); ``incomplete_accounting`` any other slot state, or a processed but
unreconciled batch whose known availability falls in the interval (unresolved inflow).

**Empty intervals** (``no_news_basis`` per theme): ``verified_complete_no_records`` only for ``accounted_complete`` with no record of
the theme; any other empty interval is ``unverified_empty_incomplete`` / ``_partial`` / ``_delayed``. A delayed batch is never
treated as evidence of absence: at the cutoff it did not exist yet.

**Preserved, unresolved:** repeated canonical URLs and title hashes are kept and only counted (``RepeatedContent``); nothing is
deduplicated and no story identity is inferred. Coverage thresholds, near-empty handling, calendars (caller-supplied), theme-specific
cutoffs and late-batch strictness beyond the minimum point-in-time rule are not decided here (``POLICY_STATUS``).

A record of a batch outside the window's nominal grid and outside the lookback is out of window (counted, not an error).

**Earlier nominal batches (F1, policy C-min).** A batch whose nominal time precedes the window can still become available inside it. The
caller declares ``earlier_batches_from``: the first nominal stamp from which ``slot_rows`` holds every manifest row up to the window start.
Every batch in that lookback is examined by its VERIFIED availability (the manifest's verified field, through the existing cutoff rules):
final-absent/failed batches can never arrive (counted); a processed batch whose availability is not inside the window is counted; one
whose availability is inside is read, validated and reconciled like any batch and its records enter the receiving interval
(``late_arrival_reconciled``; the interval is then ``accounted_with_delayed`` and an empty theme is ``unverified_empty_delayed``, never
verified no-records). If it cannot be located, validated or reconciled, the receiving interval is ``incomplete_accounting`` with a
specific ``earlier_batch_unresolved`` issue (batch, nominal time, verified availability, receiving interval); a batch whose availability
cannot be verified (missing row, non-final, unverifiable, ambiguous) cannot be placed, so EVERY interval is incomplete. Without the
declaration nothing was examined and every interval is incomplete (``earlier_batches_not_examined``). The requested window is never
extended: no interval, slot or row is produced for the lookback. Residual limit: arrivals from before ``earlier_batches_from`` are not
examined (the lookback length is an undecided parameter), and discovery uses only the manifest rows the caller supplies.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Any

from wealthpilot.data.gdelt.errors import GdeltToolError, InvalidTimestampError
from wealthpilot.data.gdelt.sentiment import schema
from wealthpilot.data.gdelt.sentiment.completeness import (
    EarlierEvidence, IntervalAssessment, IntervalEarlier, NearEmpty, SlotAccount, SlotEvidence, SourceCompleteness, ThemeEvidence,
    assess_interval, near_empty_of, result_availability, theme_evidence,
)
from wealthpilot.data.gdelt.sentiment.coverage_report import CoverageBlock, CoverageThresholds, coverage_block, coverage_rule_decision
from wealthpilot.data.gdelt.sentiment.near_empty import (
    BaselineObservation, NearEmptyParams, assess_near_empty, compare_flags, derived_counts, not_applicable,
)
from wealthpilot.data.gdelt.sentiment.policy import PolicyState
from wealthpilot.data.gdelt.sentiment.dayfile_adapter import CandidateRecord, DayFileResult, adapt_day_file
from wealthpilot.data.gdelt.sentiment.features import (
    check_calendar, check_calendar_inputs, interval_cutoffs, interval_locator, nominal_grids,
)
from wealthpilot.data.gdelt.sentiment.manifest_adapter import adapt_manifest
from wealthpilot.data.gdelt.sentiment.slots import ABSENT_OR_FAILED_STATES, INCOMPLETE_STATES, SlotAccounting, reconcile_slot
from wealthpilot.data.gdelt.timeutil import SLOT, format_batch_stamp, parse_batch_stamp, slot_grid

RECONCILED, DELAYED, ABSENT = "reconciled", "delayed", "source_batch_absent"
PROBLEM_STATES = ("missing_manifest_slot", "slot_rejected", "non_final_slot", "day_file_missing", "day_file_invalid",
                  "count_mismatch", "duplicate_record_id", "version_mismatch")
SLOT_STATES = (RECONCILED, DELAYED, ABSENT, *PROBLEM_STATES)
INTERVAL_STATUSES = ("accounted_complete", "accounted_with_delayed", "partial_source_accounting", "incomplete_accounting")
NO_NEWS_BASES = ("has_records", "verified_complete_no_records", "unverified_empty_incomplete", "unverified_empty_partial",
                 "unverified_empty_delayed")
# Immutable. Statuses follow the owner's explicit decisions of 2026-10-20 (reports/phaseB2S2_OWNER_APPROVAL_WORKSHEET.md, "Policy application decisions"). Only APPLIED_APPROVED and
# APPLIED_PROVISIONAL unblock (policy.require_policies_applied); APPLIED_PROVISIONAL stays visible as provisional in PolicyState.provisional(). The scorer policy is the one required policy still unresolved.
POLICY_STATUS: Mapping[str, str] = MappingProxyType({
    "deduplication_and_story_updates": "APPLIED_PROVISIONAL",    # primary analysis counts every eligible record; the proposed dedup policy is a sensitivity comparison
    "cross_interval_story_uniqueness": "APPLIED_APPROVED",       # each record counts in its verified availability interval; no claim of unique underlying stories
    "source_coverage_threshold": "APPLIED_PROVISIONAL",          # 0.75 primary, 0.50 / 0.90 sensitivity: INFORMATIONAL, never decides usability, never creates neutral or verified no-news
    "scoring_coverage_threshold": "APPLIED_APPROVED",            # report only: no scoring cutoff exists
    "scorer_approval_and_polarity_validation": "UNRESOLVED_NOT_APPLIED",   # no approved model, licence, runtime, weights, independent labels or validation criteria
    "near_empty_slot_handling": "APPLIED_PROVISIONAL",           # 14 days, >= 7 prior observations, < 10% of the median; unknown stays unknown
    "holiday_and_early_close_calendars": "APPLIED_PROVISIONAL",  # caller-supplied calendars, UNVERIFIED
    "theme_specific_calendars": "NOT_IMPLEMENTED",
    "late_batch_strictness": "APPLIED_PROVISIONAL",              # C-min with a caller-declared lookback per run; the residual limit is reported (WindowReport.residual_limitations)
    "scoring": "NOT_PERFORMED",
})
# Where each required policy's current status comes from. The owner decisions are in reports/phaseB2S2_OWNER_APPROVAL_WORKSHEET.md ("Policy application decisions", 2026-10-20).
POLICY_PROVENANCE: Mapping[str, str] = MappingProxyType({
    "deduplication_and_story_updates": "worksheet: owner applied provisionally (primary = every eligible record; current dedup = sensitivity)",
    "cross_interval_story_uniqueness": "worksheet: owner applied (each record in its verified availability interval; no unique-story claim)",
    "source_coverage_threshold": "worksheet: owner applied provisionally and informationally (0.75; 0.50/0.90); the verdict never decides usability",
    "scoring_coverage_threshold": "worksheet: owner applied as report-only (no scoring cutoff)",
    "scorer_approval_and_polarity_validation": "worksheet: owner kept BLOCKED until model, licence, runtime, weights, independent labels and validation criteria are resolved",
    "near_empty_slot_handling": "worksheet: owner applied provisionally (14 / 7 / 10%); unknown stays unknown",
    "holiday_and_early_close_calendars": "worksheet: owner accepted caller-supplied calendars provisionally; unverified",
    "late_batch_strictness": "worksheet: owner applied provisionally with a caller-declared lookback per run; residual limit reported",
})
_ORPHAN_CODES = ("batch_not_in_manifest", "batch_slot_not_processed")


class OrchestratorError(GdeltToolError):
    """A wrong call (arguments), not a data problem. Data problems are reported in the ``WindowReport``."""

    code = "sentiment_orchestrator_error"


@dataclass(frozen=True)
class DayFileData:
    """What a day-file source returns for one UTC day: the bytes, a provenance label and the ``day_commit`` row."""

    data: bytes
    source_name: str
    day_commit: Mapping[str, Any] | None


DaySource = Callable[[str], "DayFileData | None"]


@dataclass(frozen=True)
class WindowInputs:
    trading_days: Sequence[date]
    early_closes: frozenset[date]
    market_holidays: frozenset[date]
    filter_version: str
    min_chars: int
    slot_rows: Sequence[Mapping[str, Any]]
    series_rows: Sequence[Mapping[str, Any]]
    day_source: DaySource
    # F1 (C-min): the first nominal batch stamp from which the caller guarantees ``slot_rows`` holds EVERY manifest row up to the window
    # start (the lookback in which late arrivals are looked for). ``None`` means "earlier batches were not examined": the window then fails
    # closed. This does not extend the requested window: no interval or row is produced for the lookback.
    earlier_batches_from: str | None = None
    # S2.8E: the first nominal stamp from which the caller guarantees ``slot_rows`` holds EVERY manifest row (the near-empty baseline). ``None``:
    # no baseline evidence, so the derived near-empty state is unknown. It does not extend the window and it chooses no lookback length: the
    # detector needs ``near_empty_params.lookback_days`` of it before each assessed slot. Both parameter sets below are PROVISIONAL.
    baseline_batches_from: str | None = None
    coverage_thresholds: CoverageThresholds = CoverageThresholds()
    near_empty_params: NearEmptyParams = NearEmptyParams()


@dataclass(frozen=True)
class WindowIssue:
    scope: str                                   # manifest | day_file | record | window
    code: str
    detail: str
    batch_ts: str | None = None
    utc_day: str | None = None
    line: int | None = None
    record_id: str | None = None

    def sort_key(self) -> tuple[Any, ...]:
        return (self.scope, self.utc_day or "", self.batch_ts or "", self.line or 0, self.record_id or "", self.code, self.detail)


@dataclass(frozen=True)
class SlotView:
    batch_ts: str
    interval: date                               # the origin day whose nominal grid holds the batch
    state: str
    available_at_utc: datetime | None
    delayed_into: date | None
    n_records: int
    rows_captured: int | None
    theme_rows: Mapping[str, int] | None
    near_empty: bool | None                      # the OBSERVED manifest flag (None: NULL, unknown)
    reasons: tuple[str, ...]
    derived_near_empty: str = "not_applicable"   # the detector's own state (NearEmpty value); never replaces the observed flag
    derived_reason: str = "not_applicable"
    flag_comparison: str = "not_applicable"


@dataclass(frozen=True)
class EarlierArrival:
    """A batch whose nominal time precedes the window and whose verified availability may fall inside it (F1, policy C-min).

    ``state`` is ``late_arrival_reconciled`` (read, validated and reconciled; its records are in ``receiving_interval``) or
    ``earlier_batch_unresolved`` / one of the problem states of ``SlotView`` (the receiving interval, or every interval when the
    receiving interval cannot be known, is incomplete). Both the nominal time and the verified availability are kept.
    """

    batch_ts: str
    nominal_utc: datetime
    available_at_utc: datetime | None            # verified availability; None when none is verified
    receiving_interval: date | None              # None: unknown, so every interval of the window is affected
    state: str
    n_records: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DayFileStatus:
    utc_day: str
    status: str                                  # ok | missing | invalid
    codes: tuple[str, ...]
    source_name: str | None
    file_sha256: str | None
    rows_read: int
    n_records: int
    n_rows_rejected: int


@dataclass(frozen=True)
class ThemeEvidenceRecord:
    """Per-theme record evidence and result availability (shared vocabulary values). Never a sentiment value."""

    evidence: str                                # ThemeEvidence
    reasons: tuple[str, ...]
    result_availability: str                     # ResultAvailability: BLOCKED_BY_POLICY while any required policy is unresolved
    result_reason: str


_LEGACY_STATUS = {SourceCompleteness.COMPLETE: "accounted_complete", SourceCompleteness.COMPLETE_WITH_DELAYED: "accounted_with_delayed",
                  SourceCompleteness.FINAL_GAPS: "partial_source_accounting", SourceCompleteness.INCOMPLETE: "incomplete_accounting"}
_ACCOUNT = {RECONCILED: SlotAccount.ACCOUNTED, DELAYED: SlotAccount.ACCOUNTED_DELAYED, ABSENT: SlotAccount.FINAL_ABSENT,
            "missing_manifest_slot": SlotAccount.MISSING, "non_final_slot": SlotAccount.NON_FINAL}


def _slot_evidence(v: "SlotView") -> SlotEvidence:
    """A window slot as shared evidence: any state that is not accounted, final-absent, missing or non-final is a rejection."""
    account = _ACCOUNT.get(v.state, SlotAccount.REJECTED)
    accounted = account in (SlotAccount.ACCOUNTED, SlotAccount.ACCOUNTED_DELAYED)
    return SlotEvidence(v.batch_ts, account, near_empty_of(v.near_empty) if accounted else NearEmpty.NOT_APPLICABLE, v.reasons)


def _basis(a: IntervalAssessment, ev: ThemeEvidence) -> str:
    """The legacy ``no_news_basis`` label for a theme, derived from the shared evidence (never decided separately)."""
    if ev is ThemeEvidence.HAS_RECORDS:
        return "has_records"
    if ev is ThemeEvidence.VERIFIED_ZERO_RECORDS:
        return "verified_complete_no_records"
    return {SourceCompleteness.INCOMPLETE: "unverified_empty_incomplete", SourceCompleteness.FINAL_GAPS: "unverified_empty_partial",
            SourceCompleteness.COMPLETE_WITH_DELAYED: "unverified_empty_delayed",
            SourceCompleteness.COMPLETE: "unverified_empty_indicator"}[a.source]


@dataclass(frozen=True)
class IntervalAccounting:
    origin_date: date
    cutoff_utc: datetime
    status: str
    n_expected_slots: int
    slot_state_counts: Mapping[str, int]
    records: tuple[CandidateRecord, ...] = field(repr=False)
    n_records_by_theme: Mapping[str, int]
    n_late_carried_in: int
    n_delayed_slots: int
    delayed_theme_rows: Mapping[str, int]
    n_near_empty_slots: int
    unresolved_inflow: tuple[str, ...]
    no_news_basis: Mapping[str, str]             # legacy label derived from ``theme_evidence`` (see ``_basis``)
    reasons: tuple[str, ...]
    n_earlier_arrivals: int = 0                  # reconciled earlier-nominal batches whose records entered this interval
    assessment: IntervalAssessment | None = None           # shared vocabulary: source completeness and interval usability
    theme_evidence: Mapping[str, "ThemeEvidenceRecord"] = field(default_factory=dict)    # per theme: evidence and result availability
    coverage: CoverageBlock | None = None                  # SOURCE-slot coverage (S2.8E): provisional thresholds, a report only
    derived_near_empty: Mapping[str, int] = field(default_factory=dict)    # detector states over the accounted slots (counts)


@dataclass(frozen=True)
class RepeatedContent:
    """Repeats are preserved and counted only. No story identity is inferred."""

    n_url_groups: int
    n_url_groups_across_batches: int
    n_records_in_repeated_urls: int
    n_title_hash_groups: int
    n_title_hash_groups_across_batches: int
    n_records_in_repeated_title_hashes: int
    policy: str = POLICY_STATUS["deduplication_and_story_updates"]


@dataclass(frozen=True)
class WindowReport:
    trading_days: tuple[date, ...]
    filter_version: str
    intervals: tuple[IntervalAccounting, ...]
    slots: tuple[SlotView, ...]
    day_files: tuple[DayFileStatus, ...]
    issues: tuple[WindowIssue, ...]
    repeated_content: RepeatedContent
    n_manifest_rows_outside_window: int
    n_out_of_window_records: int
    n_records_beyond_window: int
    n_records_held_back: int
    n_records_invalid_batch_ts: int              # rejected records whose batch_ts is not a canonical stamp (never "out of window")
    early_closes: frozenset[date]
    market_holidays: frozenset[date]
    min_chars: int
    observed_versions: tuple[tuple[str | None, str | None], ...]   # distinct (filter, parser) pairs of the processed slots
    input_fingerprint: str                       # canonical hash of the in-window manifest slot and series rows
    record_fingerprint: str                      # canonical hash of every record accepted from the day files (content hashes, not text)
    earlier_batches_from: str | None             # the declared start of the lookback in which earlier nominal batches were examined
    earlier_arrivals: tuple[EarlierArrival, ...]
    n_lookback_rows: int
    n_earlier_final_unavailable: int             # earlier batches that are final-absent/failed/invalid: they can never become available
    n_earlier_outside_window: int                # earlier batches whose verified availability is not inside the window
    policy_status: Mapping[str, str] = field(default_factory=lambda: MappingProxyType(dict(POLICY_STATUS)))
    baseline_batches_from: str | None = None
    coverage_thresholds: CoverageThresholds = CoverageThresholds()
    near_empty_params: NearEmptyParams = NearEmptyParams()
    n_baseline_rows: int = 0

    def interval(self, d: date) -> IntervalAccounting:
        return next(i for i in self.intervals if i.origin_date == d)

    def earlier_evidence(self) -> EarlierEvidence:
        """The earlier-nominal (C-min) evidence of this window in the shared form the feature aggregator requires."""
        if self.earlier_batches_from is None:
            return EarlierEvidence.not_examined()
        by_interval: dict[date, list[str]] = defaultdict(list)
        window: list[str] = []
        reconciled: Counter[date] = Counter()
        for a in self.earlier_arrivals:
            if a.state == "late_arrival_reconciled":
                reconciled[a.receiving_interval] += 1                      # type: ignore[index]
            elif a.receiving_interval is None:
                window.append(a.batch_ts)
            else:
                by_interval[a.receiving_interval].append(a.batch_ts)
        return EarlierEvidence(True, tuple(sorted(window)), tuple((k, tuple(sorted(v))) for k, v in sorted(by_interval.items())),
                               tuple(sorted(reconciled.items())))

    def residual_limitations(self) -> tuple[str, ...]:
        """What this result does NOT establish, given the provisional policies it ran under (always shown with the result; none of it is a warning to ignore)."""
        out = [f"calendars are caller-supplied and unverified ({len(self.early_closes)} early close(s), {len(self.market_holidays)} holiday(s) supplied)",
               f"coverage thresholds {self.coverage_thresholds.primary} / {tuple(self.coverage_thresholds.sensitivity)} are provisional and informational: they never decide usability or create no-news",
               f"near-empty detector ({self.near_empty_params.lookback_days} days, >= {self.near_empty_params.min_baseline_obs} observations, < {self.near_empty_params.ratio:.0%} of the median) is provisional; unknown stays unknown"]
        if self.earlier_batches_from is None:
            out.append("earlier nominal batches were NOT examined: no lookback was declared, so every interval is incomplete")
        else:
            out.append(f"late-arrival completeness is established only for batches from {self.earlier_batches_from} onward; a batch from before that stamp could still arrive inside the window and is not examined")
        out.append("no derived baseline evidence was declared: derived near-empty states are unknown" if self.baseline_batches_from is None
                   else f"derived near-empty states use manifest rows from {self.baseline_batches_from} onward only")
        return tuple(out)

    def policy_state(self) -> PolicyState:
        """An immutable snapshot of ``policy_status`` for ``policy.require_policies_applied``."""
        return PolicyState.from_mapping(self.policy_status)

    def digest(self) -> str:
        """A deterministic fingerprint binding the window, configuration, policy, versions, input rows, day files, record content and
        every derived state. It carries only hashes, identifiers and counts: no title, URL or other payload text. Anything that has no
        semantic order (inputs, records) is sorted before it is hashed.

        Provenance the existing schema does not provide, and which is therefore NOT bound: the code version of this tool, the
        filter specification hash, and the identity of the manifest database or day-file paths (``source_name`` is the caller's label).
        """
        iso = lambda v: None if v is None else v.isoformat()                                            # noqa: E731
        payload = {
            "tag": "wp-window-digest-v3",
            "trading_days": [d.isoformat() for d in self.trading_days], "filter_version": self.filter_version,
            "early_closes": sorted(d.isoformat() for d in self.early_closes),
            "market_holidays": sorted(d.isoformat() for d in self.market_holidays), "min_chars": self.min_chars,
            "versions": sorted([list(v) for v in self.observed_versions], key=str), "policy": sorted(self.policy_status.items()),
            "input_fingerprint": self.input_fingerprint, "record_fingerprint": self.record_fingerprint,
            "day_files": [[d.utc_day, d.status, list(d.codes), d.source_name, d.file_sha256, d.rows_read, d.n_records, d.n_rows_rejected]
                          for d in self.day_files],
            "slots": [[s.batch_ts, s.interval.isoformat(), s.state, iso(s.available_at_utc), iso(s.delayed_into), s.n_records,
                       s.rows_captured, None if s.theme_rows is None else sorted(s.theme_rows.items()), s.near_empty, list(s.reasons),
                       s.derived_near_empty, s.derived_reason, s.flag_comparison]
                      for s in self.slots],
            "intervals": [[i.origin_date.isoformat(), i.cutoff_utc.isoformat(), i.status, i.n_expected_slots,
                           sorted(i.slot_state_counts.items()), [r.article_id for r in i.records], sorted(i.n_records_by_theme.items()),
                           i.n_late_carried_in, i.n_delayed_slots, sorted(i.delayed_theme_rows.items()), i.n_near_empty_slots,
                           list(i.unresolved_inflow), sorted(i.no_news_basis.items()), list(i.reasons), i.n_earlier_arrivals,
                           None if i.assessment is None else [i.assessment.source.value, i.assessment.usability.value,
                                                             i.assessment.n_near_empty, i.assessment.n_near_empty_unknown],
                           [[t, e.evidence, list(e.reasons), e.result_availability] for t, e in sorted(i.theme_evidence.items())],
                           None if i.coverage is None else [i.coverage.n_expected, i.coverage.n_covered, i.coverage.ratio,
                                                            sorted(i.coverage.excluded_by_reason.items()),
                                                            i.coverage.max_consecutive_missing_run, i.coverage.max_consecutive_uncovered_run,
                                                            [[t.threshold, t.label, t.meets] for t in i.coverage.thresholds]],
                           sorted(i.derived_near_empty.items())]
                          for i in self.intervals],
            "earlier": [self.earlier_batches_from, self.n_lookback_rows, self.n_earlier_final_unavailable, self.n_earlier_outside_window,
                        [[a.batch_ts, iso(a.nominal_utc), iso(a.available_at_utc), iso(a.receiving_interval), a.state, a.n_records,
                          list(a.reasons)] for a in self.earlier_arrivals]],
            "detector": [self.baseline_batches_from, self.n_baseline_rows, self.coverage_thresholds.primary,
                         list(self.coverage_thresholds.sensitivity), self.coverage_thresholds.status, self.near_empty_params.lookback_days,
                         self.near_empty_params.min_baseline_obs, self.near_empty_params.ratio, self.near_empty_params.status],
            "issues": [list(x.sort_key()) for x in self.issues], "repeated_content": asdict(self.repeated_content),
            "counters": [self.n_manifest_rows_outside_window, self.n_out_of_window_records, self.n_records_beyond_window,
                         self.n_records_held_back, self.n_records_invalid_batch_ts],
        }
        return _fingerprint(payload)


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")


def _fingerprint(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _record_line(r: CandidateRecord) -> list[Any]:
    """The content and provenance of one record as hashes and identifiers (the title and URL text are represented by their hashes)."""
    return [r.article_id, r.batch_ts, r.available_at_utc.isoformat(), r.source_domain, r.title_sha256_raw, r.filter_title_hash,
            hashlib.sha256(r.url_canonical.encode("utf-8")).hexdigest(), r.word_count, r.text_status, sorted(r.theme_flags.items()),
            r.company_item, r.same_batch_status, r.filter_version, r.parser_version, r.source_file, r.source_line, list(r.tone_raw)]


def _is_stamp(value: Any) -> bool:
    try:
        parse_batch_stamp(value)
    except InvalidTimestampError:
        return False
    return True


_ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _verified_availability(row: Any) -> datetime | None:
    """The manifest's own verified availability of a (possibly rejected) row, or None. Never a page publication time."""
    if not isinstance(row, Mapping) or row.get("availability_status") != "verified":
        return None
    raw = row.get("available_at_utc")
    if not (isinstance(raw, str) and _ISO_Z.match(raw)):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _utc_day(batch: str) -> str:
    return f"{batch[:4]}-{batch[4:6]}-{batch[6:8]}"


def _seq(rec: CandidateRecord) -> tuple[str, int]:
    return rec.batch_ts, int(rec.article_id.split("-", 1)[1])


def _repeats(records: Sequence[CandidateRecord], key: Callable[[CandidateRecord], str | None]) -> tuple[int, int, int]:
    groups: dict[str, list[CandidateRecord]] = defaultdict(list)
    for r in records:
        k = key(r)
        if k:
            groups[k].append(r)
    rep = [g for g in groups.values() if len(g) > 1]
    return len(rep), sum(1 for g in rep if len({r.batch_ts for r in g}) > 1), sum(len(g) for g in rep)


def _baseline_observations(rows: Sequence[Mapping[str, Any]], series: Sequence[Mapping[str, Any]], filter_version: str,
                           first: str, last: str) -> tuple[list[BaselineObservation], int]:
    """Manifest observations of ``rows_english_valid`` in ``[first, last]`` for the near-empty baseline. A processed slot is committed and valid;
    a non-final one is uncommitted; a rejected or ambiguous one is invalid. A stamp with no row at all has no observation."""
    lo, hi = parse_batch_stamp(first), parse_batch_stamp(last)
    pick = lambda r: isinstance(r, Mapping) and _is_stamp(r.get("batch_ts")) and lo <= parse_batch_stamp(r["batch_ts"]) <= hi     # noqa: E731
    chosen = [r for r in rows if pick(r)]
    chosen_series = [r for r in series if pick(r)]
    ad = adapt_manifest(chosen, chosen_series, filter_version=filter_version)
    rejected = {r.batch_ts for r in ad.rejections if r.batch_ts}
    out: list[BaselineObservation] = []
    for b in sorted({r["batch_ts"] for r in chosen}):
        src = ad.sources.get(b)
        if b in rejected or src is None:
            out.append(BaselineObservation(b, None, False, False))
        elif src.stage_counts is None:
            out.append(BaselineObservation(b, None, False, True))
        else:
            out.append(BaselineObservation(b, src.stage_counts["rows_english_valid"], True, True))
    return out, len(chosen)


def orchestrate_window(inputs: WindowInputs) -> WindowReport:
    """Account for a window: adapt, reconcile and place unscored records, and report every state. No sentiment is produced."""
    if not isinstance(inputs, WindowInputs):
        raise OrchestratorError("inputs must be a WindowInputs")
    if not isinstance(inputs.trading_days, (list, tuple)):
        raise OrchestratorError("trading_days must be a list or tuple")
    if not callable(inputs.day_source):
        raise OrchestratorError("day_source must be a callable returning DayFileData or None")
    if not isinstance(inputs.slot_rows, (list, tuple)) or not isinstance(inputs.series_rows, (list, tuple)):
        raise OrchestratorError("slot_rows and series_rows must be lists or tuples of mappings")
    try:
        check_calendar_inputs(inputs.early_closes, inputs.market_holidays)
        check_calendar(tuple(inputs.trading_days), inputs.market_holidays)
    except GdeltToolError as exc:
        raise OrchestratorError(f"invalid calendar: {exc}") from exc
    days = tuple(inputs.trading_days)
    cutoffs = interval_cutoffs(days, inputs.early_closes)
    grids = nominal_grids(days, cutoffs)
    locate = interval_locator(days, inputs.early_closes)
    interval_of_batch = {b: d for d, grid in grids.items() for b in grid}
    expected = sorted(interval_of_batch)
    issues: list[WindowIssue] = []

    # the lookback: nominal batches before the first interval, in which late arrivals into the window are looked for (F1, C-min)
    first_slot = grids[days[1]][0]
    lookback_grid: list[str] = []
    if inputs.earlier_batches_from is not None:
        if not _is_stamp(inputs.earlier_batches_from) or parse_batch_stamp(inputs.earlier_batches_from) >= parse_batch_stamp(first_slot):
            raise OrchestratorError(f"earlier_batches_from must be a canonical batch stamp before the window's first slot {first_slot}")
        lookback_grid = slot_grid(inputs.earlier_batches_from, format_batch_stamp(parse_batch_stamp(first_slot) - SLOT))
    lookback = set(lookback_grid)
    baseline: list[BaselineObservation] = []
    n_baseline_rows = 0
    if inputs.baseline_batches_from is not None:
        if not _is_stamp(inputs.baseline_batches_from) or parse_batch_stamp(inputs.baseline_batches_from) >= parse_batch_stamp(first_slot):
            raise OrchestratorError(f"baseline_batches_from must be a canonical batch stamp before the window's first slot {first_slot}")
        baseline, n_baseline_rows = _baseline_observations(inputs.slot_rows, inputs.series_rows, inputs.filter_version,
                                                           inputs.baseline_batches_from, max(interval_of_batch))

    # 1. manifest rows in the window and in the lookback (rows of other batches are counted, not adapted)
    in_rows, lb_rows, outside = [], [], 0
    for row in inputs.slot_rows:
        stamp = row.get("batch_ts") if isinstance(row, Mapping) else None
        if _is_stamp(stamp) and stamp in lookback:
            lb_rows.append(row)
        elif _is_stamp(stamp) and stamp not in interval_of_batch:
            outside += 1
        else:
            in_rows.append(row)
    in_series, lb_series = [], []
    for r in inputs.series_rows:
        stamp = r.get("batch_ts") if isinstance(r, Mapping) else None
        if _is_stamp(stamp) and stamp in lookback:
            lb_series.append(r)
        elif not (_is_stamp(stamp) and stamp not in interval_of_batch):
            in_series.append(r)
    input_fp = _fingerprint({"slot_rows": sorted(_canonical(r).decode() for r in in_rows),
                             "series_rows": sorted(_canonical(r).decode() for r in in_series), "outside": outside,
                             "lookback_from": inputs.earlier_batches_from,
                             "lookback_rows": sorted(_canonical(r).decode() for r in lb_rows),
                             "lookback_series": sorted(_canonical(r).decode() for r in lb_series)}
                            | ({"baseline_from": inputs.baseline_batches_from,
                                "baseline": [[o.batch_ts, o.rows_english_valid, o.committed, o.valid] for o in baseline]}
                               if inputs.baseline_batches_from is not None else {}))
    adaptation = adapt_manifest(in_rows, in_series, filter_version=inputs.filter_version, expected_batches=expected)
    slots = adaptation.by_batch()
    rej_by_batch: dict[str, list[str]] = defaultdict(list)
    for r in adaptation.rejections:
        issues.append(WindowIssue("manifest", r.code, r.detail, batch_ts=r.batch_ts))
        if r.batch_ts:
            rej_by_batch[r.batch_ts].append(r.code)

    # 1a. earlier nominal batches (F1, policy C-min): a batch from before the window whose VERIFIED availability falls inside it must be
    # accounted for (read, validated, reconciled) before the receiving interval can be complete. Discovery uses only the manifest rows the
    # caller supplied for the declared lookback; without that declaration nothing was examined and the window fails closed.
    inflow_slots: dict[str, SlotAccounting] = {}
    receiving: dict[str, date] = {}
    early_unresolved_by_interval: dict[date, list[EarlierArrival]] = defaultdict(list)
    early_unresolved_window: list[EarlierArrival] = []
    early_final_unavailable = early_outside = 0
    if lookback_grid:
        lb = adapt_manifest(lb_rows, lb_series, filter_version=inputs.filter_version, expected_batches=lookback_grid)
        lb_slots = lb.by_batch()
        lb_codes: dict[str, list[str]] = defaultdict(list)
        for rej in lb.rejections:
            if rej.batch_ts:
                lb_codes[rej.batch_ts].append(rej.code)
        raw_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in lb_rows:
            raw_rows[row["batch_ts"]].append(row)
        for b in lookback_grid:
            nominal = parse_batch_stamp(b)
            s, codes_b = lb_slots.get(b), sorted(set(lb_codes.get(b, [])))
            if s is not None and s.state in ABSENT_OR_FAILED_STATES:
                early_final_unavailable += 1                              # final and never available: it cannot arrive in the window
                continue
            if s is not None and s.processed:
                target = locate(s.available_at_utc)                       # the verified availability, through the existing cutoff rules
                if target is None:
                    early_outside += 1
                    continue
                inflow_slots[b], receiving[b] = s, target
                continue
            if s is not None:                                             # non-final: its availability is not known yet
                early_unresolved_window.append(EarlierArrival(b, nominal, None, None, "earlier_batch_unresolved", 0,
                                                               (f"non_final_slot:{s.state}",)))
                continue
            rows_b = raw_rows.get(b, [])
            usable = _verified_availability(rows_b[0]) if len(rows_b) == 1 else None
            if usable is not None:                                        # a rejected row whose manifest-verified availability is usable
                target = locate(usable)
                if target is None:
                    early_outside += 1
                    continue
                early_unresolved_by_interval[target].append(EarlierArrival(b, nominal, usable, target, "earlier_batch_unresolved", 0,
                                                                           tuple(codes_b) or ("rejected",)))
            else:
                early_unresolved_window.append(EarlierArrival(b, nominal, None, None, "earlier_batch_unresolved", 0,
                                                               tuple(codes_b) or ("no_verified_availability",)))
    for arrival in [a for lst in early_unresolved_by_interval.values() for a in lst] + early_unresolved_window:
        where = f"receiving interval {arrival.receiving_interval}" if arrival.receiving_interval else "every interval of the window"
        when = f", verified availability {arrival.available_at_utc.isoformat()}" if arrival.available_at_utc else ", no verified availability"
        issues.append(WindowIssue("window", "earlier_batch_unresolved",
                                  f"earlier batch {arrival.batch_ts} (nominal {arrival.nominal_utc.isoformat()}{when}) cannot be accounted for "
                                  f"({', '.join(arrival.reasons)}): {where} is incomplete", batch_ts=arrival.batch_ts))
    earlier_not_examined = inputs.earlier_batches_from is None
    if earlier_not_examined:
        issues.append(WindowIssue("window", "earlier_batches_not_examined",
                                  "earlier_batches_from was not supplied, so no earlier nominal batch was looked for: a late arrival could "
                                  "sit in any interval; every interval is incomplete until the lookback evidence is supplied"))

    # 1b. one parser and filter version across the window: a mixed window cannot say which one is right, so it fails closed
    version_counts = Counter((s.filter_version, s.parser_version) for s in [*slots.values(), *inflow_slots.values()] if s.processed)
    observed_versions = tuple(sorted(version_counts, key=str))
    version_conflict = len(version_counts) > 1
    if version_conflict:
        detail = "; ".join(f"filter {fv} / parser {pv}: {n} batch(es)" for (fv, pv), n in sorted(version_counts.items(), key=str))
        issues.append(WindowIssue("window", "mixed_versions", f"processed batches come from different versions ({detail}); no batch is trusted"))

    # 2. day files for the UTC days of processed slots
    slots_all = {**slots, **inflow_slots}                          # window slots plus accepted earlier late arrivals
    needed = [] if version_conflict else sorted({_utc_day(b) for b, s in slots_all.items() if s.processed})
    day_status: dict[str, DayFileStatus] = {}
    results: dict[str, DayFileResult] = {}
    out_of_window = 0
    invalid_ts_lines: set[tuple[str, int | None]] = set()
    dup_batches: set[str] = set()
    for day in needed:
        fetched = inputs.day_source(day)
        if fetched is None:
            day_status[day] = DayFileStatus(day, "missing", ("day_file_missing",), None, None, 0, 0, 0)
            issues.append(WindowIssue("day_file", "day_file_missing", "no day file for a UTC day that has processed batches", utc_day=day))
            continue
        if not isinstance(fetched, DayFileData):
            raise OrchestratorError("day_source must return DayFileData or None")
        if fetched.day_commit is None:
            day_status[day] = DayFileStatus(day, "invalid", ("day_commit_missing",), fetched.source_name, None, 0, 0, 0)
            issues.append(WindowIssue("day_file", "day_commit_missing", "a day file without its day_commit record is not trusted", utc_day=day))
            continue
        res = adapt_day_file(fetched.data, utc_day=day, slots=slots_all, min_chars=inputs.min_chars, source_name=fetched.source_name,
                             day_commit=fetched.day_commit)
        file_level = [r for r in res.rejections if r.line is None]
        if file_level:
            codes = tuple(sorted({r.code for r in file_level}))
            day_status[day] = DayFileStatus(day, "invalid", codes, fetched.source_name, res.file_sha256, res.rows_read, 0, len(res.rejections))
            issues += [WindowIssue("day_file", r.code, r.detail, utc_day=day) for r in file_level]
            continue
        rows_rejected = 0
        for r in res.rejections:
            rows_rejected += 1
            if r.code == "invalid_batch_ts":
                invalid_ts_lines.add((day, r.line))                      # its own specific issue below; never "out of window"
            if r.code in _ORPHAN_CODES and r.batch_ts is not None and r.batch_ts not in interval_of_batch:
                out_of_window += 1
                continue
            if r.code == "duplicate_record_id" and r.batch_ts:
                dup_batches.add(r.batch_ts)
            issues.append(WindowIssue("record", r.code, r.detail, batch_ts=r.batch_ts, utc_day=day, line=r.line, record_id=r.record_id))
        day_status[day] = DayFileStatus(day, "ok", (), fetched.source_name, res.file_sha256, res.rows_read, len(res.records), rows_rejected)
        results[day] = res
    # an id cannot repeat across files: the adapter requires the id prefix to equal the batch and the batch to lie on the file's day
    records_by_batch: dict[str, list[CandidateRecord]] = defaultdict(list)
    for res in results.values():
        for rec in res.records:
            records_by_batch[rec.batch_ts].append(rec)

    def processed_state(b: str, s: SlotAccounting) -> tuple[str, tuple[str, ...]]:
        """The trust state of a processed batch, before any delay is considered (shared by window and earlier batches)."""
        if version_conflict:
            return "version_mismatch", (f"filter {s.filter_version} / parser {s.parser_version}",)
        ds = day_status[_utc_day(b)]
        if ds.status == "missing":
            return "day_file_missing", ()
        if ds.status == "invalid":
            return "day_file_invalid", ds.codes
        if b in dup_batches:
            return "duplicate_record_id", ()
        problems = reconcile_slot(s, records_by_batch.get(b, []), company_evidence=True)
        return ("count_mismatch", tuple(problems)) if problems else (RECONCILED, ())

    # 3. per-batch state
    views: dict[str, SlotView] = {}
    for b in expected:
        d, s = interval_of_batch[b], slots.get(b)
        reasons: tuple[str, ...] = ()
        avail = delayed_into = None
        if s is None:
            codes = rej_by_batch.get(b, [])
            state = "missing_manifest_slot" if "missing_manifest_row" in codes else "slot_rejected"
            reasons = tuple(sorted(set(codes)))
        elif s.state in INCOMPLETE_STATES:
            state, reasons = "non_final_slot", (s.state,)
        elif s.state in ABSENT_OR_FAILED_STATES:
            state, reasons = ABSENT, (s.state,)
        else:
            avail = s.available_at_utc
            state, reasons = processed_state(b, s)
            if state == RECONCILED and avail > cutoffs[d]:
                state, delayed_into = DELAYED, locate(avail)
        derived = not_applicable()
        if state in (RECONCILED, DELAYED):
            src = adaptation.sources.get(b)
            derived = assess_near_empty(b, src.stage_counts["rows_english_valid"] if src and src.stage_counts else None, baseline,
                                        inputs.near_empty_params, baseline_declared_from=inputs.baseline_batches_from)
        views[b] = SlotView(b, d, state, avail, delayed_into, len(records_by_batch.get(b, [])) if state in (RECONCILED, DELAYED) else 0,
                            s.rows_captured if s else None, dict(s.theme_rows) if s and s.theme_rows else None,
                            s.near_empty if s else None, reasons, derived.state.value, derived.reason.value,
                            compare_flags(s.near_empty if s else None, derived.state).value)

    # 3b. earlier nominal batches whose verified availability is inside the window: the same trust rules as any batch
    arrivals: list[EarlierArrival] = []
    placed: dict[date, list[CandidateRecord]] = defaultdict(list)
    held_back = beyond = 0
    inflow: dict[date, list[str]] = defaultdict(list)
    earlier_reconciled: Counter[date] = Counter()
    for b in sorted(inflow_slots):
        s, target = inflow_slots[b], receiving[b]
        state, reasons = processed_state(b, s)
        recs_b = records_by_batch.get(b, [])
        if state == RECONCILED:
            arrivals.append(EarlierArrival(b, parse_batch_stamp(b), s.available_at_utc, target, "late_arrival_reconciled", len(recs_b), ()))
            placed[target].extend(recs_b)
            earlier_reconciled[target] += 1
        else:
            arrival = EarlierArrival(b, parse_batch_stamp(b), s.available_at_utc, target, state, 0, reasons)
            arrivals.append(arrival)
            early_unresolved_by_interval[target].append(arrival)
            held_back += len(recs_b)
            issues.append(WindowIssue("window", "earlier_batch_unresolved",
                                      f"earlier batch {b} (nominal {arrival.nominal_utc.isoformat()}, verified availability "
                                      f"{s.available_at_utc.isoformat()}) is {state}: receiving interval {target} is incomplete", batch_ts=b))
    arrivals += [a for lst in early_unresolved_by_interval.values() for a in lst if a.state == "earlier_batch_unresolved"] + early_unresolved_window
    for b, v in views.items():
        recs = records_by_batch.get(b, [])
        if v.state in (RECONCILED, DELAYED):
            for rec in recs:
                target = locate(rec.available_at_utc)
                if target is None:
                    beyond += 1
                else:
                    placed[target].append(rec)
        else:
            held_back += len(recs)
            if v.available_at_utc is not None and v.state in PROBLEM_STATES:
                target = locate(v.available_at_utc)
                if target is not None:
                    inflow[target].append(b)

    # 5. intervals
    policy_blocked = bool(PolicyState.from_mapping(POLICY_STATUS).unresolved())     # a required policy is unresolved: no result may be used
    out_intervals: list[IntervalAccounting] = []
    for d in days[1:]:
        own = [views[b] for b in grids[d]]
        counts = Counter(v.state for v in own)
        recs = sorted(placed[d], key=_seq)
        carried = sum(1 for r in recs if interval_of_batch.get(r.batch_ts) != d)
        delayed_rows = {t: sum((v.theme_rows or {}).get(t, 0) for v in own if v.state == DELAYED) for t in schema.THEMES}
        early_d = [a.batch_ts for a in early_unresolved_by_interval[d]] + [a.batch_ts for a in early_unresolved_window]
        inflow_d = tuple(sorted(set(inflow[d]) | set(early_d)) + (["earlier_batches_not_examined"] if earlier_not_examined else []))
        n_early = earlier_reconciled[d]
        # the SHARED contract (completeness.py): the same state transitions the aggregator uses
        real = tuple(sorted(set(inflow[d]) | set(early_d)))
        evid = [_slot_evidence(v) for v in own]
        cov = coverage_block(evid, inputs.coverage_thresholds, expected_n=len(grids[d]))
        # coverage can decide usability only through an APPLIED policy status; today it is selected-provisional-not-applied, so it is undecided
        rule = coverage_rule_decision(cov, inputs.coverage_thresholds, POLICY_STATUS["source_coverage_threshold"])
        a = assess_interval(evid, IntervalEarlier(real, earlier_not_examined, n_early), coverage_rule_met=rule)
        status = _LEGACY_STATUS[a.source]
        why = [f"{counts[s]} slot(s) {s}" for s in PROBLEM_STATES if counts[s]] + list(a.reasons)
        basis: dict[str, str] = {}
        evidence: dict[str, ThemeEvidenceRecord] = {}
        for t in schema.THEMES:
            ev, ev_reasons = theme_evidence(a, sum(1 for r in recs if r.theme_flags[t]), delayed_rows[t])
            ra, rr = result_availability(a, ev, policy_blocked=policy_blocked, scoring_performed=False)
            evidence[t] = ThemeEvidenceRecord(ev.value, ev_reasons, ra.value, rr)
            basis[t] = _basis(a, ev)
        out_intervals.append(IntervalAccounting(
            d, cutoffs[d], status, len(own), {s: counts[s] for s in SLOT_STATES if counts[s]}, tuple(recs),
            {t: sum(1 for r in recs if r.theme_flags[t]) for t in schema.THEMES}, carried, counts[DELAYED], delayed_rows,
            sum(1 for v in own if v.state in (RECONCILED, DELAYED) and v.near_empty is True), inflow_d, basis, tuple(why), n_early,
            a, evidence, cov, dict(derived_counts([NearEmpty(v.derived_near_empty) for v in own]))))

    accepted = [r for res in results.values() for r in res.records]
    url = _repeats(accepted, lambda r: r.url_canonical)
    th = _repeats(accepted, lambda r: r.filter_title_hash)
    return WindowReport(
        days, inputs.filter_version, tuple(out_intervals), tuple(views[b] for b in expected),
        tuple(day_status[k] for k in sorted(day_status)), tuple(sorted(issues, key=WindowIssue.sort_key)),
        RepeatedContent(url[0], url[1], url[2], th[0], th[1], th[2]), outside, out_of_window, beyond, held_back,
        len(invalid_ts_lines), inputs.early_closes, inputs.market_holidays, inputs.min_chars, observed_versions, input_fp,
        _fingerprint(sorted(_record_line(r) for r in accepted)), inputs.earlier_batches_from,
        tuple(sorted(arrivals, key=lambda a: (a.batch_ts, a.state))), len(lb_rows), early_final_unavailable, early_outside,
        baseline_batches_from=inputs.baseline_batches_from, coverage_thresholds=inputs.coverage_thresholds,
        near_empty_params=inputs.near_empty_params, n_baseline_rows=n_baseline_rows)
