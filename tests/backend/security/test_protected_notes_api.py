"""Protected notes API: authorization, encryption at rest, audit trail, failure behaviour and non-disclosure.

SQLite-backed (see conftest), synthetic data only. The prototype's identity is the asserted `X-Customer-Id` header
(ADR-020/031), so "another user" below means a request whose header names a different customer than the profile in the
path. These tests prove that mechanism holds; they do not and cannot prove protection against a client that lies about
its header.
"""

from __future__ import annotations

import logging
import uuid

import pytest
from sqlalchemy import text

from wealthpilot.api.dependencies import get_encryption_service
from wealthpilot.api.main import app
from wealthpilot.api.schemas import PROTOTYPE_NOTICE
from wealthpilot.security.crypto import EncryptionService
from wealthpilot.security.errors import EncryptionError, LedgerError
from wealthpilot.security.keys import EnvironmentKeyProvider
from wealthpilot.security.ledger import LocalHashChainLedger

SECRET = "Synthetic-concern-8f3a: worried about the fictional EMI and a 12345.67 shortfall"
OTHER_SECRET = "Synthetic-other-77c1: planning for a fictional wedding"


def h(customer_id) -> dict[str, str]:
    return {"X-Customer-Id": str(customer_id)}


def notes_url(profile_id, record_id: str | None = None) -> str:
    base = f"/api/profiles/{profile_id}/protected-notes"
    return base if record_id is None else f"{base}/{record_id}"


def create(api, profile_id, content=SECRET, acting=None):
    return api.post(notes_url(profile_id), json={"content": content}, headers=h(profile_id if acting is None else acting))


def problem_without_path(response) -> str:
    """The problem body minus `instance`, which is RFC 7807's echo of the path the CALLER requested (and so contains
    the record id the caller themselves supplied). Everything else must not mention the record."""
    body = dict(response.json())
    body.pop("instance", None)
    return str(body)


def rows(engine, sql: str, **params):
    with engine.connect() as connection:
        return connection.execute(text(sql), params).all()


def ledger_types(engine) -> list[str]:
    return [r[0] for r in rows(engine, "SELECT event_type FROM audit_ledger_events ORDER BY sequence")]


def everything_stored(engine) -> bytes:
    """Every byte the feature persists, as one blob, for 'is the plaintext anywhere?' checks."""
    blob = b""
    for table in ("protected_records", "audit_ledger_events"):
        for row in rows(engine, f"SELECT * FROM {table}"):
            for value in row:
                blob += value if isinstance(value, bytes) else str(value).encode("utf-8")
    return blob


# ------------------------------------------------------------------------------------------------- owner happy path


def test_owner_creates_reads_updates_and_deletes_a_note(api, customers, engine):
    a, _ = customers
    created = create(api, a)
    assert created.status_code == 201
    note = created.json()
    assert uuid.UUID(note["id"]).version == 4
    assert note["protection"] == {"encrypted_at_rest": True, "algorithm": "AES-256-GCM", "envelope_version": 1, "storage": "off_chain_private_database"}
    assert "content" not in note  # create never echoes the note back

    fetched = api.get(notes_url(a, note["id"]), headers=h(a))
    assert fetched.status_code == 200 and fetched.json()["content"] == SECRET

    updated = api.put(notes_url(a, note["id"]), json={"content": OTHER_SECRET}, headers=h(a))
    assert updated.status_code == 200 and "content" not in updated.json()
    assert api.get(notes_url(a, note["id"]), headers=h(a)).json()["content"] == OTHER_SECRET

    assert api.delete(notes_url(a, note["id"]), headers=h(a)).status_code == 204
    assert api.get(notes_url(a, note["id"]), headers=h(a)).status_code == 404
    assert rows(engine, "SELECT count(*) FROM protected_records")[0][0] == 0


def test_the_audit_trail_records_each_operation_in_order(api, customers, engine):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    api.get(notes_url(a, note_id), headers=h(a))
    api.put(notes_url(a, note_id), json={"content": OTHER_SECRET}, headers=h(a))
    api.delete(notes_url(a, note_id), headers=h(a))
    assert ledger_types(engine) == [
        "protected_record.created", "protected_record.accessed", "protected_record.updated", "protected_record.deleted",
    ]
    assert {r[0] for r in rows(engine, "SELECT record_ref FROM audit_ledger_events")} == {note_id}


