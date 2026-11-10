"""OPT-IN smoke test of the REAL Horizon weights through the application's own adapter and service path (ADR-055, ADR-056, owner request R2). SKIPPED BY DEFAULT and not part of ordinary CI.

It runs only when BOTH are true:
  1. WEALTHPILOT_REAL_WEIGHTS_SMOKE=1 is set (an explicit decision to run a real model), and
  2. `models/sentiment_pretrained/horizon/` holds the approved files and a `pretrained_manifest.json` written by `scripts/write_pretrained_manifest.py`.
Every sentence is FICTIONAL. The result is a SMOKE observation: it shows that the registered adapter can verify, load and run the approved revision and that its outputs are normalised, deterministic,
single-softmax and private. It is NOT an accuracy, calibration or validation measurement, and nothing here compares the model with ground truth. No network entry point is allowed.

Set WEALTHPILOT_SMOKE_EVIDENCE=<path.json> to write the measured outputs (the file contains no sentence other than the fixed fictional ones).
"""
from __future__ import annotations

import json
import logging
import math
import os
import socket
import statistics
import threading
import time

import pytest

from wealthpilot.api.services import personalized_insight_service as service
from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.sentiment import adapter, registry
from wealthpilot.core.user_text_sentiment import analyse_user_text

HORIZON = registry.HORIZON                                                                                    # the REAL registered constant (R1): no test-only copy
DIRECTORY = adapter.PRETRAINED_ROOT / HORIZON.key

pytestmark = pytest.mark.skipif(os.environ.get("WEALTHPILOT_REAL_WEIGHTS_SMOKE") != "1" or not (DIRECTORY / adapter.MANIFEST_FILE).is_file(),
                                reason="opt-in: set WEALTHPILOT_REAL_WEIGHTS_SMOKE=1 and place the verified model with a manifest under models/sentiment_pretrained/horizon (owner request R2)")

# Fixed fictional sentences, with the raw logits the Stage A run (direct loading, outside the application) produced for the same text, rounded to 4 decimals there.
SENTENCES = {
    "positive": ("I feel happy because my savings have increased this month.", [-2.0312, -1.7527, 6.6002]),
    "negative": ("I am worried because my monthly loan payments are becoming difficult to manage.", [4.7016, 0.621, -2.8954]),
    "neutral": ("I deposited five thousand rupees into my savings account this month.", [-2.3736, 3.4073, 0.1764]),
    "negation": ("I am not worried about my savings at all.", [-1.1405, 0.8518, 1.9771]),
    "mixed": ("My investments are growing, but I am worried about future expenses.", [0.211, 2.544, -0.8277]),
    "ambiguous": ("I reviewed my account statement yesterday.", [-1.7857, 4.418, -0.8145]),
}
UNSUPPORTED = "Estoy muy contento porque por fin pude ahorrar para mis vacaciones."                               # Spanish: must never reach the model
MARKER = "zebra-quartz-8141"                                                                                  # a unique token to prove no text is logged or returned
CONFIG = adapter.ResearchConfig(enabled=True, max_tokens=512, timeout_seconds=60.0, device="cpu")
EVIDENCE: dict = {"scope": "smoke observation on fictional sentences; not an accuracy evaluation", "machine_note": "this machine and this test configuration only"}


def softmax(values):
    peak = max(values)
    exps = [math.exp(v - peak) for v in values]
    return [e / sum(exps) for e in exps]


def rss_mb() -> dict:
    import ctypes
    from ctypes import wintypes as wt

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    counters = PMC()
    counters.cb = ctypes.sizeof(PMC)
    k32, psapi = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("psapi", use_last_error=True)
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return {"peak_mb": round(counters.PeakWorkingSetSize / 1048576, 1), "current_mb": round(counters.WorkingSetSize / 1048576, 1)}


