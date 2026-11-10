"""Protected notes: the off-chain, encrypted, owner-scoped repository and its audit trail (ADR-047).

Order of every operation: AUTHORIZE -> (encrypt | fetch + decrypt) -> persist -> append audit event. Encryption happens
before anything is written, so a failed encryption persists nothing; the audit event is appended in the SAME database
transaction as the data change (the request's session), so data and audit succeed or fail together, and an audit failure
aborts the operation. The only event written outside that rule is `access_denied`, which has no data change to be atomic
with: it is committed on its own, best effort, before the denial is returned.

Authorization is the project's existing mechanism and nothing stronger (ADR-020/031): the caller asserts the customer it
acts as in `X-Customer-Id`, and every operation requires that to equal the profile in the path. The prototype has no
server session, so this stops accidental and URL-edited cross-profile access; it cannot stop a client that simply lies
about its header. Real confidentiality against a malicious client needs real authentication (docs/THREAT_MODEL.md).

Existence is never leaked: a record id that is unknown, malformed or owned by another profile produces the same 404.
Plaintext exists only in local variables inside this module; it is not logged, cached, or written to the ledger.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from wealthpilot.api.errors import (
    AccessDeniedError,
    CustomerNotFoundError,
    ProtectedRecordIntegrityError,
    ProtectedRecordNotFoundError,
    ServiceUnavailableError,
)
from wealthpilot.api.schemas import (
    PROTOTYPE_NOTICE,
    EncryptionStatusOut,
    ExternalAnchorStatusOut,
    LedgerStatusOut,
    LegacyDataStatusOut,
    ProtectedNoteListOut,
    ProtectedNoteMetadataOut,
    ProtectedNoteOut,
    ProtectionInfoOut,
    SecurityStatusOut,
)
from wealthpilot.db.models import AuditLedgerEvent, Customer, ProtectedRecord
from wealthpilot.security.anchor import LedgerAnchor
from wealthpilot.security.crypto import ALGORITHM, EncryptionContext, EncryptionService, Envelope
from wealthpilot.security.errors import DecryptionError, EncryptionError, KeyUnavailableError, MalformedEnvelopeError, SecurityError
from wealthpilot.security.ledger import (
    EVENT_ACCESS_DENIED,
    EVENT_PROTECTED_RECORD_ACCESSED,
    EVENT_PROTECTED_RECORD_CREATED,
    EVENT_PROTECTED_RECORD_DELETED,
    EVENT_PROTECTED_RECORD_UPDATED,
    AuditLedger,
)

logger = logging.getLogger(__name__)

PURPOSE = "private_note"
_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Verified against db/models.py: every one of these is stored in plaintext today. Only `protected_records` is encrypted.
UNPROTECTED_EXISTING_DATA = [
    "Customer profile (name, age, income, employment status, risk inputs)",
    "Financial inputs and monthly financial records",
    "Questionnaire answers and financial goals",
    "Household finance records and household goals",
    "Risk assessments, recommendations, analysis runs and agent logs",
    "Transactions and market data",
]
LIMITATIONS = [
    "Identity is asserted by the client (X-Customer-Id); there is no server-side authentication, so a client that lies about its identity is not stopped.",
    "The development key provider reads keys from the environment; it is not a managed key-management service.",
    "The audit chain lives in the same database as the data: it detects accidental or partial edits, not a privileged attacker who rewrites the whole chain.",
    "Only protected notes are encrypted; existing records stay in plaintext until they are deliberately migrated.",
]


def _record_denial(session: Session, ledger: AuditLedger, record_ref: str | None) -> None:
    """Best-effort audit of a refused request, committed on its own (the request is about to fail, so the request
    transaction would otherwise discard it). Never raises and never changes the response the caller receives."""
    try:
        ledger.append(session, EVENT_ACCESS_DENIED, record_ref if record_ref and _UUID_PATTERN.fullmatch(record_ref) else None)
        session.commit()
    except (SecurityError, SQLAlchemyError):
        session.rollback()
        logger.warning("Could not record an access-denied audit event.")


_STORAGE_TABLES = (ProtectedRecord.__tablename__, AuditLedgerEvent.__tablename__)
_storage_ready: set[str] = set()  # databases already seen to have both tables (a positive answer never changes; a negative one is re-checked)


def _ensure_storage(session: Session) -> None:
    """The two tables come from migration `f7a2d4b6c810`. Where it has not been applied (a database that was not upgraded), say so plainly with a 503 instead of letting the
    first query fail as an anonymous 500 with a logged traceback. Checked once per database; nothing is created here."""
    bind = session.get_bind()
    key = str(bind.engine.url) if hasattr(bind, "engine") else str(bind.url)
    if key in _storage_ready:
        return
    try:
        present = all(inspect(bind).has_table(name) for name in _STORAGE_TABLES)
    except SQLAlchemyError:
        present = False
    if not present:
        raise ServiceUnavailableError("Protected storage is not set up on this database: the migration that creates its tables has not been applied. Nothing was read or saved.")
    _storage_ready.add(key)


def _authorize(session: Session, ledger: AuditLedger, profile_id: int, acting_customer_id: int, record_ref: str | None = None) -> None:
    if acting_customer_id != profile_id:
        _record_denial(session, ledger, record_ref)
        raise AccessDeniedError("The acting customer does not match this profile.")
    _ensure_storage(session)
    if session.get(Customer, profile_id) is None:
        raise CustomerNotFoundError(f"No customer profile with id {profile_id}.")


def _metadata(row: ProtectedRecord) -> ProtectedNoteMetadataOut:
    return ProtectedNoteMetadataOut(
        id=row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        protection=ProtectionInfoOut(
            encrypted_at_rest=True, algorithm=row.algorithm, envelope_version=row.envelope_version, storage="off_chain_private_database"
        ),
    )


def _encrypt(service: EncryptionService, content: str, context: EncryptionContext) -> Envelope:
    try:
        return service.encrypt(content.encode("utf-8"), context)
    except KeyUnavailableError:
        raise ServiceUnavailableError("Protected storage is not configured; nothing was saved.") from None
    except EncryptionError:
        raise ServiceUnavailableError("The record could not be encrypted; nothing was saved.") from None


def _decrypt(service: EncryptionService, row: ProtectedRecord) -> str:
    envelope = Envelope(row.envelope_version, row.algorithm, row.key_id, bytes(row.nonce), bytes(row.ciphertext))
    try:
        return service.decrypt(envelope, EncryptionContext(row.purpose, row.id, row.customer_id)).decode("utf-8")
    except KeyUnavailableError:
        raise ServiceUnavailableError("Protected storage is not available.") from None
    except (DecryptionError, MalformedEnvelopeError, UnicodeDecodeError):
        logger.warning("A protected record failed authentication.")
        raise ProtectedRecordIntegrityError("The stored record could not be verified, so it was not returned.") from None


def _owned_row(session: Session, ledger: AuditLedger, profile_id: int, record_id: str) -> ProtectedRecord:
    """The record, only if it belongs to `profile_id`. Unknown, malformed and foreign ids are indistinguishable."""
    row = None
    if _UUID_PATTERN.fullmatch(record_id):
        row = session.execute(
            select(ProtectedRecord).where(ProtectedRecord.id == record_id, ProtectedRecord.customer_id == profile_id)
        ).scalar_one_or_none()
    if row is None:
        _record_denial(session, ledger, record_id)
        raise ProtectedRecordNotFoundError("No protected record with this id exists for this profile.")
    return row


# -- operations ------------------------------------------------------------------------------------------------------


def create_note(
    session: Session, ledger: AuditLedger, service: EncryptionService, profile_id: int, acting_customer_id: int, content: str
) -> ProtectedNoteMetadataOut:
    _authorize(session, ledger, profile_id, acting_customer_id)
    record_id = str(uuid.uuid4())
    envelope = _encrypt(service, content, EncryptionContext(PURPOSE, record_id, profile_id))
    row = ProtectedRecord(
        id=record_id,
        customer_id=profile_id,
        purpose=PURPOSE,
        envelope_version=envelope.version,
        algorithm=envelope.algorithm,
        key_id=envelope.key_id,
        nonce=envelope.nonce,
        ciphertext=envelope.ciphertext,
    )
    session.add(row)
    session.flush()
    ledger.append(session, EVENT_PROTECTED_RECORD_CREATED, record_id)
    session.refresh(row)
    return _metadata(row)


def list_notes(session: Session, ledger: AuditLedger, profile_id: int, acting_customer_id: int) -> ProtectedNoteListOut:
    _authorize(session, ledger, profile_id, acting_customer_id)
    rows = session.execute(
        select(ProtectedRecord).where(ProtectedRecord.customer_id == profile_id).order_by(ProtectedRecord.created_at, ProtectedRecord.id)
    ).scalars()
    return ProtectedNoteListOut(items=[_metadata(row) for row in rows])


def get_note(
    session: Session, ledger: AuditLedger, service: EncryptionService, profile_id: int, acting_customer_id: int, record_id: str
) -> ProtectedNoteOut:
    _authorize(session, ledger, profile_id, acting_customer_id, record_id)
    row = _owned_row(session, ledger, profile_id, record_id)
    content = _decrypt(service, row)  # raises before any "accessed" event: a failed read is not a successful access
    ledger.append(session, EVENT_PROTECTED_RECORD_ACCESSED, row.id)
    return ProtectedNoteOut(**_metadata(row).model_dump(), content=content)


def update_note(
    session: Session, ledger: AuditLedger, service: EncryptionService, profile_id: int, acting_customer_id: int, record_id: str, content: str
) -> ProtectedNoteMetadataOut:
    _authorize(session, ledger, profile_id, acting_customer_id, record_id)
    row = _owned_row(session, ledger, profile_id, record_id)
    envelope = _encrypt(service, content, EncryptionContext(row.purpose, row.id, row.customer_id))
    row.envelope_version, row.algorithm, row.key_id = envelope.version, envelope.algorithm, envelope.key_id
    row.nonce, row.ciphertext = envelope.nonce, envelope.ciphertext
    session.flush()
    ledger.append(session, EVENT_PROTECTED_RECORD_UPDATED, row.id)
    session.refresh(row)
    return _metadata(row)


def delete_note(session: Session, ledger: AuditLedger, profile_id: int, acting_customer_id: int, record_id: str) -> None:
    _authorize(session, ledger, profile_id, acting_customer_id, record_id)
    row = _owned_row(session, ledger, profile_id, record_id)
    record_ref = row.id
    session.delete(row)
    session.flush()
    ledger.append(session, EVENT_PROTECTED_RECORD_DELETED, record_ref)


def security_status(
    session: Session, ledger: AuditLedger, service: EncryptionService, anchor: LedgerAnchor, profile_id: int, acting_customer_id: int
) -> SecurityStatusOut:
    """Real checks, run now: an encrypt/decrypt round trip with a random probe, and a full walk of the audit chain."""
    _authorize(session, ledger, profile_id, acting_customer_id)
    count = session.execute(select(func.count()).select_from(ProtectedRecord).where(ProtectedRecord.customer_id == profile_id)).scalar_one()

    if not service.configured():
        encryption = EncryptionStatusOut(
            status="not_configured", algorithm=ALGORITHM, self_test_passed=None,
            unavailable_reason="No usable encryption key is configured, so protected notes cannot be saved or read.",
        )
    elif service.self_test():
        encryption = EncryptionStatusOut(status="operational", algorithm=ALGORITHM, self_test_passed=True, unavailable_reason=None)
    else:
        encryption = EncryptionStatusOut(
            status="failed", algorithm=ALGORITHM, self_test_passed=False, unavailable_reason="The encryption self-test failed."
        )

    result = ledger.verify(session)
    ledger_status = LedgerStatusOut(
        kind="local_hash_chain",
        verification=result.status,  # type: ignore[arg-type]
        events_checked=result.events_checked,
        first_invalid_sequence=result.first_invalid_sequence,
        reason=result.reason,
        note="Internally consistent means the recorded chain links up. It does not prove the database was never tampered with.",
    )
    anchor_status = anchor.status()
    return SecurityStatusOut(
        prototype_notice=PROTOTYPE_NOTICE,
        storage="off_chain_private_database",
        protected_note_count=count,
        encryption=encryption,
        ledger=ledger_status,
        external_anchor=ExternalAnchorStatusOut(state=anchor_status.state, detail=anchor_status.detail),  # type: ignore[arg-type]
        existing_data=LegacyDataStatusOut(
            encrypted=False,
            unprotected_categories=UNPROTECTED_EXISTING_DATA,
            note="Encryption applies only to protected notes. Everything listed here was stored before this feature and is not encrypted.",
        ),
        limitations=LIMITATIONS,
    )
