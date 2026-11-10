"""S2.5: the manifest -> SlotAccounting adapter and the day file -> candidate record adapter.

Synthetic fixtures only (no real titles, URLs, labels or keys), no scoring, no network. One test verifies both adapters against the
local B2-M sample **read-only** (it is skipped when the sample is absent); it takes a before/after (path, size, mtime) snapshot of the
whole sample tree and asserts nothing changed.
"""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
import random
import sqlite3
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.filters import load_spec
from wealthpilot.data.gdelt.output import COLUMNS, encode_rows
from wealthpilot.data.gdelt.sentiment import dayfile_adapter as da
from wealthpilot.data.gdelt.sentiment import manifest_adapter as ma
from wealthpilot.data.gdelt.sentiment import schema as sc
from wealthpilot.data.gdelt.sentiment import slots as sl
from wealthpilot.data.gdelt.timeutil import SLOT

ROOT = Path(__file__).resolve().parents[4]
SAMPLE = ROOT / "datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1"
UTC = timezone.utc
FV, PV = "gdelt_filter_v1", "gkg_parser_v1"
B1, B2, B3 = "20220302150000", "20220302153000", "20220302160000"
DAY = "2022-03-02"
MIN_CHARS = 20


def iso_avail(batch: str) -> str:
    return (datetime.strptime(batch, "%Y%m%d%H%M%S").replace(tzinfo=UTC) + SLOT).strftime("%Y-%m-%dT%H:%M:%SZ")


def mrow(batch: str = B1, **over):
    base = dict(batch_ts=batch, existence="present_verified", fetch_status="fetched", parse_status="parsed_validated",
                commit_status="committed", availability_status="verified", available_at_utc=iso_avail(batch),
                near_empty_flag=None, filter_version=FV, parser_version=PV, rows_physical=100, rows_malformed=2,
                rows_date_mismatch=0, rows_translated=0, rows_non_web=0, rows_english_valid=98, rows_captured=3,
                rows_company_item=1, rows_dup_same_batch=20, rows_audit_sample=1, availability_flags="", late_flag=0)
    return {**base, **over}


def srows(batch: str = B1, fv: str = FV, eq: int = 2, ra: int = 1, go: int = 0):
    return [dict(batch_ts=batch, filter_version=fv, series=s, rows=n, rows_us_relevant=n, new_stories=None)
            for s, n in (("EQUITY_US", eq), ("RATES_US", ra), ("GOLD", go))]


def adapt(slot_rows, series, **kw):
    return ma.adapt_manifest(slot_rows, series, filter_version=kw.pop("filter_version", FV), **kw)


def codes(result):
    return [r.code for r in result.rejections]


# ================================================================ Adapter A: manifest -> SlotAccounting

def test_a_valid_final_slot_becomes_a_processed_slot_with_provenance():
    r = adapt([mrow()], srows())
    assert r.ok and len(r.slots) == 1
    s = r.slots[0]
    assert s == sl.slot_from_manifest(mrow(), {"EQUITY_US": 2, "RATES_US": 1, "GOLD": 0})            # the existing validation, reused
    assert s.state == "processed" and s.rows_captured == 3 and s.theme_rows == {"equity_us": 2, "rates_us": 1, "gold": 0}
    src = r.sources[B1]
    assert src.filter_version == FV and src.stage_counts["rows_english_valid"] == 98 and src.stage_counts["rows_captured"] == 3
    assert src.stage_counts["rows_dup_same_batch"] == 20 and src.series_us_relevant == {"EQUITY_US": 2, "RATES_US": 1, "GOLD": 0}
    assert r.require_ok() is r and r.by_batch() == {B1: s}


def test_a_non_final_slot_is_accepted_as_non_final_and_never_as_processed():
    for state_over, state in ((dict(existence="available", fetch_status="in_progress", parse_status="pending", commit_status="pending"), "in_progress"),
                              (dict(existence="available", fetch_status="pending", parse_status="pending", commit_status="pending"), "verified_available"),
                              (dict(parse_status="parsed_validated", commit_status="pending"), "parsed_validated"),
                              (dict(existence="absent_confirmed", fetch_status="not_applicable", parse_status="not_applicable",
                                    commit_status="not_applicable"), "confirmed_absent")):
        r = adapt([mrow(**state_over)], [])
        assert r.ok and r.slots[0].state == state and not r.slots[0].processed and r.slots[0].rows_captured is None, state