def test_listing_returns_metadata_only_and_decrypts_nothing(api, customers):
    a, _ = customers
    create(api, a)
    create(api, a, OTHER_SECRET)
    response = api.get(notes_url(a), headers=h(a))
    assert response.status_code == 200 and len(response.json()["items"]) == 2
    assert SECRET not in response.text and OTHER_SECRET not in response.text
    assert all(set(item) == {"id", "created_at", "updated_at", "protection"} for item in response.json()["items"])


def test_responses_carrying_user_text_are_not_cacheable(api, customers):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    for response in (api.get(notes_url(a), headers=h(a)), api.get(notes_url(a, note_id), headers=h(a)), api.get(f"/api/profiles/{a}/security-status", headers=h(a))):
        assert response.headers["cache-control"] == "no-store"


# ----------------------------------------------------------------------------------------------- encrypted at rest


def test_plaintext_is_nowhere_in_the_database_and_the_row_is_a_real_envelope(api, customers, engine):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    api.put(notes_url(a, note_id), json={"content": OTHER_SECRET}, headers=h(a))
    stored = everything_stored(engine)
    for needle in (SECRET, OTHER_SECRET, "12345.67", "Synthetic-concern", "wedding"):
        assert needle.encode() not in stored
    ((version, algorithm, key_id, nonce, ciphertext),) = rows(engine, "SELECT envelope_version, algorithm, key_id, nonce, ciphertext FROM protected_records")
    assert (version, algorithm, key_id) == (1, "AES-256-GCM", "test-key-1")
    assert len(nonce) == 12 and len(ciphertext) == len(OTHER_SECRET.encode()) + 16


def test_the_same_text_is_stored_as_different_ciphertexts(api, customers, engine):
    a, _ = customers
    create(api, a), create(api, a)
    cts = {bytes(r[0]) for r in rows(engine, "SELECT ciphertext FROM protected_records")}
    nonces = {bytes(r[0]) for r in rows(engine, "SELECT nonce FROM protected_records")}
    assert len(cts) == 2 and len(nonces) == 2


def test_an_update_uses_a_fresh_nonce(api, customers, engine):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    before = rows(engine, "SELECT nonce FROM protected_records")[0][0]
    api.put(notes_url(a, note_id), json={"content": SECRET}, headers=h(a))  # even identical content
    assert rows(engine, "SELECT nonce FROM protected_records")[0][0] != before


# --------------------------------------------------------------------------------------------------- authorization


@pytest.mark.parametrize("header", [None, "", "abc", "0", "-3", "1.5"])
def test_a_missing_or_unusable_identity_is_refused_for_every_route(api, customers, header):
    a, _ = customers
    headers = {} if header is None else {"X-Customer-Id": header}
    note_id = create(api, a).json()["id"]
    calls = [
        api.post(notes_url(a), json={"content": SECRET}, headers=headers),
        api.get(notes_url(a), headers=headers),
        api.get(notes_url(a, note_id), headers=headers),
        api.put(notes_url(a, note_id), json={"content": SECRET}, headers=headers),
        api.delete(notes_url(a, note_id), headers=headers),
        api.get(f"/api/profiles/{a}/security-status", headers=headers),
    ]
    assert [c.status_code for c in calls] == [401] * 6
    assert all(c.headers["content-type"].startswith("application/problem+json") for c in calls)


def test_another_identity_cannot_use_any_route_on_this_profile(api, customers, engine):
    a, b = customers
    note_id = create(api, a).json()["id"]
    before = rows(engine, "SELECT ciphertext, nonce FROM protected_records")
    calls = [
        create(api, a, "intruder text", acting=b),
        api.get(notes_url(a), headers=h(b)),
        api.get(notes_url(a, note_id), headers=h(b)),
        api.put(notes_url(a, note_id), json={"content": "intruder text"}, headers=h(b)),
        api.delete(notes_url(a, note_id), headers=h(b)),
        api.get(f"/api/profiles/{a}/security-status", headers=h(b)),
    ]
    assert [c.status_code for c in calls] == [403] * 6
    for call in calls:
        assert SECRET not in call.text and note_id not in problem_without_path(call) and "intruder" not in call.text
    assert rows(engine, "SELECT ciphertext, nonce FROM protected_records") == before  # nothing changed
    assert api.get(notes_url(a, note_id), headers=h(a)).json()["content"] == SECRET  # and the owner still reads it


