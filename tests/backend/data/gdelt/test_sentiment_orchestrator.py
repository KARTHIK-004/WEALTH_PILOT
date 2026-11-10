"""S2.6: the window orchestrator, tested end to end through BOTH adapters with synthetic fixtures.

Synthetic only (no real titles, URLs, labels or keys); no scorer of any kind is imported; no network. The orchestrator returns
accounting and unscored candidate records, never predictions or features.
"""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from wealthpilot.data.gdelt.output import COLUMNS, encode_rows
from wealthpilot.data.gdelt.sentiment import dayfile_adapter as da
from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment import schema as sc
from wealthpilot.data.gdelt.sentiment.features import interval_cutoffs, nominal_grids
from wealthpilot.data.gdelt.timeutil import SLOT, slot_grid

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / "backend/wealthpilot/data/gdelt/sentiment"
UTC = timezone.utc
FV, PV = "gdelt_filter_v1", "gkg_parser_v1"
D1, D2, D3 = date(2022, 3, 1), date(2022, 3, 2), date(2022, 3, 3)
DAYS = [D1, D2, D3]
IN_D2, IN_D2_B, IN_D3 = "20220302150000", "20220302153000", "20220303150000"
LAST_D2 = "20220302204500"                       # the last nominal slot of D2: available 21:00:00Z, exactly its cutoff
CUT2 = datetime(2022, 3, 2, 21, 0, tzinfo=UTC)
THEMES = ("equity_us", "rates_us", "gold")


def nominal(b: str) -> datetime:
    return datetime.strptime(b, "%Y%m%d%H%M%S").replace(tzinfo=UTC)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def drow(batch: str, seq: int, at: datetime, **over):
    base = {c: "" for c in COLUMNS}
    base.update(row_kind="captured", gkg_record_id=f"{batch}-{seq}", batch_ts=batch, available_at_utc=iso(at),
                source_domain="example.invalid", document_url=f"https://example.invalid/{batch}/{seq}",
                url_canonical=f"example.invalid/{batch}/{seq}", page_title=f"SYNTHETIC headline {batch} {seq} about nothing real",
                title_hash=hashlib.sha256(f"h{batch}{seq}".encode()).hexdigest(), tone="0", word_count="100", us_location="0",
                us_relevant="0", company_item="0", member_equity_us="1", member_rates_us="0", member_gold="0", mech_dup="ORIGINAL",
                near_miss_cue="0", filter_version=FV, parser_version=PV)
    base.update(over)
    return base


def dbytes(rows):
    return gzip.compress(encode_rows([[r[c] for c in COLUMNS] for r in rows], header=True), mtime=0)


ABSENT_ROW = dict(existence="absent_confirmed", fetch_status="not_applicable", parse_status="not_applicable", commit_status="not_applicable")
NONFINAL_ROW = dict(existence="available", fetch_status="in_progress", parse_status="pending", commit_status="pending")


class World:
    """A synthetic window: manifest rows, series rows and day files that agree, plus knobs to break one thing at a time."""

    def __init__(self, recs=None, *, avail=None, state=None, drop_slots=(), row_over=None, series_delta=None, series_version=FV,
                 days=None, early=frozenset(), holidays=frozenset(), extra_rows=None, lookback=True, near_empty=0):
        self.days = days or DAYS
        recs, avail, state = recs or {}, avail or {}, state or {}
        row_over, series_delta, extra_rows = row_over or {}, series_delta or {}, extra_rows or {}
        grids = nominal_grids(self.days, interval_cutoffs(self.days, early))
        self.batches = sorted(b for g in grids.values() for b in g)
        # the lookback (S2.8C): the 24 hours of nominal batches before the first interval, all present in the manifest
        first = nominal(self.batches[0])
        self.lookback_from = (first - timedelta(hours=24)).strftime("%Y%m%d%H%M%S") if lookback else None
        self.lookback_batches = slot_grid(self.lookback_from, (first - SLOT).strftime("%Y%m%d%H%M%S")) if lookback else []
        self.slot_rows, self.series_rows = [], []
        day_rows: dict[str, list] = defaultdict(list)
        processed_days = set()
        for b in self.lookback_batches + self.batches:
            specs = recs.get(b, [])
            at = avail.get(b, nominal(b) + SLOT)
            st = state.get(b, "processed")
            for i, spec in enumerate(specs, 1):
                day_rows[b[:8]].append(drow(b, i, at, **spec))
            if b in drop_slots:
                continue
            if st == "processed":
                processed_days.add(b[:8])
                eq, ra, go = (sum(1 for s in specs if s.get(k, d) == "1") for k, d in
                              (("member_equity_us", "1"), ("member_rates_us", "0"), ("member_gold", "0")))
                row = dict(batch_ts=b, existence="present_verified", fetch_status="fetched", parse_status="parsed_validated",
                           commit_status="committed", availability_status="verified", available_at_utc=iso(at), near_empty_flag=near_empty,
                           filter_version=FV, parser_version=PV, rows_physical=len(specs) + 12, rows_malformed=2, rows_date_mismatch=0,
                           rows_translated=0, rows_non_web=0, rows_english_valid=len(specs) + 10, rows_captured=len(specs),
                           rows_company_item=sum(1 for s in specs if s.get("company_item", "0") == "1"), rows_dup_same_batch=0,
                           rows_audit_sample=1, availability_flags="", late_flag=0)
                row.update(row_over.get(b, {}))
                for s, n in (("EQUITY_US", eq), ("RATES_US", ra), ("GOLD", go)):
                    n += series_delta.get(b, {}).get(s, 0)
                    self.series_rows.append(dict(batch_ts=b, filter_version=series_version, series=s, rows=n, rows_us_relevant=n, new_stories=None))
            else:
                row = dict(batch_ts=b, availability_status="pending", available_at_utc=None, **(ABSENT_ROW if st == "absent" else NONFINAL_ROW))
                row.update(row_over.get(b, {}))
            self.slot_rows.append(row)
        for b, specs in extra_rows.items():                                        # rows for batches outside the window grid
            for i, spec in enumerate(specs, 1):
                day_rows[b[:8]].append(drow(b, i, nominal(b) + SLOT, **spec))
        self.source: dict[str, orc.DayFileData] = {}
        for d8 in sorted(processed_days):
            rows = sorted(day_rows[d8], key=lambda r: (r["batch_ts"], int(r["gkg_record_id"].split("-")[1])))
            day = f"{d8[:4]}-{d8[4:6]}-{d8[6:8]}"
            data = dbytes(rows)
            self.source[day] = orc.DayFileData(data, f"synthetic/{day}.tsv.gz", dict(
                utc_day=day, status="committed", filter_version=FV, parser_version=PV, rows_kept=len(rows),
                file_sha256=hashlib.sha256(data).hexdigest()))
        self.early, self.holidays = early, holidays

    def inputs(self, **over) -> orc.WindowInputs:
        base = dict(trading_days=tuple(self.days), early_closes=self.early, market_holidays=self.holidays, filter_version=FV,
                    min_chars=20, slot_rows=self.slot_rows, series_rows=self.series_rows, day_source=self.source.get,
                    earlier_batches_from=self.lookback_from)
        return orc.WindowInputs(**{**base, **over})

    def run(self, **over) -> orc.WindowReport:
        return orc.orchestrate_window(self.inputs(**over))


def states(report, d):
    return {v.batch_ts: v.state for v in report.slots if v.interval == d}


def codes(report, scope=None):
    return [i.code for i in report.issues if scope is None or i.scope == scope]


# ================================================================ reconciled windows

