"""Conditional routing functions tested directly and in isolation --
pure functions of structured state only, deterministic, no DB/LLM/network."""

from wealthpilot.agents.graph import (
    NODE_FAILED,
    NODE_FINANCIAL_HEALTH,
    NODE_GOAL_ANALYST,
    NODE_INFORMATION_REQUEST,
    NODE_PORTFOLIO_MANAGER,
    NODE_REPROFILE,
    NODE_SAVINGS_FIRST,
    route_after_compliance,
    route_after_financial_health,
    route_after_market,
    route_after_risk,
)
from wealthpilot.agents.state import (
    AgentState,
    EmergencyFundResult,
    FinancialHealthResult,
    NodeError,
    RiskAssessmentResult,
)
from wealthpilot.core.compliance import ComplianceProposal, evaluate_compliance


# --- route_after_risk ---------------------------------------------------


def test_route_after_risk_low_confidence_goes_to_information_request():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Income", confidence=0.3, model_version="v1", data_source="models/risk"))
    assert route_after_risk(state) == NODE_INFORMATION_REQUEST


def test_route_after_risk_exactly_at_threshold_proceeds():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Balanced", confidence=0.50, model_version="v1", data_source="models/risk"))
    assert route_after_risk(state) == NODE_FINANCIAL_HEALTH


def test_route_after_risk_just_below_threshold_requests_information():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Balanced", confidence=0.4999, model_version="v1", data_source="models/risk"))
    assert route_after_risk(state) == NODE_INFORMATION_REQUEST


def test_route_after_risk_high_confidence_proceeds():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Aggressive", confidence=0.9, model_version="v1", data_source="models/risk"))
    assert route_after_risk(state) == NODE_FINANCIAL_HEALTH


def test_route_after_risk_none_confidence_goes_to_information_request():
    """None confidence (feature row unavailable) is the extreme case of
    low confidence -- same routing as a numeric value below threshold."""
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(model_version="v1", data_source="models/risk", unavailable_reason="no feature row"))
    assert route_after_risk(state) == NODE_INFORMATION_REQUEST


def test_route_after_risk_missing_risk_assessment_goes_to_information_request():
    state = AgentState(customer_id=1)
    assert route_after_risk(state) == NODE_INFORMATION_REQUEST


def test_route_after_risk_processing_failure_takes_priority():
    state = AgentState(
        customer_id=1,
        risk_assessment=RiskAssessmentResult(risk_category="Balanced", confidence=0.9, model_version="v1", data_source="models/risk"),
        errors=[NodeError(node_name="customer_analyzer", error_type="processing_failure", message="db exploded")],
    )
    assert route_after_risk(state) == NODE_FAILED


# --- route_after_financial_health ----------------------------------------


def test_route_after_financial_health_drift_goes_to_reprofile():
    state = AgentState(customer_id=1, financial_health=FinancialHealthResult(behaviour_drift_flag=True))
    assert route_after_financial_health(state) == NODE_REPROFILE


def test_route_after_financial_health_no_drift_proceeds_to_goal_analyst():
    state = AgentState(customer_id=1, financial_health=FinancialHealthResult(behaviour_drift_flag=False))
    assert route_after_financial_health(state) == NODE_GOAL_ANALYST


def test_route_after_financial_health_unknown_drift_proceeds_to_goal_analyst():
    """drift_flag=None (unavailable, e.g. insufficient history) is NOT
    treated as drift -- there is no evidence of drift, only absence of
    evidence, which is a different thing."""
    state = AgentState(customer_id=1, financial_health=FinancialHealthResult(behaviour_drift_flag=None))
    assert route_after_financial_health(state) == NODE_GOAL_ANALYST


def test_route_after_financial_health_missing_result_proceeds_to_goal_analyst():
    state = AgentState(customer_id=1)
    assert route_after_financial_health(state) == NODE_GOAL_ANALYST


def test_route_after_financial_health_processing_failure_takes_priority():
    state = AgentState(
        customer_id=1,
        financial_health=FinancialHealthResult(behaviour_drift_flag=True),
        errors=[NodeError(node_name="financial_health_analyst", error_type="processing_failure", message="x")],
    )
    assert route_after_financial_health(state) == NODE_FAILED


