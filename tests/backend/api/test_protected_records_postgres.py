"""Protected notes and the audit ledger on PostgreSQL (the isolated TEST database only).

Uses the existing rollback-safe `client` / `db_session` fixtures on TEST_DATABASE_URL, so nothing persists. Run these
through `scripts/run_isolated_db_tests.py`, never against the development database. The SQLite-backed suite in
tests/backend/security covers the logic exhaustively; this file covers what only PostgreSQL can show: the migration's
real schema, the advisory-lock path, bytea / timestamptz round trips and the unique-constraint backstop.
"""

from __future__ import annotations

import secrets
import uuid

import pytest
from sqlalchemy import inspect, text

from wealthpilot.api.dependencies import get_encryption_service
from wealthpilot.api.main import app
from wealthpilot.security.crypto import EncryptionService
from wealthpilot.security.errors import LedgerError
from wealthpilot.security.keys import EnvironmentKeyProvider, generate_key_spec
from wealthpilot.security.ledger import (
    EVENT_PROTECTED_RECORD_ACCESSED,
    EVENT_PROTECTED_RECORD_CREATED,
    INVALID,
    VALID,
    LocalHashChainLedger,
)

SECRET = "Synthetic-pg-concern-51d9: fictional loan worry"


@pytest.fixture()
def service() -> EncryptionService:
    return EncryptionService(EnvironmentKeyProvider(generate_key_spec("pg-key-1", secrets.token_bytes(32)), "pg-key-1"))


@pytest.fixture()
def configured_client(client, service):
    app.dependency_overrides[get_encryption_service] = lambda: service
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_encryption_service, None)


def h(customer) -> dict[str, str]:
    return {"X-Customer-Id": str(customer.id)}


def test_the_migration_created_both_tables_with_the_expected_columns(db_session):
    inspector = inspect(db_session.connection())
    columns = {c["name"]: c for c in inspector.get_columns("protected_records")}
    assert set(columns) == {"id", "customer_id", "purpose", "envelope_version", "algorithm", "key_id", "nonce", "ciphertext", "created_at", "updated_at"}
    assert "plaintext" not in columns and "content" not in columns
    assert {c["name"] for c in inspector.get_columns("audit_ledger_events")} == {
        "sequence", "event_type", "occurred_at", "record_ref", "schema_version", "prev_hash", "event_hash",
    }
    unique = {tuple(u["column_names"]) for u in inspector.get_unique_constraints("audit_ledger_events")}
    assert {("prev_hash",), ("event_hash",)} <= unique


def test_ledger_appends_verify_on_postgres_including_the_advisory_lock_path(db_session):
    ledger = LocalHashChainLedger()
    refs = [str(uuid.uuid4()) for _ in range(5)]
    for ref in refs:
        ledger.append(db_session, EVENT_PROTECTED_RECORD_CREATED, ref)
    result = ledger.verify(db_session)
    assert (result.status, result.events_checked) == (VALID, 5)
    stored = ledger.event_at(db_session, 3)
    assert stored.record_ref == refs[2] and stored.occurred_at.utcoffset().total_seconds() == 0  # timestamptz round trip


def test_postgres_detects_tampering_and_a_conflicting_append(db_session):
    ledger = LocalHashChainLedger()
    for _ in range(4):
        ledger.append(db_session, EVENT_PROTECTED_RECORD_ACCESSED, str(uuid.uuid4()))
    db_session.execute(text("UPDATE audit_ledger_events SET event_type = 'protected_record.deleted' WHERE sequence = 2"))
    tampered = ledger.verify(db_session)
    assert (tampered.status, tampered.first_invalid_sequence, tampered.reason_code) == (INVALID, 2, "hash_mismatch")

    class StaleHead(LocalHashChainLedger):
        @staticmethod
        def _tail(session):
            return None

    with pytest.raises(LedgerError):
        StaleHead().append(db_session, EVENT_PROTECTED_RECORD_CREATED, str(uuid.uuid4()))


def test_notes_are_encrypted_in_postgres_and_owner_scoped(configured_client, make_customer, db_session):
    owner, other = make_customer(name="Synthetic Owner"), make_customer(name="Synthetic Other")
    created = configured_client.post(f"/api/profiles/{owner.id}/protected-notes", json={"content": SECRET}, headers=h(owner))
    assert created.status_code == 201, created.text
    note_id = created.json()["id"]

    stored = db_session.execute(text("SELECT nonce, ciphertext, key_id FROM protected_records WHERE id = :i"), {"i": note_id}).one()
    assert SECRET.encode() not in bytes(stored.ciphertext) and len(bytes(stored.nonce)) == 12 and stored.key_id == "pg-key-1"
    assert db_session.execute(text("SELECT count(*) FROM protected_records WHERE position(:p in ciphertext) > 0"), {"p": b"Synthetic"}).scalar_one() == 0

    assert configured_client.get(f"/api/profiles/{owner.id}/protected-notes/{note_id}", headers=h(owner)).json()["content"] == SECRET
    assert configured_client.get(f"/api/profiles/{owner.id}/protected-notes/{note_id}", headers=h(other)).status_code == 403
    assert configured_client.get(f"/api/profiles/{other.id}/protected-notes/{note_id}", headers=h(other)).status_code == 404
    assert configured_client.put(f"/api/profiles/{other.id}/protected-notes/{note_id}", json={"content": "x"}, headers=h(other)).status_code == 404
    assert configured_client.delete(f"/api/profiles/{other.id}/protected-notes/{note_id}", headers=h(other)).status_code == 404

    status = configured_client.get(f"/api/profiles/{owner.id}/security-status", headers=h(owner)).json()
    assert status["ledger"]["verification"] == "valid" and status["encryption"]["status"] == "operational"
    events = [r[0] for r in db_session.execute(text("SELECT event_type FROM audit_ledger_events ORDER BY sequence"))]
    assert events[:2] == ["protected_record.created", "protected_record.accessed"]
    assert events.count("protected_record.access_denied") == 4
