"""Market-session cutoffs and forecast-interval mapping. Pure functions; the calendar is an input.

Forecast origin d receives batches with cutoff(previous trading day) < available_at <= cutoff(d).
cutoff(d) is 16:00 America/New_York, or 13:00 on an early-close day. The early-close list is an
input: ``PROPOSED_EARLY_CLOSES`` (B2-H, official NYSE releases) is a candidate, not an approved
setting, and nothing here uses it unless a caller passes it.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wealthpilot.data.gdelt.errors import ConfigError
from wealthpilot.data.gdelt.timeutil import require_utc

NEW_YORK = "America/New_York"
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)

PROPOSED_EARLY_CLOSES: frozenset[date] = frozenset({   # PROPOSED (B2-H section 5.4); not approved
    date(2022, 11, 25), date(2023, 7, 3), date(2023, 11, 24), date(2024, 7, 3), date(2024, 11, 29),
    date(2024, 12, 24), date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
})


def new_york() -> ZoneInfo:
    try:
        return ZoneInfo(NEW_YORK)
    except ZoneInfoNotFoundError as exc:  # Windows without the tzdata package
        raise ConfigError("IANA time-zone data unavailable; run in the project venv (tzdata via pandas)") from exc


def assert_tz_offsets() -> None:
    """Fail closed unless New York offsets are right for a winter and a summer date."""
    tz = new_york()
    checks = {date(2022, 1, 3): 21, date(2022, 7, 1): 20}
    for day, utc_hour in checks.items():
        got = datetime.combine(day, REGULAR_CLOSE, tz).astimezone(timezone.utc).hour
        if got != utc_hour:
            raise ConfigError(f"unexpected New York offset on {day}: 16:00 ET -> {got}:00 UTC")


def cutoff_utc(day: date, early_closes: Iterable[date] = ()) -> datetime:
    close = EARLY_CLOSE if day in set(early_closes) else REGULAR_CLOSE
    return datetime.combine(day, close, new_york()).astimezone(timezone.utc)


def origin_for(available_at: datetime, trading_days: Sequence[date], early_closes: Iterable[date] = ()) -> date | None:
    """The forecast origin whose interval contains ``available_at``; None if after the last cutoff.

    ``trading_days`` must be sorted ascending; a batch before the first cutoff maps to the first day.
    """
    available_at = require_utc(available_at, "available_at")
    closes = frozenset(early_closes)
    cutoffs = [cutoff_utc(d, closes) for d in trading_days]
    i = bisect.bisect_left(cutoffs, available_at)  # first cutoff >= available_at
    return trading_days[i] if i < len(trading_days) else None
