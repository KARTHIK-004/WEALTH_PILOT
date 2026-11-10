"""The provisional availability-time rule, as a pure function.

    availability_time = max(batch_timestamp, verified_server_file_timestamp) + 15 minutes

The server file timestamp is the HTTP ``Last-Modified`` header of the downloaded archive. It is
used only when it can be *verified*; otherwise the batch fails closed (``status="unverified"``)
and the reason is reported. The page publication time (``PAGE_PRECISEPUBTIMESTAMP``) is never an
input here.

Verification rules (all must hold):

1. ``Last-Modified`` is present and is a strict IMF-fixdate in GMT.
2. The response ``Date`` header is present and strict; ``Last-Modified`` is not later than it
   (plus a small clock allowance): a file cannot be modified in the server's future.
3. ``Last-Modified`` is not implausibly early: at most ``max_early`` (60 min) before the nominal
   batch time. GDELT writes files 8-12 minutes before their nominal time (B2-F, B2-G).
4. When the archive's zip member time is supplied, it agrees with ``Last-Modified`` within
   ``zip_tolerance`` (10 min). A disagreement is inconsistent metadata: fail closed.
5. A response served from a cache (``Age`` > 0) is accepted only when the zip member time
   corroborates ``Last-Modified``; an uncorroborated cached timestamp fails closed.

Assumptions and known limitations:

- The zip member time is a timezone-less DOS time. It is interpreted as UTC because the one archive
  inspected (B2-G) carried a member time within 3 s of its UTC Last-Modified. If GDELT ever wrote
  local times, rule 4 would fail closed (never open).
- Last-Modified describes the copy served today. A file rewritten later than its nominal time only
  moves availability later (conservative); a ``rewrite_suspect`` flag marks gaps above 24 h.
- The rule assumes GDELT published each file at its Last-Modified time; that cannot be proven
  historically and is why the 15-minute margin and the flags exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from wealthpilot.data.gdelt.timeutil import SLOT, parse_batch_stamp, parse_http_date, require_utc

MAX_EARLY = timedelta(minutes=60)
MAX_CLOCK_AHEAD = timedelta(seconds=120)
ZIP_TOLERANCE = timedelta(minutes=10)
REWRITE_SUSPECT_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class AvailabilityResult:
    status: str                      # "verified" or "unverified"
    available_at: datetime | None    # UTC; None when unverified
    server_file_time: datetime | None
    flags: tuple[str, ...]
    reason: str | None               # why it is unverified; None when verified

    @property
    def verified(self) -> bool:
        return self.status == "verified"


def zip_member_time_utc(date_time: tuple[int, int, int, int, int, int] | None) -> datetime | None:
    """Interpret a ZipInfo.date_time tuple as UTC (see module assumptions). None if absent/invalid."""
    if not date_time:
        return None
    try:
        return datetime(*date_time, tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _unverified(reason: str, server_time: datetime | None, flags: list[str]) -> AvailabilityResult:
    return AvailabilityResult("unverified", None, server_time, tuple(sorted(set(flags))), reason)


def compute_availability(
    batch_stamp: str,
    last_modified: str | None,
    server_date: str | None,
    *,
    age_seconds: int | None = None,
    zip_member_time: datetime | None = None,
    max_early: timedelta = MAX_EARLY,
    max_clock_ahead: timedelta = MAX_CLOCK_AHEAD,
    zip_tolerance: timedelta = ZIP_TOLERANCE,
) -> AvailabilityResult:
    """Return the conservative availability time of one batch, or an unverified result with a reason.

    Raises ``InvalidTimestampError`` for a malformed batch stamp or a naive ``zip_member_time``:
    those are caller errors, not server metadata problems.
    """
    nominal = parse_batch_stamp(batch_stamp)
    if zip_member_time is not None:
        zip_member_time = require_utc(zip_member_time, "zip member time")
    flags: list[str] = []

    if last_modified is None or not last_modified.strip():
        return _unverified("last_modified_missing", None, flags)
    lm = parse_http_date(last_modified)
    if lm is None:
        return _unverified("last_modified_unparseable", None, flags)
    if server_date is None or not server_date.strip():
        return _unverified("server_date_missing", lm, flags)
    served = parse_http_date(server_date)
    if served is None:
        return _unverified("server_date_unparseable", lm, flags)
    if lm > served + max_clock_ahead:
        return _unverified("last_modified_after_server_date", lm, flags)
    if lm < nominal - max_early:
        return _unverified("last_modified_implausibly_early", lm, flags)

    cached = age_seconds is not None and age_seconds > 0
    if age_seconds is not None and age_seconds < 0:
        return _unverified("age_header_invalid", lm, flags)
    if zip_member_time is not None:
        if abs(zip_member_time - lm) > zip_tolerance:
            return _unverified("zip_member_time_disagrees_with_last_modified", lm, flags)
        flags.append("zip_time_corroborated")
    elif cached:
        return _unverified("cached_timestamp_uncorroborated", lm, flags + ["served_from_cache"])
    if cached:
        flags.append("served_from_cache")

    if lm > nominal:
        flags.append("written_after_nominal")
    if lm > nominal + SLOT:
        flags.append("late")
    if lm > nominal + REWRITE_SUSPECT_AFTER:
        flags.append("rewrite_suspect")
    available = max(nominal, lm) + SLOT
    return AvailabilityResult("verified", available, lm, tuple(sorted(set(flags))), None)
