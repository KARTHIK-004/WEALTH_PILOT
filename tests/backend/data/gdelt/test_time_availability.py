"""Timestamps, UTC normalisation, the fail-closed availability rule and the session calendar."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from wealthpilot.data.gdelt.availability import compute_availability, zip_member_time_utc
from wealthpilot.data.gdelt.errors import InvalidTimestampError
from wealthpilot.data.gdelt.session_calendar import (
    PROPOSED_EARLY_CLOSES,
    assert_tz_offsets,
    cutoff_utc,
    origin_for,
)
from wealthpilot.data.gdelt.timeutil import parse_batch_stamp, parse_http_date, require_utc, slot_grid

UTC = timezone.utc
STAMP = "20251223144500"
NOMINAL = datetime(2025, 12, 23, 14, 45, tzinfo=UTC)
SERVER_NOW = "Tue, 13 Oct 2026 06:00:00 GMT"


def lm(minutes: float) -> str:
    t = NOMINAL + timedelta(minutes=minutes)
    return t.strftime("%a, %d %b %Y %H:%M:%S GMT")


# ---------------------------------------------------------------- batch stamps and UTC

def test_batch_stamp_is_utc_aware():
    assert parse_batch_stamp(STAMP) == NOMINAL
    assert parse_batch_stamp(STAMP).tzinfo is UTC


@pytest.mark.parametrize("bad", ["2025122314450", "202512231445000", "2025122314450x", "20250231120000",
                                 "20251223141000", "20251223144501", "", None, 20251223144500])
def test_malformed_or_off_grid_stamps_are_rejected(bad):
    with pytest.raises(InvalidTimestampError):
        parse_batch_stamp(bad)


def test_naive_datetime_is_rejected_and_aware_is_normalised():
    with pytest.raises(InvalidTimestampError):
        require_utc(datetime(2025, 1, 1, 12, 0))
    ist = timezone(timedelta(hours=5, minutes=30))
    assert require_utc(datetime(2025, 1, 1, 17, 30, tzinfo=ist)) == datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("value,expected", [
    ("Tue, 23 Dec 2025 14:36:05 GMT", datetime(2025, 12, 23, 14, 36, 5, tzinfo=UTC)),
    ("Tue, 23 Dec 2025 14:36:05 +0000", None),          # not GMT form: ambiguous by policy
    ("Tuesday, 23-Dec-25 14:36:05 GMT", None),          # obsolete RFC 850
    ("Tue Dec 23 14:36:05 2025", None),                 # asctime
    ("Wed, 23 Dec 2025 14:36:05 GMT", None),            # weekday contradicts the date
    ("Tue, 31 Feb 2025 14:36:05 GMT", None),
    ("", None), (None, None),
])
def test_http_dates_are_parsed_strictly(value, expected):
    assert parse_http_date(value) == expected


def test_slot_grid_counts_and_rejects_reversed_range():
    assert len(slot_grid("20211201000000", "20211201234500")) == 96
    with pytest.raises(InvalidTimestampError):
        slot_grid("20211202000000", "20211201000000")


# ---------------------------------------------------------------- availability rule

def test_file_written_before_nominal_uses_nominal_plus_15():
    r = compute_availability(STAMP, lm(-9), SERVER_NOW)
    assert r.verified and r.available_at == NOMINAL + timedelta(minutes=15)
    assert "late" not in r.flags and r.reason is None


def test_file_written_after_nominal_uses_server_time_plus_15():
    r = compute_availability(STAMP, lm(10), SERVER_NOW)
    assert r.available_at == NOMINAL + timedelta(minutes=25)
    assert "written_after_nominal" in r.flags and "late" not in r.flags


def test_late_and_rewrite_suspect_flags_only_move_availability_later():
    late = compute_availability(STAMP, lm(30), SERVER_NOW)
    assert late.available_at == NOMINAL + timedelta(minutes=45) and "late" in late.flags
    rewritten = compute_availability(STAMP, lm(60 * 48), SERVER_NOW)
    assert rewritten.verified and "rewrite_suspect" in rewritten.flags
    assert rewritten.available_at > NOMINAL + timedelta(hours=48)


@pytest.mark.parametrize("last_modified,server_date,reason", [
    (None, SERVER_NOW, "last_modified_missing"),
    ("   ", SERVER_NOW, "last_modified_missing"),
    ("23/12/2025 14:36", SERVER_NOW, "last_modified_unparseable"),
    ("Tue, 23 Dec 2025 14:36:05 +0530", SERVER_NOW, "last_modified_unparseable"),
    (lm(-9), None, "server_date_missing"),
    (lm(-9), "yesterday", "server_date_unparseable"),
    (lm(-9), "Tue, 23 Dec 2025 14:30:00 GMT", "last_modified_after_server_date"),
    (lm(-120), SERVER_NOW, "last_modified_implausibly_early"),
])
def test_missing_or_inconsistent_server_metadata_fails_closed(last_modified, server_date, reason):
    r = compute_availability(STAMP, last_modified, server_date)
    assert r.status == "unverified" and r.available_at is None and r.reason == reason


def test_cached_timestamp_needs_zip_corroboration():
    cached = compute_availability(STAMP, lm(-9), SERVER_NOW, age_seconds=1657)
    assert not cached.verified and cached.reason == "cached_timestamp_uncorroborated"
    zt = NOMINAL - timedelta(minutes=9, seconds=3)
    ok = compute_availability(STAMP, lm(-9), SERVER_NOW, age_seconds=1657, zip_member_time=zt)
    assert ok.verified and {"served_from_cache", "zip_time_corroborated"} <= set(ok.flags)


def test_zip_time_disagreeing_with_server_time_fails_closed():
    r = compute_availability(STAMP, lm(-9), SERVER_NOW, zip_member_time=NOMINAL + timedelta(hours=3))
    assert not r.verified and r.reason == "zip_member_time_disagrees_with_last_modified"


def test_negative_age_is_invalid_and_naive_zip_time_is_a_caller_error():
    assert compute_availability(STAMP, lm(-9), SERVER_NOW, age_seconds=-5).reason == "age_header_invalid"
    with pytest.raises(InvalidTimestampError):
        compute_availability(STAMP, lm(-9), SERVER_NOW, zip_member_time=datetime(2025, 12, 23, 14, 36))


def test_zip_member_time_tuple_is_read_as_utc():
    assert zip_member_time_utc((2025, 12, 23, 14, 36, 2)) == datetime(2025, 12, 23, 14, 36, 2, tzinfo=UTC)
    assert zip_member_time_utc(None) is None
    assert zip_member_time_utc((2025, 2, 31, 0, 0, 0)) is None


def test_availability_is_a_pure_function():
    a = compute_availability(STAMP, lm(5), SERVER_NOW)
    b = compute_availability(STAMP, lm(5), SERVER_NOW)
    assert a == b


# ---------------------------------------------------------------- session calendar

def test_new_york_offsets_and_early_close():
    assert_tz_offsets()
    assert cutoff_utc(date(2024, 1, 4)) == datetime(2024, 1, 4, 21, 0, tzinfo=UTC)          # EST
    assert cutoff_utc(date(2024, 7, 2)) == datetime(2024, 7, 2, 20, 0, tzinfo=UTC)          # EDT
    assert cutoff_utc(date(2023, 11, 24), PROPOSED_EARLY_CLOSES) == datetime(2023, 11, 24, 18, 0, tzinfo=UTC)
    assert cutoff_utc(date(2023, 11, 24)) == datetime(2023, 11, 24, 21, 0, tzinfo=UTC)      # list not passed


TRADING = [date(2023, 3, 10), date(2023, 3, 13), date(2025, 1, 8), date(2025, 1, 10)]  # 2025-01-09 closed


def test_batch_exactly_at_cutoff_belongs_to_that_day_one_second_later_to_the_next():
    at = datetime(2023, 3, 10, 21, 0, tzinfo=UTC)          # Friday 16:00 EST
    assert origin_for(at, TRADING) == date(2023, 3, 10)
    assert origin_for(at + timedelta(seconds=1), TRADING) == date(2023, 3, 13)   # weekend rolls to Monday


def test_daylight_saving_change_moves_the_utc_cutoff():
    # Monday 2023-03-13 is EDT: cutoff 20:00 UTC, so 20:30 UTC belongs to the next trading day
    assert origin_for(datetime(2023, 3, 13, 19, 59, tzinfo=UTC), TRADING) == date(2023, 3, 13)
    assert origin_for(datetime(2023, 3, 13, 20, 30, tzinfo=UTC), TRADING) == date(2025, 1, 8)


def test_unscheduled_closure_rolls_forward_and_after_last_cutoff_is_none():
    assert origin_for(datetime(2025, 1, 9, 15, 0, tzinfo=UTC), TRADING) == date(2025, 1, 10)
    assert origin_for(datetime(2025, 1, 11, 0, 0, tzinfo=UTC), TRADING) is None
    with pytest.raises(InvalidTimestampError):
        origin_for(datetime(2025, 1, 9, 15, 0), TRADING)
