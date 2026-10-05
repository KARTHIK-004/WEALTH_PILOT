"""THE most important Phase 10 test (section 25): an explicit end-to-end
safety-contract test proving a compliance REJECT blocks downstream
execution. No LangGraph is built to test this -- a small, testable gate
function stands in for what Phase 11 will eventually wire into the real
graph, exactly as section 25 asks for.
"""

import pytest
from sqlalchemy.orm import Session

from wealthpilot.agents.nodes import compliance_analyst_node, portfolio_manager_node
from wealthpilot.agents.state import AgentState, AgentStateDelta, EmergencyFundResult, RiskAssessmentResult, apply_delta
from wealthpilot.config import get_settings
from wealthpilot.core.compliance import ComplianceRejectedError, enforce_gate


@pytest.fixture(scope="module")
def real_session():
    from wealthpilot.db.session import get_engine

    settings = get_settings()
    engine = get_engine(settings.database_url)
    with Session(engine) as session:
        yield session


def _run_pipeline_through_compliance(real_session, risk_level: str, weights: dict, ef_sufficient: bool) -> AgentState:
    """Minimal stand-in for a future LangGraph run: Portfolio Manager then
    Compliance Analyst, exactly the sequence BUILD_PLAN.md's flow diagram
    specifies immediately before the (not-yet-built) explanation step."""
    state = AgentState(customer_id=1)
    state = apply_delta(
        state,
        AgentStateDelta(
            risk_assessment=RiskAssessmentResult(risk_category=risk_level, model_version="v1", data_source="models/risk"),
            emergency_fund=EmergencyFundResult(sufficient=ef_sufficient),
        ),
    )
    # Force specific weights (bypassing the optimizer) so the test controls
    # exactly what compliance sees, rather than depending on whatever MVO
    # happens to produce for real market data today.
    from wealthpilot.agents.state import PortfolioResult

    state = apply_delta(
        state,
        AgentStateDelta(
            portfolio_result=PortfolioResult(
                strategy="mvo", risk_level=risk_level, weights=weights, asset_universe=list(weights),
                config_version="v1", data_source="market_data (PostgreSQL)",
            )
        ),
    )
    comp_delta = compliance_analyst_node(state)
    return apply_delta(state, comp_delta)


def _downstream_explanation_stub(state: AgentState) -> str:
    """Stand-in for the future Gemini Explanation node (Phase 13) and the
    Recommendation Engine (Phase 14) -- both explicitly out of scope here.
    The ONLY thing that matters for this test is: does execution reach
    this function's body when it must not?"""
    enforce_gate(state.compliance_result)  # <-- the binding gate
    return f"[not a real explanation] recommendation prepared, decision={state.compliance_result.decision}"


# --- the critical safety contract --------------------------------------


def test_reject_blocks_the_downstream_explanation_step(real_session):
    # Conservative risk level with a 90% QQQ weight -- far outside the
    # approved 10-30% band -- must REJECT.
    state = _run_pipeline_through_compliance(
        real_session, risk_level="Conservative", weights={"QQQ": 0.90, "AGG": 0.05, "GLD": 0.05}, ef_sufficient=True
    )
    assert state.compliance_result.decision == "REJECT"
    assert state.blocked is True

    with pytest.raises(ComplianceRejectedError):
        _downstream_explanation_stub(state)


def test_pass_allows_the_downstream_explanation_step(real_session):
    state = _run_pipeline_through_compliance(
        real_session, risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, ef_sufficient=True
    )
    assert state.compliance_result.decision == "PASS"
    assert state.blocked is False

    explanation = _downstream_explanation_stub(state)
    assert "PASS" in explanation


def test_reject_state_cannot_be_treated_as_pass_by_reading_blocked_alone(real_session):
    """Even a caller that (incorrectly) tries to gate on state.blocked
    directly instead of calling enforce_gate must see the correct value --
    blocked is never left stale or defaulted to False on a REJECT."""
    state = _run_pipeline_through_compliance(
        real_session, risk_level="Conservative", weights={"QQQ": -0.1, "AGG": 0.6, "GLD": 0.5}, ef_sufficient=True
    )
    assert state.compliance_result.decision == "REJECT"
    assert state.blocked is True
    assert state.block_reason is not None and len(state.block_reason) > 0


def test_emergency_fund_insufficient_without_savings_first_flag_rejects(real_session):
    """The exact PROJECT_PLAN.md/MASTER_PROMPT.md scenario: EF insufficient
    but a NORMAL allocation proposed -- must REJECT and block downstream."""
    state = _run_pipeline_through_compliance(
        real_session, risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, ef_sufficient=False
    )
    assert state.compliance_result.decision == "REJECT"
    with pytest.raises(ComplianceRejectedError):
        _downstream_explanation_stub(state)


def test_a_caller_who_forgets_to_check_the_decision_still_cannot_bypass_reject(real_session):
    """The core structural guarantee: even a caller that calls
    _downstream_explanation_stub() WITHOUT first inspecting
    state.compliance_result.decision at all still gets blocked, because
    enforce_gate() is embedded in the stub itself, not left to caller
    discipline."""
    state = _run_pipeline_through_compliance(
        real_session, risk_level="Aggressive", weights={"QQQ": 0.95, "AGG": 0.05, "GLD": 0.0}, ef_sufficient=True
    )
    # Deliberately do NOT check state.compliance_result.decision here.
    reached_body = False
    with pytest.raises(ComplianceRejectedError):
        result = _downstream_explanation_stub(state)
        reached_body = True  # pragma: no cover -- must never execute
    assert reached_body is False


def test_real_portfolio_manager_output_still_gets_correctly_gated(real_session):
    """End-to-end with the REAL Portfolio Manager node output (not
    hand-constructed weights) -- proves the whole chain, not just the
    compliance engine in isolation."""
    state = AgentState(customer_id=1)
    state = apply_delta(
        state,
        AgentStateDelta(
            risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk"),
            emergency_fund=EmergencyFundResult(sufficient=True),
        ),
    )
    port_delta = portfolio_manager_node(state, real_session, strategy="mvo")
    state = apply_delta(state, port_delta)
    assert state.portfolio_result.unavailable_reason is None

    comp_delta = compliance_analyst_node(state)
    state = apply_delta(state, comp_delta)

    # A real Phase 8 MVO result for Balanced must satisfy Phase 8's own
    # bounds by construction, so this must PASS and reach downstream.
    assert state.compliance_result.decision == "PASS"
    explanation = _downstream_explanation_stub(state)
    assert "PASS" in explanation
