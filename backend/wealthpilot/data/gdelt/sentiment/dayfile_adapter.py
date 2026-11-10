"""Adapter B (S2.5): processed GDELT day files -> candidate (UNSCORED) sentiment records. Pure: the caller supplies the file bytes.

Source format (``output.py``): a gzip TSV with a header equal to ``output.COLUMNS``, then ``captured`` rows only, written for the
UTC day of the nominal batch stamp. The header is validated before any row is read; a different header rejects the file and no row
is parsed or guessed.

A ``CandidateRecord`` is deliberately **not** an ``ArticleRecord``: it has no model, probabilities, label, ``story_id`` or
cross-batch duplicate status, because none of those exist yet. It keeps what a later phase needs, and keeps it apart:

- ``title_sha256_raw`` is the hash of the stored day-file title (``schema.title_sha256``); ``filter_title_hash`` is the filter's
  normalised-title hash, copied from the file unchanged. They are different keys and are never substituted for one another.
- ``text_status`` (``ok``, ``empty``, ``short``, ``malformed``) is explicit; an empty title is kept, not dropped. ``min_chars`` is
  an explicit argument (the filter specification's ``title_hash_min_chars``).
- ``same_batch_status`` is the engine's ``mech_dup`` value (``ORIGINAL``, ``DUP_SAME_BATCH``, ``SYNDICATED_SAME_BATCH``). No
  cross-batch status is invented and nothing is dropped because of it. ``url_canonical`` and ``word_count`` are kept only as the
  inputs a future, separately approved story pass would need.
- The page publication time is not carried. The four tone columns are carried only as raw strings (``tone_raw``) for the tone baseline.

Every record is checked against the manifest side: its batch must be a **processed** slot, its availability must equal the slot's
verified availability, and its filter and parser versions must equal the slot's. A row that fails any check is rejected with its
line number and record id; the other rows are still returned, but ``ok`` is false and only an ``ok`` result is to be trusted.
Output is sorted by ``(batch_ts, sequence)``, so it is deterministic.

``day_commit`` (optional) adds the integrity checks: committed status, day, versions, ``rows_kept`` and the SHA-256 of the bytes.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from wealthpilot.data.gdelt.errors import InvalidTimestampError
from wealthpilot.data.gdelt.output import COLUMNS
from wealthpilot.data.gdelt.sentiment import schema
from wealthpilot.data.gdelt.sentiment.manifest_adapter import ManifestAdapterError, Rejection
from wealthpilot.data.gdelt.sentiment.slots import PROCESSED, SlotAccounting
from wealthpilot.data.gdelt.timeutil import parse_batch_stamp

SAME_BATCH_STATUSES = ("ORIGINAL", "DUP_SAME_BATCH", "SYNDICATED_SAME_BATCH")
_MEMBER = {"equity_us": "member_equity_us", "rates_us": "member_rates_us", "gold": "member_gold"}
_ID = re.compile(r"^(\d{14})-(\d+)$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED = ("gkg_record_id", "batch_ts", "available_at_utc", "filter_version", "parser_version", "source_domain")
_COMMIT_FIELDS = ("utc_day", "status", "filter_version", "parser_version", "rows_kept", "file_sha256")


@dataclass(frozen=True)
class CandidateRecord:
    """One captured row, validated against its manifest slot. Unscored; carries no story identity or prediction."""

    article_id: str
    batch_ts: str
    available_at_utc: datetime
    source_domain: str
    title: str = field(repr=False)
    text_status: str
    title_sha256_raw: str
    filter_title_hash: str | None
    url_canonical: str = field(repr=False)
    word_count: str
    theme_flags: Mapping[str, bool]
    company_item: bool
    same_batch_status: str
    filter_version: str
    parser_version: str
    source_file: str
    source_line: int
    # The four GDELT tone columns exactly as written in the day file (tone, positive, negative, polarity), never parsed here: the local tone baseline
    # (``tone_baseline.py``) validates them. They are document-level lexicon values, not title sentiment. Empty strings mean the file had no value.
    tone_raw: tuple[str, str, str, str] = ("", "", "", "")

    @property
    def availability_status(self) -> str:
        """Always ``verified``: a candidate exists only when its availability equals its processed slot's."""
        return "verified"


@dataclass(frozen=True)
class DayFileResult:
    utc_day: str
    source_file: str
    records: tuple[CandidateRecord, ...]
    rejections: tuple[Rejection, ...]
    file_sha256: str
    rows_read: int                       # data rows parsed from the file (rejected ones included)
    integrity_checked: bool              # whether a day_commit record was supplied and checked

    @property
    def ok(self) -> bool:
        return not self.rejections


