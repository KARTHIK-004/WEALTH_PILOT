"""Encryption service and key-provider tests. DB-free; every key is random bytes generated at run time (none is stored)."""

from __future__ import annotations

import base64
import logging
import secrets
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from wealthpilot.config.settings import Settings
from wealthpilot.security.crypto import (
    ALGORITHM,
    ENVELOPE_VERSION,
    MAX_PLAINTEXT_BYTES,
    NONCE_BYTES,
    EncryptionContext,
    EncryptionService,
    Envelope,
    build_aad,
)
from wealthpilot.security.errors import DecryptionError, EncryptionError, KeyUnavailableError, MalformedEnvelopeError
from wealthpilot.security.keys import EnvironmentKeyProvider, UnavailableKeyProvider, generate_key_spec

# Synthetic content only.
SECRET_TEXT = "Synthetic note: worried about the fictional car loan EMI"
CTX = EncryptionContext(purpose="private_note", record_id="3f1c9a52-7b8e-4d21-9a60-0c4e5d6f7a81", owner_id=7)


def new_key() -> bytes:
    return secrets.token_bytes(32)


def provider(*key_ids: str, active: str | None = None, keys: dict[str, bytes] | None = None) -> tuple[EnvironmentKeyProvider, dict[str, bytes]]:
    material = keys or {key_id: new_key() for key_id in key_ids}
    spec = ",".join(generate_key_spec(key_id, key) for key_id, key in material.items())
    return EnvironmentKeyProvider(spec, active or next(iter(material))), material


@pytest.fixture()
def service() -> EncryptionService:
    return EncryptionService(provider("k1")[0])


def encrypt(service: EncryptionService, text: str = SECRET_TEXT, context: EncryptionContext = CTX) -> Envelope:
    return service.encrypt(text.encode("utf-8"), context)


# --------------------------------------------------------------------------------------------- round trip and nonces


def test_round_trip_returns_the_original_plaintext(service):
    envelope = encrypt(service)
    assert service.decrypt(envelope, CTX).decode("utf-8") == SECRET_TEXT


def test_round_trip_handles_unicode_and_empty_payloads(service):
    for text in ("", "₹ 45,000 — मासिक बचत 💰", "x" * 5000):
        assert service.decrypt(encrypt(service, text), CTX).decode("utf-8") == text


def test_the_ciphertext_does_not_contain_the_plaintext(service):
    envelope = encrypt(service)
    assert SECRET_TEXT.encode() not in envelope.ciphertext
    assert b"Synthetic" not in envelope.ciphertext
    assert len(envelope.ciphertext) == len(SECRET_TEXT.encode()) + 16  # GCM adds exactly the 16-byte tag


def test_every_encryption_uses_a_fresh_random_nonce(service):
    envelopes = [encrypt(service) for _ in range(200)]
    assert len({e.nonce for e in envelopes}) == 200
    assert len({e.ciphertext for e in envelopes}) == 200  # same plaintext + context, still different ciphertexts
    assert all(len(e.nonce) == NONCE_BYTES for e in envelopes)


def test_the_envelope_carries_versioned_non_secret_metadata(service):
    envelope = encrypt(service)
    assert (envelope.version, envelope.algorithm, envelope.key_id) == (ENVELOPE_VERSION, ALGORITHM, "k1")


def test_envelope_matches_standard_aes_256_gcm_so_it_is_not_a_homemade_format(service):
    """An independent decryption with the library's primitive, using the documented AAD layout."""
    key = new_key()
    svc = EncryptionService(provider(keys={"k1": key})[0])
    envelope = encrypt(svc)
    aad = build_aad(envelope.version, envelope.algorithm, envelope.key_id, CTX)
    assert AESGCM(key).decrypt(envelope.nonce, envelope.ciphertext, aad) == SECRET_TEXT.encode()


def test_aad_encoding_is_unambiguous():
    a = build_aad(1, "AES-256-GCM", "k1", EncryptionContext("ab", "c", 1))
    b = build_aad(1, "AES-256-GCM", "k1", EncryptionContext("a", "bc", 1))
    assert a != b


# ------------------------------------------------------------------------------------------------------ tampering


def flip(data: bytes, index: int) -> bytes:
    return data[:index] + bytes([data[index] ^ 0x01]) + data[index + 1 :]


