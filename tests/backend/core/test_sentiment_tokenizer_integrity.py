"""ADR-052 -- tokenizer integrity of a trained sentiment artifact. The artifact records `tokenizer.length` (the real `len(tokenizer)` it was written with); the loader compares it with the
tokenizer it loads and refuses the artifact on any difference, with the repository-standard fixed code `artifact_incompatible` (no number, path or text in the error). The recorded length is
deliberately not required to EQUAL `config.vocab_size` (a padded embedding matrix is valid), but it may not EXCEED it (D9: a longer tokenizer can emit an id with no embedding row).

These tests need no deep-learning package: the metadata checks are stdlib, and the real `TransformersBackend` class is driven through fake `torch` / `transformers` modules, so its keywords and
the order of its errors are checked everywhere. The same class against a real (locally generated, randomly initialised) model is in `tests/training/sentiment/test_transformer_standin.py`."""

from __future__ import annotations

import json
import sys
import types

import pytest

from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.user_text_sentiment import FALLBACK_REASONS

LABELS = ("positive", "negative", "neutral")


class FakeBackend:
    def predict(self, text: str) -> sm.BackendOutput:
        return sm.BackendOutput((2.0, 0.0, 0.0))


def reason(call):
    with pytest.raises(sm.ModelUnavailable) as info:
        call()
    assert info.value.reason in FALLBACK_REASONS and str(info.value) == info.value.reason          # a fixed code, nothing else
    return info.value.reason


def edit_metadata(directory, change):
    path = directory / "model_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    change(metadata)
    path.write_text(json.dumps(metadata), encoding="utf-8")


# ------------------------------------------------------------------------------------------------ the explicit comparison


def test_a_matching_tokenizer_length_is_accepted():
    sm.check_tokenizer_length(25, 25)
    sm.check_tokenizer_length(1, 1)


@pytest.mark.parametrize("expected,loaded", [(25, 5), (25, 26), (25, 24), (1, 0), (30522, 30521)])
def test_a_mismatched_tokenizer_length_is_rejected_with_a_fixed_code_and_no_number(expected, loaded):
    assert reason(lambda: sm.check_tokenizer_length(expected, loaded)) == "artifact_incompatible"
    with pytest.raises(sm.ModelUnavailable) as info:
        sm.check_tokenizer_length(expected, loaded)
    assert str(expected) not in str(info.value) and str(loaded) not in str(info.value) and info.value.__cause__ is None


@pytest.mark.parametrize("expected,loaded", [(True, 1), (25, True), (None, 25), (25, None), ("25", 25), (25, "25"), (25.0, 25), (25, 25.0)])
def test_lengths_that_are_not_integers_are_never_treated_as_equal(expected, loaded):
    assert reason(lambda: sm.check_tokenizer_length(expected, loaded)) == "artifact_incompatible"


# ------------------------------------------------------------------------------------------------ the metadata

def test_the_recorded_length_is_read_into_the_verified_artifact(artifact_root, make_artifact):
    directory = make_artifact(vocab_size=1000, tokenizer_length=1000)
    info = sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128)
    assert info.tokenizer_length == 1000


def test_a_tokenizer_shorter_than_the_embedding_matrix_is_valid(config, artifact_root, make_artifact):
    """A padded embedding matrix (config vocab_size 1008, tokenizer 1000) is how many pretrained models are built: it must not be rejected."""
    directory = make_artifact(vocab_size=1008, tokenizer_length=1000)
    info = sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128)
    assert (info.tokenizer_length, json.loads((directory / "config.json").read_text(encoding="utf-8"))["vocab_size"]) == (1000, 1008)
    assert sm.model_status(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root).state == "ready"


