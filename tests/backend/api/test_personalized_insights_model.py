"""ADR-052 -- the trained-model path of `POST /api/profiles/{id}/personalized-insights` and `GET /api/sentiment-model/status`, WITHOUT a database (the session is a stub that fails on any use) and
WITHOUT any deep-learning package: a fake backend stands in for the Transformer, and a real (tiny, stand-in) artifact directory goes through the real settings -> verification -> service chain.
Covers the response contract in every state, fallback and abstention, the configuration chain, the stored assessment's authority, and privacy (nothing in logs, errors or metadata)."""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.main import app
from wealthpilot.api.services import personalized_insight_service as svc
from wealthpilot.config import get_settings
from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.behaviour_features import MonthlyObservation, compute_behaviour_features
from wealthpilot.core.personalized_insight import RiskProfileView
from wealthpilot.core.user_text_sentiment import ModelReading

URL = "/api/profiles/{}/personalized-insights"
ROOT = Path(__file__).resolve().parents[3]
PRIVATE = "Zq-private-model-marker-3310"
TEXT = "I am nervous about the market."


class NoDb:
    def __getattr__(self, name):                                                                      # pragma: no cover - only reached on a violation
        raise AssertionError(f"the route used the database session ({name})")


class Double:
    """A trained-model test double: returns a fixed reading, or raises."""

    def __init__(self, reading=None, error=None):
        self.reading, self.error = reading, error

    def interpret(self, text):
        if self.error:
            raise self.error
        return self.reading


def reading(label="negative", probability=0.9, probabilities=None, **over):
    values = dict(sentiment=label, probability=probability, calibrated=True, model_version="sentiment-v1", validation_status="validated", abstain_below=0.6, band_cutoffs=(0.6, 0.85),
                  class_probabilities=probabilities or {"positive": 0.04, "negative": probability, "neutral": round(0.96 - probability, 6)}, intensity=None, model_name="test-model")
    values.update(over)
    return ModelReading(**values)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(svc.monthly_records_service, "core_features", lambda session, cid: compute_behaviour_features([
        MonthlyObservation(period=date(2026, 1, 1), income=Decimal(10000), expenses=Decimal(4000), savings=Decimal(2000)),
        MonthlyObservation(period=date(2026, 2, 1), income=Decimal(10000), expenses=Decimal(5000), savings=Decimal(2000))]))
    monkeypatch.setattr(svc, "_risk_profile", lambda session, cid: RiskProfileView("Conservative", "stored risk assessment of the latest analysis", None))
    app.dependency_overrides[get_session] = lambda: NoDb()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def post(client, text=TEXT):
    return client.post(URL.format(1), json={"text": text})


def model_env(monkeypatch, **env):
    for key, value in {"SENTIMENT_MODEL_ENABLED": "true", "SENTIMENT_MODEL_NAME": "test-model", "SENTIMENT_MODEL_PATH": "sentiment-v1", "SENTIMENT_MODEL_VERSION": "sentiment-v1",
                       "SENTIMENT_MODEL_MAX_TOKENS": "128", **env}.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    sm.clear_cache()


@pytest.fixture(autouse=True)
def _clean_settings():
    yield
    get_settings.cache_clear()
    sm.clear_cache()


# ------------------------------------------------------------------------------------------------ switched off: the default


