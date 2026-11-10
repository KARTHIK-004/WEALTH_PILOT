"""ADR-052 -- `core/sentiment_model.py`: the local inference service for a pretrained Transformer sentiment classifier, tested with FAKE backends and tiny stand-in artifacts. No weights, no
deep-learning package and no network are used; the one part not exercised is `TransformersBackend` itself (the packages are outside the approved stack). Each test breaks a valid artifact in
exactly one way and expects a FIXED reason code, never a path, a stack trace or text."""

from __future__ import annotations

import json
import logging
import math
import os

import pytest

from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.user_text_sentiment import FALLBACK_REASONS, ModelReading

PRIVATE = "PRIVATE-TEXT-LEAK-9921"


class FakeBackend:
    """Stands in for the Transformer: returns fixed logits, or raises / sleeps on demand. Records the texts it was given (so a test can check what the model was allowed to read)."""

    def __init__(self, logits=(2.0, 0.0, 0.0), *, error: Exception | None = None, delay: float = 0.0, intensity: float | None = None) -> None:
        self.logits, self.error, self.delay, self.intensity, self.seen = tuple(logits), error, delay, intensity, []

    def predict(self, text: str) -> sm.BackendOutput:
        import time

        self.seen.append(text)
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return sm.BackendOutput(self.logits, self.intensity)


def factory(backend):
    return lambda info, cfg: backend


def load(config, artifact_root, backend=None, **over):
    return sm.load_model(config(**over), backend_factory=factory(backend or FakeBackend()), root=artifact_root)


def reason(call):
    with pytest.raises(sm.ModelUnavailable) as info:
        call()
    assert info.value.reason in FALLBACK_REASONS and str(info.value) == info.value.reason          # a fixed code, nothing else
    return info.value.reason


# ------------------------------------------------------------------------------------------------ disabled and enabled


def test_a_model_that_is_switched_off_reports_disabled_and_is_never_loaded(config, artifact_root):
    status = sm.model_status(config(enabled=False), root=artifact_root)
    assert (status.enabled, status.state, status.reason, status.model_name) == (False, "disabled", None, None)
    assert reason(lambda: sm.load_model(config(enabled=False), root=artifact_root))


def test_a_valid_artifact_loads_and_reports_ready_with_its_own_metadata(config, artifact_root, make_artifact):
    make_artifact()
    status = sm.model_status(config(), backend_factory=factory(FakeBackend()), root=artifact_root)
    assert (status.state, status.reason, status.model_name, status.model_version, status.validation_status, status.calibration_status, status.intensity_available) == (
        "ready", None, "test-model", "sentiment-v1", "validated", "calibrated", False)
    assert str(artifact_root) not in repr(status)                                    # no filesystem path leaves the service


def test_inference_returns_the_documented_output_shape_with_temperature_scaled_probabilities(config, artifact_root, make_artifact):
    make_artifact(temperature=2.0)
    model = load(config, artifact_root, FakeBackend((2.0, 0.0, 0.0)))
    reading = model.interpret("I am worried about my savings")
    assert isinstance(reading, ModelReading) and reading.sentiment == "positive" and reading.model_name == "test-model" and reading.model_version == "sentiment-v1"
    expected = [math.exp(1.0), 1.0, 1.0]
    total = sum(expected)
    assert reading.class_probabilities == pytest.approx({"positive": expected[0] / total, "negative": 1 / total, "neutral": 1 / total})
    assert reading.probability == pytest.approx(expected[0] / total) and reading.calibrated is True and reading.band_cutoffs == (0.6, 0.85)
    assert sum(reading.class_probabilities.values()) == pytest.approx(1.0) and reading.abstain_below == 0.6 and reading.intensity is None


def test_the_artifacts_own_threshold_can_only_be_raised_by_configuration_never_lowered(config, artifact_root, make_artifact):
    make_artifact(min_confidence=0.6)
    assert load(config, artifact_root, min_confidence=0.9).interpret("x y z").abstain_below == 0.9
    sm.clear_cache()
    assert load(config, artifact_root, min_confidence=0.2).interpret("x y z").abstain_below == 0.6


