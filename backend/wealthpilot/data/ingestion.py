"""Real-data ingestion: FAR-Trans -> PostgreSQL.

Scope for Phase 3 (synthetic assembly is deferred — see docs/BUILD_PLAN.md
Phase 3 notes):

- `customers`: one row per unique FAR-Trans customerID, identity + the
  FAR-Trans-derived fields only (customer_type, investment_capacity, taken
  from that customer's LATEST dated record). `age`/`income`/
  `employment_status` are left NULL — FAR-Trans has no such data, and
  filling them in requires the deferred Kaggle synthetic-assembly step; NULL
  here is honest, not a fabricated value. `name` is a deterministic,
  transparent label built from the real customerID
  (`"FAR-Trans Customer {customerID}"`), never a fabricated human name. The
  real customerID is also stored in `risk_inputs` (an existing nullable JSON
  column — reused rather than adding a new schema column for this) as
  `{"external_customer_id": ...}`, so a FAR-Trans customer can be looked up
  by their real ID later without adding a new column.
- `customer_risk_snapshots`: every one of FAR-Trans's 32,468 dated
  `customer_information.csv` rows, unfiltered — including
  `Predicted_*`/`Not_Available` — linked to the seeded customer.
- `transactions`: every one of FAR-Trans's 388,048 transaction rows.
  `category` is the asset's `assetCategory` (Stock/Bond/MTF), joined in from
  `asset_information.csv` on ISIN (missing category is stored as "Unknown",
  matching the same convention `preprocessing.py` uses for missing sector).
  `external_transaction_id`/`isin` are preserved so `(customer_id,
  external_transaction_id)` — the transaction identity found in Phase 2 —
  is the table's actual unique key, enforced by the Phase 3 migration.

`financial_goals` and `market_data` are intentionally NOT populated here:
`financial_goals` has no real source in either raw dataset and is never
fabricated (CLAUDE.md: never invent customer attributes); `market_data` can
only come from yfinance, which is Phase 6's job in full (clarified
2026-09-13 in docs/BUILD_PLAN.md).
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

from wealthpilot.db.models import Customer, CustomerRiskSnapshot, Transaction

CHUNK_SIZE = 5_000


def _chunks(rows: list[dict], size: int = CHUNK_SIZE):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def ingest_customers(session: Session, customers_df: pd.DataFrame) -> dict[str, int]:
    """Seed one `customers` row per unique FAR-Trans customerID.

    Returns a dict mapping the original customerID to the new internal
    `customers.id`, for use by the other ingestion functions.
    """
    latest = customers_df.sort_values("timestamp").groupby("customerID").tail(1)

    rows = [
        {
            "name": f"FAR-Trans Customer {row.customerID}",
            "age": None,
            "income": None,
            "employment_status": None,
            "customer_type": row.customerType,
            "investment_capacity": row.investmentCapacity,
            "risk_inputs": {"external_customer_id": row.customerID},
            "data_source": "FAR-Trans",
        }
        for row in latest.itertuples()
    ]
    external_ids = latest["customerID"].tolist()

    id_map: dict[str, int] = {}
    for chunk_rows, chunk_ids in zip(_chunks(rows), _chunks(external_ids), strict=True):
        result = session.execute(insert(Customer).returning(Customer.id), chunk_rows)
        # SQLAlchemy's insertmanyvalues preserves input/output row order.
        new_ids = [row[0] for row in result]
        id_map.update(dict(zip(chunk_ids, new_ids, strict=True)))

    session.flush()
    return id_map


def ingest_customer_risk_snapshots(
    session: Session, customers_df: pd.DataFrame, customer_id_map: dict[str, int]
) -> int:
    """Insert every dated FAR-Trans row, unfiltered, into customer_risk_snapshots."""
    rows = [
        {
            "customer_id": customer_id_map[row.customerID],
            "snapshot_date": row.timestamp.date(),
            "customer_type": row.customerType,
            "risk_level": row.riskLevel,
            "investment_capacity": row.investmentCapacity,
            "data_source": "FAR-Trans",
        }
        for row in customers_df.itertuples()
    ]

    inserted = 0
    for chunk in _chunks(rows):
        session.execute(insert(CustomerRiskSnapshot), chunk)
        inserted += len(chunk)
    session.flush()
    return inserted


def ingest_transactions(
    session: Session,
    transactions_df: pd.DataFrame,
    assets_df: pd.DataFrame,
    customer_id_map: dict[str, int],
) -> int:
    """Insert every FAR-Trans transaction row.

    `category` comes from joining assetCategory on ISIN; a missing/unmatched
    ISIN is stored as "Unknown" (same convention as preprocessing.py's
    missing-sector handling), never dropped. `assets_df` is deduplicated on
    ISIN (keeping the latest row) before building the lookup — 28 ISINs
    have more than one row in asset_information.csv, and 3 of those
    disagree on assetCategory between rows (found during the Phase 3
    leakage audit); without deduplicating, a plain
    `set_index("ISIN").to_dict()` would pick whichever duplicate happens to
    be processed last, non-deterministically.
    """
    deduplicated_assets = assets_df.sort_values("timestamp").drop_duplicates("ISIN", keep="last")
    category_by_isin = deduplicated_assets.set_index("ISIN")["assetCategory"].to_dict()

    rows = [
        {
            "customer_id": customer_id_map[row.customerID],
            "external_transaction_id": row.transactionID,
            "isin": row.ISIN,
            "transaction_date": row.timestamp,
            "category": category_by_isin.get(row.ISIN, "Unknown"),
            "amount": row.totalValue,
            "transaction_type": row.transactionType,
            "data_source": "FAR-Trans",
        }
        for row in transactions_df.itertuples()
    ]

    inserted = 0
    for chunk in _chunks(rows):
        session.execute(insert(Transaction), chunk)
        inserted += len(chunk)
    session.flush()
    return inserted
