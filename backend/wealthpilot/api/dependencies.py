"""Phase 15 — FastAPI dependencies.

Reuses `db/session.py`'s existing engine/session-factory exactly (section
31: "do not create a new database engine for each request... do not
create a second database configuration") — this module adds nothing new
beyond FastAPI's own `Depends()` wiring around `db.session.get_db`, plus
one request-scoped policy `db.session.get_db` itself deliberately does
NOT apply (it is also used by non-request test fixtures, where committing
automatically would be wrong): commit once at the end of a successful
request, roll back on any exception. Every Phase 14/10 write function
(`persist_recommendation`, etc.) already flushes but never commits "the
caller owns the transaction boundary" — for an API request, that caller
is this dependency, not `db/session.py`.

`get_session_factory` exists ONLY for `api/sse.py`: a `StreamingResponse`
body generator is still running after the route function itself returns,
so a `Depends()` GENERATOR's cleanup (which FastAPI runs once the route
function returns) would close/commit the session while the SSE pipeline
is still mid-stream. A plain (non-generator) dependency that returns a
zero-arg session-constructing callable is resolved immediately, before
that timing problem can occur, and lets the generator manage the
session's lifecycle itself. Both dependencies are override points in
tests (`tests/backend/api/conftest.py`), which is the other reason this
is a callable rather than inlining `Session(get_engine(...))` directly in
`api/sse.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Header
from sqlalchemy.orm import Session

from wealthpilot.api.errors import IdentityRequiredError

from wealthpilot.config import get_settings
from wealthpilot.db.session import get_db as _get_db
from wealthpilot.db.session import get_engine


def get_session() -> Generator[Session, None, None]:
    db_gen = _get_db()
    session = next(db_gen)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        # Drives db.session.get_db()'s own generator to completion so its
        # `finally: session.close()` runs deterministically here, rather
        # than being left for garbage collection to eventually trigger.
        next(db_gen, None)


def get_session_factory() -> Callable[[], Session]:
    engine = get_engine(get_settings().database_url)
    return lambda: Session(bind=engine)


def get_acting_customer_id(
    x_customer_id: Annotated[
        str | None,
        Header(
            alias="X-Customer-Id",
            description=(
                "Phase 32: the id of the customer the session is associated with "
                "(the frontend's single `profileId`). Required by every household "
                "route, which authorizes against household membership. The "
                "prototype has no server session, so this is an ASSERTED identity "
                "-- it stops accidental or URL-edited cross-household access, not "
                "a malicious client (docs/DECISIONS.md ADR-031, docs/SECURITY.md)."
            ),
        ),
    ] = None,
) -> int:
    """Household routes' caller identity. Missing, non-numeric or
    non-positive -> 401 problem+json."""
    try:
        acting = int(x_customer_id) if x_customer_id is not None else None
    except ValueError:
        acting = None
    if acting is None or acting <= 0:
        raise IdentityRequiredError("A valid X-Customer-Id header identifying the associated customer is required.")
    return acting
