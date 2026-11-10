"""Local, append-only, hash-linked audit ledger. ACADEMIC PROTOTYPE -- NOT A BLOCKCHAIN.

What this is: events stored in the application's own PostgreSQL database, each carrying the SHA-256 of
(domain tag + previous event's hash + canonical serialization of its own fields). Editing, reordering or removing an
event in the middle of the chain makes `verify` fail at a specific sequence number.

What this is NOT: decentralized, consensus-backed, replicated, independently witnessed or immutable. One database
holds the whole chain, so anyone with write access to it (a DBA, an attacker who obtained database credentials, a
compromised application) can rewrite every event and recompute every hash, and the chain will still verify. Removing
the newest events is invisible to the chain alone; it is detected only when `verify` is given a head (sequence, hash)
that was recorded somewhere else (`expected_head`) -- which is exactly what an external anchor (see `anchor.py`) would
supply. A successful local verification therefore means "internally consistent", never "the database was not
tampered with".

Event content is deliberately minimal and structurally enforced: event type (from a closed allow-list), UTC
timestamp, an opaque record reference (a canonical lowercase UUID or none), schema version, previous hash, event hash.
There is no field that could hold an amount, name, e-mail, free text, token or key.

Canonical form (schema version 1): UTF-8 JSON of {event_type, occurred_at, record_ref, schema_version, sequence} with
sorted keys, `(",", ":")` separators and ASCII escaping; `occurred_at` is `YYYY-MM-DDTHH:MM:SS.ffffffZ` in UTC. Hash =
SHA-256(b"wealthpilot/ledger/v1\\n" + previous_hash_hex + b"\\n" + canonical). Genesis previous hash = 64 zeros.
The same function is used to write and to verify.

Ordering and concurrency: `sequence` is assigned by the ledger inside the caller's transaction after taking a
PostgreSQL transaction-scoped advisory lock, so concurrent appenders serialize. UNIQUE constraints on `sequence` and
`prev_hash` are the backstop (a SQLite test database has no advisory lock): a losing concurrent append raises
`LedgerError` rather than forking the chain. Appends happen in the SAME transaction as the data change they describe,
so data and audit are atomic with each other; an audit failure aborts the operation (fail closed).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wealthpilot.db.models import AuditLedgerEvent
from wealthpilot.security.errors import LedgerError

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64
HASH_DOMAIN = b"wealthpilot/ledger/v1\n"
_ADVISORY_LOCK_KEY = 0x57504C47  # "WPLG": one chain, one lock
_VERIFY_BATCH = 500

EVENT_PROTECTED_RECORD_CREATED = "protected_record.created"
EVENT_PROTECTED_RECORD_ACCESSED = "protected_record.accessed"
EVENT_PROTECTED_RECORD_UPDATED = "protected_record.updated"
EVENT_PROTECTED_RECORD_DELETED = "protected_record.deleted"
EVENT_ACCESS_DENIED = "protected_record.access_denied"

EVENT_TYPES = frozenset(
    {
        EVENT_PROTECTED_RECORD_CREATED,
        EVENT_PROTECTED_RECORD_ACCESSED,
        EVENT_PROTECTED_RECORD_UPDATED,
        EVENT_PROTECTED_RECORD_DELETED,
        EVENT_ACCESS_DENIED,
    }
)

_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# Verification outcomes.
VALID = "valid"
INVALID = "invalid"
EMPTY = "empty"


@dataclass(frozen=True)
class LedgerEvent:
    sequence: int
    event_type: str
    occurred_at: datetime  # timezone-aware, UTC
    record_ref: str | None
    schema_version: int
    prev_hash: str
    event_hash: str


@dataclass(frozen=True)
class LedgerHead:
    """The newest event's position and hash -- the small digest an external anchor would commit."""

    sequence: int
    event_hash: str


@dataclass(frozen=True)
class VerificationResult:
    status: str  # "valid" | "invalid" | "empty"
    events_checked: int
    first_invalid_sequence: int | None = None
    reason_code: str | None = None
    reason: str | None = None  # fixed, non-sensitive explanation
    head: LedgerHead | None = None