def test_changing_the_record_id_to_another_profiles_record_looks_exactly_like_a_missing_record(api, customers, engine):
    a, b = customers
    a_note = create(api, a).json()["id"]
    b_note = create(api, b, OTHER_SECRET).json()["id"]
    missing = str(uuid.uuid4())

    foreign = [
        api.get(notes_url(b, a_note), headers=h(b)),
        api.put(notes_url(b, a_note), json={"content": "overwrite"}, headers=h(b)),
        api.delete(notes_url(b, a_note), headers=h(b)),
    ]
    absent = [
        api.get(notes_url(b, missing), headers=h(b)),
        api.put(notes_url(b, missing), json={"content": "overwrite"}, headers=h(b)),
        api.delete(notes_url(b, missing), headers=h(b)),
    ]
    assert [r.status_code for r in foreign] == [404] * 3 == [r.status_code for r in absent]
    for got, expected, record in zip(foreign, absent, (a_note, a_note, a_note), strict=True):
        body = got.json()
        assert body["title"] == expected.json()["title"] and body["detail"] == expected.json()["detail"]
        assert SECRET not in got.text and record not in problem_without_path(got)
    assert api.get(notes_url(a, a_note), headers=h(a)).json()["content"] == SECRET  # untouched
    assert api.get(notes_url(b, b_note), headers=h(b)).json()["content"] == OTHER_SECRET


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "1", "../../etc/passwd", "11111111-1111-4111-8111-11111111111G", "%27%20OR%201=1", "A" * 300])
def test_malformed_record_ids_are_just_not_found(api, customers, bad_id):
    a, _ = customers
    for response in (api.get(notes_url(a, bad_id), headers=h(a)), api.delete(notes_url(a, bad_id), headers=h(a))):
        assert response.status_code == 404 and response.headers["content-type"].startswith("application/problem+json")


def test_an_unknown_customer_cannot_act(api):
    assert create(api, 9999).status_code == 404


def test_a_ciphertext_copied_onto_another_customer_does_not_decrypt(api, customers, engine):
    """Even someone who can write the table cannot make a record readable by a different owner: the owner id is in the
    authenticated data. (The route returns a generic integrity error and discloses nothing.)"""
    a, b = customers
    note_id = create(api, a).json()["id"]
    with engine.begin() as connection:
        connection.execute(text("UPDATE protected_records SET customer_id = :b WHERE id = :i"), {"b": b, "i": note_id})
    response = api.get(notes_url(b, note_id), headers=h(b))
    assert response.status_code == 500 and SECRET not in response.text


def test_there_is_no_endpoint_that_exposes_audit_events_or_cross_profile_verification():
    paths = [path for path in app.openapi()["paths"] if "protected" in path or "security" in path or "audit" in path or "ledger" in path]
    assert sorted(paths) == [
        "/api/profiles/{profile_id}/protected-notes",
        "/api/profiles/{profile_id}/protected-notes/{record_id}",
        "/api/profiles/{profile_id}/security-status",
    ]
    assert all("{profile_id}" in p for p in paths)


# ----------------------------------------------------------------------------------------- the denial audit trail


def test_refused_requests_are_audited_identically_whatever_the_reason(api, customers, engine):
    a, b = customers
    note_id = create(api, a).json()["id"]
    missing = str(uuid.uuid4())
    api.get(notes_url(a, note_id), headers=h(b))  # wrong identity, a real record
    api.get(notes_url(b, missing), headers=h(b))  # right identity, unknown record
    api.get(notes_url(b, "not-a-uuid"), headers=h(b))  # malformed id
    events = rows(engine, "SELECT event_type, record_ref FROM audit_ledger_events ORDER BY sequence")
    # One event type for every refusal: the ledger holds no actor, no reason and no 'record exists' bit. The reference
    # is only the opaque id the CALLER supplied (none when it was not a well-formed id).
    assert [e[0] for e in events] == ["protected_record.created"] + ["protected_record.access_denied"] * 3
    assert [e[1] for e in events[1:]] == [note_id, missing, None]


