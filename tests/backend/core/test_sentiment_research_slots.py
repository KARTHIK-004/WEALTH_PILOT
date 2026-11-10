"""The research-only comparison of pretrained classifiers over ROLE SLOTS (ADR-053, role slots and lifecycle hardening from ADR-055).

EVERY model result in this file comes from a STAND-IN backend that returns fixed logits (TESTED_WITH_MOCKS). No real weight file is used, so nothing here is evidence that any real model works, is
accurate or is calibrated. The artifacts built under `tmp_path` are a few bytes of placeholder text with correct checksums: they exercise the verification policy only. Horizon is NOT registered
in the code (registration is a separate owner decision), so the tests that need a "registered" candidate use a test-only copy with `registration=registered`.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import threading
import time
from pathlib import Path

import pytest

from wealthpilot.api.services import personalized_insight_service as service
from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.sentiment import adapter, comparison, inference_service, normalization, registry
from wealthpilot.core.sentiment.registry import FINBERT, HORIZON, ROBERTA
from wealthpilot.core.user_text_sentiment import analyse_user_text

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "backend" / "wealthpilot" / "core" / "sentiment"
TEXT = "I am worried because my monthly loan EMI keeps increasing and I cannot save"
HZ_ORDER = {"0": "negative", "1": "neutral", "2": "positive"}               # Horizon's documented order
FIN_ORDER = {"0": "Bearish", "1": "Bullish", "2": "Neutral"}                # a financial-tweet vocabulary, to exercise the mapping across roles


def registered(candidate):
    """A TEST-ONLY copy that satisfies every gate (the real constants never do)."""
    return dataclasses.replace(candidate, licence_status=registry.LICENCE_VERIFIED, format_status=registry.FORMAT_SAFETENSORS, registration=registry.REGISTERED)


HZ = registered(HORIZON)
FIN = dataclasses.replace(registered(FINBERT), key="fintest", role="financial")


def slots(general=HZ, financial=None):
    return {"financial": (financial, None if financial else "no_candidate_approved"), "general": (general, None if general else "registration_pending")}


def build_artifact(root: Path, candidate, id2label=None, **manifest_over) -> Path:
    directory = root / candidate.key
    directory.mkdir(parents=True)
    labels = id2label or (FIN_ORDER if candidate.role == "financial" else HZ_ORDER)
    files = {sm.WEIGHTS_FILE: b"placeholder-weights", sm.CONFIG_FILE: json.dumps({"id2label": labels, "vocab_size": 100, "max_position_embeddings": 514}).encode(), sm.TOKENIZER_CONFIG_FILE: b"{}"}
    for name, data in files.items():
        (directory / name).write_bytes(data)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    manifest = {"manifest_schema_version": 1, "repository": candidate.repository, "revision": candidate.revision, "weight_licence": candidate.weight_licence,
                "tokenizer_length": 90, "files": hashes, "manifest_sha256": sm.manifest_sha256(hashes)}
    manifest.update(manifest_over)
    (directory / adapter.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    return directory


class Stand:
    """A stand-in backend: fixed logits in the model's own index order, or a chosen failure."""

    def __init__(self, logits=None, delay=0.0, error=None):
        self.logits, self.delay, self.error, self.calls = logits, delay, error, 0

    def predict(self, text):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error(text)                       # an exception that CARRIES the text, to prove it never leaves
        return sm.BackendOutput(tuple(self.logits))


CFG = adapter.ResearchConfig(enabled=True, max_tokens=128, timeout_seconds=2.0, device="cpu")


@pytest.fixture(autouse=True)
def _clean():
    adapter.clear_cache()
    yield
    adapter.clear_cache()


def factory(stand):
    return lambda info, config: stand


def by_role(stands):
    """A factory that gives each candidate its own stand-in (looked up by the directory name)."""
    return lambda info, config: stands[info.directory.name]


# ------------------------------------------------------------------------------------------------------------------------ the recorded registry
def test_the_registry_records_horizon_as_the_one_registered_general_research_candidate_and_nothing_else():
    assert (HORIZON.repository, HORIZON.revision, HORIZON.weight_licence, HORIZON.role) == ("Horizon-Labs/multilingual-sentiment-small", "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac", "apache-2.0", "general")
    assert HORIZON.licence_status == registry.LICENCE_VERIFIED and HORIZON.format_status == registry.FORMAT_SAFETENSORS and HORIZON.registration == registry.REGISTERED     # R1, ADR-056
    assert FINBERT.registration == ROBERTA.registration == registry.HISTORICAL
    assert all(re.fullmatch(r"[0-9a-f]{40}", c.revision) for c in registry.CANDIDATES)
    assert [c.key for c in registry.CANDIDATES if c.registered] == ["horizon"] and [c.key for c in registry.CANDIDATES if c.runnable_in_principle] == ["horizon"]
    assert registry.registered_candidate("general") is HORIZON and registry.registered_candidate("financial") is None
    assert registry.slot_state("general") == (HORIZON, None) and registry.slot_state("financial") == (None, "no_candidate_approved")          # the financial slot stays empty
    assert HORIZON.blocker is None and "research" in HORIZON.registration_note.lower() and "not production" in HORIZON.registration_note.lower()