def test_a_fully_reconciled_on_time_batch_is_placed_and_everything_else_is_verified_empty():
    r = World({IN_D2: [{}, {"member_rates_us": "1"}]}).run()
    assert r.issues == () and all(v.state == "reconciled" for v in r.slots) and len(r.slots) == 192
    d2, d3 = r.interval(D2), r.interval(D3)
    assert d2.status == "accounted_complete" and [x.article_id for x in d2.records] == [f"{IN_D2}-1", f"{IN_D2}-2"]
    assert d2.n_records_by_theme == {"equity_us": 2, "rates_us": 1, "gold": 0} and d2.n_late_carried_in == 0
    assert d2.no_news_basis == {"equity_us": "has_records", "rates_us": "has_records", "gold": "verified_complete_no_records"}
    assert d3.status == "accounted_complete" and d3.records == () and set(d3.no_news_basis.values()) == {"verified_complete_no_records"}
    assert d2.n_expected_slots == 96 and d2.slot_state_counts == {"reconciled": 96}
    assert [d.status for d in r.day_files] == ["ok", "ok", "ok"] and r.n_out_of_window_records == 0 and r.n_records_held_back == 0
    assert all(isinstance(x, da.CandidateRecord) and not isinstance(x, sc.ArticleRecord) for x in d2.records)


def test_several_batches_in_one_window_are_placed_in_order_with_per_theme_counts():
    recs = {IN_D2_B: [{}], IN_D2: [{}, {"member_gold": "1"}], IN_D3: [{"member_rates_us": "1", "member_equity_us": "0"}],
            "20220301230000": [{}]}                                      # a D2-interval batch on the previous UTC day
    r = World(recs).run()
    assert [x.article_id for x in r.interval(D2).records] == ["20220301230000-1", f"{IN_D2}-1", f"{IN_D2}-2", f"{IN_D2_B}-1"]
    assert r.interval(D3).n_records_by_theme == {"equity_us": 0, "rates_us": 1, "gold": 0}
    assert r.interval(D2).n_records_by_theme == {"equity_us": 4, "rates_us": 0, "gold": 1}
    assert r.issues == () and all(i.status == "accounted_complete" for i in r.intervals)


def test_an_empty_window_with_complete_accounting_is_verified_no_records():
    r = World().run()
    assert all(i.status == "accounted_complete" and i.records == () for i in r.intervals)
    assert all(set(i.no_news_basis.values()) == {"verified_complete_no_records"} for i in r.intervals)
    assert r.repeated_content == orc.RepeatedContent(0, 0, 0, 0, 0, 0) and r.n_records_held_back == 0


# ================================================================ missing, non-final and rejected sources

def test_a_missing_manifest_slot_makes_the_interval_incomplete_and_empty_is_not_no_news():
    r = World({IN_D2_B: [{}]}, drop_slots={IN_D2}).run()
    assert states(r, D2)[IN_D2] == "missing_manifest_slot" and "missing_manifest_row" in codes(r, "manifest")
    d2 = r.interval(D2)
    assert d2.status == "incomplete_accounting" and d2.no_news_basis["gold"] == "unverified_empty_incomplete"
    assert d2.no_news_basis["equity_us"] == "has_records" and r.interval(D3).status == "accounted_complete"


def test_a_missing_day_file_blocks_every_interval_that_uses_it():
    w = World({IN_D2: [{}]})
    del w.source["2022-03-02"]
    r = w.run()
    assert [d.status for d in r.day_files] == ["ok", "missing", "ok"] and "day_file_missing" in codes(r, "day_file")
    assert {v.state for v in r.slots if v.batch_ts.startswith("20220302")} == {"day_file_missing"}
    assert r.interval(D2).status == "incomplete_accounting" and r.interval(D3).status == "incomplete_accounting"
    assert r.interval(D2).records == () and set(r.interval(D2).no_news_basis.values()) == {"unverified_empty_incomplete"}


def test_an_untrusted_day_file_is_invalid_and_yields_no_records():
    w = World({IN_D2: [{}]})
    day = w.source["2022-03-02"]
    w.source["2022-03-02"] = dataclasses.replace(day, data=day.data[:-3] + b"xyz")                 # bytes no longer match the commit
    r = w.run()
    assert r.day_files[1].status == "invalid" and "file_sha256_mismatch" in r.day_files[1].codes and "file_sha256_mismatch" in codes(r, "day_file")
    assert r.interval(D2).records == () and r.interval(D2).status == "incomplete_accounting"
    w2 = World({IN_D2: [{}]})
    w2.source["2022-03-02"] = dataclasses.replace(w2.source["2022-03-02"], day_commit=None)
    r2 = w2.run()
    assert r2.day_files[1].codes == ("day_commit_missing",) and r2.interval(D2).status == "incomplete_accounting"
    w3 = World({IN_D2: [{}]})
    w3.source["2022-03-02"] = dataclasses.replace(w3.source["2022-03-02"], day_commit={**w3.source["2022-03-02"].day_commit, "status": "superseded"})
    assert World.run(w3).day_files[1].status == "invalid"


def test_a_non_final_slot_is_incomplete_not_empty():
    r = World({}, state={IN_D2: "in_progress"}).run()
    assert states(r, D2)[IN_D2] == "non_final_slot" and r.interval(D2).status == "incomplete_accounting"
    assert r.interval(D2).no_news_basis["equity_us"] == "unverified_empty_incomplete"


def test_an_absent_source_batch_is_partial_accounting_with_no_coverage_verdict():
    r = World({IN_D2_B: [{}]}, state={IN_D2: "absent"}).run()
    d2 = r.interval(D2)
    assert states(r, D2)[IN_D2] == "source_batch_absent" and d2.status == "partial_source_accounting"
    assert d2.no_news_basis["gold"] == "unverified_empty_partial" and d2.no_news_basis["equity_us"] == "has_records"
    assert r.policy_status["source_coverage_threshold"] == "APPLIED_PROVISIONAL"      # owner applied it provisionally and informationally
    assert World({}, state={IN_D2: "absent"}).run().interval(D2).no_news_basis["equity_us"] == "unverified_empty_partial"


def test_an_incorrect_filter_version_is_rejected_per_batch_and_never_mixed():
    r = World({IN_D2: [{}]}, row_over={IN_D2: {"filter_version": "gdelt_filter_v0"}}).run()
    assert states(r, D2)[IN_D2] == "slot_rejected" and "filter_version_differs" in codes(r, "manifest")
    assert r.interval(D2).status == "incomplete_accounting" and r.interval(D2).records == ()
    wrong_series = World({IN_D2: [{}]}, series_version="gdelt_filter_v0").run()
    assert {v.state for v in wrong_series.slots} == {"slot_rejected"} and "missing_series" in codes(wrong_series, "manifest")
    asked_other = World({IN_D2: [{}]}).run(filter_version="gdelt_filter_v0")
    assert {v.state for v in asked_other.slots} == {"slot_rejected"} and all(i.status == "incomplete_accounting" for i in asked_other.intervals)


# ================================================================ count and record mismatches

def test_per_batch_and_per_theme_count_mismatches_hold_the_records_back():
    batch_count = World({IN_D2: [{}, {}]}, row_over={IN_D2: {"rows_captured": 3, "rows_english_valid": 20, "rows_physical": 40}}).run()
    assert states(batch_count, D2)[IN_D2] == "count_mismatch" and "rows_captured 3 but 2" in " ".join(
        next(v for v in batch_count.slots if v.batch_ts == IN_D2).reasons)
    assert batch_count.interval(D2).records == () and batch_count.n_records_held_back == 2
    assert batch_count.interval(D2).status == "incomplete_accounting" and batch_count.interval(D2).no_news_basis["equity_us"] == "unverified_empty_incomplete"
    theme = World({IN_D2: [{}]}, series_delta={IN_D2: {"RATES_US": 1}}).run()
    assert states(theme, D2)[IN_D2] == "count_mismatch" and any("rates_us series rows 1 but 0" in x
                                                              for v in theme.slots for x in v.reasons)
    assert theme.interval(D2).records == ()