def test_missing_required_fields_and_null_values_are_rejected_with_the_batch():
    for field in ("existence", "commit_status", "available_at_utc", "rows_captured", "filter_version", "rows_english_valid"):
        broken = {k: v for k, v in mrow().items() if k != field}
        r = adapt([broken], srows())
        assert not r.ok and r.slots == () and r.rejections[0].batch_ts == B1 and "missing" in r.rejections[0].code, field
    for field in ("available_at_utc", "rows_captured", "parser_version", "rows_physical"):
        r = adapt([mrow(**{field: None})], srows())
        assert "missing_value" in codes(r) and r.slots == (), field
    r = adapt([mrow(near_empty_flag=None)], srows())
    assert r.ok                                                                                      # null is the legitimate "unknown"
    assert codes(adapt([{k: v for k, v in mrow().items() if k != "batch_ts"}], srows())) == ["invalid_batch_ts", "series_rows_without_slot"]


def test_a_duplicate_batch_ts_is_ambiguous_and_every_copy_is_rejected():
    r = adapt([mrow(B1), mrow(B1, rows_captured=4), mrow(B2)], srows(B1) + srows(B2))
    assert [s.batch_ts for s in r.slots] == [B2]
    dup = [x for x in r.rejections if x.code == "duplicate_batch_ts"]
    assert len(dup) == 1 and dup[0].batch_ts == B1 and "2 slot rows" in dup[0].detail


def test_an_invalid_timestamp_or_state_is_rejected():
    for stamp in ("2022-03-02", "20220302150700", "20220302", None, 20220302150000):
        r = adapt([mrow(batch_ts=stamp)], [])
        assert r.slots == () and "invalid_batch_ts" in codes(r), stamp
    for over, code in ((dict(available_at_utc="2022-03-02 15:15"), "invalid_slot"), (dict(available_at_utc="2022-03-02T15:00:00Z"), "invalid_slot"),
                       (dict(availability_status="unverified"), "invalid_slot"), (dict(near_empty_flag=2), "invalid_slot"),
                       (dict(existence="available"), "inconsistent_state"), (dict(parse_status="pending"), "inconsistent_state")):
        r = adapt([mrow(**over)], srows())
        assert code in codes(r) and r.slots == (), over


def test_missing_and_wrong_version_series_counts_are_rejected_and_versions_never_mix():
    r = adapt([mrow()], [])
    assert codes(r) == ["missing_series"] and r.slots == ()
    r = adapt([mrow()], srows()[:2])                                                                 # GOLD absent
    assert codes(r) == ["missing_series"] and "GOLD" not in r.rejections[0].detail.split("need")[0]
    old_only = adapt([mrow()], srows(fv="gdelt_filter_v0"))                                          # another version only
    assert codes(old_only) == ["missing_series"] and "only for other versions" in old_only.rejections[0].detail
    mixed = adapt([mrow()], srows(fv="gdelt_filter_v0", eq=99, ra=99, go=99) + srows())              # both present: the requested one is used
    assert mixed.ok and mixed.slots[0].theme_rows == {"equity_us": 2, "rates_us": 1, "gold": 0}
    assert mixed.sources[B1].series_versions_seen == ("gdelt_filter_v0", FV)
    wrong_slot = adapt([mrow(filter_version="gdelt_filter_v0")], srows())                           # the slot is another version
    assert "filter_version_differs" in codes(wrong_slot) and wrong_slot.slots == ()
    assert adapt([mrow(filter_version="gdelt_filter_v0")], srows(fv="gdelt_filter_v0"), filter_version="gdelt_filter_v0").ok