@pytest.mark.parametrize("where", ["first", "middle", "tag"])
def test_modified_ciphertext_fails_authentication(service, where):
    envelope = encrypt(service)
    index = {"first": 0, "middle": len(envelope.ciphertext) // 2, "tag": len(envelope.ciphertext) - 1}[where]
    with pytest.raises(DecryptionError):
        service.decrypt(replace(envelope, ciphertext=flip(envelope.ciphertext, index)), CTX)


def test_modified_nonce_fails_authentication(service):
    envelope = encrypt(service)
    with pytest.raises(DecryptionError):
        service.decrypt(replace(envelope, nonce=flip(envelope.nonce, 0)), CTX)


def test_appended_or_dropped_bytes_fail(service):
    envelope = encrypt(service)
    with pytest.raises(DecryptionError):
        service.decrypt(replace(envelope, ciphertext=envelope.ciphertext + b"\x00"), CTX)
    with pytest.raises(DecryptionError):
        service.decrypt(replace(envelope, ciphertext=envelope.ciphertext[:-1]), CTX)


@pytest.mark.parametrize(
    "other",
    [
        EncryptionContext("private_note", "00000000-0000-4000-8000-000000000000", 7),  # another record id
        EncryptionContext("private_note", CTX.record_id, 8),  # another owner
        EncryptionContext("other_purpose", CTX.record_id, 7),  # another purpose
    ],
)
def test_a_ciphertext_moved_to_another_record_owner_or_purpose_does_not_decrypt(service, other):
    envelope = encrypt(service)
    with pytest.raises(DecryptionError):
        service.decrypt(envelope, other)


def test_swapping_the_key_id_in_the_metadata_fails_even_with_the_same_key_material():
    key = new_key()
    svc = EncryptionService(provider(keys={"k1": key, "k2": key}, active="k1")[0])
    envelope = encrypt(svc)
    with pytest.raises(DecryptionError):  # key id is bound into the associated data
        svc.decrypt(replace(envelope, key_id="k2"), CTX)


def test_wrong_key_fails_safely_without_returning_anything():
    sender = EncryptionService(provider(keys={"k1": new_key()})[0])
    receiver = EncryptionService(provider(keys={"k1": new_key()})[0])  # same id, different key
    with pytest.raises(DecryptionError):
        receiver.decrypt(encrypt(sender), CTX)


def test_unknown_key_id_is_reported_as_an_unavailable_key(service):
    with pytest.raises(KeyUnavailableError):
        service.decrypt(replace(encrypt(service), key_id="retired-key"), CTX)


@pytest.mark.parametrize(
    "mutation",
    [
        {"version": 2},
        {"version": 0},
        {"algorithm": "AES-128-CBC"},
        {"algorithm": "none"},
        {"nonce": b"short"},
        {"nonce": b""},
        {"ciphertext": b"\x00" * 15},
        {"ciphertext": b""},
        {"key_id": ""},
    ],
)
def test_malformed_or_downgraded_envelopes_are_rejected_before_any_decryption(service, mutation):
    with pytest.raises(MalformedEnvelopeError):
        service.decrypt(replace(encrypt(service), **mutation), CTX)


# --------------------------------------------------------------------------------------------- keys and fail-closed


def test_no_key_configured_means_nothing_is_encrypted_and_there_is_no_default():
    service = EncryptionService(EnvironmentKeyProvider("", ""))
    assert service.configured() is False
    with pytest.raises(KeyUnavailableError):
        encrypt(service)


def test_active_key_must_be_one_of_the_configured_keys():
    spec = generate_key_spec("k1", new_key())
    with pytest.raises(KeyUnavailableError):
        EnvironmentKeyProvider(spec, "missing").active_key_id()
    with pytest.raises(KeyUnavailableError):
        EnvironmentKeyProvider(spec, "").active_key_id()


@pytest.mark.parametrize(
    "spec",
    [
        "k1:not-base64!!",
        "k1:" + base64.b64encode(b"short").decode(),  # wrong length
        "k1:" + base64.b64encode(secrets.token_bytes(16)).decode(),  # AES-128 length is not accepted
        "no-separator",
        "bad id:" + base64.b64encode(secrets.token_bytes(32)).decode(),
        "k1:" + base64.b64encode(b"\x01" * 32).decode() + ",k1:" + base64.b64encode(b"\x02" * 32).decode(),  # duplicate id
    ],
)
def test_malformed_key_configuration_is_rejected(spec):
    with pytest.raises(KeyUnavailableError):
        EnvironmentKeyProvider(spec, "k1")


def test_a_failed_key_provider_fails_closed():
    service = EncryptionService(UnavailableKeyProvider())
    assert service.configured() is False and service.self_test() is False
    with pytest.raises(KeyUnavailableError):
        encrypt(service)


def test_key_rotation_new_writes_use_the_new_key_and_old_records_still_decrypt():
    old, new = new_key(), new_key()
    before = EncryptionService(provider(keys={"k1": old})[0])
    legacy = encrypt(before)
    after = EncryptionService(provider(keys={"k1": old, "k2": new}, active="k2")[0])
    assert after.decrypt(legacy, CTX).decode() == SECRET_TEXT
    assert encrypt(after).key_id == "k2"
    retired = EncryptionService(provider(keys={"k2": new}, active="k2")[0])  # k1 removed too early
    with pytest.raises(KeyUnavailableError):
        retired.decrypt(legacy, CTX)


def test_plaintext_size_is_bounded_and_non_bytes_are_rejected(service):
    with pytest.raises(EncryptionError):
        service.encrypt(b"x" * (MAX_PLAINTEXT_BYTES + 1), CTX)
    with pytest.raises(EncryptionError):
        service.encrypt("a str, not bytes", CTX)  # type: ignore[arg-type]


def test_an_encryption_failure_returns_no_envelope(monkeypatch):
    class Boom:
        def encrypt(self, *a, **k):
            raise RuntimeError(SECRET_TEXT)  # a library error that mentions the plaintext must not escape

    svc = EncryptionService(provider("k1")[0])
    monkeypatch.setattr(EncryptionService, "_aesgcm", lambda self, key_id: Boom())
    with pytest.raises(EncryptionError) as raised:
        encrypt(svc)
    assert SECRET_TEXT not in str(raised.value) and raised.value.__cause__ is None


def test_self_test_is_a_real_round_trip(service, monkeypatch):
    assert service.self_test() is True and service.configured() is True
    monkeypatch.setattr(EncryptionService, "decrypt", lambda self, envelope, context: b"not the probe")
    assert service.self_test() is False


# ------------------------------------------------------------------------------- nothing sensitive leaks anywhere


def test_errors_reprs_and_logs_never_contain_plaintext_or_key_material(caplog):
    key = new_key()
    encoded = base64.b64encode(key).decode()
    prov = EnvironmentKeyProvider(generate_key_spec("k1", key), "k1")
    svc = EncryptionService(prov)
    envelope = encrypt(svc)
    raised: list[str] = []
    with caplog.at_level(logging.DEBUG):
        for bad in (replace(envelope, ciphertext=flip(envelope.ciphertext, 0)), replace(envelope, key_id="nope"), replace(envelope, nonce=b"x")):
            with pytest.raises(Exception) as caught:
                svc.decrypt(bad, CTX)
            raised += [str(caught.value), repr(caught.value)]
    surfaces = raised + [repr(envelope), repr(prov), caplog.text]
    for surface in surfaces:
        assert SECRET_TEXT not in surface
        assert encoded not in surface and key.hex() not in surface and repr(key) not in surface
        assert envelope.nonce.hex() not in surface and repr(envelope.nonce) not in surface


def test_settings_do_not_reveal_the_configured_keys():
    spec = generate_key_spec("k1", new_key())
    settings = Settings(protected_data_keys=spec, protected_data_active_key_id="k1")
    assert spec not in repr(settings) and spec not in str(settings)
    assert spec.split(":", 1)[1] not in repr(settings.model_dump())


def test_the_repository_ships_no_key_and_no_default_key():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    assert Settings.model_fields["protected_data_keys"].default.get_secret_value() == ""
    for relative in ("backend/wealthpilot/security", "backend/wealthpilot/api/services/protected_record_service.py"):
        for path in [root / relative] if (root / relative).is_file() else (root / relative).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert not any(len(token) == 44 and token.endswith("=") for token in text.replace('"', " ").replace("'", " ").split()), path