def find_duplicate_record_ids(results: Sequence[DayFileResult]) -> tuple[str, ...]:
    """Record ids that occur in more than one result (across files). Within a file they are rejected by the adapter itself."""
    counts = Counter(r.article_id for res in results for r in res.records)
    return tuple(sorted(i for i, n in counts.items() if n > 1))


def _file_reject(day: str, name: str, sha: str, code: str, detail: str, rows: int = 0, checked: bool = False) -> DayFileResult:
    return DayFileResult(day, name, (), (Rejection(None, code, detail),), sha, rows, checked)


def adapt_day_file(data: bytes, *, utc_day: str, slots: Mapping[str, SlotAccounting], min_chars: int, source_name: str,
                   day_commit: Mapping[str, Any] | None = None) -> DayFileResult:
    """Parse one day file (``filtered/<filter_version>/YYYY/YYYY-MM-DD.tsv.gz``) into candidate records plus rejections."""
    if not isinstance(data, (bytes, bytearray)):
        raise ManifestAdapterError("data must be the file's bytes")
    if not (isinstance(utc_day, str) and _DAY.match(utc_day)):
        raise ManifestAdapterError("utc_day must be YYYY-MM-DD")
    if not isinstance(slots, Mapping) or not all(isinstance(s, SlotAccounting) for s in slots.values()):
        raise ManifestAdapterError("slots must map batch_ts to SlotAccounting (use manifest_adapter.adapt_manifest)")
    if not isinstance(min_chars, int) or isinstance(min_chars, bool) or min_chars < 1:
        raise ManifestAdapterError("min_chars must be a positive integer (the filter specification's title_hash_min_chars)")
    if not (isinstance(source_name, str) and source_name.strip()):
        raise ManifestAdapterError("source_name is required (it is the provenance label of every record)")
    sha = hashlib.sha256(bytes(data)).hexdigest()
    checked = day_commit is not None
    commit_problems: list[Rejection] = []
    if checked:
        if not isinstance(day_commit, Mapping):
            raise ManifestAdapterError("day_commit must be a mapping")
        missing = [f for f in _COMMIT_FIELDS if f not in day_commit or day_commit[f] is None]
        if missing:
            return _file_reject(utc_day, source_name, sha, "day_commit_missing_field", f"day_commit lacks {missing}", checked=True)
        if day_commit["status"] != "committed":
            commit_problems.append(Rejection(None, "day_commit_not_committed", f"status is {day_commit['status']!r}"))
        if day_commit["utc_day"] != utc_day:
            commit_problems.append(Rejection(None, "day_commit_day_mismatch", f"commit is for {day_commit['utc_day']!r}"))
        if day_commit["file_sha256"] != sha:
            commit_problems.append(Rejection(None, "file_sha256_mismatch", "the bytes do not match the committed hash"))
        if commit_problems:
            return DayFileResult(utc_day, source_name, (), tuple(commit_problems), sha, 0, True)
    try:
        text = gzip.decompress(bytes(data)).decode("utf-8")
    except (OSError, EOFError, UnicodeDecodeError, ValueError) as exc:
        return _file_reject(utc_day, source_name, sha, "file_unreadable", f"{type(exc).__name__}: not a valid UTF-8 gzip file", checked=checked)
    reader = csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
    try:
        header = next(reader, None)
        if header is None or tuple(header) != COLUMNS:
            return _file_reject(utc_day, source_name, sha, "header_mismatch",
                                f"the header has {0 if header is None else len(header)} columns and is not output.COLUMNS ({len(COLUMNS)})",
                                checked=checked)
        parsed = [(reader.line_num, row) for row in reader if row]
    except csv.Error as exc:
        return _file_reject(utc_day, source_name, sha, "file_unreadable", f"csv error: {exc}", checked=checked)

    rejections: list[Rejection] = []
    if checked and day_commit["rows_kept"] != len(parsed):          # type: ignore[index]
        rejections.append(Rejection(None, "rows_kept_mismatch", f"day_commit says {day_commit['rows_kept']}, file has {len(parsed)}"))  # type: ignore[index]
    id_col = COLUMNS.index("gkg_record_id")
    ids = Counter(row[id_col] for _, row in parsed if len(row) == len(COLUMNS))
    records: list[CandidateRecord] = []
    for line, row in parsed:
        rid = row[id_col] if len(row) > id_col else None
        problems: list[tuple[str, str]] = []
        if len(row) != len(COLUMNS):
            rejections.append(Rejection(None, "wrong_column_count", f"{len(row)} columns, expected {len(COLUMNS)}", line, rid))
            continue
        d = dict(zip(COLUMNS, row))
        for name in _REQUIRED:
            if not d[name].strip():
                problems.append(("missing_required_field", name))
        if d["row_kind"] != "captured":
            problems.append(("row_kind_not_captured", f"row_kind {d['row_kind']!r}"))
        m = _ID.match(d["gkg_record_id"])
        if not m:
            problems.append(("invalid_record_id", "expected <14-digit batch>-<sequence>"))
        elif m.group(1) != d["batch_ts"]:
            problems.append(("record_id_batch_mismatch", "the record id prefix differs from the batch_ts column"))
        batch = d["batch_ts"]
        batch_ok = True
        try:
            parse_batch_stamp(batch)
            if f"{batch[:4]}-{batch[4:6]}-{batch[6:8]}" != utc_day:
                problems.append(("batch_not_in_file_day", f"batch {batch} is not on UTC day {utc_day}"))
        except InvalidTimestampError:
            batch_ok = False                    # the specific cause; the batch is then never looked up, so it is never "outside the window"
            problems.append(("invalid_batch_ts", "not a canonical batch stamp"))
        at = None
        if d["available_at_utc"].strip():
            if _TS.match(d["available_at_utc"]):
                at = datetime.strptime(d["available_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            else:
                problems.append(("invalid_available_at", "not YYYY-MM-DDTHH:MM:SSZ"))
        slot = slots.get(batch) if batch_ok else None
        if not batch_ok:
            pass
        elif slot is None:
            problems.append(("batch_not_in_manifest", "no manifest slot for this batch"))
        elif slot.state != PROCESSED:
            problems.append(("batch_slot_not_processed", f"the manifest slot is {slot.state}"))
        else:
            if at is not None and at != slot.available_at_utc:
                problems.append(("availability_differs_from_manifest", "available_at_utc differs from the slot's verified availability"))
            if (d["filter_version"], d["parser_version"]) != (slot.filter_version, slot.parser_version):
                problems.append(("version_differs_from_manifest", "filter or parser version differs from the slot's"))
        if checked and (d["filter_version"], d["parser_version"]) != (day_commit["filter_version"], day_commit["parser_version"]):  # type: ignore[index]
            problems.append(("version_differs_from_day_commit", "filter or parser version differs from the day commit"))
        flags = {t: d[col] for t, col in _MEMBER.items()}
        if any(v not in ("0", "1") for v in flags.values()) or d["company_item"] not in ("0", "1"):
            problems.append(("invalid_flag", "a member_* or company_item value is not 0 or 1"))
        if d["mech_dup"] not in SAME_BATCH_STATUSES:
            problems.append(("unknown_same_batch_status", f"mech_dup {d['mech_dup']!r}"))
        if d["title_hash"] and not _SHA.match(d["title_hash"]):
            problems.append(("invalid_title_hash", "the filter title hash is neither empty nor a SHA-256"))
        if ids[rid] > 1:
            problems.append(("duplicate_record_id", f"{ids[rid]} rows share this record id: ambiguous, all rejected"))
        if problems:
            rejections += [Rejection(batch if batch_ok else None, c, t, line, rid) for c, t in problems]
            continue
        title = d["page_title"]
        records.append(CandidateRecord(
            article_id=d["gkg_record_id"], batch_ts=batch, available_at_utc=at, source_domain=d["source_domain"], title=title,  # type: ignore[arg-type]
            text_status=schema.classify_title(title, min_chars=min_chars), title_sha256_raw=schema.title_sha256(title),
            filter_title_hash=d["title_hash"] or None, url_canonical=d["url_canonical"], word_count=d["word_count"],
            theme_flags={t: v == "1" for t, v in flags.items()}, company_item=d["company_item"] == "1",
            same_batch_status=d["mech_dup"], filter_version=d["filter_version"], parser_version=d["parser_version"],
            source_file=source_name, source_line=line,
            tone_raw=(d["tone"], d["positive"], d["negative"], d["polarity"])))
    records.sort(key=lambda r: (r.batch_ts, int(r.article_id.split("-", 1)[1])))
    return DayFileResult(utc_day, source_name, tuple(records), tuple(sorted(rejections, key=Rejection.sort_key)), sha, len(parsed), checked)
