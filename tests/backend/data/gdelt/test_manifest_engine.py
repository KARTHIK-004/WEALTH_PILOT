"""Manifest states and transitions; batch processing; atomic daily output; interruption and resumption."""

from __future__ import annotations

import gzip
import sqlite3
from datetime import datetime, timedelta

import pytest

from wealthpilot.data.gdelt.engine import commit_ready_days, prepare_resume
from wealthpilot.data.gdelt.errors import InvalidTransition
from wealthpilot.data.gdelt.manifest import Manifest, slot_state
from wealthpilot.data.gdelt.output import read_shard_rows, sha256_file
from wealthpilot.data.gdelt.transport import archive_url

STAMP = "20220301120000"
US = "3#Springfield, Illinois, United States#US#USIL#39.8#-89.6#1"


def batch(gkg, stamp=STAMP, n=6, **row_kw):
    rows = [gkg.row(stamp, 1, title="SYNTHETIC TEST ROW: Wall Street placeholder", url="https://example.com/dup"),
            gkg.row(stamp, 2, title="SYNTHETIC TEST ROW: Wall Street placeholder", url="https://example.com/dup"),
            gkg.row(stamp, 3, themes=["ECON_GOLDPRICE"], pubts="20991231235900"),     # future page time
            gkg.row(stamp, 4, themes=["ECON_CENTRALBANK"], locations=[US]),
            gkg.row(stamp, 5, collection="2")]
    rows += [gkg.row(stamp, i, **row_kw) for i in range(6, 6 + n)]
    return gkg.zip(stamp, rows)


# ---------------------------------------------------------------- schema and states

