"""Authenticated encryption for sensitive records at rest.

AES-256-GCM through `cryptography` (already installed as a dependency of `google-auth`; pinned explicitly in
`pyproject.toml`). A fresh 96-bit nonce from the OS CSPRNG is drawn for every encryption. The stored envelope is
`(version, algorithm, key_id, nonce, ciphertext+tag)`; none of it is secret except that the ciphertext is unreadable
without the key.

Associated data binds the ciphertext to its context, so a ciphertext copied to another row, owner or purpose, or
whose metadata was edited (for example a downgraded version/algorithm or a swapped key id), fails authentication
instead of decrypting. The context is: envelope version, algorithm, key id, purpose, record id, owner id.

Fail-closed behaviour: any key problem, malformed envelope or authentication failure raises; there is no plaintext
fallback, no default key and no partial result. Error messages are fixed strings (see `errors.py`).

This service encrypts and decrypts whatever it is handed. It does NOT authorise anything: callers authorise first.

Nonce note: random 96-bit nonces are safe for far more messages than this prototype will ever write under one key
(NIST SP 800-38D bounds random-nonce use to 2^32 encryptions per key); a deployment with high volume should rotate keys
before that bound or use a KMS-managed data key per record.
"""

from __future__ import annotations

import secrets
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from wealthpilot.security.errors import DecryptionError, EncryptionError, KeyUnavailableError, MalformedEnvelopeError
from wealthpilot.security.keys import KEY_BYTES, KeyProvider

ENVELOPE_VERSION = 1
ALGORITHM = "AES-256-GCM"
NONCE_BYTES = 12
TAG_BYTES = 16
MAX_PLAINTEXT_BYTES = 64 * 1024
_AAD_DOMAIN = b"wealthpilot/aad/v1"


@dataclass(frozen=True)
class EncryptionContext:
    """What a ciphertext is bound to. All three must match at decryption time."""

    purpose: str  # what kind of field/record this is, e.g. "private_note"
    record_id: str  # the record's own id
    owner_id: int  # the customer the record belongs to


@dataclass(frozen=True)
class Envelope:
    """A versioned ciphertext container. `repr` omits the bytes."""

    version: int
    algorithm: str
    key_id: str
    nonce: bytes
    ciphertext: bytes  # ciphertext with the 16-byte GCM tag appended

    def __repr__(self) -> str:
        return f"Envelope(version={self.version}, algorithm={self.algorithm!r}, key_id={self.key_id!r}, <{len(self.ciphertext)} bytes>)"

    def validate_shape(self) -> None:
        """Rejects an envelope this code cannot interpret, before any key is touched."""
        if self.version != ENVELOPE_VERSION:
            raise MalformedEnvelopeError("Unsupported envelope version.")
        if self.algorithm != ALGORITHM:
            raise MalformedEnvelopeError("Unsupported encryption algorithm.")
        if not isinstance(self.nonce, bytes) or len(self.nonce) != NONCE_BYTES:
            raise MalformedEnvelopeError("Envelope nonce has the wrong length.")
        if not isinstance(self.ciphertext, bytes) or len(self.ciphertext) < TAG_BYTES:
            raise MalformedEnvelopeError("Envelope ciphertext is truncated.")
        if not isinstance(self.key_id, str) or not self.key_id:
            raise MalformedEnvelopeError("Envelope names no key.")


def _field(value: str) -> bytes:
    data = value.encode("utf-8")
    return struct.pack(">I", len(data)) + data


def build_aad(version: int, algorithm: str, key_id: str, context: EncryptionContext) -> bytes:
    """Unambiguous (length-prefixed) encoding of everything the ciphertext is bound to."""
    return _AAD_DOMAIN + b"".join(
        _field(part) for part in (str(version), algorithm, key_id, context.purpose, context.record_id, str(context.owner_id))
    )


class EncryptionService:
    def __init__(self, key_provider: KeyProvider) -> None:
        self._keys = key_provider

    def _aesgcm(self, key_id: str) -> AESGCM:
        key = self._keys.get_key(key_id)
        if len(key) != KEY_BYTES:
            raise KeyUnavailableError("Encryption key has the wrong length.")
        return AESGCM(key)

    def encrypt(self, plaintext: bytes, context: EncryptionContext) -> Envelope:
        if not isinstance(plaintext, bytes | bytearray) or len(plaintext) > MAX_PLAINTEXT_BYTES:
            raise EncryptionError("Plaintext is not acceptable for encryption.")
        key_id = self._keys.active_key_id()
        aesgcm = self._aesgcm(key_id)
        nonce = secrets.token_bytes(NONCE_BYTES)
        aad = build_aad(ENVELOPE_VERSION, ALGORITHM, key_id, context)
        try:
            ciphertext = aesgcm.encrypt(nonce, bytes(plaintext), aad)
        except Exception:  # the library's message is never propagated
            raise EncryptionError("Encryption failed.") from None
        return Envelope(ENVELOPE_VERSION, ALGORITHM, key_id, nonce, ciphertext)

    def decrypt(self, envelope: Envelope, context: EncryptionContext) -> bytes:
        envelope.validate_shape()
        aesgcm = self._aesgcm(envelope.key_id)
        aad = build_aad(envelope.version, envelope.algorithm, envelope.key_id, context)
        try:
            return aesgcm.decrypt(envelope.nonce, envelope.ciphertext, aad)
        except InvalidTag:
            raise DecryptionError("The stored record failed authentication.") from None
        except Exception:
            raise DecryptionError("The stored record could not be decrypted.") from None

    def configured(self) -> bool:
        """True when an active key can be loaded. Never reveals why not."""
        try:
            self._aesgcm(self._keys.active_key_id())
            return True
        except Exception:
            return False

    def self_test(self) -> bool:
        """A REAL round trip with a random probe (nothing is stored): proves a key is configured, loadable and that
        encryption, authentication and decryption work. Returns False on any failure -- never raises."""
        try:
            probe = secrets.token_bytes(16)
            context = EncryptionContext(purpose="self_test", record_id=secrets.token_hex(8), owner_id=0)
            return self.decrypt(self.encrypt(probe, context), context) == probe
        except Exception:
            return False
