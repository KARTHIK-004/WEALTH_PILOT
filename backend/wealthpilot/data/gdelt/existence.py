"""Turn header-check observations into an existence state, keeping absent, failed and unknown apart.

Rules (B2-H section 3, with the CDN behaviour it found):

- A 404 counts toward "absent" only if it is *fresh* (``Age`` <= ``fresh_max_age`` and a ``Date``
  header is present) and *independent* (at least ``spacing`` after the previous counted 404), because
  the CDN caches answers for an hour and ignores client no-cache requests.
- Two counted 404s and no 200 -> ``absent_confirmed``.
- Any 404 that cannot be counted twice -> ``absent_pending`` while checks remain, else
  ``absent_inconclusive``. A 200 mixed with a 404 is inconsistent -> ``absent_inconclusive``
  (fail closed; the batch is not used).
- A 200 and no 404 -> ``available`` (the download itself is then verified).
- Another 4xx, or a redirect that is not the same resource -> ``inaccessible``.
- Only timeouts, connection errors, 5xx or 429 -> ``pending`` while checks remain, else ``request_failed``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from wealthpilot.data.gdelt.timeutil import require_utc

TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class HeadObservation:
    at: datetime                      # local UTC time of the check
    status: int | None                # None when no HTTP response arrived
    error_kind: str | None = None     # timeout, connection_error, tls_error, redirect_rejected
    age_seconds: int | None = None
    has_server_date: bool = False


@dataclass(frozen=True)
class ExistenceDecision:
    state: str        # available, absent_confirmed, absent_pending, absent_inconclusive, inaccessible,
                      # pending, request_failed
    evidence: str
    recheck_after: datetime | None = None


def classify(observations: Sequence[HeadObservation], *, spacing: timedelta, fresh_max_age: int,
             max_checks: int) -> ExistenceDecision:
    obs = sorted(observations, key=lambda o: require_utc(o.at, "observation time"))
    if not obs:
        return ExistenceDecision("pending", "no observation")
    oks = [o for o in obs if o.status is not None and 200 <= o.status < 300]
    nfs = [o for o in obs if o.status == 404]
    other_4xx = [o for o in obs if o.status is not None and 400 <= o.status < 500 and o.status not in (404, 429)]
    redirect_bad = [o for o in obs if o.error_kind == "redirect_rejected"]
    exhausted = len(obs) >= max_checks

    if other_4xx or redirect_bad:
        what = f"HTTP {other_4xx[0].status}" if other_4xx else "redirect to another resource"
        return ExistenceDecision("inaccessible", what)
    if oks and nfs:
        return ExistenceDecision("absent_inconclusive", f"{len(oks)} x 200 and {len(nfs)} x 404: inconsistent")
    if oks:
        return ExistenceDecision("available", f"HTTP {oks[-1].status}")
    if nfs:
        counted: list[HeadObservation] = []
        for o in nfs:
            fresh = o.has_server_date and o.age_seconds is not None and 0 <= o.age_seconds <= fresh_max_age
            if not fresh:
                continue
            if counted and o.at - counted[-1].at < spacing:
                continue
            counted.append(o)
        if len(counted) >= 2:
            return ExistenceDecision("absent_confirmed", f"{len(counted)} fresh independent 404s")
        evidence = f"{len(nfs)} x 404, {len(counted)} fresh and independent"
        if exhausted:
            return ExistenceDecision("absent_inconclusive", evidence)
        base = counted[-1].at if counted else nfs[-1].at
        return ExistenceDecision("absent_pending", evidence, recheck_after=base + spacing)
    # only transient failures
    if exhausted:
        return ExistenceDecision("request_failed", f"{len(obs)} attempts, no HTTP answer usable")
    return ExistenceDecision("pending", "transient failure; retry")