def test_duplicate_unknown_and_malformed_series_rows_are_rejected():
    dup = adapt([mrow()], srows() + srows()[:1])
    assert "duplicate_series_row" in codes(dup) and "ambiguous_series_rows" in codes(dup) and dup.slots == ()
    assert "unknown_series" in codes(adapt([mrow()], srows() + [dict(srows()[0], series="OTHER")]))
    assert "missing_field" in codes(adapt([mrow()], [{k: v for k, v in srows()[0].items() if k != "rows"}] + srows()[1:]))
    assert "invalid_series_row" in codes(adapt([mrow()], [dict(srows()[0], batch_ts="bad")] + srows()[1:]))
    for bad in (-1, 1.5, True, None, "2"):
        assert "invalid_series_count" in codes(adapt([mrow()], [dict(srows()[0], rows=bad)] + srows()[1:])), bad
    over = [dict(srows()[0], rows=2, rows_us_relevant=3)] + srows()[1:]
    assert "inconsistent_series_count" in codes(adapt([mrow()], over))


def test_inconsistent_captured_and_stage_counts_are_rejected_but_unequal_stages_are_not():
    for over, text in ((dict(rows_captured=99), "rows_captured exceeds rows_english_valid"),
                       (dict(rows_company_item=4), "rows_company_item exceeds rows_captured"),
                       (dict(rows_audit_sample=96), "audit_sample + captured"),
                       (dict(rows_dup_same_batch=99), "rows_dup_same_batch exceeds"),
                       (dict(rows_physical=90), "disjoint line classes")):
        r = adapt([mrow(**over)], srows())
        assert "inconsistent_count" in codes(r) and any(text in x.detail for x in r.rejections) and r.slots == (), over
    for bad in (-1, 2.0, True, "3"):
        assert "invalid_count" in codes(adapt([mrow(rows_captured=bad)], srows())), bad
    # different stages are different quantities: nothing requires them to be equal
    ok = adapt([mrow(rows_physical=5000, rows_english_valid=4000, rows_captured=3, rows_dup_same_batch=900, rows_company_item=0)],
               srows(eq=2, ra=2, go=2))                                                              # series rows exceed captured, duplicates differ
    assert ok.ok and ok.slots[0].rows_captured == 3 and ok.slots[0].theme_rows == {"equity_us": 2, "rates_us": 2, "gold": 2}


def test_expected_batches_and_orphan_series_rows_are_reported():
    r = adapt([mrow(B1), mrow(B3)], srows(B1) + srows(B3) + srows(B2), expected_batches=[B1, B2])
    assert [s.batch_ts for s in r.slots] == [B1]
    assert {(x.batch_ts, x.code) for x in r.rejections} == {(B2, "missing_manifest_row"), (B3, "unexpected_batch"),
                                                          (B2, "series_rows_without_slot")}
    with pytest.raises(ma.ManifestAdapterError):
        r.require_ok()
    with pytest.raises(ma.ManifestAdapterError):
        adapt([mrow()], srows(), expected_batches=["bad"])


def test_calls_with_the_wrong_argument_types_raise_instead_of_guessing():
    for slot_rows, series in ((iter([mrow()]), []), ([mrow()], iter([])), ([("x",)], []), (mrow(), [])):
        with pytest.raises(ma.ManifestAdapterError):
            ma.adapt_manifest(slot_rows, series, filter_version=FV)                                  # type: ignore[arg-type]
    for fv in ("", None, 3):
        with pytest.raises(ma.ManifestAdapterError):
            ma.adapt_manifest([mrow()], srows(), filter_version=fv)                                  # type: ignore[arg-type]


def test_the_manifest_adaptation_is_deterministic_and_input_order_free():
    rows = [mrow(B3), mrow(B1), mrow(B2, existence="absent_confirmed", fetch_status="not_applicable",
                                    parse_status="not_applicable", commit_status="not_applicable"), mrow(B1, batch_ts="bad")]
    series = srows(B1) + srows(B3) + srows("20220302170000")
    first = adapt(rows, series)
    rng = random.Random(42)
    for _ in range(5):
        a, b = rows[:], series[:]
        rng.shuffle(a), rng.shuffle(b)
        assert adapt(a, b) == first
    assert [s.batch_ts for s in first.slots] == sorted(s.batch_ts for s in first.slots)
    assert list(first.rejections) == sorted(first.rejections, key=ma.Rejection.sort_key)
    assert {x.code for x in first.rejections} == {"invalid_batch_ts", "series_rows_without_slot"}


# ================================================================ Adapter B: day file -> candidate records

