"""Adapter-contract tests: the shipped anchor is honestly 'not configured' and never fabricates a receipt."""

from __future__ import annotations

import uuid

import pytest

from wealthpilot.security.anchor import (
    LedgerAnchor,
    LedgerCommitment,
    UnconfiguredAnchor,
    commitment_from_head,
    verify_commitment_against_ledger,
)
from wealthpilot.security.errors import AnchorUnavailableError
from wealthpilot.security.ledger import EVENT_PROTECTED_RECORD_CREATED, LocalHashChainLedger


def test_the_local_anchor_reports_that_no_external_ledger_exists():
    anchor = UnconfiguredAnchor()
    assert isinstance(anchor, LedgerAnchor)
    status = anchor.status()
    assert status.state == "not_configured" and "local only" in status.detail


def test_nothing_can_be_submitted_and_no_receipt_is_ever_fabricated():
    anchor = UnconfiguredAnchor()
    commitment = LedgerCommitment(sequence=3, head_hash="a" * 64, schema_version=1)
    with pytest.raises(AnchorUnavailableError):
        anchor.submit_commitment(commitment)
    assert anchor.get_receipt(commitment) is None
    verification = anchor.verify_commitment(commitment, None)
    assert verification.status == "unverified"


def test_a_commitment_carries_only_a_position_and_a_hash():
    assert set(LedgerCommitment.__dataclass_fields__) == {"sequence", "head_hash", "schema_version"}


def test_a_commitment_is_verified_against_the_local_off_chain_event(session):
    ledger = LocalHashChainLedger()
    for _ in range(3):
        ledger.append(session, EVENT_PROTECTED_RECORD_CREATED, str(uuid.uuid4()))
    session.commit()
    commitment = commitment_from_head(ledger.head(session))
    assert verify_commitment_against_ledger(session, ledger, commitment).status == "verified"
    assert verify_commitment_against_ledger(session, ledger, LedgerCommitment(3, "f" * 64, 1)).status == "mismatch"
    assert verify_commitment_against_ledger(session, ledger, LedgerCommitment(9, commitment.head_hash, 1)).status == "mismatch"