def test_with_the_model_switched_off_the_rules_baseline_is_the_method_and_every_model_field_is_honestly_empty(client):
    s = post(client).json()["user_sentiment"]
    assert (s["method"], s["fallback_used"], s["fallback_reason"], s["model_name"], s["class_probabilities"], s["confidence"], s["confidence_band"]) == ("rules_baseline", False, None, None, None, None, "unavailable")
    assert (s["confidence_calibration_status"], s["sentiment_intensity"], s["intensity_available"], s["disagreement"]) == ("not_applicable", None, False, False)
    assert s["rules_baseline"] == {"label": "negative", "method": "rules_baseline", "model_version": "user_text_rules_v1"} and s["validation_status"] == "UNVALIDATED_BASELINE"
    status = client.get("/api/sentiment-model/status")
    assert status.status_code == 200
    body = status.json()
    research = {"research_models", "reviewed_candidates", "research_slots", "transformers_enabled", "production_method", "production_activation"}        # ADR-053 / ADR-054 additive fields, covered by test_sentiment_research_api.py and test_sentiment_candidate_reviews.py
    assert {k: v for k, v in body.items() if k not in research} == {"enabled": False, "state": "disabled", "reason": None, "method_when_used": "rules_baseline", "model_name": None, "model_version": None,
                                                                    "validation_status": None, "calibration_status": None, "intensity_available": False, "fallback_enabled": True,
                                                                    "dependencies_available": sm.dependencies_available(), "data_source": "models/sentiment"}
    assert research <= set(body)


def test_the_default_settings_keep_the_model_off():
    settings = get_settings()
    assert settings.sentiment_model_enabled is False and settings.sentiment_model_allow_fallback is True and settings.sentiment_model_device == "cpu"
    assert "SENTIMENT_MODEL_ENABLED=false" in (ROOT / ".env.example").read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ a model answers


def test_a_validated_model_reading_fills_the_new_fields_and_changes_nothing_about_the_risk_profile(client, monkeypatch):
    plain = post(client).json()
    monkeypatch.setattr(svc, "get_sentiment_model", lambda: Double(reading(intensity=-0.72)))
    j = post(client).json()
    s = j["user_sentiment"]
    assert (s["method"], s["model_name"], s["model_version"], s["validation_status"], s["sentiment"], s["fallback_used"]) == ("hybrid", "test-model", "sentiment-v1", "validated", "negative", False)
    assert (s["confidence"], s["confidence_band"], s["confidence_calibration_status"], s["sentiment_intensity"], s["intensity_available"]) == (0.9, "high", "calibrated", -0.72, True)
    assert s["class_probabilities"] == {"positive": 0.04, "negative": 0.9, "neutral": 0.06} and s["rules_baseline"]["label"] == "negative" and s["disagreement"] is False
    assert j["risk_profile"] == plain["risk_profile"] and j["risk_profile"]["category"] == "Conservative" and j["risk_profile"]["remains_authoritative"] is True        # sentiment moves nothing
    assert j["conflicts"] == plain["conflicts"] and j["data_source"] == plain["data_source"] and "model_version" in j and j["model_version"].endswith("|sentiment-v1")
    assert (s["emotional_tone"], s["topics"], s["preferences"]) == (plain["user_sentiment"]["emotional_tone"], plain["user_sentiment"]["topics"], plain["user_sentiment"]["preferences"])


def test_a_disagreement_is_returned_with_both_readings_and_a_caveat(client, monkeypatch):
    monkeypatch.setattr(svc, "get_sentiment_model", lambda: Double(reading("positive", 0.93, {"positive": 0.93, "negative": 0.03, "neutral": 0.04})))
    j = post(client).json()
    s = j["user_sentiment"]
    assert (s["sentiment"], s["disagreement"], s["interpretation_state"], s["rules_baseline"]["label"], s["confidence"]) == ("uncertain", True, "weak", "negative", None)
    assert s["class_probabilities"]["positive"] == 0.93
    assert any("read this text differently" in c for c in j["caveats"]) and not any(st["kind"] == "stated_by_user" and "reads as positive" in st["text"] for st in j["statements"])


def test_a_confidence_below_the_models_threshold_falls_back_visibly(client, monkeypatch):
    monkeypatch.setattr(svc, "get_sentiment_model", lambda: Double(reading("negative", 0.41, {"positive": 0.29, "negative": 0.41, "neutral": 0.30})))
    j = post(client).json()
    s = j["user_sentiment"]
    assert (s["method"], s["fallback_used"], s["fallback_reason"], s["sentiment"], s["confidence"]) == ("rules_baseline", True, "below_threshold", "negative", None)
    assert "The validated sentiment model was unavailable. The result uses the rules baseline." in j["caveats"]