def drow(batch: str, seq: int, **over):
    base = {c: "" for c in COLUMNS}
    base.update(row_kind="captured", gkg_record_id=f"{batch}-{seq}", batch_ts=batch, available_at_utc=iso_avail(batch),
                source_domain="example.invalid", document_url=f"https://example.invalid/{seq}", url_canonical=f"example.invalid/{seq}",
                page_title=f"SYNTHETIC headline number {seq} about nothing real", title_hash=hashlib.sha256(f"h{seq}".encode()).hexdigest(),
                tone="0", word_count="100", us_location="0", us_relevant="0", company_item="0", member_equity_us="1",
                member_rates_us="0", member_gold="0", mech_dup="ORIGINAL", near_miss_cue="0", filter_version=FV, parser_version=PV)
    base.update(over)
    return base


def dbytes(rows, *, header=True):
    body = encode_rows([[r[c] for c in COLUMNS] for r in rows], header=header)
    return gzip.compress(body, mtime=0)


def slots_for(*batches, **over):
    rows = [mrow(b, **over) for b in batches]
    series = [s for b in batches for s in srows(b)]
    res = adapt(rows, series)
    assert res.ok
    return res.by_batch()


def parse(rows, slots=None, **kw):
    return da.adapt_day_file(dbytes(rows), utc_day=kw.pop("utc_day", DAY), slots=slots or slots_for(B1, B2), min_chars=MIN_CHARS,
                             source_name="synthetic/2022-03-02.tsv.gz", **kw)


def test_a_valid_multi_theme_record_keeps_identity_availability_and_provenance():
    rec = parse([drow(B1, 1, member_rates_us="1", company_item="1", mech_dup="SYNDICATED_SAME_BATCH")]).records[0]
    assert rec.article_id == f"{B1}-1" and rec.batch_ts == B1 and rec.theme_flags == {"equity_us": True, "rates_us": True, "gold": False}
    assert rec.available_at_utc == datetime(2022, 3, 2, 15, 15, tzinfo=UTC) and rec.availability_status == "verified"
    assert rec.source_domain == "example.invalid" and rec.company_item is True and rec.same_batch_status == "SYNDICATED_SAME_BATCH"
    assert (rec.filter_version, rec.parser_version, rec.source_file, rec.source_line) == (FV, PV, "synthetic/2022-03-02.tsv.gz", 2)
    assert rec.text_status == "ok" and rec.word_count == "100" and rec.url_canonical == "example.invalid/1"
    assert "SYNTHETIC" not in repr(rec) and "example.invalid/1" not in repr(rec)                     # titles and URLs stay out of logs


def test_a_candidate_is_unscored_and_has_no_story_identity_or_prediction():
    names = {f.name for f in dataclasses.fields(da.CandidateRecord)}
    for forbidden in ("story_id", "dup_status", "pred_label", "p_positive", "p_negative", "p_neutral", "model_id", "scorer_code_sha256",
                      "scored_at_utc", "page_pub_ts_utc"):
        assert forbidden not in names, forbidden
    assert not isinstance(parse([drow(B1, 1)]).records[0], sc.ArticleRecord)


def test_the_raw_title_hash_and_the_filter_hash_are_kept_apart():
    filt = hashlib.sha256(b"normalised form").hexdigest()
    rec = parse([drow(B1, 1, page_title="Some SYNTHETIC Title, Mixed Case!", title_hash=filt)]).records[0]
    assert rec.title_sha256_raw == sc.title_sha256("Some SYNTHETIC Title, Mixed Case!") and rec.filter_title_hash == filt
    assert rec.title_sha256_raw != rec.filter_title_hash
    assert parse([drow(B1, 1, title_hash="")]).records[0].filter_title_hash is None                  # empty stays empty, never the raw hash


def test_empty_short_and_malformed_titles_are_kept_with_an_explicit_state():
    res = parse([drow(B1, 1, page_title="", title_hash=""), drow(B1, 2, page_title="short"), drow(B1, 3, page_title="bad\x07title long enough here"),
                 drow(B1, 4)])
    assert res.ok and [r.text_status for r in res.records] == ["empty", "short", "malformed", "ok"]
    assert res.records[0].title_sha256_raw == sc.title_sha256("") and res.records[0].filter_title_hash is None


