"""Fixtures for the sensitive-data-protection tests.

These run on a throwaway SQLite file in pytest's temp directory: no network, no development database, no shared Neon
database. Only the three tables the feature touches are created. PostgreSQL-specific behaviour (the advisory lock,
bytea, timestamptz) is covered separately through the isolated test-database runner (tests/backend/api and
tests/backend/db: *_postgres tests).
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from wealthpilot.api.dependencies import get_encryption_service, get_session
from wealthpilot.api.main import app
from wealthpilot.db.base import Base
from wealthpilot.db.models import AuditLedgerEvent, Customer, ProtectedRecord
from wealthpilot.security.crypto import EncryptionService
from wealthpilot.security.keys import EnvironmentKeyProvider, generate_key_spec

TABLES = [Customer.__table__, ProtectedRecord.__table__, AuditLedgerEvent.__table__]


@pytest.fixture()
def engine(tmp_path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'security.db'}", connect_args={"timeout": 30})
    Base.metadata.create_all(engine, tables=TABLES)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine) -> Iterator[Session]:
    with Session(engine) as db:
        yield db


@pytest.fixture()
def make_session(engine):
    """Independent sessions on the same database (separate connections), for concurrency tests."""
    return sessionmaker(bind=engine)


@pytest.fixture()
def key_spec() -> str:
    """A fresh random key per test, formatted for configuration. Never stored anywhere."""
    return generate_key_spec("test-key-1", secrets.token_bytes(32))


@pytest.fixture()
def encryption_service(key_spec) -> EncryptionService:
    return EncryptionService(EnvironmentKeyProvider(key_spec, "test-key-1"))


@pytest.fixture()
def api(engine, encryption_service) -> Iterator[TestClient]:
    """The real application wired to the SQLite file, one commit per request like `get_session`.
    The lifespan (model warm-up) is not started: these routes use no model."""
    maker = sessionmaker(bind=engine)

    def override_session():
        db = maker()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_encryption_service] = lambda: encryption_service
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_encryption_service, None)


@pytest.fixture()
def customers(engine):
    """Two independent synthetic customers, committed."""
    with Session(engine) as db:
        rows = [Customer(name="Synthetic Customer A", data_source="user-entered"), Customer(name="Synthetic Customer B", data_source="user-entered")]
        db.add_all(rows)
        db.commit()
        return [row.id for row in rows]