def test_registering_is_one_reviewed_constant_and_two_registered_candidates_for_one_role_are_refused(monkeypatch):
    monkeypatch.setattr(registry, "CANDIDATES", (HZ, dataclasses.replace(HZ, key="other")))
    with pytest.raises(ValueError):
        registry.registered_candidate("general")
    monkeypatch.setattr(registry, "CANDIDATES", (HZ, FIN, ROBERTA))
    assert registry.slot_state("general") == (HZ, None) and registry.slot_state("financial") == (FIN, None)
    assert HZ.runnable_in_principle and registered(HORIZON).blocker is None


@pytest.mark.parametrize("candidate,reason", [(HORIZON, "weights_missing"), (FINBERT, "licence_not_verified"), (ROBERTA, "licence_not_verified")])
def test_no_real_constant_can_load_without_its_verified_files_and_the_blocked_ones_never_can(tmp_path, candidate, reason):
    result = adapter.classify_with(candidate, CFG, TEXT, role=candidate.role, root=tmp_path / "does-not-exist", backend_factory=factory(Stand([0, 0, 1])))
    assert (result.available, result.unavailable_reason, result.role) == (False, reason, candidate.role)


def test_a_candidate_that_passes_licence_but_not_format_or_registration_is_refused_in_that_order(tmp_path):
    no_format = dataclasses.replace(HZ, format_status=registry.FORMAT_NOT_ALLOWED)
    assert adapter.classify_with(no_format, CFG, TEXT, root=tmp_path).unavailable_reason == "format_not_allowed"
    no_registration = dataclasses.replace(HZ, registration=registry.HISTORICAL)
    assert adapter.classify_with(no_registration, CFG, TEXT, root=tmp_path).unavailable_reason == "no_candidate_approved"


# ------------------------------------------------------------------------------------------------------------------------ label normalization
def test_native_labels_map_by_name_including_the_financial_vocabulary_and_anything_else_is_unsupported():
    assert [normalization.normalise_native_label(v) for v in ("positive", "Negative", " NEUTRAL ", "Bullish", "BEARISH")] == ["positive", "negative", "neutral", "positive", "negative"]
    for bad in ("LABEL_0", "mixed", "uncertain", "", None, 1, "pos", "sideways"):
        assert normalization.normalise_native_label(bad) is None
    assert normalization.label_order_from_id2label(HZ_ORDER) == ("negative", "neutral", "positive")
    assert normalization.label_order_from_id2label(FIN_ORDER) == ("Bearish", "Bullish", "Neutral")                  # the model's own spelling is kept
    for bad in ({}, None, {"0": "LABEL_0", "1": "LABEL_1", "2": "LABEL_2"}, {"0": "positive", "1": "positive", "2": "neutral"}, {"0": "bullish", "1": "positive", "2": "neutral"}, {"0": "positive", "2": "neutral"}, ["x"]):
        assert normalization.label_order_from_id2label(bad) is None


def test_the_same_logits_give_different_labels_under_different_documented_orders_and_carry_their_role():
    logits = [0.2, 3.0, 0.1]
    a = normalization.result_from_logits("k", "r", "v", ("negative", "neutral", "positive"), logits, 1.0, role="general")
    b = normalization.result_from_logits("k", "r", "v", ("Bearish", "Bullish", "Neutral"), logits, 1.0, role="financial")
    assert (a.native_label, a.normalized_label, a.role) == ("neutral", "neutral", "general") and (b.native_label, b.normalized_label, b.role) == ("Bullish", "positive", "financial")
    assert abs(sum(p for _, p in a.probabilities) - 1.0) < 1e-9 and dict(a.raw_scores)["neutral"] == 3.0


def test_invalid_model_output_is_unavailable_never_a_neutral_guess():
    for bad in ([1.0, 2.0], [float("nan"), 0.0, 1.0], [float("inf"), 0.0, 1.0], [True, 0.0, 1.0], ["a", "b", "c"], None, 5):
        result = normalization.result_from_logits("k", "r", "v", ("negative", "neutral", "positive"), bad, 1.0, role="general")
        assert (result.available, result.unavailable_reason, result.normalized_label, result.native_label, result.role) == (False, "invalid_output", None, None, "general")