def test_invalid_and_malformed_rows_are_rejected_with_line_and_record_id():
    short_row = "\t".join(["captured", f"{B1}-9"]).encode()
    res = da.adapt_day_file(gzip.compress(encode_rows([], header=True) + short_row + b"\n", mtime=0), utc_day=DAY, slots=slots_for(B1),
                            min_chars=MIN_CHARS, source_name="s")
    assert [(r.code, r.line, r.record_id) for r in res.rejections] == [("wrong_column_count", 2, f"{B1}-9")] and res.records == ()
    cases = {
        "invalid_record_id": drow(B1, 1, gkg_record_id="not-an-id"),
        "record_id_batch_mismatch": drow(B1, 1, gkg_record_id=f"{B2}-1"),
        "row_kind_not_captured": drow(B1, 1, row_kind="audit"),
        "invalid_flag": drow(B1, 1, member_gold="yes"),
        "unknown_same_batch_status": drow(B1, 1, mech_dup="REOBSERVATION"),                         # a cross-batch status is not invented here
        "invalid_title_hash": drow(B1, 1, title_hash="xyz"),
        "invalid_available_at": drow(B1, 1, available_at_utc="2022-03-02 15:15"),
        "invalid_batch_ts": drow(B1, 1, batch_ts="2022-03-02"),
    }
    for code, row in cases.items():
        res = parse([row])
        assert res.records == () and code in [r.code for r in res.rejections] and not res.ok, code
        assert all(r.line == 2 for r in res.rejections)


def test_missing_required_provenance_is_rejected_by_field_name():
    for field in ("gkg_record_id", "batch_ts", "available_at_utc", "filter_version", "parser_version", "source_domain"):
        res = parse([drow(B1, 1, **{field: ""})])
        assert res.records == () and any(r.code == "missing_required_field" and r.detail == field for r in res.rejections), field


def test_availability_and_versions_must_equal_the_manifest_slot():
    res = parse([drow(B1, 1, available_at_utc="2022-03-02T15:16:00Z")])
    assert [r.code for r in res.rejections] == ["availability_differs_from_manifest"] and res.records == ()
    assert [r.code for r in parse([drow(B1, 1, filter_version="gdelt_filter_v0")]).rejections] == ["version_differs_from_manifest"]
    assert [r.code for r in parse([drow(B1, 1, parser_version="gkg_parser_v0")]).rejections] == ["version_differs_from_manifest"]
    assert [r.code for r in parse([drow(B3, 1)]).rejections] == ["batch_not_in_manifest"]
    not_processed = slots_for(B1) | {B2: sl.SlotAccounting(B2, "in_progress")}
    assert [r.code for r in parse([drow(B2, 1)], not_processed).rejections] == ["batch_slot_not_processed"]
    assert [r.code for r in parse([drow("20220303150000", 1, available_at_utc="2022-03-03T15:15:00Z")]).rejections] == [
        "batch_not_in_file_day", "batch_not_in_manifest"]


def test_duplicate_record_ids_reject_every_copy_and_keep_the_other_rows():
    res = parse([drow(B1, 1), drow(B1, 2), drow(B1, 1, page_title="another title that is long enough")])
    assert [r.article_id for r in res.records] == [f"{B1}-2"]
    dups = [r for r in res.rejections if r.code == "duplicate_record_id"]
    assert [r.line for r in dups] == [2, 4] and not res.ok
    a, b = parse([drow(B1, 1)]), parse([drow(B1, 1)], utc_day=DAY)
    assert da.find_duplicate_record_ids([a, b]) == (f"{B1}-1",) and da.find_duplicate_record_ids([a]) == ()


def test_several_batches_in_one_file_and_repeats_across_batches_are_kept_without_any_dedup():
    same_hash = hashlib.sha256(b"same story").hexdigest()
    res = parse([drow(B1, 1, url_canonical="example.invalid/shared", title_hash=same_hash),
                 drow(B2, 1, url_canonical="example.invalid/shared", title_hash=same_hash),
                 drow(B2, 2, url_canonical="example.invalid/shared", title_hash=same_hash)])
    assert res.ok and len(res.records) == 3 and {r.batch_ts for r in res.records} == {B1, B2}
    assert {r.filter_title_hash for r in res.records} == {same_hash} and {r.url_canonical for r in res.records} == {"example.invalid/shared"}
    assert {r.same_batch_status for r in res.records} == {"ORIGINAL"}                                # no REOBSERVATION / SYNDICATED invented
    assert not any(hasattr(r, "story_id") for r in res.records)


