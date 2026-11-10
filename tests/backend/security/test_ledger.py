"""Local hash-chain ledger tests (SQLite, DB-free of any hosted database).

The ledger is an ACADEMIC PROTOTYPE, not a blockchain. These tests prove what it does detect (edits, reordering,
removal in the middle or at the start, broken links, a stale concurrent append) and, deliberately, what it does NOT
(a privileged rewrite of the whole chain; removal of the newest events without an externally recorded head).
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from wealthpilot.db.models import AuditLedgerEvent
from wealthpilot.security.errors import LedgerError
from wealthpilot.security.ledger import (
    EMPTY,
    EVENT_ACCESS_DENIED,
    EVENT_PROTECTED_RECORD_ACCESSED,
    EVENT_PROTECTED_RECORD_CREATED,
    EVENT_PROTECTED_RECORD_DELETED,
    EVENT_PROTECTED_RECORD_UPDATED,
    EVENT_TYPES,
    GENESIS_HASH,
    HASH_DOMAIN,
    INVALID,
    VALID,
    AuditLedger,
    LedgerHead,
    LocalHashChainLedger,
    canonical_payload,
    compute_event_hash,
    format_timestamp,
)

FIXED = datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=UTC)


def ref() -> str:
    return str(uuid.uuid4())


def fill(session, ledger: LocalHashChainLedger, count: int) -> list:
    events = [ledger.append(session, EVENT_PROTECTED_RECORD_CREATED, ref()) for _ in range(count)]
    session.commit()
    return events


def raw(session, sql: str, **params) -> None:
    session.execute(text(sql), params)
    session.commit()


@pytest.fixture()
def ledger() -> LocalHashChainLedger:
    return LocalHashChainLedger()


# ------------------------------------------------------------------------------------ canonical form and hashing


def test_canonical_serialization_is_exact_and_deterministic():
    payload = canonical_payload(1, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 1)
    assert payload == (
        b'{"event_type":"protected_record.created","occurred_at":"2026-01-02T03:04:05.000006Z",'
        b'"record_ref":null,"schema_version":1,"sequence":1}'
    )
    assert canonical_payload(1, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 1) == payload


def test_event_hash_is_sha256_of_domain_previous_hash_and_canonical_payload():
    expected = hashlib.sha256(HASH_DOMAIN + GENESIS_HASH.encode() + b"\n" + canonical_payload(1, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 1)).hexdigest()
    assert compute_event_hash(GENESIS_HASH, 1, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 1) == expected
    assert GENESIS_HASH == "0" * 64


def test_every_field_and_the_previous_hash_affect_the_hash():
    base = compute_event_hash(GENESIS_HASH, 1, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 1)
    variants = [
        compute_event_hash("1" * 64, 1, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 1),
        compute_event_hash(GENESIS_HASH, 2, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 1),
        compute_event_hash(GENESIS_HASH, 1, EVENT_PROTECTED_RECORD_DELETED, FIXED, None, 1),
        compute_event_hash(GENESIS_HASH, 1, EVENT_PROTECTED_RECORD_CREATED, FIXED + timedelta(microseconds=1), None, 1),
        compute_event_hash(GENESIS_HASH, 1, EVENT_PROTECTED_RECORD_CREATED, FIXED, ref(), 1),
        compute_event_hash(GENESIS_HASH, 1, EVENT_PROTECTED_RECORD_CREATED, FIXED, None, 2),
    ]
    assert len({base, *variants}) == 7


def test_timestamps_are_normalised_to_utc_for_hashing():
    ist = timezone(timedelta(hours=5, minutes=30))
    same_instant = FIXED.astimezone(ist)
    assert format_timestamp(same_instant) == format_timestamp(FIXED) == "2026-01-02T03:04:05.000006Z"
    assert format_timestamp(FIXED.replace(tzinfo=None)) == format_timestamp(FIXED)  # naive == already UTC by construction


# ------------------------------------------------------------------------------------------- valid chains


def test_an_empty_ledger_verifies_as_empty_not_as_valid(session, ledger):
    result = ledger.verify(session)
    assert (result.status, result.events_checked, result.first_invalid_sequence, result.head) == (EMPTY, 0, None, None)
    assert ledger.head(session) is None


def test_the_first_event_links_to_the_genesis_value(session, ledger):
    (first,) = fill(session, ledger, 1)
    assert (first.sequence, first.prev_hash) == (1, GENESIS_HASH)
    assert ledger.verify(session).status == VALID


def test_a_valid_chain_verifies_and_reports_its_head(session, ledger):
    events = fill(session, ledger, 25)
    result = ledger.verify(session)
    assert (result.status, result.events_checked, result.reason_code) == (VALID, 25, None)
    assert result.head == LedgerHead(25, events[-1].event_hash)
    assert [e.sequence for e in events] == list(range(1, 26))
    assert all(events[i].prev_hash == events[i - 1].event_hash for i in range(1, 25))


def test_verification_spans_more_than_one_read_batch(session, ledger, monkeypatch):
    monkeypatch.setattr("wealthpilot.security.ledger._VERIFY_BATCH", 4)
    fill(session, ledger, 11)
    assert ledger.verify(session).events_checked == 11


def test_stored_events_round_trip_through_the_database_unchanged(session, ledger):
    (event,) = fill(session, ledger, 1)
    stored = ledger.event_at(session, 1)
    assert stored == event
    assert ledger.event_at(session, 2) is None


def test_the_local_implementation_satisfies_the_ledger_interface(ledger):
    assert isinstance(ledger, AuditLedger)


def test_timestamps_come_from_the_injected_clock_in_utc(session):
    clock_ledger = LocalHashChainLedger(clock=lambda: FIXED.astimezone(timezone(timedelta(hours=-8))))
    event = clock_ledger.append(session, EVENT_PROTECTED_RECORD_ACCESSED, ref())
    session.commit()
    assert event.occurred_at == FIXED and event.occurred_at.utcoffset() == timedelta(0)
    assert clock_ledger.verify(session).status == VALID


# --------------------------------------------------------------------------------------------- tamper detection


def test_a_modified_event_payload_is_detected_at_that_event(session, ledger):
    fill(session, ledger, 6)
    raw(session, "UPDATE audit_ledger_events SET event_type = :t WHERE sequence = 4", t=EVENT_PROTECTED_RECORD_DELETED)
    result = ledger.verify(session)
    assert (result.status, result.first_invalid_sequence, result.reason_code) == (INVALID, 4, "hash_mismatch")
    assert result.events_checked == 3


@pytest.mark.parametrize(
    ("column", "value"),
    [("occurred_at", "2030-01-01 00:00:00.000000"), ("record_ref", "11111111-1111-4111-8111-111111111111"), ("record_ref", None)],
)
def test_modifying_any_other_field_is_detected(session, ledger, column, value):
    fill(session, ledger, 5)
    raw(session, f"UPDATE audit_ledger_events SET {column} = :v WHERE sequence = 3", v=value)
    result = ledger.verify(session)
    assert (result.status, result.first_invalid_sequence, result.reason_code) == (INVALID, 3, "hash_mismatch")


def test_a_modified_stored_hash_is_detected(session, ledger):
    fill(session, ledger, 5)
    raw(session, "UPDATE audit_ledger_events SET event_hash = :h WHERE sequence = 2", h="a" * 64)
    result = ledger.verify(session)
    assert (result.first_invalid_sequence, result.reason_code) == (2, "hash_mismatch")


def test_a_broken_previous_hash_link_is_detected(session, ledger):
    fill(session, ledger, 5)
    raw(session, "UPDATE audit_ledger_events SET prev_hash = :h WHERE sequence = 4", h="b" * 64)
    result = ledger.verify(session)
    assert (result.status, result.first_invalid_sequence, result.reason_code) == (INVALID, 4, "previous_hash_mismatch")


def test_an_event_removed_from_the_middle_is_detected(session, ledger):
    fill(session, ledger, 6)
    raw(session, "DELETE FROM audit_ledger_events WHERE sequence = 3")
    result = ledger.verify(session)
    assert (result.status, result.first_invalid_sequence, result.reason_code) == (INVALID, 4, "sequence_gap")


def test_removing_the_start_of_the_chain_is_detected(session, ledger):
    fill(session, ledger, 4)
    raw(session, "DELETE FROM audit_ledger_events WHERE sequence = 1")
    result = ledger.verify(session)
    assert (result.first_invalid_sequence, result.reason_code) == (2, "missing_genesis")


def test_reordered_events_are_detected(session, ledger):
    fill(session, ledger, 5)
    raw(session, "UPDATE audit_ledger_events SET sequence = 1002 WHERE sequence = 2")
    raw(session, "UPDATE audit_ledger_events SET sequence = 2 WHERE sequence = 3")
    raw(session, "UPDATE audit_ledger_events SET sequence = 3 WHERE sequence = 1002")
    result = ledger.verify(session)
    assert result.status == INVALID and result.first_invalid_sequence == 2


def test_an_unknown_schema_version_or_malformed_field_is_reported(session, ledger):
    fill(session, ledger, 3)
    raw(session, "UPDATE audit_ledger_events SET schema_version = 9 WHERE sequence = 2")
    assert ledger.verify(session).reason_code == "unsupported_schema_version"
    raw(session, "UPDATE audit_ledger_events SET schema_version = 1, record_ref = :r WHERE sequence = 2", r="alice@example.com")
    result = ledger.verify(session)
    assert (result.first_invalid_sequence, result.reason_code) == (2, "malformed_event")


def test_the_reported_reason_is_fixed_text_that_cannot_contain_event_data(session, ledger):
    fill(session, ledger, 3)
    raw(session, "UPDATE audit_ledger_events SET record_ref = :r WHERE sequence = 2", r="secret@example.com")
    result = ledger.verify(session)
    assert "secret" not in (result.reason or "") and "example.com" not in (result.reason or "")


# ------------------------------------------------------------------------------------- what the chain cannot do


def test_removing_the_newest_events_is_invisible_without_an_externally_recorded_head(session, ledger):
    events = fill(session, ledger, 6)
    anchored = LedgerHead(6, events[-1].event_hash)  # what an external anchor would have recorded
    raw(session, "DELETE FROM audit_ledger_events WHERE sequence > 4")
    assert ledger.verify(session).status == VALID  # LIMITATION: the shortened chain is internally consistent
    detected = ledger.verify(session, expected_head=anchored)
    assert (detected.status, detected.reason_code) == (INVALID, "head_mismatch")


def test_an_expected_head_on_an_empty_ledger_is_a_mismatch(session, ledger):
    assert ledger.verify(session, expected_head=LedgerHead(3, "c" * 64)).reason_code == "head_mismatch"


def test_a_matching_expected_head_verifies(session, ledger):
    events = fill(session, ledger, 3)
    assert ledger.verify(session, expected_head=LedgerHead(3, events[-1].event_hash)).status == VALID


def test_a_privileged_full_chain_rewrite_still_verifies_locally_which_is_why_this_is_not_tamper_proof(session, ledger):
    """Documents the limitation instead of hiding it: anyone who can write the table can rewrite EVERY event and
    recompute every hash, and the local verifier cannot tell. Only an independently recorded head exposes it."""
    original = fill(session, ledger, 5)
    anchored = LedgerHead(5, original[-1].event_hash)

    rows = session.execute(text("SELECT sequence, occurred_at, record_ref FROM audit_ledger_events ORDER BY sequence")).all()
    for row in rows:  # park the old hashes on unique placeholders first: the columns are UNIQUE
        session.execute(
            text("UPDATE audit_ledger_events SET prev_hash = :p, event_hash = :h WHERE sequence = :s"),
            {"p": f"{row.sequence:064d}", "h": f"{row.sequence + 100:064d}", "s": row.sequence},
        )
    prev = GENESIS_HASH
    for row in rows:  # then write a different history with every hash recomputed
        occurred = datetime.fromisoformat(row.occurred_at).replace(tzinfo=UTC)
        digest = compute_event_hash(prev, row.sequence, EVENT_ACCESS_DENIED, occurred, row.record_ref, 1)
        session.execute(
            text("UPDATE audit_ledger_events SET event_type = :t, prev_hash = :p, event_hash = :h WHERE sequence = :s"),
            {"t": EVENT_ACCESS_DENIED, "p": prev, "h": digest, "s": row.sequence},
        )
        prev = digest
    session.commit()

    rewritten = ledger.verify(session)
    assert rewritten.status == VALID  # LIMITATION: a consistent forgery passes
    assert ledger.verify(session, expected_head=anchored).reason_code == "head_mismatch"  # an external anchor catches it


# ------------------------------------------------------------------------------ appending: privacy and concurrency


def test_events_have_no_field_that_could_hold_sensitive_content():
    assert {c.name for c in AuditLedgerEvent.__table__.columns} == {
        "sequence", "event_type", "occurred_at", "record_ref", "schema_version", "prev_hash", "event_hash",
    }
    assert EVENT_TYPES == {
        EVENT_PROTECTED_RECORD_CREATED, EVENT_PROTECTED_RECORD_ACCESSED, EVENT_PROTECTED_RECORD_UPDATED,
        EVENT_PROTECTED_RECORD_DELETED, EVENT_ACCESS_DENIED,
    }


@pytest.mark.parametrize(
    "bad_ref",
    ["alice@example.com", "₹45,000 salary", "my private note", "42", "11111111-1111-4111-8111-11111111111G", str(uuid.uuid4()).upper(), "a" * 200],
)
def test_a_record_reference_can_only_be_an_opaque_uuid(session, ledger, bad_ref):
    with pytest.raises(LedgerError):
        ledger.append(session, EVENT_PROTECTED_RECORD_CREATED, bad_ref)
    assert ledger.head(session) is None  # nothing persisted


def test_an_unknown_event_type_is_refused(session, ledger):
    with pytest.raises(LedgerError):
        ledger.append(session, "user.typed.free.text", ref())


def test_an_event_may_have_no_record_reference(session, ledger):
    event = ledger.append(session, EVENT_ACCESS_DENIED, None)
    session.commit()
    assert event.record_ref is None and ledger.verify(session).status == VALID


def test_an_append_that_loses_a_race_fails_loudly_and_leaves_the_chain_intact(session, make_session, ledger):
    """The advisory lock does not exist on SQLite, so this exercises the UNIQUE backstop: a writer holding a stale view
    of the head tries to reuse an existing position. It must raise, not fork or silently overwrite."""
    fill(session, ledger, 2)

    class StaleHead(LocalHashChainLedger):
        @staticmethod
        def _tail(session):
            return None  # believes the ledger is still empty

    with make_session() as other:
        with pytest.raises(LedgerError):
            StaleHead().append(other, EVENT_PROTECTED_RECORD_CREATED, ref())
        other.rollback()
    result = ledger.verify(session)
    assert (result.status, result.events_checked) == (VALID, 2)


def test_a_failed_append_does_not_poison_the_session_for_a_retry(session, ledger):
    fill(session, ledger, 1)

    class StaleHead(LocalHashChainLedger):
        @staticmethod
        def _tail(session):
            return None

    with pytest.raises(LedgerError):
        StaleHead().append(session, EVENT_PROTECTED_RECORD_CREATED, ref())  # the savepoint absorbed the conflict
    ledger.append(session, EVENT_PROTECTED_RECORD_CREATED, ref())
    session.commit()
    assert ledger.verify(session).events_checked == 2


def test_concurrent_appenders_produce_one_gapless_verifiable_chain(engine, make_session, ledger):
    threads, per_thread = 6, 5
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(per_thread):
                for _attempt in range(200):
                    with make_session() as db:
                        try:
                            ledger.append(db, EVENT_PROTECTED_RECORD_ACCESSED, ref())
                            db.commit()
                            break
                        except (LedgerError, OperationalError):
                            db.rollback()  # lost the race: retry on a fresh view of the head
                else:
                    raise AssertionError("append never succeeded")
        except BaseException as exc:  # noqa: BLE001 - surfaced below
            errors.append(exc)

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    assert not errors, errors

    with make_session() as db:
        result = ledger.verify(db)
        sequences = [r[0] for r in db.execute(text("SELECT sequence FROM audit_ledger_events ORDER BY sequence"))]
    assert (result.status, result.events_checked) == (VALID, threads * per_thread)
    assert sequences == list(range(1, threads * per_thread + 1))
