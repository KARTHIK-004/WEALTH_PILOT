"""Model round-trip tests, one per table in docs/BUILD_PLAN.md section 5.

Each test inserts a row, reads it back via a fresh query, and asserts the
fields survived the round trip. Runs inside a transaction that is always
rolled back (see conftest.py) against TEST_DATABASE_URL only.
"""

from datetime import date, datetime, timezone

from sqlalchemy import select

from wealthpilot.db.models import (
    AgentLog,
    AnalysisRun,
    Customer,
    CustomerRiskSnapshot,
    FinancialGoal,
    MarketData,
    Portfolio,
    Recommendation,
    RiskAssessment,
    Transaction,
)


def _make_customer(db_session) -> Customer:
    customer = Customer(
        name="Test Customer",
        age=35,
        income=75000,
        employment_status="Employed",
        customer_type="Mass",
        investment_capacity="CAP_30K_80K",
        risk_inputs={"q1": "Balanced"},
        data_source="user-entered",
    )
    db_session.add(customer)
    db_session.flush()
    return customer


def test_customer_round_trip(db_session):
    customer = _make_customer(db_session)

    fetched = db_session.scalar(select(Customer).where(Customer.id == customer.id))

    assert fetched is not None
    assert fetched.name == "Test Customer"
    assert fetched.data_source == "user-entered"
    assert fetched.created_at is not None


def test_financial_goal_round_trip(db_session):
    customer = _make_customer(db_session)
    goal = FinancialGoal(
        customer_id=customer.id,
        goal_type="House Purchase",
        target_amount=5_000_000,
        target_date=date(2035, 1, 1),
        current_savings=1_000_000,
        priority=1,
    )
    db_session.add(goal)
    db_session.flush()

    fetched = db_session.scalar(select(FinancialGoal).where(FinancialGoal.id == goal.id))

    assert fetched is not None
    assert fetched.customer_id == customer.id
    assert float(fetched.target_amount) == 5_000_000


def test_transaction_round_trip(db_session):
    customer = _make_customer(db_session)
    txn = Transaction(
        customer_id=customer.id,
        transaction_date=datetime(2022, 3, 1, tzinfo=timezone.utc),
        category="Stock",
        amount=1500.50,
        transaction_type="buy",
        data_source="FAR-Trans",
    )
    db_session.add(txn)
    db_session.flush()

    fetched = db_session.scalar(select(Transaction).where(Transaction.id == txn.id))

    assert fetched is not None
    assert fetched.transaction_type == "buy"
    assert fetched.data_source == "FAR-Trans"


def test_portfolio_round_trip(db_session):
    customer = _make_customer(db_session)
    holding = Portfolio(
        customer_id=customer.id,
        asset="Equity",
        allocation=60.0,
        value=45000.0,
        data_source="computed",
    )
    db_session.add(holding)
    db_session.flush()

    fetched = db_session.scalar(select(Portfolio).where(Portfolio.id == holding.id))

    assert fetched is not None
    assert float(fetched.allocation) == 60.0


def test_market_data_round_trip(db_session):
    bar = MarketData(
        ticker="QQQ",
        date=date(2024, 1, 2),
        open=400.0,
        high=405.0,
        low=398.0,
        close=402.5,
        volume=1_000_000,
        source="yfinance",
    )
    db_session.add(bar)
    db_session.flush()

    fetched = db_session.scalar(select(MarketData).where(MarketData.id == bar.id))

    assert fetched is not None
    assert fetched.ticker == "QQQ"
    assert fetched.source == "yfinance"


def test_recommendation_round_trip(db_session):
    customer = _make_customer(db_session)
    rec = Recommendation(
        customer_id=customer.id,
        recommendation="Reduce equity exposure given updated risk profile.",
        risk_category="Balanced",
        portfolio_allocation={"equity": 60, "bonds": 25, "gold": 10, "cash": 5},
        confidence=0.87,
        model_version="v0.1.0",
        data_source="computed",
    )
    db_session.add(rec)
    db_session.flush()

    fetched = db_session.scalar(select(Recommendation).where(Recommendation.id == rec.id))

    assert fetched is not None
    assert fetched.portfolio_allocation["equity"] == 60
    assert fetched.model_version == "v0.1.0"


def test_agent_log_round_trip(db_session):
    customer = _make_customer(db_session)
    log = AgentLog(
        customer_id=customer.id,
        agent_name="risk_analyst",
        action="classify_risk",
        status="completed",
        result="Balanced, confidence 0.87",
        duration_ms=120,
        model_version="xgb-v1",
    )
    db_session.add(log)
    db_session.flush()

    fetched = db_session.scalar(select(AgentLog).where(AgentLog.id == log.id))

    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.duration_ms == 120


