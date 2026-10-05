"""Validates the WealthPilot AI synthetic training dataset in `datasets/generated/` (ADR-039).

USAGE (repo root, venv active):

    python scripts/validate_synthetic_training_dataset.py      # exit 0 = pass, 1 = fail

It reads only the generated files (plus, read-only, the raw FAR-Trans customer
IDs to prove no ID overlaps, and the demo package manifest's raw-data hashes).
No database. It checks, and reports:

- file format: UTF-8, comma-delimited, one header row, no duplicate columns, no
  embedded newlines, no NaN/Infinity/null strings, no spreadsheet formulas;
- row / column counts, duplicate rows, null rates, label distributions, date ranges;
- customers: unique synthetic IDs, vocabularies, non-negative amounts, and every
  sum and ratio recomputed from its source columns; income = expenses + EMI +
  savings; the allocation totals 100%; the emergency fund matches the
  production rule (6 months of essential expenses);
- transactions: value = quantity x price, price = the market close that day,
  holdings never negative, dates in order and after onboarding, weights in (0, 1];
- point-in-time behaviour features: re-computed from transactions on or before
  each customer's cutoff and compared (post-cutoff activity must not leak in);
- goals: unique IDs and priorities, amounts / status / contributions consistent,
  feasibility = the production thresholds, and a sample re-run through the
  production goal engine using a return series rebuilt from the published prices;
- cross-file referential integrity;
- leakage: no single feature predicts risk_label with > 70% accuracy, no single
  feature gives behavior_anomaly an AUC > 0.995 (targets and engine outputs excluded);
- the EXISTING pipelines read the format copies unchanged: FAR-Trans loader +
  `engineer_features` + `build_monthly_panel`, Kaggle loader + `engineer_expense_features`;
- the raw training datasets still match the recorded SHA-256 hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from wealthpilot.core.goals import (  # noqa: E402
    AT_RISK_THRESHOLD,
    EMERGENCY_FUND_TARGET_MONTHS,
    FEASIBLE_THRESHOLD,
    GoalAssumptions,
    GoalInput,
    analyze_goal_funding,
    run_goal_monte_carlo,
)

DATA_DIR = REPO_ROOT / "datasets" / "generated"
CUSTOMER_FILE = "wealthpilot_customer_training.csv"
TRANSACTION_FILE = "wealthpilot_transactions_training.csv"
GOAL_FILE = "wealthpilot_goals_training.csv"
METADATA_FILE = "wealthpilot_training_metadata.json"
FAR_TRANS_FILES = ["customer_information.csv", "asset_information.csv", "transactions.csv", "close_prices.csv"]
KAGGLE_FILE = "kaggle_format/synthetic_personal_finance_dataset.csv"
MIN_CUSTOMERS, MIN_TRANSACTIONS, MIN_GOALS = 100_000, 2_000_000, 300_000
START, END = "2019-01-01", "2024-12-31"

VOCAB = {
    "employment_status": {"Employed", "Self-employed", "Unemployed", "Student", "Retired"},
    "city_tier": {"Tier 1", "Tier 2", "Tier 3"},
    "housing_status": {"Living with family", "Rented", "Owned with mortgage", "Owned outright"},
    "debt_profile": {"debt-free", "low", "moderate", "high"},
    "investor_type": {"inactive", "occasional", "regular_sip", "highly_active"},
    "education_level": {"High School", "Bachelor", "Master", "PhD", "Other"},
    "marital_status": {"Single", "Married", "Divorced", "Widowed"},
    "customer_type": {"Mass", "Premium", "Professional"},
    "investment_capacity": {"CAP_LT30K", "CAP_30K_80K", "CAP_80K_300K", "CAP_GT300K"},
    "investment_experience": {"No experience", "Beginner", "Intermediate", "Advanced"},
    "loss_tolerance": {"Low", "Medium", "High"},
    "emergency_fund_status": {"sufficient", "insufficient"},
    "risk_label": {"Conservative", "Income", "Balanced", "Aggressive"},
    "expense_segment": {"low-expense-low-leverage-higher-savings", "moderate-expense-low-leverage-moderate-savings",
                        "high-expense-low-leverage-lower-savings", "moderate-expense-high-leverage-lower-savings"},
}
OPTIONAL_CUSTOMER_COLUMNS = {"education_level", "marital_status", "employment_years", "income_growth_rate",
                             "income_source_count", "income_stability_score", "savings_stability",
                             "investment_experience", "loss_tolerance", "credit_utilization", "behavior_anomaly_month",
                             "portfolio_turnover", "average_transaction_value", "behaviour_volatility"}
EXPENSE_COMPONENTS = ["housing_expense", "food_expense", "transport_expense", "healthcare_expense",
                      "education_expense", "utilities_expense", "insurance_expense", "discretionary_expense",
                      "other_expense"]
NON_NEGATIVE = ["annual_income", "monthly_income", "monthly_expenses", *EXPENSE_COMPONENTS,
                "monthly_essential_expenses", "total_debt", "monthly_emi", "credit_card_debt", "credit_card_limit",
                "personal_loan_debt", "home_loan_debt", "auto_loan_debt", "cash_savings", "liquid_assets",
                "investment_contribution", "investment_portfolio_value", "emergency_fund_required", "trade_count",
                "buy_value", "sell_value", "dependents", "age"]
NOT_FEATURES = {"customer_id", "data_source", "onboarding_date", "feature_cutoff_date", "risk_label",
                "expense_segment", "behavior_anomaly", "behavior_anomaly_month"}
BAD_TOKEN = re.compile(r"(?:^|,)(?:nan|-?inf(?:inity)?|null|none|n/a|#n/a)(?=,|$)", re.IGNORECASE)
FORMULA = re.compile(r"(?:^|,)(?:[=+@]|-(?![0-9.]))")


class Checks:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.report: dict = {}

    def require(self, ok, message: str) -> None:
        if not bool(ok):
            self.errors.append(message)


def _py(obj):
    """JSON-safe copy (numpy scalars -> Python)."""
    if isinstance(obj, dict):
        return {str(k): _py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_py(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# File format
# ---------------------------------------------------------------------------


def check_format(path: Path, rel: str, ck: Checks) -> int:
    """One streaming pass: UTF-8, one header, no duplicate columns, no bad tokens or formulas. Returns data rows."""
    lines = 0
    bad = formula = repeated_header = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        header = handle.readline()
        columns = header.rstrip("\n").split(",")
        ck.require(len(columns) == len(set(columns)), f"{rel}: duplicate column names")
        for line in handle:
            lines += 1
            text = line.rstrip("\n")
            if text == header.rstrip("\n"):
                repeated_header += 1
            if BAD_TOKEN.search(text):
                bad += 1
            if FORMULA.search(text):
                formula += 1
    ck.require(repeated_header == 0, f"{rel}: the header row appears {repeated_header} more time(s)")
    ck.require(bad == 0, f"{rel}: {bad} line(s) contain a NaN/Infinity/null-like token")
    ck.require(formula == 0, f"{rel}: {formula} line(s) contain a spreadsheet-formula-like cell")
    return lines


def _close(a, b, tol: float) -> np.ndarray:
    return np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) <= tol


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


def check_customers(c: pd.DataFrame, ck: Checks, raw_far_trans_ids: set[str]) -> None:
    n = len(c)
    ck.require(n >= MIN_CUSTOMERS, f"customers: {n:,} rows (< {MIN_CUSTOMERS:,})")
    ck.require(c["customer_id"].is_unique, "customers: customer_id is not unique")
    ck.require(c["customer_id"].str.fullmatch(r"SYN\d{6}").all(), "customers: an ID is outside the SYN000001 namespace")
    ck.require(not (set(c["customer_id"]) & raw_far_trans_ids), "customers: an ID overlaps a FAR-Trans customer ID")
    ck.require(c.duplicated().sum() == 0, "customers: duplicate rows")
    ck.require((c["data_source"] == "synthetic_generated").all(), "customers: data_source must be synthetic_generated")
    for column in c.columns:
        if column not in OPTIONAL_CUSTOMER_COLUMNS:
            ck.require(c[column].notna().all(), f"customers: mandatory column {column} has missing values")
    for column, allowed in VOCAB.items():
        extra = set(c[column].dropna().unique()) - allowed
        ck.require(not extra, f"customers: {column} has unexpected values {sorted(extra)[:5]}")
    for column in NON_NEGATIVE:
        ck.require((c[column].dropna() >= 0).all(), f"customers: {column} has a negative value")

    rules = {
        "monthly_income = annual_income / 12": _close(c.monthly_income, (c.annual_income / 12).round(2), 0.0051),
        "monthly_expenses = sum of its 9 components": _close(c.monthly_expenses, c[EXPENSE_COMPONENTS].sum(axis=1), 0.011),
        "monthly_essential_expenses = housing..insurance": _close(
            c.monthly_essential_expenses, c[EXPENSE_COMPONENTS[:7]].sum(axis=1), 0.011),
        "monthly_savings = monthly_income - monthly_expenses - monthly_emi": _close(
            c.monthly_savings, c.monthly_income - c.monthly_expenses - c.monthly_emi, 0.011),
        "total_debt = card + personal + home + auto": _close(
            c.total_debt, c[["credit_card_debt", "personal_loan_debt", "home_loan_debt", "auto_loan_debt"]].sum(axis=1),
            0.011),
        "debt_to_income_ratio = total_debt / annual_income": _close(c.debt_to_income_ratio, c.total_debt / c.annual_income, 2e-6),
        "emi_to_income_ratio = monthly_emi / monthly_income": _close(c.emi_to_income_ratio, c.monthly_emi / c.monthly_income, 2e-6),
        "savings_rate = monthly_savings / monthly_income": _close(c.savings_rate, c.monthly_savings / c.monthly_income, 2e-6),
        "expense_to_income_ratio = monthly_expenses / monthly_income": _close(
            c.expense_to_income_ratio, c.monthly_expenses / c.monthly_income, 2e-6),
        "savings_to_income_ratio = cash_savings / annual_income": _close(
            c.savings_to_income_ratio, c.cash_savings / c.annual_income, 2e-6),
        "liquidity_ratio = liquid_assets / monthly_expenses": _close(
            c.liquidity_ratio, c.liquid_assets / c.monthly_expenses, 2e-6),
        "discretionary_expense_ratio = discretionary / monthly_expenses": _close(
            c.discretionary_expense_ratio, c.discretionary_expense / c.monthly_expenses, 2e-6),
        "investment_ratio = investment_contribution / monthly_income": _close(
            c.investment_ratio, c.investment_contribution / c.monthly_income, 2e-6),
        "liquid_assets >= cash_savings": c.liquid_assets >= c.cash_savings - 1e-9,
        "investment_contribution <= positive monthly savings": c.investment_contribution <= c.monthly_savings.clip(lower=0) + 0.0051,
        "emergency_fund_required = 6 x essential expenses (production rule)": _close(
            c.emergency_fund_required, c.monthly_essential_expenses * EMERGENCY_FUND_TARGET_MONTHS, 0.011),
        "emergency_fund_target_months = production constant": c.emergency_fund_target_months == EMERGENCY_FUND_TARGET_MONTHS,
        "emergency_fund_months = liquid_assets / essential expenses": _close(
            c.emergency_fund_months, c.liquid_assets / c.monthly_essential_expenses, 6e-5),
        "emergency_fund_status matches liquid vs required": (
            (c.emergency_fund_status == "sufficient") == (c.liquid_assets >= c.monthly_essential_expenses * EMERGENCY_FUND_TARGET_MONTHS))
        | _close(c.liquid_assets, c.emergency_fund_required, 0.011),
        "allocation totals 100%": _close(c[["equity_pct", "bond_pct", "gold_pct", "cash_pct", "other_pct"]].sum(axis=1), 100, 0.011),
        "allocation shares are 0..100": c[["equity_pct", "bond_pct", "gold_pct", "cash_pct", "other_pct"]].ge(0).all(axis=1),
        "credit_utilization empty exactly when there is no card": c.credit_utilization.isna() == (c.credit_card_limit == 0),
        "credit_utilization = card debt / limit, within 0..1": c.credit_utilization.isna() | (
            _close(c.credit_utilization, c.credit_card_debt / c.credit_card_limit.replace(0, np.nan), 2e-6)
            & c.credit_utilization.between(0, 1)),
        "onboarding_date <= feature_cutoff_date": c.onboarding_date <= c.feature_cutoff_date,
        "behavior_anomaly_month present exactly when behavior_anomaly = 1": c.behavior_anomaly_month.notna() == (c.behavior_anomaly == 1),
        "anomaly month inside the observation window": c.behavior_anomaly_month.isna() | (
            (c.behavior_anomaly_month >= c.onboarding_date.str[:7]) & (c.behavior_anomaly_month <= c.feature_cutoff_date.str[:7])),
        "a mortgage exists exactly when housing_status is 'Owned with mortgage'": (c.home_loan_debt > 0) == (
            c.housing_status == "Owned with mortgage"),
        "no dependents -> no education expense": (c.dependents > 0) | (c.education_expense == 0),
        "debt_profile matches total_debt and the EMI-to-income bands": c.debt_profile == np.select(
            [c.total_debt == 0, c.emi_to_income_ratio < 0.15, c.emi_to_income_ratio < 0.35],
            ["debt-free", "low", "moderate"], "high"),
        "inactive investors have no trades before the cutoff": (c.investor_type != "inactive") | (c.trade_count == 0),
        "trade ratios empty exactly when there are no trades": (c.trade_count == 0) == c.average_transaction_value.isna(),
        "annual_income within 0.25 lakh .. 5 crore": c.annual_income.between(25_000, 50_000_000),
    }
    consistency = {}
    for name, ok in rules.items():
        failures = int((~np.asarray(ok, dtype=bool)).sum())
        consistency[name] = "ok" if failures == 0 else f"{failures} row(s) fail"
        ck.require(failures == 0, f"customers: {name} fails on {failures} row(s)")
    ck.report["customer_consistency"] = consistency
    no_earnings = c["employment_status"].isin(["Unemployed", "Retired"])
    emi_over = c["monthly_emi"] > c["monthly_income"]
    debt_over = c["total_debt"] > 8 * c["annual_income"]
    ck.report["debt_edge_cases"] = {
        "emi_above_income": int(emi_over.sum()),
        "emi_above_income_by_status": c.loc[emi_over, "employment_status"].value_counts().to_dict(),
        "debt_above_8x_income": int(debt_over.sum()),
        "debt_above_8x_income_by_status": c.loc[debt_over, "employment_status"].value_counts().to_dict(),
        "why": "debt originated on an earlier, higher (career) income; income fell after unemployment or retirement",
    }
    ck.require(not (emi_over & ~no_earnings).any(),
               "customers: EMI above income for a customer who is employed / self-employed / a student")
    ck.require(not (debt_over & ~no_earnings).any(),
               "customers: debt above 8x income for a customer who is employed / self-employed / a student")
    top_share = float(c["annual_income"].value_counts(normalize=True).iloc[0])
    ck.report["annual_income_most_common_value_share"] = round(top_share, 5)
    ck.require(top_share <= 0.002, f"customers: one annual_income value covers {top_share:.2%} of customers "
                                   "(a placeholder-like pile-up)")
    shares = c["risk_label"].value_counts(normalize=True)
    ck.require(shares.min() >= 0.05, "risk_label: a class has under 5% of customers (too few for training)")
    rate = float(c["behavior_anomaly"].mean())
    ck.require(0.005 <= rate <= 0.10, f"behavior_anomaly: rate {rate:.4f} outside 0.5%..10%")


# ---------------------------------------------------------------------------
# Transactions (+ point-in-time behaviour features)
# ---------------------------------------------------------------------------


def check_transactions(t: pd.DataFrame, c: pd.DataFrame, close: pd.DataFrame, asset_ids: set[str], ck: Checks) -> None:
    n = len(t)
    ck.require(n >= MIN_TRANSACTIONS, f"transactions: {n:,} rows (< {MIN_TRANSACTIONS:,})")
    ck.require(t["transaction_id"].is_unique, "transactions: transaction_id is not unique")
    ck.require(t.duplicated().sum() == 0, "transactions: duplicate rows")
    ck.require(t["customer_id"].isin(c["customer_id"]).all(), "transactions: a customer_id has no customer row")
    ck.require(set(t["asset_id"].astype(str).unique()) <= asset_ids, "transactions: an asset_id is not in asset_information")
    ck.require(t.notna().all().all(), "transactions: missing values")
    dates = t["transaction_date"].astype(str)
    ck.require(dates.is_monotonic_increasing, "transactions: rows are not in date order")
    ck.require((dates.min() >= START) and (dates.max() <= END), "transactions: a date is outside 2019-01-01..2024-12-31")
    onboarding = t["customer_id"].map(c.set_index("customer_id")["onboarding_date"])
    ck.require((dates >= onboarding).all(), "transactions: a transaction precedes its customer's onboarding")
    buy = t["transaction_type"] == "Buy"
    ck.require(t["transaction_type"].isin(["Buy", "Sell"]).all(), "transactions: unexpected transaction_type")
    ck.require(((t["buy_sell_indicator"] == 1) == buy).all() and t["buy_sell_indicator"].isin([1, -1]).all(),
               "transactions: buy_sell_indicator does not match transaction_type")
    ck.require((t[["quantity", "price", "transaction_value"]] > 0).all().all(), "transactions: a non-positive quantity/price/value")
    ck.require(_close(t["transaction_value"], (t["quantity"] * t["price"]).round(2), 0.011).all(),
               "transactions: transaction_value != quantity x price")
    ck.require(t["portfolio_weight"].between(1e-12, 1.0).all(), "transactions: portfolio_weight outside (0, 1]")
    ck.require(t["channel"].isin(["Internet Banking", "Branch", "Phone Banking"]).all(), "transactions: unexpected channel")
    priced = t[["asset_id", "transaction_date", "price"]].merge(
        close, left_on=["asset_id", "transaction_date"], right_on=["ISIN", "timestamp"], how="left")
    ck.require((priced["price"] == priced["closePrice"]).all(), "transactions: price differs from that day's market close")
    wealth = t["customer_id"].map((c["investment_portfolio_value"] + c["cash_savings"]).set_axis(c["customer_id"]))
    cap = np.maximum(0.5 * wealth, 1000.0)          # the generator's purchase cap: half of investable wealth
    funds = t["asset_type"] == "Fund"
    # a purchase is executed in whole units (stocks, bonds) or thousandths (funds), so its value may exceed the
    # intended amount by less than one quantity step; beyond that step it is a cap violation
    step = np.where(funds, 0.001 * t["price"], np.where(t["quantity"] <= 1, t["price"], 0.0))
    over_strict = buy & (t["transaction_value"] > cap + 0.005)
    violation = buy & (t["transaction_value"] > cap + step + 0.01)
    sells_large = (~buy) & (t["transaction_value"] > 0.5 * wealth)
    ck.report["purchase_cap"] = {
        "violations_beyond_one_quantity_step": int(violation.sum()),
        "strict_overshoot_within_rounding": int((over_strict & ~violation).sum()),
        "max_strict_overshoot_rupees": round(float((t["transaction_value"] - cap)[over_strict].max()), 2)
        if over_strict.any() else 0.0,
        "large_sells_over_50pct_current_wealth": int(sells_large.sum()),
        "large_sells_note": "sells of lots whose price rose after purchase; the cap applies to purchases only",
    }
    ck.require(not violation.any(), f"transactions: {int(violation.sum())} purchase(s) exceed the 50%-of-wealth cap")
    signed = np.where(buy, t["quantity"], -t["quantity"])
    order = t.assign(signed=signed).sort_values(["customer_id", "asset_id"], kind="stable")
    held = order.groupby(["customer_id", "asset_id"], sort=False, observed=True)["signed"].cumsum()
    ck.require(held.min() >= -1e-9, "transactions: a sell exceeds the units held")

    # point-in-time behaviour features, recomputed
    cutoff = t["customer_id"].map(c.set_index("customer_id")["feature_cutoff_date"])
    pre = t[dates <= cutoff]
    g = pre.groupby("customer_id")
    stats = pd.DataFrame({
        "trade_count": g.size(),
        "buy_value": pre[pre["transaction_type"] == "Buy"].groupby("customer_id")["transaction_value"].sum(),
        "sell_value": pre[pre["transaction_type"] == "Sell"].groupby("customer_id")["transaction_value"].sum(),
    }).reindex(c["customer_id"]).fillna(0.0)
    ci = c.set_index("customer_id")
    ok_count = (stats["trade_count"].to_numpy() == ci["trade_count"].to_numpy()).all()
    ok_buy = _close(stats["buy_value"], ci["buy_value"], 0.05).all()
    ok_sell = _close(stats["sell_value"], ci["sell_value"], 0.05).all()
    month = lambda s: (s.str[:4].astype(int) - 2019) * 12 + s.str[5:7].astype(int) - 1  # noqa: E731
    first_m, last_m = month(ci["onboarding_date"]), month(ci["feature_cutoff_date"])
    observed = (last_m - first_m + 1).to_numpy()
    ok_freq = _close(ci["investment_frequency"], stats["trade_count"].to_numpy() / observed, 6e-5).all()
    pm = pre.assign(m=month(pre["transaction_date"].astype(str))).groupby(["customer_id", "m"]).size()
    sums = pm.groupby(level=0).sum().reindex(ci.index).fillna(0).to_numpy()
    sq = (pm ** 2).groupby(level=0).sum().reindex(ci.index).fillna(0).to_numpy()
    mean = sums / observed
    traded = mean > 0
    vol = np.sqrt(np.maximum(sq / observed - mean ** 2, 0)) / np.where(traded, mean, 1)
    stored_vol = ci["behaviour_volatility"].to_numpy()
    ok_vol = bool(_close(stored_vol[traded], vol[traded], 6e-5).all() and np.isnan(stored_vol[~traded]).all())
    all_counts = t.groupby("customer_id").size().reindex(ci.index).to_numpy()
    later = int((all_counts > ci["trade_count"].to_numpy()).sum())
    ck.report["point_in_time_behaviour_features"] = {
        "recomputed_from_pre_cutoff_transactions_match": bool(ok_count and ok_buy and ok_sell and ok_freq and ok_vol),
        "customers_with_later_activity_excluded_from_features": later,
    }
    ck.require(ok_count and ok_buy and ok_sell, "behaviour features: trade_count/buy_value/sell_value do not match "
                                               "the pre-cutoff transactions")
    ck.require(ok_freq and ok_vol, "behaviour features: investment_frequency/behaviour_volatility do not match")
    bought = ci["buy_value"] > 0
    ck.require(bool(_close(ci.loc[bought, "portfolio_turnover"],
                           ci.loc[bought, "sell_value"] / ci.loc[bought, "buy_value"], 2e-6).all()
                    and ci.loc[~bought, "portfolio_turnover"].isna().all()),
               "behaviour features: portfolio_turnover != sell_value / buy_value")
    has = ci["trade_count"] > 0
    ck.require(_close(ci.loc[has, "average_transaction_value"],
                      ((ci.loc[has, "buy_value"] + ci.loc[has, "sell_value"]) / ci.loc[has, "trade_count"]).round(2),
                      0.011).all(), "behaviour features: average_transaction_value inconsistent")


# ---------------------------------------------------------------------------
# Goals (+ a production-engine re-run on a sample)
# ---------------------------------------------------------------------------


def goal_return_series(far_trans_dir: Path) -> np.ndarray:
    """The goal engine's return series, rebuilt from the PUBLISHED prices: equal-weight equity / bond / gold blend,
    compounded to monthly periods by the application's own helper."""
    from wealthpilot.api.services.analysis_service import _compound_to_period_returns
    from wealthpilot.core.optimizer import equal_weight_portfolio

    close = pd.read_csv(far_trans_dir / "close_prices.csv")
    assets = pd.read_csv(far_trans_dir / "asset_information.csv")
    wide = close.pivot(index="timestamp", columns="ISIN", values="closePrice").sort_index()
    simple = wide.pct_change().iloc[1:]
    group = {"EQUITY": assets.loc[assets.assetCategory == "Stock", "ISIN"],
             "BOND": assets.loc[assets.assetCategory == "Bond", "ISIN"],
             "GOLD": assets.loc[assets.assetSubCategory == "Gold Fund", "ISIN"]}
    daily = pd.DataFrame({k: simple[list(v)].mean(axis=1) for k, v in group.items()})
    return _compound_to_period_returns(daily.dot(equal_weight_portfolio(list(daily.columns))).to_numpy(), 12)


