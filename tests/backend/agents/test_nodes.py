"""Phase 10 node tests: one node at a time, provenance preservation,
missing-data handling, error handling, no LLM/AutoGen calls, and
regression coverage that Phase 4-9 artifacts/methodology are consumed
unmodified. A handful of tests connect READ-ONLY to the real dev database
(settings.database_url) to verify genuine integration against real Phase
3/4/5/6/8 data/artifacts -- never writing, matching how the training
scripts for those phases already read this same data non-destructively.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from wealthpilot.agents.nodes import (
    compliance_analyst_node,
    customer_analyzer_node,
    engineer_features_for_customer,
    financial_health_node,
    goal_analyst_node,
    information_request_node,
    market_analyst_node,
    portfolio_manager_node,
    reprofile_node,
    risk_analyst_node,
    savings_first_node,
)
from wealthpilot.agents.state import (
    AgentState,
    AgentStateDelta,
    CustomerProfile,
    EmergencyFundResult,
    GoalSummary,
    PortfolioResult,
    RiskAssessmentResult,
    apply_delta,
)
from wealthpilot.config import get_settings
from wealthpilot.core.goals import GoalAssumptions


@pytest.fixture(scope="module")
def real_session():
    """Read-only access to the real dev database -- never writes."""
    from wealthpilot.db.session import get_engine

    settings = get_settings()
    engine = get_engine(settings.database_url)
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="module")
def real_customer_id(real_session):
    from sqlalchemy import text

    row = real_session.execute(text("SELECT id FROM customers WHERE data_source='FAR-Trans' LIMIT 1")).fetchone()
    assert row is not None, "expected at least one FAR-Trans customer in the dev database"
    return row[0]


@pytest.fixture(scope="module")
def real_external_id(real_session, real_customer_id):
    from wealthpilot.db.models import Customer

    customer = real_session.get(Customer, real_customer_id)
    return customer.risk_inputs["external_customer_id"]


# --- Customer Analyzer ----------------------------------------------


def test_customer_analyzer_loads_a_real_customer(real_session, real_customer_id):
    state = AgentState(customer_id=real_customer_id)
    delta = customer_analyzer_node(state, real_session)
    assert delta.customer_profile is not None
    assert delta.customer_profile.customer_id == real_customer_id
    assert delta.customer_profile.data_source == "FAR-Trans"


def test_customer_analyzer_reports_missing_data_for_unknown_customer(real_session):
    state = AgentState(customer_id=99_999_999)
    delta = customer_analyzer_node(state, real_session)
    assert delta.customer_profile is None
    assert len(delta.new_errors) == 1
    assert delta.new_errors[0].error_type == "missing_data"


def test_customer_analyzer_does_not_duplicate_the_full_db_row():
    """CustomerProfile should be a lean projection, not the raw ORM object."""
    fields = set(CustomerProfile.model_fields.keys())
    assert "risk_inputs" not in fields  # internal DB-only field, not surfaced


# --- Risk Analyst -----------------------------------------------------


def test_engineer_features_for_customer_returns_a_real_feature_row(real_external_id):
    features = engineer_features_for_customer(real_external_id)
    assert features is not None
    from wealthpilot.data.preprocessing import ALL_FEATURES

    assert set(features.keys()) == set(ALL_FEATURES)


def test_engineer_features_for_customer_returns_none_for_unknown_id():
    assert engineer_features_for_customer("NOT_A_REAL_CUSTOMER_ID") is None


def test_risk_analyst_node_on_a_real_customer_produces_a_genuine_risk_level(real_external_id):
    feature_row = engineer_features_for_customer(real_external_id)
    state = AgentState(customer_id=1)
    delta = risk_analyst_node(state, feature_row)
    assert delta.risk_assessment.unavailable_reason is None
    from wealthpilot.data.preprocessing import GENUINE_RISK_LEVELS

    assert delta.risk_assessment.risk_category in GENUINE_RISK_LEVELS
    assert 0.0 <= delta.risk_assessment.confidence <= 1.0
    assert delta.risk_assessment.model_version == "v1"
    assert delta.risk_assessment.data_source == "models/risk"


def test_risk_analyst_node_reports_unavailable_when_feature_row_is_none():
    state = AgentState(customer_id=1)
    delta = risk_analyst_node(state, None)
    assert delta.risk_assessment.risk_category is None
    assert delta.risk_assessment.unavailable_reason is not None
    # provenance is still recorded even when the result is unavailable
    assert delta.risk_assessment.model_version == "v1"


def test_risk_analyst_node_reports_validation_error_for_incomplete_feature_row():
    state = AgentState(customer_id=1)
    delta = risk_analyst_node(state, {"pct_value_stock": 0.5})  # missing most required columns
    assert delta.risk_assessment.unavailable_reason is not None
    assert len(delta.new_errors) == 1
    assert delta.new_errors[0].error_type == "validation"


def test_risk_analyst_node_never_produces_predicted_or_not_available_label(real_external_id):
    feature_row = engineer_features_for_customer(real_external_id)
    state = AgentState(customer_id=1)
    delta = risk_analyst_node(state, feature_row)
    assert delta.risk_assessment.risk_category not in ("Predicted_Conservative", "Predicted_Income", "Predicted_Balanced", "Predicted_Aggressive", "Not_Available")


def test_reprofile_node_reuses_risk_analyst_node_not_a_second_implementation(real_external_id):
    feature_row = engineer_features_for_customer(real_external_id)
    state = AgentState(customer_id=1)
    direct = risk_analyst_node(state, feature_row)
    reprofiled = reprofile_node(state, feature_row)
    assert direct.risk_assessment.risk_category == reprofiled.risk_assessment.risk_category
    # RandomForest's n_jobs=-1 parallel aggregation has ~1e-16 float
    # non-determinism across separate .predict_proba() calls (same known
    # cause as Phase 4's own determinism test) -- approx, not exact.
    assert direct.risk_assessment.confidence == pytest.approx(reprofiled.risk_assessment.confidence, abs=1e-9)


# --- Information Request ----------------------------------------------


def test_information_request_node_requires_a_risk_assessment():
    state = AgentState(customer_id=1)
    delta = information_request_node(state)
    assert len(delta.new_errors) == 1
    assert delta.new_errors[0].error_type == "missing_data"


def test_information_request_node_produces_structured_follow_up():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Income", confidence=0.3, model_version="v1", data_source="models/risk"))
    delta = information_request_node(state)
    assert len(delta.new_errors) == 1
    assert "?" in delta.new_errors[0].message  # contains an actual question


# --- Financial Health ---------------------------------------------------


def test_financial_health_node_always_marks_expense_persona_unavailable(real_external_id):
    delta = financial_health_node(AgentState(customer_id=1), real_external_id)
    assert delta.financial_health.expense_persona is None
    assert delta.financial_health.expense_persona_unavailable_reason is not None
    assert "Kaggle" in delta.financial_health.expense_persona_unavailable_reason


def test_financial_health_node_never_fabricates_savings_rate_or_expense_ratio(real_external_id):
    delta = financial_health_node(AgentState(customer_id=1), real_external_id)
    assert delta.financial_health.savings_rate is None
    assert delta.financial_health.expense_ratio is None


def test_financial_health_node_reports_unavailable_for_none_external_id():
    delta = financial_health_node(AgentState(customer_id=1), None)
    assert delta.financial_health.unavailable_reason is not None


def test_financial_health_node_reports_unavailable_for_unknown_customer():
    delta = financial_health_node(AgentState(customer_id=1), "NOT_A_REAL_ID")
    assert delta.financial_health.unavailable_reason is not None
    assert "no transaction history" in delta.financial_health.unavailable_reason


def test_financial_health_node_provenance_is_always_recorded(real_external_id):
    delta = financial_health_node(AgentState(customer_id=1), real_external_id)
    assert delta.financial_health.model_version == "v1"
    assert delta.financial_health.data_source == "models/behaviour"


# --- Goal Analyst -----------------------------------------------------


def _state_with_one_goal():
    profile = CustomerProfile(
        customer_id=1, name="Test", data_source="FAR-Trans",
        goals=[GoalSummary(id=1, goal_type="House Purchase", target_amount=5_000_000, current_savings=1_000_000, target_date=date(2031, 9, 14), priority=1)],
    )
    return apply_delta(AgentState(customer_id=1), AgentStateDelta(customer_profile=profile))


def test_goal_analyst_node_requires_customer_profile():
    delta = goal_analyst_node(AgentState(customer_id=1), assumptions=None, current_date=date(2026, 9, 14))
    assert len(delta.new_errors) == 1
    assert delta.new_errors[0].error_type == "missing_data"


def test_goal_analyst_node_reports_unavailable_without_assumptions():
    state = _state_with_one_goal()
    delta = goal_analyst_node(state, assumptions=None, current_date=date(2026, 9, 14))
    assert delta.goal_results[0].unavailable_reason is not None
    assert delta.goal_results[0].required_periodic_contribution is None


def test_goal_analyst_node_computes_required_contribution_with_assumptions():
    state = _state_with_one_goal()
    assumptions = GoalAssumptions(contribution_amount=35_000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    delta = goal_analyst_node(state, assumptions=assumptions, current_date=date(2026, 9, 14))
    result = delta.goal_results[0]
    assert result.unavailable_reason is None
    assert result.required_periodic_contribution > 0
    assert result.inflation_adjusted_target_amount > result.nominal_target_amount


def test_goal_analyst_node_runs_monte_carlo_when_historical_returns_supplied():
    state = _state_with_one_goal()
    assumptions = GoalAssumptions(contribution_amount=35_000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    hist = np.random.default_rng(42).normal(0.0005, 0.01, 500)
    delta = goal_analyst_node(state, assumptions=assumptions, current_date=date(2026, 9, 14), historical_returns=hist)
    result = delta.goal_results[0]
    assert result.monte_carlo_success_probability is not None
    assert 0.0 <= result.monte_carlo_success_probability <= 1.0
    assert result.feasibility in ("Feasible", "At Risk", "Not Feasible")


def test_goal_analyst_node_omits_monte_carlo_without_historical_returns():
    state = _state_with_one_goal()
    assumptions = GoalAssumptions(contribution_amount=35_000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    delta = goal_analyst_node(state, assumptions=assumptions, current_date=date(2026, 9, 14))
    assert delta.goal_results[0].monte_carlo_success_probability is None
    assert delta.goal_results[0].feasibility is None


def test_goal_analyst_node_emergency_fund_unavailable_without_inputs():
    state = _state_with_one_goal()
    delta = goal_analyst_node(state, assumptions=None, current_date=date(2026, 9, 14))
    assert delta.emergency_fund.unavailable_reason is not None
    assert delta.emergency_fund.sufficient is None


def test_goal_analyst_node_computes_emergency_fund_with_inputs():
    state = _state_with_one_goal()
    delta = goal_analyst_node(
        state, assumptions=None, current_date=date(2026, 9, 14),
        monthly_essential_expenses=30_000, current_liquid_assets=90_000,
    )
    assert delta.emergency_fund.sufficient is False
    assert delta.emergency_fund.shortfall == pytest.approx(90_000)
    assert delta.emergency_fund.savings_first_required is True


def test_goal_analyst_node_does_not_duplicate_tvm_math():
    """The node's required_periodic_contribution must EXACTLY match a
    direct call to Phase 7's own analyze_goal_funding -- proving the node
    is a thin wrapper, not a re-derivation."""
    from wealthpilot.core.goals import GoalInput, analyze_goal_funding

    state = _state_with_one_goal()
    assumptions = GoalAssumptions(contribution_amount=35_000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    delta = goal_analyst_node(state, assumptions=assumptions, current_date=date(2026, 9, 14))

    goal_input = GoalInput(customer_id=1, goal_type="House Purchase", target_amount=5_000_000, current_savings=1_000_000, target_date=date(2031, 9, 14))
    direct = analyze_goal_funding(goal_input, assumptions, date(2026, 9, 14))
    assert delta.goal_results[0].required_periodic_contribution == pytest.approx(direct.required_periodic_contribution)


# --- Market Analyst -----------------------------------------------------


def test_market_analyst_node_reads_real_metrics_json():
    delta = market_analyst_node(AgentState(customer_id=1))
    assert delta.market_analysis.unavailable_reason is None
    tickers = {i.ticker for i in delta.market_analysis.instruments}
    assert tickers == {"^IXIC", "^NDX", "QQQ", "AGG", "GLD"}
    assert delta.market_analysis.model_version == "v1"
    assert all(i.latest_regime in ("Range-bound", "Trending", "Volatile") for i in delta.market_analysis.instruments)


def test_market_analyst_node_does_not_introduce_a_new_forecast():
    """The node's regime values must match metrics.json EXACTLY -- no
    recomputation, no adjustment."""
    import json
    from wealthpilot.agents.nodes import METRICS_PATH

    delta = market_analyst_node(AgentState(customer_id=1))
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    for instrument in delta.market_analysis.instruments:
        expected = metrics["market"]["results_by_instrument"][instrument.ticker]["latest_regime"]
        assert instrument.latest_regime == expected


# --- Portfolio Manager / Savings-first --------------------------------


def test_portfolio_manager_node_mvo_requires_risk_category(real_session):
    state = AgentState(customer_id=1)  # no risk_assessment
    delta = portfolio_manager_node(state, real_session, strategy="mvo")
    assert delta.portfolio_result.unavailable_reason is not None


def test_portfolio_manager_node_mvo_produces_valid_weights(real_session):
    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk")),
    )
    delta = portfolio_manager_node(state, real_session, strategy="mvo")
    result = delta.portfolio_result
    assert result.unavailable_reason is None
    assert sum(result.weights.values()) == pytest.approx(1.0, abs=1e-6)
    lower, upper = result.constraints["risk_level_qqq_band"]
    assert lower - 1e-6 <= result.weights["QQQ"] <= min(upper, result.constraints["general_single_asset_cap"]) + 1e-6


def test_portfolio_manager_node_equal_weight_ignores_risk_level(real_session):
    delta = portfolio_manager_node(AgentState(customer_id=1), real_session, strategy="equal_weight")
    weights = delta.portfolio_result.weights
    assert weights["QQQ"] == pytest.approx(1 / 3)


def test_portfolio_manager_node_hrp(real_session):
    delta = portfolio_manager_node(AgentState(customer_id=1), real_session, strategy="hrp")
    assert delta.portfolio_result.unavailable_reason is None
    assert sum(delta.portfolio_result.weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_portfolio_manager_node_uses_approved_phase_8_bounds_not_a_second_system(real_session):
    """The node's QQQ band for a risk level must exactly equal Phase 8's
    own RISK_LEVEL_QQQ_BANDS constant -- no re-derivation."""
    from wealthpilot.core.optimizer import RISK_LEVEL_QQQ_BANDS

    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(risk_assessment=RiskAssessmentResult(risk_category="Aggressive", model_version="v1", data_source="models/risk")),
    )
    delta = portfolio_manager_node(state, real_session, strategy="mvo")
    assert delta.portfolio_result.constraints["risk_level_qqq_band"] == list(RISK_LEVEL_QQQ_BANDS["Aggressive"])


def test_savings_first_node_requires_emergency_fund_status():
    delta = savings_first_node(AgentState(customer_id=1))
    assert len(delta.new_errors) == 1


def test_savings_first_node_produces_no_weights():
    state = apply_delta(AgentState(customer_id=1), AgentStateDelta(emergency_fund=EmergencyFundResult(sufficient=False, shortfall=50_000)))
    delta = savings_first_node(state)
    assert delta.portfolio_result.weights is None
    assert delta.portfolio_result.strategy == "savings_first"


def test_compliance_never_modifies_portfolio_weights(real_session):
    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(
            risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk"),
            emergency_fund=EmergencyFundResult(sufficient=True),
        ),
    )
    port_delta = portfolio_manager_node(state, real_session, strategy="mvo")
    state = apply_delta(state, port_delta)
    original_weights = dict(state.portfolio_result.weights)

    comp_delta = compliance_analyst_node(state)
    state = apply_delta(state, comp_delta)
    assert state.portfolio_result.weights == original_weights


# --- Compliance Analyst -------------------------------------------------


def test_compliance_analyst_node_calls_the_real_phase_9_engine():
    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(
            risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk"),
            portfolio_result=PortfolioResult(strategy="mvo", risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, asset_universe=["QQQ", "AGG", "GLD"], config_version="v1", data_source="x"),
            emergency_fund=EmergencyFundResult(sufficient=True),
        ),
    )
    delta = compliance_analyst_node(state)
    assert delta.compliance_result.decision == "PASS"
    assert delta.compliance_result.rules_version == "v1"


def test_compliance_analyst_node_rejects_when_qqq_out_of_band():
    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(
            risk_assessment=RiskAssessmentResult(risk_category="Conservative", model_version="v1", data_source="models/risk"),
            portfolio_result=PortfolioResult(strategy="mvo", risk_level="Conservative", weights={"QQQ": 0.9, "AGG": 0.05, "GLD": 0.05}, asset_universe=["QQQ", "AGG", "GLD"], config_version="v1", data_source="x"),
            emergency_fund=EmergencyFundResult(sufficient=True),
        ),
    )
    delta = compliance_analyst_node(state)
    assert delta.compliance_result.decision == "REJECT"


def test_compliance_analyst_node_passes_savings_first_flag_through():
    state = apply_delta(AgentState(customer_id=1), AgentStateDelta(emergency_fund=EmergencyFundResult(sufficient=False)))
    delta = compliance_analyst_node(state, is_savings_first_recommendation=True)
    ef_rule = next(rr for rr in delta.compliance_result.rule_results if rr.rule_id == "emergency_fund_savings_first")
    assert ef_rule.passed  # insufficient EF but flagged as a savings-first recommendation -> compliant


# --- no LLM / no AutoGen -----------------------------------------------


def test_no_node_module_imports_an_llm_or_autogen_library():
    """Checks actual import statements only -- the module's own docstring
    legitimately mentions these names in prose (explaining that none of
    them are called), so a bare substring search would false-positive on
    that explanation."""
    import ast

    import wealthpilot.agents.nodes as nodes_module

    source = open(nodes_module.__file__, encoding="utf-8").read()
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    forbidden_roots = {"google", "openai", "anthropic", "autogen", "langgraph"}
    overlap = imported_roots & forbidden_roots
    assert not overlap, f"nodes.py imports forbidden module(s): {overlap} (Phase 10 has no LLM/AutoGen/LangGraph)"