def test_output_is_sorted_and_identical_across_runs_and_input_order():
    rows = [drow(B2, 10), drow(B1, 2), drow(B2, 3), drow(B1, 11)]
    first = parse(rows)
    assert [r.article_id for r in first.records] == [f"{B1}-2", f"{B1}-11", f"{B2}-3", f"{B2}-10"]   # numeric sequence, not text order
    assert parse(rows) == first
    unlined = lambda res: [dataclasses.replace(r, source_line=0) for r in res.records]               # the line number is where it was found
    assert unlined(parse(list(reversed(rows)))) == unlined(first)
    assert first.file_sha256 == hashlib.sha256(dbytes(rows)).hexdigest()


def test_the_header_is_validated_before_any_row_is_read():
    wrong = gzip.compress(encode_rows([[r[c] for c in COLUMNS] for r in [drow(B1, 1)]], header=False), mtime=0)   # no header row
    assert [r.code for r in da.adapt_day_file(wrong, utc_day=DAY, slots=slots_for(B1), min_chars=MIN_CHARS, source_name="s").rejections] == ["header_mismatch"]
    swapped = list(COLUMNS)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    body = ("\t".join(swapped) + "\n").encode() + encode_rows([[drow(B1, 1)[c] for c in COLUMNS]])
    res = da.adapt_day_file(gzip.compress(body, mtime=0), utc_day=DAY, slots=slots_for(B1), min_chars=MIN_CHARS, source_name="s")
    assert [r.code for r in res.rejections] == ["header_mismatch"] and res.records == () and res.rows_read == 0
    assert [r.code for r in da.adapt_day_file(b"not gzip", utc_day=DAY, slots={}, min_chars=MIN_CHARS, source_name="s").rejections] == ["file_unreadable"]
    bad_utf8 = gzip.compress(b"\xff\xfe\n", mtime=0)
    assert [r.code for r in da.adapt_day_file(bad_utf8, utc_day=DAY, slots={}, min_chars=MIN_CHARS, source_name="s").rejections] == ["file_unreadable"]


def commit_for(rows, **over):
    base = dict(utc_day=DAY, status="committed", filter_version=FV, parser_version=PV, rows_kept=len(rows),
                file_sha256=hashlib.sha256(dbytes(rows)).hexdigest())
    return {**base, **over}


def test_the_day_commit_checks_hash_status_day_versions_and_row_count():
    rows = [drow(B1, 1), drow(B2, 1)]
    ok = parse(rows, day_commit=commit_for(rows))
    assert ok.ok and ok.integrity_checked and len(ok.records) == 2
    assert not parse(rows).integrity_checked
    for over, code in ((dict(file_sha256="0" * 64), "file_sha256_mismatch"), (dict(status="superseded"), "day_commit_not_committed"),
                       (dict(utc_day="2022-03-03"), "day_commit_day_mismatch"), (dict(rows_kept=3), "rows_kept_mismatch"),
                       (dict(filter_version="gdelt_filter_v0"), "version_differs_from_day_commit")):
        res = parse(rows, day_commit=commit_for(rows, **over))
        assert code in [r.code for r in res.rejections] and not res.ok, code
        if code in ("file_sha256_mismatch", "day_commit_not_committed", "day_commit_day_mismatch"):
            assert res.records == ()                                                                  # an untrusted file yields no records
    assert [r.code for r in parse(rows, day_commit={k: v for k, v in commit_for(rows).items() if k != "rows_kept"}).rejections] == [
        "day_commit_missing_field"]


def test_wrong_calls_raise_instead_of_guessing():
    base = dict(utc_day=DAY, slots=slots_for(B1), min_chars=MIN_CHARS, source_name="s")
    for over in (dict(utc_day="2022/03/02"), dict(slots=[1]), dict(slots={B1: "processed"}), dict(min_chars=0), dict(min_chars=True),
                 dict(source_name="")):
        with pytest.raises(ma.ManifestAdapterError):
            da.adapt_day_file(dbytes([drow(B1, 1)]), **{**base, **over})
    with pytest.raises(ma.ManifestAdapterError):
        da.adapt_day_file("text", **base)                                                            # type: ignore[arg-type]


