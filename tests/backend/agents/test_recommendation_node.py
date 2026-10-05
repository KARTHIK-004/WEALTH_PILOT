"""Phase 14 node/orchestration tests: `agents/recommendation.py`.

Two DB fixtures, matching this project's established split:
- `db_session` (conftest.py's rollback-safe TEST_DATABASE_URL) for
  persistence tests and any test where a same-strategy `state.portfolio_result`
  already exists (the "reuse directly" fast path never touches
  `market_data`, so no real data is required).
- `real_session` (read-only dev database, same pattern as
  `test_nodes.py::real_session`) only for the one scenario that genuinely
  needs live `market_data`: recomputing a DIFFERENT strategy than
  whatever is already in state.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from wealthpilot.agents import recommendation as R
from wealthpilot.agents.state import (
    AgentState,
    AgentStateDelta,
    EmergencyFundResult,
    GoalAnalysisResult,
    InstrumentRegime,
    MarketAnalysisResult,
    PortfolioResult,
    RiskAssessmentResult,
    apply_delta,
)
from wealthpilot.config import get_settings
from wealthpilot.core.compliance import ComplianceResult
from wealthpilot.core.recommendation import Recommendation as CoreRecommendation
from wealthpilot.core.recommendation import RecommendationRationale
from wealthpilot.db.models import Customer
from wealthpilot.db.models import Recommendation as RecommendationRow


@pytest.fixture(scope="module")
def real_session():
    """Read-only access to the real dev database -- never writes (matches
    `test_nodes.py::real_session` exactly)."""
    from wealthpilot.db.session import get_engine

    settings = get_settings()
    engine = get_engine(settings.database_url)
    with Session(engine) as session:
        yield session


def _make_customer(db_session) -> Customer:
    customer = Customer(name="Phase 14 Test Customer", data_source="user-entered")
    db_session.add(customer)
    db_session.flush()
    return customer


def _compliance(decision: str = "PASS") -> ComplianceResult:
    return ComplianceResult(decision=decision, rules_version="v1", evaluated_at="2026-01-01T00:00:00+00:00", rule_results=[])


def _build_state(
    customer_id: int,
    risk_category: str | None = "Aggressive",
    ef_sufficient: bool | None = True,
    goal_feasibilities: list[str] | None = None,
    market_regime: str | None = "Trending",
    portfolio_strategy: str | None = "mvo",
    weights: dict[str, float] | None = None,
    compliance_decision: str = "PASS",
) -> AgentState:
    weights = weights or {"QQQ": 0.55, "AGG": 0.0, "GLD": 0.45}
    goal_results = [
        GoalAnalysisResult(goal_id=i, goal_type="retirement", nominal_target_amount=100000.0, feasibility=f)
        for i, f in enumerate(goal_feasibilities or [])
    ]
    state = AgentState(customer_id=customer_id)
    state = apply_delta(
        state,
        AgentStateDelta(
            risk_assessment=(
                RiskAssessmentResult(risk_category=risk_category, model_version="v1", data_source="models/risk")
                if risk_category
                else None
            ),
            emergency_fund=EmergencyFundResult(sufficient=ef_sufficient),
            goal_results=goal_results,
            market_analysis=(
                MarketAnalysisResult(
                    instruments=[InstrumentRegime(ticker="QQQ", latest_regime=market_regime)],
                    model_version="v1",
                    data_source="models/metrics.json",
                )
                if market_regime
                else None
            ),
            portfolio_result=(
                PortfolioResult(
                    strategy=portfolio_strategy,
                    risk_level=risk_category,
                    weights=weights,
                    asset_universe=["QQQ", "AGG", "GLD"],
                    expected_return=0.17,
                    expected_volatility=0.16,
                    sharpe_ratio=1.05,
                    config_version="v1",
                    data_source="market_data (PostgreSQL)",
                )
                if portfolio_strategy
                else None
            ),
        ),
    )
    return apply_delta(state, AgentStateDelta(compliance_result=_compliance(compliance_decision)))


# ---------------------------------------------------------------------------
# _primary_market_regime -- pure, no DB
# ---------------------------------------------------------------------------


def test_primary_market_regime_picks_qqq_specifically_not_another_instrument():
    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(
            market_analysis=MarketAnalysisResult(
                instruments=[
                    InstrumentRegime(ticker="AGG", latest_regime="Range-bound"),
                    InstrumentRegime(ticker="QQQ", latest_regime="Volatile"),
                    InstrumentRegime(ticker="GLD", latest_regime="Trending"),
                ],
                model_version="v1",
                data_source="models/metrics.json",
            )
        ),
    )
    assert R._primary_market_regime(state) == "Volatile"


def test_primary_market_regime_none_when_qqq_absent():
    state = apply_delta(
        AgentState(customer_id=1),
        AgentStateDelta(
            market_analysis=MarketAnalysisResult(
                instruments=[InstrumentRegime(ticker="GLD", latest_regime="Trending")],
                model_version="v1",
                data_source="models/metrics.json",
            )
        ),
    )
    assert R._primary_market_regime(state) is None


def test_primary_market_regime_none_when_market_analysis_missing():
    assert R._primary_market_regime(AgentState(customer_id=1)) is None


# ---------------------------------------------------------------------------
# _obtain_portfolio_candidate
# ---------------------------------------------------------------------------


def test_obtain_portfolio_candidate_reuses_state_result_without_recomputation(monkeypatch, db_session):
    """When `state.portfolio_result` already matches the requested
    strategy, `portfolio_manager_node` must NOT be called again (no
    market_data access needed at all for this path)."""

    def _boom(*args, **kwargs):
        raise AssertionError("portfolio_manager_node should not be called when state.portfolio_result already matches")

    monkeypatch.setattr(R.N, "portfolio_manager_node", _boom)
    state = _build_state(1, risk_category="Aggressive", portfolio_strategy="mvo")
    candidate = R._obtain_portfolio_candidate(state, db_session, "mvo")
    assert candidate is not None
    assert candidate.strategy == "mvo"
    assert candidate.weights == state.portfolio_result.weights


def test_obtain_portfolio_candidate_recomputes_for_a_different_strategy(real_session):
    """A Conservative customer's state may already hold an 'mvo' result
    (Phase 10's default) -- Layer 3 needs 'hrp'. This must call the
    existing, unmodified `portfolio_manager_node` again and return the
    correct strategy's real weights, not the stale mvo ones."""
    state = _build_state(1, risk_category="Conservative", portfolio_strategy="mvo")
    candidate = R._obtain_portfolio_candidate(state, real_session, "hrp")
    assert candidate is not None
    assert candidate.strategy == "hrp"
    assert candidate.strategy != state.portfolio_result.strategy
    assert sum(candidate.weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_obtain_portfolio_candidate_returns_none_when_nothing_available(db_session):
    state = AgentState(customer_id=1)  # no risk_assessment at all
    candidate = R._obtain_portfolio_candidate(state, db_session, "mvo")
    assert candidate is None


# ---------------------------------------------------------------------------
# build_recommendation_input
# ---------------------------------------------------------------------------


def test_build_recommendation_input_extracts_real_state_fields(db_session):
    state = _build_state(
        1, risk_category="Balanced", ef_sufficient=True, goal_feasibilities=["Feasible", "At Risk"],
        market_regime="Range-bound", portfolio_strategy="equal_weight", weights={"QQQ": 1 / 3, "AGG": 1 / 3, "GLD": 1 / 3},
    )
    rec_input = R.build_recommendation_input(state, db_session)
    assert rec_input.risk_category == "Balanced"
    assert rec_input.emergency_fund_sufficient is True
    assert rec_input.goal_feasibilities == ["Feasible", "At Risk"]
    assert rec_input.market_regime == "Range-bound"
    assert rec_input.portfolio_candidate is not None
    assert rec_input.portfolio_candidate.strategy == "equal_weight"


def test_build_recommendation_input_skips_portfolio_lookup_when_rejected(monkeypatch, db_session):
    def _boom(*args, **kwargs):
        raise AssertionError("should not call portfolio_manager_node for a REJECTed proposal")

    monkeypatch.setattr(R.N, "portfolio_manager_node", _boom)
    state = _build_state(1, compliance_decision="REJECT", portfolio_strategy=None)
    rec_input = R.build_recommendation_input(state, db_session)
    assert rec_input.portfolio_candidate is None


def test_build_recommendation_input_skips_portfolio_lookup_when_savings_first(monkeypatch, db_session):
    def _boom(*args, **kwargs):
        raise AssertionError("should not call portfolio_manager_node when the emergency fund is insufficient")

    monkeypatch.setattr(R.N, "portfolio_manager_node", _boom)
    state = _build_state(1, ef_sufficient=False, portfolio_strategy=None)
    rec_input = R.build_recommendation_input(state, db_session)
    assert rec_input.portfolio_candidate is None


# ---------------------------------------------------------------------------
# persist_recommendation
# ---------------------------------------------------------------------------


def test_persist_recommendation_writes_an_approved_row(db_session):
    customer = _make_customer(db_session)
    weights = {"QQQ": 0.55, "AGG": 0.0, "GLD": 0.45}
    rec = CoreRecommendation(
        status="approved", selected_strategy="mvo", weights=weights, expected_return=0.17,
        expected_volatility=0.16, sharpe_ratio=1.05, risk_category="Aggressive", compliance_decision="PASS",
        rationale=RecommendationRationale(reasons=["risk category selects mvo"]),
        data_sources=["market_data (PostgreSQL)"],
    )
    row = R.persist_recommendation(db_session, customer.id, rec)
    assert row is not None

    fetched = db_session.get(RecommendationRow, row.id)
    assert fetched.risk_category == "Aggressive"
    assert fetched.portfolio_allocation == weights
    assert fetched.confidence is None  # section 20: never invented
    assert fetched.model_version == "v1"
    payload = json.loads(fetched.recommendation)
    assert payload["status"] == "approved"
    assert payload["selected_strategy"] == "mvo"


def test_persist_recommendation_writes_a_savings_first_row_with_empty_allocation(db_session):
    customer = _make_customer(db_session)
    rec = CoreRecommendation(
        status="savings_first", risk_category="Balanced", compliance_decision="PASS",
        rationale=RecommendationRationale(reasons=["emergency fund insufficient"]),
    )
    row = R.persist_recommendation(db_session, customer.id, rec)
    assert row is not None
    assert row.portfolio_allocation == {}


def test_persist_recommendation_skips_blocked_rejected(db_session):
    customer = _make_customer(db_session)
    rec = CoreRecommendation(
        status="blocked_rejected", compliance_decision="REJECT",
        rationale=RecommendationRationale(reasons=["compliance REJECT"]), blocking_reason="Compliance decision is REJECT.",
    )
    row = R.persist_recommendation(db_session, customer.id, rec)
    assert row is None
    assert db_session.scalar(select(RecommendationRow).where(RecommendationRow.customer_id == customer.id)) is None


def test_persist_recommendation_skips_failed(db_session):
    customer = _make_customer(db_session)
    rec = CoreRecommendation(
        status="failed", compliance_decision="PASS", rationale=RecommendationRationale(reasons=["risk unavailable"]),
        blocking_reason="Risk category is unavailable.",
    )
    row = R.persist_recommendation(db_session, customer.id, rec)
    assert row is None


def test_persist_recommendation_skips_when_risk_category_not_representable(db_session):
    customer = _make_customer(db_session)
    rec = CoreRecommendation(
        status="savings_first", risk_category=None, compliance_decision="PASS",
        rationale=RecommendationRationale(reasons=["emergency fund insufficient"]),
    )
    row = R.persist_recommendation(db_session, customer.id, rec)
    assert row is None


# ---------------------------------------------------------------------------
# recommendation_engine_node -- full orchestration
# ---------------------------------------------------------------------------


def test_recommendation_engine_node_type_check():
    with pytest.raises(TypeError):
        R.recommendation_engine_node({"not": "a state"}, session=None)


def test_recommendation_engine_node_missing_compliance_result_fails(db_session):
    state = AgentState(customer_id=1)
    result = R.recommendation_engine_node(state, db_session)
    assert result["recommendation_result"]["status"] == "failed"
    assert "invalid_recommendation_input" in result["recommendation_result"]["rationale"]["reasons"][0]


def test_recommendation_engine_node_approved_end_to_end_persists(db_session):
    customer = _make_customer(db_session)
    state = _build_state(
        customer.id, risk_category="Aggressive", ef_sufficient=True, goal_feasibilities=["At Risk"],
        market_regime="Trending", portfolio_strategy="mvo", compliance_decision="PASS",
    )
    result = R.recommendation_engine_node(state, db_session)
    rec = result["recommendation_result"]
    assert rec["status"] == "approved"
    assert rec["selected_strategy"] == "mvo"

    row = db_session.scalar(select(RecommendationRow).where(RecommendationRow.customer_id == customer.id))
    assert row is not None
    assert row.risk_category == "Aggressive"


def test_recommendation_engine_node_savings_first_persists(db_session):
    customer = _make_customer(db_session)
    state = _build_state(customer.id, risk_category="Balanced", ef_sufficient=False, portfolio_strategy=None)
    result = R.recommendation_engine_node(state, db_session)
    assert result["recommendation_result"]["status"] == "savings_first"

    row = db_session.scalar(select(RecommendationRow).where(RecommendationRow.customer_id == customer.id))
    assert row is not None
    assert row.portfolio_allocation == {}


def test_recommendation_engine_node_rejected_does_not_persist_and_cannot_be_overridden(db_session):
    """CRITICAL (section 37): even with a valid portfolio candidate and
    sufficient EF, a REJECT decision must block persistence entirely."""
    customer = _make_customer(db_session)
    state = _build_state(customer.id, compliance_decision="REJECT", ef_sufficient=True, portfolio_strategy="mvo")
    result = R.recommendation_engine_node(state, db_session)
    assert result["recommendation_result"]["status"] == "blocked_rejected"

    row = db_session.scalar(select(RecommendationRow).where(RecommendationRow.customer_id == customer.id))
    assert row is None


def test_recommendation_engine_node_does_not_mutate_the_input_state(db_session):
    customer = _make_customer(db_session)
    state = _build_state(customer.id)
    original_weights = dict(state.portfolio_result.weights)
    original_decision = state.compliance_result.decision

    R.recommendation_engine_node(state, db_session)

    assert state.portfolio_result.weights == original_weights
    assert state.compliance_result.decision == original_decision
