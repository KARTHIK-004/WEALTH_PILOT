"""ADR-052 (D8, D9) -- what a trained sentiment artifact must say about where it came from, and the invariant between its tokenizer and its embedding matrix.

D8: `metadata_schema_version` 1; the exact model identifier and its immutable 40-character lowercase revision; the tokenizer's identifier and revision; the tokenizer length; the versions of
torch / transformers / tokenizers / safetensors; a manifest hash. A missing or unknown schema version, a missing or malformed field, or an artifact written before these fields existed, is
refused with the fixed code `artifact_incompatible` (a manifest hash that is well formed but wrong is `artifact_corrupt`, like any other hash mismatch).
D9: `len(tokenizer) > config.vocab_size` is refused (`artifact_incompatible`); equal and shorter (a padded embedding matrix) are accepted.

Needs no deep-learning package: the metadata is plain JSON and the backend is a fake. Every test runs under a guard that refuses sockets, records pickle calls and checks that nothing imported
`torch`, `transformers` or `huggingface_hub`. All revisions are SYNTHETIC hashes that name nothing."""

from __future__ import annotations

import hashlib
import json
import pickle
import socket
import sys

import pytest

from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.user_text_sentiment import FALLBACK_REASONS

PRIVATE = "PRIVATE-PROVENANCE-VALUE-7741"
HEAVY = {"torch", "transformers", "huggingface_hub", "tokenizers", "safetensors"}


class FakeBackend:
    def predict(self, text: str) -> sm.BackendOutput:
        return sm.BackendOutput((2.0, 0.0, 0.0))


@pytest.fixture(autouse=True)
def guard(monkeypatch):
    attempts: list = []
    pickles: list = []

    def refuse(name):
        def blocked(*a, **k):
            attempts.append(name)
            raise ConnectionError("network blocked by the test guard")
        return blocked

    for method in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, method, refuse(f"socket.{method}"))
    for function in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, function, refuse(f"socket.{function}"))
    real_load, real_loads = pickle.load, pickle.loads
    monkeypatch.setattr(pickle, "load", lambda *a, **k: (pickles.append("load"), real_load(*a, **k))[1])
    monkeypatch.setattr(pickle, "loads", lambda *a, **k: (pickles.append("loads"), real_loads(*a, **k))[1])
    before = HEAVY & set(sys.modules)
    yield attempts
    assert attempts == [] and pickles == [], (attempts, pickles)
    assert HEAVY & set(sys.modules) == before, "an artifact check imported a deep-learning or Hub package"


def reason(call):
    with pytest.raises(sm.ModelUnavailable) as info:
        call()
    assert info.value.reason in FALLBACK_REASONS and str(info.value) == info.value.reason          # a fixed code: no value, no path, no text
    assert PRIVATE not in repr(info.value) and PRIVATE not in str(info.value)
    return info.value.reason


def verify(directory):
    return sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128)


def raw_edit(directory, change):
    """Edit the metadata WITHOUT recomputing the manifest hash (for the tests that are about the manifest hash itself)."""
    path = directory / "model_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    change(metadata)
    path.write_text(json.dumps(metadata), encoding="utf-8")


REV = "0123456789abcdef0123456789abcdef01234567"
BAD_REVISIONS = ["", " ", "main", "master", "v1.0", "refs/heads/main", REV[:7], REV[:39], REV + "0", REV.upper(), "g" * 40, REV + "\n", " " + REV, REV + " ", None, 123, True, [REV], {"r": REV}, PRIVATE]


# ------------------------------------------------------------------------------------------------ D8: the schema version


def test_a_version_1_artifact_loads_and_exposes_its_provenance(config, artifact_root, make_artifact, metadata_tools):
    directory = make_artifact(vocab_size=1000, tokenizer_length=990)
    info = verify(directory)
    assert info.schema_version == 1 == sm.METADATA_SCHEMA_VERSION and sm.SUPPORTED_SCHEMA_VERSIONS == frozenset({1})
    assert (info.base_model, info.base_model_revision) == ("test/base", metadata_tools.revision)
    assert (info.tokenizer_identifier, info.tokenizer_revision, info.tokenizer_length) == ("test/base", metadata_tools.tokenizer_revision, 990)
    assert dict(info.dependency_versions) == {name: "0.0-test" for name in sm.REQUIRED_DEPENDENCIES}
    assert len(info.manifest_sha256) == 64 and info.manifest_sha256 == metadata_tools.manifest_hash(json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))["files"])
    assert sm.model_status(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root).state == "ready"


