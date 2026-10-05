"""Phase 28 — end-to-end verification that supplying real emergency-fund/
GoalAssumptions inputs through `GraphDependencies` unlocks the
previously-documented-unreachable states, using the exact same
real-data pattern `test_graph_execution.py` already established
(customer_id=2, a genuine FAR-Trans customer with risk confidence ~0.51).

Every assertion here was verified empirically against the real, running
pipeline before being written (never assumed) — see
`reports/phase28_financial_input_savings_first_report.md` for the full
before/after trace.
"""

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


def test_sufficient_emergency_fund_routes_to_portfolio_manager(real_session):
    """A real, sufficient emergency fund routes to the MVO optimizer (not
    savings-first) and produces real, non-null portfolio weights -- the
    `route_after_market` branch this project always had but nothing ever
    exercised live before Phase 28 supplied real inputs."""
    deps = GraphDependencies(
        session=real_session, monthly_essential_expenses=1000.0, current_liquid_assets=50_000.0
    )
    result = run_analysis_graph(AgentState(customer_id=2), deps)

    assert result.emergency_fund is not None
    assert result.emergency_fund.sufficient is True
    assert result.portfolio_result is not None
    assert result.portfolio_result.strategy == "mvo"
    assert result.portfolio_result.weights is not None
    assert abs(sum(result.portfolio_result.weights.values()) - 1.0) < 1e-6


def test_insufficient_known_emergency_fund_produces_valid_savings_first_result(real_session):
    """A KNOWN insufficient emergency fund still produces a valid,
    non-error savings-first `PortfolioResult` -- never an error, and never
    fabricated weights."""
    deps = GraphDependencies(
        session=real_session, monthly_essential_expenses=5000.0, current_liquid_assets=1000.0
    )
    result = run_analysis_graph(AgentState(customer_id=2), deps)

    assert result.emergency_fund.sufficient is False
    assert result.portfolio_result is not None
    assert result.portfolio_result.strategy == "savings_first"
    assert result.portfolio_result.weights is None
    assert not any(e.node_name == "savings_first" for e in result.errors)
    assert "shortfall" in (result.portfolio_result.unavailable_reason or "")


def test_unknown_emergency_fund_no_longer_errors_savings_first_node(real_session):
    """Phase 28 fix: no financial inputs supplied at all -- `sufficient`
    stays `None` (never fabricated), and `savings_first_node` now produces
    a valid result instead of a `missing_data` NodeError, matching
    `route_after_market`'s own already-approved "treat None like False"
    routing intent."""
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=2), deps)

    assert result.emergency_fund.sufficient is None
    assert result.portfolio_result is not None
    assert result.portfolio_result.strategy == "savings_first"
    assert not any(e.node_name == "savings_first" and e.error_type == "missing_data" for e in result.errors)


def test_sufficient_emergency_fund_reaches_pass_with_real_weights(real_session):
    """The real, live 'approved' path -- verified, not assumed. Every
    weight-validation rule passes because the real MVO weights genuinely
    satisfy them (never because the rule was skipped)."""
    assumptions = GoalAssumptions(contribution_amount=500, annual_return_rate=0.07, annual_inflation_rate=0.03)
    hist = np.random.default_rng(42).normal(0.0006, 0.01, 300)
    deps = GraphDependencies(
        session=real_session,
        goal_assumptions=assumptions,
        historical_returns=hist,
        monthly_essential_expenses=1000.0,
        current_liquid_assets=50_000.0,
    )
    result = run_analysis_graph(AgentState(customer_id=2), deps)

    assert result.emergency_fund.sufficient is True
    assert result.portfolio_result.weights is not None
    assert result.compliance_result is not None
    assert result.compliance_result.decision == "PASS"
    assert result.blocked is False
    triggered = {r.rule_id for r in result.compliance_result.rule_results if r.triggered}
    assert triggered == set()


def test_insufficient_emergency_fund_reaches_pass_via_savings_first(real_session):
    """The real, live 'approved, savings-first' path -- Phase 28's other
    primary target state, verified live. `emergency_fund_savings_first`
    correctly does NOT trigger, because a legitimate savings-first
    recommendation IS what was proposed for an insufficient fund (its own
    unmodified rule logic), and the four weight rules correctly do not
    trigger either, because Phase 28's compliance fix recognizes a
    savings-first proposal's absent weights as expected, not invalid."""
    deps = GraphDependencies(
        session=real_session, monthly_essential_expenses=5000.0, current_liquid_assets=1000.0
    )
    result = run_analysis_graph(AgentState(customer_id=2), deps)

    assert result.compliance_result is not None
    assert result.compliance_result.decision == "PASS"
    assert result.blocked is False
    triggered = {r.rule_id for r in result.compliance_result.rule_results if r.triggered}
    assert triggered == set()


def test_unknown_emergency_fund_still_fails_closed_to_reject(real_session):
    """Regression guard: the fail-closed REJECT behavior for a customer
    with NO financial inputs at all (e.g. every pre-Phase-28 demo persona
    that has not yet had inputs added) is completely unchanged --
    Phase 28 never weakens this path."""
    deps = GraphDependencies(session=real_session)
    result = run_analysis_graph(AgentState(customer_id=2), deps)

    assert result.compliance_result is not None
    assert result.compliance_result.decision == "REJECT"
    assert result.blocked is True
    triggered = {r.rule_id for r in result.compliance_result.rule_results if r.triggered}
    assert triggered == {"emergency_fund_savings_first"}


def test_savings_first_with_inconsistent_weights_is_still_fully_validated(real_session):
    """Guards the exemption's own boundary directly at the compliance
    layer (not just via the graph): a savings-first proposal that
    inconsistently DOES carry weights is still validated in full, never
    given a free pass merely for being flagged savings-first."""
    from wealthpilot.core.compliance import ComplianceProposal, evaluate_compliance

    proposal = ComplianceProposal(
        risk_level="Aggressive",
        weights={"QQQ": 0.9, "AGG": 0.05, "GLD": 0.05},  # QQQ far outside any approved band
        emergency_fund_sufficient=False,
        is_savings_first_recommendation=True,
    )
    result = evaluate_compliance(proposal)
    assert result.decision == "REJECT"
    triggered = {r.rule_id for r in result.rule_results if r.triggered}
    assert "qqq_within_risk_band" in triggered