@pytest.fixture(autouse=True)
def guarded(monkeypatch):
    """No network, no torch.load, offline hub flags; and a clean adapter cache around every test."""
    attempts: list[str] = []

    def refuse(*a, **k):
        attempts.append("network")
        raise RuntimeError("network blocked")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    import torch
    monkeypatch.setattr(torch, "load", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("torch.load must not be used")))
    adapter.clear_cache()
    yield attempts
    assert attempts == []
    adapter.clear_cache()


@pytest.fixture(scope="module", autouse=True)
def write_evidence():
    yield
    path = os.environ.get("WEALTHPILOT_SMOKE_EVIDENCE")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(EVIDENCE, handle, indent=2, sort_keys=True)


# ------------------------------------------------------------------------------------------------------------------------ identity and status
def test_the_registered_constant_and_the_placed_manifest_describe_the_exact_approved_revision():
    manifest = json.loads((DIRECTORY / adapter.MANIFEST_FILE).read_text(encoding="utf-8"))
    assert HORIZON.registered and HORIZON.runnable_in_principle and HORIZON.role == "general"
    assert (manifest["repository"], manifest["revision"], manifest["weight_licence"]) == ("Horizon-Labs/multilingual-sentiment-small", "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac", "apache-2.0")
    assert manifest["files"][sm.WEIGHTS_FILE] == "f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1" and manifest["tokenizer_length"] == 256000
    assert registry.registered_candidate("financial") is None                                                  # the financial slot stays empty


def test_a_status_read_with_the_real_files_present_loads_hashes_and_verifies_nothing(monkeypatch):
    boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("a status read touched the model"))           # noqa: E731
    for name in ("verify_pretrained", "_default_backend", "_sha256"):
        monkeypatch.setattr(adapter, name, boom)
    for _ in range(3):
        status = adapter.candidate_status(HORIZON, CONFIG)
    assert (status.availability, status.weights_present, status.loaded, status.reason) == ("not_loaded", True, False, None)
    assert service.sentiment_model_status().transformers_enabled is False                                      # the endpoint builder stays cheap with the flag off


# ------------------------------------------------------------------------------------------------------------------------ the real model through the adapter
def test_the_adapter_verifies_loads_and_classifies_fixed_fictional_sentences_deterministically_with_one_softmax():
    started = time.perf_counter()
    first_loaded = adapter.classify_with(HORIZON, CONFIG, SENTENCES["negative"][0], role="general")           # first call: verification (hashes), load, inference
    load_and_first_seconds = time.perf_counter() - started
    assert first_loaded.available, first_loaded.unavailable_reason
    EVIDENCE["first_call_seconds_including_verification_and_load"] = round(load_and_first_seconds, 2)
    EVIDENCE["memory_after_load"] = rss_mb()
    rows, timings = {}, []
    for name, (text, stage_a_logits) in SENTENCES.items():
        t0 = time.perf_counter()
        result = adapter.classify_with(HORIZON, CONFIG, text, role="general")
        timings.append((time.perf_counter() - t0) * 1000)
        assert result.available and result.role == "general" and result.model_key == HORIZON.key and result.revision == HORIZON.revision
        assert [label for label, _ in result.raw_scores] == ["negative", "neutral", "positive"]               # the model's own label order, read from its config
        logits = [value for _, value in result.raw_scores]
        assert all(abs(a - b) <= 6e-4 for a, b in zip(logits, stage_a_logits)), (name, logits, stage_a_logits)   # same logits as the direct Stage A run (rounding only)
        probabilities = [value for _, value in result.probabilities]
        assert abs(sum(probabilities) - 1.0) < 1e-3
        assert all(abs(a - b) < 1.5e-3 for a, b in zip(probabilities, softmax(logits))), name                  # exactly ONE softmax of the logits ...
        assert not all(abs(a - b) < 1.5e-3 for a, b in zip(probabilities, softmax(softmax(logits))))                # ... and not a second one
        assert result.native_label == result.normalized_label
        assert result.normalized_label == ["negative", "neutral", "positive"][max(range(3), key=lambda i: logits[i])]
        again = adapter.classify_with(HORIZON, CONFIG, text, role="general")
        assert again.raw_scores == result.raw_scores and again.native_label == result.native_label          # repeated identical input: identical output
        rows[name] = {"native_label": result.native_label, "raw_scores": dict(result.raw_scores), "probabilities": dict(result.probabilities), "processing_ms": result.processing_ms}
    EVIDENCE["adapter_results"] = rows
    EVIDENCE["adapter_inference_ms"] = {"median": round(statistics.median(timings), 1), "min": round(min(timings), 1), "max": round(max(timings), 1), "calls": len(timings)}
    EVIDENCE["memory_after_inference"] = rss_mb()
    assert adapter.candidate_status(HORIZON, CONFIG).availability == "ready"                                    # a status read now reports the earlier load without causing one