def check_goals(g: pd.DataFrame, c: pd.DataFrame, ck: Checks, far_trans_dir: Path, sample: int) -> None:
    n = len(g)
    ck.require(n >= MIN_GOALS, f"goals: {n:,} rows (< {MIN_GOALS:,})")
    ck.require(g["goal_id"].is_unique, "goals: goal_id is not unique")
    ck.require(g.duplicated().sum() == 0, "goals: duplicate rows")
    ck.require(g.notna().all().all(), "goals: missing values")
    ck.require(g["customer_id"].isin(c["customer_id"]).all(), "goals: a customer_id has no customer row")
    ck.require(not g.duplicated(["customer_id", "priority"]).any(), "goals: two goals share a priority")
    ck.require(not g.duplicated(["customer_id", "goal_type"]).any(), "goals: a customer has the same goal type twice")
    ck.require(set(g["goal_type"]) <= {"Emergency Fund", "Retirement", "Education", "Home", "Vehicle", "Travel",
                                       "Wealth Creation", "Other"}, "goals: unexpected goal_type")
    ck.require((g["analysis_date"] == g["customer_id"].map(c.set_index("customer_id")["feature_cutoff_date"])).all(),
               "goals: analysis_date is not the customer's feature_cutoff_date")
    ck.require((g["target_date"] > g["analysis_date"]).all(), "goals: a target_date is not after the analysis date")
    ck.require((g["target_year"] == g["target_date"].str[:4].astype(int)).all(), "goals: target_year != year(target_date)")
    years = (pd.to_datetime(g["target_date"]) - pd.to_datetime(g["analysis_date"])).dt.days / 365.25
    ck.require(_close(g["years_remaining"], years, 6e-5).all(), "goals: years_remaining inconsistent with the dates")
    ck.require((g[["target_amount", "inflation_adjusted_target_amount"]] > 0).all().all(), "goals: non-positive target")
    ck.require((g[["current_amount", "monthly_contribution"]] >= 0).all().all(), "goals: negative amount")
    achieved = g["current_amount"] >= g["inflation_adjusted_target_amount"] - 0.0051
    ck.require(((g["goal_status"] == "Achieved") == achieved).all(),
               "goals: Achieved must mean current_amount >= the inflation-adjusted target")
    ck.require(((g["current_amount"] <= g["target_amount"]) | (g["goal_status"] == "Achieved")).all(),
               "goals: current_amount exceeds target_amount on a goal that is not Achieved")
    ck.require(((g["goal_status"] == "Paused") == (~achieved & (g["monthly_contribution"] <= 0))).all(),
               "goals: Paused must mean not achieved with no monthly contribution")
    spent = g.groupby("customer_id")["monthly_contribution"].sum()
    room = c.set_index("customer_id")["monthly_savings"].clip(lower=0).reindex(spent.index)
    ck.require((spent <= room + 0.011).all(), "goals: contributions exceed the customer's positive monthly savings")
    p = g["monte_carlo_success_probability"]
    expected = np.where(p >= FEASIBLE_THRESHOLD, "Feasible", np.where(p >= AT_RISK_THRESHOLD, "At Risk", "Not Feasible"))
    ck.require((g["goal_feasibility"] == expected).all(), "goals: goal_feasibility != the production thresholds")

    returns = goal_return_series(far_trans_dir)
    rows = g.iloc[:: max(1, n // sample)].head(sample)
    mismatches = 0
    for r in rows.itertuples(index=False):
        assumptions = GoalAssumptions(contribution_amount=r.monthly_contribution,
                                      contribution_periods_per_year=r.contribution_periods_per_year,
                                      annual_return_rate=r.annual_return_rate, annual_inflation_rate=r.annual_inflation_rate)
        goal = GoalInput(customer_id=1, goal_type=r.goal_type, target_amount=r.target_amount,
                         current_savings=r.current_amount, target_date=pd.Timestamp(r.target_date).date(),
                         priority=r.priority)
        analysis = analyze_goal_funding(goal, assumptions, pd.Timestamp(r.analysis_date).date())
        mc = run_goal_monte_carlo(r.current_amount, r.monthly_contribution, analysis.periods_remaining,
                                  analysis.inflation_adjusted_target_amount, returns,
                                  n_simulations=int(r.monte_carlo_simulations))
        if round(mc.success_probability, 4) != r.monte_carlo_success_probability or \
                abs(analysis.inflation_adjusted_target_amount - r.inflation_adjusted_target_amount) > 0.011:
            mismatches += 1
    ck.report["goal_engine_rerun"] = {"sampled_goals": len(rows), "mismatches": mismatches}
    ck.require(mismatches == 0, f"goals: {mismatches} of {len(rows)} sampled goals differ when re-run through the "
                                "production goal engine")


# ---------------------------------------------------------------------------
# Leakage
# ---------------------------------------------------------------------------


def _single_feature_accuracy(x: pd.Series, y: pd.Series) -> float:
    key = pd.qcut(x.rank(method="first"), 20, labels=False) if x.dtype.kind in "fi" else x
    key = key.astype(object).where(key.notna(), "__missing__")
    table = pd.crosstab(key, y)
    return float(table.max(axis=1).sum() / len(y))


def _auc(x: pd.Series, y: pd.Series) -> float:
    x = x.fillna(x.median())
    ranks = x.rank()
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    auc = (ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    return float(max(auc, 1 - auc))


def check_leakage(c: pd.DataFrame, g: pd.DataFrame, ck: Checks) -> None:
    features = [col for col in c.columns if col not in NOT_FEATURES]
    risk = sorted(((_single_feature_accuracy(c[f], c["risk_label"]), f) for f in features), reverse=True)
    baseline = float(c["risk_label"].value_counts(normalize=True).max())
    numeric = [f for f in features if c[f].dtype.kind in "fi"]
    anomaly = sorted(((_auc(c[f], c["behavior_anomaly"]), f) for f in numeric), reverse=True)
    segment = sorted(((_single_feature_accuracy(c[f], c["expense_segment"]), f) for f in features), reverse=True)
    goal_inputs = ["goal_type", "priority", "years_remaining", "periods_remaining", "target_amount", "current_amount",
                   "monthly_contribution", "annual_return_rate", "annual_inflation_rate"]
    goal = sorted(((_single_feature_accuracy(g[f], g["goal_feasibility"]), f) for f in goal_inputs), reverse=True)
    ck.report["leakage"] = {
        "risk_label": {"majority_baseline_accuracy": round(baseline, 4),
                       "strongest_single_features": {f: round(a, 4) for a, f in risk[:5]}, "limit": 0.70},
        "behavior_anomaly": {"strongest_single_feature_auc": {f: round(a, 4) for a, f in anomaly[:5]}, "limit": 0.995},
        "expense_segment": {"strongest_single_features": {f: round(a, 4) for a, f in segment[:5]},
                            "note": "segments are defined on these ratios by design (a segmentation target)"},
        "goal_feasibility": {"strongest_single_inputs": {f: round(a, 4) for a, f in goal[:5]},
                             "excluded_engine_outputs": ["inflation_adjusted_target_amount",
                                                         "required_monthly_contribution", "contribution_gap",
                                                         "goal_status", "monte_carlo_success_probability"]},
    }
    ck.require(risk[0][0] <= 0.70, f"leakage: {risk[0][1]} alone predicts risk_label with {risk[0][0]:.1%} accuracy")
    ck.require(anomaly[0][0] <= 0.995, f"leakage: {anomaly[0][1]} alone separates behavior_anomaly (AUC {anomaly[0][0]:.4f})")
    ck.require(segment[0][0] < 0.98, f"leakage: {segment[0][1]} alone determines expense_segment")


# ---------------------------------------------------------------------------
# Existing pipelines on the format copies
# ---------------------------------------------------------------------------


def check_pipelines(data_dir: Path, c: pd.DataFrame, ck: Checks) -> None:
    from training.behaviour.common import build_monthly_panel, load_far_trans_transactions_and_assets
    from training.expense.common import engineer_expense_features, load_kaggle_primary
    from wealthpilot.data.preprocessing import ALL_FEATURES, engineer_features, load_far_trans_tables

    tables = load_far_trans_tables(data_dir / "far_trans_format")
    features = engineer_features(tables["customers"], tables["transactions"], tables["assets"], tables["close_prices"])
    labelled = features[features["risk_level"].notna()]
    traders = c[c["trade_count"] > 0]   # engineer_features drops customers with no pre-cutoff trade (by design)
    same_labels = labelled["risk_level"].value_counts().sort_index().to_dict() == \
        traders["risk_label"].value_counts().sort_index().to_dict()
    ck.require(len(labelled) == len(traders), f"pipelines: engineer_features produced {len(labelled):,} labelled "
                                              f"rows, expected {len(traders):,}")
    ck.require(same_labels, "pipelines: engineer_features' labels differ from risk_label")
    ck.require(list(features.columns[:len(ALL_FEATURES)]) == ALL_FEATURES, "pipelines: risk feature columns differ")
    del tables
    tx, assets = load_far_trans_transactions_and_assets(data_dir / "far_trans_format")
    panel = build_monthly_panel(tx, assets)
    del tx
    raw = load_kaggle_primary(data_dir / "kaggle_format")
    expense, excluded = engineer_expense_features(raw)
    ratio_match = _close(expense["expense_to_income_ratio"].reindex(c["customer_id"]).to_numpy(),
                         c["expense_to_income_ratio"].to_numpy(), 2e-6).all()
    ck.require(len(expense) == len(c) and excluded == 0, "pipelines: engineer_expense_features dropped customers")
    ck.require(ratio_match, "pipelines: the Kaggle-format expense ratios differ from the customer file")
    ck.report["existing_pipelines"] = {
        "risk: load_far_trans_tables + engineer_features": (
            f"{len(labelled):,} labelled rows x {len(ALL_FEATURES)} features ({len(c) - len(traders):,} customers "
            "with no pre-cutoff trade dropped by its point-in-time rule)"),
        "behaviour: build_monthly_panel": f"{len(panel):,} customer-months",
        "expense: load_kaggle_primary + engineer_expense_features": f"{len(expense):,} rows, {excluded} excluded",
    }


# ---------------------------------------------------------------------------
# Distribution and correlation report
# ---------------------------------------------------------------------------

STAT_COLUMNS = {
    "customers": ["annual_income", "monthly_income", "monthly_expenses", "monthly_essential_expenses",
                  "housing_expense", "monthly_emi", "total_debt", "cash_savings", "monthly_savings",
                  "investment_contribution", "investment_portfolio_value", "liquid_assets", "emergency_fund_months",
                  "savings_rate", "debt_to_income_ratio", "equity_pct", "age", "dependents", "trade_count"],
    "transactions": ["transaction_value"],
    "goals": ["target_amount", "monthly_contribution", "years_remaining"],
}
INCOME_BANDS = [(0, 2), (2, 4), (4, 8), (8, 15), (15, 30), (30, 75), (75, 10_000)]   # lakh / year
RISK_ORDER = ["Conservative", "Income", "Balanced", "Aggressive"]
CAPACITY_ORDER = ["CAP_LT30K", "CAP_30K_80K", "CAP_80K_300K", "CAP_GT300K"]


def _stats(x: pd.Series) -> dict:
    x = x.dropna().astype(float)
    q = x.quantile([0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {"min": x.min(), "max": x.max(), "mean": x.mean(), "median": x.median(), "std": x.std(),
            "p5": q[0.05], "p25": q[0.25], "p50": q[0.5], "p75": q[0.75], "p95": q[0.95], "p99": q[0.99]}


def _spearman(a, b) -> float:
    return round(float(pd.Series(np.asarray(a, dtype=float)).corr(pd.Series(np.asarray(b, dtype=float)),
                                                                   method="spearman")), 3)


def distribution_report(c: pd.DataFrame, t: pd.DataFrame, g: pd.DataFrame) -> dict:
    """Summary statistics, frequencies and the relationships the population is meant to have."""
    stats = {f"customers.{col}": _stats(c[col]) for col in STAT_COLUMNS["customers"]}
    stats.update({f"transactions.{col}": _stats(t[col]) for col in STAT_COLUMNS["transactions"]})
    stats.update({f"goals.{col}": _stats(g[col]) for col in STAT_COLUMNS["goals"]})
    lakh = c["annual_income"] / 100_000
    bands = {(f"{lo}-{hi} lakh" if hi < 10_000 else f">{lo} lakh"): int(((lakh >= lo) & (lakh < hi)).sum())
             for lo, hi in INCOME_BANDS}
    freq = {col: c[col].value_counts(dropna=False).to_dict()
            for col in ("employment_status", "risk_label", "expense_segment", "behavior_anomaly", "investor_type",
                        "debt_profile", "housing_status", "city_tier")}
    freq["goal_type"] = g["goal_type"].value_counts().to_dict()
    freq["goal_feasibility"] = g["goal_feasibility"].value_counts().to_dict()
    risk = c["risk_label"].map({v: i for i, v in enumerate(RISK_ORDER)})
    capacity = c["investment_capacity"].map({v: i for i, v in enumerate(CAPACITY_ORDER)})
    per_customer_value = t.groupby("customer_id")["transaction_value"].median().reindex(c["customer_id"]).to_numpy()
    debtors = c["total_debt"] > 0
    cards = c["credit_card_limit"] > 0
    working = c["age"] <= 55
    paying = g["monthly_contribution"] > 0
    correlations = {
        "income ~ monthly_expenses": _spearman(c.annual_income, c.monthly_expenses),
        "income ~ monthly_savings": _spearman(c.annual_income, c.monthly_savings),
        "income ~ total_debt (debtors)": _spearman(c.annual_income[debtors], c.total_debt[debtors]),
        "income ~ credit_card_limit (card holders)": _spearman(c.annual_income[cards], c.credit_card_limit[cards]),
        "age ~ employment_years": _spearman(c.age, c.employment_years),
        "age ~ income (ages 21-55)": _spearman(c.age[working], c.annual_income[working]),
        "dependents ~ essential expenses / income": _spearman(c.dependents,
                                                              c.monthly_essential_expenses / c.monthly_income),
        "dependents ~ food_expense": _spearman(c.dependents, c.food_expense),
        "risk_label (ordinal) ~ equity_pct": _spearman(risk, c.equity_pct),
        "risk_label (ordinal) ~ cash_pct": _spearman(risk, c.cash_pct),
        "investment_capacity (ordinal) ~ trade_count": _spearman(capacity, c.trade_count),
        "investment_capacity (ordinal) ~ median transaction value": _spearman(capacity[~np.isnan(per_customer_value)],
                                                                             per_customer_value[~np.isnan(per_customer_value)]),
        "goal target_amount ~ monthly_contribution (contributing goals)": _spearman(g.target_amount[paying],
                                                                                   g.monthly_contribution[paying]),
        "goal target_amount ~ years_remaining": _spearman(g.target_amount, g.years_remaining),
    }
    by_age = c.groupby(pd.cut(c.age, [20, 25, 30, 35, 45, 55, 60, 80]), observed=True)["annual_income"].median()
    employment_by_age = pd.crosstab(pd.cut(c.age, [20, 25, 35, 55, 60, 80]), c.employment_status, normalize="index")
    return _py({"statistics": stats, "annual_income_bands": bands, "frequencies": freq, "spearman": correlations,
                "median_income_by_age_band": {str(k): float(v) for k, v in by_age.round(-3).items()},
                "employment_by_age_band": {str(k): {kk: round(float(vv), 3) for kk, vv in row.items()}
                                           for k, row in employment_by_age.iterrows()}})


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def validate_dataset(data_dir: Path = DATA_DIR, require_metadata: bool = True, run_pipelines: bool = True,
                     engine_sample: int = 300) -> tuple[list[str], dict]:
    ck = Checks()
    csv_files = [CUSTOMER_FILE, TRANSACTION_FILE, GOAL_FILE, *(f"far_trans_format/{f}" for f in FAR_TRANS_FILES),
                 KAGGLE_FILE]
    missing = [f for f in csv_files if not (data_dir / f).exists()]
    if require_metadata and not (data_dir / METADATA_FILE).exists():
        missing.append(METADATA_FILE)
    if missing:
        return [f"missing file(s): {missing}"], {}

    rows = {rel: check_format(data_dir / rel, rel, ck) for rel in csv_files}
    customers = pd.read_csv(data_dir / CUSTOMER_FILE, dtype={"customer_id": str, "behavior_anomaly_month": str})
    tx = pd.read_csv(data_dir / TRANSACTION_FILE, dtype={
        "transaction_id": str, "customer_id": str, "transaction_date": str, "transaction_type": "category",
        "asset_type": "category", "asset_subtype": "category", "asset_id": "category", "channel": "category"})
    goals = pd.read_csv(data_dir / GOAL_FILE, dtype={"goal_id": str, "customer_id": str})
    close = pd.read_csv(data_dir / "far_trans_format/close_prices.csv", dtype={"ISIN": "category", "timestamp": str})
    asset_ids = set(pd.read_csv(data_dir / "far_trans_format/asset_information.csv")["ISIN"])
    raw_ids_path = REPO_ROOT / "datasets" / "raw" / "FAR-Trans" / "customer_information.csv"
    raw_ids = set(pd.read_csv(raw_ids_path, usecols=["customerID"])["customerID"]) if raw_ids_path.exists() else set()

    for rel, frame in ((CUSTOMER_FILE, customers), (TRANSACTION_FILE, tx), (GOAL_FILE, goals)):
        ck.require(rows[rel] == len(frame), f"{rel}: physical lines != parsed rows (an embedded newline?)")
    check_customers(customers, ck, raw_ids)
    check_transactions(tx, customers, close, asset_ids, ck)
    del tx, close
    check_goals(goals, customers, ck, data_dir / "far_trans_format", engine_sample)
    check_leakage(customers, goals, ck)
    if run_pipelines:
        check_pipelines(data_dir, customers, ck)

    manifest = REPO_ROOT / "demo_data" / "manifest.json"
    if manifest.exists():
        guard = json.loads(manifest.read_text(encoding="utf-8")).get("training_data_guard", {})
        changed = [rel for rel, sha in guard.items() if (REPO_ROOT / rel).exists() and _sha256(REPO_ROOT / rel) != sha]
        ck.require(not changed, f"raw training data changed: {changed}")
        ck.report["raw_datasets_unchanged"] = f"{len(guard) - len(changed)}/{len(guard)} files match recorded SHA-256"

    if require_metadata:
        meta = json.loads((data_dir / METADATA_FILE).read_text(encoding="utf-8"))
        ck.require(meta.get("synthetic") is True and meta.get("training_eligible") is True
                   and meta.get("data_source") == "synthetic_generated", "metadata: synthetic/training flags wrong")
        ck.require(meta.get("customer_rows") == len(customers) and meta.get("goal_rows") == len(goals)
                   and meta.get("transaction_rows") == rows[TRANSACTION_FILE], "metadata: row counts differ from the files")
        stale = [rel for rel, info in meta.get("files", {}).items()
                 if (data_dir / rel).exists() and _sha256(data_dir / rel) != info.get("sha256")]
        ck.require(not stale, f"metadata: sha256 differs for {stale}")

    null_rates = {col: round(float(v), 4) for col, v in customers.isna().mean().items() if v > 0}
    ck.report.update({
        "rows": rows,
        "columns": {CUSTOMER_FILE: customers.shape[1], GOAL_FILE: goals.shape[1]},
        "duplicate_rows": {CUSTOMER_FILE: int(customers.duplicated().sum()), GOAL_FILE: int(goals.duplicated().sum())},
        "customer_null_rates": null_rates,
        "label_distributions": {
            "risk_label": customers["risk_label"].value_counts().to_dict(),
            "expense_segment": customers["expense_segment"].value_counts().to_dict(),
            "behavior_anomaly": customers["behavior_anomaly"].value_counts().to_dict(),
            "goal_feasibility": goals["goal_feasibility"].value_counts().to_dict(),
        },
        "date_ranges": {
            "onboarding_date": [customers["onboarding_date"].min(), customers["onboarding_date"].max()],
            "feature_cutoff_date": [customers["feature_cutoff_date"].min(), customers["feature_cutoff_date"].max()],
            "goal_target_date": [goals["target_date"].min(), goals["target_date"].max()],
        },
    })
    return ck.errors, _py(ck.report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--skip-pipelines", action="store_true", help="skip running the existing loaders (faster)")
    args = parser.parse_args(argv)
    errors, report = validate_dataset(args.data_dir, run_pipelines=not args.skip_pipelines)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    for error in errors:
        print(f"FAIL  {error}")
    print(f"\nSYNTHETIC TRAINING DATASET {'VALID' if not errors else f'INVALID: {len(errors)} error(s)'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
