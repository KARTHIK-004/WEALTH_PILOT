"""Processing engine: one batch body -> validated shard; the sequential sample run; atomic day commits.

``process_body`` is offline and pure apart from writing the shard and the manifest. ``run_sample`` is
the only function that talks to a ``Transport``; it is reached from the CLI only after
``config.authorize`` passed, and the real HTTPS transport is itself locked in this build.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wealthpilot.data.gdelt import PARSER_VERSION
from wealthpilot.data.gdelt.availability import compute_availability, zip_member_time_utc
from wealthpilot.data.gdelt.cleanup import safe_delete, sweep_tmp
from wealthpilot.data.gdelt.config import Limits
from wealthpilot.data.gdelt.dedup import mark_same_batch
from wealthpilot.data.gdelt.errors import BudgetExceeded, GdeltToolError, IntegrityError, InvalidTransition
from wealthpilot.data.gdelt.events import EventLog
from wealthpilot.data.gdelt.existence import HeadObservation, classify
from wealthpilot.data.gdelt.filters import SERIES, Classifier, in_audit_sample
from wealthpilot.data.gdelt.guards import TransferBudget, check_free_disk, check_tmp_usage, stop_requested
from wealthpilot.data.gdelt.integrity import check_body, md5_from_etag, open_member
from wealthpilot.data.gdelt.manifest import TERMINAL_STATES, Manifest, ParsedSlot, slot_state
from wealthpilot.data.gdelt.output import COLUMNS, Layout, atomic_write, sha256_file, write_day, write_shard
from wealthpilot.data.gdelt.parser import RowCounts, iter_rows
from wealthpilot.data.gdelt.sample import SampleSlot
from wealthpilot.data.gdelt.timeutil import iso_utc, utc_day
from wealthpilot.data.gdelt.transport import HttpResponse, Transport, TransportError, archive_url

# PROPOSED near-empty / backlog policy (B2-H 5.5); inputs, not approved settings
NEAR_EMPTY_RATIO, BACKLOG_RATIO, MIN_BASELINE_OBS = 0.10, 3.0, 7


@dataclass
class RunContext:
    run_id: str
    layout: Layout
    manifest: Manifest
    classifier: Classifier
    limits: Limits
    budget: TransferBudget
    events: EventLog
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))
    sleep: Callable[[float], None] = field(default=lambda s: None)
    disk_usage: Callable[[str], object] | None = None
    keep_raw: bool = False
    sample_cutoff: datetime | None = None   # pre-registered drop rule for the review sample


@dataclass(frozen=True)
class BodyOutcome:
    status: str                  # "parsed" or "availability_unverified"
    reason: str | None = None


def _tf(flag: bool) -> str:
    return "1" if flag else "0"


def process_body(ctx: RunContext, stamp: str, body: bytes, headers: dict[str, str]) -> BodyOutcome:
    """Validate and parse one downloaded archive; write its shard; record it. Raises ``IntegrityError``."""
    row = ctx.manifest.slot(stamp)
    cl = headers.get("content-length")
    content_length = int(cl) if cl and cl.isdigit() else None
    check = check_body(body, content_length=content_length, expected_bytes=row["expected_bytes"],
                       expected_md5=row["expected_md5"], md5_source=row["md5_source"])
    archive, info = open_member(body, stamp, max_uncompressed=ctx.limits.max_uncompressed_bytes,
                                max_ratio=ctx.limits.max_expansion_ratio)
    age = headers.get("age")
    avail = compute_availability(stamp, headers.get("last-modified"), headers.get("date"),
                                 age_seconds=int(age) if age and age.lstrip("-").isdigit() else None,
                                 zip_member_time=zip_member_time_utc(info.date_time))
    if not avail.verified:
        return BodyOutcome("availability_unverified", avail.reason)
    flags = list(avail.flags)
    if ctx.sample_cutoff is not None and avail.available_at and avail.available_at > ctx.sample_cutoff:
        flags.append("after_sample_cutoff")

    counts = RowCounts()
    spec = ctx.classifier.spec
    audit_cfg = spec.raw["audit_sample"]
    kept: list[tuple] = []
    audit: list[tuple] = []
    dedup_keys: list[tuple[str, int, str, str | None]] = []
    series = {s: [0, 0] for s in SERIES}
    n_company = 0
    available_at = iso_utc(avail.available_at)
    with archive.open(info) as stream:
        for r in iter_rows(stream, stamp, counts, max_line_bytes=ctx.limits.max_line_bytes,
                           max_uncompressed=ctx.limits.max_uncompressed_bytes):
            c = ctx.classifier.classify(r)
            dedup_keys.append((r.record_id, r.seq, c.url_canonical, c.title_hash))
            for s in SERIES:
                if c.members[s]:
                    series[s][0] += 1
                    series[s][1] += int(c.us_relevant)
            n_company += int(c.company_item and c.captured)
            kind = "captured" if c.captured else (
                "audit" if in_audit_sample(r.record_id, audit_cfg["seed"], int(audit_cfg["rate_denominator"])) else None)
            if kind is None:
                continue
            values = [kind, r.record_id, stamp, available_at, r.source_domain, r.document_url, c.url_canonical,
                      r.title, c.title_hash, r.page_pub_ts, *c.tone,
                      ";".join(f"{t}:{n}" for t, n in c.candidate_mentions), ";".join(c.econ_themes),
                      ";".join(c.country_codes), _tf(c.us_location), _tf(c.us_relevant), ";".join(c.us_market_orgs),
                      ";".join(c.title_hits), _tf(c.company_item), ";".join(c.flag_themes),
                      *(_tf(c.members[s]) for s in SERIES), *(_tf(c.s1[s]) for s in SERIES),
                      *(_tf(c.s2[s]) for s in SERIES), None, _tf(c.near_miss_cue), spec.version, PARSER_VERSION]
            (kept if kind == "captured" else audit).append(values)
    # the member was read to its end: CRC-32 confirmed. Only now is anything kept.
    marks = mark_same_batch(dedup_keys)
    mech_index = COLUMNS.index("mech_dup")
    for values in kept + audit:
        values[mech_index] = marks[values[1]]
    rows = sorted(kept + audit, key=lambda v: (v[0] != "captured", int(v[1].split("-", 1)[1])))
    day = utc_day(stamp)
    shard = ctx.layout.shard_path(day, stamp)
    shard_sha = write_shard(shard, rows)
    if ctx.keep_raw:
        atomic_write(ctx.layout.raw_keep / f"{stamp}.gkg.csv.zip", body)
    cdict = {"physical_lines": counts.physical_lines, "malformed": counts.malformed,
             "date_mismatch": counts.date_mismatch, "translated": counts.translated, "non_web": counts.non_web,
             "english_valid": counts.english_valid, "captured": len(kept), "company_item": n_company,
             "dup_same_batch": sum(1 for v in marks.values() if v != "ORIGINAL"), "audit_sample": len(audit)}
    late = "late" in avail.flags
    ctx.manifest.mark_parsed(stamp, ParsedSlot(
        actual_bytes=check.size, actual_md5=check.md5, actual_sha256=check.sha256, checksum_basis=check.checksum_basis,
        zip_member_name=info.filename, zip_member_bytes=info.file_size, zip_crc32=f"{info.CRC:08x}",
        http_etag=headers.get("etag"), http_last_modified_utc=iso_utc(avail.server_file_time),
        available_at_utc=available_at or "", availability_flags=";".join(sorted(flags)), late_flag=int(late),
        counts=cdict, series={s: (v[0], v[1]) for s, v in series.items()},
        shard_relpath=str(shard.relative_to(ctx.layout.root)).replace("\\", "/"), shard_sha256=shard_sha,
        parser_version=PARSER_VERSION, filter_version=spec.version))
    ctx.events.emit("slot_parsed", batch_ts=stamp, rows=counts.english_valid, counts=cdict, flags=sorted(flags))
    return BodyOutcome("parsed")


# ---------------------------------------------------------------- resumption and day commits

def prepare_resume(ctx: RunContext) -> dict[str, list[str]]:
    """Reset interrupted fetches, verify uncommitted shards, sweep orphaned temporary files."""
    interrupted = ctx.manifest.interrupt_in_progress()
    reset: list[str] = []
    keep: set[Path] = set()
    for row in ctx.manifest.slots("parse_status = 'parsed_validated' AND commit_status = 'pending'"):
        shard = ctx.layout.root / row["shard_relpath"]
        if shard.exists() and sha256_file(shard) == row["shard_sha256"]:
            keep.add(shard)
        else:
            ctx.manifest.reset_for_resume(row["batch_ts"], "shard missing or corrupt")
            reset.append(row["batch_ts"])
    deleted, refused = sweep_tmp(ctx.layout.tmp, keep)
    ctx.events.emit("resume", counts={"interrupted": len(interrupted), "reset": len(reset), "swept": len(deleted),
                                      "refused": len(refused)})
    return {"interrupted": interrupted, "reset": reset, "swept": [str(p) for p in deleted],
            "refused": [str(p) for p in refused]}


def _near_empty(ctx: RunContext, stamp: str, rows: int) -> tuple[int | None, float | None, int | None]:
    base = ctx.manifest.baseline_rows(stamp)
    if len(base) < MIN_BASELINE_OBS:
        return None, None, None
    med = float(statistics.median(base))
    return int(rows < NEAR_EMPTY_RATIO * med), med, int(rows > BACKLOG_RATIO * med)


def commit_ready_days(ctx: RunContext, *, fail_before_replace_day: str | None = None) -> list[str]:
    """Commit every day whose slots are all in a final state. Returns the days committed."""
    fv = ctx.classifier.spec.version
    committed: list[str] = []
    for day in ctx.manifest.days():
        if ctx.manifest.day_committed(day, fv, PARSER_VERSION):
            continue
        rows = ctx.manifest.slots("utc_day = ?", (day,))
        states = [slot_state(r) for r in rows]
        if any(s not in TERMINAL_STATES for s in states):
            continue
        parsed = [r for r, s in zip(rows, states) if s == "parsed_validated"]
        shards = []
        for r in parsed:
            shard = ctx.layout.root / r["shard_relpath"]
            if not shard.exists() or sha256_file(shard) != r["shard_sha256"]:
                raise IntegrityError(f"shard for {r['batch_ts']} missing or corrupt; run resume", status="crc_failed")
            flag, base, backlog = _near_empty(ctx, r["batch_ts"], int(r["rows_english_valid"]))
            ctx.manifest.set_near_empty(r["batch_ts"], flag=flag, baseline=base, backlog=backlog)
            shards.append(shard)
        check_free_disk(ctx.layout.root, ctx.limits.min_free_bytes_runtime,
                        **({"disk_usage": ctx.disk_usage} if ctx.disk_usage else {}))
        files = write_day(ctx.layout, day, shards, fail_before_replace=(fail_before_replace_day == day))
        n_absent = sum(s in ("confirmed_absent", "absent_inconclusive") for s in states)
        record = {
            "utc_day": day, "filter_version": fv, "parser_version": PARSER_VERSION, "status": "committed",
            "slots_expected": len(rows), "slots_present": len(parsed), "slots_absent": n_absent,
            "slots_failed": len(rows) - len(parsed) - n_absent, "rows_kept": files.rows_kept,
            "file_relpath": str(files.file_path.relative_to(ctx.layout.root)).replace("\\", "/"),
            "file_bytes": files.file_bytes, "file_sha256": files.file_sha256,
            "audit_relpath": str(files.audit_path.relative_to(ctx.layout.root)).replace("\\", "/"),
            "audit_sha256": files.audit_sha256, "committed_at_utc": iso_utc(ctx.clock()), "run_id": ctx.run_id}
        ctx.manifest.commit_day(day, [r["batch_ts"] for r in parsed], record)
        for shard in shards:
            try:
                safe_delete(shard, [ctx.layout.tmp])
            except (OSError, GdeltToolError):
                ctx.events.emit("cleanup_failed", day=day)   # swept at the next start
        sweep_tmp(ctx.layout.tmp, keep={ctx.layout.root / r["shard_relpath"]
                                        for r in ctx.manifest.slots("parse_status='parsed_validated' AND "
                                                                    "commit_status='pending'")})
        committed.append(day)
        ctx.events.emit("day_committed", day=day, rows=files.rows_kept, sha256=files.file_sha256)
    return committed


# ---------------------------------------------------------------- the sequential sample run

@dataclass
class SampleRunResult:
    outcome: str
    planned_bytes: int | None = None
    substitutions: list[tuple[str, str]] = field(default_factory=list)
    stop_reason: str | None = None


def _headers_obs(ctx: RunContext, resp: HttpResponse | None, err: TransportError | None) -> HeadObservation:
    now = ctx.clock()
    if resp is None:
        return HeadObservation(now, None, err.kind if err else "connection_error")
    age = resp.header("age")
    return HeadObservation(now, resp.status, None, int(age) if age and age.isdigit() else 0,
                           resp.header("date") is not None)


def _transient(resp: HttpResponse | None, err: TransportError | None) -> bool:
    if err is not None:
        return err.kind in ("timeout", "connection_error", "tls_error", "body_incomplete")
    return resp is not None and resp.status in (429, 500, 502, 503, 504)


def _backoff(ctx: RunContext, attempt: int, resp: HttpResponse | None) -> float:
    seq = ctx.limits.backoff_seconds
    delay = seq[min(attempt - 1, len(seq) - 1)]
    ra = resp.header("retry-after") if resp is not None else None
    if ra and ra.isdigit():
        delay = max(delay, min(float(ra), ctx.limits.retry_after_cap_seconds))
    return delay


def _guards(ctx: RunContext) -> None:
    if stop_requested(ctx.layout.root):
        raise BudgetExceeded("STOP file present", limit="stop_file")
    check_free_disk(ctx.layout.root, ctx.limits.min_free_bytes_runtime,
                    **({"disk_usage": ctx.disk_usage} if ctx.disk_usage else {}))
    check_tmp_usage(ctx.layout.tmp, ctx.limits.max_tmp_bytes)


def _head_slot(ctx: RunContext, transport: Transport, stamp: str) -> str:
    url = ctx.manifest.slot(stamp)["url"]
    obs: list[HeadObservation] = []
    for n in range(1, ctx.limits.max_head_per_slot + 1):
        _guards(ctx)
        ctx.budget.reserve_request(0)
        resp, err = None, None
        try:
            resp = transport.head(url)
        except TransportError as exc:
            err = exc
        ctx.budget.record_bytes(0)
        ctx.manifest.record_attempt(ctx.run_id, stamp, "head", n, url,
                                    outcome="response" if resp else (err.kind if err else "connection_error"),
                                    http_status=resp.status if resp else None, headers=resp.headers if resp else None,
                                    elapsed_ms=resp.elapsed_ms if resp else None,
                                    error_class=err.kind if err else None)
        obs.append(_headers_obs(ctx, resp, err))
        decision = classify(obs, spacing=timedelta(seconds=ctx.limits.absence_check_spacing_seconds),
                            fresh_max_age=ctx.limits.fresh_max_age_seconds, max_checks=ctx.limits.max_head_per_slot)
        if decision.state == "available" and resp is not None:
            cl = resp.header("content-length")
            ctx.manifest.mark_available(stamp, evidence=decision.evidence,
                                        content_length=int(cl) if cl and cl.isdigit() else None,
                                        etag_md5=md5_from_etag(resp.header("etag")))
            return "available"
        if decision.state == "pending":
            ctx.sleep(_backoff(ctx, n, resp))
            continue
        # the sample never waits an hour to confirm absence: one fresh 404 makes the slot unusable now
        if decision.state in ("absent_pending", "absent_inconclusive"):
            ctx.manifest.mark_absent(stamp, "inconclusive", evidence=decision.evidence)
            return "absent"
        if decision.state == "absent_confirmed":
            ctx.manifest.mark_absent(stamp, "confirmed", evidence=decision.evidence)
            return "absent"
        ctx.manifest.mark_unreachable(stamp, decision.state, evidence=decision.evidence)
        return decision.state
    ctx.manifest.mark_unreachable(stamp, "request_failed", evidence="header checks exhausted")
    return "request_failed"


def _get_slot(ctx: RunContext, transport: Transport, stamp: str, *, final_pass: bool = False) -> str:
    integrity_failures = 0
    attempts_this_call = 0
    while True:
        _guards(ctx)
        row = ctx.manifest.slot(stamp)
        expected = int(row["expected_bytes"] or 0)
        ctx.budget.reserve_request(expected)
        attempt = ctx.manifest.begin_fetch(stamp, ctx.run_id)
        attempts_this_call += 1
        resp, err = None, None
        try:
            resp = transport.get(row["url"], min(ctx.limits.max_body_bytes, ctx.budget.remaining_bytes()))
        except TransportError as exc:
            err = exc
        received = resp.bytes_received if resp else (err.bytes_received if err else 0)
        ctx.manifest.record_attempt(ctx.run_id, stamp, "get", attempt, row["url"],
                                    outcome="response" if resp else (err.kind if err else "connection_error"),
                                    http_status=resp.status if resp else None, headers=resp.headers if resp else None,
                                    bytes_received=received, error_class=err.kind if err else None)
        ctx.budget.record_bytes(received)   # retries and partial transfers count
        if err is not None and err.kind == "aborted_by_budget":
            ctx.manifest.retry_later(stamp, None)
            raise BudgetExceeded(f"transfer aborted by budget: {err.detail}", limit="max_total_bytes")
        if err is not None and err.kind == "redirect_rejected":
            ctx.manifest.mark_unreachable(stamp, "inaccessible", evidence=err.detail)
            return "inaccessible"
        if _transient(resp, err):
            if final_pass or attempts_this_call >= ctx.limits.max_attempts:
                if final_pass:
                    ctx.manifest.mark_unreachable(stamp, "request_failed", evidence="final retry pass failed")
                    return "request_failed"
                ctx.manifest.retry_later(stamp, ctx.clock() + timedelta(seconds=ctx.limits.absence_check_spacing_seconds))
                return "retry_wait"
            ctx.manifest.retry_later(stamp, None)
            ctx.sleep(_backoff(ctx, attempts_this_call, resp))
            continue
        assert resp is not None
        if resp.status == 404:
            ctx.manifest.mark_absent(stamp, "inconclusive", evidence="404 on download after a 200 header check")
            return "absent"
        if resp.status != 200 or resp.body is None:
            ctx.manifest.mark_unreachable(stamp, "inaccessible", evidence=f"HTTP {resp.status}")
            return "inaccessible"
        try:
            outcome = process_body(ctx, stamp, resp.body, resp.headers)
        except IntegrityError as exc:
            integrity_failures += 1
            if integrity_failures <= ctx.limits.max_redownloads:
                ctx.manifest.retry_later(stamp, None)
                ctx.events.emit("integrity_retry", batch_ts=stamp, status=exc.status)
                continue
            ctx.manifest.mark_invalid(stamp, exc.status, reason=exc.reason, actual_bytes=len(resp.body))
            ctx.events.emit("slot_invalid", batch_ts=stamp, status=exc.status)
            return "invalid"
        if outcome.status == "availability_unverified":
            ctx.manifest.mark_invalid(stamp, "availability_unverified", reason="availability rule failed closed",
                                      actual_bytes=len(resp.body), availability_reason=outcome.reason)
            ctx.events.emit("slot_invalid", batch_ts=stamp, status="availability_unverified", reason=outcome.reason)
            return "invalid"
        return "parsed"


def run_sample(ctx: RunContext, transport: Transport, slots: list[SampleSlot], *, selection: str,
               substitute: Callable[[int, set[str]], str | None]) -> SampleRunResult:
    """Fetch and process pre-registered sample slots sequentially, within every guard."""
    result = SampleRunResult("completed")
    try:
        check_free_disk(ctx.layout.root, ctx.limits.min_free_bytes_preflight,
                        stage="preflight", **({"disk_usage": ctx.disk_usage} if ctx.disk_usage else {}))
        prepare_resume(ctx)
        queue = list(slots)
        unusable: set[str] = set()
        for s in queue:
            ctx.manifest.add_slot(s.stamp, archive_url(s.stamp), list_status="not_consulted",
                                  selection=selection, sample_round=s.round, sample_block=s.block)
        i = 0
        while i < len(queue):              # phase 1: header checks, with pre-registered substitution
            s = queue[i]
            i += 1
            if slot_state(ctx.manifest.slot(s.stamp)) != "unverified":
                continue
            if _head_slot(ctx, transport, s.stamp) != "available":
                unusable.add(s.stamp)
                sub = substitute(s.block, unusable)
                if sub is not None:
                    unusable.add(sub)   # never offer the same stamp twice
                    ctx.manifest.add_slot(sub, archive_url(sub), list_status="not_consulted", selection=selection,
                                          sample_round=s.round, sample_block=s.block)
                    queue.append(SampleSlot(sub, s.round, s.block))
                    result.substitutions.append((s.stamp, sub))
        planned = sum(int(r["expected_bytes"] or 0) for r in ctx.manifest.slots("existence = 'available'"))
        result.planned_bytes = planned
        ctx.events.emit("plan", planned_bytes=planned, limit=ctx.limits.max_planned_bytes)
        if planned > ctx.limits.max_planned_bytes:
            raise BudgetExceeded(f"planned {planned} B exceeds {ctx.limits.max_planned_bytes} B; nothing downloaded",
                                 limit="max_planned_bytes")
        for row in ctx.manifest.slots("existence = 'available' AND fetch_status IN ('pending', 'retry_wait')"):
            if row["next_attempt_after_utc"] and row["fetch_status"] == "retry_wait":
                continue
            _get_slot(ctx, transport, row["batch_ts"])
        now_iso = iso_utc(ctx.clock())
        for row in ctx.manifest.slots("fetch_status = 'retry_wait' AND next_attempt_after_utc <= ?", (now_iso,)):
            _get_slot(ctx, transport, row["batch_ts"], final_pass=True)
        commit_ready_days(ctx)
        if ctx.manifest.slots("fetch_status = 'retry_wait'"):
            result.outcome = "interrupted"
            result.stop_reason = "some slots wait for a final retry pass at least 65 minutes later"
    except BudgetExceeded as exc:
        result.outcome = {"max_requests": "stopped_request_budget", "min_free_bytes": "stopped_disk_space",
                          "stop_file": "stopped_by_user"}.get(exc.limit, "stopped_byte_budget")
        result.stop_reason = exc.reason
        ctx.events.emit("stopped", reason=exc.reason, limit=exc.limit)
    except InvalidTransition as exc:
        result.outcome, result.stop_reason = "stopped_error", exc.reason
        ctx.events.emit("stopped", reason=exc.reason, code=exc.code)
    return result