_REASONS = {
    "missing_genesis": "The chain does not start at the genesis position; earlier events are missing.",
    "sequence_gap": "An event is missing or out of order: the sequence numbers are not contiguous.",
    "unsupported_schema_version": "An event uses a schema version this verifier does not know.",
    "malformed_event": "An event has a field outside what the ledger allows.",
    "previous_hash_mismatch": "An event does not link to the hash of the event before it.",
    "hash_mismatch": "An event's stored hash does not match its contents.",
    "head_mismatch": "The newest event does not match the independently recorded head; events were removed or replaced.",
}


def normalize_utc(value: datetime) -> datetime:
    """Aware -> UTC. Naive values (SQLite drops the zone) are, by construction of this ledger, already UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_timestamp(value: datetime) -> str:
    return normalize_utc(value).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_payload(sequence: int, event_type: str, occurred_at: datetime, record_ref: str | None, schema_version: int) -> bytes:
    return json.dumps(
        {
            "event_type": event_type,
            "occurred_at": format_timestamp(occurred_at),
            "record_ref": record_ref,
            "schema_version": schema_version,
            "sequence": sequence,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def compute_event_hash(prev_hash: str, sequence: int, event_type: str, occurred_at: datetime, record_ref: str | None, schema_version: int) -> str:
    payload = canonical_payload(sequence, event_type, occurred_at, record_ref, schema_version)
    return hashlib.sha256(HASH_DOMAIN + prev_hash.encode("ascii") + b"\n" + payload).hexdigest()


def _validate_event_fields(event_type: str, record_ref: str | None) -> None:
    if event_type not in EVENT_TYPES:
        raise LedgerError("Unknown audit event type.")
    if record_ref is not None and not _UUID_PATTERN.fullmatch(record_ref):
        raise LedgerError("An audit event may reference a record only by its opaque identifier.")


@runtime_checkable
class AuditLedger(Protocol):
    """The audit-log contract. `LocalHashChainLedger` is the only implementation; a permissioned-ledger-backed one
    would satisfy the same interface (see `anchor.LedgerAnchor` for the narrower commitment contract)."""

    def append(self, session: Session, event_type: str, record_ref: str | None = None) -> LedgerEvent: ...

    def verify(self, session: Session, expected_head: LedgerHead | None = None) -> VerificationResult: ...

    def head(self, session: Session) -> LedgerHead | None: ...

    def event_at(self, session: Session, sequence: int) -> LedgerEvent | None: ...


class LocalHashChainLedger:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    # -- writing -----------------------------------------------------------------------------------------------

    def append(self, session: Session, event_type: str, record_ref: str | None = None) -> LedgerEvent:
        _validate_event_fields(event_type, record_ref)
        self._serialize_writers(session)
        tail = self._tail(session)
        sequence = 1 if tail is None else tail.sequence + 1
        prev_hash = GENESIS_HASH if tail is None else tail.event_hash
        occurred_at = normalize_utc(self._clock())
        event_hash = compute_event_hash(prev_hash, sequence, event_type, occurred_at, record_ref, SCHEMA_VERSION)
        try:
            with session.begin_nested():
                session.add(
                    AuditLedgerEvent(
                        sequence=sequence,
                        event_type=event_type,
                        occurred_at=occurred_at,
                        record_ref=record_ref,
                        schema_version=SCHEMA_VERSION,
                        prev_hash=prev_hash,
                        event_hash=event_hash,
                    )
                )
        except IntegrityError:
            raise LedgerError("The audit event conflicted with a concurrent append.") from None
        return LedgerEvent(sequence, event_type, occurred_at, record_ref, SCHEMA_VERSION, prev_hash, event_hash)

    @staticmethod
    def _serialize_writers(session: Session) -> None:
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})

    # -- reading -----------------------------------------------------------------------------------------------

    @staticmethod
    def _tail(session: Session) -> Any:
        return session.execute(
            select(AuditLedgerEvent.sequence, AuditLedgerEvent.event_hash).order_by(AuditLedgerEvent.sequence.desc()).limit(1)
        ).first()

    def head(self, session: Session) -> LedgerHead | None:
        tail = self._tail(session)
        return None if tail is None else LedgerHead(tail.sequence, tail.event_hash)

    def event_at(self, session: Session, sequence: int) -> LedgerEvent | None:
        row = session.execute(
            select(
                AuditLedgerEvent.sequence,
                AuditLedgerEvent.event_type,
                AuditLedgerEvent.occurred_at,
                AuditLedgerEvent.record_ref,
                AuditLedgerEvent.schema_version,
                AuditLedgerEvent.prev_hash,
                AuditLedgerEvent.event_hash,
            ).where(AuditLedgerEvent.sequence == sequence)
        ).first()
        if row is None:
            return None
        return LedgerEvent(row.sequence, row.event_type, normalize_utc(row.occurred_at), row.record_ref, row.schema_version, row.prev_hash, row.event_hash)

    def verify(self, session: Session, expected_head: LedgerHead | None = None) -> VerificationResult:
        """Walks the whole chain in sequence order. Reports the FIRST invalid event with a fixed, non-sensitive reason.
        Reads columns (not ORM entities) so rows changed behind the ORM's back are seen as they are stored."""
        expected_sequence = 1
        prev_hash = GENESIS_HASH
        checked = 0
        last: LedgerHead | None = None
        cursor = 0
        while True:
            batch: list[Any] = list(
                session.execute(
                    select(
                        AuditLedgerEvent.sequence,
                        AuditLedgerEvent.event_type,
                        AuditLedgerEvent.occurred_at,
                        AuditLedgerEvent.record_ref,
                        AuditLedgerEvent.schema_version,
                        AuditLedgerEvent.prev_hash,
                        AuditLedgerEvent.event_hash,
                    )
                    .where(AuditLedgerEvent.sequence > cursor)
                    .order_by(AuditLedgerEvent.sequence)
                    .limit(_VERIFY_BATCH)
                )
            )
            if not batch:
                break
            for row in batch:
                cursor = row.sequence
                problem = self._check_event(row, expected_sequence, prev_hash)
                if problem is not None:
                    return self._invalid(row.sequence, problem, checked, last)
                checked += 1
                expected_sequence += 1
                prev_hash = row.event_hash
                last = LedgerHead(row.sequence, row.event_hash)
        if expected_head is not None and last != expected_head:
            return self._invalid(None, "head_mismatch", checked, last)
        if last is None:
            return VerificationResult(status=EMPTY, events_checked=0)
        return VerificationResult(status=VALID, events_checked=checked, head=last)

    @staticmethod
    def _check_event(row: Any, expected_sequence: int, prev_hash: str) -> str | None:
        if row.sequence != expected_sequence:
            return "missing_genesis" if expected_sequence == 1 else "sequence_gap"
        if row.schema_version != SCHEMA_VERSION:
            return "unsupported_schema_version"
        if (
            row.event_type not in EVENT_TYPES
            or (row.record_ref is not None and not _UUID_PATTERN.fullmatch(row.record_ref))
            or not _HASH_PATTERN.fullmatch(row.prev_hash or "")
            or not _HASH_PATTERN.fullmatch(row.event_hash or "")
        ):
            return "malformed_event"
        if row.prev_hash != prev_hash:
            return "previous_hash_mismatch"
        recomputed = compute_event_hash(row.prev_hash, row.sequence, row.event_type, row.occurred_at, row.record_ref, row.schema_version)
        if recomputed != row.event_hash:
            return "hash_mismatch"
        return None

    @staticmethod
    def _invalid(sequence: int | None, code: str, checked: int, last: LedgerHead | None) -> VerificationResult:
        return VerificationResult(
            status=INVALID, events_checked=checked, first_invalid_sequence=sequence, reason_code=code, reason=_REASONS[code], head=last
        )