def test_a_record_with_no_matching_slot_is_reported_and_never_placed():
    no_row = World({IN_D2: [{}]}, drop_slots={IN_D2}).run()
    assert "batch_not_in_manifest" in codes(no_row, "record") and no_row.interval(D2).records == ()
    not_processed = World({IN_D2: [{}], IN_D2_B: [{}]}, state={IN_D2: "absent"}).run()
    assert "batch_slot_not_processed" in codes(not_processed, "record") and states(not_processed, D2)[IN_D2] == "source_batch_absent"
    assert [x.article_id for x in not_processed.interval(D2).records] == [f"{IN_D2_B}-1"]


def test_records_of_batches_outside_the_window_are_counted_not_errors():
    r = World({IN_D2: [{}]}, extra_rows={"20220301100000": [{}, {}]}).run()
    assert r.n_out_of_window_records == 2 and r.issues == () and r.interval(D2).status == "accounted_complete"
    assert r.n_manifest_rows_outside_window == 0
    w = World({IN_D2: [{}]})
    rows = w.slot_rows + [dict(w.slot_rows[0], batch_ts="20211201000000")]
    series = w.series_rows + [dict(s, batch_ts="20211201000000") for s in w.series_rows[:3]]
    out = w.run(slot_rows=rows, series_rows=series)
    assert out.n_manifest_rows_outside_window == 1 and out.issues == ()


def test_a_batch_availability_mismatch_between_record_and_manifest_is_a_mismatch():
    w = World({IN_D2: [{}]})
    w.slot_rows = [dict(r, available_at_utc=iso(nominal(IN_D2) + timedelta(minutes=30))) if r["batch_ts"] == IN_D2 else r for r in w.slot_rows]
    r = w.run()
    assert "availability_differs_from_manifest" in codes(r, "record") and states(r, D2)[IN_D2] == "count_mismatch"
    assert r.interval(D2).records == () and r.interval(D2).status == "incomplete_accounting"


def test_duplicate_record_ids_make_the_batch_ambiguous_and_none_of_it_is_used():
    w = World({IN_D2: [{}, {}], IN_D2_B: [{}]})
    day = w.source["2022-03-02"]
    # rewrite the 2022-03-02 file so two rows share one record id (and recommit its hash)
    text = gzip.decompress(day.data).decode()
    lines = text.splitlines()
    idx = next(i for i, ln in enumerate(lines) if ln.split("\t")[1] == f"{IN_D2}-2")
    lines[idx] = lines[idx].replace(f"{IN_D2}-2", f"{IN_D2}-1")
    data = gzip.compress(("\n".join(lines) + "\n").encode(), mtime=0)
    w.source["2022-03-02"] = dataclasses.replace(day, data=data, day_commit={**day.day_commit, "file_sha256": hashlib.sha256(data).hexdigest()})
    r = w.run()
    assert states(r, D2)[IN_D2] == "duplicate_record_id" and "duplicate_record_id" in codes(r, "record")
    assert [x.article_id for x in r.interval(D2).records] == [f"{IN_D2_B}-1"] and r.interval(D2).status == "incomplete_accounting"


# ================================================================ cutoffs and late batches

def test_a_batch_available_exactly_at_the_cutoff_is_on_time():
    r = World({LAST_D2: [{}]}, avail={LAST_D2: CUT2}).run()
    assert states(r, D2)[LAST_D2] == "reconciled" and r.interval(D2).status == "accounted_complete"
    assert [x.article_id for x in r.interval(D2).records] == [f"{LAST_D2}-1"] and r.interval(D3).records == ()


def test_a_batch_available_just_after_the_cutoff_is_delayed_into_the_next_interval():
    r = World({LAST_D2: [{}]}, avail={LAST_D2: CUT2 + timedelta(seconds=1)}).run()
    d2, d3 = r.interval(D2), r.interval(D3)
    assert states(r, D2)[LAST_D2] == "delayed" and next(v for v in r.slots if v.batch_ts == LAST_D2).delayed_into == D3
    assert d2.status == "accounted_with_delayed" and d2.records == () and d2.n_delayed_slots == 1 and d2.delayed_theme_rows["equity_us"] == 1
    assert d2.no_news_basis["equity_us"] == "unverified_empty_delayed" and d2.no_news_basis["gold"] == "unverified_empty_delayed"
    assert d3.status == "accounted_complete" and d3.n_late_carried_in == 1 and [x.article_id for x in d3.records] == [f"{LAST_D2}-1"]


def test_a_late_batch_whose_records_become_available_in_a_later_interval_is_never_used_earlier_or_dropped():
    late = datetime(2022, 3, 2, 21, 45, tzinfo=UTC)
    on_time = World({IN_D2: [{}], LAST_D2: [{}]}).run()
    delayed = World({IN_D2: [{}], LAST_D2: [{}]}, avail={LAST_D2: late}).run()
    assert [x.article_id for x in delayed.interval(D2).records] == [f"{IN_D2}-1"]                 # not used before it was available
    assert [x.article_id for x in on_time.interval(D2).records] == [f"{IN_D2}-1", f"{LAST_D2}-1"]
    assert [x.article_id for x in delayed.interval(D3).records] == [f"{LAST_D2}-1"] and delayed.n_records_beyond_window == 0
    assert all(x.available_at_utc == late for x in delayed.interval(D3).records)
    far = World({LAST_D2: [{}]}, avail={LAST_D2: datetime(2022, 3, 8, 0, 0, tzinfo=UTC)}).run()   # after the last cutoff
    assert far.n_records_beyond_window == 1 and not any(i.records for i in far.intervals)
    assert states(far, D2)[LAST_D2] == "delayed" and far.interval(D2).no_news_basis["equity_us"] == "unverified_empty_delayed"


def test_an_unreconciled_late_batch_makes_the_interval_it_would_enter_incomplete():
    late = datetime(2022, 3, 2, 21, 45, tzinfo=UTC)
    r = World({LAST_D2: [{}]}, avail={LAST_D2: late}, row_over={LAST_D2: {"rows_captured": 2, "rows_english_valid": 20, "rows_physical": 40}}).run()
    assert states(r, D2)[LAST_D2] == "count_mismatch" and r.interval(D3).unresolved_inflow == (LAST_D2,)
    assert r.interval(D3).status == "incomplete_accounting" and r.interval(D3).records == ()
    assert r.interval(D3).no_news_basis["equity_us"] == "unverified_empty_incomplete"


def test_a_delayed_empty_batch_is_still_not_evidence_of_absence():
    late = datetime(2022, 3, 2, 21, 45, tzinfo=UTC)
    r = World({}, avail={LAST_D2: late}).run()                                                    # delayed, carrying no rows at all
    assert states(r, D2)[LAST_D2] == "delayed" and r.interval(D2).status == "accounted_with_delayed"
    assert set(r.interval(D2).no_news_basis.values()) == {"unverified_empty_delayed"}              # point-in-time: absence unknowable at the cutoff


def test_a_weekend_window_assigns_a_saturday_availability_to_monday():
    thu, fri, mon = date(2022, 3, 3), date(2022, 3, 4), date(2022, 3, 7)
    last_fri = "20220304204500"
    r = World({last_fri: [{}]}, days=[thu, fri, mon], avail={last_fri: datetime(2022, 3, 5, 6, 0, tzinfo=UTC)}).run()
    assert r.interval(mon).n_expected_slots == 288 and r.interval(mon).n_late_carried_in == 1
    assert r.interval(fri).status == "accounted_with_delayed" and r.interval(mon).status == "accounted_complete"


# ================================================================ repeated content, calls, determinism, scope