def test_the_reason_codes_in_the_schema_are_exactly_the_ones_the_code_can_produce():
    from typing import get_args

    from wealthpilot.api.schemas import ResearchReason
    assert set(get_args(ResearchReason)) == set(normalization.UNAVAILABLE_REASONS)


# ------------------------------------------------------------------------------------------------------------------------ comparison over slots
def res(label, role="general"):
    if label is None:
        return normalization.unavailable("k", "r", "v", "load_failed", role=role)
    labels = ("positive", "negative", "neutral")
    return normalization.result_from_logits("k", "r", "v", labels, [5.0 if l == label else 0.0 for l in labels], 1.0, role=role)


def empty(role, reason="no_candidate_approved"):
    return normalization.unavailable("", "", "", reason, role=role)


def test_zero_configured_slots_is_no_model_configured_and_not_a_failure():
    c = comparison.compare_slots([empty("financial"), empty("general", "registration_pending")])
    assert c.status == "no_model_configured" and c.shared_label is None
    o = comparison.decide_overall(c, "negative", "valid")
    assert (o.sentiment, o.source, o.uncertainty_reason, o.rules_relation) == ("negative", "rules_baseline_fallback", "no_model_registered", "not_compared")


def test_one_configured_slot_is_that_model_against_the_rules_reading():
    answered = comparison.compare_slots([empty("financial"), res("negative", "general")])
    assert (answered.status, answered.shared_label) == ("single_model", "negative") and "not a human-validated finding" in answered.explanation
    agree = comparison.decide_overall(answered, "negative", "valid")
    assert (agree.sentiment, agree.source, agree.rules_relation, agree.uncertainty_reason) == ("negative", "transformer_comparison", "agrees", None)
    differ = comparison.decide_overall(answered, "positive", "valid")
    assert (differ.sentiment, differ.rules_relation, differ.uncertainty_reason) == ("uncertain", "disagrees", "rules_disagree")
    assert comparison.decide_overall(answered, "mixed", "valid").uncertainty_reason == "rules_disagree"                       # the model cannot say "mixed": the difference is disclosed
    for rules in (None, "uncertain", "insufficient_evidence"):
        o = comparison.decide_overall(answered, rules, "valid")
        assert (o.sentiment, o.rules_relation) == ("negative", "rules_abstained")
    weak = comparison.decide_overall(answered, "negative", "weak")
    assert (weak.sentiment, weak.uncertainty_reason) == ("uncertain", "context_safeguard")
    down = comparison.compare_slots([empty("financial"), res(None, "general")])
    assert down.status == "model_unavailable"
    fall = comparison.decide_overall(down, "positive", "valid")
    assert (fall.sentiment, fall.source, fall.uncertainty_reason) == ("positive", "rules_baseline_fallback", "transformers_unavailable")


def test_two_configured_slots_agree_disagree_or_one_fails_and_nothing_is_forced():
    a, b = res("negative", "financial"), res("negative", "general")
    assert comparison.compare_slots([a, b]).status == "agreement"
    split = comparison.compare_slots([a, res("positive", "general")])
    assert (split.status, split.shared_label) == ("disagreement", None)
    o = comparison.decide_overall(split, "negative", "valid")
    assert (o.sentiment, o.uncertainty_reason) == ("uncertain", "models_disagree")                          # never silently picks the financial or the general model
    assert comparison.compare_slots([a, res(None, "general")]).status == "one_model_unavailable"
    assert comparison.compare_slots([res(None, "financial"), res(None, "general")]).status == "both_models_unavailable"
    odd = dataclasses.replace(a, normalized_label="uncertain")
    assert comparison.compare_slots([odd, b]).status == "uncertain"


def test_model_vs_rules_reports_each_answering_model_separately():
    m = comparison.model_vs_rules(res("negative", "general"), "negative")
    assert (m.role, m.relation, m.model_label, m.rules_label) == ("general", "agrees", "negative", "negative")
    assert comparison.model_vs_rules(res("negative"), "positive").relation == "disagrees"
    assert comparison.model_vs_rules(res("negative"), None).relation == "rules_abstained"
    assert comparison.model_vs_rules(res(None), "positive").relation == "not_compared"


def test_not_eligible_text_falls_back_to_the_rules_reading():
    c = comparison.compare_slots([empty("financial"), res("negative")])
    o = comparison.decide_overall(c, "neutral", "abstained", eligible=False)
    assert (o.sentiment, o.source, o.uncertainty_reason) == ("neutral", "rules_baseline_fallback", "input_not_eligible")


