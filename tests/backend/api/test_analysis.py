"""POST /api/analysis, GET /api/analysis/{id} (Phase 15 sections 7-14, 41,
42). Uses `real_client` (real FAR-Trans/`market_data`, rollback-safe) for
the naturally-occurring `rejected`/`pending_information` terminal states,
and `client` (synthetic customer, mocked graph -- see `conftest.py`'s
`approved_steps`/`rejected_steps`/`patch_graph`) for a controlled
`approved` scenario without needing real financial-input data set up on a
synthetic `TEST_DATABASE_URL` customer.

**Historical note, corrected by Phase 28**: this docstring previously said
a real FAR-Trans customer could never reach `approved` because
`emergency_fund.sufficient` was always `None` for every customer (no
financial data was ever supplied to the pipeline). Phase 28 closed that
gap (`GET`/`PUT /api/profiles/{id}/financial-inputs`, wired into
`analysis_service.py::_build_graph_dependencies`) -- a real customer WITH
financial inputs on file now genuinely can, and does, reach `approved`
(verified live; see `tests/backend/agents/test_financial_inputs_integration.py`
and `reports/phase28_financial_input_savings_first_report.md`). The
`client`/mocked-graph fixtures here remain useful for testing this
endpoint's OWN orchestration (caching, persistence, response shape) in
isolation from real financial-input setup, which is why they are kept.
"""

from __future__ import annotations

from tests.backend.api.conftest import approved_steps, patch_graph, rejected_steps
from wealthpilot.api.services import analysis_service
from wealthpilot.api.services.analysis_service import compute_profile_hash
from wealthpilot.db.models import FinancialInputs


# ---------------------------------------------------------------------------
# Approved path (mocked graph, synthetic customer, TEST_DATABASE_URL)
# ---------------------------------------------------------------------------


