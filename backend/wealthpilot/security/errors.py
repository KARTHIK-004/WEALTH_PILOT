"""Security-layer exceptions.

Messages are fixed strings. They never carry plaintext, ciphertext, a nonce, a key, a key value or user input, so an
exception that is logged or turned into a response cannot disclose any of them.
"""

from __future__ import annotations


class SecurityError(Exception):
    """Base class for every error raised by `wealthpilot.security`."""


class KeyUnavailableError(SecurityError):
    """No usable key: none configured, malformed key material, or an envelope names a key id this provider does not hold."""


class MalformedEnvelopeError(SecurityError):
    """A stored envelope is structurally invalid (unsupported version/algorithm, wrong nonce length, truncated ciphertext)."""


class DecryptionError(SecurityError):
    """Authentication failed: modified ciphertext/metadata, wrong key, or a record moved to a different owner/purpose/id.
    The cause is deliberately not distinguished."""


class EncryptionError(SecurityError):
    """Encryption could not be completed. Nothing must be persisted when this is raised."""


class LedgerError(SecurityError):
    """The audit ledger could not append an event (invalid event, or a conflicting concurrent append)."""


class AnchorUnavailableError(SecurityError):
    """No external ledger is configured, so nothing can be anchored."""
