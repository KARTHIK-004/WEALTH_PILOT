"""Protected notes and the profile's security status (ADR-047).

Thin routes; authorization, encryption and the audit trail live in `api/services/protected_record_service.py`. Every
route requires the caller's `X-Customer-Id` to equal the `profile_id` in the path (the project's existing, prototype-level
identity mechanism: ADR-020/031). Responses that may carry the user's words are marked `no-store`. The note body is the
user's own text: it is never logged and a malformed body is never echoed in the 422 (api/errors.py).

There is deliberately no endpoint that lists, verifies or reads another profile's records, and no endpoint that exposes
the audit events themselves; the status route reports only the outcome of verifying the chain.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_acting_customer_id, get_audit_ledger, get_encryption_service, get_ledger_anchor, get_session
from wealthpilot.api.schemas import ProtectedNoteIn, ProtectedNoteListOut, ProtectedNoteMetadataOut, ProtectedNoteOut, SecurityStatusOut
from wealthpilot.api.services import protected_record_service as service
from wealthpilot.security.anchor import LedgerAnchor
from wealthpilot.security.crypto import EncryptionService
from wealthpilot.security.ledger import AuditLedger

router = APIRouter(tags=["protected-records"])

_NO_STORE = "no-store"


@router.post("/api/profiles/{profile_id}/protected-notes", response_model=ProtectedNoteMetadataOut, status_code=status.HTTP_201_CREATED)
def create_protected_note(
    profile_id: int,
    payload: ProtectedNoteIn,
    response: Response,
    acting: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
    ledger: AuditLedger = Depends(get_audit_ledger),
    encryption: EncryptionService = Depends(get_encryption_service),
) -> ProtectedNoteMetadataOut:
    """Encrypts the note and stores only the ciphertext. The response carries metadata, never the note."""
    response.headers["Cache-Control"] = _NO_STORE
    return service.create_note(session, ledger, encryption, profile_id, acting, payload.content)


@router.get("/api/profiles/{profile_id}/protected-notes", response_model=ProtectedNoteListOut)
def list_protected_notes(
    profile_id: int,
    response: Response,
    acting: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
    ledger: AuditLedger = Depends(get_audit_ledger),
) -> ProtectedNoteListOut:
    """The profile's note ids and timestamps. Nothing is decrypted."""
    response.headers["Cache-Control"] = _NO_STORE
    return service.list_notes(session, ledger, profile_id, acting)


@router.get("/api/profiles/{profile_id}/protected-notes/{record_id}", response_model=ProtectedNoteOut)
def get_protected_note(
    profile_id: int,
    record_id: str,
    response: Response,
    acting: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
    ledger: AuditLedger = Depends(get_audit_ledger),
    encryption: EncryptionService = Depends(get_encryption_service),
) -> ProtectedNoteOut:
    """Decrypts the note for its owner, after authorization, and records the access in the audit ledger."""
    response.headers["Cache-Control"] = _NO_STORE
    return service.get_note(session, ledger, encryption, profile_id, acting, record_id)


@router.put("/api/profiles/{profile_id}/protected-notes/{record_id}", response_model=ProtectedNoteMetadataOut)
def update_protected_note(
    profile_id: int,
    record_id: str,
    payload: ProtectedNoteIn,
    response: Response,
    acting: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
    ledger: AuditLedger = Depends(get_audit_ledger),
    encryption: EncryptionService = Depends(get_encryption_service),
) -> ProtectedNoteMetadataOut:
    response.headers["Cache-Control"] = _NO_STORE
    return service.update_note(session, ledger, encryption, profile_id, acting, record_id, payload.content)


@router.delete("/api/profiles/{profile_id}/protected-notes/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_protected_note(
    profile_id: int,
    record_id: str,
    acting: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
    ledger: AuditLedger = Depends(get_audit_ledger),
) -> Response:
    service.delete_note(session, ledger, profile_id, acting, record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": _NO_STORE})


@router.get("/api/profiles/{profile_id}/security-status", response_model=SecurityStatusOut)
def get_security_status(
    profile_id: int,
    response: Response,
    acting: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
    ledger: AuditLedger = Depends(get_audit_ledger),
    encryption: EncryptionService = Depends(get_encryption_service),
    anchor: LedgerAnchor = Depends(get_ledger_anchor),
) -> SecurityStatusOut:
    """What is protected, and the result of checks run now: an encryption round trip and a full audit-chain verification."""
    response.headers["Cache-Control"] = _NO_STORE
    return service.security_status(session, ledger, encryption, anchor, profile_id, acting)