def test_risk_assessment_round_trip(db_session):
    customer = _make_customer(db_session)
    assessment = RiskAssessment(
        customer_id=customer.id,
        risk_category="Balanced",
        risk_score=62,
        confidence=0.87,
        class_probabilities={"Conservative": 0.05, "Income": 0.08, "Balanced": 0.87, "Aggressive": 0.0},
        shap_values={"trades_per_year": 0.12},
        model_version="xgb-v1",
    )
    db_session.add(assessment)
    db_session.flush()

    fetched = db_session.scalar(select(RiskAssessment).where(RiskAssessment.id == assessment.id))

    assert fetched is not None
    assert fetched.risk_score == 62
    assert fetched.class_probabilities["Balanced"] == 0.87


def test_analysis_run_round_trip(db_session):
    customer = _make_customer(db_session)
    run = AnalysisRun(
        customer_id=customer.id,
        profile_hash="abc123",
        status="completed",
        result={"risk_category": "Balanced"},
    )
    db_session.add(run)
    db_session.flush()

    fetched = db_session.scalar(select(AnalysisRun).where(AnalysisRun.id == run.id))

    assert fetched is not None
    assert fetched.profile_hash == "abc123"
    assert fetched.status == "completed"


def test_customer_risk_snapshot_round_trip(db_session):
    customer = _make_customer(db_session)
    snapshot = CustomerRiskSnapshot(
        customer_id=customer.id,
        snapshot_date=date(2020, 1, 1),
        customer_type="Mass",
        risk_level="Conservative",
        investment_capacity="CAP_LT30K",
        data_source="FAR-Trans",
    )
    db_session.add(snapshot)
    db_session.flush()

    fetched = db_session.scalar(select(CustomerRiskSnapshot).where(CustomerRiskSnapshot.id == snapshot.id))

    assert fetched is not None
    assert fetched.customer_id == customer.id
    assert fetched.risk_level == "Conservative"
    assert fetched.investment_capacity == "CAP_LT30K"


def test_customer_risk_snapshot_preserves_raw_predicted_and_not_available_values(db_session):
    """The snapshot table stores history unfiltered — Predicted_*/Not_Available
    values must round-trip exactly, since genuine-label filtering happens at
    feature-engineering time (CLAUDE.md rule 7), not at ingestion time."""
    customer = _make_customer(db_session)
    snapshot = CustomerRiskSnapshot(
        customer_id=customer.id,
        snapshot_date=date(2021, 6, 1),
        customer_type="Mass",
        risk_level="Predicted_Balanced",
        investment_capacity="Not_Available",
        data_source="FAR-Trans",
    )
    db_session.add(snapshot)
    db_session.flush()

    fetched = db_session.scalar(select(CustomerRiskSnapshot).where(CustomerRiskSnapshot.id == snapshot.id))

    assert fetched.risk_level == "Predicted_Balanced"
    assert fetched.investment_capacity == "Not_Available"


def test_multiple_dated_snapshots_coexist_for_one_customer(db_session):
    """A single customer must be able to have several dated snapshots at
    once (FAR-Trans's multi-dated records, per Phase 2 — 3,378 real
    customers have this) without any unique constraint blocking it."""
    customer = _make_customer(db_session)
    db_session.add_all(
        [
            CustomerRiskSnapshot(
                customer_id=customer.id,
                snapshot_date=date(2020, 1, 1),
                customer_type="Mass",
                risk_level="Conservative",
                investment_capacity="CAP_LT30K",
                data_source="FAR-Trans",
            ),
            CustomerRiskSnapshot(
                customer_id=customer.id,
                snapshot_date=date(2021, 6, 1),
                customer_type="Mass",
                risk_level="Balanced",
                investment_capacity="CAP_30K_80K",
                data_source="FAR-Trans",
            ),
        ]
    )
    db_session.flush()

    snapshots = db_session.scalars(
        select(CustomerRiskSnapshot)
        .where(CustomerRiskSnapshot.customer_id == customer.id)
        .order_by(CustomerRiskSnapshot.snapshot_date)
    ).all()

    assert len(snapshots) == 2
    assert [s.risk_level for s in snapshots] == ["Conservative", "Balanced"]

    # The relationship on Customer must see both, too.
    db_session.refresh(customer)
    assert len(customer.risk_snapshots) == 2


def test_customer_risk_snapshot_requires_a_valid_customer_id(db_session):
    """Referential integrity: an orphan customer_id must be rejected."""
    from sqlalchemy.exc import IntegrityError

    orphan = CustomerRiskSnapshot(
        customer_id=999_999_999,
        snapshot_date=date(2020, 1, 1),
        customer_type="Mass",
        risk_level="Conservative",
        investment_capacity="CAP_LT30K",
        data_source="FAR-Trans",
    )
    db_session.add(orphan)
    try:
        db_session.flush()
        raised = False
    except IntegrityError:
        raised = True
        db_session.rollback()

    assert raised, "expected a foreign key violation for a nonexistent customer_id"
