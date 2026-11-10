"""ADR-043 -- `POST /api/profiles/{id}/personalized-insights`, exercised WITHOUT a database: the session dependency is a stub that fails on any use, and the two reads
(monthly features, stored risk assessment) are replaced with synthetic fixtures. That proves the route, schema, validation, privacy and isolation behaviour; it does not prove
the SQL queries (the monthly-features query is the same `core_features` used by `GET .../behaviour-features`, covered by `test_monthly_records.py`, which needs the test database)."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.errors import CustomerNotFoundError
from wealthpilot.api.main import app
from wealthpilot.api.services import personalized_insight_service as svc
from wealthpilot.core.behaviour_features import MonthlyObservation, compute_behaviour_features
from wealthpilot.core.personalized_insight import RiskProfileView

URL = "/api/profiles/{}/personalized-insights"
EXAMPLE = "I'm worried about losing my savings, and I want to invest more safely."
CALLS: list[int] = []


class NoDb:
    """Any attribute access means the route touched the database directly."""

    def __getattr__(self, name):                                                                      # pragma: no cover - only reached on a violation
        raise AssertionError(f"the route used the database session ({name})")


def features_for(customer_id: int):
    CALLS.append(customer_id)
    if customer_id == 404:
        raise CustomerNotFoundError("No customer with id=404")
    if customer_id == 2:                                                                              # a customer with no records
        return compute_behaviour_features([])
    base = 1000 * customer_id
    return compute_behaviour_features([
        MonthlyObservation(period=date(2026, 1, 1), income=Decimal(base * 10), expenses=Decimal(base * 4), savings=Decimal(base * 2)),
        MonthlyObservation(period=date(2026, 2, 1), income=Decimal(base * 10), expenses=Decimal(base * 5), savings=Decimal(base * 2))])


def risk_for(customer_id: int):
    if customer_id == 3:
        return None                                                                                   # customer 3 has no stored assessment
    return RiskProfileView("Aggressive" if customer_id == 1 else "Conservative", "stored risk assessment of the latest analysis", None)


@pytest.fixture()
def client(monkeypatch):
    CALLS.clear()
    monkeypatch.setattr(svc.monthly_records_service, "core_features", lambda session, cid: features_for(cid))
    monkeypatch.setattr(svc, "_risk_profile", lambda session, cid: risk_for(cid))
    app.dependency_overrides[get_session] = lambda: NoDb()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_no_text_returns_behaviour_with_an_explicit_unavailable_sentiment(client):
    r = client.post(URL.format(1), json={})
    assert r.status_code == 200
    j = r.json()
    assert j["customer_id"] == 1 and j["status"] == "behaviour_only"                                  # months exist, no text: behaviour still stands
    s = j["user_sentiment"]
    assert (s["status"], s["sentiment"], s["emotional_tone"], s["confidence"], s["preferences"]) == ("unavailable", None, None, None, [])
    assert s["unavailable_reason"] and j["behaviour"]["history"] == "multiple_months" and j["analysis_timestamp"]
    assert j["data_source"] and j["model_version"].startswith("personalized_insight_v2|behaviour_findings_v1|user_text_rules_v1")
    assert any("No text was provided" in c for c in j["caveats"]) and "not financial advice" in j["purpose"].lower()


def test_the_example_text_gives_the_structured_unconfirmed_reading(client):
    j = client.post(URL.format(3), json={"text": EXAMPLE}).json()
    s = j["user_sentiment"]
    assert (s["status"], s["sentiment"], s["emotional_tone"], s["confidence"], s["requires_confirmation"]) == ("analysed", "negative", "concerned", None, True)
    assert s["preferences"][0]["code"] == "capital_preservation" and s["preferences"][0]["status"] == "unconfirmed"
    assert s["validation_status"] == "UNVALIDATED_BASELINE" and j["risk_profile"] is None and j["status"] == "behaviour_only"       # no stored assessment: not "complete"
    assert "not available yet" in j["preference_confirmation"]
    assert j["behaviour"]["findings"] and all(f["sources"] for f in j["behaviour"]["findings"])


def test_a_customer_without_months_still_gets_a_valid_insight(client):
    j = client.post(URL.format(2), json={"text": EXAMPLE}).json()
    assert j["behaviour"]["history"] == "none" and j["status"] == "profile_only"
    assert all(f["status"] in ("unavailable", "not_included") for f in j["behaviour"]["findings"]) and j["user_sentiment"]["status"] == "analysed"


def test_the_stored_assessment_wins_and_a_disagreement_is_reported(client):
    j = client.post(URL.format(1), json={"text": "I want to invest safely."}).json()                  # customer 1 is Aggressive
    assert j["status"] == "complete" and j["risk_profile"]["category"] == "Aggressive" and [c["code"] for c in j["conflicts"]] == ["capital_preservation"]
    assert "remains in force" in j["conflicts"][0]["detail"]
    ok = client.post(URL.format(4), json={"text": "I want to invest safely."}).json()                  # customer 4 is Conservative
    assert ok["conflicts"] == []


def test_customers_are_isolated_by_the_path_id(client):
    a = client.post(URL.format(1), json={}).json()["behaviour"]["findings"]
    b = client.post(URL.format(5), json={}).json()["behaviour"]["findings"]
    assert CALLS == [1, 5] and a != b                                                                   # each call read only its own customer's data
    assert client.post(URL.format(404), json={}).status_code == 404


def test_unusable_text_is_a_problem_response_that_never_echoes_the_text(client):
    for body in ({"text": "ZQXJKV" * 200}, {"text": "bad\u0000text ZQXJKV"}):
        r = client.post(URL.format(1), json=body)
        assert r.status_code == 400 and r.headers["content-type"].startswith("application/problem+json")
        assert "ZQXJKV" not in r.text and r.json()["title"] == "Invalid request"


def test_the_text_is_not_logged_and_the_database_is_never_touched(client, caplog):
    caplog.set_level(logging.DEBUG)
    r = client.post(URL.format(1), json={"text": EXAMPLE})
    assert r.status_code == 200
    assert "worried about losing" not in caplog.text and "invest more safely" not in caplog.text


def test_the_response_is_display_only_and_declared_in_the_api_schema(client):
    j = client.post(URL.format(1), json={"text": EXAMPLE}).json()
    for forbidden in ("recommendation", "allocation", "portfolio", "risk_score", "compliance"):
        assert forbidden not in j
    schema = client.get("/openapi.json").json()
    assert URL.format("{profile_id}") in schema["paths"] and "post" in schema["paths"][URL.format("{profile_id}")]
    assert "PersonalizedInsightResponse" in schema["components"]["schemas"]