def test_the_service_path_gives_a_research_comparison_with_safeguards_an_empty_financial_slot_and_no_confidence():
    outputs = {}
    for name, (text, _) in SENTENCES.items():
        analysis = analyse_user_text(text)
        research = service.build_transformer_research(text, analysis, config=CONFIG)
        dump = research.model_dump()
        financial, general = research.models
        if analysis.interpretation_state == "abstained":                                                       # the application's own eligibility gate: the model is never asked
            assert general.availability == "unavailable" and general.unavailable_reason == "input_not_eligible" and research.processing_metadata["input_eligible"] is False
            assert research.overall_source == "rules_baseline_fallback" and research.overall_sentiment == analysis.sentiment
            outputs[name] = {"rules_label": analysis.sentiment, "rules_state": "abstained", "model_called": False, "general_reason": general.unavailable_reason, "overall": research.overall_sentiment}
            continue
        assert (financial.slot, financial.availability, financial.unavailable_reason, financial.model_id) == ("financial", "unavailable", "no_candidate_approved", None)
        assert general.availability == "available", (name, general.unavailable_reason)
        assert general.slot == "general" and general.model_id == HORIZON.repository and general.revision == HORIZON.revision
        assert research.enabled is True and research.production_effect == "none" and research.validation_status == "not_human_validated" and research.mode == "research_experimental"
        assert research.comparison.status == "single_model" and [v.slot for v in research.comparison.model_vs_rules] == ["general"]
        assert research.model_versions == {"general": HORIZON.revision}
        assert all("confidence" not in m for m in dump["models"]) and "intensity" not in json.dumps(dump).lower()
        label, rules_label = general.normalized_label, analysis.rules_label if analysis.rules_label is not None else analysis.sentiment
        if analysis.interpretation_state == "weak":
            assert research.overall_sentiment == "uncertain" and research.uncertainty_reason in ("context_safeguard", "rules_disagree")        # a rules safeguard keeps the combined reading uncertain
        elif rules_label == label:
            assert research.overall_sentiment == label and research.rules_relation == "agrees"
        elif analysis.interpretation_state == "abstained":
            assert research.rules_relation == "rules_abstained"
        else:
            assert research.overall_sentiment == "uncertain" and research.uncertainty_reason == "rules_disagree"
        outputs[name] = {"rules_label": rules_label, "rules_state": analysis.interpretation_state, "model_label": label, "overall": research.overall_sentiment, "overall_source": research.overall_source,
                         "relation": research.rules_relation, "uncertainty_reason": research.uncertainty_reason, "comparison": research.comparison.status}
    EVIDENCE["service_results"] = outputs                                                                      # recorded, not judged: this is not an accuracy evaluation


def test_unsupported_language_never_reaches_the_model_and_the_rules_reading_stands(monkeypatch):
    calls = []
    real = adapter.PretrainedAdapter.classify
    monkeypatch.setattr(adapter.PretrainedAdapter, "classify", lambda self, text: calls.append(1) or real(self, text))
    research = service.build_transformer_research(UNSUPPORTED, analyse_user_text(UNSUPPORTED), config=CONFIG)
    assert calls == [] and research.processing_metadata["input_eligible"] is False
    assert research.models[1].availability == "unavailable" and research.models[1].unavailable_reason == "input_not_eligible"
    assert research.overall_source == "rules_baseline_fallback" and research.overall_sentiment in ("insufficient_evidence", "uncertain")
    EVIDENCE["unsupported_language"] = {"model_called": False, "general_reason": research.models[1].unavailable_reason, "overall": research.overall_sentiment}