def test_repeated_urls_and_title_hashes_across_batches_are_preserved_and_only_counted():
    shared_url, shared_hash = "example.invalid/shared", hashlib.sha256(b"same").hexdigest()
    spec = {"url_canonical": shared_url, "title_hash": shared_hash}
    r = World({IN_D2: [spec], IN_D2_B: [spec, spec], IN_D3: [spec]}).run()
    assert len(r.interval(D2).records) == 3 and len(r.interval(D3).records) == 1                    # nothing discarded
    rc = r.repeated_content
    assert (rc.n_url_groups, rc.n_url_groups_across_batches, rc.n_records_in_repeated_urls) == (1, 1, 4)
    assert (rc.n_title_hash_groups, rc.n_title_hash_groups_across_batches, rc.n_records_in_repeated_title_hashes) == (1, 1, 4)
    assert rc.policy == "APPLIED_PROVISIONAL" == r.policy_status["deduplication_and_story_updates"]
    assert not any(hasattr(x, "story_id") for i in r.intervals for x in i.records)
    assert {x.same_batch_status for i in r.intervals for x in i.records} == {"ORIGINAL"}
    only_in_batch = World({IN_D2: [spec, spec]}).run().repeated_content
    assert (only_in_batch.n_url_groups, only_in_batch.n_url_groups_across_batches) == (1, 0)


def test_results_are_deterministic_across_runs_and_input_order():
    recs = {IN_D2: [{}, {"member_rates_us": "1"}], IN_D2_B: [{}], LAST_D2: [{}], IN_D3: [{"member_gold": "1"}]}
    w = World(recs, avail={LAST_D2: datetime(2022, 3, 2, 21, 45, tzinfo=UTC)}, state={IN_D3[:8] + "000000": "absent"})
    first = w.run()
    assert w.run() == first and w.run().digest() == first.digest()
    rng = random.Random(42)
    for _ in range(3):
        rows, series = w.slot_rows[:], w.series_rows[:]
        rng.shuffle(rows), rng.shuffle(series)
        assert w.run(slot_rows=rows, series_rows=series) == first
    assert w.run(trading_days=list(w.days)).digest() == first.digest()
    assert list(first.issues) == sorted(first.issues, key=orc.WindowIssue.sort_key)


def test_wrong_calls_and_bad_calendars_raise_instead_of_producing_a_report():
    w = World()
    for over in (dict(trading_days=(d for d in DAYS)), dict(trading_days=[D1, date(2022, 3, 5)]), dict(trading_days=[D1, D3]),
                 dict(trading_days=[datetime(2022, 3, 1), datetime(2022, 3, 2)]), dict(early_closes={D2}),
                 dict(market_holidays=frozenset({D2})), dict(day_source="not callable"), dict(slot_rows=iter([])), dict(series_rows="x")):
        with pytest.raises(orc.OrchestratorError):
            w.run(**over)
    with pytest.raises(orc.OrchestratorError):
        orc.orchestrate_window("inputs")                                                            # type: ignore[arg-type]
    with pytest.raises(orc.OrchestratorError):
        w.run(day_source=lambda d: "bytes")


def test_the_early_close_and_holiday_inputs_are_explicit_and_change_the_grid():
    day = date(2022, 11, 25)
    days = [date(2022, 11, 23), day]
    holidays = frozenset({date(2022, 11, 24)})
    normal = World(days=days, holidays=holidays).run()
    early = World(days=days, holidays=holidays, early=frozenset({day})).run()
    assert normal.interval(day).n_expected_slots == 192 and early.interval(day).n_expected_slots == 180
    assert early.interval(day).cutoff_utc.hour == 18 and early.policy_status["holiday_and_early_close_calendars"] == "APPLIED_PROVISIONAL"      # caller-supplied, unverified
    with pytest.raises(orc.OrchestratorError):
        World(days=days, holidays=frozenset()).run()                                                # the holiday is not declared


def test_nothing_is_scored_and_no_feature_or_prediction_is_produced():
    r = World({IN_D2: [{}]}).run()
    names = {f.name for f in dataclasses.fields(orc.WindowReport)} | {f.name for f in dataclasses.fields(orc.IntervalAccounting)}
    for forbidden in ("mean_net", "mean_p_pos", "no_news", "pred_label", "p_positive", "features", "scores", "story_id"):
        assert forbidden not in names, forbidden
    assert r.policy_status["scoring"] == "NOT_PERFORMED"
    text = (PKG / "orchestrator.py").read_text(encoding="utf-8")
    for word in ("fake_scorer", "FakeScorer", "aggregate_daily", "ArticleRecord(", "transformers", "torch", "sqlite3", "urllib", "socket",
                 "subprocess", "os.environ", "key_sealed", "annotation_", "ai_only"):
        assert word not in text, word


# ================================================================ S2.8B: F5, F3, F4, F6, F7

def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize("bad", ["2022-03-02", "20220302150700", "", "ABCDEFGHIJKLMN", "20221399000000"])
def test_f5_an_invalid_batch_ts_is_its_own_issue_and_never_counted_as_out_of_window(bad):
    r = World({IN_D2: [{}, {"batch_ts": bad}]}).run()
    record_codes = codes(r, "record")
    assert "invalid_batch_ts" in record_codes and "batch_not_in_manifest" not in record_codes
    assert r.n_records_invalid_batch_ts == 1 and r.n_out_of_window_records == 0
    assert states(r, D2)[IN_D2] == "count_mismatch" and r.interval(D2).status == "incomplete_accounting"
    assert all(i.batch_ts is None for i in r.issues if i.code == "invalid_batch_ts")                 # no batch is claimed for an invalid stamp


def test_f5_a_valid_stamp_outside_the_window_is_still_only_counted():
    r = World({IN_D2: [{}]}, extra_rows={"20220301100000": [{}]}).run()
    assert r.n_out_of_window_records == 1 and r.n_records_invalid_batch_ts == 0 and r.issues == ()


def test_f3_company_item_counts_must_reconcile_with_the_record_flags():
    ok = World({IN_D2: [{"company_item": "1"}, {}, {"company_item": "1"}]}).run()
    assert states(ok, D2)[IN_D2] == "reconciled" and ok.interval(D2).status == "accounted_complete"
    for over in ({"rows_company_item": 0}, {"rows_company_item": 1}, {"rows_company_item": 3}):
        r = World({IN_D2: [{"company_item": "1"}, {}, {"company_item": "1"}]}, row_over={IN_D2: over}).run()
        v = next(x for x in r.slots if x.batch_ts == IN_D2)
        assert v.state == "count_mismatch" and any("rows_company_item" in x for x in v.reasons), over
        assert r.interval(D2).records == () and r.interval(D2).status == "incomplete_accounting"
    unflagged = World({IN_D2: [{}]}, row_over={IN_D2: {"rows_company_item": 1}}).run()                # S2.7 reproduction P2
    assert states(unflagged, D2)[IN_D2] == "count_mismatch"
    no_count = World({IN_D2: [{}]})
    no_count.slot_rows = [{k: v for k, v in r.items() if k != "rows_company_item"} if r["batch_ts"] == IN_D2 else r for r in no_count.slot_rows]
    assert states(no_count.run(), D2)[IN_D2] == "slot_rejected"                                      # no count: rejected, never guessed


def test_f4_mixed_parser_versions_fail_closed_with_diagnostics():
    base = World()
    d3 = [b for b in base.batches if b.startswith("20220303")]
    w = World({IN_D3: [{"parser_version": "gkg_parser_v2"}], IN_D2: [{}]}, row_over={b: {"parser_version": "gkg_parser_v2"} for b in d3})
    dc = w.source["2022-03-03"]
    w.source["2022-03-03"] = dataclasses.replace(dc, day_commit={**dc.day_commit, "parser_version": "gkg_parser_v2"})
    r = w.run()
    mixed = [i for i in r.issues if i.code == "mixed_versions"]
    assert len(mixed) == 1 and mixed[0].scope == "window" and "gkg_parser_v1" in mixed[0].detail and "gkg_parser_v2" in mixed[0].detail
    assert r.observed_versions == ((FV, "gkg_parser_v1"), (FV, "gkg_parser_v2"))
    assert {v.state for v in r.slots} == {"version_mismatch"} and all(i.status == "incomplete_accounting" for i in r.intervals)
    assert all(i.records == () for i in r.intervals) and r.day_files == ()                            # nothing is read or trusted
    assert set(r.interval(D2).no_news_basis.values()) == {"unverified_empty_incomplete"}


