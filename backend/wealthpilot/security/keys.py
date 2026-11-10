"""Key-management boundary.

`KeyProvider` is the ONLY way the rest of the system obtains key material, and only `EncryptionService` calls it. A
production deployment would implement it against a managed KMS / HSM (envelope encryption: the KMS holds a key-encryption
key and wraps per-record or per-tenant data keys); nothing outside this module would change.

`EnvironmentKeyProvider` is the DEVELOPMENT provider. Be clear about what it is NOT: reading a key from an environment
variable is not equivalent to a managed KMS. The key sits in process memory and in whatever file or secret store populates
the environment, it has no hardware protection, no access policy, no usage audit trail, and anyone who can read the
process environment or `.env` can decrypt every record. Rotation is manual: add a new key id, make it active, keep the old
ids until every record has been re-encrypted (`PROTECTED_DATA_KEYS` holds all of them).

Configuration (read through `pydantic-settings`, never hard-coded, never defaulted):

    PROTECTED_DATA_KEYS=<key_id>:<base64 of 32 random bytes>[,<key_id>:<base64>...]
    PROTECTED_DATA_ACTIVE_KEY_ID=<key_id used for new encryptions>

Key material never appears in a repr, a log line, an exception message, an API response, the database or the ledger.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from wealthpilot.security.errors import KeyUnavailableError

KEY_BYTES = 32  # AES-256
KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


@runtime_checkable
class KeyProvider(Protocol):
    """What the encryption service needs from key management, and nothing more."""

    def active_key_id(self) -> str:
        """The non-secret id of the key used for NEW encryptions. Raises `KeyUnavailableError` when none is configured."""
        ...

    def get_key(self, key_id: str) -> bytes:
        """The raw key for `key_id` (for decryption of older envelopes too). Raises `KeyUnavailableError` if unknown."""
        ...


def _decode_key(encoded: str) -> bytes:
    try:
        raw = base64.b64decode(encoded.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise KeyUnavailableError("Encryption key material is not valid base64.") from None
    if len(raw) != KEY_BYTES:
        raise KeyUnavailableError(f"Encryption key material must decode to exactly {KEY_BYTES} bytes.")
    return raw


class EnvironmentKeyProvider:
    """Development key provider backed by configuration values. See the module docstring for its limits."""

    def __init__(self, keys_spec: str, active_key_id: str) -> None:
        self._keys: Mapping[str, bytes] = self._parse(keys_spec)
        self._active = active_key_id.strip()

    @staticmethod
    def _parse(spec: str) -> dict[str, bytes]:
        keys: dict[str, bytes] = {}
        for entry in (part for part in spec.split(",") if part.strip()):
            key_id, separator, encoded = entry.strip().partition(":")
            if not separator or not KEY_ID_PATTERN.fullmatch(key_id):
                raise KeyUnavailableError("Key configuration entries must look like <key_id>:<base64 key>.")
            if key_id in keys:
                raise KeyUnavailableError("Key configuration repeats a key id.")
            keys[key_id] = _decode_key(encoded)
        return keys

    def active_key_id(self) -> str:
        if not self._keys:
            raise KeyUnavailableError("No encryption key is configured.")
        if not self._active or self._active not in self._keys:
            raise KeyUnavailableError("The active encryption key id is not configured.")
        return self._active

    def get_key(self, key_id: str) -> bytes:
        try:
            return self._keys[key_id]
        except KeyError:
            raise KeyUnavailableError("The key named by this record is not available.") from None

    def __repr__(self) -> str:  # never reveals key ids' material
        return f"EnvironmentKeyProvider(keys={len(self._keys)}, active={'set' if self._active else 'unset'})"


class UnavailableKeyProvider:
    """Stands in when the configured key material is malformed: every operation fails closed with a fixed message."""

    def active_key_id(self) -> str:
        raise KeyUnavailableError("Encryption key configuration is invalid.")

    def get_key(self, key_id: str) -> bytes:
        raise KeyUnavailableError("Encryption key configuration is invalid.")


def generate_key_spec(key_id: str, random_bytes: bytes) -> str:
    """Formats one `<key_id>:<base64>` entry from caller-supplied random bytes (use `secrets.token_bytes(32)`).
    Provided so an operator tool or a test can build a configuration value; this module never generates or stores a key."""
    if not KEY_ID_PATTERN.fullmatch(key_id):
        raise KeyUnavailableError("Key ids use 1-32 letters, digits, '.', '_' or '-'.")
    if len(random_bytes) != KEY_BYTES:
        raise KeyUnavailableError(f"A key is exactly {KEY_BYTES} bytes.")
    return f"{key_id}:{base64.b64encode(random_bytes).decode('ascii')}"
