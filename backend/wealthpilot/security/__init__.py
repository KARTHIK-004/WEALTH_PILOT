"""Sensitive-data protection prototype (ADR-047).

An academic security extension, not a replacement of the architecture:

- `keys`    -- the key-management boundary (`KeyProvider`); the only module that reads key material.
- `crypto`  -- `EncryptionService`: versioned AES-256-GCM envelopes with record-bound associated data. It encrypts and
               decrypts; it never decides who may read anything and never exposes a key.
- `ledger`  -- `AuditLedger` and `LocalHashChainLedger`: an append-only, hash-linked event log with a verifier.
               THIS IS NOT A BLOCKCHAIN: one database, no consensus, no replication, no independent witness.
- `anchor`  -- `LedgerAnchor`: the adapter contract a future permissioned-ledger integration would implement.
               The shipped implementation is explicitly "not configured" and never pretends otherwise.

Nothing here is imported by the advisory pipeline (`core/`, `agents/`), and no LLM or agent ever receives key material.
See `docs/THREAT_MODEL.md` and `docs/DECISIONS.md` ADR-047.
"""