def test_f4_a_window_with_one_version_is_unchanged_even_if_that_version_is_new():
    base = World()
    all_v2 = {b: {"parser_version": "gkg_parser_v2"} for b in base.batches}
    w = World({IN_D2: [{"parser_version": "gkg_parser_v2"}]}, row_over=all_v2)
    for day, data in list(w.source.items()):
        w.source[day] = dataclasses.replace(data, day_commit={**data.day_commit, "parser_version": "gkg_parser_v2"})
    r = w.run()
    assert r.issues == () and r.observed_versions == ((FV, "gkg_parser_v2"),)
    assert all(i.status == "accounted_complete" for i in r.intervals) and len(r.interval(D2).records) == 1
    plain = World({IN_D2: [{}]}).run()
    assert plain.observed_versions == ((FV, PV),) and plain.issues == ()


def test_f4_mixed_filter_versions_are_rejected_per_batch_and_never_mixed():
    r = World({IN_D2: [{}]}, row_over={IN_D2: {"filter_version": "gdelt_filter_v0"}}).run()
    assert states(r, D2)[IN_D2] == "slot_rejected" and r.observed_versions == ((FV, PV),)


def test_f6_the_report_policy_status_is_immutable_and_blocks_downstream_use():
    from wealthpilot.data.gdelt.sentiment import policy as pol
    r = World().run()
    with pytest.raises(TypeError):
        r.policy_status["scoring"] = "PERFORMED"                                                     # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.policy_status = {}                                                                         # type: ignore[misc]
    with pytest.raises(pol.PolicyBlockedError):
        pol.require_policies_applied(r.policy_state())
    assert r.policy_state() == pol.PolicyState.from_mapping(orc.POLICY_STATUS)
    assert World().run() == r


def test_f7_the_digest_binds_record_content_provenance_inputs_versions_window_configuration_and_policy():
    recs = {IN_D2: [{}, {"member_rates_us": "1"}], IN_D3: [{}]}
    base = World(recs).run()
    assert World(recs).run().digest() == base.digest() and len(base.digest()) == 64
    # record content that the manifest does not count: the record fingerprint, and so the digest, must change
    for change in ({"page_title": "SYNTHETIC a different headline that is long enough"}, {"title_hash": sha("other")}, {"source_domain": "other.invalid"},
                   {"url_canonical": "example.invalid/other-path"}, {"word_count": "101"}, {"mech_dup": "DUP_SAME_BATCH"}):
        w = World({IN_D2: [change, {"member_rates_us": "1"}], IN_D3: [{}]}).run()
        assert w.input_fingerprint == base.input_fingerprint, change
        assert w.record_fingerprint != base.record_fingerprint and w.digest() != base.digest(), change
    # record content that the manifest counts, and manifest-only provenance
    for recs2, over in (({IN_D2: [{"company_item": "1"}, {"member_rates_us": "1"}], IN_D3: [{}]}, None), (recs, {IN_D2: {"rows_audit_sample": 2}}),
                        (recs, {IN_D2: {"availability_flags": "late"}})):
        assert World(recs2, row_over=over).run().digest() != base.digest(), (recs2, over)
    # file and source provenance
    w = World(recs)
    day = w.source["2022-03-02"]
    w.source["2022-03-02"] = dataclasses.replace(day, source_name="synthetic/renamed.tsv.gz")
    assert w.run().digest() != base.digest()
    # configuration, window, versions and policy
    assert World(recs).run(min_chars=25).digest() != base.digest()
    for field, value in (("early_closes", frozenset({D2})), ("market_holidays", frozenset({date(2022, 3, 9)})), ("min_chars", 21),
                         ("filter_version", "gdelt_filter_v0"), ("trading_days", (D1, D2)),
                         ("observed_versions", ((FV, "gkg_parser_v9"),)),
                         ("policy_status", MappingProxyType({**orc.POLICY_STATUS, "source_coverage_threshold": "UNRESOLVED_NOT_APPLIED"}))):
        assert dataclasses.replace(base, **{field: value}).digest() != base.digest(), field


def test_f7_the_digest_is_stable_under_semantically_irrelevant_reordering():
    recs = {IN_D2: [{}, {"member_rates_us": "1"}], IN_D2_B: [{}], IN_D3: [{}]}
    w = World(recs)
    first = w.run()
    rng = random.Random(7)
    for _ in range(4):
        rows, series = w.slot_rows[:], w.series_rows[:]
        rng.shuffle(rows), rng.shuffle(series)
        r = w.run(slot_rows=rows, series_rows=series)
        assert r.digest() == first.digest() and r.input_fingerprint == first.input_fingerprint
    reordered_keys = [dict(reversed(list(row.items()))) for row in w.slot_rows]                       # same rows, different key order
    assert w.run(slot_rows=reordered_keys).digest() == first.digest()
    assert w.run(trading_days=list(w.days)).digest() == first.digest()


def test_f7_the_digest_carries_hashes_and_identifiers_not_payload_text():
    r = World({IN_D2: [{}]}).run()
    rec = r.interval(D2).records[0]
    text = str(orc._record_line(rec))
    assert rec.title not in text and rec.url_canonical not in text and rec.title_sha256_raw in text
    assert rec.url_canonical.encode() not in orc._canonical(orc._record_line(rec))


def test_existing_valid_window_behaviour_is_unchanged_by_the_hardening():
    r = World({IN_D2: [{}, {"member_rates_us": "1"}], IN_D3: [{"member_gold": "1"}]}).run()
    assert r.issues == () and all(v.state == "reconciled" for v in r.slots) and r.n_records_invalid_batch_ts == 0
    assert [i.status for i in r.intervals] == ["accounted_complete", "accounted_complete"]
    assert r.interval(D2).n_records_by_theme == {"equity_us": 2, "rates_us": 1, "gold": 0}


# ================================================================ S2.8C: F1, earlier nominal batches arriving inside the window (C-min)

PRE = "20220301100000"                                   # nominal 11 hours before the first interval opens (2022-03-01 21:00Z)
PRE_LATE = datetime(2022, 3, 2, 5, 0, tzinfo=UTC)       # its verified availability: inside the interval of D2
LAST_LB = "20220301204500"                              # the last lookback slot: normally available exactly at the window start


def earlier(r, batch=PRE):
    return next((a for a in r.earlier_arrivals if a.batch_ts == batch), None)


def test_f1_a_late_earlier_batch_that_is_accounted_for_enters_its_receiving_interval():
    w = World({PRE: [{}, {"member_rates_us": "1"}]}, avail={PRE: PRE_LATE})
    r = w.run()
    a = earlier(r)
    assert a.state == "late_arrival_reconciled" and a.receiving_interval == D2 and a.n_records == 2
    assert a.nominal_utc == nominal(PRE) and a.available_at_utc == PRE_LATE                        # both times, the batch and the interval
    d2, d3 = r.interval(D2), r.interval(D3)
    assert [x.article_id for x in d2.records] == [f"{PRE}-1", f"{PRE}-2"] and d2.n_earlier_arrivals == 1 and d2.n_late_carried_in == 2
    assert all(x.available_at_utc == PRE_LATE for x in d2.records)                                  # placed by verified availability
    assert d2.status == "accounted_with_delayed" and d2.no_news_basis["gold"] == "unverified_empty_delayed"
    assert d2.no_news_basis["equity_us"] == "has_records" and d3.status == "accounted_complete" and d3.records == ()
    assert r.issues == () and r.n_out_of_window_records == 0 and r.n_records_held_back == 0
    assert r.earlier_batches_from == w.lookback_from and r.n_lookback_rows == 96


