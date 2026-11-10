"""Resumable SQLite manifest with an explicit state machine.

Every change goes through a method that checks the slot's current state first (``InvalidTransition``)
and then relies on the schema's CHECK constraints as a second line of defence. One writer only.

User-facing states (``slot_state``):

    unverified          expected slot, nothing observed yet
    verified_available  server confirmed the file exists (header 200); not downloaded yet
    in_progress         being downloaded or waiting for a retry
    confirmed_absent    two fresh, independent 404s (or the accepted June 2025 outage)
    absent_inconclusive 404s that could not be confirmed independently, or inconsistent answers
    request_failed      only transient failures within the retry budget
    inaccessible        other 4xx, or a redirect elsewhere
    downloaded_invalid  a body arrived but failed integrity or the availability rule (fail closed)
    parsed_validated    integrity, availability and parsing passed; rows are in a shard
    processed           its day was committed atomically
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import MANIFEST_SCHEMA_VERSION
from wealthpilot.data.gdelt.errors import InvalidTransition
from wealthpilot.data.gdelt.timeutil import iso_utc, parse_batch_stamp, utc_day

SCHEMA_PATH = Path(__file__).resolve().parent / "manifest_schema.sql"
ABSENT_KINDS = {"confirmed": "absent_confirmed", "inconclusive": "absent_inconclusive", "accepted": "absent_accepted"}


def slot_state(row: sqlite3.Row | dict[str, Any]) -> str:
    e, f, p, c = row["existence"], row["fetch_status"], row["parse_status"], row["commit_status"]
    if e in ("absent_confirmed", "absent_accepted"):
        return "confirmed_absent"
    if e == "absent_inconclusive":
        return "absent_inconclusive"
    if e in ("request_failed", "inaccessible"):
        return e
    if e == "present_invalid":
        return "downloaded_invalid"
    if c == "committed":
        return "processed"
    if p == "parsed_validated":
        return "parsed_validated"
    if f in ("in_progress", "retry_wait"):
        return "in_progress"
    if e == "available":
        return "verified_available"
    return "unverified"


TERMINAL_STATES = {"confirmed_absent", "absent_inconclusive", "request_failed", "inaccessible",
                   "downloaded_invalid", "parsed_validated", "processed"}


@dataclass(frozen=True)
class ParsedSlot:
    actual_bytes: int
    actual_md5: str
    actual_sha256: str
    checksum_basis: str
    zip_member_name: str
    zip_member_bytes: int
    zip_crc32: str
    http_etag: str | None
    http_last_modified_utc: str | None
    available_at_utc: str
    availability_flags: str
    late_flag: int
    counts: dict[str, int]
    series: dict[str, tuple[int, int]]       # series -> (rows, rows_us_relevant)
    shard_relpath: str
    shard_sha256: str
    parser_version: str
    filter_version: str


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not self.path.exists()
        self.db = sqlite3.connect(str(self.path), isolation_level=None)  # explicit transactions
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        if fresh:
            self.db.executescript("BEGIN;" + SCHEMA_PATH.read_text(encoding="utf-8") + "COMMIT;")
            self.db.execute("INSERT INTO schema_meta VALUES ('schema_version', ?)", (MANIFEST_SCHEMA_VERSION,))
        version = self.db.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        if version is None or version[0] != MANIFEST_SCHEMA_VERSION:
            raise InvalidTransition(f"manifest schema {version[0] if version else None} != {MANIFEST_SCHEMA_VERSION}")

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------------------------ helpers
    def _tx(self) -> "_Tx":
        return _Tx(self.db)

    def slot(self, stamp: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM slot WHERE batch_ts = ?", (stamp,)).fetchone()
        if row is None:
            raise InvalidTransition(f"unknown slot {stamp}")
        return row

    def state(self, stamp: str) -> str:
        return slot_state(self.slot(stamp))

    def _require(self, stamp: str, allowed: set[str], action: str) -> sqlite3.Row:
        row = self.slot(stamp)
        state = slot_state(row)
        if state not in allowed:
            raise InvalidTransition(f"{action} not allowed for {stamp} in state {state!r}")
        return row

    def _update(self, stamp: str, values: dict[str, Any]) -> None:
        cols = ", ".join(f"{k} = ?" for k in values)
        self.db.execute(f"UPDATE slot SET {cols} WHERE batch_ts = ?", (*values.values(), stamp))  # noqa: S608

    # ------------------------------------------------------------------ runs
    def start_run(self, run_id: str, mode: str, *, code_sha256: str, parser_version: str, filter_version: str,
                  filter_spec_sha256: str, audited_list_sha256: str, selection_sha256: str | None,
                  params: dict[str, Any], python_version: str, tzdata_version: str | None,
                  free_bytes_at_start: int | None, window: tuple[str, str] | None = None) -> None:
        self.db.execute(
            "INSERT INTO run (run_id, started_at_utc, mode, window_first_ts, window_last_ts, code_sha256, parser_version, "
            "filter_version, filter_spec_sha256, audited_list_sha256, selection_sha256, params_json, python_version, "
            "tzdata_version, free_bytes_at_start) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, iso_utc(datetime.now(timezone.utc)), mode, window[0] if window else None,
             window[1] if window else None, code_sha256, parser_version, filter_version, filter_spec_sha256,
             audited_list_sha256, selection_sha256, json.dumps(params, sort_keys=True, default=str), python_version,
             tzdata_version, free_bytes_at_start))

    def end_run(self, run_id: str, outcome: str, *, bytes_downloaded: int, requests_made: int) -> None:
        self.db.execute("UPDATE run SET ended_at_utc = ?, outcome = ?, bytes_downloaded = ?, requests_made = ? "
                        "WHERE run_id = ?", (iso_utc(datetime.now(timezone.utc)), outcome, bytes_downloaded,
                                             requests_made, run_id))

    # ------------------------------------------------------------------ slots
    def add_slot(self, stamp: str, url: str, *, list_status: str, selection: str = "window",
                 sample_round: int | None = None, sample_block: int | None = None, expected_bytes: int | None = None,
                 expected_md5: str | None = None, md5_source: str | None = None) -> bool:
        """Insert an expected slot; returns False if it already exists (idempotent on resume)."""
        nominal = parse_batch_stamp(stamp)
        cur = self.db.execute(
            "INSERT OR IGNORE INTO slot (batch_ts, utc_day, nominal_utc, url, selection, sample_round, sample_block, "
            "list_status, expected_bytes, expected_md5, md5_source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (stamp, utc_day(stamp), iso_utc(nominal), url, selection, sample_round, sample_block, list_status,
             expected_bytes, expected_md5, md5_source))
        return cur.rowcount == 1

    def record_attempt(self, run_id: str, stamp: str | None, kind: str, attempt_no: int, url: str, *,
                       outcome: str, http_status: int | None = None, headers: dict[str, str] | None = None,
                       bytes_received: int = 0, elapsed_ms: int | None = None, error_class: str | None = None,
                       backoff_before_s: float | None = None, location: str | None = None) -> None:
        h = headers or {}
        age = h.get("age")
        cl = h.get("content-length")
        self.db.execute(
            "INSERT INTO attempt (run_id, batch_ts, kind, attempt_no, url, started_at_utc, elapsed_ms, outcome, "
            "http_status, location, content_length, etag, last_modified_utc, server_date_utc, age_seconds, "
            "cache_control, bytes_received, error_class, backoff_before_s) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, stamp, kind, attempt_no, url, iso_utc(datetime.now(timezone.utc)), elapsed_ms, outcome,
             http_status, location, int(cl) if cl and cl.isdigit() else None, h.get("etag"), h.get("last-modified"),
             h.get("date"), int(age) if age and age.isdigit() else None, h.get("cache-control"), bytes_received,
             error_class, backoff_before_s))

    def mark_available(self, stamp: str, *, evidence: str, content_length: int | None, etag_md5: str | None) -> None:
        row = self._require(stamp, {"unverified"}, "mark_available")
        values: dict[str, Any] = {"existence": "available", "existence_evidence": evidence}
        if row["expected_bytes"] is None and content_length is not None:
            values["expected_bytes"] = content_length
        if row["expected_md5"] is None and etag_md5 is not None:
            values["expected_md5"], values["md5_source"] = etag_md5, "etag"
        self._update(stamp, values)

    def mark_absent(self, stamp: str, kind: str, *, evidence: str) -> None:
        if kind not in ABSENT_KINDS:
            raise InvalidTransition(f"unknown absence kind {kind!r}")
        self._require(stamp, {"unverified", "verified_available", "in_progress"}, "mark_absent")
        self._update(stamp, {"existence": ABSENT_KINDS[kind], "existence_evidence": evidence,
                             "fetch_status": "not_applicable", "validation_status": "not_applicable",
                             "availability_status": "not_applicable", "parse_status": "not_applicable",
                             "commit_status": "not_applicable"})

    def mark_unreachable(self, stamp: str, state: str, *, evidence: str) -> None:
        """``state`` is ``request_failed`` or ``inaccessible``. Failed is never absent."""
        if state not in ("request_failed", "inaccessible"):
            raise InvalidTransition(f"unknown failure state {state!r}")
        self._require(stamp, {"unverified", "verified_available", "in_progress"}, "mark_unreachable")
        self._update(stamp, {"existence": state, "existence_evidence": evidence, "fetch_status": "failed_permanent",
                             "validation_status": "not_applicable", "availability_status": "not_applicable",
                             "parse_status": "not_applicable", "commit_status": "not_applicable"})

    def begin_fetch(self, stamp: str, run_id: str) -> int:
        row = self._require(stamp, {"verified_available", "in_progress"}, "begin_fetch")
        if row["fetch_status"] not in ("pending", "retry_wait"):
            raise InvalidTransition(f"begin_fetch not allowed for {stamp} with fetch_status {row['fetch_status']!r}")
        attempts = row["attempts"] + 1
        self._update(stamp, {"fetch_status": "in_progress", "attempts": attempts, "run_id": run_id,
                             "next_attempt_after_utc": None})
        return attempts

    def retry_later(self, stamp: str, next_after: datetime | None) -> None:
        row = self._require(stamp, {"in_progress"}, "retry_later")
        if row["fetch_status"] != "in_progress":
            raise InvalidTransition(f"retry_later needs an in-progress fetch for {stamp}")
        self._update(stamp, {"fetch_status": "retry_wait", "next_attempt_after_utc": iso_utc(next_after)})

    def mark_invalid(self, stamp: str, validation_status: str, *, reason: str, actual_bytes: int | None = None,
                     actual_md5: str | None = None, availability_reason: str | None = None) -> None:
        row = self._require(stamp, {"in_progress"}, "mark_invalid")
        if row["fetch_status"] != "in_progress":
            raise InvalidTransition(f"mark_invalid needs an in-progress fetch for {stamp}")
        values: dict[str, Any] = {
            "existence": "present_invalid", "existence_evidence": reason, "fetch_status": "failed_permanent",
            "validation_status": validation_status, "parse_status": "not_applicable",
            "commit_status": "not_applicable", "actual_bytes": actual_bytes, "actual_md5": actual_md5}
        if validation_status == "availability_unverified":
            values["availability_status"], values["availability_reason"] = "unverified", availability_reason or reason
        else:
            values["availability_status"] = "not_applicable"
        self._update(stamp, values)

    def mark_parsed(self, stamp: str, parsed: ParsedSlot) -> None:
        """Integrity, availability and parsing passed and the shard is written: one transaction."""
        row = self._require(stamp, {"in_progress"}, "mark_parsed")
        if row["fetch_status"] != "in_progress":
            raise InvalidTransition(f"mark_parsed needs an in-progress fetch for {stamp}")
        c = parsed.counts
        with self._tx():
            self._update(stamp, {
                "existence": "present_verified", "fetch_status": "fetched", "validation_status": "passed",
                "availability_status": "verified", "availability_flags": parsed.availability_flags,
                "available_at_utc": parsed.available_at_utc, "late_flag": parsed.late_flag,
                "actual_bytes": parsed.actual_bytes, "actual_md5": parsed.actual_md5,
                "actual_sha256": parsed.actual_sha256, "checksum_basis": parsed.checksum_basis,
                "zip_member_name": parsed.zip_member_name, "zip_member_bytes": parsed.zip_member_bytes,
                "zip_crc32": parsed.zip_crc32, "http_etag": parsed.http_etag,
                "http_last_modified_utc": parsed.http_last_modified_utc,
                "rows_physical": c["physical_lines"], "rows_malformed": c["malformed"],
                "rows_date_mismatch": c["date_mismatch"], "rows_translated": c["translated"],
                "rows_non_web": c["non_web"], "rows_english_valid": c["english_valid"],
                "rows_captured": c["captured"], "rows_company_item": c["company_item"],
                "rows_dup_same_batch": c["dup_same_batch"], "rows_audit_sample": c["audit_sample"],
                "shard_relpath": parsed.shard_relpath, "shard_sha256": parsed.shard_sha256,
                "parse_status": "parsed_validated",
                "parser_version": parsed.parser_version, "filter_version": parsed.filter_version,
                "processed_at_utc": iso_utc(datetime.now(timezone.utc))})
            for series, (rows, us_rows) in parsed.series.items():
                self.db.execute("INSERT OR REPLACE INTO slot_series_count VALUES (?,?,?,?,?,NULL)",
                                (stamp, parsed.filter_version, series, rows, us_rows))

    def set_near_empty(self, stamp: str, *, flag: int | None, baseline: float | None, backlog: int | None) -> None:
        self._require(stamp, {"parsed_validated"}, "set_near_empty")
        self._update(stamp, {"near_empty_flag": flag, "near_empty_baseline": baseline, "backlog_flag": backlog})

    def commit_day(self, day: str, stamps: Sequence[str], record: dict[str, Any]) -> None:
        """Mark the day's parsed slots committed and write ``day_commit`` in one transaction.

        The day file is already durable (written, fsynced, renamed, re-hashed) before this is called.
        Shards are deleted by the caller afterwards; a failed deletion is swept at the next start.
        ``cleanup_status`` tracks temporary *archive* files only (B2-I): raw bodies stay in memory.
        """
        for s in stamps:
            self._require(s, {"parsed_validated"}, "commit_day")
        with self._tx():
            for s in stamps:
                self._update(s, {"commit_status": "committed"})
            cols = ", ".join(record)
            self.db.execute(f"INSERT INTO day_commit ({cols}) VALUES ({', '.join('?' * len(record))})",  # noqa: S608
                            tuple(record.values()))

    def set_cleanup(self, stamp: str, status: str) -> None:
        """Record what happened to a staged temporary archive (only used when staging to disk)."""
        if status not in ("nothing_written", "temp_present", "temp_deleted", "delete_failed"):
            raise InvalidTransition(f"unknown cleanup status {status!r}")
        self._update(stamp, {"cleanup_status": status})

    def reset_for_resume(self, stamp: str, reason: str) -> None:
        """Explicit resume path: an uncommitted slot whose shard is missing or corrupt goes back to
        'verified_available' so it is fetched again. Committed slots are never reset."""
        row = self.slot(stamp)
        if row["commit_status"] == "committed":
            raise InvalidTransition(f"{stamp} is committed; it is never reset")
        state = slot_state(row)
        if state not in ("in_progress", "parsed_validated"):
            raise InvalidTransition(f"reset_for_resume not allowed for {stamp} in state {state!r}")
        with self._tx():
            self._update(stamp, {
                "existence": "available", "existence_evidence": f"reset: {reason}", "fetch_status": "pending",
                "validation_status": "pending", "availability_status": "pending", "availability_reason": None,
                "availability_flags": None, "available_at_utc": None, "late_flag": None, "parse_status": "pending",
                "shard_relpath": None, "shard_sha256": None, "cleanup_status": "nothing_written",
                "near_empty_flag": None, "near_empty_baseline": None, "backlog_flag": None})
            self.db.execute("DELETE FROM slot_series_count WHERE batch_ts = ?", (stamp,))

    def interrupt_in_progress(self) -> list[str]:
        """At start-up: fetches left 'in_progress' by a crash become 'pending' again."""
        rows = self.db.execute("SELECT batch_ts FROM slot WHERE fetch_status = 'in_progress'").fetchall()
        for r in rows:
            self._update(r[0], {"fetch_status": "pending"})
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ queries
    def slots(self, where: str = "1=1", params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.db.execute(f"SELECT * FROM slot WHERE {where} ORDER BY batch_ts", tuple(params)).fetchall()  # noqa: S608

    def days(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT DISTINCT utc_day FROM slot ORDER BY utc_day")]

    def day_committed(self, day: str, filter_version: str, parser_version: str) -> bool:
        return self.db.execute("SELECT 1 FROM day_commit WHERE utc_day=? AND filter_version=? AND parser_version=?",
                               (day, filter_version, parser_version)).fetchone() is not None

    def state_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in self.slots():
            st = slot_state(row)
            out[st] = out.get(st, 0) + 1
        return dict(sorted(out.items()))

    def baseline_rows(self, stamp: str, days: int = 14) -> list[int]:
        """rows_english_valid of the same UTC slot on the previous ``days`` days (causal)."""
        nominal = parse_batch_stamp(stamp)
        out = []
        for d in range(1, days + 1):
            s = (nominal - timedelta(days=d)).strftime("%Y%m%d%H%M%S")
            r = self.db.execute("SELECT rows_english_valid, existence FROM slot WHERE batch_ts=?", (s,)).fetchone()
            if r is not None and r["existence"] == "present_verified" and r["rows_english_valid"] is not None:
                out.append(int(r["rows_english_valid"]))
        return out


class _Tx:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def __enter__(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.db.execute("ROLLBACK" if exc_type else "COMMIT")
