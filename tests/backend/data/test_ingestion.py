"""Tests for wealthpilot.data.ingestion against TEST_DATABASE_URL only.

Uses the same rolled-back-transaction fixture as tests/backend/db, so
nothing is left behind. Exercises the RETURNING-based customerID -> internal
id mapping specifically, since that's the part most likely to silently
produce wrong associations if SQLAlchemy's insertmanyvalues row-ordering
guarantee were ever violated.
"""

import pandas as pd
from sqlalchemy import select

from wealthpilot.data.ingestion import (
    ingest_customer_risk_snapshots,
    ingest_customers,
    ingest_transactions,
)
from wealthpilot.db.models import Customer, CustomerRiskSnapshot, Transaction


def _customers_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"customerID": "C1", "customerType": "Mass", "riskLevel": "Conservative",
             "investmentCapacity": "CAP_LT30K", "timestamp": pd.Timestamp("2020-01-01")},
            {"customerID": "C1", "customerType": "Mass", "riskLevel": "Predicted_Balanced",
             "investmentCapacity": "CAP_LT30K", "timestamp": pd.Timestamp("2021-06-01")},
            {"customerID": "C2", "customerType": "Premium", "riskLevel": "Aggressive",
             "investmentCapacity": "CAP_GT300K", "timestamp": pd.Timestamp("2019-01-01")},
        ]
    )


def _transactions_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"customerID": "C1", "ISIN": "ISIN_STOCK", "transactionID": "T1",
             "transactionType": "Buy", "timestamp": pd.Timestamp("2020-02-01"), "totalValue": 100.0},
            {"customerID": "C2", "ISIN": "ISIN_UNKNOWN", "transactionID": "T2",
             "transactionType": "Sell", "timestamp": pd.Timestamp("2019-05-01"), "totalValue": 50.0},
        ]
    )


def _assets_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [{"ISIN": "ISIN_STOCK", "assetCategory": "Stock", "timestamp": pd.Timestamp("2018-01-02")}]
    )


def test_ingest_customers_returns_correct_id_mapping(db_session):
    id_map = ingest_customers(db_session, _customers_fixture())

    assert set(id_map.keys()) == {"C1", "C2"}

    c1 = db_session.get(Customer, id_map["C1"])
    c2 = db_session.get(Customer, id_map["C2"])

    # C1's latest row (2021) has investmentCapacity CAP_LT30K, customerType Mass.
    assert c1.customer_type == "Mass"
    assert c1.investment_capacity == "CAP_LT30K"
    assert c1.risk_inputs == {"external_customer_id": "C1"}
    assert c1.data_source == "FAR-Trans"
    assert c1.age is None and c1.income is None and c1.employment_status is None

    assert c2.customer_type == "Premium"
    assert c2.risk_inputs == {"external_customer_id": "C2"}


def test_ingest_customer_risk_snapshots_preserves_all_dated_rows_unfiltered(db_session):
    id_map = ingest_customers(db_session, _customers_fixture())
    inserted = ingest_customer_risk_snapshots(db_session, _customers_fixture(), id_map)

    assert inserted == 3  # all 3 rows, including C1's Predicted_Balanced one

    snapshots = db_session.scalars(
        select(CustomerRiskSnapshot)
        .where(CustomerRiskSnapshot.customer_id == id_map["C1"])
        .order_by(CustomerRiskSnapshot.snapshot_date)
    ).all()
    assert [s.risk_level for s in snapshots] == ["Conservative", "Predicted_Balanced"]


def test_ingest_transactions_joins_category_and_preserves_identity(db_session):
    id_map = ingest_customers(db_session, _customers_fixture())
    inserted = ingest_transactions(db_session, _transactions_fixture(), _assets_fixture(), id_map)

    assert inserted == 2

    txn_c1 = db_session.scalar(
        select(Transaction).where(Transaction.customer_id == id_map["C1"])
    )
    assert txn_c1.category == "Stock"
    assert txn_c1.external_transaction_id == "T1"
    assert txn_c1.isin == "ISIN_STOCK"

    # ISIN_UNKNOWN has no match in the assets fixture -> "Unknown", not dropped.
    txn_c2 = db_session.scalar(
        select(Transaction).where(Transaction.customer_id == id_map["C2"])
    )
    assert txn_c2.category == "Unknown"


def test_transaction_identity_is_customer_id_plus_external_id_not_external_id_alone(db_session):
    """Two different customers may legitimately share the same raw
    transactionID (the Phase 2 joint-account finding) — the unique
    constraint must allow that, keyed on (customer_id, external_transaction_id)."""
    id_map = ingest_customers(db_session, _customers_fixture())
    shared_id_txns = pd.DataFrame(
        [
            {"customerID": "C1", "ISIN": "ISIN_STOCK", "transactionID": "SHARED",
             "transactionType": "Buy", "timestamp": pd.Timestamp("2020-02-01"), "totalValue": 100.0},
            {"customerID": "C2", "ISIN": "ISIN_STOCK", "transactionID": "SHARED",
             "transactionType": "Buy", "timestamp": pd.Timestamp("2020-02-01"), "totalValue": 100.0},
        ]
    )

    inserted = ingest_transactions(db_session, shared_id_txns, _assets_fixture(), id_map)

    assert inserted == 2  # both rows accepted, no constraint violation