def test_f1_without_accounting_the_receiving_interval_is_not_complete_and_nothing_is_dropped_silently():
    # S2.7 reproduction P1: a pre-window batch with a record became available inside D2. Before the fix D2 was "accounted_complete" and
    # its equity basis "verified_complete_no_records" with no issue.
    r = World({PRE: [{}]}, avail={PRE: PRE_LATE}, row_over={PRE: {"rows_captured": 2, "rows_english_valid": 20, "rows_physical": 40}}).run()
    a = earlier(r)
    assert a.state == "count_mismatch" and a.receiving_interval == D2 and any("rows_captured 2 but 1" in x for x in a.reasons)
    d2 = r.interval(D2)
    assert d2.status == "incomplete_accounting" and d2.unresolved_inflow == (PRE,) and d2.records == ()
    assert d2.no_news_basis["equity_us"] == "unverified_empty_incomplete" and r.interval(D3).status == "accounted_complete"
    assert r.n_records_held_back == 1                                                                # held back and reported, not discarded
    issue = next(i for i in r.issues if i.code == "earlier_batch_unresolved")
    assert issue.batch_ts == PRE and "nominal 2022-03-01T10:00:00+00:00" in issue.detail and "2022-03-02T05:00:00+00:00" in issue.detail
    assert "receiving interval 2022-03-02" in issue.detail


def test_f1_a_missing_earlier_batch_makes_every_interval_incomplete_with_a_specific_diagnostic():
    r = World({}, drop_slots={PRE}).run()
    a = earlier(r)
    assert a.state == "earlier_batch_unresolved" and a.receiving_interval is None and a.available_at_utc is None
    assert "missing_manifest_row" in a.reasons
    assert all(i.status == "incomplete_accounting" and PRE in i.unresolved_inflow for i in r.intervals)
    issue = next(i for i in r.issues if i.code == "earlier_batch_unresolved")
    assert issue.batch_ts == PRE and "every interval of the window" in issue.detail and "no verified availability" in issue.detail
    assert set(r.interval(D2).no_news_basis.values()) == {"unverified_empty_incomplete"}


@pytest.mark.parametrize("over,reason", [
    ({"availability_status": "unverified", "available_at_utc": None}, "missing_value"),
    ({"available_at_utc": "yesterday"}, "invalid_slot"),
    ({"availability_status": "unverified"}, "invalid_slot"),
    ({"available_at_utc": "2022-03-02T05:00:00Z", "availability_status": "pending"}, "invalid_slot")])
def test_f1_an_earlier_batch_with_unverifiable_availability_is_unresolved_for_the_whole_window(over, reason):
    r = World({}, row_over={PRE: over}).run()
    a = earlier(r)
    assert a.state == "earlier_batch_unresolved" and a.receiving_interval is None and reason in a.reasons, over
    assert all(i.status == "incomplete_accounting" and PRE in i.unresolved_inflow for i in r.intervals)


def test_f1_a_non_final_earlier_batch_has_an_unknown_availability_and_blocks_the_window():
    r = World({}, state={PRE: "in_progress"}).run()
    a = earlier(r)
    assert a.state == "earlier_batch_unresolved" and a.reasons == ("non_final_slot:in_progress",)
    assert all(i.status == "incomplete_accounting" for i in r.intervals)


def test_f1_a_final_absent_earlier_batch_can_never_arrive_and_is_only_counted():
    r = World({}, state={PRE: "absent"}).run()
    assert r.n_earlier_final_unavailable == 1 and earlier(r) is None and r.issues == ()
    assert all(i.status == "accounted_complete" for i in r.intervals)


def test_f1_a_rejected_earlier_row_matters_only_where_its_verified_availability_puts_it():
    bad = {"rows_captured": 5, "rows_english_valid": 3}                                              # an inconsistent row, rejected by the manifest adapter
    outside = World({}, row_over={PRE: bad}).run()                                                    # verified availability 10:15Z on 03-01: before the window
    assert earlier(outside) is None and outside.n_earlier_outside_window == 96                          # all 96 lookback batches, this one included
    assert all(i.status == "accounted_complete" for i in outside.intervals)
    inside = World({}, avail={PRE: PRE_LATE}, row_over={PRE: bad}).run()                              # verified availability inside D2
    a = earlier(inside)
    assert a.receiving_interval == D2 and a.available_at_utc == PRE_LATE and a.state == "earlier_batch_unresolved"
    assert inside.interval(D2).status == "incomplete_accounting" and inside.interval(D3).status == "accounted_complete"


def test_f1_an_earlier_batch_whose_day_file_is_missing_blocks_only_its_receiving_interval():
    pre = "20220228230000"                                                                            # a UTC day that holds no window batch
    w = World({pre: [{}]}, avail={pre: datetime(2022, 3, 2, 6, 0, tzinfo=UTC)})
    assert "2022-02-28" in w.source
    del w.source["2022-02-28"]
    r = w.run()
    a = earlier(r, pre)
    assert a.state == "day_file_missing" and a.receiving_interval == D2
    assert r.interval(D2).status == "incomplete_accounting" and r.interval(D3).status == "accounted_complete"
    assert [d.status for d in r.day_files if d.utc_day == "2022-02-28"] == ["missing"]


def test_f1_an_earlier_late_batch_with_no_records_is_not_evidence_of_absence():
    r = World({}, avail={PRE: PRE_LATE}).run()
    a = earlier(r)
    assert a.state == "late_arrival_reconciled" and a.n_records == 0
    d2 = r.interval(D2)
    assert d2.status == "accounted_with_delayed" and d2.records == ()
    assert set(d2.no_news_basis.values()) == {"unverified_empty_delayed"}                              # never verified_complete_no_records
    assert set(r.interval(D3).no_news_basis.values()) == {"verified_complete_no_records"}              # an unaffected interval stays verified
    nominal_delayed = World({}, avail={LAST_D2: datetime(2022, 3, 2, 21, 45, tzinfo=UTC)}).run()      # the existing window-nominal rule is unchanged
    assert set(nominal_delayed.interval(D2).no_news_basis.values()) == {"unverified_empty_delayed"}


def test_f1_without_lookback_evidence_nothing_was_examined_and_the_window_fails_closed():
    r = World({}).run(earlier_batches_from=None)
    assert all(i.status == "incomplete_accounting" and "earlier_batches_not_examined" in i.unresolved_inflow for i in r.intervals)
    assert set(r.interval(D2).no_news_basis.values()) == {"unverified_empty_incomplete"}
    issue = next(i for i in r.issues if i.code == "earlier_batches_not_examined")
    assert issue.scope == "window" and r.earlier_batches_from is None and r.earlier_arrivals == ()
    assert World({}).run().interval(D2).status == "accounted_complete"                                # with evidence the same window is complete


def test_f1_the_lookback_declaration_is_validated_and_bounds_what_is_examined():
    w = World({PRE: [{}]}, avail={PRE: PRE_LATE})
    for bad in ("2022-03-01", "20220301210000", "20220302000000", "20220301100700"):                  # not a stamp, = first slot, after it, off-grid
        with pytest.raises(orc.OrchestratorError, match="earlier_batches_from"):
            w.run(earlier_batches_from=bad)
    narrower = w.run(earlier_batches_from="20220301150000")                                           # PRE lies before the declared lookback
    assert earlier(narrower) is None and narrower.n_manifest_rows_outside_window >= 1                # counted as outside, not examined
    assert narrower.earlier_batches_from == "20220301150000"                                          # ...and the report says how far back it looked


