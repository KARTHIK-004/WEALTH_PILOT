"""The full pipeline for the demo personas, end to end through the real application (see conftest.py for what is real and what is test-only).

Persona E ("Full Pipeline") must clear every stage; persona C must stay rejected by compliance; persona D must stay pending without any invented result.
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy import text

from seed_demo_data import ALL_DEMO_PERSONAS, seed_persona
from wealthpilot.agents import graph as G

E, D, C, A = "WPDEMO-E", "WPDEMO-D", "WPDEMO-C", "WPDEMO-A"
PERSONAS = {p["demo_key"]: p for p in ALL_DEMO_PERSONAS}


def nodes_run(world, key: str) -> list[str]:
    with world.engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT agent_name FROM agent_logs WHERE customer_id = :id ORDER BY id"), {"id": world.ids[key]})]


# ------------------------------------------------------------------------------------------ selecting the persona


def test_the_persona_is_found_by_its_exact_name_and_nothing_else_has_it(world):
    name = PERSONAS[E]["name"]
    found = world.client.get("/api/profiles/lookup", params={"name": name}).json()["customer_id"]
    assert found == world.ids[E]
    with world.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM customers WHERE name = :n"), {"n": name}).scalar() == 1


# ------------------------------------------------------------------------------------------ risk, then past the information-request node


def test_risk_feature_engineering_and_the_model_give_a_risk_result(world):
    risk = world.results[E]["risk"]
    assert risk["risk_category"] == "Balanced" and risk["unavailable_reason"] is None
    assert risk["confidence"] is not None and risk["confidence"] >= 0.50
    assert math.isclose(sum(risk["class_probabilities"].values()), 1.0, rel_tol=1e-6)


def test_the_graph_proceeds_beyond_the_information_request_node(world):
    ran = nodes_run(world, E)
    for node in (G.NODE_RISK_ANALYST, G.NODE_FINANCIAL_HEALTH, G.NODE_GOAL_ANALYST, G.NODE_MARKET_ANALYST, G.NODE_PORTFOLIO_MANAGER, G.NODE_COMPLIANCE_ANALYST):
        assert node in ran, f"{node} did not run: {ran}"
    assert G.NODE_INFORMATION_REQUEST not in ran
    assert world.results[E]["status"] == "approved"


# ------------------------------------------------------------------------------------------ goals


def test_the_goals_are_evaluated_by_the_existing_goal_engine(world):
    goals = world.results[E]["goals"]
    assert [g["goal_type"] for g in goals] == [g["goal_type"] for g in PERSONAS[E]["goals"]]
    for goal in goals:
        assert goal["unavailable_reason"] is None and goal["feasibility"] in {"Feasible", "At Risk", "Not Feasible"}
        assert 0.0 <= goal["monte_carlo_success_probability"] <= 1.0
        assert goal["inflation_adjusted_target_amount"] > goal["nominal_target_amount"] > 0     # a future target costs more than today's
        assert goal["required_periodic_contribution"] > 0
    assert world.results[E]["emergency_fund"]["sufficient"] is True and world.results[E]["emergency_fund"]["shortfall"] == 0


# ------------------------------------------------------------------------------------------ portfolio, recommendation, compliance, explanation


def test_the_portfolio_allocation_is_computed_and_valid(world):
    portfolio = world.results[E]["portfolio"]
    assert portfolio["weights"] and portfolio["unavailable_reason"] is None
    assert set(portfolio["weights"]) == {"QQQ", "AGG", "GLD"}
    assert math.isclose(sum(portfolio["weights"].values()), 1.0, abs_tol=1e-6) and min(portfolio["weights"].values()) >= -1e-9


def test_the_recommendation_follows_the_risk_category_and_the_computed_results(world):
    result = world.results[E]
    recommendation = result["recommendation"]
    assert recommendation["status"] == "approved" and recommendation["risk_category"] == result["risk"]["risk_category"] == "Balanced"
    assert recommendation["selected_strategy"] == "equal_weight"          # the approved risk-conditioned base strategy for Balanced
    weights = recommendation["weights"]
    assert all(math.isclose(w, 1 / 3, abs_tol=1e-9) for w in weights.values()) and math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9)
    assert recommendation["compliance_decision"] == result["compliance"]["decision"] == "PASS"
    reasons = " ".join(recommendation["rationale"]["reasons"])
    assert "Balanced" in reasons and "risk suitability" in reasons or recommendation["rationale"]["risk_based_strategy"] == "equal_weight"


def test_compliance_evaluates_the_recommendation_and_passes_for_this_persona(world):
    compliance = world.results[E]["compliance"]
    assert compliance["decision"] == "PASS" and len(compliance["rule_results"]) >= 5
    assert [r["rule_id"] for r in compliance["rule_results"] if r["triggered"]] == []


def test_a_rejection_stays_enforced_no_recommendation_and_no_explanation_reach_the_response(world):
    rejected = world.results[C]
    assert rejected["status"] == "rejected" and rejected["compliance"]["decision"] == "REJECT"
    assert "emergency_fund_savings_first" in [r["rule_id"] for r in rejected["compliance"]["rule_results"] if r["triggered"]]
    assert rejected["recommendation"] is None and rejected["explanation"] is None
    for key, result in world.results.items():            # the rule holds for every persona, not only this one
        if result["compliance"] and result["compliance"]["decision"] == "REJECT":
            assert result["recommendation"] is None and result["explanation"] is None, key


def test_the_explanation_is_only_ever_a_restatement_never_a_source_of_numbers(world):
    explanation = world.results[E]["explanation"]
    assert explanation is not None
    # No Gemini key in this module: the explanation reports its own failure and carries no prose, so no number or decision can have come from it.
    assert explanation["status"] == "failed" and explanation["failure_reason"].startswith("configuration_failure")
    assert explanation["summary"] is None and explanation["validation_passed"] is False
    assert world.results[E]["recommendation"]["selected_strategy"] == "equal_weight"      # the decision came from the computed pipeline regardless


# ------------------------------------------------------------------------------------------ behaviour findings from the monthly records


def test_the_monthly_behaviour_findings_are_computed_from_the_personas_months(world):
    records = PERSONAS[E]["monthly_records"]
    insight = world.client.post(f"/api/profiles/{world.ids[E]}/personalized-insights", json={"text": None}).json()
    behaviour = insight["behaviour"]
    assert insight["customer_id"] == world.ids[E] and behaviour["observation_count"] == 12 and behaviour["latest_period"] == "2026-09"
    findings = {f["code"]: f for f in behaviour["findings"]}
    last, previous = records[-1], records[-2]
    expenses = findings["expenses_trend"]
    assert expenses["status"] == "observed" and expenses["direction"] == ("increased" if last["expenses"] > previous["expenses"] else "decreased")
    assert expenses["values"]["absolute_change"] == last["expenses"] - previous["expenses"]       # the test's own arithmetic on the persona's file
    assert findings["savings_trend"]["direction"] == "decreased" and findings["savings_trend"]["values"]["absolute_change"] == last["savings"] - previous["savings"]
    for code, field in (("expense_to_income_ratio", "expenses"), ("savings_to_income_ratio", "savings"), ("investment_contribution_to_income_ratio", "investment_contribution")):
        assert findings[code]["status"] == "observed" and math.isclose(findings[code]["values"]["ratio"], last[field] / last["income"], rel_tol=1e-6), code
    assert findings["investment_contribution_trend"]["direction"] == "unchanged"
    for code in ("savings_activity", "investment_contribution_activity"):     # twelve months are enough for the activity facts a short history cannot give
        assert findings[code]["status"] == "observed" and findings[code]["values"]["known_months"] == 12 and findings[code]["values"]["share"] == 1.0, code
    assert findings["debt_burden"]["status"] == "not_included" and findings["goal_progress"]["status"] == "not_included"   # stated as unavailable, never zero
    assert insight["risk_profile"]["category"] == "Balanced"
    assert {s["kind"] for s in insight["statements"]} >= {"behaviour_fact", "risk_assessment"}


# ------------------------------------------------------------------------------------------ the stored assessment the behaviour page shows


def insight(world, key: str, text: str | None = None) -> dict:
    return world.client.post(f"/api/profiles/{world.ids[key]}/personalized-insights", json={"text": text}).json()


def test_the_stored_assessment_on_the_behaviour_page_is_the_latest_analysis_results_category(world):
    """The pipeline never writes `risk_assessments` (no ordinal risk_score exists), so the page's stored assessment must come from the latest analysis run: it used to be
    empty for every real user, which also meant the 'stored assessment stays the authority' conflict check could never fire."""
    for key, expected in ((E, "Balanced"), (A, "Aggressive"), (C, "Conservative")):
        profile = insight(world, key)["risk_profile"]
        assert profile is not None and profile["category"] == expected == world.results[key]["risk"]["risk_category"], key
        assert profile["source"] == "stored risk assessment of the latest analysis" and profile["assessed_at"] is not None
    assert insight(world, D)["risk_profile"] is None            # a pending analysis has no risk result: nothing is assumed in its place
    with world.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM risk_assessments")).scalar() == 0     # and the pipeline still writes no fabricated row


def test_an_explicit_risk_assessments_row_still_takes_precedence_over_the_analysis(world):
    with world.engine.begin() as conn:
        conn.execute(text("INSERT INTO risk_assessments (customer_id, risk_category, risk_score, confidence, class_probabilities, model_version) VALUES (:id, 'Income', 1, 0.5, '{}', 'test')"),
                     {"id": world.ids[E]})
    try:
        assert insight(world, E)["risk_profile"]["category"] == "Income"
    finally:
        with world.engine.begin() as conn:
            conn.execute(text("DELETE FROM risk_assessments WHERE customer_id = :id"), {"id": world.ids[E]})
    assert insight(world, E)["risk_profile"]["category"] == "Balanced"


def test_a_growth_wish_against_a_conservative_assessment_is_a_conflict_and_never_changes_the_analysis(world):
    before = world.results[C]
    response = insight(world, C, "I want much higher returns and to grow my money fast.")
    assert "growth_seeking" in [c["code"] for c in response["conflicts"]]
    assert response["risk_profile"]["category"] == "Conservative"                                    # the stored assessment stays in force
    assert any(s["kind"] == "risk_assessment" and "Conservative" in s["text"] for s in response["statements"])
    after = world.client.post("/api/analysis", json={"profile_id": world.ids[C]}).json()
    assert after["analysis_id"] == before["analysis_id"] and after["risk"] == before["risk"] and after["status"] == before["status"]      # nothing in the analysis moved


# ------------------------------------------------------------------------------------------ graceful pending state


def test_a_profile_without_a_link_stays_pending_with_nothing_invented(world):
    pending = world.results[D]
    assert pending["status"] == "pending_information"
    assert pending["risk"]["risk_category"] is None and pending["risk"]["unavailable_reason"]
    assert pending["portfolio"] is None and pending["compliance"] is None and pending["recommendation"] is None and pending["explanation"] is None
    assert all(g["feasibility"] is None for g in pending["goals"])         # goals are recorded but not reviewed
    ran = nodes_run(world, D)
    assert G.NODE_INFORMATION_REQUEST in ran and G.NODE_GOAL_ANALYST not in ran and G.NODE_PORTFOLIO_MANAGER not in ran
    insight = world.client.post(f"/api/profiles/{world.ids[D]}/personalized-insights", json={"text": None}).json()
    assert insight["behaviour"]["observation_count"] == 0 and insight["risk_profile"] is None       # no months, no assessment: stated, not defaulted


# ------------------------------------------------------------------------------------------ isolation and consistency of the profile id


def test_every_response_carries_the_profile_it_was_asked_for_and_profiles_do_not_mix(world):
    for key, customer_id in world.ids.items():
        assert world.results[key]["customer_id"] == customer_id
    assert world.results[E]["risk"]["risk_category"] != world.results[A]["risk"]["risk_category"]    # Balanced vs Aggressive: two real, different results
    assert len(set(world.ids.values())) == len(world.ids)
    monthly = {key: world.client.get(f"/api/profiles/{cid}/monthly-financial-records").json() for key, cid in world.ids.items()}
    assert monthly[E]["customer_id"] == world.ids[E] and len(monthly[E]["records"]) == 12
    assert all(len(monthly[key]["records"]) == 0 for key in world.ids if key != E)                       # nobody else was given months
    assert {g["goal_id"] for g in world.results[E]["goals"]}.isdisjoint({g["goal_id"] for g in world.results[A]["goals"]})


# ------------------------------------------------------------------------------------------ idempotency (runs last: it edits one month and restores it)


def test_seeding_again_creates_nothing_and_never_overwrites_a_month_the_user_changed(world):
    counts = lambda: {t: world.engine.connect().execute(text(f"SELECT count(*) FROM {t}")).scalar()  # noqa: E731
                      for t in ("customers", "financial_goals", "monthly_financial_records", "questionnaire_answers", "financial_inputs")}
    before = counts()
    link = world.link
    again = [seed_persona(world.client, p, link_risk_data=link) for p in ALL_DEMO_PERSONAS]
    assert [r["created"] for r in again] == [[]] * len(ALL_DEMO_PERSONAS)
    assert counts() == before and before["customers"] == len(ALL_DEMO_PERSONAS) and before["monthly_financial_records"] == 12

    customer_id, original = world.ids[E], PERSONAS[E]["monthly_records"][-1]
    edit = {"expenses": 61000}
    world.client.put(f"/api/profiles/{customer_id}/monthly-financial-records/{original['period']}", json=edit).raise_for_status()
    try:
        seed_persona(world.client, PERSONAS[E], link_risk_data=link)
        stored = {r["period"]: r for r in world.client.get(f"/api/profiles/{customer_id}/monthly-financial-records").json()["records"]}
        assert stored[original["period"]]["expenses"] == 61000          # the user's own value survived the re-seed
        assert counts() == before
    finally:
        body = {k: v for k, v in original.items() if k != "period"}
        world.client.put(f"/api/profiles/{customer_id}/monthly-financial-records/{original['period']}", json=body).raise_for_status()