def test_a_tokenizer_longer_than_the_embedding_matrix_is_refused(config, artifact_root, make_artifact):
    """D9 (supersedes the seventh-brief behaviour): `len(tokenizer) > config.vocab_size` can emit an id with no embedding row, so it is refused with `artifact_incompatible`."""
    make_artifact("longer", vocab_size=1000, tokenizer_length=1001)
    assert reason(lambda: sm.verify_artifact((artifact_root / "longer").resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128)) == "artifact_incompatible"
    assert reason(lambda: sm.load_model(config(path="longer"), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"
    make_artifact("equal", vocab_size=1000, tokenizer_length=1000)                     # equality is accepted
    assert sm.verify_artifact((artifact_root / "equal").resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128).tokenizer_length == 1000


def test_a_missing_tokenizer_length_refuses_the_artifact(config, artifact_root, make_artifact):
    directory = make_artifact()
    edit_metadata(directory, lambda m: m["tokenizer"].pop("length"))
    assert reason(lambda: sm.load_model(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"


@pytest.mark.parametrize("bad", [None, "25", "", 0, -3, True, False, 25.0, 1.5, [25], {"n": 25}])
def test_a_malformed_tokenizer_length_refuses_the_artifact(config, artifact_root, make_artifact, bad):
    directory = make_artifact()
    edit_metadata(directory, lambda m: m["tokenizer"].__setitem__("length", bad))
    assert reason(lambda: sm.load_model(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"


def test_a_tokenizer_metadata_block_that_is_not_a_mapping_still_refuses(config, artifact_root, make_artifact):
    directory = make_artifact()
    edit_metadata(directory, lambda m: m.__setitem__("tokenizer", [25]))
    assert reason(lambda: sm.load_model(config(), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"


def test_the_existing_checks_are_still_enforced_alongside_the_new_one(config, artifact_root, make_artifact):
    """A valid recorded length does not excuse any other defect: vocab_size mismatch, missing safetensors entry, damaged weights."""
    make_artifact("vocab", vocab_size=1000, tokenizer_length=1000)
    edit_metadata(artifact_root / "vocab", lambda m: m["tokenizer"].__setitem__("vocab_size", 999))
    assert reason(lambda: sm.load_model(config(path="vocab"), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"
    directory = make_artifact("no-weights")
    edit_metadata(directory, lambda m: m["files"].pop("model.safetensors"))
    assert reason(lambda: sm.load_model(config(path="no-weights"), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_incompatible"
    directory = make_artifact("damaged")
    (directory / "model.safetensors").write_bytes(b"tampered")
    assert reason(lambda: sm.load_model(config(path="damaged"), backend_factory=lambda i, c: FakeBackend(), root=artifact_root)) == "artifact_corrupt"


def test_the_recorded_length_reaches_the_backend_factory(config, artifact_root, make_artifact):
    make_artifact(vocab_size=1008, tokenizer_length=1000)
    seen = []

    def factory(info, cfg):
        seen.append(info.tokenizer_length)
        return FakeBackend()

    sm.load_model(config(), backend_factory=factory, root=artifact_root)
    assert seen == [1000]


def test_the_default_backend_is_built_with_the_recorded_length(config, artifact_root, make_artifact, monkeypatch):
    directory = make_artifact(vocab_size=1008, tokenizer_length=1000)
    info = sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128)
    captured = {}
    monkeypatch.setattr(sm, "TransformersBackend", lambda *a, **k: captured.update(k) or FakeBackend())
    sm._default_backend(info, config())
    assert captured["tokenizer_length"] == 1000 and captured["device"] == "cpu" and captured["labels"] == info.labels


def test_the_evaluator_also_passes_the_recorded_length():
    """`evaluate_artifact` builds its own backend; leaving the length out would bypass the integrity check there."""
    from training.sentiment.config import REPO_ROOT

    text = (REPO_ROOT / "training" / "sentiment" / "evaluate_sentiment_model.py").read_text(encoding="utf-8")
    assert "tokenizer_length=info.tokenizer_length" in text


# ------------------------------------------------------------------------------------------------ the real backend class, driven through fake packages


class _Tokenizer:
    def __init__(self, length):
        self._length = length

    def __len__(self):
        return self._length


class _Model:
    def __init__(self, vocab_size=25, with_config=True):
        if with_config:
            self.config = types.SimpleNamespace(vocab_size=vocab_size)

    def eval(self):
        return self


def install_fake_packages(monkeypatch, *, tokenizer_length=25, tokenizer_error=None, model_error=None, no_len=False, model_vocab_size=25, model_config=True):
    calls = {"tokenizer": [], "model": []}
    transformers = types.ModuleType("transformers")

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls["tokenizer"].append((args, kwargs))
            if tokenizer_error:
                raise tokenizer_error
            return object() if no_len else _Tokenizer(tokenizer_length)

    class AutoModelForSequenceClassification:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls["model"].append((args, kwargs))
            if model_error:
                raise model_error
            return _Model(model_vocab_size, model_config)

    transformers.AutoTokenizer, transformers.AutoModelForSequenceClassification = AutoTokenizer, AutoModelForSequenceClassification
    monkeypatch.setitem(sys.modules, "torch", types.ModuleType("torch"))
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    return calls


def build(tmp_path, **over):
    return sm.TransformersBackend(tmp_path, max_tokens=64, device="cpu", labels=LABELS, **{"tokenizer_length": 25, **over})


def test_the_backend_loads_with_exactly_the_safe_keywords_and_accepts_a_matching_tokenizer(tmp_path, monkeypatch):
    calls = install_fake_packages(monkeypatch, tokenizer_length=25)
    build(tmp_path)
    assert calls["tokenizer"] == [((str(tmp_path),), {"local_files_only": True, "trust_remote_code": False})]
    assert calls["model"] == [((str(tmp_path),), {"local_files_only": True, "trust_remote_code": False, "use_safetensors": True})]


@pytest.mark.parametrize("loaded", [5, 24, 26])
def test_the_backend_rejects_a_tokenizer_of_a_different_length_as_incompatible_not_as_a_load_failure(tmp_path, monkeypatch, loaded):
    install_fake_packages(monkeypatch, tokenizer_length=loaded)
    assert reason(lambda: build(tmp_path)) == "artifact_incompatible"


def test_the_backend_accepts_a_tokenizer_shorter_than_the_embedding_matrix_because_equality_is_not_required(tmp_path, monkeypatch):
    install_fake_packages(monkeypatch, tokenizer_length=25, model_vocab_size=32)                 # a padded embedding matrix
    build(tmp_path, tokenizer_length=25)


def test_the_backend_keeps_load_failed_for_a_library_error_and_for_a_tokenizer_without_a_length(tmp_path, monkeypatch):
    install_fake_packages(monkeypatch, tokenizer_error=OSError("/private/path/tokenizer is damaged"))
    assert reason(lambda: build(tmp_path)) == "load_failed"
    install_fake_packages(monkeypatch, model_error=RuntimeError("secret detail"))
    assert reason(lambda: build(tmp_path)) == "load_failed"
    install_fake_packages(monkeypatch, no_len=True)
    assert reason(lambda: build(tmp_path)) == "load_failed"


def test_the_backend_has_no_default_for_the_length_so_the_check_cannot_be_skipped(tmp_path, monkeypatch):
    install_fake_packages(monkeypatch)
    with pytest.raises(TypeError):
        sm.TransformersBackend(tmp_path, max_tokens=64, device="cpu", labels=LABELS)


# ------------------------------------------------------------------------------------------------ D9 in the real backend class: the loaded tokenizer may not be longer than the loaded model's embedding matrix


@pytest.mark.parametrize("tokenizer,matrix", [(26, 25), (33, 32), (2, 1), (1000, 999)])
def test_the_backend_refuses_a_tokenizer_longer_than_the_embedding_matrix_even_when_it_matches_the_recorded_length(tmp_path, monkeypatch, tokenizer, matrix):
    install_fake_packages(monkeypatch, tokenizer_length=tokenizer, model_vocab_size=matrix)
    assert reason(lambda: build(tmp_path, tokenizer_length=tokenizer)) == "artifact_incompatible"            # recorded == loaded, so only the D9 check can refuse it


@pytest.mark.parametrize("tokenizer,matrix", [(25, 25), (25, 26), (25, 32), (1, 1), (1, 30522)])
def test_the_backend_accepts_equal_and_shorter(tmp_path, monkeypatch, tokenizer, matrix):
    install_fake_packages(monkeypatch, tokenizer_length=tokenizer, model_vocab_size=matrix)
    build(tmp_path, tokenizer_length=tokenizer)


@pytest.mark.parametrize("matrix", [None, "25", True, False, 0, -1, 25.0, [25]])
def test_the_backend_refuses_a_model_whose_vocabulary_size_is_missing_or_malformed(tmp_path, monkeypatch, matrix):
    install_fake_packages(monkeypatch, tokenizer_length=25, model_vocab_size=matrix)
    assert reason(lambda: build(tmp_path)) == "artifact_incompatible"


def test_the_backend_refuses_a_model_without_a_config_at_all(tmp_path, monkeypatch):
    install_fake_packages(monkeypatch, tokenizer_length=25, model_config=False)
    assert reason(lambda: build(tmp_path)) == "artifact_incompatible"


def test_the_recorded_length_check_still_comes_first_and_both_use_the_same_fixed_code(tmp_path, monkeypatch):
    install_fake_packages(monkeypatch, tokenizer_length=30, model_vocab_size=25)
    assert reason(lambda: build(tmp_path, tokenizer_length=25)) == "artifact_incompatible"                  # differs from the recorded length AND longer than the matrix
