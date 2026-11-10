"""`POST /api/demo/financial-behaviour` -- the fictional demonstration data for the Financial Behaviour & Sentiment page (development / demo mode only).

Exercised WITHOUT a database: the session dependency is a stub that fails on any use. The route is off unless `DEMO_MODE_ENABLED=true`; every month and sentence is fictional; every ratio and change
comes from the existing behaviour-feature code; the sentence is read by the existing rules baseline (`user_text_rules_v1`); the model stays disabled, confidence and intensity stay null; nothing is
logged, stored, sent to the ledger or read from a customer record.
"""
from __future__ import annotations

import ast
import json
import logging
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.main import app
from wealthpilot.api.services import demo_behaviour_service as demo
from wealthpilot.config import get_settings
from wealthpilot.config.settings import Settings
from wealthpilot.core.behaviour_features import MonthlyObservation, compute_behaviour_features
from wealthpilot.core.user_text_sentiment import METHOD_VERSION, analyse_user_text

URL = "/api/demo/financial-behaviour"
ROOT = Path(__file__).resolve().parents[3]


class NoDb:
    def __getattr__(self, name):                                                                  # pragma: no cover - only reached on a violation
        raise AssertionError(f"the demo route used the database session ({name})")


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode_enabled", True)
    app.dependency_overrides[get_session] = lambda: NoDb()
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
def off(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode_enabled", False)
    app.dependency_overrides[get_session] = lambda: NoDb()
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def post(client, text=None):
    return client.post(URL, json={"text": text})


# ------------------------------------------------------------------------------------------------------------------------------- the switch
def test_demo_mode_is_off_by_default_in_settings_and_in_the_example_environment_file():
    assert Settings(_env_file=None).demo_mode_enabled is False
    lines = [l.strip() for l in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines() if l.startswith("DEMO_MODE_ENABLED")]
    assert lines == ["DEMO_MODE_ENABLED=false"]


def test_with_demo_mode_off_the_route_is_a_404_problem_and_returns_no_data(off):
    response = post(off, "I feel more confident about saving this month")
    assert response.status_code == 404 and response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["title"] == "Demo mode is not enabled" and "months" not in body and "insight" not in body and "confidence" not in json.dumps(body)


# ------------------------------------------------------------------------------------------------------------------------------- the fictional months and the existing calculation
def test_demo_mode_returns_several_clearly_fictional_months_oldest_first_and_flags_itself_as_demo(on):
    body = post(on).json()
    assert body["demo"] is True and body["data_source"] == "demo_fixture" and body["insight"]["customer_id"] == 0
    assert "fictional" in body["notice"].lower() and "never written" in body["notice"].lower()
    assert [m["period"] for m in body["months"]] == [p for p, *_ in demo.FIXTURE_MONTHS] and len(body["months"]) == 6
    assert [(m["income"], m["expenses"], m["savings"]) for m in body["months"]] == [(float(i), float(e), float(s)) for _, i, e, s in demo.FIXTURE_MONTHS]
    assert body["insight"]["behaviour"]["observation_count"] == 6 and body["insight"]["behaviour"]["latest_period"] == "2026-08"


def test_every_ratio_and_change_comes_from_the_existing_behaviour_feature_code(on, monkeypatch):
    body = post(on).json()
    observations = [MonthlyObservation(period=date(int(p[:4]), int(p[5:7]), 1), income=Decimal(i), expenses=Decimal(e), savings=Decimal(s), income_basis="net") for p, i, e, s in demo.FIXTURE_MONTHS]
    for index, month in enumerate(body["months"]):
        expected = compute_behaviour_features(observations[: index + 1])
        assert month["expense_to_income"]["value"] == expected.latest_ratios.expense_to_income.value
        assert month["savings_to_income"]["value"] == expected.latest_ratios.savings_to_income.value
        assert month["expenses_change"]["relative_change"]["value"] == expected.expenses_change.relative_change.value
        assert month["savings_change"]["absolute_change"]["value"] == expected.savings_change.absolute_change.value
    first, second = body["months"][0], body["months"][1]
    assert first["expenses_change"]["relative_change"]["value"] is None and "no change can be measured" in first["expenses_change"]["relative_change"]["unavailable_reason"]
    assert second["expenses_change"]["relative_change"]["value"] == pytest.approx((43200 - 41500) / 41500)
    calls = []
    original = demo.compute_behaviour_features
    monkeypatch.setattr(demo, "compute_behaviour_features", lambda observations: (calls.append(len(list(observations))), original(observations))[1])
    post(on)
    assert sorted(calls) == [1, 2, 3, 4, 5, 6, 6]                                                          # one calculation per month and one over all six: nothing is calculated by hand


def test_the_behaviour_findings_cover_trends_ratios_activity_and_the_month_count(on):
    insight = post(on).json()["insight"]
    findings = {f["code"]: f for f in insight["behaviour"]["findings"]}
    for code in ("history_sufficiency", "expenses_trend", "savings_trend", "savings_activity", "expense_to_income_ratio", "savings_to_income_ratio"):
        assert findings[code]["status"] == "observed", code
    assert findings["expenses_trend"]["direction"] == "decreased" and findings["savings_trend"]["direction"] == "increased"
    assert findings["investment_contribution_trend"]["status"] == "unavailable" and findings["debt_burden"]["status"] == "not_included"             # unavailable stays unavailable, never zero
    assert "6 months have been reported." in [s["text"] for s in insight["statements"]] and insight["behaviour"]["history"] != "none"


# ------------------------------------------------------------------------------------------------------------------------------- the sentiment reading
def test_the_example_sentence_is_read_by_the_existing_rules_baseline_not_a_hand_written_result(on):
    body = post(on, demo.EXAMPLE_TEXT).json()
    sentiment = body["insight"]["user_sentiment"]
    direct = analyse_user_text(demo.EXAMPLE_TEXT)
    assert (sentiment["sentiment"], sentiment["emotional_tone"], sentiment["abstained"], sentiment["financial_relevance"]) == (direct.sentiment, direct.emotional_tone, direct.abstained, direct.financial_relevance)
    assert sentiment["method"] == "rules_baseline" and sentiment["model_version"] == METHOD_VERSION == "user_text_rules_v1"
    assert sentiment["confidence"] is None and sentiment["sentiment_intensity"] is None and sentiment["intensity_available"] is False and sentiment["class_probabilities"] is None
    assert sentiment["fallback_used"] is False and sentiment["validation_status"] != "validated"
    assert body["sentiment_model"]["enabled"] is False and body["sentiment_model"]["state"] == "disabled" and body["sentiment_model"]["method_when_used"] == "rules_baseline"
    assert body["sentiment_model"]["intensity_available"] is False and body["sentiment_model"]["model_name"] is None


def test_no_text_gives_the_records_only_view_with_an_unavailable_reading(on):
    sentiment = post(on).json()["insight"]["user_sentiment"]
    assert sentiment["status"] == "unavailable" and sentiment["sentiment"] is None and sentiment["confidence"] is None and sentiment["sentiment_intensity"] is None


@pytest.mark.parametrize("text", ['My friend said "I hate my debt" yesterday.', "My brother is terrified about his mortgage.", "The weather is lovely and the football was great."])
def test_quoted_third_person_and_unrelated_text_still_abstains_in_demo_mode(on, text):
    sentiment = post(on, text).json()["insight"]["user_sentiment"]
    assert sentiment["abstained"] is True and sentiment["sentiment"] == "insufficient_evidence" and sentiment["confidence"] is None and sentiment["evidence"] == []


@pytest.mark.parametrize("text", ["If I lost my job I would panic about my savings.", "Last year I was very stressed about my loan."])
def test_hypothetical_and_past_only_text_is_not_a_current_sentiment_in_demo_mode(on, text):
    sentiment = post(on, text).json()["insight"]["user_sentiment"]
    assert sentiment["interpretation_state"] == "weak" and sentiment["sentiment"] in ("uncertain", "neutral") and sentiment["evidence"] == [] and sentiment["confidence"] is None


def test_an_unusable_text_is_a_400_that_never_echoes_it(on):
    secret = "SECRET-TOKEN-" + "x" * 5000
    response = post(on, secret)
    assert response.status_code == 400 and "SECRET-TOKEN" not in response.text


# ------------------------------------------------------------------------------------------------------------------------------- isolation, privacy and the ledger
def test_the_demo_never_touches_the_database_a_ledger_or_the_financial_decisions(on):
    assert post(on, demo.EXAMPLE_TEXT).status_code == 200                                         # the session stub raises on any use
    for name in ("demo_behaviour_service.py", "demo.py"):
        path = ROOT / "backend" / "wealthpilot" / "api" / ("services" if name.endswith("service.py") else "routers") / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(x.startswith(("sqlalchemy", "wealthpilot.db", "wealthpilot.security", "wealthpilot.agents")) for x in imported), (name, imported)
        assert "logging" not in imported and "get_session" not in path.read_text(encoding="utf-8")
    assert "sentiment" not in (ROOT / "backend" / "wealthpilot" / "security" / "ledger.py").read_text(encoding="utf-8").lower()


def test_no_raw_text_reaches_the_logs(on, caplog):
    sentence = "I feel more confident about saving this month, but I am still watching my expenses."
    with caplog.at_level(logging.DEBUG):
        post(on, sentence)
    assert sentence not in caplog.text and "confident about saving" not in caplog.text


def test_the_sentiment_flag_stays_false_and_demo_mode_does_not_change_it(on):
    settings = get_settings()
    assert settings.sentiment_model_enabled is False and settings.demo_mode_enabled is True
    assert post(on, demo.EXAMPLE_TEXT).json()["insight"]["user_sentiment"]["method"] == "rules_baseline"


def test_the_existing_customer_route_is_unchanged_and_not_affected_by_the_demo_flag(on):
    names = {r.path for r in app.routes}
    assert "/api/profiles/{profile_id}/personalized-insights" in names and URL in names
    # a customer route still needs a real customer: with a stub session it fails the stub, it never falls back to demo data
    with pytest.raises(AssertionError, match="database session"):
        TestClient(app).post("/api/profiles/1/personalized-insights", json={"text": None})


def test_the_response_is_deterministic_apart_from_the_timestamp(on):
    first, second = post(on, demo.EXAMPLE_TEXT).json(), post(on, demo.EXAMPLE_TEXT).json()
    first["insight"].pop("analysis_timestamp"), second["insight"].pop("analysis_timestamp")
    assert first == second


def test_the_frontend_fixtures_are_what_the_route_returns_now():
    done = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "export_demo_fixtures.py"), "--check"], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert done.returncode == 0 and "fixtures match the backend" in done.stdout, done.stdout[-300:] + done.stderr[-300:]


def test_the_404_for_a_switched_off_demonstration_tells_a_developer_what_to_do_and_names_no_data(off):
    for route in ("/api/demo/financial-behaviour", "/api/demo/family-financial-behaviour"):
        body = off.post(route, json={"text": "I feel more confident about saving this month"}).json()
        assert body["status"] == 404 and body["title"] == "Demo mode is not enabled"
        assert "DEMO_MODE_ENABLED=true" in body["detail"] and "restart the backend" in body["detail"]
        assert "months" not in body and "members" not in body and "confident" not in json.dumps(body)         # nothing of the note comes back
