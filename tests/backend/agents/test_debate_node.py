"""`debate_node`: the graph-compatible (state, config) -> dict wrapper,
tested against real AgentState/ComplianceResult objects -- proves Phase 12
integrates cleanly with Phase 10/11 without modifying either."""

from datetime import date

import pytest

from wealthpilot.agents.debate import debate_node
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
    state = apply_delta(state, AgentStateDelta(compliance_result=evaluate_compliance(proposal)))
    return state


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


class _FakeClient:
    def __init__(self, config, **kwargs):
        pass

    def create(self, params):
        class _Msg:
            content = "A concise observation. SUPPORTED"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]
            model = "fake"

        return _Resp()

    def message_retrieval(self, response):
        return [response.choices[0].message.content]

    def cost(self, response):
        return 0.0

    @staticmethod
    def get_usage(response):
        return {}


def test_debate_node_signature_matches_phase10_11_node_contract():
    """(state, config) -> dict -- identical shape to every Phase 10/11
    node wrapper, so a later phase can insert it into agents/graph.py
    with zero adaptation."""
    import inspect

    sig = inspect.signature(debate_node)
    params = list(sig.parameters.keys())
    assert params[0] == "state"
    assert "config" in params


def test_debate_node_requires_an_agent_state_instance():
    with pytest.raises(TypeError):
        debate_node({"not": "an AgentState"})


def test_debate_node_reports_invalid_input_when_no_compliance_result():
    state = AgentState(customer_id=1)  # nothing computed yet
    result = debate_node(state)
    assert "debate_result" in result
    assert result["debate_result"]["status"] == "failed"
    assert "invalid_debate_input" in result["debate_result"]["failure_reason"]


def test_debate_node_reports_invalid_input_when_no_portfolio_weights():
    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(compliance_result=evaluate_compliance(ComplianceProposal())),
    )
    result = debate_node(state)
    assert result["debate_result"]["status"] == "failed"


def test_debate_node_extracts_real_provenance_from_state():
    """Confirms debate_node correctly maps AgentState's REAL Phase 8/9
    fields into DebateInput -- not placeholder/synthetic values."""
    state = _compliant_state()
    # Monkeypatch settings via env isn't needed: we pass no real api_key path
    # here by calling run_strategy_debate indirectly through debate_node,
    # which reads settings.gemini_api_key -- exercised in
    # test_debate_gemini_client.py instead. Here we only check the mapping
    # logic doesn't crash and produces sane structured output shape when
    # the settings-based key is whatever is configured in this environment.
    from wealthpilot.agents import debate as debate_module

    original = debate_module.run_strategy_debate
    captured = {}

    def _spy(debate_input, **kwargs):
        captured["input"] = debate_input
        return original(debate_input, api_key="fake", model_client_cls=_FakeClient)

    debate_module.run_strategy_debate = _spy
    try:
        result = debate_node(state)
    finally:
        debate_module.run_strategy_debate = original

    debate_input = captured["input"]
    assert debate_input.customer_risk_category == "Balanced"
    assert debate_input.approved_strategy.weights == {"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}
    assert debate_input.approved_strategy.model_version == "v1"
    assert debate_input.compliance_status.decision == "PASS"
    assert result["debate_result"]["status"] == "completed"
    assert result["debate_result"]["approved_strategy"]["weights"] == {"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}


def test_debate_node_on_rejected_state_skips_debate_via_compliance_veto():
    state = _rejected_state()
    from wealthpilot.agents import debate as debate_module

    original = debate_module.run_strategy_debate

    def _spy(debate_input, **kwargs):
        return original(debate_input, api_key="fake", model_client_cls=_FakeClient)

    debate_module.run_strategy_debate = _spy
    try:
        result = debate_node(state)
    finally:
        debate_module.run_strategy_debate = original

    assert result["debate_result"]["status"] == "skipped_rejected"
    assert result["debate_result"]["compliance_status"]["decision"] == "REJECT"


def test_debate_node_does_not_mutate_the_input_state():
    state = _compliant_state()
    original_weights = dict(state.portfolio_result.weights)
    original_compliance_decision = state.compliance_result.decision

    from wealthpilot.agents import debate as debate_module

    original = debate_module.run_strategy_debate
    debate_module.run_strategy_debate = lambda debate_input, **kwargs: original(debate_input, api_key="fake", model_client_cls=_FakeClient)
    try:
        debate_node(state)
    finally:
        debate_module.run_strategy_debate = original

    assert state.portfolio_result.weights == original_weights
    assert state.compliance_result.decision == original_compliance_decision
