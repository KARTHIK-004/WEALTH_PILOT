"""Adapter A (S2.5): GDELT manifest rows -> ``SlotAccounting``. Pure and offline: no database, file or network access.

The caller reads the manifest (``slot`` rows and ``slot_series_count`` rows, as plain mappings: ``dict(sqlite_row)``) and passes
them in. Nothing is defaulted and nothing is repaired: every problem becomes a ``Rejection`` that names the batch, a stable code
and the reason, and a rejected batch yields **no** slot (the aggregator then reports it as missing, never as covered).

Contract, from the real manifest (``manifest_schema.sql``, ``engine.process_body``, ``manifest.mark_parsed``):

- The identifier is the canonical nominal ``batch_ts`` (``slot`` primary key). A duplicate ``batch_ts`` is ambiguous: every row
  carrying it is rejected.
- The state is the manifest's own ``slot_state`` (not re-derived). Only ``processed`` (committed) is final-and-counted; a
  non-final state becomes a non-final ``SlotAccounting`` (the aggregator then marks the interval incomplete).
- ``slot_series_count`` rows are selected by ``(batch_ts, filter_version, series)``. The caller names the ``filter_version`` and a
  processed slot must carry exactly that version, and exactly one row for each of ``EQUITY_US``, ``RATES_US``, ``GOLD``. Rows of
  another version are never mixed in; they are only reported.
- Stage counts are kept apart and are never compared as if equal. Only relations that hold by construction are checked, as
  inequalities between nested sets: ``captured <= english_valid``, ``company_item <= captured``,
  ``audit_sample + captured <= english_valid``, ``dup_same_batch <= english_valid``, the disjoint rejected classes plus
  ``english_valid <= physical``, and ``us_relevant <= rows`` within one series. Equality between ``english_valid``,
  ``captured``, duplicate counts or series rows is never required.
- Reconciling a slot with article records is the job of ``slots.reconcile_slot``, not of this adapter.

``SlotSource`` keeps the stage counts and versions of each accepted slot as provenance.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from wealthpilot.data.gdelt.errors import GdeltToolError, InvalidTimestampError
from wealthpilot.data.gdelt.filters import SERIES
from wealthpilot.data.gdelt.manifest import slot_state
from wealthpilot.data.gdelt.sentiment.slots import PROCESSED, SentimentSlotError, SlotAccounting, slot_from_manifest
from wealthpilot.data.gdelt.timeutil import parse_batch_stamp

STATE_FIELDS = ("batch_ts", "existence", "fetch_status", "parse_status", "commit_status")
STAGE_COUNT_FIELDS = ("rows_physical", "rows_malformed", "rows_date_mismatch", "rows_translated", "rows_non_web",
                      "rows_english_valid", "rows_captured", "rows_company_item", "rows_dup_same_batch", "rows_audit_sample")
PROCESSED_FIELDS = ("availability_status", "available_at_utc", "near_empty_flag", "filter_version", "parser_version",
                    *STAGE_COUNT_FIELDS)
SERIES_FIELDS = ("batch_ts", "filter_version", "series", "rows", "rows_us_relevant")
_MAX_SHOWN = 5


class ManifestAdapterError(GdeltToolError):
    """A wrong call (not data): wrong argument types. Data problems are reported as rejections instead."""

    code = "sentiment_manifest_adapter_error"


@dataclass(frozen=True)
class Rejection:
    """Why a batch, a series row, a file or a record was not accepted. ``code`` is stable; ``detail`` is for people."""

    batch_ts: str | None
    code: str
    detail: str
    line: int | None = None
    record_id: str | None = None

    def sort_key(self) -> tuple[Any, ...]:
        return (self.line or 0, self.batch_ts or "", self.record_id or "", self.code, self.detail)


@dataclass(frozen=True)
class SlotSource:
    """Provenance of one accepted slot: the manifest facts it was built from (nothing derived)."""

    batch_ts: str
    state: str
    filter_version: str | None
    parser_version: str | None
    stage_counts: Mapping[str, int] | None
    series_us_relevant: Mapping[str, int] | None
    availability_flags: str | None
    late_flag: int | None
    series_versions_seen: tuple[str, ...]


@dataclass(frozen=True)
class ManifestAdaptation:
    slots: tuple[SlotAccounting, ...]                 # accepted slots, sorted by batch_ts
    sources: Mapping[str, SlotSource]                 # provenance of the accepted slots
    rejections: tuple[Rejection, ...]                 # sorted; empty means every row was accepted

    @property
    def ok(self) -> bool:
        return not self.rejections

    def by_batch(self) -> dict[str, SlotAccounting]:
        return {s.batch_ts: s for s in self.slots}

    def require_ok(self) -> "ManifestAdaptation":
        if self.rejections:
            shown = "; ".join(f"{r.batch_ts}: {r.code}" for r in self.rejections[:_MAX_SHOWN])
            raise ManifestAdapterError(f"{len(self.rejections)} manifest rejection(s): {shown}")
        return self


def _count(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _rows(value: Any, name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(r, Mapping) for r in value):
        raise ManifestAdapterError(f"{name} must be a list or tuple of mappings (convert database rows with dict())")
    return list(value)


def _valid_stamp(value: Any) -> bool:
    try:
        parse_batch_stamp(value)
    except InvalidTimestampError:
        return False
    return True


def _check_processed(row: Mapping[str, Any], b: str, fv: str, versions: Mapping[str, Mapping[str, Mapping[str, Any]]]
                     ) -> tuple[list[Rejection], dict[str, int] | None, dict[str, int] | None]:
    out: list[Rejection] = []

    def reject(code: str, detail: str) -> None:
        out.append(Rejection(b, code, detail))

    missing = [f for f in PROCESSED_FIELDS if f not in row]
    if missing:
        reject("missing_field", f"a processed slot lacks {missing}")
        return out, None, None
    none_fields = [f for f in PROCESSED_FIELDS if row[f] is None and f != "near_empty_flag"]
    if none_fields:
        reject("missing_value", f"a processed slot has null {none_fields}")
        return out, None, None
    if row["existence"] != "present_verified" or row["parse_status"] != "parsed_validated":
        reject("inconsistent_state", f"committed but existence={row['existence']!r}, parse_status={row['parse_status']!r}")
    if row["filter_version"] != fv:
        reject("filter_version_differs", f"the slot is {row['filter_version']!r} but {fv!r} was requested: versions are never mixed")
    bad = [f for f in STAGE_COUNT_FIELDS if not _count(row[f])]
    if bad:
        reject("invalid_count", f"not non-negative integers: {bad}")
        return out, None, None
    c = {f: row[f] for f in STAGE_COUNT_FIELDS}
    nested = (
        (c["rows_captured"] <= c["rows_english_valid"], "rows_captured exceeds rows_english_valid"),
        (c["rows_company_item"] <= c["rows_captured"], "rows_company_item exceeds rows_captured"),
        (c["rows_audit_sample"] + c["rows_captured"] <= c["rows_english_valid"], "audit_sample + captured exceeds english_valid"),
        (c["rows_dup_same_batch"] <= c["rows_english_valid"], "rows_dup_same_batch exceeds rows_english_valid"),
        (c["rows_english_valid"] + c["rows_malformed"] + c["rows_date_mismatch"] + c["rows_translated"] + c["rows_non_web"]
         <= c["rows_physical"], "the disjoint line classes exceed rows_physical"),
    )
    for ok, text in nested:
        if not ok:
            reject("inconsistent_count", text)
    seen = versions.get(fv, {})
    if set(seen) != set(SERIES):
        others = sorted(v for v in versions if v != fv)
        reject("missing_series", f"series rows for filter_version {fv!r} are {sorted(seen)}, need exactly {list(SERIES)}"
                                 + (f" (rows exist only for other versions {others})" if others and not seen else ""))
        return out, c, None
    series_bad = [s for s in SERIES if not (_count(seen[s]["rows"]) and _count(seen[s]["rows_us_relevant"]))]
    if series_bad:
        reject("invalid_series_count", f"non-integer or negative counts for {series_bad}")
        return out, c, None
    over = [s for s in SERIES if seen[s]["rows_us_relevant"] > seen[s]["rows"]]
    if over:
        reject("inconsistent_series_count", f"rows_us_relevant exceeds rows for {over}")
    return out, c, {s: seen[s]["rows_us_relevant"] for s in SERIES}


def adapt_manifest(slot_rows: Sequence[Mapping[str, Any]], series_rows: Sequence[Mapping[str, Any]], *, filter_version: str,
                   expected_batches: Sequence[str] | None = None) -> ManifestAdaptation:
    """Adapt manifest ``slot`` and ``slot_series_count`` rows into ``SlotAccounting`` plus rejections.

    ``filter_version`` is required and explicit. ``expected_batches`` (the nominal grid the caller needs) makes a missing manifest
    row, or a row outside the grid, a rejection.
    """
    slot_rows, series_rows = _rows(slot_rows, "slot_rows"), _rows(series_rows, "series_rows")
    if not (isinstance(filter_version, str) and filter_version.strip()):
        raise ManifestAdapterError("filter_version is required")
    rejections: list[Rejection] = []

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in slot_rows:
        stamp = row.get("batch_ts")
        if not _valid_stamp(stamp):
            rejections.append(Rejection(stamp if isinstance(stamp, str) else None, "invalid_batch_ts",
                                        f"a slot row has no valid canonical batch_ts: {stamp!r}"))
            continue
        grouped[stamp].append(row)

    index: dict[str, dict[str, dict[str, Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(dict))
    ambiguous: set[tuple[str, str]] = set()
    for row in series_rows:
        missing = [f for f in SERIES_FIELDS if f not in row]
        b = row.get("batch_ts") if isinstance(row.get("batch_ts"), str) else None
        if missing:
            rejections.append(Rejection(b, "missing_field", f"a series row ({row.get('series')!r}) lacks {missing}"))
            continue
        if not _valid_stamp(row["batch_ts"]) or not isinstance(row["filter_version"], str) or not row["filter_version"].strip():
            rejections.append(Rejection(b, "invalid_series_row", f"a series row ({row['series']!r}) has an invalid batch_ts or filter_version"))
            continue
        if row["series"] not in SERIES:
            rejections.append(Rejection(b, "unknown_series", f"series {row['series']!r} is not one of {list(SERIES)}"))
            continue
        slot = index[row["batch_ts"]][row["filter_version"]]
        if row["series"] in slot:
            ambiguous.add((row["batch_ts"], row["filter_version"]))
            rejections.append(Rejection(b, "duplicate_series_row", f"{row['series']} appears twice for {row['filter_version']!r}"))
            continue
        slot[row["series"]] = row

    wanted = None
    if expected_batches is not None:
        if not isinstance(expected_batches, (list, tuple)) or not all(_valid_stamp(s) for s in expected_batches):
            raise ManifestAdapterError("expected_batches must be a list or tuple of canonical batch stamps")
        wanted = set(expected_batches)
        rejections += [Rejection(b, "missing_manifest_row", "no manifest slot row for an expected batch")
                       for b in sorted(wanted - set(grouped))]

    accepted: dict[str, SlotAccounting] = {}
    sources: dict[str, SlotSource] = {}
    for b in sorted(grouped):
        rows = grouped[b]
        if wanted is not None and b not in wanted:
            rejections.append(Rejection(b, "unexpected_batch", "the batch is outside the expected grid"))
            continue
        if len(rows) > 1:
            rejections.append(Rejection(b, "duplicate_batch_ts", f"{len(rows)} slot rows share this batch_ts: ambiguous, all rejected"))
            continue
        row = rows[0]
        missing = [f for f in STATE_FIELDS if f not in row or row[f] is None]
        if missing:
            rejections.append(Rejection(b, "missing_field", f"required state fields absent or null: {missing}"))
            continue
        state = slot_state(row)
        if state != PROCESSED:
            accepted[b] = SlotAccounting(b, state)
            sources[b] = SlotSource(b, state, None, None, None, None, None, None, tuple(sorted(index.get(b, {}))))
            continue
        problems, counts, us = _check_processed(row, b, filter_version, index.get(b, {}))
        if any((b, v) in ambiguous for v in index.get(b, {}) if v == filter_version):
            problems.append(Rejection(b, "ambiguous_series_rows", "duplicate series rows for the requested filter_version"))
        if not problems:
            series = {s: index[b][filter_version][s]["rows"] for s in SERIES}
            try:
                slot = slot_from_manifest(row, series)
            except SentimentSlotError as exc:
                problems.append(Rejection(b, "invalid_slot", str(exc)))
            else:
                accepted[b] = slot
                sources[b] = SlotSource(b, state, row["filter_version"], row["parser_version"], counts, us,
                                        row.get("availability_flags"), row.get("late_flag"), tuple(sorted(index[b])))
        rejections += problems

    accepted_batches = set(grouped)
    rejections += [Rejection(b, "series_rows_without_slot", "series rows exist but no valid slot row does")
                   for b in sorted(set(index) - accepted_batches)]
    return ManifestAdaptation(tuple(accepted[b] for b in sorted(accepted)), sources,
                              tuple(sorted(rejections, key=Rejection.sort_key)))
