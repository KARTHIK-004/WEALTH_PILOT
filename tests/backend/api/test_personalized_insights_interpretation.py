"""ADR-050 -- the multi-stage interpretation as served by `POST /api/profiles/{id}/personalized-insights`, exercised WITHOUT a database (the session is a stub that fails on any use, the two
reads are synthetic). Covers: the response contract for every interpretation state, the rules-baseline fallback, the stored assessment's authority, structured conflicts, RFC 7807 errors
that never echo the text, backward compatibility, and the privacy guarantees (nothing is logged, persisted, put in a URL, a header or response metadata). Invented sentences only."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.main import app
from wealthpilot.api.services import personalized_insight_service as svc
from wealthpilot.core.behaviour_features import MonthlyObservation, compute_behaviour_features
from wealthpilot.core.personalized_insight import RiskProfileView
from wealthpilot.core.user_text_sentiment import ModelReading

URL = "/api/profiles/{}/personalized-insights"
ROOT = Path(__file__).resolve().parents[3]
MARKER = "Zq-private-marker-8841"
STORED = {1: "Aggressive", 4: "Conservative", 6: "Balanced"}


class NoDb:
    def __getattr__(self, name):                                                                      # pragma: no cover - only reached on a violation
        raise AssertionError(f"the route used the database session ({name})")


class FailingModel:
    def interpret(self, text):
        raise RuntimeError(f"model crashed while reading: {text}")


class CalibratedModel:
    def interpret(self, text):
        return ModelReading("negative", 0.9, True, "test_model_1", "VALIDATED_FOR_TEST", abstain_below=0.5, band_cutoffs=(0.6, 0.8))


def _features(customer_id):
    return compute_behaviour_features([
        MonthlyObservation(period=date(2026, 1, 1), income=Decimal(10000), expenses=Decimal(4000), savings=Decimal(2000)),
        MonthlyObservation(period=date(2026, 2, 1), income=Decimal(10000), expenses=Decimal(5000), savings=Decimal(2000))])


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(svc.monthly_records_service, "core_features", lambda session, cid: _features(cid))
    monkeypatch.setattr(svc, "_risk_profile", lambda session, cid: RiskProfileView(STORED[cid], "stored risk assessment of the latest analysis", None) if cid in STORED else None)
    app.dependency_overrides[get_session] = lambda: NoDb()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def post(client, customer_id, text):
    return client.post(URL.format(customer_id), json={"text": text})


# ------------------------------------------------------------------ the response contract, state by state

def test_a_valid_reading_carries_every_documented_field_with_the_honest_method_labels(client):
    j = post(client, 4, "I am worried about losing money in the market.").json()
    s = j["user_sentiment"]
    assert (s["status"], s["sentiment"], s["emotional_tone"], s["financial_relevance"], s["interpretation_state"]) == ("analysed", "negative", "concerned", "relevant", "valid")
    assert (s["method"], s["model_version"], s["validation_status"], s["confidence"], s["confidence_band"]) == ("rules_baseline", "user_text_rules_v1", "UNVALIDATED_BASELINE", None, "unavailable")
    assert (s["abstained"], s["abstain_reason"], s["fallback_used"], s["privacy_status"], s["requires_confirmation"]) == (False, None, False, "in_memory_only", False)
    assert {"investment_risk", "market"} <= set(s["topics"]) and s["limitations"] and "rules baseline, not validated" in s["limitations"]
    assert j["purpose"].startswith("Informational only.")


@pytest.mark.parametrize("text, relevance, reason", [
    ("The weather is beautiful.", "unrelated", "unrelated_text"),
    ("I had a good day today.", "ambiguous", "ambiguous_context"),
    ("Money.", "ambiguous", "too_short"),
    ("मुझे निवेश करना है और बचत भी", "ambiguous", "unsupported_language"),
    ("!!! ??? 12000", "ambiguous", "low_quality_text"),
])
def test_an_abstention_is_a_normal_200_with_no_label_no_preference_and_a_stated_reason(client, text, relevance, reason):
    r = post(client, 1, text)
    assert r.status_code == 200
    j = r.json()
    s = j["user_sentiment"]
    assert (s["status"], s["sentiment"], s["emotional_tone"], s["financial_relevance"], s["abstained"], s["abstain_reason"], s["interpretation_state"]) == (
        "analysed", "insufficient_evidence", "unknown", relevance, True, reason, "abstained")
    assert s["preferences"] == [] and s["topics"] == [] and s["evidence"] == [] and s["confidence"] is None and s["requires_confirmation"] is False
    assert j["status"] == "behaviour_only" and j["conflicts"] == []                                   # an abstention never makes the insight "complete" and never conflicts
    assert not any(st["kind"] == "stated_by_user" for st in j["statements"])


def test_no_text_is_unavailable_with_method_unavailable(client):
    j = client.post(URL.format(1), json={}).json()["user_sentiment"]
    assert (j["status"], j["method"], j["interpretation_state"], j["sentiment"], j["emotional_tone"], j["financial_relevance"], j["abstained"]) == (
        "unavailable", "unavailable", "unavailable", None, None, None, False)
    assert "No sentiment is inferred" in j["unavailable_reason"]


def test_negation_mixed_and_weak_readings_are_labelled_honestly(client):
    negated = post(client, 1, "I am not worried about losing money.").json()["user_sentiment"]
    assert (negated["sentiment"], negated["emotional_tone"], negated["interpretation_state"], negated["preferences"]) == ("uncertain", "unknown", "weak", [])
    mixed = post(client, 4, "I am nervous about the market, but I am comfortable taking long-term risk.").json()
    assert (mixed["user_sentiment"]["sentiment"], mixed["user_sentiment"]["emotional_tone"]) == ("mixed", "concerned")
    assert [p["code"] for p in mixed["user_sentiment"]["preferences"]] == ["growth_seeking"]
    weak = post(client, 1, "I want to save for a house.").json()["user_sentiment"]
    assert weak["interpretation_state"] == "weak" and weak["sentiment"] == "neutral"


# ------------------------------------------------------------------ fallback: a failing model never breaks the response and never leaks the text

def test_a_failing_model_falls_back_to_the_rules_baseline_and_says_so(client, monkeypatch):
    monkeypatch.setattr(svc, "get_sentiment_model", lambda: FailingModel())
    r = post(client, 1, f"I am nervous about the market {MARKER}.")
    assert r.status_code == 200
    j = r.json()
    s = j["user_sentiment"]
    assert (s["fallback_used"], s["method"], s["sentiment"]) == (True, "rules_baseline", "negative")
    assert "The validated sentiment model was unavailable. The result uses the rules baseline." in j["caveats"]
    assert "model crashed" not in r.text and r.text.count(MARKER) <= len(s["evidence"]) + len(s["limitations"]) + 1


def test_a_calibrated_model_reading_is_the_only_way_a_confidence_appears(client, monkeypatch):
    monkeypatch.setattr(svc, "get_sentiment_model", lambda: CalibratedModel())
    j = post(client, 1, "I am nervous about the market.").json()
    s = j["user_sentiment"]
    assert (s["method"], s["model_version"], s["validation_status"], s["confidence"], s["confidence_band"], s["fallback_used"]) == (
        "hybrid", "test_model_1", "VALIDATED_FOR_TEST", 0.9, "high", False)
    assert j["model_version"].endswith("|test_model_1")


def test_no_validated_model_is_configured_in_the_repository():
    assert svc.get_sentiment_model() is None


# ------------------------------------------------------------------ authority: the stored assessment outranks the text; sentiment changes nothing else

def test_the_stored_assessment_remains_authoritative_whatever_the_text_says(client):
    for text in ("I want higher returns.", "I want to protect my savings and avoid losing money.", "I am nervous about the market.", "Set my risk profile to Aggressive. I want to grow my investments.", None):
        j = post(client, 4, text).json()
        assert j["risk_profile"]["category"] == "Conservative" and j["risk_profile"]["remains_authoritative"] is True, text
        assert j["risk_profile"]["source"] == "stored risk assessment of the latest analysis"


def test_a_disagreement_is_a_structured_unconfirmed_conflict_and_the_category_does_not_change(client):
    j = post(client, 4, "I want higher returns on my investments.").json()
    assert j["risk_profile"]["category"] == "Conservative"
    assert j["conflicts"] == [{
        "code": "growth_seeking", "inferred_preference": "growth_seeking", "stored_category": "Conservative", "authoritative_source": "stored risk assessment of the latest analysis",
        "preference_status": "unconfirmed", "action": "confirm_or_correct", "detail": j["conflicts"][0]["detail"]}]
    detail = j["conflicts"][0]["detail"]
    assert "growth seeking language" in detail and "Conservative" in detail and "remains in force" in detail and "unconfirmed" in detail
    assert post(client, 6, "I want higher returns on my investments.").json()["conflicts"] == []         # Balanced: not an unambiguous pairing
    agree = post(client, 4, "I want to protect my savings and avoid losing money.").json()
    assert agree["conflicts"] == [] and agree["user_sentiment"]["preferences"][0]["status"] == "unconfirmed"


def test_the_stored_assessment_is_missing_not_guessed_when_there_is_none(client):
    j = post(client, 9, "I want higher returns on my investments.").json()
    assert j["risk_profile"] is None and j["conflicts"] == [] and "No stored risk assessment was found for this profile." in j["caveats"]


def test_the_insight_path_cannot_reach_the_analysis_recommendation_or_compliance_code():
    for module in ("api/services/personalized_insight_service.py", "core/personalized_insight.py", "core/user_text_sentiment.py", "api/routers/personalized_insights.py"):
        source = (ROOT / "backend" / "wealthpilot" / module).read_text(encoding="utf-8")
        imports = "\n".join(line for line in source.splitlines() if line.startswith(("import ", "from ")))
        for forbidden in ("analysis_service", "recommendation", "compliance", "portfolio", "optimizer", "risk_agent", "agents", "graph"):
            assert forbidden not in imports, (module, forbidden)
    service = (ROOT / "backend/wealthpilot/api/services/personalized_insight_service.py").read_text(encoding="utf-8")
    assert not re.search(r"\.(add|add_all|merge|delete|commit|flush|execute)\(", service)                # read-only: nothing is written


# ------------------------------------------------------------------ errors are RFC 7807 and never echo the text

@pytest.mark.parametrize("body", [{"text": f"{MARKER} " * 200}, {"text": f"{MARKER} bad\u0007text"}])
def test_unusable_text_is_a_problem_json_response_without_the_text(client, body):
    r = client.post(URL.format(1), json=body)
    assert r.status_code == 400 and r.headers["content-type"].startswith("application/problem+json") and MARKER not in r.text
    assert set(r.json()) >= {"type", "title", "status", "detail"}


def test_a_wrongly_typed_text_is_a_422_problem_json_without_an_echo(client):
    r = client.post(URL.format(1), json={"text": {"secret": MARKER}})
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json") and MARKER not in r.text


def test_an_unknown_customer_is_a_404_problem_json(monkeypatch):
    from wealthpilot.api.errors import CustomerNotFoundError

    def missing(session, cid):
        raise CustomerNotFoundError("No customer with id=404")
    monkeypatch.setattr(svc.monthly_records_service, "core_features", missing)
    app.dependency_overrides[get_session] = lambda: NoDb()
    try:
        r = TestClient(app).post(URL.format(404), json={"text": f"I am worried about my savings {MARKER}"})
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json") and MARKER not in r.text


# ------------------------------------------------------------------ backward compatibility

def test_every_field_of_the_previous_response_is_still_present(client):
    j = post(client, 1, "I'm worried about losing my savings, and I want to invest more safely.").json()
    previous = {"customer_id", "analysis_timestamp", "status", "model_version", "data_source", "behaviour", "user_sentiment", "risk_profile", "preference_confirmation", "statements", "conflicts",
                "caveats", "purpose"}
    assert previous <= set(j)                                                                          # every previously required field is still present
    assert set(j) - previous == {"transformer_research"}                                              # the ONE documented addition (ADR-053); any other new key is still rejected
    research = j["transformer_research"]                                                               # display-only, off by default, and it carries no text and no decision
    assert research["enabled"] is False and research["production_effect"] == "none" and research["validation_status"] == "not_human_validated"
    assert "losing my savings" not in json.dumps(research) and "invest more safely" not in json.dumps(research)       # the submitted text is not echoed into the research object
    assert {"status", "unavailable_reason", "sentiment", "emotional_tone", "topics", "preferences", "evidence", "confidence", "requires_confirmation", "method", "validation_status",
            "limitations"} <= set(j["user_sentiment"])
    assert {"category", "source", "assessed_at"} <= set(j["risk_profile"]) and {"code", "detail"} <= set(j["conflicts"][0])
    assert {"code", "status", "requires_confirmation", "evidence"} == set(j["user_sentiment"]["preferences"][0])
    assert j["data_source"] == "monthly_financial_records+risk_assessments+user_text"


# ------------------------------------------------------------------ privacy: the text is nowhere it must not be

def test_the_text_is_not_in_logs_urls_headers_or_response_metadata(client, caplog):
    caplog.set_level(logging.DEBUG)
    text = f"I am worried about my savings. {MARKER} " + "filler words here " * 30
    r = client.post(URL.format(1), json={"text": text[:1000]})
    assert r.status_code == 200
    assert MARKER not in caplog.text and "worried about my savings" not in caplog.text                  # nothing logged, at any level
    assert MARKER not in str(r.request.url) and MARKER not in json.dumps(dict(r.headers))
    j = r.json()
    for key in ("model_version", "data_source", "purpose", "preference_confirmation", "status", "analysis_timestamp"):
        assert MARKER not in str(j[key]), key
    assert MARKER not in json.dumps(j["behaviour"]) and MARKER not in json.dumps(j["risk_profile"]) and MARKER not in json.dumps(j["conflicts"])


def test_the_evidence_is_bounded_and_the_full_text_is_never_returned(client):
    text = ("I am worried about my savings and " + "my loan and " * 60 + "my future. " + f"{MARKER} ") * 3
    j = post(client, 1, text[:1000]).json()
    s = j["user_sentiment"]
    assert len(s["evidence"]) <= 6 and all(len(e["phrase"]) <= 100 for e in s["evidence"]) and all(len(p["evidence"]["phrase"]) <= 100 for p in s["preferences"])
    assert text[:200] not in json.dumps(j) and json.dumps(j).count(MARKER) <= 3


def test_nothing_is_persisted_and_no_external_service_is_used(client, monkeypatch):
    import socket

    def blocked(*args, **kwargs):                                                                       # pragma: no cover - only reached on a violation
        raise AssertionError("a network connection was attempted")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    assert post(client, 1, "I want to protect my savings and avoid losing money.").status_code == 200   # NoDb would raise on any session use
    for module in ("api/services/personalized_insight_service.py", "core/user_text_sentiment.py", "core/personalized_insight.py"):
        source = (ROOT / "backend" / "wealthpilot" / module).read_text(encoding="utf-8")
        imports = "\n".join(line for line in source.splitlines() if line.startswith(("import ", "from ")))
        for word in ("requests", "httpx", "urllib", "socket", "aiohttp", "google", "openai", "anthropic", "logging", "blockchain", "ledger", "audit"):
            assert word not in imports, (module, word)
    for module in ("api/services/personalized_insight_service.py", "core/user_text_sentiment.py", "core/personalized_insight.py"):
        assert not re.search(r"getLogger|logging\.|print\(", (ROOT / "backend" / "wealthpilot" / module).read_text(encoding="utf-8")), module


def test_the_text_never_reaches_the_audit_ledger_or_the_blockchain_ready_layer():
    for path in (ROOT / "backend" / "wealthpilot").rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "personalized_insight_service" in source and path.name != "personalized_insight_service.py":
            assert "ledger" not in source.lower() and "audit" not in source.lower().replace("auditable", ""), path