# ------------------------------------------------------------------------------------------------ a model that cannot answer


def test_a_model_exception_is_a_visible_fallback_and_never_leaks_the_text_or_the_error(client, monkeypatch, caplog):
    monkeypatch.setattr(svc, "get_sentiment_model", lambda: Double(error=RuntimeError(f"C:/secret/model/path failed on {PRIVATE}")))
    caplog.set_level(logging.DEBUG)
    r = post(client, f"{TEXT} {PRIVATE}")
    s = r.json()["user_sentiment"]
    assert r.status_code == 200 and (s["fallback_used"], s["fallback_reason"], s["method"], s["sentiment"]) == (True, "inference_failed", "rules_baseline", "negative")
    assert "C:/secret" not in r.text and "failed on" not in r.text and "Traceback" not in r.text and "failed on" not in caplog.text and PRIVATE not in caplog.text


def test_switched_on_without_the_packages_the_rules_answer_and_the_status_says_why(client, monkeypatch):
    model_env(monkeypatch)
    monkeypatch.setattr(sm, "dependencies_available", lambda: False)
    s = post(client).json()["user_sentiment"]
    assert (s["fallback_used"], s["fallback_reason"], s["method"], s["model_name"], s["sentiment"]) == (True, "dependencies_missing", "rules_baseline", None, "negative")
    status = client.get("/api/sentiment-model/status").json()
    assert (status["enabled"], status["state"], status["reason"], status["dependencies_available"], status["method_when_used"]) == (True, "unavailable", "dependencies_missing", False, "rules_baseline")


def test_switched_on_with_fallback_off_the_text_is_not_interpreted(client, monkeypatch):
    model_env(monkeypatch, SENTIMENT_MODEL_ALLOW_FALLBACK="false")
    monkeypatch.setattr(sm, "dependencies_available", lambda: False)
    j = post(client).json()
    s = j["user_sentiment"]
    assert (s["abstained"], s["abstain_reason"], s["sentiment"], s["preferences"], s["fallback_reason"], s["interpretation_state"]) == (True, "model_unavailable", "insufficient_evidence", [], "dependencies_missing", "abstained")
    assert j["status"] == "behaviour_only" and any("fallback to the rules baseline is switched off" in c for c in j["caveats"])
    assert client.get("/api/sentiment-model/status").json()["fallback_enabled"] is False


@pytest.mark.parametrize("env", [dict(SENTIMENT_MODEL_MAX_TOKENS="many"), dict(SENTIMENT_MODEL_MIN_CONFIDENCE="high"), dict(SENTIMENT_MODEL_MIN_CONFIDENCE="1.5"),
                                  dict(SENTIMENT_MODEL_TIMEOUT_SECONDS="soon")])
def test_an_unparsable_configuration_is_invalid_not_guessed(client, monkeypatch, env):
    model_env(monkeypatch, **env)
    s = post(client).json()["user_sentiment"]
    assert (s["fallback_reason"], s["method"]) == ("invalid_configuration", "rules_baseline")
    assert client.get("/api/sentiment-model/status").json()["reason"] == "invalid_configuration"


def test_a_device_other_than_cpu_or_a_missing_token_limit_is_refused(client, monkeypatch):
    monkeypatch.setattr(sm, "dependencies_available", lambda: True)
    for env in (dict(SENTIMENT_MODEL_DEVICE="cuda"), dict(SENTIMENT_MODEL_MAX_TOKENS="")):
        model_env(monkeypatch, **env)
        assert post(client).json()["user_sentiment"]["fallback_reason"] == "invalid_configuration", env


