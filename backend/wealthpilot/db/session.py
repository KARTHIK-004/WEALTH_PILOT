"""Engine and session factory.

`DATABASE_URL` is stored in .env in the plain `postgresql://` form (so tools
like `psql` and Alembic's URL parsing accept it as-is); `to_sqlalchemy_url`
rewrites it to `postgresql+psycopg://` so SQLAlchemy uses the psycopg3
driver pinned in pyproject.toml instead of guessing a default.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from wealthpilot.config import get_settings


def to_sqlalchemy_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql+"):
        return raw_url
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


def get_engine(database_url: str | None = None) -> Engine:
    url = to_sqlalchemy_url(database_url or get_settings().database_url)
    return create_engine(url, pool_pre_ping=True)


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _session_factory() -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = get_engine()
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, closes it after the request."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