# ------------------------------------------------------------------------------------------------ not validated, not calibrated


def test_an_unvalidated_artifact_is_refused_as_primary(config, artifact_root, make_artifact):
    make_artifact(validated=False)
    assert reason(lambda: load(config, artifact_root)) == "not_validated"
    assert sm.model_status(config(), backend_factory=factory(FakeBackend()), root=artifact_root).reason == "not_validated"


def test_a_validated_claim_without_its_evidence_is_incompatible(config, artifact_root, make_artifact):
    make_artifact(evidence=False)
    assert reason(lambda: load(config, artifact_root)) == "artifact_incompatible"


def test_a_validated_claim_without_calibration_is_incompatible(config, artifact_root, make_artifact):
    make_artifact(calibrated=False)
    assert reason(lambda: load(config, artifact_root)) == "artifact_incompatible"


def test_a_validated_claim_with_a_tiny_or_missing_test_set_is_incompatible(config, artifact_root, make_artifact):
    make_artifact(test_samples=0)
    assert reason(lambda: load(config, artifact_root)) == "artifact_incompatible"


def test_an_uncalibrated_model_never_exposes_a_calibrated_probability(config, artifact_root, make_artifact):
    directory = make_artifact(validated=False, calibrated=False)
    info = sm.verify_artifact(directory.resolve(), expected_version="sentiment-v1", expected_name="test-model", max_tokens=128)
    reading = sm.TrainedSentimentModel(info, FakeBackend((2.0, 0.0, 0.0))).interpret("x y z")
    assert reading.calibrated is False and reading.abstain_below is None and reading.band_cutoffs is None and reading.validation_status == "unvalidated"
    assert reading.probability == pytest.approx(math.exp(2) / (math.exp(2) + 2))      # the raw softmax, honestly not calibrated


# ------------------------------------------------------------------------------------------------ missing, corrupted, incompatible, outside the approved root


def test_a_missing_artifact_directory_is_artifact_missing(config, artifact_root):
    assert reason(lambda: load(config, artifact_root, path="does-not-exist")) == "artifact_missing"
    assert reason(lambda: load(config, artifact_root, path="")) == "artifact_missing"


@pytest.mark.parametrize("path", ["../outside", "..", ".", "sentiment-v1/../../outside", os.path.abspath(os.sep)])
def test_a_path_outside_the_approved_artifact_root_is_refused(config, artifact_root, make_artifact, tmp_path, path):
    make_artifact()
    (tmp_path / "outside").mkdir(exist_ok=True)
    assert reason(lambda: load(config, artifact_root, path=path)) == "path_not_allowed"


def test_a_symbolic_link_inside_the_root_is_refused(config, artifact_root, make_artifact, tmp_path):
    real = make_artifact("real")
    link = artifact_root / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not permitted for this account")
    assert reason(lambda: load(config, artifact_root, path="link")) == "path_not_allowed"


@pytest.mark.parametrize("damage", ["weights", "config", "metadata_json", "metadata_missing", "listed_file_missing"])
def test_a_corrupted_artifact_is_detected(config, artifact_root, make_artifact, damage):
    directory = make_artifact()
    if damage == "weights":
        (directory / "model.safetensors").write_bytes(b"tampered")
    elif damage == "config":
        (directory / "config.json").write_text("{}", encoding="utf-8")
    elif damage == "metadata_json":
        (directory / "model_metadata.json").write_text("{not json", encoding="utf-8")
    elif damage == "metadata_missing":
        (directory / "model_metadata.json").unlink()
    else:
        (directory / "metrics.json").unlink()
    assert reason(lambda: load(config, artifact_root)) == "artifact_corrupt"


