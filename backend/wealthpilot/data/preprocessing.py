"""Risk-classification preprocessing and feature engineering, built from
FAR-Trans data only.

Kaggle synthetic profile assembly is deliberately NOT part of this module —
it is deferred pending a currency/matching-methodology decision (see
docs/BUILD_PLAN.md Phase 3 notes).

Two-stage design, per CLAUDE.md rule 8 ("fit preprocessors on training data
only and serialize them with the model"):

1. `engineer_features(...)` — deterministic aggregation from raw FAR-Trans
   tables to one feature row per customer. This is not an sklearn
   transformer: it holds no fitted state, so every customer's row is
   computed identically regardless of which split (train/test) it later
   falls into — there is nothing here that could leak between splits.
2. `build_preprocessing_pipeline()` — an *unfit* sklearn `Pipeline`
   (median-impute + scale numeric columns, one-hot encode categorical
   columns) over the output of (1). Phase 4 fits this on the training split
   only and serializes it alongside the trained model — this module never
   fits or serializes anything itself.

PROJECT_PLAN.md section 2.1 specifies which feature groups to compute but
not their exact windowing/weighting/aggregation. Where a choice had to be
made, it is documented here rather than picked silently:

- **One feature row per customer, not per dated snapshot.** PROJECT_PLAN.md
  frames risk classification as "predict risk category from observed
  investment behaviour" per customer, not per snapshot — using each dated
  row as a separate training example would give identical features with
  different labels for the ~3,378 customers who have multiple dated rows,
  since these behavioural features summarize a customer's history rather
  than being computed independently per snapshot.
- **Target label** = the customer's most recent GENUINE `riskLevel`
  (Conservative/Income/Balanced/Aggressive), per CLAUDE.md rule 7. A
  customer whose *latest* row is `Predicted_*`/`Not_Available` but who has
  an earlier genuine row still gets a label (their latest genuine one) —
  this is why the resulting label count matches Phase 2's genuine-label
  *customer* count (21,629), not the genuine-label *row* count (24,850).
- **Point-in-time cutoff (added after a temporal-leakage audit — see
  reports/phase3_leakage_audit.md).** For a labeled customer, the target's
  date is the `timestamp` of the genuine-labeled row that supplies the
  label — NOT `lastQuestionnaireDate`, which is inconsistent with
  `timestamp` for a large share of rows (12,501 of 32,468 rows have
  `timestamp < lastQuestionnaireDate`, by up to several thousand days) and
  is therefore not a reliable temporal anchor. Every behavioural feature
  (asset mix, trading intensity, position sizing, channel share,
  concentration) is computed **only from that customer's transactions on or
  before their target date** — never their full history. A customer with
  zero transactions before their own target date is dropped from the
  feature table entirely (there is nothing point-in-time-safe to compute),
  rather than silently backfilled with post-target data.
- **"Realized volatility of held assets" / "max drawdown of holdings"** are
  computed as *expanding* (point-in-time) statistics per ISIN — the running
  std of daily returns and the running max drawdown as of each date in
  `close_prices.csv` — then looked up "as of" each customer's target date
  via `pandas.merge_asof` (backward direction: the most recent price data
  at or before the target date, never after) before being averaged
  unweighted across the customer's distinct held ISINs. An ISIN with no
  price history at all before a customer's target date contributes no
  value for that holding (excluded from the average, not zero-filled) — a
  customer whose *only* holdings have no pre-target price history gets NaN,
  which `build_preprocessing_pipeline()`'s median imputer then handles the
  same way it handles any other missing value.
- **Customers with no genuine label** (`risk_level` is NaN in the output)
  are not point-in-time-restricted — there is no target date to leak
  *into* for them, so their full available history is used. This matters
  only for a future inference-time reuse of this function (scoring a live
  customer has no historical target either); it has no bearing on training
  safety, since Phase 4 must filter to `risk_level.notna()` before fitting
  anything, and unlabeled rows are excluded from every training-safety
  test in `tests/backend/data/test_preprocessing.py`.
- **Missing `sector`** in `asset_information.csv` (46% missing, per Phase 2)
  is bucketed as `"Unknown"` rather than dropped, so top-sector-share is
  still computable for every customer.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from wealthpilot.data.acquisition import FAR_TRANS_DIR

GENUINE_RISK_LEVELS = ["Conservative", "Income", "Balanced", "Aggressive"]

NUMERIC_FEATURES = [
    "pct_value_stock",
    "pct_value_bond",
    "pct_value_mtf",
    "equity_to_bond_ratio",
    "trades_per_year",
    "buy_sell_ratio",
    "active_months",
    "position_size_mean",
    "position_size_median",
    "position_size_std",
    "largest_trade_pct_of_total",
    "realized_volatility",
    "max_drawdown",
    "herfindahl_index",
    "top_sector_share",
    "pct_channel_internet",
    "pct_channel_phone",
    "pct_channel_branch",
]
CATEGORICAL_FEATURES = ["customer_type", "investment_capacity"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_far_trans_tables(far_trans_dir: Path = FAR_TRANS_DIR) -> dict[str, pd.DataFrame]:
    """Read the raw CSVs needed for feature engineering. Read-only."""
    customers = pd.read_csv(
        far_trans_dir / "customer_information.csv",
        parse_dates=["lastQuestionnaireDate", "timestamp"],
    )
    assets = pd.read_csv(far_trans_dir / "asset_information.csv")
    transactions = pd.read_csv(far_trans_dir / "transactions.csv", parse_dates=["timestamp"])
    close_prices = pd.read_csv(far_trans_dir / "close_prices.csv", parse_dates=["timestamp"])
    return {
        "customers": customers,
        "assets": assets,
        "transactions": transactions,
        "close_prices": close_prices,
    }


def _latest_genuine_risk_rows(customers: pd.DataFrame) -> pd.DataFrame:
    """Each genuine-labeled customer's latest such row — the single source
    of their label, their point-in-time cutoff (the row's `timestamp`), AND
    their customer_type/investment_capacity as of that same row. Using this
    one row for all three prevents the customer_type/investment_capacity
    columns from silently drifting ahead of the target date the way a
    separately-computed "latest row overall" would (customerType/
    investmentCapacity happen not to differ between the two in the current
    FAR-Trans data — verified directly, not assumed — but deriving all
    three from one row makes that a non-issue by construction rather than
    a coincidence future data would need to keep being true)."""
    genuine = customers[customers["riskLevel"].isin(GENUINE_RISK_LEVELS)]
    return genuine.sort_values("timestamp").groupby("customerID").tail(1).set_index("customerID")


def _latest_genuine_risk_labels(customers: pd.DataFrame) -> pd.Series:
    return _latest_genuine_risk_rows(customers)["riskLevel"].rename("risk_level")


def target_dates(customers: pd.DataFrame) -> pd.Series:
    """customerID -> the point-in-time cutoff date for that customer's
    target label (the `timestamp` of their latest genuine-labeled row).
    Exposed (not prefixed `_`) so tests can assert against it directly.
    """
    return _latest_genuine_risk_rows(customers)["timestamp"].rename("target_date")


def _customer_attributes(customers: pd.DataFrame) -> pd.DataFrame:
    """customer_type / investment_capacity per customer.

    For a genuine-labeled customer these come from their target row (the
    same row supplying the label and the cutoff date) — never from a
    separately-computed "latest row overall", which could reflect a
    post-target-date change. Only a customer with NO genuine label falls
    back to their latest row overall, since there is no target date to be
    consistent with for them.
    """
    genuine_attrs = _latest_genuine_risk_rows(customers)[["customerType", "investmentCapacity"]]
    unlabeled_ids = customers.loc[~customers["customerID"].isin(genuine_attrs.index), "customerID"].unique()
    latest_overall = (
        customers.sort_values("timestamp").groupby("customerID").tail(1).set_index("customerID")
    )
    fallback_attrs = latest_overall.loc[
        latest_overall.index.intersection(unlabeled_ids), ["customerType", "investmentCapacity"]
    ]

    attrs = pd.concat([genuine_attrs, fallback_attrs])
    return attrs.rename(columns={"customerType": "customer_type", "investmentCapacity": "investment_capacity"})


def _deduplicated_assets(assets: pd.DataFrame) -> pd.DataFrame:
    """asset_information.csv has 28 ISINs with more than one row (Phase 2);
    3 of those (IE00B66F4759, IE00BCRY6003, LU0055631609) even disagree on
    `assetCategory` between their duplicate rows. Joining transactions
    against `assets` without deduplicating first multiplies every affected
    transaction row once per duplicate (13,157 transaction rows touch a
    duplicated ISIN) — a real correctness bug, not a temporal-leakage one,
    found during the Phase 3 leakage audit. Keeping each ISIN's latest row
    (by `timestamp`) is a reasonable, low-stakes default: `assetCategory` is
    a structural classification that essentially never legitimately changes
    for a security, so this is a data-quality inconsistency to note, not a
    point-in-time feature to build out for 3 of 836 assets.
    """
    return assets.sort_values("timestamp").drop_duplicates("ISIN", keep="last")


def _asset_mix_features(transactions: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    txn = transactions.merge(
        _deduplicated_assets(assets)[["ISIN", "assetCategory", "sector"]], on="ISIN", how="left"
    )
    txn["sector"] = txn["sector"].fillna("Unknown")
    txn.loc[txn["sector"].astype(str).str.strip() == "", "sector"] = "Unknown"

    value_by_category = (
        txn.groupby(["customerID", "assetCategory"])["totalValue"].sum().unstack(fill_value=0.0)
    )
    for col in ["Stock", "Bond", "MTF"]:
        if col not in value_by_category.columns:
            value_by_category[col] = 0.0
    total_value = value_by_category[["Stock", "Bond", "MTF"]].sum(axis=1)

    out = pd.DataFrame(index=value_by_category.index)
    out["pct_value_stock"] = np.where(total_value > 0, value_by_category["Stock"] / total_value, 0.0)
    out["pct_value_bond"] = np.where(total_value > 0, value_by_category["Bond"] / total_value, 0.0)
    out["pct_value_mtf"] = np.where(total_value > 0, value_by_category["MTF"] / total_value, 0.0)
    out["equity_to_bond_ratio"] = np.where(
        value_by_category["Bond"] > 0,
        value_by_category["Stock"] / value_by_category["Bond"],
        value_by_category["Stock"],
    )

    sector_value = txn.groupby(["customerID", "sector"])["totalValue"].sum()
    top_sector = sector_value.groupby("customerID").max()
    customer_total = txn.groupby("customerID")["totalValue"].sum()
    out["top_sector_share"] = (top_sector / customer_total).reindex(out.index).fillna(0.0)

    isin_value = txn.groupby(["customerID", "ISIN"])["totalValue"].sum()

    def herfindahl(group: pd.Series) -> float:
        total = group.sum()
        if total <= 0:
            return 0.0
        shares = group / total
        return float((shares**2).sum())

    out["herfindahl_index"] = isin_value.groupby("customerID").apply(herfindahl).reindex(out.index).fillna(0.0)

    return out


def _trading_intensity_features(transactions: pd.DataFrame) -> pd.DataFrame:
    grouped = transactions.groupby("customerID")

    span_days = (grouped["timestamp"].max() - grouped["timestamp"].min()).dt.days.clip(lower=1)
    years = (span_days / 365.25).clip(lower=1 / 365.25)
    trade_count = grouped.size()

    buy_count = transactions[transactions["transactionType"] == "Buy"].groupby("customerID").size()
    sell_count = transactions[transactions["transactionType"] == "Sell"].groupby("customerID").size()
    buy_count = buy_count.reindex(trade_count.index, fill_value=0)
    sell_count = sell_count.reindex(trade_count.index, fill_value=0)

    active_months = grouped["timestamp"].apply(lambda s: s.dt.to_period("M").nunique())

    out = pd.DataFrame(index=trade_count.index)
    out["trades_per_year"] = trade_count / years
    out["buy_sell_ratio"] = np.where(sell_count > 0, buy_count / sell_count, buy_count.astype(float))
    out["active_months"] = active_months
    return out


def _position_sizing_features(transactions: pd.DataFrame) -> pd.DataFrame:
    grouped = transactions.groupby("customerID")["totalValue"]
    out = pd.DataFrame(index=grouped.mean().index)
    out["position_size_mean"] = grouped.mean()
    out["position_size_median"] = grouped.median()
    out["position_size_std"] = grouped.std().fillna(0.0)

    customer_total = transactions.groupby("customerID")["totalValue"].sum()
    largest_trade = transactions.groupby("customerID")["totalValue"].max()
    out["largest_trade_pct_of_total"] = np.where(
        customer_total > 0, largest_trade / customer_total, 0.0
    )
    return out


def _channel_features(transactions: pd.DataFrame) -> pd.DataFrame:
    counts = transactions.groupby(["customerID", "channel"]).size().unstack(fill_value=0)
    for col in ["Internet Banking", "Phone Banking", "Branch"]:
        if col not in counts.columns:
            counts[col] = 0
    total = counts[["Internet Banking", "Phone Banking", "Branch"]].sum(axis=1)

    out = pd.DataFrame(index=counts.index)
    out["pct_channel_internet"] = np.where(total > 0, counts["Internet Banking"] / total, 0.0)
    out["pct_channel_phone"] = np.where(total > 0, counts["Phone Banking"] / total, 0.0)
    out["pct_channel_branch"] = np.where(total > 0, counts["Branch"] / total, 0.0)
    return out


def _risk_exposure_features(
    transactions: pd.DataFrame, close_prices: pd.DataFrame, as_of_dates: pd.Series
) -> pd.DataFrame:
    """Per-customer average realized volatility and max drawdown across held
    ISINs, computed point-in-time as of each customer's `as_of_dates[customerID]`.

    Volatility and drawdown are computed once per ISIN as *expanding*
    (running) statistics — the value at each date uses only price data up
    to and including that date — then looked up "as of" each customer's
    date via `merge_asof` (backward: the most recent available value at or
    before that date, never after). This is what makes the lookup
    point-in-time-safe without an O(holdings x price rows) computation: the
    expensive expanding statistics are computed once per ISIN regardless of
    how many customers hold it or what their individual cutoff dates are.

    A held ISIN with no price history at all before a customer's as_of date
    contributes NaN for that holding, which pandas' `.mean()` correctly
    excludes rather than treating as zero.
    """
    prices = close_prices.sort_values(["ISIN", "timestamp"]).copy()
    prices["return"] = prices.groupby("ISIN")["closePrice"].pct_change()
    prices["running_volatility"] = (
        prices.groupby("ISIN")["return"].expanding().std().reset_index(level=0, drop=True)
    )
    prices["running_max"] = prices.groupby("ISIN")["closePrice"].cummax()
    drawdown = (prices["closePrice"] - prices["running_max"]) / prices["running_max"]
    prices["running_max_drawdown"] = drawdown.groupby(prices["ISIN"]).cummin()

    held = transactions[["customerID", "ISIN"]].drop_duplicates().copy()
    held["as_of_date"] = held["customerID"].map(as_of_dates)

    price_lookup = prices[["ISIN", "timestamp", "running_volatility", "running_max_drawdown"]]
    matched = pd.merge_asof(
        held.sort_values("as_of_date"),
        price_lookup.sort_values("timestamp"),
        left_on="as_of_date",
        right_on="timestamp",
        by="ISIN",
        direction="backward",
    )

    out = matched.groupby("customerID")[["running_volatility", "running_max_drawdown"]].mean()
    out = out.rename(
        columns={"running_volatility": "realized_volatility", "running_max_drawdown": "max_drawdown"}
    )
    return out


def _point_in_time_transactions(transactions: pd.DataFrame, as_of_dates: pd.Series) -> pd.DataFrame:
    """Restrict transactions to each customer's own as-of date.

    A customer absent from `as_of_dates` (no genuine label) keeps their
    full transaction history — there is no target date to leak into for
    them (see the module docstring's point-in-time-cutoff note).
    """
    cutoff = transactions["customerID"].map(as_of_dates)
    visible = cutoff.isna() | (transactions["timestamp"] <= cutoff)
    return transactions[visible]


def engineer_features(
    customers: pd.DataFrame,
    transactions: pd.DataFrame,
    assets: pd.DataFrame,
    close_prices: pd.DataFrame,
) -> pd.DataFrame:
    """Build one feature row per customer who has at least one transaction
    on or before their own point-in-time cutoff.

    Returns a DataFrame indexed by customerID with columns
    `ALL_FEATURES + ["risk_level", "target_date"]`. `risk_level` and
    `target_date` are both NaN/NaT for customers with no genuine label
    (kept for potential inference-time feature building, where there is no
    label or target date at all — never used for training).

    A genuine-labeled customer with zero transactions on or before their
    own target date is absent from the returned table entirely — there is
    nothing point-in-time-safe to compute for them, and silently including
    them would mean either fabricating a placeholder or falling back to
    post-target data, both of which are exactly what this function exists
    to avoid. See reports/phase3_leakage_audit.md for how many customers
    this affects.
    """
    labels = _latest_genuine_risk_labels(customers)
    cutoffs = target_dates(customers)

    visible_transactions = _point_in_time_transactions(transactions, cutoffs)

    # as-of date for market-feature lookups: the target date for labeled
    # customers, else that customer's own latest visible transaction date
    # (there is no target to be point-in-time-safe against, so "as of their
    # most recent known activity" is the natural stand-in).
    fallback_as_of = visible_transactions.groupby("customerID")["timestamp"].max()
    as_of_dates = cutoffs.combine_first(fallback_as_of)

    parts = [
        _asset_mix_features(visible_transactions, assets),
        _trading_intensity_features(visible_transactions),
        _position_sizing_features(visible_transactions),
        _channel_features(visible_transactions),
        _risk_exposure_features(visible_transactions, close_prices, as_of_dates),
    ]
    features = parts[0]
    for part in parts[1:]:
        features = features.join(part, how="outer")

    attrs = _customer_attributes(customers)
    features = features.join(attrs, how="left")
    features = features.join(labels, how="left")
    features = features.join(cutoffs, how="left")

    features.index.name = "customerID"
    return features[ALL_FEATURES + ["risk_level", "target_date"]]


def build_preprocessing_pipeline() -> ColumnTransformer:
    """An *unfit* preprocessor: median-impute + scale numeric columns,
    most-frequent-impute + one-hot encode categorical columns.

    Phase 4 fits this on the training split only and serializes it
    alongside the trained model (CLAUDE.md rule 8) — never fit here.
    """
    numeric_pipeline = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ]
    )