def test_approved_analysis_returns_recommendation_and_explanation(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    response = client.post("/api/analysis", json={"profile_id": customer.id})
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "approved"
    assert body["compliance"]["decision"] == "PASS"
    assert body["recommendation"] is not None
    assert body["recommendation"]["status"] == "approved"
    assert body["recommendation"]["selected_strategy"] == "equal_weight"
    assert body["explanation"] is not None
    assert body["explanation"]["disclaimer"]


def test_approved_analysis_preserves_exact_phase8_weights_numerical_integrity(client, make_customer, monkeypatch):
    """CRITICAL (section 42): the response must contain EXACTLY the
    authoritative weights, unmodified -- no presentation rounding, no
    recalculation, not `55%`/`30%`/`15%` when the source is raw decimals
    (section 13)."""
    customer = make_customer()
    weights = {"QQQ": 0.55, "AGG": 0.30, "GLD": 0.15}
    steps = approved_steps(customer.id)
    # Overwrite the portfolio_manager/compliance/approved steps' weights to
    # the exact CRITICAL-example values from the prompt, keeping the risk
    # category consistent with the "mvo" base strategy those weights imply.
    fixed_steps = []
    for node, state_dict in steps:
        if node in ("portfolio_manager", "compliance_analyst", "approved"):
            state_dict = dict(state_dict)
            state_dict["risk_assessment"] = dict(state_dict["risk_assessment"], risk_category="Aggressive")
            state_dict["portfolio_result"] = dict(state_dict["portfolio_result"], strategy="mvo", weights=weights)
        fixed_steps.append((node, state_dict))
    from tests.backend.api.conftest import FakeCompiledGraph

    monkeypatch.setattr(analysis_service, "build_analysis_graph", lambda: FakeCompiledGraph(fixed_steps))

    response = client.post("/api/analysis", json={"profile_id": customer.id})
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio"]["weights"] == weights
    assert body["recommendation"]["weights"] == weights
    assert body["recommendation"]["weights"]["QQQ"] == 0.55  # exact decimal, not "55"/"55%"


def test_approved_analysis_persists_recommendation_and_agent_logs(client, make_customer, monkeypatch, db_session):
    from sqlalchemy import select

    from wealthpilot.db.models import AgentLog, Recommendation

    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    response = client.post("/api/analysis", json={"profile_id": customer.id})
    assert response.status_code == 200

    rec_row = db_session.scalar(select(Recommendation).where(Recommendation.customer_id == customer.id))
    assert rec_row is not None
    assert rec_row.risk_category == "Balanced"
    assert rec_row.confidence is None  # section 12: never invented

    log_rows = db_session.scalars(select(AgentLog).where(AgentLog.customer_id == customer.id)).all()
    assert len(log_rows) >= 8  # 6 graph nodes + recommendation + explanation
    assert {row.agent_name for row in log_rows} >= {"risk_analyst", "compliance_analyst", "recommendation", "explanation"}


def test_second_call_with_identical_profile_returns_cached_analysis_id(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    first = client.post("/api/analysis", json={"profile_id": customer.id})
    second = client.post("/api/analysis", json={"profile_id": customer.id})
    assert first.json()["analysis_id"] == second.json()["analysis_id"]


def test_profile_hash_changes_when_financial_inputs_change(client, make_customer, db_session):
    """Phase 28 regression guard: `financial_inputs` is a real pipeline
    input now (see `_build_graph_dependencies`), so it must be part of the
    cache key -- otherwise editing it via `PUT .../financial-inputs` would
    silently keep serving a stale, pre-edit analysis result forever."""
    customer = make_customer()
    goals = list(customer.financial_goals)

    hash_with_none = compute_profile_hash(customer, goals, None, None)

    inputs_a = FinancialInputs(customer_id=customer.id, monthly_essential_expenses=1000.0, current_liquid_assets=5000.0)
    hash_with_a = compute_profile_hash(customer, goals, None, inputs_a)
    assert hash_with_a != hash_with_none

    inputs_b = FinancialInputs(customer_id=customer.id, monthly_essential_expenses=2000.0, current_liquid_assets=5000.0)
    hash_with_b = compute_profile_hash(customer, goals, None, inputs_b)
    assert hash_with_b != hash_with_a


def test_second_call_after_financial_inputs_change_runs_a_fresh_analysis(client, make_customer, monkeypatch):
    """API-level confirmation of the same guarantee: `PUT
    .../financial-inputs` between two `POST /api/analysis` calls for the
    same profile must NOT return the first call's cached `analysis_id`."""
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    first = client.post("/api/analysis", json={"profile_id": customer.id})
    client.put(f"/api/profiles/{customer.id}/financial-inputs", json={"monthly_essential_expenses": 1500.0})
    second = client.post("/api/analysis", json={"profile_id": customer.id})

    assert first.json()["analysis_id"] != second.json()["analysis_id"]


def test_get_analysis_by_id_returns_the_same_result(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    created = client.post("/api/analysis", json={"profile_id": customer.id})
    analysis_id = created.json()["analysis_id"]

    fetched = client.get(f"/api/analysis/{analysis_id}")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


# ---------------------------------------------------------------------------
# Compliance REJECT (CRITICAL — section 22/37 precedent from Phase 14)
# ---------------------------------------------------------------------------


def test_rejected_analysis_produces_no_recommendation_and_no_portfolio_in_recommendation(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, rejected_steps(customer.id))

    response = client.post("/api/analysis", json={"profile_id": customer.id})
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "rejected"
    assert body["compliance"]["decision"] == "REJECT"
    assert body["recommendation"] is None
    assert body["explanation"] is None


def test_rejected_analysis_is_not_persisted_as_a_recommendation(client, make_customer, monkeypatch, db_session):
    from sqlalchemy import select

    from wealthpilot.db.models import Recommendation

    customer = make_customer()
    patch_graph(monkeypatch, rejected_steps(customer.id))

    client.post("/api/analysis", json={"profile_id": customer.id})

    rec_row = db_session.scalar(select(Recommendation).where(Recommendation.customer_id == customer.id))
    assert rec_row is None


# ---------------------------------------------------------------------------
# Naturally-occurring terminal states against real FAR-Trans data
# ---------------------------------------------------------------------------


def test_real_customer_analysis_reaches_a_valid_terminal_status(real_client):
    response = real_client.post("/api/analysis", json={"profile_id": 1})
    assert response.status_code == 200
    assert response.json()["status"] in ("approved", "rejected", "pending_information", "failed")


def test_real_customer_pending_information_has_no_recommendation(real_client):
    response = real_client.post("/api/analysis", json={"profile_id": 3})
    assert response.status_code == 200
    body = response.json()
    if body["status"] == "pending_information":
        assert body["recommendation"] is None
        assert body["explanation"] is None