def test_incompatible_artifacts_are_refused_with_their_own_reasons(config, artifact_root, make_artifact):
    make_artifact("tokenizer", vocab_size=1000)
    path = artifact_root / "tokenizer" / "model_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["tokenizer"]["vocab_size"] = 999                                         # the tokenizer was built for a different vocabulary than the weights
    path.write_text(json.dumps(metadata), encoding="utf-8")
    assert reason(lambda: load(config, artifact_root, path="tokenizer")) == "artifact_incompatible"
    make_artifact("short-positions", positions=100)                                   # the model cannot take max_tokens tokens
    assert reason(lambda: load(config, artifact_root, path="short-positions", max_tokens=128)) == "artifact_incompatible"
    make_artifact("labels", labels=["positive", "negative", "neutral", "mixed"])      # a head may only have the three classes
    assert reason(lambda: load(config, artifact_root, path="labels")) == "artifact_incompatible"
    make_artifact("ok")
    assert reason(lambda: load(config, artifact_root, path="ok", version="sentiment-v2")) == "version_mismatch"
    assert reason(lambda: load(config, artifact_root, path="ok", name="another-model")) == "artifact_incompatible"


def test_a_pickle_checkpoint_is_never_accepted(config, artifact_root, make_artifact):
    directory = make_artifact()
    path = directory / "model_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["files"]["pytorch_model.bin"] = metadata["files"].pop("model.safetensors")
    path.write_text(json.dumps(metadata), encoding="utf-8")
    assert reason(lambda: load(config, artifact_root)) == "artifact_incompatible"


def test_a_listed_file_that_escapes_the_directory_is_refused(config, artifact_root, make_artifact):
    directory = make_artifact()
    path = directory / "model_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["files"]["../../escape.txt"] = "0" * 64
    path.write_text(json.dumps(metadata), encoding="utf-8")
    assert reason(lambda: load(config, artifact_root)) == "path_not_allowed"


def test_the_real_backend_is_unavailable_without_the_packages_and_says_so(config, artifact_root, make_artifact, monkeypatch):
    make_artifact()
    monkeypatch.setattr(sm, "dependencies_available", lambda: False)
    assert reason(lambda: sm.load_model(config(), root=artifact_root)) == "dependencies_missing"
    assert sm.model_status(config(), root=artifact_root).dependencies_available is False


def test_the_transformers_backend_refuses_a_gpu_and_missing_packages_with_fixed_codes(tmp_path):
    assert reason(lambda: sm.TransformersBackend(tmp_path, max_tokens=64, device="cuda", labels=("positive", "negative", "neutral"), tokenizer_length=1000)) == "invalid_configuration"
    if not sm.dependencies_available():
        assert reason(lambda: sm.TransformersBackend(tmp_path, max_tokens=64, device="cpu", labels=("positive", "negative", "neutral"), tokenizer_length=1000)) == "dependencies_missing"


@pytest.mark.parametrize("over", [dict(max_tokens=None), dict(max_tokens=0), dict(device="cuda"), dict(timeout_seconds=0)])
def test_an_invalid_configuration_is_refused(config, artifact_root, make_artifact, over):
    make_artifact()
    assert reason(lambda: load(config, artifact_root, **over)) == "invalid_configuration"


# ------------------------------------------------------------------------------------------------ inference failures never carry the text


def test_a_backend_exception_becomes_a_fixed_reason_without_the_text(config, artifact_root, make_artifact, caplog):
    make_artifact()
    model = load(config, artifact_root, FakeBackend(error=RuntimeError(f"cannot read: {PRIVATE}")))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(sm.ModelUnavailable) as info:
        model.interpret(f"I worry about {PRIVATE}")
    assert info.value.reason == "inference_failed" and PRIVATE not in str(info.value) and PRIVATE not in repr(info.value) and info.value.__cause__ is None
    assert PRIVATE not in caplog.text