def test_f1_the_boundary_of_the_first_cutoff_decides_whether_an_earlier_batch_is_inside_the_window():
    at_cutoff = World({LAST_LB: [{}]}).run()                                                          # available exactly at cutoff(D1): not in the window
    assert earlier(at_cutoff, LAST_LB) is None and at_cutoff.n_earlier_outside_window >= 1
    just_after = World({LAST_LB: [{}]}, avail={LAST_LB: datetime(2022, 3, 1, 21, 0, 1, tzinfo=UTC)}).run()
    a = earlier(just_after, LAST_LB)
    assert a.receiving_interval == D2 and a.state == "late_arrival_reconciled" and len(just_after.interval(D2).records) == 1


def test_f1_the_window_is_never_extended_silently_and_an_on_time_window_is_unchanged():
    r = World({IN_D2: [{}], IN_D3: [{}]}).run()
    assert r.trading_days == tuple(DAYS) and [i.origin_date for i in r.intervals] == [D2, D3]
    assert len(r.slots) == 192 and {v.interval for v in r.slots} == {D2, D3}                           # no slot or row for the lookback days
    assert r.earlier_arrivals == () and r.issues == () and r.n_lookback_rows == 96 and r.n_earlier_outside_window == 96
    assert [i.status for i in r.intervals] == ["accounted_complete", "accounted_complete"]
    assert all(i.n_earlier_arrivals == 0 for i in r.intervals)
    assert r.n_manifest_rows_outside_window == 0                                                      # lookback rows are not "outside"


def test_f1_availability_comes_only_from_verified_source_timestamps():
    text = (PKG / "orchestrator.py").read_text(encoding="utf-8")
    for word in ("page_pub", "PAGE_PRECISEPUBTIMESTAMP", "pub_ts"):
        assert word not in text, word
    r = World({PRE: [{"page_pub_ts_utc": "2022-03-02T05:00:00Z"}]}).run()                              # a page publication time inside D2 is ignored
    assert earlier(r) is None and r.interval(D2).status == "accounted_complete" and r.interval(D2).records == ()


def test_f1_the_digest_binds_the_lookback_and_the_earlier_arrivals():
    base = World({PRE: [{}]}, avail={PRE: PRE_LATE}).run()
    assert World({PRE: [{}]}, avail={PRE: PRE_LATE}).run().digest() == base.digest()
    assert dataclasses.replace(base, earlier_batches_from="20220301120000").digest() != base.digest()
    assert dataclasses.replace(base, earlier_arrivals=()).digest() != base.digest()
    assert World({PRE: [{}]}, avail={PRE: datetime(2022, 3, 2, 6, 0, tzinfo=UTC)}).run().digest() != base.digest()


# ================================================================ S2.8D: the shared vocabulary; F2 and F2b

from wealthpilot.data.gdelt.sentiment import completeness as cp                                        # noqa: E402
from wealthpilot.data.gdelt.sentiment import features as ft                                            # noqa: E402
from wealthpilot.data.gdelt.sentiment import manifest_adapter as ma                                    # noqa: E402
from wealthpilot.data.gdelt.sentiment import policy as pol                                             # noqa: E402

APPLIED_FOR_TESTS = pol.PolicyState.from_mapping({n: pol.APPLIED_APPROVED for n in pol.REQUIRED_POLICIES})   # a TEST FIXTURE
CFG_AGG = ft.SentimentConfig(coverage_threshold=0.75, early_closes=frozenset(), market_holidays=frozenset(), dedup=ft.PROPOSED_DEDUP_POLICY,
                             expected_model_id="AUDIT_NO_SCORER", expected_model_revision="r0", expected_scorer_code_sha256="0" * 64,
                             policy=APPLIED_FOR_TESTS)
LATE_D2 = datetime(2022, 3, 2, 21, 45, tzinfo=UTC)


def aggregator_rows(w, report):
    """The aggregator on the SAME manifest, built through the same adapter, with the report's own earlier-nominal evidence."""
    by = ma.adapt_manifest(w.slot_rows, w.series_rows, filter_version=FV, expected_batches=w.batches).by_batch()
    grids = nominal_grids(w.days, interval_cutoffs(w.days, w.early))
    slots = {d: [by[b] for b in grids[d] if b in by] for d in grids}
    cfg = dataclasses.replace(CFG_AGG, early_closes=w.early, market_holidays=w.holidays)
    return ft.aggregate_daily([], w.days, slots, config=cfg, earlier=report.earlier_evidence())


def agreement(w, d=D2, **run_over):
    """Run both layers on one fixture and assert the agreement relation; return (orchestrator interval, {theme: aggregator row})."""
    report = w.run(**run_over)
    rows = {r.theme: r for r in aggregator_rows(w, report) if r.origin_date == d}
    o = report.interval(d)
    for theme in THEMES:
        row_, oe = rows[theme], o.theme_evidence[theme]
        assert row_.source_completeness == o.assessment.source.value, theme                            # one accounting contract
        assert (row_.interval_usability == "usable") == (o.assessment.usability is cp.IntervalUsability.USABLE), theme
        assert row_.theme_evidence in (oe.evidence, "not_evaluated"), theme                             # never contradicts the orchestrator
        assert (row_.no_news is True) == (oe.evidence == "verified_zero_records"), theme               # verified no-news only where both agree
        assert row_.mean_net is None and row_.mean_p_pos is None and row_.disp_net is None, theme       # no value is ever invented
        assert oe.result_availability == "blocked_by_policy"                                            # an unresolved policy blocks the report's results
    return o, rows


def test_both_layers_agree_on_a_fully_accounted_interval():
    o, rows = agreement(World({}))
    assert o.assessment.source is cp.SourceCompleteness.COMPLETE and o.assessment.usability is cp.IntervalUsability.USABLE
    assert {r.theme_evidence for r in rows.values()} == {"verified_zero_records"} and {r.no_news for r in rows.values()} == {True}
    assert {r.result_availability for r in rows.values()} == {"unavailable"}                            # nothing to score: not a value


@pytest.mark.parametrize("label,world,source", [
    ("missing source batch", lambda: World({}, drop_slots={IN_D2}), "incomplete"),
    ("rejected source batch", lambda: World({}, row_over={IN_D2: {"rows_captured": 2, "rows_english_valid": 20, "rows_physical": 40}}), "incomplete"),
    ("non-final source batch", lambda: World({}, state={IN_D2: "in_progress"}), "incomplete"),
    ("final-absent source batch", lambda: World({}, state={IN_D2: "absent"}), "final_gaps"),
    ("explicitly near-empty slot", lambda: World({}, row_over={IN_D2: {"near_empty_flag": 1}}), "complete"),
    ("unknown near-empty (F2b)", lambda: World({}, near_empty=None), "complete"),
    ("delayed empty batch (F2)", lambda: World({}, avail={LAST_D2: LATE_D2}), "complete_with_delayed"),
    ("unresolved earlier-nominal batch, C-min", lambda: World({}, drop_slots={PRE}), "incomplete"),
])
def test_both_layers_agree_and_neither_calls_incomplete_or_unvouched_evidence_verified_no_news(label, world, source):
    o, rows = agreement(world())
    assert o.assessment.source.value == source, label
    assert o.assessment.usability is not cp.IntervalUsability.USABLE, label
    for theme in THEMES:
        assert o.theme_evidence[theme].evidence == "unverified_empty", (label, theme)
        assert rows[theme].no_news is None and rows[theme].theme_evidence != "verified_zero_records", (label, theme)
        assert rows[theme].n_eligible in (None, 0) and rows[theme].mean_net is None                       # never a neutral or zero sentiment value
        assert rows[theme].result_availability in ("unavailable", "scoring_not_performed"), (label, theme)