def test_candidates_reconcile_with_their_slot_through_the_existing_contract():
    rows = [drow(B1, 1), drow(B1, 2, member_equity_us="0", member_rates_us="1"), drow(B1, 3, member_equity_us="0")]
    slots = adapt([mrow(B1, rows_captured=3)], srows(B1, eq=1, ra=1, go=0)).by_batch()
    res = parse(rows, slots)
    assert res.ok and sl.reconcile_slot(slots[B1], res.records) == []
    wrong = adapt([mrow(B1, rows_captured=4)], srows(B1, eq=1, ra=1, go=0)).by_batch()
    assert any("rows_captured 4 but 3" in p for p in sl.reconcile_slot(wrong[B1], res.records))


def test_the_adapters_are_not_wired_into_production_or_scoring():
    pkg = ROOT / "backend/wealthpilot/data/gdelt/sentiment"
    for name in ("manifest_adapter.py", "dayfile_adapter.py"):
        text = (pkg / name).read_text(encoding="utf-8")
        for word in ("fake_scorer", "FakeScorer", "transformers", "torch", "sqlite3", "urllib", "socket", "subprocess", "os.environ",
                     "aggregate_daily", "key_sealed", "annotation_", "ai_only"):
            assert word not in text, (name, word)


# ================================================================ read-only verification against the local B2-M sample

