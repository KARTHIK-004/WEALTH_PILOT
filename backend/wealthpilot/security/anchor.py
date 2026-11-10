"""Adapter contract for a FUTURE permissioned-ledger integration.

The local hash chain cannot prove it was not rewritten (see `ledger.py`). The standard remedy is to periodically commit a
small digest of the chain -- its head (sequence + hash) -- to a system the application's database administrators do not
control: a permissioned ledger operated by a separate party, a notary or a write-once store. This module defines that
boundary and nothing more.

Rules for any implementation:
- Only privacy-reviewed digests cross this boundary (`LedgerCommitment`): a sequence number and a SHA-256 hash. Never a
  record, a plaintext, a key, an identifier of a person or a financial amount.
- Vendor-specific code lives entirely behind `LedgerAnchor`; nothing else in the application imports a vendor SDK.
- No wallet handling, cryptocurrency, tokenisation, smart-contract execution or public-chain upload.
- Unavailability is reported as unavailability (`AnchorStatus.state == "not_configured"` / `"unreachable"`), never
  faked as success.

The shipped implementation, `UnconfiguredAnchor`, is NOT connected to anything. It exists so the application and its
tests exercise the contract honestly: `submit_commitment` refuses, `get_receipt` finds nothing, and
`verify_commitment` answers "unverified". No receipt is ever fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from wealthpilot.security.errors import AnchorUnavailableError
from wealthpilot.security.ledger import AuditLedger, LedgerHead


@dataclass(frozen=True)
class LedgerCommitment:
    """The only thing that may leave the application: where the chain stands, and its hash."""

    sequence: int
    head_hash: str
    schema_version: int


@dataclass(frozen=True)
class AnchorReceipt:
    """Proof an external system accepted a commitment. Only a real backend may create one."""

    commitment: LedgerCommitment
    receipt_id: str
    anchored_at: datetime
    backend: str


@dataclass(frozen=True)
class AnchorStatus:
    state: str  # "not_configured" | "unreachable" | "available"
    detail: str


@dataclass(frozen=True)
class AnchorVerification:
    status: str  # "verified" | "mismatch" | "unverified"
    reason: str


@runtime_checkable
class LedgerAnchor(Protocol):
    def status(self) -> AnchorStatus: ...

    def submit_commitment(self, commitment: LedgerCommitment) -> AnchorReceipt:
        """Commit the digest externally. Raises `AnchorUnavailableError` when no external system can take it."""
        ...

    def get_receipt(self, commitment: LedgerCommitment) -> AnchorReceipt | None:
        """The receipt previously issued for exactly this commitment, or None."""
        ...

    def verify_commitment(self, commitment: LedgerCommitment, receipt: AnchorReceipt | None) -> AnchorVerification:
        """Does the external system confirm `receipt` for `commitment`? 'unverified' when it cannot say."""
        ...


class UnconfiguredAnchor:
    """The local prototype's anchor: there is no external ledger, and this says so."""

    def status(self) -> AnchorStatus:
        return AnchorStatus(state="not_configured", detail="No external permissioned ledger is configured; the audit chain is local only.")

    def submit_commitment(self, commitment: LedgerCommitment) -> AnchorReceipt:
        raise AnchorUnavailableError("No external ledger is configured.")

    def get_receipt(self, commitment: LedgerCommitment) -> AnchorReceipt | None:
        return None

    def verify_commitment(self, commitment: LedgerCommitment, receipt: AnchorReceipt | None) -> AnchorVerification:
        return AnchorVerification(status="unverified", reason="No external ledger is configured, so nothing can confirm this commitment.")


def commitment_from_head(head: LedgerHead, schema_version: int = 1) -> LedgerCommitment:
    return LedgerCommitment(sequence=head.sequence, head_hash=head.event_hash, schema_version=schema_version)


def verify_commitment_against_ledger(session: Session, ledger: AuditLedger, commitment: LedgerCommitment) -> AnchorVerification:
    """Checks a commitment against the OFF-CHAIN (local) event it claims to describe. This is the local half of
    commitment verification; the external half is `LedgerAnchor.verify_commitment`."""
    event = ledger.event_at(session, commitment.sequence)
    if event is None:
        return AnchorVerification(status="mismatch", reason="The local ledger has no event at the committed position.")
    if event.event_hash != commitment.head_hash:
        return AnchorVerification(status="mismatch", reason="The local event at the committed position has a different hash.")
    return AnchorVerification(status="verified", reason="The commitment matches the local event (local check only).")
