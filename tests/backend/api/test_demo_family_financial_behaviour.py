"""`POST /api/demo/family-financial-behaviour` -- the fictional family for the Financial Behaviour & Sentiment page (development / demo mode only).

Exercised WITHOUT a database (the session dependency is a stub that fails on any use). The route is off unless `DEMO_MODE_ENABLED=true`; every name, month and sentence is fictional; every ratio and
change comes from the existing behaviour-feature code; the household totals are the real household engine over invented records; the note is the primary member's and is read by the existing rules
baseline (`user_text_rules_v1`); nothing is logged, stored or sent anywhere.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.main import app
from wealthpilot.api.services import demo_behaviour_service as demo
from wealthpilot.config import get_settings
from wealthpilot.core import household_finance as engine
from wealthpilot.core.behaviour_features import compute_behaviour_features
from wealthpilot.core.user_text_sentiment import analyse_user_text

URL = "/api/demo/family-financial-behaviour"
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


def family(client, text=None):
    response = client.post(URL, json={"text": text})
    assert response.status_code == 200, response.text[:300]
    return response.json()


def test_the_family_route_is_a_404_when_demo_mode_is_off(off):
    response = off.post(URL, json={"text": None})
    assert response.status_code == 404 and response.json()["title"] == "Demo mode is not enabled" and "members" not in response.json()


def test_the_family_demo_is_labelled_fictional_with_three_members_over_several_months(on):
    body = family(on)
    assert body["demo"] is True and body["scenario"] == "family" and body["data_source"] == "demo_fixture"
    assert body["notice"].startswith("Demo data — fictional family example") and body["household_label"] == "The Demo family (fictional)"
    assert [(m["label"], m["role"]) for m in body["members"]] == [("Primary member (demo)", "Primary household member"), ("Partner (demo)", "Partner"), ("Dependent (demo)", "Dependent")]
    assert [len(m["months"]) for m in body["members"]] == [6, 6, 3]
    assert all(m["insight"]["customer_id"] == 0 for m in body["members"])


def test_each_members_ratios_and_changes_come_from_the_existing_feature_code(on):
    body = family(on)
    for member, (label, _role, rows) in zip(body["members"], demo.FAMILY_MEMBERS):
        observations = [demo._observation(*row) for row in rows]
        for index, month in enumerate(member["months"]):
            expected = compute_behaviour_features(observations[: index + 1])
            assert month["expense_to_income"]["value"] == expected.latest_ratios.expense_to_income.value, (label, month["period"])
            assert month["savings_to_income"]["value"] == expected.latest_ratios.savings_to_income.value, (label, month["period"])
            assert month["income_change"]["relative_change"]["value"] == expected.income_change.relative_change.value, (label, month["period"])
            assert month["expenses_change"]["absolute_change"]["value"] == expected.expenses_change.absolute_change.value, (label, month["period"])
            assert month["investment_contribution_change"]["absolute_change"]["value"] == expected.investment_contribution_change.absolute_change.value, (label, month["period"])
            assert month["investment_contribution"] == (None if rows[index][4] is None else float(rows[index][4]))


def test_investment_history_is_shown_where_it_exists_and_missing_data_is_explained_where_it_does_not(on):
    body = family(on)
    findings = {m["label"]: {f["code"]: f for f in m["insight"]["behaviour"]["findings"]} for m in body["members"]}
    primary, partner, dependent = findings["Primary member (demo)"], findings["Partner (demo)"], findings["Dependent (demo)"]
    assert primary["investment_contribution_trend"]["status"] == "observed" and primary["investment_contribution_trend"]["direction"] == "increased"
    assert primary["income_trend"]["status"] == "observed" and primary["expenses_trend"]["direction"] == "decreased"
    assert primary["income_trend"]["statement"] == "Income was unchanged from the previous month."                  # grammar: a singular label takes "was"
    assert primary["income_trend"]["direction"] == "unchanged"
    assert partner["investment_contribution_trend"]["status"] == "observed" and partner["investment_contribution_activity"]["status"] == "unavailable"       # only two months of investing
    assert dependent["investment_contribution_trend"]["status"] == "unavailable" and dependent["income_trend"]["status"] == "unavailable" and dependent["savings_trend"]["status"] == "unavailable"
    assert "not reported in both months" in dependent["income_trend"]["statement"]
    for month in body["members"][2]["months"]:                                                         # a dependent with no income or savings reported: never zero
        assert month["income"] is None and month["savings"] is None and month["expense_to_income"]["value"] is None and month["expense_to_income"]["unavailable_reason"]


def test_the_household_totals_are_the_real_engine_output_over_invented_records(on):
    summary = family(on)["household_summary"]
    d = Decimal
    expected = engine.summarize_household_finances(
        [engine.IncomeRecord(amount=d(60000), frequency="monthly", is_active=True), engine.IncomeRecord(amount=d(44000), frequency="monthly", is_active=True)],
        [engine.ExpenseRecord(amount=d(18000), frequency="monthly", is_essential=True, is_active=True), engine.ExpenseRecord(amount=d(6000), frequency="monthly", is_essential=True, is_active=True),
         engine.ExpenseRecord(amount=d(120000), frequency="yearly", is_essential=True, is_active=True), engine.ExpenseRecord(amount=d(60000), frequency="one_time", is_essential=False, is_active=True)],
        [engine.AssetRecord(current_value=d(150000), is_liquid=True), engine.AssetRecord(current_value=d(300000), is_liquid=True), engine.AssetRecord(current_value=d(3500000), is_liquid=False)],
        [engine.LiabilityRecord(outstanding_amount=d(1800000), monthly_payment=d(21000)), engine.LiabilityRecord(outstanding_amount=d(220000), monthly_payment=None)])
    assert summary["household_id"] == 0
    assert summary["liabilities"]["outstanding"] == float(expected.liabilities.outstanding) == 2020000.0
    assert summary["liabilities"]["monthly_payment"] == float(expected.liabilities.monthly_payment) == 21000.0       # sums only the loan that states a payment: the other is not counted as zero
    assert summary["liabilities"]["record_count"] == 2
    assert summary["income"]["recurring_monthly"] == float(expected.income.recurring_monthly) == 104000.0
    assert summary["cash_flow"]["monthly"] == (None if expected.cash_flow.monthly is None else float(expected.cash_flow.monthly))


def test_the_note_is_the_primary_members_and_is_read_by_the_rules_baseline(on):
    body = family(on, demo.EXAMPLE_TEXT)
    primary, others = body["members"][0]["insight"]["user_sentiment"], [m["insight"]["user_sentiment"] for m in body["members"][1:]]
    direct = analyse_user_text(demo.EXAMPLE_TEXT)
    assert primary["sentiment"] == direct.sentiment and primary["method"] == "rules_baseline" and primary["model_version"] == "user_text_rules_v1"
    assert all(o["status"] == "unavailable" and o["sentiment"] is None for o in others)               # nobody else's note is invented
    assert primary["confidence"] is None and primary["sentiment_intensity"] is None and primary["intensity_available"] is False
    assert body["sentiment_model"]["enabled"] is False and body["sentiment_model"]["state"] == "disabled"


@pytest.mark.parametrize("text", ['My friend said "I hate my debt" yesterday.', "My brother is terrified about his mortgage.", "If I lost my job I would panic about my savings."])
def test_quoted_third_person_and_hypothetical_notes_are_not_a_current_feeling(on, text):
    primary = family(on, text)["members"][0]["insight"]["user_sentiment"]
    assert primary["abstained"] is True or primary["interpretation_state"] == "weak"
    assert primary["sentiment"] in ("insufficient_evidence", "uncertain", "neutral") and primary["confidence"] is None


def test_the_family_demo_uses_no_database_and_logs_no_text(on, caplog):
    sentence = "I feel more confident about saving this month, but I am still watching my expenses."
    with caplog.at_level(logging.DEBUG):
        assert on.post(URL, json={"text": sentence}).status_code == 200                              # the session stub raises on any use
    assert sentence not in caplog.text and "confident about saving" not in caplog.text
    source = (ROOT / "backend" / "wealthpilot" / "api" / "services" / "demo_behaviour_service.py").read_text(encoding="utf-8")
    assert "get_session" not in source and "logging" not in source and "Session" not in source


def test_the_family_response_is_deterministic_apart_from_the_timestamps(on):
    first, second = family(on, demo.EXAMPLE_TEXT), family(on, demo.EXAMPLE_TEXT)
    for body in (first, second):
        for member in body["members"]:
            member["insight"].pop("analysis_timestamp")
    assert first == second
    assert "analysis_timestamp" not in json.dumps(first)
