"""UTC-only time helpers. Pure functions; naive or ambiguous inputs are rejected, never guessed."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from wealthpilot.data.gdelt.errors import InvalidTimestampError

STAMP_FORMAT = "%Y%m%d%H%M%S"
SLOT = timedelta(minutes=15)
_STAMP_RE = re.compile(r"^\d{14}$")
# RFC 9110 "IMF-fixdate", the only HTTP-date form servers must generate; it is always GMT.
_IMF_FIXDATE_RE = re.compile(
    r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), (\d{2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
    r"(\d{4}) (\d{2}):(\d{2}):(\d{2}) GMT$"
)
_MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}


def require_utc(value: datetime, what: str = "datetime") -> datetime:
    """Return ``value`` converted to UTC; raise if it is naive (timezone-ambiguous)."""
    if not isinstance(value, datetime):
        raise InvalidTimestampError(f"{what} is not a datetime: {value!r}")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise InvalidTimestampError(f"{what} is timezone-naive; refusing to guess a zone: {value!r}")
    return value.astimezone(timezone.utc)


def parse_batch_stamp(stamp: str) -> datetime:
    """Parse a GDELT batch stamp ``YYYYMMDDHHMMSS`` (UTC by definition) on the 15-minute grid."""
    if not isinstance(stamp, str) or not _STAMP_RE.match(stamp):
        raise InvalidTimestampError(f"batch stamp must be 14 digits: {stamp!r}")
    try:
        naive = datetime.strptime(stamp, STAMP_FORMAT)
    except ValueError as exc:
        raise InvalidTimestampError(f"batch stamp is not a valid date-time: {stamp!r}") from exc
    if naive.minute % 15 or naive.second:
        raise InvalidTimestampError(f"batch stamp is off the 15-minute grid: {stamp!r}")
    return naive.replace(tzinfo=timezone.utc)


def format_batch_stamp(value: datetime) -> str:
    return require_utc(value, "batch time").strftime(STAMP_FORMAT)


def parse_http_date(value: str | None) -> datetime | None:
    """Parse an IMF-fixdate HTTP header strictly. Returns None for missing, empty or any other form.

    Obsolete RFC 850 / asctime forms and non-GMT zones are deliberately not accepted: a value the
    tool cannot read unambiguously is treated as unverifiable, never coerced.
    """
    if value is None:
        return None
    match = _IMF_FIXDATE_RE.match(value.strip())
    if not match:
        return None
    weekday, day, month, year, hh, mm, ss = match.groups()
    try:
        parsed = datetime(int(year), _MONTHS[month], int(day), int(hh), int(mm), int(ss), tzinfo=timezone.utc)
    except ValueError:
        return None
    if parsed.strftime("%a") != weekday:  # internally inconsistent date: unreliable
        return None
    return parsed


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return require_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_day(stamp: str) -> str:
    return parse_batch_stamp(stamp).strftime("%Y-%m-%d")


def slot_grid(first: str, last: str) -> list[str]:
    """Every 15-minute stamp from ``first`` to ``last`` inclusive."""
    start, end = parse_batch_stamp(first), parse_batch_stamp(last)
    if end < start:
        raise InvalidTimestampError(f"grid end {last} precedes start {first}")
    out, t = [], start
    while t <= end:
        out.append(t.strftime(STAMP_FORMAT))
        t += SLOT
    return out
