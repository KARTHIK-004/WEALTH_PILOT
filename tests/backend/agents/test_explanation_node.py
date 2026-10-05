"""`explanation_node`: the graph-compatible (state, config) -> dict
wrapper, tested against real AgentState/ComplianceResult objects."""

import inspect

import pytest

from wealthpilot.agents.explanation import ExplanationOutput, explanation_node
from wealthpilot.agents.state import AgentState, AgentStateDelta, EmergencyFundResult, PortfolioResult, RiskAssessmentResult, apply_delta
from wealthpilot.core.compliance import ComplianceProposal, evaluate_compliance


def _compliant_state() -> AgentState:
    state = AgentState(customer_id=1)
    state = apply_delta(
        state,
        AgentStateDelta(
            risk_assessment=RiskAssessmentResult(risk_category="Balanced", confidence=0.8, model_version="v1", data_source="models/risk"),
            emergency_fund=EmergencyFundResult(sufficient=True),
            portfolio_result=PortfolioResult(
                strategy="mvo", risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3},
                asset_universe=["QQQ", "AGG", "GLD"], expected_return=0.15, expected_volatility=0.18, sharpe_ratio=0.83,
                config_version="v1", data_source="market_data (PostgreSQL)",
            ),
        ),
    )
    proposal = ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)
    return apply_delta(state, AgentStateDelta(compliance_result=evaluate_compliance(proposal)))


def _rejected_state() -> AgentState:
    state = AgentState(customer_id=1)
    state = apply_delta(
        state,
        AgentStateDelta(
            risk_assessment=RiskAssessmentResult(risk_category="Conservative", confidence=0.9, model_version="v1", data_source="models/risk"),
            emergency_fund=EmergencyFundResult(sufficient=True),
            portfolio_result=PortfolioResult(
                strategy="mvo", risk_level="Conservative", weights={"QQQ": 0.9, "AGG": 0.05, "GLD": 0.05},
                asset_universe=["QQQ", "AGG", "GLD"], config_version="v1", data_source="market_data (PostgreSQL)",
            ),
        ),
    )
    proposal = ComplianceProposal(risk_level="Conservative", weights={"QQQ": 0.9, "AGG": 0.05, "GLD": 0.05}, emergency_fund_sufficient=True)
    state = apply_delta(state, AgentStateDelta(compliance_result=evaluate_compliance(proposal)))
    assert state.compliance_result.decision == "REJECT"
    return state


def _fake_call_fn(output: ExplanationOutput):
    def _call(prompt, api_key, model, temperature, max_output_tokens, timeout_seconds):
        return output

    return _call


def _valid_output(**overrides) -> ExplanationOutput:
    defaults = dict(
        summary="Summary.", risk_explanation="Balanced risk category.", financial_health_explanation="Limited data.",
        goal_explanation="No goals.", portfolio_explanation="40% QQQ, 30% AGG, 30% GLD.", market_explanation="No market data.",
        compliance_explanation="Passed.", limitations="None noted.", disclaimer="placeholder",
    )
    defaults.update(overrides)
    return ExplanationOutput(**defaults)


def test_explanation_node_signature_matches_phase10_11_12_node_contract():
    sig = inspect.signature(explanation_node)
    params = list(sig.parameters.keys())
    assert params[0] == "state"
    assert "config" in params


def test_explanation_node_requires_an_agent_state_instance():
    with pytest.raises(TypeError):
        explanation_node({"not": "an AgentState"})


def test_explanation_node_reports_invalid_input_without_compliance_result():
    state = AgentState(customer_id=1)
    result = explanation_node(state)
    assert result["explanation_result"]["status"] == "failed"
    assert "invalid_explanation_input" in result["explanation_result"]["failure_reason"]


def test_explanation_node_on_rejected_state_skips_via_compliance_veto():
    state = _rejected_state()
    from wealthpilot.agents import explanation as explanation_module

    original = explanation_module.run_explanation

    def _spy(explanation_input, **kwargs):
        return original(explanation_input, api_key="fake", call_fn=_fake_call_fn(_valid_output()))

    explanation_module.run_explanation = _spy
    try:
        result = explanation_node(state)
    finally:
        explanation_module.run_explanation = original

    assert result["explanation_result"]["status"] == "skipped_rejected"
    assert result["explanation_result"]["compliance_decision"] == "REJECT"


def test_explanation_node_extracts_real_provenance_from_state():
    state = _compliant_state()
    from wealthpilot.agents import explanation as explanation_module

    original = explanation_module.run_explanation
    captured = {}

    def _spy(explanation_input, **kwargs):
        captured["input"] = explanation_input
        return original(explanation_input, api_key="fake", call_fn=_fake_call_fn(_valid_output()))

    explanation_module.run_explanation = _spy
    try:
        result = explanation_node(state)
    finally:
        explanation_module.run_explanation = original

    ei = captured["input"]
    assert ei.risk.risk_category == "Balanced"
    assert ei.portfolio.weights == {"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}
    assert ei.compliance.decision == "PASS"
    assert result["explanation_result"]["status"] == "completed"


def test_explanation_node_does_not_mutate_the_input_state():
    state = _compliant_state()
    original_weights = dict(state.portfolio_result.weights)
    original_decision = state.compliance_result.decision

    from wealthpilot.agents import explanation as explanation_module

    original = explanation_module.run_explanation
    explanation_module.run_explanation = lambda explanation_input, **kwargs: original(
        explanation_input, api_key="fake", call_fn=_fake_call_fn(_valid_output())
    )
    try:
        explanation_node(state)
    finally:
        explanation_module.run_explanation = original

    assert state.portfolio_result.weights == original_weights
    assert state.compliance_result.decision == original_decision