def test_a_real_artifact_goes_through_settings_verification_and_the_service(client, monkeypatch, artifact_root, make_artifact):
    """The real chain (settings -> config -> verification -> cache -> service) with a stand-in artifact and a fake backend; only the artifact root and the backend are substituted."""
    make_artifact("sentiment-v1")
    model_env(monkeypatch)
    original, original_status = sm.load_model, sm.model_status
    monkeypatch.setattr(svc.trained, "load_model", lambda cfg, **kw: original(cfg, backend_factory=lambda i, c: type("B", (), {"predict": lambda self, t: sm.BackendOutput((3.0, 0.0, 0.0))})(), root=artifact_root))
    monkeypatch.setattr(svc.trained, "model_status", lambda cfg, **kw: original_status(cfg, backend_factory=lambda i, c: None, root=artifact_root))
    s = post(client, "I feel confident about my savings.").json()["user_sentiment"]
    assert (s["method"], s["model_name"], s["validation_status"], s["confidence_calibration_status"], s["fallback_used"]) == ("hybrid", "test-model", "validated", "calibrated", False) and s["confidence"] is not None
    status = client.get("/api/sentiment-model/status").json()
    assert (status["state"], status["model_name"], status["model_version"], status["validation_status"], status["calibration_status"], status["method_when_used"]) == (
        "ready", "test-model", "sentiment-v1", "validated", "calibrated", "hybrid")
    assert str(artifact_root) not in json.dumps(status)                                              # no path leaves the service
    make_artifact("bad", validated=False)
    sm.clear_cache()
    model_env(monkeypatch, SENTIMENT_MODEL_PATH="bad")
    assert client.get("/api/sentiment-model/status").json()["reason"] == "not_validated"
    assert post(client).json()["user_sentiment"]["fallback_reason"] == "not_validated"


def test_the_status_route_is_read_only_and_customer_independent(client):
    assert client.post("/api/sentiment-model/status").status_code == 405
    schema = client.get("/openapi.json").json()
    assert "get" in schema["paths"]["/api/sentiment-model/status"] and list(schema["paths"]["/api/sentiment-model/status"]) == ["get"]


# ------------------------------------------------------------------------------------------------ safety and privacy


def test_the_model_path_cannot_reach_the_analysis_recommendation_compliance_or_the_ledger():
    for module in ("core/sentiment_model.py", "api/services/personalized_insight_service.py", "core/user_text_sentiment.py"):
        source = (ROOT / "backend" / "wealthpilot" / module).read_text(encoding="utf-8")
        imports = "\n".join(line for line in source.splitlines() if line.startswith(("import ", "from ")))
        for forbidden in ("analysis_service", "recommendation", "compliance", "portfolio", "optimizer", "agents", "graph", "security", "ledger", "audit", "blockchain", "requests", "httpx", "urllib", "socket"):
            assert forbidden not in imports, (module, forbidden)
    for path in (ROOT / "backend" / "wealthpilot" / "agents").rglob("*.py"):
        assert "sentiment_model" not in path.read_text(encoding="utf-8", errors="ignore"), path.name           # no agent, node or graph reads sentiment


def test_the_text_never_reaches_logs_urls_headers_or_error_bodies_on_the_model_paths(client, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    for model in (Double(reading()), Double(error=RuntimeError(PRIVATE)), Double(reading=None)):
        monkeypatch.setattr(svc, "get_sentiment_model", lambda m=model: m)
        r = post(client, f"I am nervous about my savings {PRIVATE}.")
        assert r.status_code == 200 and PRIVATE not in str(r.request.url) and PRIVATE not in json.dumps(dict(r.headers))
        body = r.json()
        for key in ("model_version", "data_source", "purpose", "status", "preference_confirmation"):
            assert PRIVATE not in str(body[key])
        assert PRIVATE not in json.dumps(body["user_sentiment"]["class_probabilities"]) and PRIVATE not in str(body["user_sentiment"]["fallback_reason"])
    assert PRIVATE not in caplog.text


def test_unusable_text_is_still_a_400_problem_response_on_the_model_path(client, monkeypatch):
    monkeypatch.setattr(svc, "get_sentiment_model", lambda: Double(reading()))
    r = client.post(URL.format(1), json={"text": f"{PRIVATE} bad\u0007text"})
    assert r.status_code == 400 and r.headers["content-type"].startswith("application/problem+json") and PRIVATE not in r.text