# ------------------------------------------------------------------------------------------------------------------------ privacy and isolation
def test_no_text_is_logged_returned_stored_or_sent_and_no_decision_module_is_touched(caplog):
    text = f"I am worried about my loan {MARKER} payments this month."
    with caplog.at_level(logging.DEBUG):
        research = service.build_transformer_research(text, analyse_user_text(text), config=CONFIG)
        adapter.classify_with(HORIZON, CONFIG, text, role="general")
    blob = research.model_dump_json() + "\n" + "\n".join(f"{r.name} {r.getMessage()}" for r in caplog.records)
    assert MARKER not in blob                                                                                  # (the structural isolation of decision modules is guarded in test_sentiment_research_slots.py)
    EVIDENCE["privacy"] = {"marker_in_response_or_logs": False, "network_attempts": 0, "torch_load_called": False}


# ------------------------------------------------------------------------------------------------------------------------ lifecycle
def test_concurrent_first_use_loads_once_and_the_other_callers_get_loading_or_the_result_without_an_error():
    results, errors = [], []
    barrier = threading.Barrier(4)

    def call():
        try:
            barrier.wait(timeout=30)
            results.append(adapter.classify_with(HORIZON, CONFIG, SENTENCES["positive"][0], role="general"))
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))
    threads = [threading.Thread(target=call) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=180)
    assert errors == [] and len(results) == 4
    states = sorted((r.available, r.unavailable_reason) for r in results)
    assert all(r.available or r.unavailable_reason == "loading" for r in results), states
    assert any(r.available for r in results)
    assert adapter.classify_with(HORIZON, CONFIG, SENTENCES["positive"][0], role="general").available                # after the load everything answers
    EVIDENCE["concurrency"] = {"callers": 4, "available": sum(r.available for r in results), "loading": sum(r.unavailable_reason == "loading" for r in results), "errors": 0}


def test_a_missing_directory_is_reported_as_a_fixed_reason_and_never_raises(tmp_path):
    missing = adapter.classify_with(HORIZON, CONFIG, SENTENCES["positive"][0], role="general", root=tmp_path / "nowhere")
    assert (missing.available, missing.unavailable_reason) == (False, "weights_missing")
    research = service.build_transformer_research(SENTENCES["positive"][0], analyse_user_text(SENTENCES["positive"][0]), config=CONFIG, root=tmp_path / "nowhere")
    assert research.models[1].unavailable_reason == "weights_missing" and research.overall_source == "rules_baseline_fallback"


def test_the_inference_timeout_is_bounded_and_the_breaker_answers_immediately_afterwards():
    tight = adapter.ResearchConfig(enabled=True, max_tokens=512, timeout_seconds=0.001, device="cpu")
    adapter.classify_with(HORIZON, tight, SENTENCES["positive"][0], role="general")                            # includes the (untimed) load; may or may not time out on the first call
    t0 = time.perf_counter()
    result = adapter.classify_with(HORIZON, tight, SENTENCES["negative"][0], role="general")
    elapsed = time.perf_counter() - t0
    t1 = time.perf_counter()
    again = adapter.classify_with(HORIZON, tight, SENTENCES["negative"][0], role="general")
    fast = time.perf_counter() - t1
    assert result.unavailable_reason == "timeout" and again.unavailable_reason == "timeout"
    assert elapsed < 1.0 and fast < 0.05                                                                       # bounded, and the second call does not queue behind the running one
    EVIDENCE["timeout"] = {"configured_seconds": 0.001, "second_call_seconds": round(elapsed, 4), "breaker_call_seconds": round(fast, 5)}