def test_a_backend_that_reports_its_own_fixed_reason_keeps_it(config, artifact_root, make_artifact):
    make_artifact()
    model = load(config, artifact_root, FakeBackend(error=sm.ModelUnavailable("load_failed")))
    assert reason(lambda: model.interpret("a b c")) == "load_failed"


def test_inference_that_takes_too_long_is_cut_off(config, artifact_root, make_artifact):
    make_artifact()
    model = load(config, artifact_root, FakeBackend(delay=0.6), timeout_seconds=0.05)
    assert reason(lambda: model.interpret("a b c")) == "timeout"


@pytest.mark.parametrize("logits", [(1.0, 2.0), (1.0, 2.0, 3.0, 4.0), (float("nan"), 0.0, 0.0), (float("inf"), 0.0, 0.0), (True, 0.0, 0.0), ()])
def test_a_malformed_model_output_is_invalid(config, artifact_root, make_artifact, logits):
    make_artifact()
    assert reason(lambda: load(config, artifact_root, FakeBackend(logits)).interpret("a b c")) == "invalid_output"


def test_an_out_of_range_intensity_is_invalid_and_a_valid_one_needs_a_validated_regression_head(config, artifact_root, make_artifact):
    make_artifact("no-head")
    assert load(config, artifact_root, FakeBackend(intensity=-0.5), path="no-head").interpret("a b c").intensity is None        # no validated head: intensity stays null
    sm.clear_cache()
    make_artifact("head", regression={"available": True, "validated": True, "mae": 0.2, "rmse": 0.3, "samples": 400})
    assert load(config, artifact_root, FakeBackend(intensity=-0.5), path="head").interpret("a b c").intensity == -0.5
    sm.clear_cache()
    assert reason(lambda: load(config, artifact_root, FakeBackend(intensity=1.5), path="head").interpret("a b c")) == "invalid_output"
    sm.clear_cache()
    make_artifact("unvalidated-head", regression={"available": True, "validated": False})
    assert load(config, artifact_root, FakeBackend(intensity=0.4), path="unvalidated-head").interpret("a b c").intensity is None


# ------------------------------------------------------------------------------------------------ caching


def test_a_loaded_model_is_cached_and_a_failure_is_not_retried_at_once(config, artifact_root, make_artifact):
    make_artifact()
    first = load(config, artifact_root)
    assert sm.load_model(config(), backend_factory=first and (lambda i, c: FakeBackend()), root=artifact_root) is not None
    sm.clear_cache()
    calls = []

    def counting(info, cfg):
        calls.append(1)
        return FakeBackend()

    a = sm.load_model(config(), backend_factory=counting, root=artifact_root)
    b = sm.load_model(config(), backend_factory=counting, root=artifact_root)
    assert a is b and len(calls) == 1
    sm.clear_cache()
    shared = factory(FakeBackend())
    assert reason(lambda: sm.load_model(config(path="missing"), backend_factory=shared, root=artifact_root)) == "artifact_missing"
    (artifact_root / "missing").mkdir()                                                # created right after the failure: the failure is cached for a short time
    assert reason(lambda: sm.load_model(config(path="missing"), backend_factory=shared, root=artifact_root)) == "artifact_missing"
    sm.clear_cache()
    assert reason(lambda: sm.load_model(config(path="missing"), backend_factory=shared, root=artifact_root)) == "artifact_corrupt"     # a fresh attempt sees the empty directory


def test_the_module_has_no_network_logging_or_training_code():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "backend/wealthpilot/core/sentiment_model.py").read_text(encoding="utf-8")
    imports = "\n".join(line for line in source.splitlines() if line.startswith(("import ", "from ")))
    for word in ("requests", "urllib", "socket", "httpx", "aiohttp", "logging", "openai", "google", "sqlalchemy", "wealthpilot.security", "training"):
        assert word not in imports, word
    assert ".fit(" not in source and "backward(" not in source and "Trainer" not in source              # inference only
    assert "trust_remote_code=False" in source and "local_files_only=True" in source and "use_safetensors=True" in source