# --- route_after_market (EF branch) --------------------------------------


def test_route_after_market_sufficient_ef_goes_to_portfolio_manager():
    state = AgentState(customer_id=1, emergency_fund=EmergencyFundResult(sufficient=True))
    assert route_after_market(state) == NODE_PORTFOLIO_MANAGER


def test_route_after_market_insufficient_ef_goes_to_savings_first():
    state = AgentState(customer_id=1, emergency_fund=EmergencyFundResult(sufficient=False))
    assert route_after_market(state) == NODE_SAVINGS_FIRST


def test_route_after_market_unavailable_ef_goes_to_savings_first():
    """Approved 2026-09-14: unknown EF status is treated the same as
    insufficient -- the conservative reading."""
    state = AgentState(customer_id=1, emergency_fund=EmergencyFundResult(sufficient=None))
    assert route_after_market(state) == NODE_SAVINGS_FIRST


def test_route_after_market_missing_result_goes_to_savings_first():
    state = AgentState(customer_id=1)
    assert route_after_market(state) == NODE_SAVINGS_FIRST


def test_route_after_market_processing_failure_takes_priority():
    state = AgentState(
        customer_id=1,
        emergency_fund=EmergencyFundResult(sufficient=True),
        errors=[NodeError(node_name="market_analyst", error_type="processing_failure", message="x")],
    )
    assert route_after_market(state) == NODE_FAILED


# --- route_after_compliance -----------------------------------------


def test_route_after_compliance_pass_routes_to_approved():
    proposal = ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)
    state = AgentState(customer_id=1, compliance_result=evaluate_compliance(proposal))
    assert route_after_compliance(state) == "approved"


def test_route_after_compliance_reject_routes_to_rejected():
    state = AgentState(customer_id=1, compliance_result=evaluate_compliance(ComplianceProposal()))
    assert route_after_compliance(state) == "rejected"


def test_route_after_compliance_warn_routes_to_approved():
    from wealthpilot.core.compliance import RulesConfig

    rules = RulesConfig.model_validate(
        {"version": "test", "rules": [{"id": "r1", "description": "d", "severity": "WARN", "condition": "single_asset_cap", "message": "m"}]}
    )
    proposal = ComplianceProposal(weights={"QQQ": 0.9, "AGG": 0.1})
    state = AgentState(customer_id=1, compliance_result=evaluate_compliance(proposal, rules))
    assert state.compliance_result.decision == "WARN"
    assert route_after_compliance(state) == "approved"


def test_route_after_compliance_missing_result_routes_to_approved_not_a_silent_reject():
    """A missing compliance_result is a graph-construction bug, not a
    REJECT -- there is nothing to reject. This path should never actually
    be reached in a real run (compliance_analyst always sets a result),
    but the function must not crash or misclassify it as a rejection."""
    state = AgentState(customer_id=1)
    assert route_after_compliance(state) == "approved"


def test_route_after_compliance_processing_failure_takes_priority():
    state = AgentState(
        customer_id=1,
        compliance_result=evaluate_compliance(ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)),
        errors=[NodeError(node_name="portfolio_manager", error_type="processing_failure", message="x")],
    )
    assert route_after_compliance(state) == NODE_FAILED


# --- determinism -----------------------------------------------------


def test_all_routing_functions_are_deterministic():
    state = AgentState(
        customer_id=1,
        risk_assessment=RiskAssessmentResult(risk_category="Balanced", confidence=0.8, model_version="v1", data_source="models/risk"),
        financial_health=FinancialHealthResult(behaviour_drift_flag=False),
        emergency_fund=EmergencyFundResult(sufficient=True),
        compliance_result=evaluate_compliance(ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)),
    )
    for _ in range(5):
        assert route_after_risk(state) == NODE_FINANCIAL_HEALTH
        assert route_after_financial_health(state) == NODE_GOAL_ANALYST
        assert route_after_market(state) == NODE_PORTFOLIO_MANAGER
        assert route_after_compliance(state) == "approved"