def test_both_layers_agree_when_the_lookback_was_not_examined():
    w = World({})
    o, rows = agreement(w, earlier_batches_from=None)
    assert o.assessment.source is cp.SourceCompleteness.INCOMPLETE and o.assessment.earlier.not_examined
    assert all(r.coverage_status == "incomplete_source_accounting" and r.no_news is None for r in rows.values())


def test_f2_a_delayed_empty_batch_and_a_missing_batch_are_not_verified_no_news_in_either_layer():
    delayed_o, delayed_rows = agreement(World({}, avail={LAST_D2: LATE_D2}))
    assert delayed_rows["gold"].coverage_status == "ok"                                                   # the aggregator's provisional coverage rule is met...
    assert delayed_rows["gold"].no_news is None and delayed_rows["gold"].interval_usability == "undecided_policy"   # ...yet zero is not verified
    assert delayed_o.theme_evidence["gold"].reasons == ("complete_with_delayed",)
    missing_o, missing_rows = agreement(World({}, drop_slots={IN_D2}))
    assert missing_rows["gold"].coverage_status == "slot_grid_mismatch" and missing_rows["gold"].interval_usability == "unusable_incomplete"
    absent_o, absent_rows = agreement(World({}, state={IN_D2: "absent"}))                                 # 95/96 covered, above the supplied 0.75
    assert absent_rows["gold"].coverage_status == "ok" and absent_rows["gold"].no_news is None           # previously no_news = True
    assert absent_o.theme_evidence["gold"].reasons == ("final_gaps",)


def test_f2b_an_unknown_near_empty_indicator_is_unknown_in_both_layers():
    o, rows = agreement(World({}, near_empty=None))
    assert o.assessment.n_near_empty_unknown == 96 and o.assessment.n_near_empty == 0
    assert o.assessment.usability is cp.IntervalUsability.UNDECIDED_POLICY                              # previously "accounted_complete, verified no records"
    assert all("near_empty_unknown" in oe.reasons for oe in o.theme_evidence.values())
    r = rows["gold"]
    assert r.n_slots_near_empty_unknown == 96 and r.n_slots_near_empty == 0                                # unknown is not counted as near-empty
    assert r.coverage_status == "ok" and r.no_news is None and r.coverage == 0.0 and r.coverage_threshold_met is False   # unknown is uncovered; the ratio is informational, so the integrity rules decide
    assert o.status == "accounted_complete" and o.no_news_basis["gold"] == "unverified_empty_indicator"
    known_false = agreement(World({}, near_empty=0))[0]
    assert known_false.assessment.usability is cp.IntervalUsability.USABLE and known_false.no_news_basis["gold"] == "verified_complete_no_records"


def test_an_explicit_near_empty_slot_is_neither_a_missing_slot_nor_an_unknown_one():
    near, near_rows = agreement(World({}, row_over={IN_D2: {"near_empty_flag": 1}}))
    missing, _ = agreement(World({}, drop_slots={IN_D2}))
    unknown, _ = agreement(World({}, near_empty=None))
    assert (near.assessment.n_near_empty, near.assessment.n_near_empty_unknown, near.assessment.account_counts.get("missing", 0)) == (1, 0, 0)
    assert (missing.assessment.n_near_empty, missing.assessment.account_counts["missing"]) == (0, 1)
    assert unknown.assessment.n_near_empty == 0 and near.n_near_empty_slots == 1
    assert near_rows["gold"].n_slots_near_empty == 1 and near_rows["gold"].n_slots_near_empty_unknown == 0


def test_verified_records_for_one_theme_and_verified_zero_for_another_in_the_orchestrator():
    r = World({IN_D2: [{}], IN_D3: [{"member_gold": "1", "member_equity_us": "0"}]}).run()
    d2, d3 = r.interval(D2), r.interval(D3)
    assert d2.theme_evidence["equity_us"].evidence == "has_records" and d2.theme_evidence["gold"].evidence == "verified_zero_records"
    assert d3.theme_evidence["gold"].evidence == "has_records" and d3.theme_evidence["rates_us"].evidence == "verified_zero_records"
    assert d2.assessment.usability is cp.IntervalUsability.USABLE
    for iv in r.intervals:
        for e in iv.theme_evidence.values():
            assert e.result_availability == "blocked_by_policy"                                         # records exist, but the results are blocked


def test_scoring_not_performed_and_unresolved_policy_are_distinct_blocking_states():
    full = World({IN_D2: [{}]}).run().interval(D2).assessment
    assert cp.result_availability(full, cp.ThemeEvidence.HAS_RECORDS, policy_blocked=False, scoring_performed=False)[0] is cp.ResultAvailability.SCORING_NOT_PERFORMED
    assert cp.result_availability(full, cp.ThemeEvidence.HAS_RECORDS, policy_blocked=True, scoring_performed=False)[0] is cp.ResultAvailability.BLOCKED_BY_POLICY
    report = World({IN_D2: [{}]}).run()
    assert {e.result_availability for i in report.intervals for e in i.theme_evidence.values()} == {"blocked_by_policy"}
    assert "scorer_approval_and_polarity_validation" in {n for n, _ in report.policy_state().unresolved()}
    with pytest.raises(pol.PolicyBlockedError):                                                          # and the aggregator refuses the report's own status
        ft.aggregate_daily([], DAYS, {}, config=dataclasses.replace(CFG_AGG, policy=report.policy_state()), earlier=report.earlier_evidence())


def test_mixed_versions_leave_no_interval_usable_in_the_orchestrator_and_the_aggregator_refuses():
    base = World()
    d3 = [b for b in base.batches if b.startswith("20220303")]
    w = World({}, row_over={b: {"parser_version": "gkg_parser_v2"} for b in d3})
    r = w.run()
    assert all(i.assessment.usability is cp.IntervalUsability.UNUSABLE_INCOMPLETE for i in r.intervals)
    assert all(e.evidence == "unverified_empty" for i in r.intervals for e in i.theme_evidence.values())
    with pytest.raises(ft.SentimentFeatureError, match="different filter/parser versions"):
        aggregator_rows(w, r)


def test_the_orchestrator_report_and_the_aggregator_use_the_same_vocabulary_values():
    r = World({}).run()
    allowed = {m.value for m in cp.SourceCompleteness}
    assert {i.assessment.source.value for i in r.intervals} <= allowed
    row_ = aggregator_rows(World({}), r)[0]
    assert row_.source_completeness in allowed and row_.interval_usability in {m.value for m in cp.IntervalUsability}
    assert row_.theme_evidence in {m.value for m in cp.ThemeEvidence} and row_.result_availability in {m.value for m in cp.ResultAvailability}


def test_the_aggregator_requires_the_c_min_evidence_and_has_no_default():
    w = World({})
    by = ma.adapt_manifest(w.slot_rows, w.series_rows, filter_version=FV, expected_batches=w.batches).by_batch()
    grids = nominal_grids(w.days, interval_cutoffs(w.days, w.early))
    slots = {d: [by[b] for b in grids[d]] for d in grids}
    with pytest.raises(TypeError):
        ft.aggregate_daily([], w.days, slots, config=CFG_AGG)                                             # type: ignore[call-arg]
    with pytest.raises(ft.SentimentFeatureError, match="EarlierEvidence"):
        ft.aggregate_daily([], w.days, slots, config=CFG_AGG, earlier=None)                               # type: ignore[arg-type]
    unexamined = ft.aggregate_daily([], w.days, slots, config=CFG_AGG, earlier=cp.EarlierEvidence.not_examined())
    assert {r.coverage_status for r in unexamined} == {"incomplete_source_accounting"} and {r.no_news for r in unexamined} == {None}
    examined = ft.aggregate_daily([], w.days, slots, config=CFG_AGG, earlier=cp.EarlierEvidence.none_found())
    assert {r.coverage_status for r in examined} == {"ok"} and {r.no_news for r in examined} == {True}
