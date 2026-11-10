"""Incremental ZIP/CSV parsing, malformed and truncated archives, checksums and bounded memory."""

from __future__ import annotations

import hashlib
import tracemalloc
import zipfile

import pytest

from wealthpilot.data.gdelt.coverage import REASON_BELOW_THRESHOLD, REASON_NO_SLOTS, SlotSummary, interval_count
from wealthpilot.data.gdelt.errors import IntegrityError
from wealthpilot.data.gdelt.integrity import check_body, md5_from_etag, open_member
from wealthpilot.data.gdelt.parser import RowCounts, iter_rows

STAMP = "20220301120000"
LIM = {"max_uncompressed": 400_000_000, "max_ratio": 10.0}


def parse(body: bytes, *, max_line: int = 8 * 1024 * 1024, stamp: str = STAMP, max_ratio: float = 10.0):
    # synthetic rows repeat text and compress far better than GDELT's ~3.1x; tests not about the ratio
    # guard pass a looser ratio explicitly
    archive, info = open_member(body, stamp, max_uncompressed=LIM["max_uncompressed"], max_ratio=max_ratio)
    counts = RowCounts()
    with archive.open(info) as stream:
        rows = list(iter_rows(stream, stamp, counts, max_line_bytes=max_line, max_uncompressed=LIM["max_uncompressed"]))
    return rows, counts


def test_valid_rows_parse_with_decoded_titles(gkg):
    lines = [gkg.row(STAMP, 1, title="SYNTHETIC TEST ROW: S&amp;P 500 &quot;placeholder&quot;", pubts="20220301101500"),
             gkg.row(STAMP, 2)]
    rows, counts = parse(gkg.zip(STAMP, lines))
    assert [r.seq for r in rows] == [1, 2]
    assert rows[0].title == 'SYNTHETIC TEST ROW: S&P 500 "placeholder"'
    assert rows[0].page_pub_ts == "20220301101500"
    assert counts.english_valid == 2 and counts.malformed == 0 and not counts.missing_final_newline


def test_each_rejection_reason_is_counted_and_parsing_continues(gkg):
    good = gkg.row(STAMP, 1)
    lines = [
        good,
        gkg.row(STAMP, 2, n_fields=26),                         # field count
        gkg.row(STAMP, 3, n_fields=28),
        gkg.row(STAMP, 4, date="20220301121500"),               # V2.1DATE mismatch
        gkg.row(STAMP, 5, record_id="20220301121500-5"),        # record-ID prefix mismatch
        gkg.row(STAMP, 6, translation="srclc:fra;eng:Moses"),   # translated
        gkg.row(STAMP, 7, record_id=f"{STAMP}-T7"),             # translated-record marker
        gkg.row(STAMP, 8, collection="2"),                      # not web
        "",                                                     # empty line
        gkg.row(STAMP, 9),
    ]
    body = ("\n".join(lines) + "\n").encode("utf-8")
    body = body.replace(b"\n" + gkg.row(STAMP, 9).encode(), b"\n" + gkg.row(STAMP, 9).encode() + b"\r")
    bad_utf8 = gkg.row(STAMP, 10).encode().replace(b"neutral", b"neutr\xff\xfel")
    rows, c = parse(gkg.zip(STAMP, body + bad_utf8 + b"\n"))
    assert [r.seq for r in rows] == [1, 9]
    assert (c.field_count_errors, c.date_mismatch, c.translated, c.non_web, c.empty_lines, c.decode_errors,
            c.crlf_lines) == (2, 2, 2, 1, 1, 1, 1)
    assert c.physical_lines == 11


def test_missing_final_newline_still_parses_last_row(gkg):
    rows, c = parse(gkg.zip(STAMP, [gkg.row(STAMP, 1), gkg.row(STAMP, 2)], final_newline=False))
    assert len(rows) == 2 and c.missing_final_newline


def test_oversize_line_is_skipped_with_bounded_buffer(gkg):
    huge = gkg.row(STAMP, 2, title="SYNTHETIC " + "x" * 5000)
    rows, c = parse(gkg.zip(STAMP, [gkg.row(STAMP, 1), huge, gkg.row(STAMP, 3)]), max_line=2000, max_ratio=1000)
    assert [r.seq for r in rows] == [1, 3] and c.oversize_lines == 1


@pytest.mark.parametrize("kwargs,status", [
    ({"extra_members": 1}, "member_unexpected"),
    ({"member": "20220301121500.gkg.csv"}, "member_unexpected"),
    ({"member": "../20220301120000.gkg.csv"}, "member_unexpected"),
    ({"member": "sub/20220301120000.gkg.csv"}, "member_unexpected"),
])
def test_unexpected_members_are_refused(gkg, kwargs, status):
    with pytest.raises(IntegrityError) as e:
        open_member(gkg.zip(STAMP, [gkg.row(STAMP, 1)], **kwargs), STAMP, **LIM)
    assert e.value.status == status