def tree_snapshot(base: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(base.rglob("*")):
        if p.is_file():
            st = p.stat()
            h.update(f"{p.relative_to(base).as_posix()}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


@pytest.mark.skipif(not (SAMPLE / "manifest" / "manifest.sqlite").exists(), reason="the local B2-M sample is not present")
def test_both_adapters_over_the_real_local_sample_read_only():
    before = tree_snapshot(SAMPLE)
    db = sqlite3.connect(f"file:{(SAMPLE / 'manifest' / 'manifest.sqlite').as_posix()}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    slot_rows = [dict(r) for r in db.execute("SELECT * FROM slot")]
    series = [dict(r) for r in db.execute("SELECT * FROM slot_series_count")]
    commits = [dict(r) for r in db.execute("SELECT * FROM day_commit ORDER BY utc_day")]
    db.close()
    min_chars = int(load_spec().raw["title_hash_min_chars"])

    first = ma.adapt_manifest(slot_rows, series, filter_version="gdelt_filter_v1", expected_batches=sorted(r["batch_ts"] for r in slot_rows))
    assert first.ok and len(first.slots) == 192 and all(s.processed for s in first.slots)
    assert first == ma.adapt_manifest(slot_rows, series, filter_version="gdelt_filter_v1", expected_batches=sorted(r["batch_ts"] for r in slot_rows))
    by_batch = first.by_batch()

    def run():
        results = []
        for c in commits:
            data = (SAMPLE / c["file_relpath"]).read_bytes()
            results.append(da.adapt_day_file(data, utc_day=c["utc_day"], slots=by_batch, min_chars=min_chars,
                                             source_name=c["file_relpath"], day_commit=c))
        return results

    results = run()
    assert len(results) == 170 and all(r.ok and r.integrity_checked for r in results), [r.rejections[:2] for r in results if not r.ok][:1]
    records = [rec for r in results for rec in r.records]
    assert len(records) == sum(c["rows_kept"] for c in commits) == 26854 and da.find_duplicate_record_ids(results) == ()
    per_batch: dict[str, list] = {}
    for rec in records:
        per_batch.setdefault(rec.batch_ts, []).append(rec)
    assert set(per_batch) == set(by_batch)                                                           # every batch traced, none unmatched
    assert all(sl.reconcile_slot(by_batch[b], per_batch[b]) == [] for b in by_batch)                 # captured and per-theme counts: 192 / 192
    assert all(sl.reconcile_slot(by_batch[b], per_batch[b], company_evidence=True) == [] for b in by_batch)   # and company items: 192 / 192
    assert sum(s.rows_company_item for s in by_batch.values()) == sum(r.company_item for r in records) == 1560
    assert all(rec.available_at_utc == by_batch[rec.batch_ts].available_at_utc for rec in records)
    assert sum(1 for rec in records if rec.text_status != "ok") > 0 and {r.text_status for r in records} <= set(sc.TEXT_STATUSES)
    assert run() == results                                                                          # deterministic across runs
    assert tree_snapshot(SAMPLE) == before                                                           # nothing in the sample changed


# ================================================================ S2.8B: F5 (adapter level) and F3 (slot level)

@pytest.mark.parametrize("bad", ["2022-03-02", "20220302150700", "", "ABCDEFGHIJKLMN", "20221399000000"])
def test_an_invalid_batch_ts_is_rejected_specifically_and_never_looked_up_in_the_manifest(bad):
    res = parse([drow(B1, 1, batch_ts=bad)])
    found = [r.code for r in res.rejections]
    assert "invalid_batch_ts" in found and res.records == ()
    assert not {"batch_not_in_manifest", "batch_slot_not_processed", "availability_differs_from_manifest", "version_differs_from_manifest",
                "batch_not_in_file_day"} & set(found)
    assert all(r.batch_ts is None for r in res.rejections)                                           # no batch is claimed for an invalid stamp


def test_a_valid_stamp_that_is_not_in_the_manifest_is_still_reported_with_its_batch():
    res = parse([drow(B3, 1)])
    assert [(r.code, r.batch_ts) for r in res.rejections] == [("batch_not_in_manifest", B3)]


def test_rows_company_item_is_validated_on_a_slot_and_carried_from_the_manifest():
    series = {"EQUITY_US": 2, "RATES_US": 1, "GOLD": 0}
    ok = sl.slot_from_manifest(mrow(B1, rows_company_item=2), series)
    assert ok.rows_company_item == 2 and sl.slot_from_manifest(mrow(B1, rows_company_item=None), series).rows_company_item is None
    assert adapt([mrow(B1, rows_company_item=2)], srows(B1)).slots[0].rows_company_item == 2
    base = dict(batch_ts=IN_B, state="processed", available_at_utc=datetime(2022, 3, 2, 15, 15, tzinfo=UTC), rows_captured=3,
                theme_rows={"equity_us": 1, "rates_us": 0, "gold": 0}, filter_version=FV, parser_version=PV)
    for bad in (-1, 4, True, 1.0, "1"):
        with pytest.raises(sl.SentimentSlotError):
            sl.SlotAccounting(**base, rows_company_item=bad)
    with pytest.raises(sl.SentimentSlotError):
        sl.SlotAccounting(IN_B, "confirmed_absent", rows_company_item=0)                             # no counts on a non-processed slot


IN_B = "20220302150000"


def test_company_reconciliation_is_explicit_and_never_a_silent_pass():
    rec = lambda company: types.SimpleNamespace(article_id="a", theme_flags={"equity_us": True, "rates_us": False, "gold": False},
                                                availability_status="verified", available_at_utc=datetime(2022, 3, 2, 15, 15, tzinfo=UTC),
                                                company_item=company)
    slot = lambda n: sl.SlotAccounting(IN_B, "processed", datetime(2022, 3, 2, 15, 15, tzinfo=UTC), 2,
                                       {"equity_us": 2, "rates_us": 0, "gold": 0}, None, FV, PV, n)
    recs = [rec(True), rec(False)]
    assert sl.reconcile_slot(slot(1), recs, company_evidence=True) == []
    assert any("rows_company_item 0 but 1" in p for p in sl.reconcile_slot(slot(0), recs, company_evidence=True))
    assert any("rows_company_item 2 but 1" in p for p in sl.reconcile_slot(slot(2), recs, company_evidence=True))
    assert any("no rows_company_item" in p for p in sl.reconcile_slot(slot(None), recs, company_evidence=True))     # no evidence on the slot
    no_flag = [types.SimpleNamespace(**{k: v for k, v in vars(r).items() if k != "company_item"}) for r in recs]
    assert any("carry no company_item flag" in p for p in sl.reconcile_slot(slot(1), no_flag, company_evidence=True))   # no evidence on the records
    assert sl.reconcile_slot(slot(0), recs) == []                                                    # not requested: the existing contract is unchanged
