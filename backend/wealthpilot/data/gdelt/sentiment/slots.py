"""Source-slot accounting for the sentiment aggregator (S2.3): what one batch of the real pipeline reports, and how that is
reconciled with the article records supplied for it. Pure and offline: no database, no network, no clock.

**What the real counts mean** (``engine.py`` ``process_body``, ``manifest.py`` ``mark_parsed``):

- ``rows_captured`` (manifest ``slot.rows_captured``): the rows of one batch that were *kept* in its shard. It includes
  same-batch duplicates and company items, and excludes every row that was rejected or not captured.
- per-series member counts (manifest ``slot_series_count.rows``, series ``EQUITY_US`` / ``RATES_US`` / ``GOLD``): the rows of
  the batch that are members of **that one series**, counted before any dedup. A row can be a member of several series, so the
  three counts neither add up to ``rows_captured`` nor equal it. They map to the sentiment themes ``equity_us`` / ``rates_us`` /
  ``gold`` (``filters.SERIES`` lower-cased).
- ``rows_english_valid``, ``rows_physical`` and the rejected-row counts belong to earlier processing stages. They are NOT
  comparable with the number of article records, and nothing here compares against them.

**The contract (C1).** For a processed batch, the article records supplied for it must satisfy, exactly:

1. ``len(records) == rows_captured``;
2. for each theme, ``count(records with theme_flags[theme]) == theme_rows[theme]``;
3. every record has verified availability equal to the batch's ``available_at_utc`` (one availability per batch).

For a batch that is not processed (absent, failed, invalid) no record may be supplied. Records therefore include duplicates and
invalid-text rows: the counts are taken before dedup. Any difference is reported with the batch stamp and both numbers; it is
never repaired.

A batch in a state that is not final (``unverified``, ``verified_available``, ``in_progress``, ``parsed_validated``) is
incomplete accounting: the aggregator marks the interval unavailable instead of guessing.

Nothing here approves a threshold, a dedup policy or a calendar.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from wealthpilot.data.gdelt.errors import GdeltToolError, InvalidTimestampError
from wealthpilot.data.gdelt.filters import SERIES
from wealthpilot.data.gdelt.manifest import slot_state
from wealthpilot.data.gdelt.sentiment import schema
from wealthpilot.data.gdelt.timeutil import SLOT, parse_batch_stamp, require_utc

PROCESSED = "processed"
ABSENT_OR_FAILED_STATES = ("confirmed_absent", "absent_inconclusive", "request_failed", "inaccessible", "downloaded_invalid")
INCOMPLETE_STATES = ("unverified", "verified_available", "in_progress", "parsed_validated")
ALL_STATES = (PROCESSED, *ABSENT_OR_FAILED_STATES, *INCOMPLETE_STATES)
SERIES_TO_THEME = {s: s.lower() for s in SERIES}
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class SentimentSlotError(GdeltToolError):
    code = "sentiment_slot_error"


@dataclass(frozen=True)
class SlotAccounting:
    """What the pipeline reports for one batch slot. Counts are present only for a processed slot, and then all of them are."""

    batch_ts: str
    state: str                                   # the manifest's ``slot_state`` vocabulary (``ALL_STATES``)
    available_at_utc: datetime | None = None     # verified availability (existing rule); processed slots only
    rows_captured: int | None = None
    theme_rows: Mapping[str, int] | None = None  # keys exactly ``schema.THEMES``
    near_empty: bool | None = None               # None: no causal baseline (existing meaning)
    filter_version: str | None = None
    parser_version: str | None = None
    rows_company_item: int | None = None         # captured rows flagged as company items (None: not supplied)

    def __post_init__(self) -> None:
        try:
            nominal = parse_batch_stamp(self.batch_ts)
        except InvalidTimestampError as exc:
            raise SentimentSlotError(f"batch_ts: {exc}") from exc
        if self.state not in ALL_STATES:
            raise SentimentSlotError(f"state {self.state!r} is not one of {ALL_STATES}")
        if self.state != PROCESSED:
            if any(v is not None for v in (self.available_at_utc, self.rows_captured, self.theme_rows, self.near_empty,
                                           self.filter_version, self.parser_version, self.rows_company_item)):
                raise SentimentSlotError(f"{self.batch_ts}: a {self.state} slot carries no counts, availability or versions")
            return
        try:
            at = require_utc(self.available_at_utc, "available_at_utc") if self.available_at_utc is not None else None
        except InvalidTimestampError as exc:
            raise SentimentSlotError(f"{self.batch_ts}: available_at_utc: {exc}") from exc
        if at is None or at.microsecond or at < nominal + SLOT:
            raise SentimentSlotError(f"{self.batch_ts}: a processed slot needs a whole-second available_at_utc of at least the "
                                     "batch time plus one slot (the verified availability rule)")
        if not _count(self.rows_captured):
            raise SentimentSlotError(f"{self.batch_ts}: rows_captured must be a non-negative integer")
        if not isinstance(self.theme_rows, Mapping) or set(self.theme_rows) != set(schema.THEMES) \
                or not all(_count(v) for v in self.theme_rows.values()):
            raise SentimentSlotError(f"{self.batch_ts}: theme_rows must hold a non-negative integer for exactly {schema.THEMES}")
        if self.near_empty is not None and not isinstance(self.near_empty, bool):
            raise SentimentSlotError(f"{self.batch_ts}: near_empty must be true, false or null")
        if self.rows_company_item is not None and not (_count(self.rows_company_item) and self.rows_company_item <= self.rows_captured):
            raise SentimentSlotError(f"{self.batch_ts}: rows_company_item must be a non-negative integer not above rows_captured")
        for name in ("filter_version", "parser_version"):
            if not (isinstance(getattr(self, name), str) and getattr(self, name).strip()):
                raise SentimentSlotError(f"{self.batch_ts}: {name} is required for a processed slot")

    @property
    def processed(self) -> bool:
        return self.state == PROCESSED


def _count(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def slot_from_manifest(row: Mapping[str, Any], series_rows: Mapping[str, int] | None) -> SlotAccounting:
    """Map one manifest ``slot`` row and its ``slot_series_count`` rows (series name -> member rows) to a ``SlotAccounting``.

    ``series_rows`` must hold exactly the filter's series (``EQUITY_US``, ``RATES_US``, ``GOLD``) for a processed slot. A
    missing, extra, malformed or inconsistent input raises ``SentimentSlotError``: nothing is defaulted. The state comes from the
    manifest's own ``slot_state`` (not re-derived here).
    """
    stamp = row["batch_ts"]
    state = slot_state(row)
    if state != PROCESSED:
        return SlotAccounting(stamp, state)
    if row["availability_status"] != "verified":
        raise SentimentSlotError(f"{stamp}: a processed slot must have verified availability, found {row['availability_status']!r}")
    raw_at = row["available_at_utc"]
    if not (isinstance(raw_at, str) and _TS.match(raw_at)):
        raise SentimentSlotError(f"{stamp}: available_at_utc must be YYYY-MM-DDTHH:MM:SSZ, found {raw_at!r}")
    at = datetime.strptime(raw_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if not isinstance(series_rows, Mapping) or set(series_rows) != set(SERIES):
        raise SentimentSlotError(f"{stamp}: series counts must be present for exactly {SERIES}, found "
                                 f"{sorted(series_rows) if isinstance(series_rows, Mapping) else series_rows!r}")
    near = row["near_empty_flag"]
    if near not in (None, 0, 1):
        raise SentimentSlotError(f"{stamp}: near_empty_flag must be null, 0 or 1, found {near!r}")
    return SlotAccounting(stamp, PROCESSED, at, row["rows_captured"], {SERIES_TO_THEME[s]: series_rows[s] for s in SERIES},
                          None if near is None else bool(near), row["filter_version"], row["parser_version"],
                          row.get("rows_company_item"))


def reconcile_slot(slot: SlotAccounting, records: Sequence[Any], *, company_evidence: bool = False) -> list[str]:
    """Every way the supplied records disagree with the slot (empty when they reconcile). Never repairs anything.

    ``records`` are the article records of this batch, whatever their theme, text or duplicate status.

    ``company_evidence=True`` also reconciles ``rows_company_item`` (the engine counts captured rows that are company items,
    ``engine.py`` ``n_company``) with the records' ``company_item`` flags. It is for records that carry the flag (day-file
    candidates). It is a keyword, not a default, because ``ArticleRecord`` has no company flag: a caller that asks for it with records
    or a slot that cannot supply the evidence gets an explicit problem, never a silent pass.
    """
    b, n = slot.batch_ts, len(records)
    if not slot.processed:
        return [f"{b}: slot is {slot.state} but {n} article record(s) were supplied"] if n else []
    out: list[str] = []
    assert slot.rows_captured is not None and slot.theme_rows is not None and slot.available_at_utc is not None
    if any(slot.theme_rows[t] > slot.rows_captured for t in schema.THEMES):
        out.append(f"{b}: a theme count exceeds rows_captured {slot.rows_captured}: the slot's own counts are inconsistent")
    if n != slot.rows_captured:
        out.append(f"{b}: rows_captured {slot.rows_captured} but {n} article record(s) supplied")
    for t in schema.THEMES:
        supplied = sum(1 for r in records if r.theme_flags[t])
        if supplied != slot.theme_rows[t]:
            out.append(f"{b}: {t} series rows {slot.theme_rows[t]} but {supplied} flagged record(s) supplied")
    if company_evidence:
        if slot.rows_company_item is None:
            out.append(f"{b}: the slot has no rows_company_item, so company items cannot be reconciled")
        elif any(not hasattr(r, "company_item") for r in records):
            out.append(f"{b}: the records carry no company_item flag, so rows_company_item cannot be reconciled")
        else:
            flagged = sum(1 for r in records if r.company_item)
            if flagged != slot.rows_company_item:
                out.append(f"{b}: rows_company_item {slot.rows_company_item} but {flagged} company-flagged record(s) supplied")
    for r in records:
        if r.availability_status != "verified" or r.available_at_utc is None:
            out.append(f"{b}: record {r.article_id} has no verified availability in a processed slot")
            break
        if require_utc(r.available_at_utc) != slot.available_at_utc:
            out.append(f"{b}: record {r.article_id} availability differs from the batch availability {slot.available_at_utc.isoformat()}")
            break
    return out