def test_not_a_zip_and_truncated_zip_are_invalid(gkg):
    body = gkg.zip(STAMP, [gkg.row(STAMP, 1)])
    for bad in (b"not a zip at all", body[: len(body) // 2]):
        with pytest.raises(IntegrityError) as e:
            open_member(bad, STAMP, **LIM)
        assert e.value.status == "zip_invalid"


def test_encrypted_flag_and_unsupported_compression_are_invalid(gkg):
    body = bytearray(gkg.zip(STAMP, [gkg.row(STAMP, 1)]))
    cd = body.find(b"PK\x01\x02")
    body[cd + 8] |= 0x01                                        # central-directory "encrypted" bit
    with pytest.raises(IntegrityError) as e:
        open_member(bytes(body), STAMP, **LIM)
    assert e.value.status == "zip_invalid"
    bz = gkg.zip(STAMP, [gkg.row(STAMP, 1)], compression=zipfile.ZIP_BZIP2)
    with pytest.raises(IntegrityError) as e:
        open_member(bz, STAMP, **LIM)
    assert e.value.status == "zip_invalid"


def test_crc_corruption_is_detected_only_after_reading_and_nothing_survives(gkg):
    data = ("\n".join(gkg.row(STAMP, i) for i in range(1, 50)) + "\n").encode()
    body = bytearray(gkg.zip(STAMP, data, compression=zipfile.ZIP_STORED))
    pos = body.find(b"SYNTHETIC TEST ROW", len(body) // 2)
    body[pos] ^= 0x20                                           # flip one byte in the stored data
    with pytest.raises(IntegrityError) as e:
        parse(bytes(body))
    assert e.value.status == "crc_failed"


def test_corrupt_deflate_stream_is_an_integrity_error(gkg):
    body = bytearray(gkg.zip(STAMP, [gkg.row(STAMP, i) for i in range(1, 200)]))
    start = body.find(b".gkg.csv") + len(".gkg.csv")
    for i in range(start + 20, start + 60):
        body[i] ^= 0xFF
    with pytest.raises(IntegrityError):
        parse(bytes(body))


def test_zip_bomb_is_refused_from_the_header(gkg):
    bomb = gkg.zip(STAMP, b"0" * 5_000_000)
    with pytest.raises(IntegrityError) as e:
        open_member(bomb, STAMP, **LIM)
    assert e.value.status == "size_guard_exceeded"
    with pytest.raises(IntegrityError):
        open_member(gkg.zip(STAMP, [gkg.row(STAMP, 1)]), STAMP, max_uncompressed=100, max_ratio=10.0)


def test_md5_size_and_truncation_checks(gkg):
    body = gkg.zip(STAMP, [gkg.row(STAMP, 1)])
    md5 = hashlib.md5(body).hexdigest()
    ok = check_body(body, content_length=len(body), expected_bytes=len(body), expected_md5=md5, md5_source="etag")
    assert ok.checksum_basis == "md5_etag" and ok.md5 == md5
    assert check_body(body, content_length=None, expected_bytes=None, expected_md5=None,
                      md5_source=None).checksum_basis == "crc_and_size_only"
    cases = [
        ({"content_length": len(body) + 10, "expected_bytes": None, "expected_md5": None}, "body_incomplete"),
        ({"content_length": None, "expected_bytes": len(body) + 1, "expected_md5": None}, "size_mismatch"),
        ({"content_length": len(body), "expected_bytes": len(body), "expected_md5": "0" * 32}, "md5_mismatch"),
    ]
    for kwargs, status in cases:
        with pytest.raises(IntegrityError) as e:
            check_body(body, md5_source="master_list", **kwargs)
        assert e.value.status == status


@pytest.mark.parametrize("etag,expected", [
    ('"3aeaea3ff1a8d92ee9dd27fab54190e6"', "3aeaea3ff1a8d92ee9dd27fab54190e6"),
    ("3AEAEA3FF1A8D92EE9DD27FAB54190E6", "3aeaea3ff1a8d92ee9dd27fab54190e6"),
    ('W/"3aeaea3ff1a8d92ee9dd27fab54190e6"', None),
    ('"3aeaea3ff1a8d92ee9dd27fab54190e6-4"', None),
    (None, None), ("", None),
])
def test_etag_is_a_checksum_only_when_a_plain_md5(etag, expected):
    assert md5_from_etag(etag) == expected


def test_parsing_memory_stays_bounded(gkg):
    rows = [gkg.row(STAMP, i, title=f"SYNTHETIC TEST ROW {i} " + "y" * 400) for i in range(1, 40_001)]
    body = gkg.zip(STAMP, rows)                                 # ~20 MB uncompressed
    del rows
    archive, info = open_member(body, STAMP, max_uncompressed=LIM["max_uncompressed"], max_ratio=1000)
    assert info.file_size > 15_000_000
    tracemalloc.start()
    n = 0
    with archive.open(info) as stream:
        for _ in iter_rows(stream, STAMP, RowCounts(), max_line_bytes=8 * 1024 * 1024, max_uncompressed=10**9):
            n += 1
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert n == 40_000 and peak < 8_000_000, peak


# ---------------------------------------------------------------- missing versus neutral

def test_missing_news_is_never_a_zero():
    covered = SlotSummary(processed=True, near_empty=False, series_rows=0)
    assert interval_count([covered] * 4, 0.75).value == 0                      # a real, covered zero
    missing = SlotSummary(processed=False, near_empty=None, series_rows=None)
    low = interval_count([covered, missing, missing, missing], 0.75)
    assert low.value is None and low.reason == REASON_BELOW_THRESHOLD and low.coverage == 0.25
    assert interval_count([], 0.75) == interval_count([], 0.75)
    assert interval_count([], 0.75).value is None and interval_count([], 0.75).reason == REASON_NO_SLOTS


def test_near_empty_and_unknown_baseline_are_not_coverage():
    near = SlotSummary(True, True, 3)
    unknown = SlotSummary(True, None, 5)
    assert interval_count([near, near], 0.5).value is None
    assert interval_count([unknown], 0.75).value is None
    assert interval_count([unknown], 0.75, unknown_near_empty_is_covered=True).value == 5
    with pytest.raises(ValueError):
        interval_count([unknown], 0.0)
