"""A database that has not had migration f7a2d4b6c810 applied (the development database until its owner upgrades it) must answer the protected-note and
security-status routes with a clear 503, never an anonymous 500 with a logged traceback, and must never create tables or save anything."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from wealthpilot.api.dependencies import get_encryption_service, get_session
from wealthpilot.api.main import app
from wealthpilot.db.base import Base
from wealthpilot.db.models import AuditLedgerEvent, Customer, ProtectedRecord

SECRET = "Synthetic-unmigrated-note-4471"
H = {"X-Customer-Id": "1"}


@pytest.fixture()
def unmigrated(tmp_path, encryption_service):
    """Only the customers table exists: protected_records and audit_ledger_events are missing."""
    engine = create_engine(f"sqlite:///{tmp_path / 'unmigrated.db'}")
    Base.metadata.create_all(engine, tables=[Customer.__table__])
    with Session(engine) as db:
        db.add(Customer(name="Synthetic Customer", data_source="user-entered"))
        db.commit()
    maker = sessionmaker(bind=engine)

    def override():
        db = maker()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_encryption_service] = lambda: encryption_service
    try:
        yield TestClient(app, raise_server_exceptions=False), engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_encryption_service, None)
        engine.dispose()


def test_every_route_says_the_migration_is_missing_instead_of_failing_with_a_500(unmigrated):
    client, _ = unmigrated
    calls = [
        client.get("/api/profiles/1/security-status", headers=H),
        client.get("/api/profiles/1/protected-notes", headers=H),
        client.post("/api/profiles/1/protected-notes", json={"content": SECRET}, headers=H),
        client.get("/api/profiles/1/protected-notes/3f1c9a52-7b8e-4d21-9a60-0c4e5d6f7a81", headers=H),
        client.put("/api/profiles/1/protected-notes/3f1c9a52-7b8e-4d21-9a60-0c4e5d6f7a81", json={"content": SECRET}, headers=H),
        client.delete("/api/profiles/1/protected-notes/3f1c9a52-7b8e-4d21-9a60-0c4e5d6f7a81", headers=H),
    ]
    assert [c.status_code for c in calls] == [503] * 6
    for call in calls:
        assert call.headers["content-type"].startswith("application/problem+json")
        assert "migration" in call.json()["detail"] and "has not been applied" in call.json()["detail"]
        assert SECRET not in call.text and "Traceback" not in call.text and "no such table" not in call.text.lower()


def test_nothing_is_created_or_saved_and_the_failure_is_not_logged_as_an_unhandled_exception(unmigrated, caplog):
    client, engine = unmigrated
    with caplog.at_level(logging.DEBUG):
        client.post("/api/profiles/1/protected-notes", json={"content": SECRET}, headers=H)
        client.get("/api/profiles/1/security-status", headers=H)
    assert set(inspect(engine).get_table_names()) == {"customers"}  # no table was created on the way
    assert "Unhandled exception" not in caplog.text and SECRET not in caplog.text


def test_identity_is_still_checked_first_so_a_foreign_identity_is_a_403_and_a_missing_identity_a_401(unmigrated):
    client, _ = unmigrated
    assert client.get("/api/profiles/1/security-status", headers={"X-Customer-Id": "2"}).status_code == 403
    assert client.get("/api/profiles/1/security-status").status_code == 401


def test_once_the_tables_exist_the_same_routes_work_and_a_missing_table_is_re_checked(unmigrated):
    client, engine = unmigrated
    assert client.get("/api/profiles/1/security-status", headers=H).status_code == 503
    Base.metadata.create_all(engine, tables=[ProtectedRecord.__table__, AuditLedgerEvent.__table__])  # the owner applies the migration
    status = client.get("/api/profiles/1/security-status", headers=H)
    assert status.status_code == 200 and status.json()["ledger"]["verification"] == "empty"
    assert client.post("/api/profiles/1/protected-notes", json={"content": SECRET}, headers=H).status_code == 201
