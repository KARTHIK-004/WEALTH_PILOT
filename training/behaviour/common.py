"""Shared utilities for Phase 5 behaviour-detection.

**Indicator definition, decided explicitly with the user on 2026-09-14**:
PROJECT_PLAN.md section 2.3 names "savings rate, expense ratio, contribution
rate" as the monitored indicators, but FAR-Trans has no savings/expense
data — only investment/risk-profile history (verified directly). The
indicators actually monitored here are FAR-Trans-native investment-
behaviour signals:

- **trading intensity** — monthly trade count (the direct analog of
  "how active is this customer")
- **contribution rate** — monthly Buy-transaction value (the direct analog
  of "how much are they putting into investments per month")
- **asset-allocation mix** — monthly Stock/Bond/MTF share of traded value
  (fed to the Isolation Forest layer, not univariate z-score/CUSUM — see
  detection.py)
- **risk-category / investment-capacity change** — direct comparison of
  consecutive dated `customer_information.csv` snapshots (this is the one
  indicator PROJECT_PLAN.md's own FAR-Trans justification actually
  describes: "real risk-profile drift is observable")

Literal savings rate / expense ratio are NOT computed — there is no source
data for them without the still-deferred Kaggle synthetic-assembly link.
"""

from __future__ import annotations

import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from wealthpilot.data.acquisition import FAR_TRANS_DIR

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models" / "behaviour"
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"
REPORTS_DIR = REPO_ROOT / "reports"

RANDOM_STATE = 42

# Minimum number of PRIOR months of activity required before a rolling
# baseline is considered meaningful — a customer's 1st or 2nd active month
# gets no z-score/CUSUM value (NaN), not a baseline computed from too few
# points. Chosen as a documented, defensible minimum (not zero, not an
# arbitrarily large number requiring a full year of history that would
# exclude most customers) rather than left undocumented.
MIN_PRIOR_MONTHS = 3

PANEL_FEATURES = ["trade_count", "buy_value", "pct_equity", "pct_bond", "pct_mtf"]


def load_far_trans_transactions_and_assets(far_trans_dir: Path = FAR_TRANS_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    transactions = pd.read_csv(far_trans_dir / "transactions.csv", parse_dates=["timestamp"])
    assets = pd.read_csv(far_trans_dir / "asset_information.csv")
    return transactions, assets


def load_far_trans_customers(far_trans_dir: Path = FAR_TRANS_DIR) -> pd.DataFrame:
    return pd.read_csv(
        far_trans_dir / "customer_information.csv", parse_dates=["timestamp", "lastQuestionnaireDate"]
    )


def build_monthly_panel(transactions: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    """One row per (customerID, month) with at least one transaction that
    month. Every value here uses ONLY that month's own transactions — never
    a later month's — so it is point-in-time-safe by construction; the
    rolling baseline computed on TOP of this panel (detection.py) is what
    additionally restricts itself to PRIOR months only.
    """
    txn = transactions.merge(
        assets.sort_values("timestamp").drop_duplicates("ISIN", keep="last")[["ISIN", "assetCategory"]],
        on="ISIN",
        how="left",
    )
    txn["assetCategory"] = txn["assetCategory"].fillna("Unknown")
    txn["month"] = txn["timestamp"].dt.to_period("M")

    trade_count = txn.groupby(["customerID", "month"]).size().rename("trade_count")
    buy_value = (
        txn[txn["transactionType"] == "Buy"]
        .groupby(["customerID", "month"])["totalValue"]
        .sum()
        .rename("buy_value")
    )

    value_by_cat = (
        txn.groupby(["customerID", "month", "assetCategory"])["totalValue"].sum().unstack(fill_value=0.0)
    )
    for col in ["Stock", "Bond", "MTF"]:
        if col not in value_by_cat.columns:
            value_by_cat[col] = 0.0
    cat_total = value_by_cat[["Stock", "Bond", "MTF"]].sum(axis=1)
    pct_equity = (value_by_cat["Stock"] / cat_total.replace(0, np.nan)).rename("pct_equity")
    pct_bond = (value_by_cat["Bond"] / cat_total.replace(0, np.nan)).rename("pct_bond")
    pct_mtf = (value_by_cat["MTF"] / cat_total.replace(0, np.nan)).rename("pct_mtf")

    panel = pd.concat([trade_count, buy_value, pct_equity, pct_bond, pct_mtf], axis=1)
    panel["buy_value"] = panel["buy_value"].fillna(0.0)
    panel[["pct_equity", "pct_bond", "pct_mtf"]] = panel[["pct_equity", "pct_bond", "pct_mtf"]].fillna(0.0)
    panel = panel.reset_index().sort_values(["customerID", "month"])
    return panel


def library_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