# ------------------------------------------------------------------------------------------------------------------------ artifact verification
def test_a_valid_artifact_classifies_with_mocked_logits_under_each_roles_own_vocabulary(tmp_path):
    build_artifact(tmp_path, HZ)
    build_artifact(tmp_path, FIN)
    general = adapter.classify_with(HZ, CFG, TEXT, role="general", root=tmp_path, backend_factory=factory(Stand([4.0, 0.1, 0.2])))        # Horizon order: index 0 = negative
    financial = adapter.classify_with(FIN, CFG, TEXT, role="financial", root=tmp_path, backend_factory=factory(Stand([0.1, 4.0, 0.2])))  # Bearish, Bullish, Neutral: index 1 = Bullish
    assert (general.available, general.native_label, general.normalized_label, general.revision, general.role) == (True, "negative", "negative", HORIZON.revision, "general")
    assert (financial.native_label, financial.normalized_label, financial.role) == ("Bullish", "positive", "financial")
    assert general.processing_ms is not None and general.processing_ms >= 0


@pytest.mark.parametrize("case", ["missing", "wrong_revision", "floating_revision", "wrong_repository", "wrong_licence", "pickle_listed", "bad_checksum", "bad_manifest_hash",
                                  "unsupported_label", "no_manifest", "bad_tokenizer_length", "tokenizer_longer_than_embeddings"])
def test_every_artifact_defect_makes_the_model_unavailable_with_a_fixed_reason(tmp_path, case):
    expected = {"missing": "weights_missing", "wrong_revision": "revision_mismatch", "floating_revision": "revision_mismatch", "wrong_repository": "manifest_invalid", "wrong_licence": "manifest_invalid",
                "pickle_listed": "format_not_allowed", "bad_checksum": "artifact_corrupt", "bad_manifest_hash": "artifact_corrupt", "unsupported_label": "label_unsupported",
                "no_manifest": "manifest_invalid", "bad_tokenizer_length": "manifest_invalid", "tokenizer_longer_than_embeddings": "manifest_invalid"}[case]
    if case != "missing":
        over = {"wrong_revision": {"revision": "a" * 40}, "floating_revision": {"revision": "main"}, "wrong_repository": {"repository": "someone/else"}, "wrong_licence": {"weight_licence": "mit"},
                "bad_tokenizer_length": {"tokenizer_length": 0}, "tokenizer_longer_than_embeddings": {"tokenizer_length": 101}}.get(case, {})
        directory = build_artifact(tmp_path, HZ, id2label={"0": "LABEL_0", "1": "LABEL_1", "2": "LABEL_2"} if case == "unsupported_label" else None, **over)
        manifest = json.loads((directory / adapter.MANIFEST_FILE).read_text())
        if case == "pickle_listed":
            manifest["files"]["pytorch_model.bin"] = "0" * 64
            (directory / "pytorch_model.bin").write_bytes(b"x")
            manifest["manifest_sha256"] = sm.manifest_sha256(manifest["files"])
        if case == "bad_checksum":
            (directory / sm.WEIGHTS_FILE).write_bytes(b"tampered")
        if case == "bad_manifest_hash":
            manifest["manifest_sha256"] = "0" * 64
        if case == "no_manifest":
            (directory / adapter.MANIFEST_FILE).unlink()
        elif case in ("pickle_listed", "bad_manifest_hash"):
            (directory / adapter.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    result = adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=factory(Stand([1, 0, 0])))
    assert (result.available, result.unavailable_reason, result.normalized_label) == (False, expected, None)


def test_a_symlinked_artifact_directory_is_refused(tmp_path):
    real = tmp_path / "elsewhere"
    build_artifact(real, HZ)
    link_root = tmp_path / "root"
    link_root.mkdir()
    try:
        (link_root / HZ.key).symlink_to(real / HZ.key, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available here")
    assert adapter.classify_with(HZ, CFG, TEXT, root=link_root, backend_factory=factory(Stand([1, 0, 0]))).unavailable_reason == "manifest_invalid"


# ------------------------------------------------------------------------------------------------------------------------ runtime policy
def test_timeout_backend_error_and_bad_output_are_fixed_codes_and_never_carry_the_text(tmp_path):
    build_artifact(tmp_path, HZ)
    slow = adapter.classify_with(HZ, dataclasses.replace(CFG, timeout_seconds=0.05), TEXT, root=tmp_path, backend_factory=factory(Stand([1, 0, 0], delay=0.5)))
    assert slow.unavailable_reason == "timeout"
    adapter.clear_cache()
    boom = adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=factory(Stand(error=lambda t: RuntimeError(f"failed on: {t}"))))
    assert boom.unavailable_reason == "inference_failed" and TEXT not in repr(boom)
    adapter.clear_cache()
    assert adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=factory(Stand([float("nan"), 0, 0]))).unavailable_reason == "invalid_output"