def test_manifest_opens_with_wal_foreign_keys_and_schema_version(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    assert m.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert m.db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert m.db.execute("SELECT value FROM schema_meta").fetchone()[0] == "gdelt_manifest_v1.1"
    m.close()
    Manifest(tmp_path / "m.sqlite").close()                       # reopening an existing manifest works


@pytest.mark.parametrize("sql", [
    "UPDATE slot SET existence='present_verified', fetch_status='fetched'",                       # validation pending
    "UPDATE slot SET existence='absent_confirmed'",                                               # fetch still pending
    "UPDATE slot SET existence='missing'",                                                        # unknown state
    "UPDATE slot SET commit_status='committed'",                                                  # not parsed
    "UPDATE slot SET md5_source='etag'",                                                          # no md5
    "UPDATE slot SET availability_status='verified'",                                             # no time
    "UPDATE slot SET availability_status='unverified'",                                           # no reason
    "UPDATE slot SET parse_status='parsed_validated'",                                            # not verified
    "UPDATE slot SET existence='present_invalid', fetch_status='failed_permanent', validation_status='passed'",
    "INSERT INTO slot (batch_ts, utc_day, nominal_utc, url, list_status) VALUES ('2022030112000x','d','n','u','listed')",
    "INSERT INTO slot_series_count VALUES ('20220301120000','v','EQUITY',1,1,NULL)",
    "INSERT INTO attempt (run_id, batch_ts, kind, attempt_no, url, started_at_utc, outcome) "
    "VALUES ('nope','20220301120000','get',1,'u','t','timeout')",                                 # FK
])
def test_schema_constraints_reject_invalid_states(tmp_path, sql):
    m = Manifest(tmp_path / "m.sqlite")
    m.add_slot(STAMP, archive_url(STAMP), list_status="listed")
    with pytest.raises(sqlite3.IntegrityError):
        m.db.execute(sql)


def test_state_machine_refuses_illegal_transitions(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.start_run("r", "dev_sample", code_sha256="x", parser_version="p", filter_version="f", filter_spec_sha256="s",
                audited_list_sha256="a", selection_sha256=None, params={}, python_version="3", tzdata_version=None,
                free_bytes_at_start=None)
    for s in ("20220301120000", "20220301121500", "20220301123000", "20220301124500"):
        assert m.add_slot(s, archive_url(s), list_status="listed")
    assert not m.add_slot("20220301120000", archive_url(STAMP), list_status="listed")   # idempotent
    assert m.state("20220301120000") == "unverified"
    with pytest.raises(InvalidTransition):
        m.begin_fetch("20220301120000", "r")                       # never header-confirmed
    m.mark_available("20220301120000", evidence="HTTP 200", content_length=10, etag_md5="a" * 32)
    assert m.state("20220301120000") == "verified_available"
    with pytest.raises(InvalidTransition):
        m.mark_available("20220301120000", evidence="again", content_length=10, etag_md5=None)
    m.mark_absent("20220301121500", "accepted", evidence="June 2025 outage accepted")
    with pytest.raises(InvalidTransition):
        m.begin_fetch("20220301121500", "r")
    m.mark_unreachable("20220301123000", "request_failed", evidence="timeouts")
    m.mark_unreachable("20220301124500", "inaccessible", evidence="HTTP 403")
    states = {s: m.state(s) for s in ("20220301121500", "20220301123000", "20220301124500")}
    assert states == {"20220301121500": "confirmed_absent", "20220301123000": "request_failed",
                      "20220301124500": "inaccessible"}                # failed is never absent
    m.begin_fetch("20220301120000", "r")
    m.mark_invalid("20220301120000", "availability_unverified", reason="fail closed",
                   availability_reason="last_modified_missing")
    row = m.slot("20220301120000")
    assert slot_state(row) == "downloaded_invalid" and row["availability_reason"] == "last_modified_missing"
    with pytest.raises(InvalidTransition):
        m.reset_for_resume("20220301120000", "no")                   # invalid slots are not silently retried
    with pytest.raises(InvalidTransition):
        m.mark_absent("20220301120000", "maybe", evidence="x")
    assert m.state_counts() == {"confirmed_absent": 1, "downloaded_invalid": 1, "inaccessible": 1,
                                "request_failed": 1}


# ---------------------------------------------------------------- processing

def test_processing_records_counts_flags_and_conservative_availability(make_ctx, gkg, ingest_fn):
    ctx = make_ctx()
    body = batch(gkg)
    out = ingest_fn(ctx, STAMP, body, gkg.headers(STAMP, body))
    assert out.status == "parsed"
    row = ctx.manifest.slot(STAMP)
    assert slot_state(row) == "parsed_validated"
    assert row["available_at_utc"] == "2022-03-01T12:15:00Z"         # nominal + 15; page time ignored
    assert (row["rows_english_valid"], row["rows_non_web"], row["rows_dup_same_batch"]) == (10, 1, 1)
    assert row["checksum_basis"] == "md5_etag" and row["actual_md5"] and row["zip_crc32"]
    series = {r["series"]: r["rows"] for r in ctx.manifest.db.execute("SELECT * FROM slot_series_count")}
    assert series == {"EQUITY_US": 2, "RATES_US": 1, "GOLD": 1}
    shard_rows = read_shard_rows(ctx.layout.root / row["shard_relpath"])
    kept = [r for r in shard_rows if r[0] == "captured"]
    assert {r[1] for r in kept} == {f"{STAMP}-1", f"{STAMP}-2", f"{STAMP}-3", f"{STAMP}-4"}
    dup = {r[1]: r[35] for r in kept}
    assert dup[f"{STAMP}-1"] == "ORIGINAL" and dup[f"{STAMP}-2"] == "DUP_SAME_BATCH"
    gold = next(r for r in kept if r[1] == f"{STAMP}-3")
    assert gold[3] == "2022-03-01T12:15:00Z" and gold[9] == "20991231235900"   # stored as a diagnostic only


def test_missing_server_timestamp_fails_closed(make_ctx, gkg, ingest_fn):
    ctx = make_ctx()
    body = batch(gkg)
    out = ingest_fn(ctx, STAMP, body, gkg.headers(STAMP, body, drop=("last-modified",)))
    assert out.status == "availability_unverified" and out.reason == "last_modified_missing"
    assert not list(ctx.layout.tmp.rglob("*.tsv.gz"))               # nothing kept for an unverifiable batch


# ---------------------------------------------------------------- day commit, atomicity, resume

def two_batches(make_ctx, gkg, ingest_fn, **ctx_kw):
    ctx = make_ctx(**ctx_kw)
    for stamp in ("20220301120000", "20220301121500"):
        body = batch(gkg, stamp)
        ingest_fn(ctx, stamp, body, gkg.headers(stamp, body))
    ctx.manifest.add_slot("20220301123000", archive_url("20220301123000"), list_status="unlisted")
    ctx.manifest.mark_absent("20220301123000", "confirmed", evidence="two fresh 404s")
    return ctx


def test_day_commit_is_atomic_deterministic_and_cleans_shards(make_ctx, gkg, ingest_fn, tmp_path):
    ctx = two_batches(make_ctx, gkg, ingest_fn)
    assert commit_ready_days(ctx) == ["2022-03-01"]
    rec = ctx.manifest.db.execute("SELECT * FROM day_commit").fetchone()
    assert (rec["slots_expected"], rec["slots_present"], rec["slots_absent"], rec["slots_failed"]) == (3, 2, 1, 0)
    day_file = ctx.layout.root / rec["file_relpath"]
    assert sha256_file(day_file) == rec["file_sha256"]
    lines = gzip.decompress(day_file.read_bytes()).decode().splitlines()
    assert lines[0].startswith("row_kind\tgkg_record_id") and len(lines) == 1 + rec["rows_kept"]
    assert not list(ctx.layout.tmp.rglob("*.tsv.gz"))
    assert all(ctx.manifest.state(s) == "processed" for s in ("20220301120000", "20220301121500"))
    assert commit_ready_days(ctx) == []                             # committed days are never rewritten
    other = two_batches(make_ctx, gkg, ingest_fn, root=tmp_path / "second")
    commit_ready_days(other)
    rec2 = other.manifest.db.execute("SELECT file_sha256 FROM day_commit").fetchone()
    assert rec2[0] == rec["file_sha256"]                             # byte-identical output


def test_day_with_an_unfinished_slot_is_not_committed(make_ctx, gkg, ingest_fn):
    ctx = two_batches(make_ctx, gkg, ingest_fn)
    ctx.manifest.add_slot("20220301124500", archive_url("20220301124500"), list_status="listed")
    assert commit_ready_days(ctx) == []


def test_crash_before_rename_then_resume_commits_once(make_ctx, gkg, ingest_fn):
    ctx = two_batches(make_ctx, gkg, ingest_fn)
    with pytest.raises(OSError, match="simulated crash"):
        commit_ready_days(ctx, fail_before_replace_day="2022-03-01")
    assert ctx.manifest.db.execute("SELECT COUNT(*) FROM day_commit").fetchone()[0] == 0
    assert len(list(ctx.layout.tmp.rglob("*.tsv.gz"))) == 2          # shards survive the crash
    report = prepare_resume(ctx)
    assert report["reset"] == []
    assert commit_ready_days(ctx) == ["2022-03-01"]
    assert ctx.manifest.db.execute("SELECT COUNT(*) FROM day_commit").fetchone()[0] == 1
    assert not list((ctx.layout.root / "filtered").rglob("*.partial"))


def test_resume_resets_interrupted_and_corrupt_slots_and_sweeps_orphans(make_ctx, gkg, ingest_fn):
    ctx = two_batches(make_ctx, gkg, ingest_fn)
    shard = ctx.layout.root / ctx.manifest.slot("20220301121500")["shard_relpath"]
    shard.write_bytes(b"corrupted")
    orphan = ctx.layout.tmp / "2022-03-01" / "20220301133000.tsv.gz"
    orphan.write_bytes(b"left over")
    ctx.manifest.add_slot("20220301124500", archive_url("20220301124500"), list_status="listed")
    ctx.manifest.mark_available("20220301124500", evidence="200", content_length=1, etag_md5=None)
    ctx.manifest.begin_fetch("20220301124500", ctx.run_id)          # crash while downloading
    report = prepare_resume(ctx)
    assert report["interrupted"] == ["20220301124500"] and report["reset"] == ["20220301121500"]
    assert ctx.manifest.state("20220301121500") == "verified_available"   # will be fetched again
    assert ctx.manifest.state("20220301120000") == "parsed_validated"      # its valid shard is reused
    assert not orphan.exists() and not shard.exists()


def test_near_empty_batch_is_flagged_from_a_causal_baseline(make_ctx, gkg, ingest_fn):
    from wealthpilot.data.gdelt.config import Limits
    # repetitive synthetic rows compress far beyond GDELT's ~3.1x; this test is not about the ratio guard
    ctx = make_ctx(limits=Limits(max_expansion_ratio=1000.0))
    base = datetime(2022, 3, 1, 12, 0)
    for d in range(14, 0, -1):                                       # same UTC slot, 14 previous days
        stamp = (base - timedelta(days=d)).strftime("%Y%m%d%H%M%S")
        body = gkg.zip(stamp, [gkg.row(stamp, i) for i in range(1, 101)])
        ingest_fn(ctx, stamp, body, gkg.headers(stamp, body))
    tiny = gkg.zip(STAMP, [gkg.row(STAMP, 1), gkg.row(STAMP, 2)])
    ingest_fn(ctx, STAMP, tiny, gkg.headers(STAMP, tiny))
    commit_ready_days(ctx)
    row = ctx.manifest.slot(STAMP)
    assert row["near_empty_flag"] == 1 and row["near_empty_baseline"] == 100.0 and row["backlog_flag"] == 0
    first = ctx.manifest.slot((base - timedelta(days=14)).strftime("%Y%m%d%H%M%S"))
    assert first["near_empty_flag"] is None                          # no baseline yet: unknown, not "fine"
