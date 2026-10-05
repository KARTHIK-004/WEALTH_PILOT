"""POST /api/scenarios/compare."""

from __future__ import annotations

from tests.backend.api.conftest import approved_steps, patch_graph
from wealthpilot.api.services import analysis_service


def test_compare_two_scenarios_for_the_same_profile(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    response = client.post(
        "/api/scenarios/compare",
        json={
            "scenario_a": {"profile_id": customer.id},
            "scenario_b": {"profile_id": customer.id, "portfolio_strategy": "hrp"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_a"]["label"] == "A"
    assert body["scenario_b"]["label"] == "B"
    assert body["scenario_a"]["risk_category"] == "Balanced"


def test_compare_scenarios_nonexistent_profile_returns_404(client):
    response = client.post(
        "/api/scenarios/compare",
        json={"scenario_a": {"profile_id": 999999999}, "scenario_b": {"profile_id": 999999998}},
    )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