def test_after_a_timeout_the_next_call_fails_fast_instead_of_queueing_behind_the_running_call(tmp_path):
    build_artifact(tmp_path, HZ)
    cfg = dataclasses.replace(CFG, timeout_seconds=0.3)
    stand = Stand([1, 0, 0], delay=1.2)
    first = adapter.classify_with(HZ, cfg, TEXT, root=tmp_path, backend_factory=factory(stand))
    start = time.perf_counter()
    second = adapter.classify_with(HZ, cfg, TEXT, root=tmp_path, backend_factory=factory(stand))
    waited = time.perf_counter() - start
    assert (first.unavailable_reason, second.unavailable_reason) == ("timeout", "timeout") and waited < 0.1            # measured 0.31 s before the circuit breaker (ADR-055)
    time.sleep(1.0)                                                                                                    # let the abandoned call finish before the next test


def test_a_failed_load_is_not_retried_for_the_backoff_window(tmp_path):
    build_artifact(tmp_path, HZ)
    calls = {"n": 0}

    def failing(info, config):
        calls["n"] += 1
        raise adapter.ResearchUnavailable("load_failed")

    for _ in range(3):
        assert adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=failing).unavailable_reason == "load_failed"
    assert calls["n"] == 1 and adapter.FAILURE_TTL_SECONDS > 0


def test_a_good_model_is_loaded_once_and_cached(tmp_path):
    build_artifact(tmp_path, HZ)
    stand, loads = Stand([1, 0, 0]), {"n": 0}

    def once(info, config):
        loads["n"] += 1
        return stand

    for _ in range(3):
        assert adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=once).available
    assert loads["n"] == 1 and stand.calls == 3


def test_disabled_and_invalid_configuration_never_load_anything_including_a_bad_thread_cap(tmp_path):
    build_artifact(tmp_path, HZ)
    bad = Stand([1, 0, 0])
    assert adapter.classify_with(HZ, dataclasses.replace(CFG, enabled=False), TEXT, root=tmp_path, backend_factory=factory(bad)).unavailable_reason == "disabled"
    for config in (dataclasses.replace(CFG, max_tokens=None), dataclasses.replace(CFG, max_tokens=0), dataclasses.replace(CFG, timeout_seconds=0.0), dataclasses.replace(CFG, device="cuda"),
                   dataclasses.replace(CFG, threads=0), dataclasses.replace(CFG, threads=adapter.MAX_THREADS + 1), dataclasses.replace(CFG, threads=True)):
        adapter.clear_cache()
        assert adapter.classify_with(HZ, config, TEXT, root=tmp_path, backend_factory=factory(bad)).unavailable_reason == "invalid_configuration", config
    assert bad.calls == 0
    adapter.clear_cache()
    assert adapter.classify_with(HZ, dataclasses.replace(CFG, threads=2), TEXT, root=tmp_path, backend_factory=factory(Stand([1, 0, 0]))).available     # a valid cap is accepted


def test_without_the_packages_the_real_backend_is_dependencies_missing_not_a_crash(tmp_path):
    build_artifact(tmp_path, HZ)
    if sm.dependencies_available():
        pytest.skip("the packages are installed here")
    assert adapter.classify_with(HZ, CFG, TEXT, root=tmp_path).unavailable_reason == "dependencies_missing"


# ------------------------------------------------------------------------------------------------------------------------ lifecycle (ADR-055)
@pytest.mark.parametrize("fault,reason", [(OSError("[WinError 126] DLL load failed"), "load_failed"), (MemoryError(), "load_failed"), (PermissionError("denied"), "load_failed"), (RuntimeError("x"), "internal_error")])
def test_an_unexpected_exception_while_building_the_model_is_a_fixed_reason_and_never_escapes(tmp_path, fault, reason):
    build_artifact(tmp_path, HZ)

    def exploding(info, config):
        raise fault

    result = adapter.classify_with(HZ, CFG, TEXT, role="general", root=tmp_path, backend_factory=exploding)
    assert (result.available, result.unavailable_reason) == (False, reason) and TEXT not in repr(result)


def test_an_unexpected_exception_while_hashing_a_file_is_a_fixed_reason_and_never_escapes(tmp_path, monkeypatch):
    build_artifact(tmp_path, HZ)
    monkeypatch.setattr(adapter, "_sha256", lambda p: (_ for _ in ()).throw(PermissionError("denied")))
    assert adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=factory(Stand([1, 0, 0]))).unavailable_reason == "load_failed"


