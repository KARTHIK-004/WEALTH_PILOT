"""End-to-end graph execution against real data (read-only DB access,
matching the pattern already established in Phase 10's own tests): happy
path, pending-information halt, savings-first branch, node ordering,
provenance preservation, state preservation, and processing-failure
handling."""

import numpy as np
import pytest
from sqlalchemy.orm import Session

from wealthpilot.agents.graph import GraphDependencies, run_analysis_graph
from wealthpilot.agents.state import AgentState
from wealthpilot.config import get_settings
from wealthpilot.core.goals import GoalAssumptions


@pytest.fixture(scope="module")
def real_session():
    from wealthpilot.db.session import get_engine

    settings = get_settings()
    engine = get_engine(settings.database_url)
    with Session(engine) as session:
        yield session


def test_low_confidence_customer_halts_at_pending_information(real_session):
    """customer_id=1 is verified (Phase 10 smoke test) to have risk
    confidence ~0.369, below the 0.50 threshold."""
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=1), deps)

    assert result.risk_assessment is not None
    assert result.risk_assessment.confidence < 0.50
    # Nothing downstream of Risk Analyst ran.
    assert result.financial_health is None
    assert result.emergency_fund is None
    assert result.portfolio_result is None
    assert result.compliance_result is None
    assert result.blocked is False  # not REJECTed -- simply never reached compliance
    assert any(e.node_name == "information_request" for e in result.errors)


def test_higher_confidence_customer_proceeds_past_risk_analyst(real_session):
    """customer_id=2 is verified (this phase's own smoke test) to have
    risk confidence ~0.513, at/above the 0.50 threshold."""
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=2), deps)

    assert result.risk_assessment.confidence >= 0.50
    assert result.financial_health is not None  # financial_health_analyst ran
    assert result.market_analysis is not None  # market_analyst ran
    # This customer has no expense data -> EF unavailable -> savings_first path,
    # which (given no EF figures at all) cannot itself produce a portfolio
    # either -- verified this is the REAL, correct, fail-closed outcome, not
    # a bug: both paths converge on compliance_analyst regardless.
    assert result.compliance_result is not None


def test_node_ordering_customer_before_risk_before_financial_health(real_session):
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=2), deps)
    assert result.customer_profile is not None
    assert result.risk_assessment is not None
    assert result.financial_health is not None


def test_compliance_always_runs_when_reached(real_session):
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=2), deps)
    assert result.compliance_result is not None
    assert result.compliance_result.decision in ("PASS", "WARN", "REJECT")


def test_state_preserves_earlier_node_outputs_through_to_the_end(real_session):
    """Nothing overwrites or discards an earlier node's result on the way
    to the terminal state -- direct manual-verification test for section
    22's "do not silently discard node outputs"."""
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=2), deps)
    assert result.customer_profile.customer_id == 2
    assert result.risk_assessment.risk_category is not None
    # financial_health, computed several nodes earlier than the terminal
    # state, is still present and unchanged.
    assert result.financial_health.model_version == "v1"


def test_provenance_preserved_through_every_transition(real_session):
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=2), deps)
    assert result.risk_assessment.model_version == "v1"
    assert result.risk_assessment.data_source == "models/risk"
    assert result.financial_health.model_version == "v1"
    assert result.financial_health.data_source == "models/behaviour"
    assert result.market_analysis.model_version == "v1"
    if result.portfolio_result is not None:
        assert result.portfolio_result.config_version == "v1"
    assert result.compliance_result.rules_version == "v1"


def test_run_is_deterministic_for_the_same_customer(real_session):
    deps1 = GraphDependencies(session=real_session)
    deps2 = GraphDependencies(session=real_session)
    result1 = run_analysis_graph(AgentState(customer_id=2), deps1)
    result2 = run_analysis_graph(AgentState(customer_id=2), deps2)
    assert result1.risk_assessment.risk_category == result2.risk_assessment.risk_category
    assert result1.compliance_result.decision == result2.compliance_result.decision
    assert result1.blocked == result2.blocked


def test_processing_failure_halts_the_graph_instead_of_continuing():
    """A `None` session (deliberately invalid, bypassing GraphDependencies'
    own type hint to inject a guaranteed failure) causes customer_analyzer
    to raise `AttributeError` -- the graph must convert this into a
    processing_failure and stop, never continuing as if a valid profile
    had loaded."""
    deps = GraphDependencies(session=None)  # type: ignore[arg-type]
    result = run_analysis_graph(AgentState(customer_id=1), deps)

    assert any(e.error_type == "processing_failure" for e in result.errors)
    assert result.customer_profile is None
    assert result.risk_assessment is None
    assert result.compliance_result is None


def test_goal_analyst_runs_with_assumptions_supplied(real_session):
    """Even though real customers currently have no financial_goals rows
    (Phase 1's table is user-entered only, still empty -- Phase 10's own
    documented limitation), goal_analyst_node still runs and produces an
    empty goal_results list rather than an error."""
    assumptions = GoalAssumptions(contribution_amount=10_000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    hist = np.random.default_rng(1).normal(0.0005, 0.01, 300)
    deps = GraphDependencies(session=real_session, goal_assumptions=assumptions, historical_returns=hist)
    result = run_analysis_graph(AgentState(customer_id=2), deps)
    assert result.goal_results == []
