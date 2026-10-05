"""Shared Phase 15 API test fixtures.

Two separate `TestClient` flavors, matching the same DB split the rest of
this project's tests already use:

- `client` — the API wired to the rollback-safe `TEST_DATABASE_URL`
  (mirrors `tests/backend/conftest.py::db_session` exactly, via
  `get_session`/`get_session_factory` dependency overrides), for tests
  that create their own synthetic customer/profile data and never need
  real FAR-Trans/`market_data`.
- `real_client` — the API wired to a rollback-safe connection against the
  REAL dev `DATABASE_URL` (mirrors `tests/backend/agents/test_nodes.py`'s
  `real_session` fixture's "read real data, never write" intent), for
  tests that need genuine FAR-Trans customers and `market_data`.

Both overridden dependencies share ONE connection per fixture (see
`_client_for`) — a plain-route write (via `get_session`) and an
SSE-triggered write (via `get_session_factory`, used only by
`api/sse.py`) are therefore both visible to the test's own assertions on
`db_session`/`real_db_session`, and both roll back together: the
`session.commit()` `api/sse.py`'s generator calls only ends/restarts a
SAVEPOINT (SQLAlchemy 2.0's `join_transaction_mode="create_savepoint"`,
the same mechanism `tests/backend/conftest.py` already documents for
`.rollback()`) — the fixture's OUTER transaction, and so every row either
override ever wrote, is still rolled back in teardown either way.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from wealthpilot.agents.state import (
    AgentState,
    AgentStateDelta,
    CustomerProfile,
    EmergencyFundResult,
    InstrumentRegime,
    MarketAnalysisResult,
    PortfolioResult,
    RiskAssessmentResult,
    apply_delta,
)
from wealthpilot.api.dependencies import get_session, get_session_factory
from wealthpilot.api.main import app
from wealthpilot.api.services import analysis_service
from wealthpilot.config import get_settings
from wealthpilot.core.compliance import ComplianceResult
from wealthpilot.db.models import Customer
from wealthpilot.db.session import get_engine


def _rollback_safe_connection(database_url: str):
    engine = get_engine(database_url)
    connection = engine.connect()
    outer_transaction = connection.begin()
    try:
        yield connection
    finally:
        outer_transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture()
def db_connection():
    settings = get_settings()
    assert settings.test_database_url, "TEST_DATABASE_URL is not set -- see .env.example"
    yield from _rollback_safe_connection(settings.test_database_url)


@pytest.fixture()
def real_db_connection():
    settings = get_settings()
    yield from _rollback_safe_connection(settings.database_url)


def _session_on(connection):
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def db_session(db_connection):
    yield from _session_on(db_connection)


@pytest.fixture()
def real_db_session(real_db_connection):
    yield from _session_on(real_db_connection)


def _client_for(connection, session: Session):
    """Overrides BOTH `get_session` (regular routes) and
    `get_session_factory` (`api/sse.py`'s SSE endpoint) so every route a
    test hits shares the SAME underlying connection/transaction as
    `session` — a plain-route write and an SSE-triggered write are both
    visible to the test's own assertions, and both roll back together
    when the connection-level fixture tears down (see module docstring)."""

    def _override_get_session():
        yield session

    def _override_get_session_factory():
        return lambda: Session(bind=connection, join_transaction_mode="create_savepoint")

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = _override_get_session_factory
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_session_factory, None)


@pytest.fixture()
def client(db_connection, db_session):
    yield from _client_for(db_connection, db_session)


@pytest.fixture()
def real_client(real_db_connection, real_db_session):
    yield from _client_for(real_db_connection, real_db_session)


@pytest.fixture()
def make_customer(db_session):
    def _make(**overrides) -> Customer:
        defaults = dict(name="API Test Customer", data_source="user-entered")
        defaults.update(overrides)
        customer = Customer(**defaults)
        db_session.add(customer)
        db_session.flush()
        return customer

    return _make


# ---------------------------------------------------------------------------
# Shared mocked-graph helpers for test_analysis.py / test_sse.py -- a hand-
# built, fully deterministic sequence of (node, cumulative full state dict)
# pairs, exactly what `stream_mode="updates"` yields from the real graph,
# constructed directly instead of requiring real FAR-Trans/market_data.
# ---------------------------------------------------------------------------


def approved_steps(customer_id: int) -> list[tuple[str, dict]]:
    """Balanced risk -> "equal_weight" is the approved risk-conditioned
    base strategy (Phase 14), so no live portfolio recomputation is
    needed either (1/3 weights are a constant, not read from data)."""
    state = AgentState(customer_id=customer_id)
    steps: list[tuple[str, dict]] = []

    state = apply_delta(state, AgentStateDelta(customer_profile=CustomerProfile(customer_id=customer_id, name="Test", data_source="user-entered")))
    steps.append(("customer_analyzer", state.model_dump()))

    state = apply_delta(state, AgentStateDelta(risk_assessment=RiskAssessmentResult(risk_category="Balanced", confidence=0.85, model_version="v1", data_source="models/risk")))
    steps.append(("risk_analyst", state.model_dump()))

    steps.append(("financial_health_analyst", state.model_dump()))

    state = apply_delta(state, AgentStateDelta(emergency_fund=EmergencyFundResult(sufficient=True)))
    steps.append(("goal_analyst", state.model_dump()))

    state = apply_delta(
        state,
        AgentStateDelta(
            market_analysis=MarketAnalysisResult(
                instruments=[InstrumentRegime(ticker="QQQ", latest_regime="Trending")], model_version="v1", data_source="models/metrics.json"
            )
        ),
    )
    steps.append(("market_analyst", state.model_dump()))

    weights = {"QQQ": 1 / 3, "AGG": 1 / 3, "GLD": 1 / 3}
    state = apply_delta(
        state,
        AgentStateDelta(
            portfolio_result=PortfolioResult(
                strategy="equal_weight", risk_level="Balanced", weights=weights, asset_universe=["QQQ", "AGG", "GLD"],
                expected_return=0.1, expected_volatility=0.12, sharpe_ratio=0.83, config_version="v1", data_source="market_data (PostgreSQL)",
            )
        ),
    )
    steps.append(("portfolio_manager", state.model_dump()))

    state = apply_delta(
        state,
        AgentStateDelta(compliance_result=ComplianceResult(decision="PASS", rules_version="v1", evaluated_at="2026-01-01T00:00:00+00:00", rule_results=[])),
    )
    steps.append(("compliance_analyst", state.model_dump()))
    steps.append(("approved", state.model_dump()))

    return steps


def rejected_steps(customer_id: int) -> list[tuple[str, dict]]:
    state = AgentState(customer_id=customer_id)
    state = apply_delta(state, AgentStateDelta(risk_assessment=RiskAssessmentResult(risk_category="Aggressive", confidence=0.9, model_version="v1", data_source="models/risk")))
    state = apply_delta(state, AgentStateDelta(emergency_fund=EmergencyFundResult(sufficient=False)))
    state = apply_delta(
        state,
        AgentStateDelta(compliance_result=ComplianceResult(decision="REJECT", rules_version="v1", evaluated_at="2026-01-01T00:00:00+00:00", rule_results=[])),
    )
    return [
        ("customer_analyzer", state.model_dump()),
        ("risk_analyst", state.model_dump()),
        ("financial_health_analyst", state.model_dump()),
        ("goal_analyst", state.model_dump()),
        ("market_analyst", state.model_dump()),
        ("savings_first", state.model_dump()),
        ("compliance_analyst", state.model_dump()),
        ("rejected", state.model_dump()),
    ]


class FakeCompiledGraph:
    def __init__(self, steps: list[tuple[str, dict]]):
        self._steps = steps

    def stream(self, state, config, stream_mode="updates"):
        for node_name, state_dict in self._steps:
            yield {node_name: state_dict}


def patch_graph(monkeypatch, steps: list[tuple[str, dict]]) -> None:
    monkeypatch.setattr(analysis_service, "build_analysis_graph", lambda: FakeCompiledGraph(steps))