def test_a_status_read_never_loads_hashes_or_verifies_anything(tmp_path, monkeypatch):
    build_artifact(tmp_path, HZ)
    monkeypatch.setattr(adapter, "verify_pretrained", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a status read verified (hashed) the model")))
    monkeypatch.setattr(adapter, "_default_backend", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a status read built the model")))
    monkeypatch.setattr(adapter, "_sha256", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a status read hashed a file")))
    status = adapter.candidate_status(HZ, CFG, root=tmp_path)
    assert (status.availability, status.loaded, status.weights_present, status.reason) == ("not_loaded", False, True, None)
    assert adapter.candidate_status(HZ, dataclasses.replace(CFG, enabled=False), root=tmp_path).availability == "disabled"
    assert adapter.candidate_status(dataclasses.replace(HORIZON, registration=registry.PENDING), CFG, root=tmp_path).reason == "registration_pending"
    assert adapter.candidate_status(HZ, CFG, root=tmp_path / "nowhere").availability == "weights_missing"
    assert adapter.candidate_status(HZ, dataclasses.replace(CFG, threads=0), root=tmp_path).reason == "invalid_configuration"


def test_the_status_reports_loaded_failed_and_loading_from_the_memory_of_earlier_attempts(tmp_path):
    build_artifact(tmp_path, HZ)
    assert adapter.warm(HZ, CFG, root=tmp_path, backend_factory=factory(Stand([1, 0, 0]))) is None
    assert (adapter.candidate_status(HZ, CFG, root=tmp_path).availability, adapter.candidate_status(HZ, CFG, root=tmp_path).loaded) == ("ready", True)
    adapter.clear_cache()
    assert adapter.warm(HZ, CFG, root=tmp_path, backend_factory=lambda i, c: (_ for _ in ()).throw(adapter.ResearchUnavailable("load_failed"))) == "load_failed"
    assert adapter.candidate_status(HZ, CFG, root=tmp_path).availability == "unavailable"


def test_while_one_request_builds_the_model_a_concurrent_request_and_a_status_read_do_not_wait(tmp_path):
    build_artifact(tmp_path, HZ)
    other = dataclasses.replace(HZ, key="other")
    build_artifact(tmp_path, other)
    release, started = threading.Event(), threading.Event()

    def slow(info, config):
        started.set()
        release.wait(5)
        return Stand([1, 0, 0])

    worker = threading.Thread(target=lambda: adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=slow))
    worker.start()
    assert started.wait(5)
    t0 = time.perf_counter()
    second = adapter.classify_with(HZ, CFG, TEXT, root=tmp_path, backend_factory=slow)                                     # same model, being built
    status = adapter.candidate_status(HZ, CFG, root=tmp_path)
    other_status = adapter.candidate_status(other, CFG, root=tmp_path)                                                      # another candidate: the module lock is not held
    quick = time.perf_counter() - t0
    release.set()
    worker.join(5)
    assert second.unavailable_reason == "loading" and status.availability == "loading" and other_status.availability == "not_loaded"
    assert quick < 0.5                                                                                                      # measured 1.31 s behind the old global lock
    assert adapter.candidate_status(HZ, CFG, root=tmp_path).availability == "ready"


# ------------------------------------------------------------------------------------------------------------------------ inference service and the panel
def panel(text=TEXT, config=CFG, root=None, factory_=None, the_slots=None):
    return service.build_transformer_research(text, analyse_user_text(text), config=config, root=root, backend_factory=factory_, slots=the_slots)


def test_off_by_default_horizon_is_registered_but_disabled_the_financial_slot_is_empty_and_the_panel_falls_back_to_the_rules_reading():
    out = service.build_transformer_research(TEXT, analyse_user_text(TEXT))
    assert out.enabled is False and out.mode == "research_experimental" and out.validation_status == "not_human_validated" and out.production_effect == "none"
    assert [(m.slot, m.availability, m.unavailable_reason, m.model_id) for m in out.models] == [("financial", "unavailable", "no_candidate_approved", None), ("general", "unavailable", "disabled", HORIZON.repository)]
    assert out.comparison.status == "model_unavailable" and out.overall_source == "rules_baseline_fallback" and out.uncertainty_reason == "transformers_unavailable"
    assert out.overall_sentiment == out.rules_baseline.label and out.model_versions == {"general": HORIZON.revision} and out.processing_metadata["total_ms"] is None      # nothing ran
    assert len(out.notices) == 3 and "not human validated" in out.notices[0] and "not financial advice" in out.notices[1] and "risk profile" in out.notices[2]


def test_switched_on_with_no_verified_files_the_registered_horizon_reports_weights_missing_and_the_rules_reading_answers(tmp_path):
    out = panel(config=CFG, root=tmp_path)
    assert [m.unavailable_reason for m in out.models] == ["no_candidate_approved", "weights_missing"] and out.comparison.status == "model_unavailable"
    assert out.overall_source == "rules_baseline_fallback" and out.overall_sentiment == out.rules_baseline.label


def test_with_horizon_registered_in_a_test_only_slot_the_single_model_flows_through_the_panel(tmp_path):
    build_artifact(tmp_path, HZ)
    out = panel(root=tmp_path, factory_=factory(Stand([4.0, 0.1, 0.2])), the_slots=slots())                                       # negative under Horizon's order
    general = next(m for m in out.models if m.slot == "general")
    assert (general.availability, general.native_label, general.normalized_label, general.model_id, general.revision) == ("available", "negative", "negative", HORIZON.repository, HORIZON.revision)
    assert general.probability_kind == "raw_softmax_uncalibrated" and general.raw_scores["negative"] == 4.0 and "confidence" not in general.model_dump()
    assert next(m for m in out.models if m.slot == "financial").unavailable_reason == "no_candidate_approved"                   # the empty financial slot is not a failure
    assert out.comparison.status == "single_model" and out.comparison.shared_label == "negative"
    assert [(v.slot, v.relation) for v in out.comparison.model_vs_rules] == [("general", out.rules_relation)]
    assert out.model_versions == {"general": HORIZON.revision} and out.processing_metadata["total_ms"] is not None and out.processing_metadata["input_eligible"] is True


def test_single_model_disagreeing_with_the_rules_reading_is_uncertain_and_both_readings_are_kept(tmp_path):
    build_artifact(tmp_path, HZ)
    out = panel(root=tmp_path, factory_=factory(Stand([0.0, 0.1, 6.0])), the_slots=slots())                                     # positive; the rules read this text as negative
    assert out.rules_baseline.label == "negative" and out.comparison.model_vs_rules[0].model_label == "positive"
    assert (out.overall_sentiment, out.uncertainty_reason, out.rules_relation) == ("uncertain", "rules_disagree", "disagrees")


def test_two_registered_slots_in_a_test_only_setup_agree_and_disagree_across_vocabularies(tmp_path):
    build_artifact(tmp_path, HZ)
    build_artifact(tmp_path, FIN)
    agree = panel(root=tmp_path, factory_=by_role({HZ.key: Stand([4.0, 0.1, 0.2]), FIN.key: Stand([4.0, 0.1, 0.2])}), the_slots=slots(financial=FIN))        # Horizon: negative; FIN: Bearish = negative
    assert agree.comparison.status == "agreement" and agree.comparison.shared_label == "negative" and agree.overall_source == "transformer_comparison"
    assert {m.slot: m.native_label for m in agree.models} == {"financial": "Bearish", "general": "negative"}
    adapter.clear_cache()
    split = panel(root=tmp_path, factory_=by_role({HZ.key: Stand([4.0, 0.1, 0.2]), FIN.key: Stand([0.1, 4.0, 0.2])}), the_slots=slots(financial=FIN))        # FIN: Bullish = positive
    assert split.comparison.status == "disagreement" and split.overall_sentiment == "uncertain" and split.uncertainty_reason == "models_disagree"
    assert {m.slot: m.normalized_label for m in split.models} == {"financial": "positive", "general": "negative"}                 # both independent results preserved
    adapter.clear_cache()
    one = panel(root=tmp_path, factory_=by_role({HZ.key: Stand([4.0, 0.1, 0.2]), FIN.key: Stand(error=lambda t: RuntimeError(t))}), the_slots=slots(financial=FIN))
    assert one.comparison.status == "one_model_unavailable" and one.overall_source == "rules_baseline_fallback" and one.uncertainty_reason == "one_model_unavailable"


def test_text_the_rules_pipeline_declines_never_reaches_a_model_including_tamil_and_code_mixed_text(tmp_path):
    build_artifact(tmp_path, HZ)
    stand = Stand([1, 0, 0])
    declined = ["The weather is lovely and the football was great", "ok", "Je suis inquiet pour mon épargne et mes dettes ce mois", "என் கடன் தவணை அதிகரித்து வருவதால் எனக்கு கவலையாக இருக்கிறது",
                "எனக்கு savings பற்றி ரொம்ப worry ஆக இருக்கு and my EMI is high"]
    for text in declined:
        out = panel(text, root=tmp_path, factory_=factory(stand), the_slots=slots())
        general = next(m for m in out.models if m.slot == "general")
        assert out.processing_metadata["input_eligible"] is False and general.unavailable_reason == "input_not_eligible", text
        assert out.uncertainty_reason == "input_not_eligible" and out.processing_metadata["total_ms"] is None
    assert stand.calls == 0                                                                                                 # multilingual inference is unreachable BY DESIGN (ADR-055)


def test_no_text_and_no_reading_means_no_result_not_a_neutral():
    out = service.build_transformer_research(None, analyse_user_text(None))
    assert out.overall_sentiment is None and out.rules_baseline is None and all(m.normalized_label is None for m in out.models)


def test_the_research_path_can_never_break_the_production_response(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("[WinError 126] DLL load failed: " + TEXT)

    monkeypatch.setattr(inference_service, "run_research", boom)
    out = service.build_transformer_research(TEXT, analyse_user_text(TEXT))
    assert [m.unavailable_reason for m in out.models] == ["internal_error", "internal_error"] and out.overall_source == "rules_baseline_fallback"
    assert out.overall_sentiment == out.rules_baseline.label and "DLL" not in out.model_dump_json() and TEXT not in out.model_dump_json()


# ------------------------------------------------------------------------------------------------------------------------ privacy and isolation
def test_the_text_appears_nowhere_in_the_serialised_panel_or_in_any_log(tmp_path, caplog):
    secret = "my savings number is blue-harbour-47 and my loan EMI worries me"
    caplog.set_level("DEBUG")
    build_artifact(tmp_path, HZ)
    out = panel(secret, root=tmp_path, factory_=factory(Stand(error=lambda t: RuntimeError(t))), the_slots=slots())
    assert "blue-harbour" not in out.model_dump_json() and "blue-harbour" not in caplog.text


def test_the_package_logs_prints_stores_and_sends_nothing():
    for path in PKG.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(logging|socket|requests|httpx|urllib|http|aiohttp|sqlalchemy|pickle|joblib|shelve|sqlite3|subprocess)\b", source, re.M), path.name
        assert not re.search(r"\bprint\(|\.write_text\(|\.write_bytes\(|(?<![\w.])open\(|\.open\([^)]*[\"'][wax+]|os\.system|os\.environ", source), path.name
        assert not re.search(r"^\s*(import|from)\s+(torch|transformers|tokenizers|safetensors)\b", source, re.M), path.name           # only the existing guarded backend imports them, lazily
        assert "trust_remote_code=True" not in source and "from_pretrained" not in source and "hf_hub_download" not in source and "snapshot_download" not in source


def test_the_research_panel_changes_nothing_else_in_the_response(monkeypatch):
    from wealthpilot.api.services import demo_behaviour_service as demo
    real = service.build_transformer_research
    outputs = []
    for label in ("negative", "positive"):
        def fake(text, analysis, _label=label, **kw):
            return real(text, analysis).model_copy(update={"overall_sentiment": _label, "uncertainty_reason": None, "overall_source": "transformer_comparison"})
        monkeypatch.setattr(service, "build_transformer_research", fake)
        outputs.append(demo.build_demo(TEXT))
    a, b = (o.model_dump(exclude={"insight": {"transformer_research", "analysis_timestamp"}}) for o in outputs)
    assert json.dumps(a, default=str, sort_keys=True) == json.dumps(b, default=str, sort_keys=True)


def test_the_package_imports_no_financial_decision_module():
    forbidden = ("risk", "portfolio", "goals", "compliance", "recommendation", "optimizer", "household_finance", "emi", "loan", "agents", "api", "db", "training")
    for path in PKG.glob("*.py"):
        for match in re.finditer(r"^\s*(?:from|import)\s+wealthpilot\.([\w.]+)", path.read_text(encoding="utf-8"), re.M):
            parts = match.group(1).split(".")
            assert parts[0] == "core" and not any(p in forbidden or p.startswith(("risk_", "portfolio_", "goal", "compliance", "recommend")) for p in parts[1:]), (path.name, match.group(0))


def test_production_activation_is_still_off_everywhere():
    from wealthpilot.config.settings import Settings
    s = Settings(_env_file=None)
    assert s.sentiment_transformers_enabled is False and s.sentiment_model_enabled is False and s.sentiment_transformers_threads == ""
    example = [l.strip() for l in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines() if l.startswith("SENTIMENT_TRANSFORMERS_ENABLED")]
    assert example == ["SENTIMENT_TRANSFORMERS_ENABLED=false"]
    status = service.sentiment_model_status()
    assert status.production_method == "user_text_rules_v1" and status.production_activation == "not_activated" and status.transformers_enabled is False
    assert {c.model_key: c.availability for c in status.research_models} == {"horizon": "disabled", "finbert": "disabled", "roberta": "disabled"}
    assert [(s.role, s.state) for s in status.research_slots] == [("financial", "no_candidate_approved"), ("general", "registered")]
    assert status.method_when_used == "rules_baseline"