def test_a_failure_to_audit_a_denial_never_changes_the_denial(api, customers, monkeypatch):
    a, b = customers
    monkeypatch.setattr(LocalHashChainLedger, "append", lambda self, *args, **kwargs: (_ for _ in ()).throw(LedgerError("down")))
    assert api.get(notes_url(a), headers=h(b)).status_code == 403


# ------------------------------------------------------------------------------------------- fail-closed behaviour


class _Unconfigured(EncryptionService):
    def __init__(self):
        super().__init__(EnvironmentKeyProvider("", ""))


def test_without_a_configured_key_nothing_is_saved_and_the_status_says_so(api, customers, engine):
    a, _ = customers
    app.dependency_overrides[get_encryption_service] = _Unconfigured
    response = create(api, a)
    assert response.status_code == 503 and SECRET not in response.text
    assert rows(engine, "SELECT count(*) FROM protected_records")[0][0] == 0
    assert ledger_types(engine) == []
    status = api.get(f"/api/profiles/{a}/security-status", headers=h(a)).json()
    assert status["encryption"]["status"] == "not_configured" and status["encryption"]["self_test_passed"] is None


def test_an_encryption_failure_persists_nothing_and_never_falls_back_to_plaintext(api, customers, engine, monkeypatch):
    a, _ = customers

    def boom(self, plaintext, context):
        raise EncryptionError("synthetic failure")

    monkeypatch.setattr(EncryptionService, "encrypt", boom)
    response = create(api, a)
    assert response.status_code == 503
    assert rows(engine, "SELECT count(*) FROM protected_records")[0][0] == 0 and ledger_types(engine) == []
    assert SECRET.encode() not in everything_stored(engine)


def test_an_audit_failure_aborts_the_data_write_so_data_and_audit_stay_atomic(api, customers, engine, monkeypatch):
    a, _ = customers
    monkeypatch.setattr(LocalHashChainLedger, "append", lambda self, *args, **kwargs: (_ for _ in ()).throw(LedgerError("synthetic failure")))
    response = create(api, a)
    assert response.status_code == 500
    assert rows(engine, "SELECT count(*) FROM protected_records")[0][0] == 0 and ledger_types(engine) == []


def test_a_tampered_stored_ciphertext_is_never_returned_and_is_not_recorded_as_an_access(api, customers, engine):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    with engine.begin() as connection:
        connection.execute(text("UPDATE protected_records SET ciphertext = :c WHERE id = :i"), {"c": b"\x00" * 40, "i": note_id})
    response = api.get(notes_url(a, note_id), headers=h(a))
    assert response.status_code == 500 and response.headers["content-type"].startswith("application/problem+json")
    assert SECRET not in response.text and "Traceback" not in response.text and "InvalidTag" not in response.text
    assert ledger_types(engine) == ["protected_record.created"]


def test_a_record_whose_key_is_no_longer_available_reports_unavailable_not_a_decryption_attempt(api, customers, engine):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    with engine.begin() as connection:
        connection.execute(text("UPDATE protected_records SET key_id = 'retired'"))
    assert api.get(notes_url(a, note_id), headers=h(a)).status_code == 503


# ----------------------------------------------------------------------------------- validation and non-disclosure


@pytest.mark.parametrize(
    "body",
    [
        {"content": 12345},
        {"content": ["Synthetic-concern-8f3a"]},
        {"content": {"k": "Synthetic-concern-8f3a"}},
        {"content": ""},
        {"content": "   "},
        {"content": "x" * 2001},
        {"content": "Synthetic-concern-8f3a", "extra": "Synthetic-concern-8f3a"},
        {},
    ],
)
def test_a_rejected_note_is_never_echoed_in_the_error(api, customers, body):
    a, _ = customers
    response = api.post(notes_url(a), json=body, headers=h(a))
    assert response.status_code == 422
    assert "Synthetic-concern-8f3a" not in response.text and "xxxxxxxx" not in response.text and "12345" not in response.text


def test_a_non_json_body_is_not_echoed_either(api, customers):
    a, _ = customers
    response = api.post(notes_url(a), content='"Synthetic-concern-8f3a" not json', headers={**h(a), "content-type": "application/json"})
    assert response.status_code == 422 and "Synthetic-concern-8f3a" not in response.text