def test_a_missing_schema_version_is_refused(config, artifact_root, make_artifact):
    directory = make_artifact()
    raw_edit(directory, lambda m: m.pop("metadata_schema_version"))
    assert reason(lambda: sm.load_model(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"


@pytest.mark.parametrize("bad", [0, 2, 3, 99, -1, "1", "", 1.0, 1.5, True, False, None, [1], {"v": 1}, PRIVATE])
def test_an_unknown_or_malformed_schema_version_is_refused(artifact_root, make_artifact, metadata_tools, bad):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m.__setitem__("metadata_schema_version", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


def test_an_artifact_written_before_the_provenance_fields_existed_fails_closed(config, artifact_root, make_artifact):
    """The seventh-brief format (tokenizer length but no schema version, revisions, versions or manifest hash): refused, with no migration and no best-effort reading."""
    directory = make_artifact()

    def strip(m):
        for key in ("metadata_schema_version", "base_model_revision", "manifest_sha256"):
            m.pop(key)
        m["library_versions"] = {}
        m["tokenizer"] = {"vocab_size": m["tokenizer"]["vocab_size"], "length": m["tokenizer"]["length"], "files": []}

    raw_edit(directory, strip)
    assert reason(lambda: verify(directory)) == "artifact_incompatible"
    assert reason(lambda: sm.load_model(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"
    assert sm.model_status(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root).reason == "artifact_incompatible"


# ------------------------------------------------------------------------------------------------ D8: revisions and identifiers


@pytest.mark.parametrize("bad", BAD_REVISIONS)
def test_a_malformed_base_model_revision_is_refused(artifact_root, make_artifact, metadata_tools, bad):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m.__setitem__("base_model_revision", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("bad", BAD_REVISIONS)
def test_a_malformed_tokenizer_revision_is_refused(artifact_root, make_artifact, metadata_tools, bad):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m["tokenizer"].__setitem__("revision", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("field", ["base_model_revision", "base_model", "library_versions", "manifest_sha256"])
def test_a_missing_top_level_provenance_field_is_refused(artifact_root, make_artifact, field):
    directory = make_artifact()
    raw_edit(directory, lambda m: m.pop(field))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("field", ["identifier", "revision", "length"])
def test_a_missing_tokenizer_provenance_field_is_refused(artifact_root, make_artifact, metadata_tools, field):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m["tokenizer"].pop(field))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("bad", ["", "   ", None, 5, True, ["test/base"], {"id": "x"}])
def test_a_missing_or_malformed_model_identifier_is_refused(artifact_root, make_artifact, metadata_tools, bad):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m.__setitem__("base_model", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("bad", ["", "   ", None, 5, True, ["test/base"], {"id": "x"}])
def test_a_missing_or_malformed_tokenizer_identifier_is_refused(artifact_root, make_artifact, metadata_tools, bad):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m["tokenizer"].__setitem__("identifier", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("name", sm.REQUIRED_DEPENDENCIES)
@pytest.mark.parametrize("bad", ["__missing__", "", "   ", None, 2, True, ["2.0"]])
def test_each_required_dependency_version_must_be_a_non_empty_string(artifact_root, make_artifact, metadata_tools, name, bad):
    directory = make_artifact()

    def edit(m):
        if bad == "__missing__":
            m["library_versions"].pop(name)
        else:
            m["library_versions"][name] = bad

    metadata_tools.rewrite(directory, edit)
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("bad", [None, [], "torch=2", 5, ["torch"]])
def test_the_dependency_versions_must_be_a_mapping(artifact_root, make_artifact, metadata_tools, bad):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m.__setitem__("library_versions", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


def test_extra_dependency_entries_are_allowed_and_the_installed_libraries_are_not_compared(artifact_root, make_artifact, metadata_tools):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m["library_versions"].update({"numpy": "1.26.4", "python": "3.11.9"}))
    assert dict(verify(directory).dependency_versions) == {name: "0.0-test" for name in sm.REQUIRED_DEPENDENCIES}          # provenance only: not a gate


def test_a_malformed_value_never_appears_in_the_error(artifact_root, make_artifact, metadata_tools):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m.__setitem__("base_model_revision", PRIVATE))
    with pytest.raises(sm.ModelUnavailable) as info:
        verify(directory)
    assert str(info.value) == "artifact_incompatible" and PRIVATE not in repr(info.value) and str(directory) not in repr(info.value) and info.value.__cause__ is None


# ------------------------------------------------------------------------------------------------ D8: the manifest hash


def test_the_manifest_hash_is_the_sha256_of_the_canonical_json_of_the_file_list():
    files = {"b.json": "2" * 64, "a.json": "1" * 64}
    assert sm.manifest_sha256(files) == hashlib.sha256(('{"a.json":"' + "1" * 64 + '","b.json":"' + "2" * 64 + '"}').encode("ascii")).hexdigest()
    assert sm.manifest_sha256(files) == sm.manifest_sha256(dict(reversed(list(files.items()))))            # key order does not matter
    assert sm.manifest_sha256(files) != sm.manifest_sha256({**files, "a.json": "3" * 64})


@pytest.mark.parametrize("bad", ["", "abc", "A" * 64, "g" * 64, "0" * 63, "0" * 65, None, 5, True, ["0" * 64], PRIVATE])
def test_a_malformed_manifest_hash_is_refused_as_incompatible(artifact_root, make_artifact, bad):
    directory = make_artifact()
    raw_edit(directory, lambda m: m.__setitem__("manifest_sha256", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


def test_a_well_formed_but_wrong_manifest_hash_is_refused_as_corrupt(artifact_root, make_artifact):
    directory = make_artifact()
    raw_edit(directory, lambda m: m.__setitem__("manifest_sha256", "0" * 64))
    assert reason(lambda: verify(directory)) == "artifact_corrupt"


def test_the_manifest_hash_follows_the_file_list_not_the_other_metadata(artifact_root, make_artifact, metadata_tools):
    directory = make_artifact()
    raw_edit(directory, lambda m: m.__setitem__("training_timestamp", "2027-01-01T00:00:00+00:00"))        # not part of the file list: the hash still matches
    assert verify(directory).manifest_sha256 == json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))["manifest_sha256"]


# ------------------------------------------------------------------------------------------------ the existing checks stay enforced


def test_damaged_weights_still_fail_the_file_hash_check(artifact_root, make_artifact):
    directory = make_artifact()
    (directory / "model.safetensors").write_bytes(b"tampered")
    assert reason(lambda: verify(directory)) == "artifact_corrupt"


def test_a_missing_listed_file_still_fails(artifact_root, make_artifact):
    directory = make_artifact()
    (directory / "metrics.json").unlink()
    assert reason(lambda: verify(directory)) == "artifact_corrupt"


def test_a_listed_file_with_a_changed_hash_is_a_file_corruption_even_if_the_manifest_hash_is_recomputed(artifact_root, make_artifact, metadata_tools):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m["files"].__setitem__("config.json", "0" * 64))
    assert reason(lambda: verify(directory)) == "artifact_corrupt"


def test_the_version_and_name_checks_still_apply(artifact_root, make_artifact):
    directory = make_artifact()
    assert reason(lambda: sm.verify_artifact(directory.resolve(), expected_version="sentiment-v2", expected_name="test-model", max_tokens=128)) == "version_mismatch"
    assert reason(lambda: sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="other", max_tokens=128)) == "artifact_incompatible"


def test_the_label_map_and_calibration_checks_still_apply(artifact_root, make_artifact):
    assert reason(lambda: verify(make_artifact("labels", labels=["positive", "negative", "neutral", "mixed"]))) == "artifact_incompatible"
    directory = make_artifact("calibration")
    raw_edit(directory, lambda m: m["calibration"].__setitem__("temperature", -1.0))
    assert reason(lambda: sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128)) == "artifact_incompatible"


@pytest.mark.parametrize("name", ["pytorch_model.bin", "model.bin", "model.pt", "model.pth", "model.pt2", "pytorch_model.pt2", "model.ckpt", "model.pkl"])
def test_a_pickle_or_exported_program_in_place_of_safetensors_is_refused(artifact_root, make_artifact, metadata_tools, name):
    directory = make_artifact()
    (directory / name).write_bytes(b"NOT-A-CHECKPOINT-PLACEHOLDER (not a serialized pickle)")

    def swap(m):
        m["files"][name] = m["files"].pop("model.safetensors")

    metadata_tools.rewrite(directory, swap)
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


def test_a_pickle_named_file_listed_beside_safetensors_must_still_match_its_hash(artifact_root, make_artifact, metadata_tools):
    directory = make_artifact()
    (directory / "pytorch_model.bin").write_bytes(b"NOT-A-CHECKPOINT-PLACEHOLDER (not a serialized pickle)")
    metadata_tools.rewrite(directory, lambda m: m["files"].__setitem__("pytorch_model.bin", "0" * 64))
    assert reason(lambda: verify(directory)) == "artifact_corrupt"                    # never read as a checkpoint: it is only a hashed file


# ------------------------------------------------------------------------------------------------ D9: the tokenizer may not be longer than the embedding matrix


@pytest.mark.parametrize("vocab,length", [(1000, 1000), (1000, 999), (1000, 500), (1000, 1), (1008, 1000), (32, 25), (1, 1)])
def test_a_tokenizer_equal_to_or_shorter_than_the_embedding_matrix_is_accepted(artifact_root, make_artifact, vocab, length):
    directory = make_artifact(vocab_size=vocab, tokenizer_length=length)
    info = verify(directory)
    assert (info.tokenizer_length, json.loads((directory / "config.json").read_text(encoding="utf-8"))["vocab_size"]) == (length, vocab)


@pytest.mark.parametrize("vocab,length", [(1000, 1001), (1000, 1200), (1000, 100000), (32, 33), (1, 2)])
def test_a_tokenizer_longer_than_the_embedding_matrix_is_refused_before_any_backend_is_built(config, artifact_root, make_artifact, vocab, length):
    make_artifact(vocab_size=vocab, tokenizer_length=length)
    built: list = []
    assert reason(lambda: sm.load_model(config(), backend_factory=lambda i, c: built.append(1) or FakeBackend(), root=artifact_root)) == "artifact_incompatible"
    assert built == []                                                                                       # refused at the artifact check, before a model could be loaded or used
    status = sm.model_status(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)
    assert (status.state, status.reason) == ("unavailable", "artifact_incompatible")


@pytest.mark.parametrize("bad", [None, "1000", "", 0, -5, True, False, 100.5, [1000], {"n": 1}])
def test_a_missing_or_malformed_tokenizer_length_is_refused(artifact_root, make_artifact, metadata_tools, bad):
    directory = make_artifact()
    metadata_tools.rewrite(directory, lambda m: m["tokenizer"].__setitem__("length", bad))
    assert reason(lambda: verify(directory)) == "artifact_incompatible"


@pytest.mark.parametrize("length,vocab", [(1, 1), (25, 25), (25, 32), (1, 100)])
def test_the_embedding_check_function_accepts_equal_and_shorter(length, vocab):
    sm.check_tokenizer_fits_embeddings(length, vocab)


@pytest.mark.parametrize("length,vocab", [(26, 25), (2, 1), (101, 100), (0, 25), (-1, 25), (25, 0), (25, -1), (True, 25), (25, True), (None, 25), (25, None), ("25", 25), (25, "25"), (25.0, 25), (25, 25.0)])
def test_the_embedding_check_function_refuses_a_longer_a_missing_or_a_malformed_value(length, vocab):
    assert reason(lambda: sm.check_tokenizer_fits_embeddings(length, vocab)) == "artifact_incompatible"


def test_the_guard_itself_refuses_and_records_a_socket_attempt(guard):
    with pytest.raises(ConnectionError):
        socket.create_connection(("synthetic-host.invalid", 80))
    assert guard == ["socket.create_connection"]
    guard.clear()                                                                                            # the control is done: the autouse check now expects silence
