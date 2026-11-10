"""API surface of the research-only pretrained comparison (ADR-053, role slots and lifecycle from ADR-055), exercised WITHOUT a database (the session dependency fails on any use).

`GET /api/sentiment-model/status` reports the known candidates, the role slots, their recorded findings, whether weights exist, and that production is still the rules baseline. A status read
NEVER loads, hashes or verifies a model. The insight response carries one OPTIONAL object, `transformer_research`; every existing field and every old client payload stays valid, and a failure
anywhere in the research path still gives the production response a 200. Nothing here runs a real model: nothing is registered, and the stand-in cases register a test-only copy.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.main import app
from wealthpilot.api.schemas import PersonalizedInsightResponse
from wealthpilot.api.services import personalized_insight_service as service
from wealthpilot.config import get_settings
from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.sentiment import adapter, inference_service, registry


@pytest.fixture(autouse=True)
def _the_real_model_directory_is_never_read(monkeypatch, tmp_path_factory):
    """Horizon is registered (R1) and its verified files may now sit under models/sentiment_pretrained. Unit tests must stay hermetic: whenever the default (real) directory would be used, an empty one is
    substituted, so no test can load the real weights by accident. The opt-in real-weights smoke test lives in its own file and is the only thing that reads the real directory."""
    empty = tmp_path_factory.mktemp("no-models")
    real_classify, real_status = inference_service.classify_with, adapter.candidate_status
    monkeypatch.setattr(inference_service, "classify_with", lambda cand, cfg, text, **kw: real_classify(cand, cfg, text, **{**kw, "root": empty if kw.get("root") == adapter.PRETRAINED_ROOT else kw.get("root", empty)}))
    monkeypatch.setattr(adapter, "candidate_status", lambda cand, cfg, *, root=None: real_status(cand, cfg, root=empty if root in (None, adapter.PRETRAINED_ROOT) else root))

TEXT = "I am worried because my monthly loan payments are becoming difficult to manage."
SECRET = "blue-harbour-47"


class NoDb:
    def __getattr__(self, name):                                                                  # pragma: no cover - only reached on a violation
        raise AssertionError(f"the route used the database session ({name})")


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode_enabled", True)
    app.dependency_overrides[get_session] = lambda: NoDb()
    adapter.clear_cache()
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)
    adapter.clear_cache()


def switch_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "sentiment_transformers_enabled", True)
    monkeypatch.setattr(get_settings(), "sentiment_transformers_max_tokens", "128")
    monkeypatch.setattr(get_settings(), "sentiment_transformers_timeout_seconds", "5")


def test_the_status_endpoint_reports_candidates_slots_and_that_only_a_research_candidate_is_registered_and_nothing_is_activated(client):
    body = client.get("/api/sentiment-model/status").json()
    assert body["production_method"] == "user_text_rules_v1" and body["production_activation"] == "not_activated" and body["transformers_enabled"] is False
    assert body["enabled"] is False and body["state"] == "disabled" and body["method_when_used"] == "rules_baseline"                # the existing fields are unchanged
    assert {(s["role"], s["state"], s["candidate_key"]) for s in body["research_slots"]} == {("financial", "no_candidate_approved", None), ("general", "registered", "horizon")}
    by_key = {m["model_key"]: m for m in body["research_models"]}
    assert set(by_key) == {"horizon", "finbert", "roberta"}
    hz = by_key["horizon"]
    assert (hz["role"], hz["repository"], hz["revision"], hz["weight_licence"], hz["licence_status"], hz["format_status"], hz["registration"]) == (
        "general", "Horizon-Labs/multilingual-sentiment-small", "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac", "apache-2.0", "license_verified", "safetensors_available", "registered")
    assert by_key["finbert"]["registration"] == by_key["roberta"]["registration"] == "historical"
    assert (by_key["finbert"]["licence_status"], by_key["roberta"]["licence_status"]) == ("blocked_by_licence", "license_unverified")
    for m in by_key.values():
        assert m["loaded"] is False and m["inference_enabled"] is False and m["availability"] == "disabled" and m["checked_on"] == "2026-11-03"
        assert bool(m["blocker"]) == (m["model_key"] != "horizon")                                                        # only the registered research candidate has no blocker


def test_the_status_never_returns_a_local_path_or_a_secret(client):
    raw = client.get("/api/sentiment-model/status").text
    for needle in ("C:\\\\", "Users", "Administrator", "sentiment_pretrained", "secret", "password", "api_key", "bearer"):
        assert needle.lower() not in raw.lower(), needle
    import re
    assert not re.search(r"hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}", raw)                    # no access-token-shaped string ("tokenizer" in public review text is not a secret)


def test_switched_on_the_status_reports_the_registered_candidate_without_loading_it_and_never_claims_activation(client, monkeypatch):
    switch_on(monkeypatch)
    body = client.get("/api/sentiment-model/status").json()
    assert body["transformers_enabled"] is True and body["production_activation"] == "not_activated"
    by_key = {m["model_key"]: m for m in body["research_models"]}
    assert (by_key["horizon"]["availability"], by_key["horizon"]["reason"]) == ("weights_missing", "weights_missing")                  # (the hermetic fixture points at an empty directory)
    assert (by_key["finbert"]["availability"], by_key["finbert"]["reason"]) == ("blocked", "licence_not_verified")
    assert all(m["loaded"] is False for m in by_key.values())


def test_a_status_request_never_loads_hashes_or_verifies_a_model_even_when_one_is_registered_and_present(client, monkeypatch, tmp_path):
    switch_on(monkeypatch)
    hz = dataclasses.replace(registry.HORIZON, registration=registry.REGISTERED)                                         # TEST-ONLY registration
    monkeypatch.setattr(registry, "CANDIDATES", (hz, registry.FINBERT, registry.ROBERTA))
    weights = tmp_path / hz.key
    weights.mkdir()
    (weights / sm.WEIGHTS_FILE).write_bytes(b"placeholder")
    real = adapter.candidate_status
    monkeypatch.setattr(service.research_adapter, "candidate_status", lambda c, cfg: real(c, cfg, root=tmp_path))
    monkeypatch.setattr(adapter, "verify_pretrained", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a status request verified the model")))
    monkeypatch.setattr(adapter, "_default_backend", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a status request built the model")))
    monkeypatch.setattr(adapter, "_sha256", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a status request hashed a file")))
    for _ in range(3):
        response = client.get("/api/sentiment-model/status")
        assert response.status_code == 200
    by_key = {m["model_key"]: m for m in response.json()["research_models"]}
    assert (by_key["horizon"]["availability"], by_key["horizon"]["weights_present"], by_key["horizon"]["loaded"], by_key["horizon"]["inference_enabled"]) == ("not_loaded", True, False, True)
    assert {(s["role"], s["state"], s["candidate_key"]) for s in response.json()["research_slots"]} == {("financial", "no_candidate_approved", None), ("general", "registered", "horizon")}


def test_the_insight_response_carries_the_research_object_beside_unchanged_existing_fields(client):
    body = client.post("/api/demo/financial-behaviour", json={"text": TEXT}).json()["insight"]
    research = body["transformer_research"]
    assert research["enabled"] is False and research["mode"] == "research_experimental" and research["production_effect"] == "none" and research["validation_status"] == "not_human_validated"
    assert [(m["slot"], m["availability"], m["unavailable_reason"], m["model_id"]) for m in research["models"]] == [("financial", "unavailable", "no_candidate_approved", None), ("general", "unavailable", "disabled", "Horizon-Labs/multilingual-sentiment-small")]
    assert research["comparison"]["status"] == "model_unavailable" and research["comparison"]["model_vs_rules"] == [] and len(research["notices"]) == 3
    assert research["overall_source"] == "rules_baseline_fallback" and research["uncertainty_reason"] == "transformers_unavailable" and research["model_versions"] == {"general": "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac"}
    sentiment = body["user_sentiment"]                                                           # the production reading is untouched
    assert sentiment["method"] == "rules_baseline" and sentiment["confidence"] is None and sentiment["sentiment_intensity"] is None and sentiment["fallback_used"] is False
    assert body["risk_profile"] is None or body["risk_profile"]["remains_authoritative"] is True
    assert all("confidence" not in m for m in research["models"]) and "intensity" not in json.dumps(research).lower()                 # no confidence field and no intensity anywhere in the research object


def test_the_response_is_identical_apart_from_the_research_object_whatever_the_research_settings_say(client, monkeypatch):
    base = client.post("/api/demo/financial-behaviour", json={"text": TEXT}).json()["insight"]
    switch_on(monkeypatch)
    monkeypatch.setattr(get_settings(), "sentiment_transformers_threads", "2")
    on = client.post("/api/demo/financial-behaviour", json={"text": TEXT}).json()["insight"]
    for body in (base, on):
        body.pop("transformer_research"), body.pop("analysis_timestamp")
    assert base == on


def test_an_old_client_payload_without_the_new_field_still_validates(client):
    body = client.post("/api/demo/financial-behaviour", json={"text": TEXT}).json()["insight"]
    body.pop("transformer_research")
    assert PersonalizedInsightResponse.model_validate(body).transformer_research is None


def test_a_rejected_text_is_a_problem_response_that_never_echoes_the_text(client):
    secret = "x" * 5 + "\x07" + "call me on 07700 900123 about my savings"
    response = client.post("/api/demo/financial-behaviour", json={"text": secret})
    assert response.status_code in (400, 422) and "07700" not in response.text and "call me" not in response.text


def test_no_text_means_no_model_is_asked_and_the_panel_says_so(client):
    research = client.post("/api/demo/financial-behaviour", json={"text": None}).json()["insight"]["transformer_research"]
    assert research["processing_metadata"]["input_eligible"] is False and research["overall_sentiment"] is None and research["processing_metadata"]["total_ms"] is None


def test_a_failure_anywhere_in_the_research_path_still_gives_the_production_response_a_200_and_leaks_nothing(client, monkeypatch):
    def explode(*a, **k):
        raise OSError(f"[WinError 126] DLL load failed while handling: {SECRET}")

    monkeypatch.setattr(inference_service, "run_research", explode)
    response = client.post("/api/demo/financial-behaviour", json={"text": f"I am worried about my loan, reference {SECRET}"})
    assert response.status_code == 200 and SECRET not in response.text and "DLL" not in response.text
    body = response.json()["insight"]
    assert [m["unavailable_reason"] for m in body["transformer_research"]["models"]] == ["internal_error", "internal_error"]
    assert body["user_sentiment"]["method"] == "rules_baseline" and body["transformer_research"]["overall_source"] == "rules_baseline_fallback"


def test_a_stand_in_model_registered_for_the_test_flows_through_the_whole_response_and_the_text_is_not_in_it(client, monkeypatch, tmp_path):
    switch_on(monkeypatch)
    hz = dataclasses.replace(registry.HORIZON, registration=registry.REGISTERED)
    monkeypatch.setattr(registry, "CANDIDATES", (hz, registry.FINBERT, registry.ROBERTA))
    directory = tmp_path / hz.key
    directory.mkdir()
    files = {sm.WEIGHTS_FILE: b"placeholder", sm.CONFIG_FILE: json.dumps({"id2label": {"0": "negative", "1": "neutral", "2": "positive"}, "vocab_size": 100}).encode(), sm.TOKENIZER_CONFIG_FILE: b"{}"}
    for name, data in files.items():
        (directory / name).write_bytes(data)
    hashes = {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}
    (directory / adapter.MANIFEST_FILE).write_text(json.dumps({"manifest_schema_version": 1, "repository": hz.repository, "revision": hz.revision, "weight_licence": hz.weight_licence, "tokenizer_length": 90,
                                                                "files": hashes, "manifest_sha256": sm.manifest_sha256(hashes)}), encoding="utf-8")

    class Stand:
        def predict(self, text):
            return sm.BackendOutput((4.0, 0.1, 0.2))

    real = service.build_transformer_research
    monkeypatch.setattr(service, "build_transformer_research", lambda text, analysis, **k: real(text, analysis, root=tmp_path, backend_factory=lambda i, c: Stand(), **k))
    response = client.post("/api/demo/financial-behaviour", json={"text": f"{TEXT} {SECRET}"})
    research = response.json()["insight"]["transformer_research"]
    general = next(m for m in research["models"] if m["slot"] == "general")
    assert (general["availability"], general["native_label"], general["normalized_label"], general["model_id"]) == ("available", "negative", "negative", "Horizon-Labs/multilingual-sentiment-small")
    assert research["comparison"]["status"] == "single_model" and research["model_versions"] == {"general": hz.revision} and SECRET not in response.text
    assert response.json()["insight"]["user_sentiment"]["method"] == "rules_baseline"