def test_neither_plaintext_nor_key_material_reaches_the_logs(api, customers, key_spec, caplog):
    a, b = customers
    with caplog.at_level(logging.DEBUG):
        note_id = create(api, a).json()["id"]
        api.get(notes_url(a, note_id), headers=h(a))
        api.put(notes_url(a, note_id), json={"content": OTHER_SECRET}, headers=h(a))
        api.get(notes_url(a, note_id), headers=h(b))
        api.post(notes_url(a), json={"content": 5}, headers=h(a))
        api.delete(notes_url(a, note_id), headers=h(a))
    key_material = key_spec.split(":", 1)[1]
    for needle in (SECRET, OTHER_SECRET, key_material, "Synthetic-concern", "12345.67"):
        assert needle not in caplog.text


# -------------------------------------------------------------------------------------------------- security status


def test_security_status_reports_real_checks_and_the_exact_prototype_label(api, customers):
    a, _ = customers
    create(api, a)
    status = api.get(f"/api/profiles/{a}/security-status", headers=h(a)).json()
    assert status["prototype_notice"] == PROTOTYPE_NOTICE == "Academic prototype — not a real blockchain."
    assert status["storage"] == "off_chain_private_database" and status["protected_note_count"] == 1
    assert status["encryption"] == {"status": "operational", "algorithm": "AES-256-GCM", "self_test_passed": True, "unavailable_reason": None}
    assert status["ledger"]["kind"] == "local_hash_chain" and status["ledger"]["verification"] == "valid" and status["ledger"]["events_checked"] == 1
    assert status["external_anchor"]["state"] == "not_configured"
    assert status["existing_data"]["encrypted"] is False and len(status["existing_data"]["unprotected_categories"]) >= 4
    assert "asserted" in " ".join(status["limitations"]) and "managed key" in " ".join(status["limitations"])


def test_security_status_on_an_empty_ledger_says_empty_not_valid(api, customers):
    a, _ = customers
    assert api.get(f"/api/profiles/{a}/security-status", headers=h(a)).json()["ledger"]["verification"] == "empty"


def test_security_status_reflects_a_tampered_chain_with_a_non_sensitive_reason(api, customers, engine):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    api.get(notes_url(a, note_id), headers=h(a))
    with engine.begin() as connection:
        connection.execute(text("UPDATE audit_ledger_events SET event_type = 'protected_record.deleted' WHERE sequence = 2"))
    ledger = api.get(f"/api/profiles/{a}/security-status", headers=h(a)).json()["ledger"]
    assert (ledger["verification"], ledger["first_invalid_sequence"]) == ("invalid", 2)
    assert note_id not in str(ledger) and SECRET not in str(ledger)


def test_security_status_exposes_no_hashes_keys_or_record_contents(api, customers, engine, key_spec):
    a, _ = customers
    note_id = create(api, a).json()["id"]
    api.get(notes_url(a, note_id), headers=h(a))
    text_ = api.get(f"/api/profiles/{a}/security-status", headers=h(a)).text
    head = rows(engine, "SELECT event_hash FROM audit_ledger_events ORDER BY sequence DESC LIMIT 1")[0][0]
    for needle in (SECRET, key_spec.split(":", 1)[1], head, note_id, "test-key-1"):
        assert needle not in text_


def test_the_status_check_does_not_write_to_the_ledger(api, customers, engine):
    a, _ = customers
    api.get(f"/api/profiles/{a}/security-status", headers=h(a))
    assert ledger_types(engine) == []


# ------------------------------------------------------------------------------------------- commit-time failure


def test_a_failed_commit_is_reported_as_an_error_never_as_success_and_nothing_is_kept(api, customers, engine):
    """Data and audit share one transaction committed by the session dependency. If that commit fails the client must not be told
    the note was saved, and neither the row nor its audit event may exist."""
    from sqlalchemy.orm import sessionmaker

    from wealthpilot.api.dependencies import get_session

    a, _ = customers
    maker = sessionmaker(bind=engine)

    def failing_commit_session():
        db = maker()
        try:
            yield db
            raise RuntimeError("synthetic commit failure")  # stands in for a failure at commit time
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_session] = failing_commit_session
    response = create(api, a)
    assert response.status_code == 500 and SECRET not in response.text
    assert rows(engine, "SELECT count(*) FROM protected_records")[0][0] == 0 and ledger_types(engine) == []
