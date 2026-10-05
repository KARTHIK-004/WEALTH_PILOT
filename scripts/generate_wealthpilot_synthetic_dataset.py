"""Generates the WealthPilot AI synthetic ML training dataset (ADR-039).

USAGE (repo root, venv active):

    python scripts/generate_wealthpilot_synthetic_dataset.py
    python scripts/generate_wealthpilot_synthetic_dataset.py --customers 100000 --seed 42

Writes to `datasets/generated/` (CSV files are git-ignored; regenerate them
with this script -- same seed, same bytes):

    wealthpilot_customer_training.csv      one row per synthetic customer
    wealthpilot_transactions_training.csv  investment transactions, in date order
    wealthpilot_goals_training.csv         goals, with the production goal engine's result
    wealthpilot_training_metadata.json     counts, rates, distributions, method, validation
    far_trans_format/                      the same population in the FAR-Trans file format
    kaggle_format/                         the same population in the Kaggle file format

The data is SYNTHETIC. It is not customer data and must not be represented as
empirical financial data. It is separate from FAR-Trans, from the Kaggle
dataset and from `demo_data/`. Amounts are in INR (the income bands below are
modelling choices for realistic variation, not claims about any real population).

POPULATION MODEL (each step builds on the previous ones; full detail: datasets/generated/README.md)

1. Life stage: age (right-skewed, adults 21-78) -> education (socio-economic
   background + age) -> city tier -> employment status (students young,
   retirees 56+) -> total work experience (age minus education-dependent
   start age minus career gaps).
2. Income: a log-normal around a median built from education x city tier x an
   experience curve (steep early, plateau mid-career, gentle decline after 55)
   x background; wider spread for the self-employed; retirees get a pension /
   interest income at a replacement ratio of their career income; students and
   the unemployed get small stipend / support incomes. Out-of-range draws are
   RE-DRAWN, never clipped, so there are no spikes at the bounds.
3. Household: marriage by age; dependents = children + dependent parents + a
   non-earning spouse; housing situation (with family / rented / owned with a
   mortgage / owned outright) from age, income, tier and marriage.
4. Debt: a mortgage only for "owned with mortgage" (sized on career income x a
   tier-dependent property multiple), vehicle, personal and credit-card debt
   from income, age, credit behaviour and the leverage-shaped expense segment;
   instalments from the standard annuity formula at sampled rates / tenures /
   elapsed time; credit cards revolve for some, are paid in full by others.
5. Spending: essential components from income, household size, tier, housing
   and a lifestyle factor; discretionary from what is left after essentials
   and EMIs, shaped by the planted expense segment; outflows above a
   plausibility cap trim discretionary spending first.
6. Savings and wealth: monthly savings = income - expenses - EMIs (can be a
   deficit); investment contribution is a behaviour-driven share of positive
   savings; the savings stock and the portfolio accumulate from those flows
   over the customer's working years (retirees hold a retirement corpus).
7. Risk: latent tolerance, capacity (from the finances), horizon (from age),
   stability and experience -> documented weighted score + label noise ->
   ordinal thresholds give `risk_label`; the observed scores are noisy views
   of the same latents; allocation follows the same latents with its own noise.
8. Behaviour: investor types (inactive / occasional / regular SIP / highly
   active) from experience, tolerance and wealth; SIP instalments are monthly,
   in multiples of Rs 500; lump sums and trades scale with the portfolio.
   `behavior_anomaly` marks customers given one injected burst of unusual trades.
9. Goals: eligibility and horizons by life stage; amounts by type (retirement
   corpus from annual spending, education per child, home from a property
   price, ...); contributions allocated from positive savings by need and
   priority; feasibility from the PRODUCTION goal engine (core/goals.py) with
   500 Monte Carlo paths per goal (the application uses 10,000). The
   emergency-fund requirement comes from the production assess_emergency_fund.

Random streams: one `numpy.random.SeedSequence(seed)` spawns an independent
generator per component, so the output depends only on the seed and sizes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from wealthpilot.core.goals import (  # noqa: E402  -- production engine, called, never copied
    EMERGENCY_FUND_TARGET_MONTHS,
    GoalAssumptions,
    GoalInput,
    analyze_goal_funding,
    assess_emergency_fund,
    classify_feasibility,
    run_goal_monte_carlo,
)
from wealthpilot.core.optimizer import equal_weight_portfolio  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "datasets" / "generated"
DEFAULT_CUSTOMERS = 100_000
MIN_TRANSACTIONS = 2_000_000
MIN_GOALS = 300_000
DEFAULT_SEED = 42
GOAL_MC_SIMULATIONS = 500          # the application uses 10,000; see the module docstring
CONTRIBUTION_PERIODS_PER_YEAR = 12
START_DATE, END_DATE = "2019-01-01", "2024-12-31"
LAST_CUTOFF_DATE = "2024-06-28"    # later activity stays available for time-based validation
BDAYS_PER_MONTH = 21
N_MONTHS = 72
LAKH = 100_000
CURRENCY = "INR"

CUSTOMER_FILE = "wealthpilot_customer_training.csv"
TRANSACTION_FILE = "wealthpilot_transactions_training.csv"
GOAL_FILE = "wealthpilot_goals_training.csv"
METADATA_FILE = "wealthpilot_training_metadata.json"
FAR_TRANS_DIR = "far_trans_format"
KAGGLE_DIR = "kaggle_format"
KAGGLE_FILE = "synthetic_personal_finance_dataset.csv"  # the name the existing loader expects

RISK_CLASSES = ["Conservative", "Income", "Balanced", "Aggressive"]  # ordinal, FAR-Trans's genuine levels
RISK_SHARES = [0.13, 0.42, 0.33, 0.12]                                # close to FAR-Trans's genuine distribution
EXPENSE_SEGMENTS = [  # descriptive ratio-profile labels, in the existing model's labelling style
    "low-expense-low-leverage-higher-savings",
    "moderate-expense-low-leverage-moderate-savings",
    "high-expense-low-leverage-lower-savings",
    "moderate-expense-high-leverage-lower-savings",
]
EDUCATION = ["High School", "Bachelor", "Master", "PhD", "Other"]     # the Kaggle dataset's vocabulary
CITY_TIERS = ["Tier 1", "Tier 2", "Tier 3"]
HOUSING = ["Living with family", "Rented", "Owned with mortgage", "Owned outright"]
EXPERIENCE = ["No experience", "Beginner", "Intermediate", "Advanced"]  # not "None": pandas reads that as missing
LOSS_TOLERANCE = ["Low", "Medium", "High"]
INVESTOR_TYPES = ["inactive", "occasional", "regular_sip", "highly_active"]
INVESTOR_SHARES = [0.08, 0.40, 0.37, 0.15]
CHANNELS = ["Internet Banking", "Branch", "Phone Banking"]            # FAR-Trans channels
GOAL_TYPES = ["Emergency Fund", "Retirement", "Education", "Home", "Vehicle", "Travel", "Wealth Creation", "Other"]
ESSENTIAL_EXPENSES = ["housing_expense", "food_expense", "transport_expense", "healthcare_expense",
                      "education_expense", "utilities_expense", "insurance_expense"]
EXPENSE_COMPONENTS = [*ESSENTIAL_EXPENSES, "discretionary_expense", "other_expense"]
CAPACITY_SHARES = [0.57, 0.22, 0.174, 0.036]   # FAR-Trans's genuine investmentCapacity shares
CAPACITY_BANDS = ["CAP_LT30K", "CAP_30K_80K", "CAP_80K_300K", "CAP_GT300K"]
# (asset_type, asset_subtype, count, annual drift, annual volatility, equity beta, bond beta, gold beta, FAR-Trans category)
ASSET_SPEC = [
    ("Stock", "Equity", 150, 0.110, 0.26, 1.00, 0.00, 0.00, "Stock"),
    ("Bond", "Government", 30, 0.068, 0.035, 0.00, 1.00, 0.00, "Bond"),
    ("Bond", "Corporate", 30, 0.078, 0.050, 0.15, 1.00, 0.00, "Bond"),
    ("Fund", "Equity Fund", 30, 0.100, 0.17, 0.90, 0.00, 0.00, "MTF"),
    ("Fund", "Bond Fund", 20, 0.065, 0.035, 0.05, 0.90, 0.00, "MTF"),
    ("Fund", "Balanced Fund", 15, 0.085, 0.10, 0.50, 0.50, 0.00, "MTF"),
    ("Fund", "Money Market Fund", 10, 0.060, 0.004, 0.00, 0.05, 0.00, "MTF"),
    ("Fund", "Gold Fund", 15, 0.080, 0.14, -0.10, 0.00, 1.00, "MTF"),
]
STOCK_SECTORS = ["Technology", "Financial Services", "Industrials", "Consumer Cyclical", "Consumer Defensive",
                 "Healthcare", "Energy", "Basic Materials", "Utilities", "Communication Services"]
MISSING_RATES = {  # leaf columns only: nothing else is computed from them
    "education_level": 0.03, "marital_status": 0.02, "employment_years": 0.04, "income_growth_rate": 0.06,
    "income_source_count": 0.02, "income_stability_score": 0.03, "savings_stability": 0.04,
    "investment_experience": 0.05, "loss_tolerance": 0.03,
}
TARGET_SIDE_CUSTOMER_COLUMNS = ["risk_label", "expense_segment", "behavior_anomaly", "behavior_anomaly_month"]
TARGET_SIDE_GOAL_COLUMNS = ["monte_carlo_success_probability", "goal_feasibility"]
ENGINE_OUTPUT_GOAL_COLUMNS = ["inflation_adjusted_target_amount", "required_monthly_contribution",
                              "contribution_gap", "goal_status"]


def _streams(seed: int) -> dict[str, np.random.Generator]:
    names = ["market", "demographics", "latent", "income", "segment", "household", "debt", "expenses", "savings",
             "allocation", "risk", "activity", "buys", "sells", "anomaly", "channel", "goals", "missing", "sip"]
    return {n: np.random.default_rng(s) for n, s in zip(names, np.random.SeedSequence(seed).spawn(len(names)))}


def _round(x, digits: int = 2) -> np.ndarray:
    return np.round(np.asarray(x, dtype=float), digits)


def _sigmoid(x) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def _z(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return (x - x.mean()) / x.std()


def _categorical(rng: np.random.Generator, probs: np.ndarray) -> np.ndarray:
    """One draw per row from row-wise probabilities (rows sum to 1)."""
    cum = np.cumsum(probs, axis=1)
    cum[:, -1] = 1.0
    return (rng.random(len(probs))[:, None] > cum).sum(axis=1)


def _softmax(logits: np.ndarray) -> np.ndarray:
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def _bounded_lognormal(rng: np.random.Generator, median: np.ndarray, sigma: np.ndarray, lo: float,
                       hi: float) -> np.ndarray:
    """Log-normal draws around a per-row median; a draw outside [lo, hi] is RE-DRAWN (not clipped), so the bounds
    never create a pile-up of identical values."""
    median, sigma = np.broadcast_to(median, median.shape).astype(float), np.broadcast_to(sigma, median.shape)
    x = median * np.exp(sigma * rng.standard_normal(len(median)))
    for _ in range(25):
        bad = (x < lo) | (x > hi)
        if not bad.any():
            break
        x[bad] = median[bad] * np.exp(sigma[bad] * rng.standard_normal(int(bad.sum())))
    bad = (x < lo) | (x > hi)
    x[bad] = rng.uniform(lo, hi, int(bad.sum()))   # vanishingly rare after 25 re-draws
    return x


def _annuity_payment(principal, annual_rate, years) -> np.ndarray:
    r, n = annual_rate / 12, years * 12
    return principal * r / (1 - (1 + r) ** -n)


def _remaining_balance(principal, annual_rate, years, elapsed_years) -> np.ndarray:
    r, n, k = annual_rate / 12, years * 12, elapsed_years * 12
    return principal * ((1 + r) ** n - (1 + r) ** k) / ((1 + r) ** n - 1)


# ---------------------------------------------------------------------------
# 1. Synthetic market (INR price levels)
# ---------------------------------------------------------------------------


def generate_market(rng: np.random.Generator) -> dict:
    dates = pd.bdate_range(START_DATE, END_DATE)
    n_days = len(dates)
    in_period = lambda a, b: (dates >= a) & (dates <= b)  # noqa: E731
    equity = rng.normal(0.12 / 252, 0.17 / np.sqrt(252), n_days)
    equity[in_period("2020-02-20", "2020-03-23")] -= 0.013      # a crash ...
    equity[in_period("2020-03-24", "2020-08-31")] += 0.0035     # ... and its recovery
    equity[in_period("2022-01-03", "2022-06-30")] -= 0.0008     # a correction
    bond = rng.normal(0.068 / 252, 0.03 / np.sqrt(252), n_days)
    bond[in_period("2022-04-01", "2022-10-31")] -= 0.0003       # a rate-hike cycle
    gold = rng.normal(0.09 / 252, 0.13 / np.sqrt(252), n_days)
    factor_drift = np.array([0.12, 0.068, 0.09]) / 252

    rows, logret = [], []
    counters: dict[str, int] = {}
    for asset_type, subtype, count, drift, vol, b_eq, b_bd, b_gd, category in ASSET_SPEC:
        prefix = {"Stock": "SYNS", "Bond": "SYNB", "Fund": "SYNF"}[asset_type]
        betas = np.array([b_eq, b_bd, b_gd])
        for _ in range(count):
            counters[asset_type] = counters.get(asset_type, 0) + 1
            k = counters[asset_type]
            asset_vol = vol * rng.uniform(0.7, 1.3)
            idio = rng.normal((drift - betas @ factor_drift * 252) / 252 * rng.uniform(0.6, 1.4),
                              asset_vol * 0.6 / np.sqrt(252), n_days)
            logret.append(b_eq * equity + b_bd * bond + b_gd * gold + idio)
            sector = (STOCK_SECTORS[(k - 1) % len(STOCK_SECTORS)] if asset_type == "Stock"
                      else "Sovereign" if subtype == "Government" else "Corporate" if subtype == "Corporate" else None)
            rows.append({"asset_id": f"{prefix}{k:08d}", "asset_type": asset_type, "asset_subtype": subtype,
                         "far_trans_category": category, "sector": sector,
                         "asset_name": f"Synthetic {subtype} {k:03d}"})
    assets = pd.DataFrame(rows)
    sub = assets["asset_subtype"].to_numpy()
    start_price = np.select(
        [assets["asset_type"] == "Stock", assets["asset_type"] == "Bond", sub == "Money Market Fund", sub == "Gold Fund"],
        [np.clip(400 * np.exp(rng.normal(0, 0.9, len(assets))), 20, 6000), rng.uniform(950, 1050, len(assets)),
         rng.uniform(1000, 3500, len(assets)), rng.uniform(35, 65, len(assets))],
        rng.uniform(12, 250, len(assets)))
    prices = np.maximum(_round(start_price[:, None] * np.exp(np.cumsum(np.vstack(logret), axis=1)), 4), 0.01)

    # The goal engine's return series, built the way the application builds its own: the equal-weight blend of
    # an equity / bond / gold series (the app: QQQ / AGG / GLD), compounded from daily to contribution-period returns
    # by the application's own helper.
    from wealthpilot.api.services.analysis_service import _compound_to_period_returns

    simple = prices[:, 1:] / prices[:, :-1] - 1.0
    class_daily = pd.DataFrame({
        "EQUITY": simple[(assets["asset_type"] == "Stock").to_numpy()].mean(axis=0),
        "BOND": simple[(assets["asset_type"] == "Bond").to_numpy()].mean(axis=0),
        "GOLD": simple[sub == "Gold Fund"].mean(axis=0),
    })
    weights = equal_weight_portfolio(list(class_daily.columns))
    period_returns = _compound_to_period_returns(class_daily.dot(weights).to_numpy(), CONTRIBUTION_PERIODS_PER_YEAR)
    month_index = ((dates.year - 2019) * 12 + dates.month - 1).to_numpy()
    # first business day on or after day d (1..28) of each month -- for SIP instalment dates
    sip_day = np.empty((N_MONTHS, 28), dtype=int)
    for m in range(N_MONTHS):
        year, month = 2019 + m // 12, m % 12 + 1
        stamps = pd.to_datetime([f"{year}-{month:02d}-{d:02d}" for d in range(1, 29)])
        sip_day[m] = np.minimum(np.searchsorted(dates, stamps), n_days - 1)
    return {"dates": dates, "date_str": dates.strftime("%Y-%m-%d").to_numpy(), "month_index": month_index,
            "sip_day": sip_day, "assets": assets, "prices": prices, "goal_returns": period_returns}


# ---------------------------------------------------------------------------
# 2. Customers
# ---------------------------------------------------------------------------


def generate_customers(n: int, s: dict, market: dict) -> tuple[pd.DataFrame, dict]:
    rd, rl, ri, rh = s["demographics"], s["latent"], s["income"], s["household"]

    # latent traits (never written out; every observable column is a noisy consequence of them)
    z_ses = rl.normal(size=n)                                    # socio-economic background
    z_prudence = rl.normal(size=n)
    z_tolerance = rl.normal(size=n)                              # psychological risk tolerance
    z_leverage = 0.8 * rl.normal(size=n) - 0.3 * z_prudence       # appetite for credit
    z_lifestyle = 0.6 * z_ses + 0.8 * rl.normal(size=n)
    z_stability = rl.normal(size=n)
    z_experience = rl.normal(size=n)
    z_impulsive = 0.6 * rl.normal(size=n) + 0.4 * z_experience + 0.3 * z_tolerance

    # --- 1. life stage
    age_f = 21 + rd.gamma(2.2, 8.5, n)          # right-skewed adult ages; re-drawn above 78, never clipped
    for _ in range(30):
        bad = age_f >= 78.5
        if not bad.any():
            break
        age_f[bad] = 21 + rd.gamma(2.2, 8.5, int(bad.sum()))
    age = np.round(np.minimum(age_f, 78.49)).astype(int)
    old = (age > 45).astype(float)
    edu_logits = np.column_stack([-0.9 * z_ses + 0.5 * old, 0.7 + 0 * z_ses, 0.7 * z_ses - 0.4 * old - 0.2,
                                  1.1 * z_ses - 3.0, -1.8 - 0.3 * z_ses])
    education = np.array(EDUCATION)[_categorical(rd, _softmax(edu_logits))]
    tier = _categorical(rd, _softmax(np.column_stack([0.8 * z_ses - 0.35, 0.3 + 0 * z_ses, -0.6 * z_ses - 0.15])))
    city_tier = np.array(CITY_TIERS)[tier]
    advanced = np.isin(education, ["Master", "PhD"])
    p_student = np.where(age <= 24, 0.40, np.where((age <= 28) & advanced, 0.15, 0.0))
    p_retired = np.where(age >= 60, 0.80, np.where(age >= 56, 0.15, 0.0))
    p_unemployed = 0.035 + 0.03 * (age < 27) + 0.03 * (education == "High School") - 0.01 * np.tanh(z_ses)
    p_self = 0.18 + 0.08 * np.isin(education, ["High School", "Other"]) + 0.05 * (age >= 40)
    u = rd.random((n, 4))
    status = np.full(n, "Employed", dtype=object)
    status[u[:, 0] < p_student] = "Student"
    free = status == "Employed"
    status[free & (u[:, 1] < p_retired)] = "Retired"
    free = status == "Employed"
    status[free & (u[:, 2] < p_unemployed)] = "Unemployed"
    free = status == "Employed"
    status[free & (u[:, 3] < p_self)] = "Self-employed"
    student, retired, unemployed = status == "Student", status == "Retired", status == "Unemployed"
    self_employed = status == "Self-employed"
    start_age = pd.Series(education).map({"High School": 19, "Other": 20, "Bachelor": 22, "Master": 24,
                                          "PhD": 28}).to_numpy()
    retire_age = rd.integers(55, 61, n)
    working_end = np.where(retired, np.minimum(age, retire_age), age)
    gap = rd.gamma(1.0, 1.2, n) + np.where(unemployed, rd.gamma(1.2, 1.0, n), 0.0)
    employment_years = np.where(student, 0.0, np.clip(np.round(working_end - start_age - gap), 0, None))

    # --- 2. income (annual, INR): education x tier x experience curve x background, log-normal
    base = pd.Series(education).map({"High School": 2.2, "Other": 2.4, "Bachelor": 3.8, "Master": 5.2,
                                     "PhD": 7.0}).to_numpy() * LAKH       # entry-level medians (0 years)
    tier_mult = np.array([1.25, 1.0, 0.85])[tier]
    curve = lambda y: 1 + 1.6 * (1 - np.exp(-y / 9)) + 0.9 * (1 - np.exp(-y / 25))  # noqa: E731
    late = np.where(age > 55, 1 - 0.012 * (age - 55), 1.0)
    career_income = base * tier_mult * curve(employment_years) * np.exp(0.35 * z_ses)   # what a career pays
    median = career_income * late
    sigma = np.full(n, 0.38)
    median = np.where(self_employed, median * 1.05, median)
    sigma = np.where(self_employed, 0.72, sigma)
    median = np.where(retired, career_income * ri.uniform(0.25, 0.6, n), median)          # pension / interest
    sigma = np.where(retired, 0.45, sigma)
    median = np.where(unemployed, 0.9 * LAKH * tier_mult, median)                         # support / odd jobs
    sigma = np.where(unemployed, 0.6, sigma)
    median = np.where(student, np.where(education == "PhD", 3.6 * LAKH, 0.7 * LAKH), median)  # stipend
    sigma = np.where(student, np.where(education == "PhD", 0.2, 0.5), sigma)
    annual_income = np.round(_bounded_lognormal(ri, median, sigma, 0.25 * LAKH, 500 * LAKH), -2)
    monthly_income = _round(annual_income / 12)
    income_growth_rate = _round(np.clip(np.select(
        [status == "Employed", self_employed, retired],
        [ri.normal(0.09 - 0.0015 * (age - 25), 0.04), ri.normal(0.07, 0.10), ri.normal(0.035, 0.02)],
        ri.normal(0.05, 0.12)), -0.3, 0.5), 4)
    income_stability_score = _round(np.clip(
        np.select([status == "Employed", self_employed, retired, student], [72, 50, 80, 35], 20)
        + 12 * z_stability + ri.normal(0, 6, n), 0, 100), 1)
    income_source_count = np.minimum(1 + ri.poisson(0.15 + 0.3 * (annual_income > 15 * LAKH) + 0.4 * retired), 5)

    # --- 3. household
    married_p = np.where(age < 23, 0.03, np.clip(0.1 + 0.075 * (age - 23), 0.1, 0.85))
    marital = np.where(rh.random(n) < married_p, "Married", "Single")
    marital = np.where((marital == "Single") & (age > 33) & (rh.random(n) < 0.08), "Divorced", marital)
    marital = np.where((age > 58) & (rh.random(n) < 0.12), "Widowed", marital)
    married = marital == "Married"
    child_lambda = np.select([(age >= 30) & (age <= 50), (age >= 25) & (age < 30), (age > 50) & (age <= 55)],
                             [1.5, 0.5, 0.6], np.where(age > 55, 0.08, 0.02))
    children = np.where(np.isin(marital, ["Married", "Divorced", "Widowed"]), rh.poisson(child_lambda), 0)
    children = np.where(student, 0, np.minimum(children, 4))
    parents = np.where((age >= 30) & (age <= 58) & (rh.random(n) < 0.22), rh.integers(1, 3, n), 0)
    spouse_dependent = married & (rh.random(n) < 0.45)
    dependents = np.minimum(children + parents + spouse_dependent, 7)
    household = 1 + dependents
    segment = _categorical(s["segment"], _softmax(np.column_stack([   # planted expense segment
        1.1 * z_prudence - 0.4 * z_lifestyle - 0.3 * z_leverage, 0.6 + 0 * z_prudence,
        -0.9 * z_prudence + 0.7 * z_lifestyle - 0.3, 1.2 * z_leverage - 0.9])))
    housing_logits = np.column_stack([
        1.5 * (age <= 27) + 2.5 * student - 0.8 * married - 1.0,
        0.3 * (tier == 0) + 0.2 + 0 * age,
        0.8 * ((age >= 28) & (age <= 58)) + 0.6 * np.log(np.maximum(career_income, 1) / (6 * LAKH))
        + 0.6 * (segment == 3) - 1.4 - 2.5 * (student | unemployed) - 0.8 * retired,
        0.06 * (age - 40) + 0.4 * (tier == 2) - 0.5])
    housing = _categorical(rh, _softmax(housing_logits))
    housing_status = np.array(HOUSING)[housing]
    mortgage = housing == 2

    # --- 4. debt (instalments from the annuity formula)
    rdb = s["debt"]
    earners = ~(student | unemployed)
    has_vehicle = rdb.random(n) < np.where(earners, _sigmoid(-1.0 + 0.9 * np.log(annual_income / (8 * LAKH))
                                                             + 0.3 * (tier == 0)), 0.1)

    # --- 5a. spending: essentials as an income-dependent budget share (poorer households spend a larger share),
    # scaled by household size, city tier and lifestyle; then discretionary from what is left after essentials + EMIs
    re_ = s["expenses"]
    life = np.exp(0.25 * z_lifestyle)
    noise = lambda sd: np.exp(re_.normal(0, sd, n))  # noqa: E731
    supported = student | unemployed     # they report their own spending; family covers the household
    non_housing_share = np.clip(0.45 * (monthly_income / 40000) ** -0.30, 0.18, 0.85) \
        * (np.where(supported, 1, household) ** 0.4 / 2 ** 0.4) * life ** 0.3 * np.array([1.08, 1.0, 0.92])[tier] \
        * noise(0.12)
    non_housing = monthly_income * non_housing_share
    base_split = np.column_stack([
        0.33 + 0.035 * np.minimum(household, 6),                       # food (more mouths, more of the budget)
        0.17 + 0.05 * has_vehicle,                                     # transport
        0.08 + 0.002 * np.maximum(age - 40, 0),                        # healthcare
        np.where(children > 0, 0.12 * np.minimum(children, 3) ** 0.7, 0.0),   # children's education
        np.full(n, 0.13),                                              # utilities
        np.where(re_.random(n) < _sigmoid(0.3 + 0.8 * z_ses + 0.5 * married), 0.09, 0.0)])   # insurance
    split_draw = re_.gamma(40 * base_split)
    split = split_draw / split_draw.sum(axis=1, keepdims=True)
    food, transport, healthcare, education_cost, utilities, insurance = (non_housing * split[:, i] for i in range(6))
    min_rent = np.array([9000, 5500, 3500])[tier] * (1 + 0.12 * (household - 1)) * re_.uniform(0.85, 1.2, n)
    rent = np.maximum(min_rent, np.array([0.25, 0.18, 0.13])[tier] * monthly_income * life ** 0.5 * noise(0.15))
    housing_cost = np.select([housing == 0, housing == 1, housing == 2],
                             [np.maximum(1000, 0.06 * monthly_income) * noise(0.3), rent,
                              (0.025 * monthly_income + 1000 * np.array([1.4, 1.0, 0.7])[tier]) * noise(0.2)],
                             (0.02 * monthly_income + 700) * noise(0.2))
    essentials = housing_cost + food + transport + healthcare + education_cost + utilities + insurance

    sizing_income = np.where(retired | unemployed, career_income, annual_income)   # income when the loan was taken
    property_value = sizing_income * rdb.uniform(2.5, 5.0, n) * np.array([1.2, 1.0, 0.8])[tier]
    home_rate = np.clip(rdb.normal(0.088, 0.006, n), 0.075, 0.11)
    home_tenure = rdb.choice([15, 20, 25], n)
    # affordability when the loan was taken: EMI <= min(45% of the sizing income, what that income leaves after
    # essential living costs and a 10% buffer). Essentials are taken as the share of income they absorb now. The
    # cap never falls below 10% of income, because these customers do hold a mortgage (a stretched one).
    essential_share = np.clip(essentials / monthly_income, 0.0, 0.9)
    emi_share_cap = np.maximum(np.minimum(0.45, 1.0 - essential_share - 0.10), 0.10)
    foir_cap = emi_share_cap * (sizing_income / 12) / _annuity_payment(1.0, home_rate, home_tenure)
    home_principal = np.minimum(property_value * rdb.uniform(0.6, 0.8, n), foir_cap)
    home_elapsed = np.where(retired, rdb.uniform(0.7, 0.95, n), rdb.uniform(0, 0.8, n)) * home_tenure
    home_loan = _round(np.where(mortgage, _remaining_balance(home_principal, home_rate, home_tenure, home_elapsed), 0))
    home_emi = np.where(mortgage, _annuity_payment(home_principal, home_rate, home_tenure), 0.0)
    car = annual_income >= 7 * LAKH
    vehicle_price = np.where(car, np.clip(annual_income * rdb.uniform(0.4, 1.0, n), 4 * LAKH, 25 * LAKH),
                             rdb.uniform(0.7, 1.8, n) * LAKH)
    new_credit = np.where(age > 70, 0.0, np.where(retired, 0.2, 1.0))   # lenders rarely lend new to retirees
    has_auto = has_vehicle & earners & (rdb.random(n) < 0.55 * new_credit)
    auto_tenure = np.where(car, 5, 3)
    auto_rate = rdb.uniform(0.09, 0.12, n)
    auto_principal = vehicle_price * rdb.uniform(0.7, 0.9, n)
    auto_elapsed = rdb.uniform(0, 0.9, n) * auto_tenure
    auto_loan = _round(np.where(has_auto, _remaining_balance(auto_principal, auto_rate, auto_tenure, auto_elapsed), 0))
    auto_emi = np.where(has_auto, _annuity_payment(auto_principal, auto_rate, auto_tenure), 0.0)
    p_personal = _sigmoid(-2.4 + 1.1 * z_leverage + 0.9 * (segment == 3) + 0.4 * (segment == 2)) \
        * np.where(earners, 1.0, 0.3) * new_credit
    has_personal = rdb.random(n) < p_personal
    personal_rate = rdb.uniform(0.12, 0.18, n)
    # lenders cap all instalments together at ~60% of income; a small over-leveraged tail (4%) gets past it
    room = np.maximum(0.60 * monthly_income - home_emi - auto_emi, 0) / _annuity_payment(1.0, personal_rate, 3)
    room = np.where(rdb.random(n) < 0.04, np.inf, room)
    personal_principal = np.minimum(np.maximum(career_income, annual_income) * rdb.uniform(0.1, 0.6, n), room)
    has_personal &= personal_principal >= 20000
    personal_elapsed = rdb.uniform(0, 2.7, n)
    personal_loan = _round(np.where(has_personal, _remaining_balance(personal_principal, personal_rate, 3,
                                                                     personal_elapsed), 0))
    personal_emi = np.where(has_personal, _annuity_payment(personal_principal, personal_rate, 3), 0.0)
    has_card = rdb.random(n) < _sigmoid(-0.3 + 1.2 * z_ses + 0.8 * np.log(annual_income / (5 * LAKH))) \
        * np.where(earners, 1.0, 0.4)
    card_limit = np.where(has_card, np.maximum(np.round(monthly_income * rdb.uniform(1.5, 3.5, n), -3), 10000), 0.0)
    revolver = has_card & (rdb.random(n) < np.clip(np.array([0.15, 0.30, 0.50, 0.65])[segment]
                                                    + 0.1 * np.tanh(z_leverage), 0.02, 0.95))
    card_debt = _round(np.where(revolver, card_limit * rdb.beta(2, 3, n), 0.0))
    total_debt = _round(home_loan + auto_loan + personal_loan + card_debt)
    monthly_emi = _round(home_emi + auto_emi + personal_emi + 0.05 * card_debt)   # cards: 5% minimum due

    # --- 5b. discretionary spending from what is left after essentials + EMIs
    residual = monthly_income - essentials - monthly_emi
    # higher earners tend to spend a smaller share of what is left (gently -- segment and noise still dominate)
    income_grade = np.clip((monthly_income / 60000) ** -0.2, 0.6, 1.5)
    discretionary = np.maximum(0.04 * monthly_income * life,
                               np.array([0.20, 0.35, 0.60, 0.35])[segment] * income_grade * np.maximum(residual, 0)) \
        * noise(0.2)
    other = 0.02 * monthly_income * noise(0.4)
    # realism cap per customer: an outflow above it makes the customer cut discretionary / other spending first,
    # then economise on essentials (never below 60%); deficits remain possible, bounded
    cap = monthly_income * np.where(supported, re_.uniform(1.1, 1.8, n), re_.uniform(1.0, 1.3, n))
    over = np.maximum(essentials + discretionary + other + monthly_emi - cap, 0)
    flexible = discretionary + other
    cut_flex = np.minimum(over, 0.7 * flexible)
    scale_flex = np.where(flexible > 0, 1 - cut_flex / np.where(flexible > 0, flexible, 1), 1.0)
    discretionary, other = discretionary * scale_flex, other * scale_flex
    over = np.maximum(over - cut_flex, 0)
    cut_ess = np.minimum(over, 0.4 * essentials)
    scale_ess = 1 - cut_ess / essentials
    housing_cost, food, transport, healthcare, education_cost, utilities, insurance = (
        x * scale_ess for x in (housing_cost, food, transport, healthcare, education_cost, utilities, insurance))
    components = _round(np.column_stack([housing_cost, food, transport, healthcare, education_cost, utilities,
                                         insurance, discretionary, other]))
    monthly_expenses = _round(components.sum(axis=1))
    monthly_essential = _round(components[:, :7].sum(axis=1))

    # --- 6. savings and wealth (flows first, then the stocks they accumulate into)
    rs = s["savings"]
    monthly_savings = _round(monthly_income - monthly_expenses - monthly_emi)
    positive = np.maximum(monthly_savings, 0.0)
    invest_share = np.clip(0.05 + 0.3 * _sigmoid(z_tolerance + 0.5 * z_experience) + 0.25 * _sigmoid(z_prudence)
                           + rs.normal(0, 0.05, n), 0, 0.85)
    investment_contribution = _round(positive * invest_share)
    accumulate_years = np.minimum(employment_years, 10) * rs.uniform(0.2, 0.8, n)
    retention = 0.10 + 0.25 * _sigmoid(z_prudence)
    cash_savings = (positive - investment_contribution) * 12 * accumulate_years * retention \
        + monthly_income * rs.uniform(0.3, 2.0, n) * (0.5 + _sigmoid(z_prudence))
    cash_savings = np.where(monthly_savings < 0, monthly_income * rs.uniform(0.1, 1.2, n), cash_savings)
    cash_savings = np.where(retired, cash_savings + annual_income * rs.uniform(0.3, 2.0, n), cash_savings)
    cash_savings = _round(np.maximum(cash_savings, 500.0))
    years_investing = np.round(employment_years * _sigmoid(z_experience + 0.5))
    portfolio_value = investment_contribution * 12 * years_investing * (1 + 0.06 * years_investing) \
        * rs.uniform(0.6, 1.2, n)
    portfolio_value += np.where(z_ses > 1.2, annual_income * np.exp(rs.normal(0.0, 0.8, n)), 0.0)   # inheritance
    portfolio_value += np.where(retired, career_income * rs.uniform(1.0, 5.0, n), 0.0)              # corpus
    portfolio_value = _round(np.maximum(portfolio_value, monthly_income * rs.uniform(0.5, 3.0, n)))  # FDs at least
    savings_stability = _round(np.clip(55 + 15 * z_prudence + rs.normal(0, 8, n), 0, 100), 1)

    # --- 7. risk: latent components -> documented score + label noise -> ordinal classes
    rr = s["risk"]
    horizon = np.where(retired, rr.integers(3, 16, n),
                       np.clip(np.round(60 - age + rr.normal(0, 3, n)), 1, 40)).astype(int)
    tolerance = z_tolerance + 0.2 * z_experience
    liquidity_months = (cash_savings + 0) / np.maximum(monthly_essential, 1)
    capacity = 0.45 * _z(np.log(annual_income)) + 0.25 * _z(np.log1p(liquidity_months)) - 0.2 * _z(dependents) \
        + 0.2 * z_stability
    stability = 0.5 * z_stability + 0.3 * _z(np.clip(monthly_savings / monthly_income, -1, 1)) \
        + 0.2 * _z(income_stability_score)
    experience = z_experience + 0.3 * _z(age)
    latent_risk = 0.45 * tolerance + 0.25 * capacity + 0.15 * _z(horizon) + 0.10 * stability + 0.05 * experience \
        + rr.normal(0, 0.5, n)
    thresholds = np.quantile(latent_risk, np.cumsum(RISK_SHARES)[:-1])
    risk_label = np.array(RISK_CLASSES)[np.searchsorted(thresholds, latent_risk)]
    risk_tolerance_score = _round(np.clip(50 + 16 * (tolerance + rr.normal(0, 0.7, n)), 0, 100), 1)
    risk_capacity_score = _round(np.clip(50 + 16 * (capacity + rr.normal(0, 0.6, n)), 0, 100), 1)
    financial_stability_score = _round(np.clip(50 + 14 * (stability + rr.normal(0, 0.6, n)), 0, 100), 1)
    exp_obs = experience + rr.normal(0, 0.5, n)
    investment_experience = np.array(EXPERIENCE)[np.searchsorted(np.quantile(exp_obs, [0.20, 0.50, 0.85]), exp_obs)]
    loss_obs = tolerance + rr.normal(0, 0.8, n)
    loss_tolerance = np.array(LOSS_TOLERANCE)[np.searchsorted(np.quantile(loss_obs, [0.35, 0.80]), loss_obs)]

    # --- 8. investor type and allocation
    ra = s["allocation"]
    activity = 0.4 * z_experience + 0.25 * z_tolerance + 0.35 * _z(np.log(portfolio_value)) + ra.normal(0, 0.6, n)
    investor_type = np.searchsorted(np.quantile(activity, np.cumsum(INVESTOR_SHARES)[:-1]), activity)
    a = 0.5 * tolerance + 0.2 * capacity + 0.2 * _z(horizon) + 0.1 * experience + ra.normal(0, 0.3, n)
    target = np.column_stack([
        0.08 + 0.72 * _sigmoid(1.4 * a),                                   # equity
        np.full(n, 0.20),                                                  # bonds / debt funds / FDs
        0.06 + 0.06 * _sigmoid(-a) + 0.03 * (age > 50),                    # gold
        0.04 + 0.20 * _sigmoid(-1.5 * a) + 0.25 * (investor_type == 0),    # cash / liquid
        np.full(n, 0.04)])                                                 # other
    target[:, 1] = np.maximum(1.0 - target[:, [0, 2, 3, 4]].sum(axis=1), 0.03)
    target /= target.sum(axis=1, keepdims=True)
    draws = ra.gamma(30 * target)
    alloc = draws / draws.sum(axis=1, keepdims=True)
    alloc_pct = _round(alloc * 100)
    alloc_pct[np.arange(n), alloc_pct.argmax(axis=1)] += _round(100 - alloc_pct.sum(axis=1))
    alloc_pct = _round(alloc_pct)
    liquid_assets = _round(cash_savings + portfolio_value * alloc_pct[:, 3] / 100)

    # --- emergency fund: the production rule (core/goals.py::assess_emergency_fund)
    ef = [assess_emergency_fund(float(e), float(v)) for e, v in zip(monthly_essential, liquid_assets)]
    ef_required = _round([x.required_amount for x in ef])
    ef_status = np.where([x.sufficient for x in ef], "sufficient", "insufficient")

    # FAR-Trans categorical attributes: assigned by rank to FAR-Trans's own shares (the band names carry EUR
    # thresholds, which are NOT applied to INR amounts -- no currency conversion)
    investable = portfolio_value + cash_savings
    wealth_rank = pd.Series(investable).rank(pct=True).to_numpy()
    investment_capacity = np.array(CAPACITY_BANDS)[np.searchsorted(np.cumsum(CAPACITY_SHARES)[:-1], wealth_rank)]
    standing = 0.6 * pd.Series(annual_income).rank(pct=True).to_numpy() + 0.4 * wealth_rank + ra.normal(0, 0.08, n)
    customer_type = np.where(standing >= np.quantile(standing, 0.68), "Premium", "Mass")
    customer_type = np.where(self_employed & (annual_income >= 15 * LAKH) & (ra.random(n) < 0.6), "Professional",
                             customer_type)
    emi_ratio = monthly_emi / monthly_income
    debt_profile = np.select([total_debt == 0, emi_ratio < 0.15, emi_ratio < 0.35],
                             ["debt-free", "low", "moderate"], "high")

    # --- time: onboarding, and the point-in-time cutoff every customer feature is computed as of
    rt = s["activity"]
    last_onboarding = int(np.searchsorted(market["dates"], pd.Timestamp("2022-06-30"), side="right") - 1)
    last_cutoff = int(np.searchsorted(market["dates"], pd.Timestamp(LAST_CUTOFF_DATE), side="right") - 1)
    onboarding = rt.integers(0, last_onboarding + 1, n)
    cutoff = np.minimum(onboarding + np.round(rt.uniform(12, 30, n) * BDAYS_PER_MONTH).astype(int), last_cutoff)

    customers = pd.DataFrame({
        "customer_id": [f"SYN{i:06d}" for i in range(1, n + 1)],
        "data_source": "synthetic_generated",
        "onboarding_date": market["date_str"][onboarding],
        "feature_cutoff_date": market["date_str"][cutoff],
        "customer_type": customer_type, "investment_capacity": investment_capacity,
        "age": age, "dependents": dependents, "employment_status": status,
        "employment_years": employment_years.astype(float), "marital_status": marital, "education_level": education,
        "city_tier": city_tier, "housing_status": housing_status,
        "annual_income": annual_income, "monthly_income": monthly_income, "income_growth_rate": income_growth_rate,
        "income_stability_score": income_stability_score, "income_source_count": income_source_count.astype(float),
        "monthly_expenses": monthly_expenses,
        **{name: components[:, i] for i, name in enumerate(EXPENSE_COMPONENTS)},
        "monthly_essential_expenses": monthly_essential,
        "total_debt": total_debt, "monthly_emi": monthly_emi, "credit_card_debt": card_debt,
        "credit_card_limit": _round(card_limit), "personal_loan_debt": personal_loan, "home_loan_debt": home_loan,
        "auto_loan_debt": auto_loan,
        "debt_to_income_ratio": _round(total_debt / annual_income, 6),
        "emi_to_income_ratio": _round(monthly_emi / monthly_income, 6),
        "credit_utilization": np.where(card_limit > 0, _round(card_debt / np.where(card_limit > 0, card_limit, 1), 6),
                                       np.nan),
        "debt_profile": debt_profile,
        "cash_savings": cash_savings, "monthly_savings": monthly_savings,
        "savings_rate": _round(monthly_savings / monthly_income, 6), "liquid_assets": liquid_assets,
        "investment_contribution": investment_contribution, "savings_stability": savings_stability,
        "investment_portfolio_value": portfolio_value,
        "emergency_fund_months": _round(liquid_assets / monthly_essential, 4),
        "emergency_fund_target_months": EMERGENCY_FUND_TARGET_MONTHS,
        "emergency_fund_required": ef_required, "emergency_fund_status": ef_status,
        "expense_to_income_ratio": _round(monthly_expenses / monthly_income, 6),
        "savings_to_income_ratio": _round(cash_savings / annual_income, 6),
        "liquidity_ratio": _round(liquid_assets / monthly_expenses, 6),
        "discretionary_expense_ratio": _round(components[:, 7] / monthly_expenses, 6),
        "investment_ratio": _round(investment_contribution / monthly_income, 6),
        "risk_tolerance_score": risk_tolerance_score, "risk_capacity_score": risk_capacity_score,
        "investment_horizon_years": horizon, "financial_stability_score": financial_stability_score,
        "investment_experience": investment_experience, "loss_tolerance": loss_tolerance,
        "equity_pct": alloc_pct[:, 0], "bond_pct": alloc_pct[:, 1], "gold_pct": alloc_pct[:, 2],
        "cash_pct": alloc_pct[:, 3], "other_pct": alloc_pct[:, 4],
        "investor_type": np.array(INVESTOR_TYPES)[investor_type],
        "risk_label": risk_label, "expense_segment": np.array(EXPENSE_SEGMENTS)[segment],
    })
    internal = {"onboarding": onboarding, "cutoff": cutoff, "investor_type": investor_type, "alloc": alloc,
                "z_impulsive": z_impulsive, "z_prudence": z_prudence, "age": age, "children": children,
                "tier": tier, "housing": housing, "portfolio_value": portfolio_value, "investable": investable,
                "investment_contribution": investment_contribution, "monthly_savings": monthly_savings,
                "annual_income": annual_income, "monthly_expenses": monthly_expenses, "ef_required": ef_required,
                "has_auto": has_auto, "retired": retired, "equity_share": alloc_pct[:, 0] / 100,
                "bond_share": alloc_pct[:, 1] / 100}
    return customers, internal


# ---------------------------------------------------------------------------
# 3. Transactions: SIP instalments, lump sums, active trading, later sells, injected anomalies
# ---------------------------------------------------------------------------

# trading classes: Stock, Bond, Equity Fund, Bond Fund, Balanced Fund, Money Market Fund, Gold Fund
CLASS_SUBTYPES = ["Equity", None, "Equity Fund", "Bond Fund", "Balanced Fund", "Money Market Fund", "Gold Fund"]
FUND_CLASSES = np.array([2, 3, 4, 5, 6])


def _class_asset_index(assets: pd.DataFrame) -> list[np.ndarray]:
    return [np.flatnonzero(assets["asset_type"] == "Stock"), np.flatnonzero(assets["asset_type"] == "Bond"),
            *[np.flatnonzero(assets["asset_subtype"] == sub) for sub in CLASS_SUBTYPES[2:]]]


def _vector_pick(class_assets: list[np.ndarray], class_sizes: np.ndarray, cls: np.ndarray,
                 offset: np.ndarray) -> np.ndarray:
    out = np.empty(len(cls), dtype=int)
    for c, members in enumerate(class_assets):
        m = cls == c
        out[m] = members[offset[m] % class_sizes[c]]
    return out


def _days_in_window(rng: np.random.Generator, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    return lo + np.floor(rng.random(len(lo)) * (hi - lo + 1)).astype(int)


def generate_transactions(n: int, s: dict, market: dict, internal: dict) -> tuple[pd.DataFrame, dict]:
    rb, rsl, ran, rch, rsip = s["buys"], s["sells"], s["anomaly"], s["channel"], s["sip"]
    n_days = len(market["dates"])
    last = n_days - 1
    onboarding, cutoff, itype = internal["onboarding"], internal["cutoff"], internal["investor_type"]
    portfolio, investable = internal["portfolio_value"], internal["investable"]
    class_assets = _class_asset_index(market["assets"])
    class_sizes = np.array([len(c) for c in class_assets])
    a = internal["alloc"]  # equity, bond, gold, cash, other
    class_p = np.column_stack([0.7 * a[:, 0], 0.7 * a[:, 1], 0.3 * a[:, 0], 0.3 * a[:, 1], a[:, 4],
                               0.3 * a[:, 3], a[:, 2]])
    class_p = 0.9 * class_p / class_p.sum(axis=1, keepdims=True) + 0.1 / 7
    favourite = rb.integers(0, class_sizes.max(), size=(n, 7))
    lot_cap = np.maximum(0.5 * investable, 1000.0)
    events: list[tuple] = []   # (customer, day, class, amount, sell probability, median holding days, anomalous)

    def add(cust, day, cls, amount, p_sell, hold_days, anomalous=False):
        events.append((cust, day, cls, np.clip(amount, 500.0, lot_cap[cust]), np.full(len(cust), p_sell),
                       np.full(len(cust), hold_days), np.full(len(cust), anomalous)))

    # occasional lump sums (occasional investors; SIP investors top up now and then)
    k = np.where(itype == 1, 1 + rb.poisson(2.5, n), np.where(itype == 2, rb.poisson(1.2, n), 0))
    cust = np.repeat(np.arange(n), k)
    first = np.r_[True, cust[1:] != cust[:-1]] if len(cust) else np.array([], bool)
    day = _days_in_window(rb, onboarding[cust], np.full(len(cust), last))
    day[first] = np.minimum(onboarding[cust[first]] + rb.integers(0, 60, first.sum()), last)
    fund_pref = class_p[cust] * np.array([0.25, 0.1, 1, 1, 1, 0.4, 0.6])     # lump sums go mostly into funds
    cls = _categorical(rb, fund_pref / fund_pref.sum(axis=1, keepdims=True))
    add(cust, day, cls, portfolio[cust] * np.exp(rb.normal(np.log(0.08), 0.6, len(cust))), 0.25, 250)

    # regular SIPs: 1-3 plans per SIP investor, monthly on a fixed day, amounts in multiples of Rs 500
    sip_n = np.where(itype == 2, 1 + rsip.binomial(2, 0.3, n), 0)
    sc = np.repeat(np.arange(n), sip_n)
    start_m = market["month_index"][onboarding[sc]] + rsip.integers(1, 7, len(sc))
    duration = np.maximum(6, np.round(np.exp(rsip.normal(np.log(18), 0.6, len(sc))))).astype(int)
    end_m = np.minimum(start_m + duration - 1, N_MONTHS - 1)
    per_plan = internal["investment_contribution"][sc] * rsip.uniform(0.3, 0.8, len(sc)) / np.maximum(sip_n[sc], 1)
    sip_amount = np.floor(per_plan / 500) * 500            # SIPs run in multiples of Rs 500
    keep = (start_m <= N_MONTHS - 1) & (sip_amount >= 500)  # a plan the customer cannot fund does not exist
    sc, start_m, end_m, sip_amount = sc[keep], start_m[keep], end_m[keep], sip_amount[keep]
    has_sip_plan = np.zeros(n, dtype=bool)
    has_sip_plan[sc] = True
    sip_fund = FUND_CLASSES[_categorical(rsip, (class_p[sc][:, FUND_CLASSES]
                                                / class_p[sc][:, FUND_CLASSES].sum(axis=1, keepdims=True)))]
    dom = rsip.integers(1, 29, len(sc))
    count = end_m - start_m + 1
    ic = np.repeat(np.arange(len(sc)), count)
    im = np.repeat(start_m, count) + (np.arange(count.sum()) - np.repeat(np.cumsum(count) - count, count))
    sip_days = market["sip_day"][im, dom[ic] - 1]
    events.append((sc[ic], sip_days, sip_fund[ic], sip_amount[ic], np.full(len(ic), 0.05), np.full(len(ic), 400),
                   np.zeros(len(ic), bool)))
    sip_asset_plan = favourite[sc, sip_fund] + rsip.integers(0, 3, len(sc))   # one fund per plan

    # highly active traders: many stock-heavy trades, partly clustered, short holding periods
    k = np.where(itype == 3, rb.poisson(np.exp(rb.normal(np.log(50), 0.5, n))), 0)
    cust = np.repeat(np.arange(n), k)
    day = _days_in_window(rb, onboarding[cust], np.full(len(cust), last))
    centres = onboarding[:, None] + np.floor(rb.random((n, 5)) * (n_days - onboarding[:, None])).astype(int)
    clustered = rb.random(len(cust)) < 0.5
    day[clustered] = np.clip(centres[cust[clustered], rb.integers(0, 5, clustered.sum())]
                             + np.round(rb.normal(0, 4, clustered.sum())).astype(int), onboarding[cust[clustered]], last)
    stock_pref = class_p[cust] * np.array([1.6, 0.6, 1, 0.5, 0.5, 0.3, 0.6])  # traders favour stocks
    cls = _categorical(rb, stock_pref / stock_pref.sum(axis=1, keepdims=True))
    add(cust, day, cls, portfolio[cust] * np.exp(rb.normal(np.log(0.04), 0.7, len(cust))), 0.6, 40)

    # natural variation: 6% of investors have one ordinary busy month (NOT an anomaly)
    active = np.flatnonzero(itype > 0)
    busy = active[rb.random(len(active)) < 0.06]
    busy_n = rb.integers(3, 9, len(busy))
    bstart = _days_in_window(rb, onboarding[busy], np.maximum(onboarding[busy], cutoff[busy] - BDAYS_PER_MONTH))
    bc = np.repeat(busy, busy_n)
    bday = np.minimum(np.repeat(bstart, busy_n) + rb.integers(0, BDAYS_PER_MONTH, len(bc)), last)
    add(bc, bday, _categorical(rb, class_p[bc]), portfolio[bc] * np.exp(rb.normal(np.log(0.06), 0.6, len(bc))),
        0.3, 200)

    # the planted anomaly population: impulsive investors, one burst of unusually many and large buys in the
    # asset class they normally use least, inside the observation window after >= 4 months of history
    window_ok = (cutoff - onboarding) >= 6 * BDAYS_PER_MONTH
    score = np.where((itype > 0) & window_ok, internal["z_impulsive"] + ran.normal(0, 0.35, n), -np.inf)
    anomaly_customers = np.sort(np.argsort(-score)[: int(round(0.025 * n))])
    lo = onboarding[anomaly_customers] + 4 * BDAYS_PER_MONTH
    hi = np.maximum(lo, cutoff[anomaly_customers] - BDAYS_PER_MONTH)
    astart = _days_in_window(ran, lo, hi)
    acount = ran.integers(10, 31, len(anomaly_customers))
    ac = np.repeat(anomaly_customers, acount)
    aday = np.minimum(np.repeat(astart, acount) + ran.integers(0, BDAYS_PER_MONTH, len(ac)), cutoff[ac])
    least = np.array([0, 1, 6])[np.argmin(class_p[anomaly_customers][:, [0, 1, 6]], axis=1)]
    typical = np.maximum(portfolio * 0.06, 2000.0)
    add(ac, aday, np.repeat(least, acount), np.minimum(typical[ac] * ran.uniform(3, 8, len(ac)),
                                                       0.3 * investable[ac]), 0.3, 200, anomalous=True)
    behavior_anomaly = np.zeros(n, dtype=int)
    behavior_anomaly[anomaly_customers] = 1
    anomaly_month = np.full(n, "", dtype=object)
    anomaly_month[anomaly_customers] = pd.to_datetime(market["date_str"][astart]).strftime("%Y-%m").to_numpy()

    cust, day, cls, amount, p_sell, hold, anomalous = (np.concatenate(x) for x in zip(*events))
    offset = favourite[cust, cls] + rb.geometric(0.3, len(cust)) - 1
    n_sip = len(ic)
    sip_start = sum(len(e[0]) for e in events[:1])   # the SIP block is the second event block
    offset[sip_start:sip_start + n_sip] = sip_asset_plan[ic]                        # SIPs keep their fund
    anomaly_block = slice(len(cust) - len(ac), len(cust))
    offset[anomaly_block] = favourite[ac, np.repeat(least, acount)] + ran.geometric(0.7, len(ac)) - 1
    asset = _vector_pick(class_assets, class_sizes, cls, offset)

    prices = market["prices"]
    price = prices[asset, day]
    whole_units = cls <= 1  # stocks and bonds trade in whole units; funds in thousandths
    qty = np.where(whole_units, np.maximum(1, np.floor(amount / price)), np.maximum(0.001, np.round(amount / price, 3)))
    value = _round(qty * price)

    # sells: a lot may later be sold, fully or partly -- never more units than the lot holds
    sold = rsl.random(len(cust)) < p_sell
    delay = np.maximum(1, np.ceil(np.exp(rsl.normal(np.log(hold), 0.8, len(cust))))).astype(int)
    sell_day = day + delay
    sold &= sell_day <= last
    fraction = np.where(rsl.random(len(cust)) < 0.6, 1.0, rsl.uniform(0.2, 0.95, len(cust)))
    sell_qty = np.where(whole_units, np.floor(qty * fraction), np.floor(qty * fraction * 1000) / 1000)
    sold &= sell_qty > 0
    si = np.flatnonzero(sold)
    s_price = prices[asset[si], sell_day[si]]

    all_cust = np.concatenate([cust, cust[si]])
    all_day = np.concatenate([day, sell_day[si]])
    all_asset = np.concatenate([asset, asset[si]])
    is_buy = np.concatenate([np.ones(len(cust), bool), np.zeros(len(si), bool)])
    all_qty = np.concatenate([qty, sell_qty[si]])
    all_price = np.concatenate([price, s_price])
    all_value = np.concatenate([value, _round(sell_qty[si] * s_price)])

    pref = np.column_stack([np.full(n, 6.0) - 0.05 * (internal["age"] - 40),
                            np.full(n, 2.0) + 0.04 * (internal["age"] - 40), np.full(n, 2.0)])
    pref = rch.gamma(np.clip(pref, 0.5, None))
    channel = _categorical(rch, (pref / pref.sum(axis=1, keepdims=True))[all_cust])

    order = np.lexsort((all_asset, ~is_buy, all_cust, all_day))  # date, customer, buys before sells, asset
    all_cust, all_day, all_asset, is_buy, all_qty, all_price, all_value, channel = (
        x[order] for x in (all_cust, all_day, all_asset, is_buy, all_qty, all_price, all_value, channel))
    total = len(all_cust)

    # portfolio_weight: the asset's share of the customer's cumulative purchase value up to and including this
    # transaction (cost basis, backward-looking only)
    frame = pd.DataFrame({"c": all_cust, "a": all_asset, "bv": np.where(is_buy, all_value, 0.0)})
    frame["seq"] = np.arange(total)
    chron = frame.sort_values(["c", "seq"], kind="stable")
    cum_asset = chron.groupby(["c", "a"], sort=False)["bv"].cumsum()
    cum_all = chron.groupby("c", sort=False)["bv"].cumsum()
    weight = np.empty(total)
    weight[chron["seq"].to_numpy()] = (cum_asset / cum_all).to_numpy()

    assets = market["assets"]
    transactions = pd.DataFrame({
        "transaction_id": [f"TX{i:010d}" for i in range(1, total + 1)],
        "customer_id": np.char.add("SYN", np.char.zfill((all_cust + 1).astype(str), 6)),
        "transaction_date": market["date_str"][all_day],
        "transaction_type": np.where(is_buy, "Buy", "Sell"),
        "buy_sell_indicator": np.where(is_buy, 1, -1),
        "asset_type": assets["asset_type"].to_numpy()[all_asset],
        "asset_subtype": assets["asset_subtype"].to_numpy()[all_asset],
        "asset_id": assets["asset_id"].to_numpy()[all_asset],
        "quantity": all_qty,
        "price": all_price,
        "transaction_value": all_value,
        "portfolio_weight": _round(weight, 6),
        "channel": np.array(CHANNELS)[channel],
    })
    return transactions, {"cust": all_cust, "day": all_day, "is_buy": is_buy, "value": all_value,
                          "has_sip_plan": has_sip_plan,
                          "behavior_anomaly": behavior_anomaly, "anomaly_month": anomaly_month,
                          "n_anomaly_trades": int(anomalous.sum())}


def add_behaviour_features(customers: pd.DataFrame, internal: dict, tx: dict, market: dict) -> pd.DataFrame:
    """Customer behaviour features from transactions ON OR BEFORE each customer's feature_cutoff_date only.
    Ratios with a zero denominator (no trades yet) are empty -- not applicable, never 0."""
    n = len(customers)
    cutoff, onboarding = internal["cutoff"], internal["onboarding"]
    pre = tx["day"] <= cutoff[tx["cust"]]
    c, buy, value = tx["cust"][pre], tx["is_buy"][pre], tx["value"][pre]
    trade_count = np.bincount(c, minlength=n)
    buy_value = _round(np.bincount(c[buy], weights=value[buy], minlength=n))
    sell_value = _round(np.bincount(c[~buy], weights=value[~buy], minlength=n))
    month = market["month_index"]
    first_m, last_m = month[onboarding], month[cutoff]
    observed_months = last_m - first_m + 1
    flat = c * N_MONTHS + month[tx["day"][pre]]
    per_month = np.bincount(flat, minlength=n * N_MONTHS).reshape(n, N_MONTHS).astype(float)
    m = np.arange(N_MONTHS)
    in_window = (m[None, :] >= first_m[:, None]) & (m[None, :] <= last_m[:, None])
    per_month = np.where(in_window, per_month, 0.0)
    mean = per_month.sum(axis=1) / observed_months
    var = np.maximum((per_month ** 2).sum(axis=1) / observed_months - mean ** 2, 0.0)
    traded = trade_count > 0
    customers["trade_count"] = trade_count
    customers["buy_value"] = buy_value
    customers["sell_value"] = sell_value
    customers["portfolio_turnover"] = np.where(buy_value > 0, _round(sell_value / np.where(buy_value > 0, buy_value, 1),
                                                                     6), np.nan)
    customers["average_transaction_value"] = np.where(
        traded, _round((buy_value + sell_value) / np.maximum(trade_count, 1)), np.nan)
    customers["investment_frequency"] = _round(trade_count / observed_months, 4)
    customers["behaviour_volatility"] = np.where(traded, _round(np.sqrt(var) / np.where(traded, mean, 1), 4), np.nan)
    customers["behavior_anomaly"] = tx["behavior_anomaly"]
    customers["behavior_anomaly_month"] = np.where(tx["anomaly_month"] == "", None, tx["anomaly_month"])
    return customers


# ---------------------------------------------------------------------------
# 4. Goals, analysed by the production goal engine
# ---------------------------------------------------------------------------


def generate_goals(customers: pd.DataFrame, internal: dict, s: dict, market: dict) -> pd.DataFrame:
    rg = s["goals"]
    n = len(customers)
    age, children, tier = internal["age"], internal["children"], internal["tier"]
    income = internal["annual_income"]
    retired = internal["retired"]
    owns = np.isin(internal["housing"], [2, 3])
    # eligibility x life-stage weights; ineligible types get weight 0
    w = np.column_stack([
        np.where(customers["emergency_fund_status"] == "insufficient", 3.0, 0.6),
        np.where(retired | (age > 57), 0.0, np.where(age >= 28, 2.5, 1.0)),
        np.where(children > 0, 2.2, 0.0),
        np.where(~owns & (age >= 24) & (age <= 50), 2.0, 0.0),
        np.where(internal["has_auto"], 0.3, 1.0),
        np.full(n, 1.0),
        np.where(income >= 12 * LAKH, 1.6, 0.9),
        np.full(n, 0.7)])
    eligible = (w > 0).sum(axis=1)
    n_goals = np.minimum(np.minimum(1 + rg.poisson(2.2, n), 6), eligible)
    scores = np.where(w > 0, np.log(np.where(w > 0, w, 1)) + rg.gumbel(size=w.shape), -np.inf)
    ranked = np.argsort(-scores, axis=1)
    cust = np.repeat(np.arange(n), n_goals)
    rank = np.arange(len(cust)) - np.repeat(np.cumsum(n_goals) - n_goals, n_goals)
    gtype = ranked[cust, rank]
    priority = rank + 1
    m = len(cust)
    inc, ag = income[cust], age[cust]
    u = rg.random(m)

    years = np.select(
        [gtype == 0, gtype == 1, gtype == 2, gtype == 3, gtype == 4, gtype == 5, gtype == 6],
        [1 + 2 * u, np.maximum(3.0, 60 - ag + rg.normal(0, 1, m)), 3 + 13 * u, 2 + 6 * u, 1 + 3 * u,
         0.5 + 2.5 * u, 5 + 15 * u],
        1 + 7 * u)
    as_of = pd.to_datetime(customers["feature_cutoff_date"].to_numpy()[cust])
    target_date = as_of + pd.to_timedelta(np.round(years * 365.25).astype(int), unit="D")
    annual_spend = internal["monthly_expenses"][cust] * 12
    tier_mult = np.array([1.3, 1.0, 0.75])[tier[cust]]
    v = rg.random(m)
    floor = lambda lo: lo * rg.uniform(1.0, 1.6, m)   # noqa: E731  -- a spread-out floor, never a pile-up at lo
    target = np.select(
        [gtype == 0, gtype == 1, gtype == 2, gtype == 3, gtype == 4, gtype == 5, gtype == 6],
        [np.maximum(internal["ef_required"][cust], 10000.0),                                     # production rule
         annual_spend * (20 + 10 * v),                                                           # retirement corpus
         np.maximum(np.exp(rg.normal(np.log(15 * LAKH * (inc / (8 * LAKH)) ** 0.35), 0.4, m))
                    * np.maximum(children[cust], 1) ** 0.6, floor(3 * LAKH)),                   # education
         np.maximum(inc * (3 + 3 * v) * tier_mult * np.where(rg.random(m) < 0.7, 0.25, 1.0), floor(4 * LAKH)),
         np.where(inc >= 7 * LAKH, np.maximum(inc * (0.4 + 0.6 * v), floor(4 * LAKH)),         # car ...
                  (0.7 + 1.3 * v) * LAKH),                                                       # ... or two-wheeler
         np.maximum(inc * (0.05 + 0.25 * v), floor(30000)),                                      # travel
         inc * (1 + 7 * v)],                                                                     # wealth creation
        np.maximum(inc * (0.2 + 1.8 * v), floor(50000)))                                         # other
    typical = target                                   # the type-typical amount for this customer
    achieved = rg.random(m) < 0.04
    paused = ~achieved & (rg.random(m) < 0.03)
    progress = rg.beta(1.2 + 0.4 * np.tanh(internal["z_prudence"][cust]), 3.0)
    raw_current = np.where(achieved, 0.0, typical * progress * 0.9)
    # what is already saved towards goals cannot exceed what the customer owns: earmark a share of cash + portfolio
    earmark = internal["investable"] * rg.uniform(0.3, 0.9, n)
    raw_sum = np.bincount(cust, weights=raw_current, minlength=n)
    fit = np.minimum(1.0, earmark / np.where(raw_sum > 0, raw_sum, 1))
    current = _round(raw_current * fit[cust])
    equity_share, bond_share = internal["equity_share"], internal["bond_share"]
    annual_return = _round(0.06 + 0.06 * equity_share + 0.01 * bond_share + rg.normal(0, 0.005, n), 4)
    inflation = _round(rg.uniform(0.04, 0.06, n), 4)

    # the monthly budget the customer sets aside for goals, split by goal importance and priority
    saving = np.maximum(internal["monthly_savings"], 0.0)
    budget = saving * rg.uniform(0.5, 1.0, n)
    importance = np.array([3.0, 2.0, 2.0, 2.0, 1.0, 0.7, 1.2, 0.8])[gtype] / np.sqrt(priority)
    importance = np.where(achieved | paused, 0.0, importance)
    isum = np.bincount(cust, weights=importance, minlength=n)
    share = np.where(isum[cust] > 0, budget[cust] * importance / np.where(isum[cust] > 0, isum[cust], 1), 0.0)
    months = np.maximum(years * 12, 1)
    # the target: the geometric mean of the type-typical amount and what that budget could reach, with personal
    # variation -- ambitious plans for some, modest for others; the Emergency Fund keeps the production requirement
    # what the plan could reach, in today's money: current savings and the budget share compounded at the real
    # (after-inflation) return the customer assumes
    real = (1 + annual_return[cust]) / (1 + inflation[cust]) - 1
    real_m = (1 + real) ** (1 / 12) - 1
    reach = current * (1 + real) ** years + share * ((1 + real_m) ** (12 * years) - 1) / real_m
    # two planning styles: realistic planners (more likely the more prudent the person) set a target within what
    # their plan can reach; aspirational planners pull it towards the type-typical amount
    realistic = rg.random(m) < 0.2 + 0.4 * _sigmoid(2 * internal["z_prudence"][cust])
    anchor = np.where(realistic, 0.9, rg.uniform(0.3, 0.6, m))      # weight on what the plan can reach
    # realistic planners keep a safety margin (~30% below reach); aspirational ones do not
    style_noise = np.where(realistic, rg.normal(-0.35, 0.2, m), rg.normal(0.0, 0.3, m))
    blended = typical ** (1 - anchor) * np.maximum(reach, 0.02 * typical) ** anchor * np.exp(style_noise)
    # a type-plausible minimum, spread out (a two-wheeler, a short trip, ...) -- never a pile-up at one value
    type_min = np.array([0, 5 * LAKH, 1 * LAKH, 2 * LAKH, 60000, 20000, 50000, 25000], dtype=float)[gtype]
    target = np.where(gtype == 0, _round(typical),
                      np.round(np.maximum(blended, type_min * rg.uniform(1.0, 1.6, m)), -3))  # round amounts
    target = np.where(~achieved & (current >= target), np.round(current * rg.uniform(1.1, 1.6, m), -3) + 1000,
                      target)
    returns = market["goal_returns"]
    as_of_d, target_d = as_of.date, target_date.date
    current = current.astype(float).copy()

    # pass 1 -- what each plan requires: the production engine's required monthly contribution
    required = np.empty(m)
    t0 = time.perf_counter()
    for i in range(m):
        c = cust[i]
        planning = GoalAssumptions(contribution_amount=0.0, contribution_periods_per_year=CONTRIBUTION_PERIODS_PER_YEAR,
                                   annual_return_rate=float(annual_return[c]), annual_inflation_rate=float(inflation[c]))
        goal = GoalInput(customer_id=int(c) + 1, goal_type=GOAL_TYPES[gtype[i]], target_amount=float(target[i]),
                         current_savings=float(current[i]), target_date=target_d[i], priority=int(priority[i]))
        analysis = analyze_goal_funding(goal, planning, as_of_d[i])
        if achieved[i]:  # achieved = already at or above the inflation-adjusted target
            current[i] = round(analysis.inflation_adjusted_target_amount * float(rg.uniform(1.0, 1.15)), 2)
            analysis = analyze_goal_funding(goal.model_copy(update={"current_savings": current[i]}), planning, as_of_d[i])
        required[i] = max(analysis.required_periodic_contribution, 0.0)
    print(f"    goal planning: {m:,} goals ({time.perf_counter() - t0:.0f}s)", flush=True)

    # each person would like to put in about what the plan requires (some under-save, some over-save), but the
    # monthly budget is spread across the goals by importance and priority, each capped at what that goal needs;
    # amounts are whole Rs 100 -- a share under Rs 500 is not worth setting up, so that goal is paused, except that
    # the top-priority goal is always funded when the budget allows at least Rs 500
    active = ~achieved & ~paused
    # disciplined (realistic) planners put in at least about what is required; aspirational savers vary more
    desired = np.where(active, required * np.exp(np.where(realistic, rg.normal(0.3, 0.2, m), rg.normal(0.0, 0.35, m))),
                       0.0)
    contribution = np.floor(np.minimum(desired, share) / 100) * 100
    first_active = active & (pd.Series(np.where(active, priority, 99)).groupby(cust).transform("min").to_numpy()
                             == priority)
    contribution = np.where(contribution < 500, 0.0, contribution)
    others = np.bincount(cust, weights=contribution, minlength=n)[cust] - contribution
    room = np.maximum(budget[cust] - others, 0.0)
    fallback = first_active & (contribution < 500) & (desired > 0) & (room >= 500)
    contribution = np.where(fallback, np.floor(np.minimum(np.maximum(desired, 500), room) / 100) * 100, contribution)
    contribution = np.where(contribution < 500, 0.0, contribution)

    # pass 2 -- the production engine analyses each goal as funded, and its Monte Carlo decides feasibility
    out = {k: np.empty(m) for k in ("adj", "req", "gap", "years", "prob", "cur")}
    feasibility = np.empty(m, dtype=object)
    periods = np.empty(m, dtype=int)
    t0 = time.perf_counter()
    for i in range(m):
        c = cust[i]
        assumptions = GoalAssumptions(contribution_amount=float(contribution[i]),
                                      contribution_periods_per_year=CONTRIBUTION_PERIODS_PER_YEAR,
                                      annual_return_rate=float(annual_return[c]), annual_inflation_rate=float(inflation[c]))
        goal = GoalInput(customer_id=int(c) + 1, goal_type=GOAL_TYPES[gtype[i]], target_amount=float(target[i]),
                         current_savings=float(current[i]), target_date=target_d[i], priority=int(priority[i]))
        analysis = analyze_goal_funding(goal, assumptions, as_of_d[i])
        mc = run_goal_monte_carlo(current_savings=goal.current_savings, periodic_contribution=float(contribution[i]),
                                  n_periods=analysis.periods_remaining,
                                  target_amount=analysis.inflation_adjusted_target_amount,
                                  historical_returns=returns, n_simulations=GOAL_MC_SIMULATIONS)
        out["cur"][i] = goal.current_savings
        out["adj"][i] = analysis.inflation_adjusted_target_amount
        out["req"][i] = analysis.required_periodic_contribution
        out["gap"][i] = analysis.contribution_gap
        out["years"][i] = analysis.years_remaining
        periods[i] = analysis.periods_remaining
        out["prob"][i] = mc.success_probability
        feasibility[i] = classify_feasibility(mc.success_probability)
        if (i + 1) % 50000 == 0:
            print(f"    goal engine: {i + 1:,}/{m:,} goals ({time.perf_counter() - t0:.0f}s)", flush=True)

    status = np.where(out["cur"] >= out["adj"], "Achieved", np.where(contribution <= 0, "Paused", "Active"))
    return pd.DataFrame({
        "goal_id": [f"G{i:08d}" for i in range(1, m + 1)],
        "customer_id": customers["customer_id"].to_numpy()[cust],
        "data_source": "synthetic_generated",
        "goal_type": np.array(GOAL_TYPES)[gtype],
        "priority": priority,
        "analysis_date": customers["feature_cutoff_date"].to_numpy()[cust],
        "target_date": target_date.strftime("%Y-%m-%d"),
        "target_year": target_date.year,
        "years_remaining": _round(out["years"], 4),
        "periods_remaining": periods,
        "target_amount": target,
        "current_amount": _round(out["cur"]),
        "monthly_contribution": contribution,
        "annual_return_rate": annual_return[cust],
        "annual_inflation_rate": inflation[cust],
        "contribution_periods_per_year": CONTRIBUTION_PERIODS_PER_YEAR,
        "inflation_adjusted_target_amount": _round(out["adj"]),
        "required_monthly_contribution": _round(out["req"]),
        "contribution_gap": _round(out["gap"]),
        "goal_status": status,
        "monte_carlo_simulations": GOAL_MC_SIMULATIONS,
        "monte_carlo_success_probability": _round(out["prob"], 4),
        "goal_feasibility": feasibility,
    })


# ---------------------------------------------------------------------------
# 5. Missing values, format exports, writing
# ---------------------------------------------------------------------------


def apply_missingness(customers: pd.DataFrame, rng: np.random.Generator) -> dict[str, float]:
    for column, rate in MISSING_RATES.items():
        mask = rng.random(len(customers)) < rate
        customers.loc[mask, column] = np.nan if customers[column].dtype.kind in "fi" else None
    return {c: round(float(customers[c].isna().mean()), 6) for c in customers.columns if customers[c].isna().any()}


def far_trans_export(customers: pd.DataFrame, transactions: pd.DataFrame, market: dict) -> dict[str, pd.DataFrame]:
    """The same population in the FAR-Trans file format, so the EXISTING loaders and feature code
    (`load_far_trans_tables(dir)`, `engineer_features`, `build_monthly_panel`) read it unchanged. One genuine-
    labelled row per customer, dated at the feature cutoff (the risk pipeline's point-in-time anchor)."""
    assets = market["assets"]
    info = pd.DataFrame({
        "customerID": customers["customer_id"], "customerType": customers["customer_type"],
        "riskLevel": customers["risk_label"], "investmentCapacity": customers["investment_capacity"],
        "lastQuestionnaireDate": customers["feature_cutoff_date"], "timestamp": customers["feature_cutoff_date"],
    })
    asset_info = pd.DataFrame({
        "ISIN": assets["asset_id"], "assetName": assets["asset_name"],
        "assetShortName": assets["asset_id"].str.replace("SYN", "S", regex=False),
        "assetCategory": assets["far_trans_category"], "assetSubCategory": assets["asset_subtype"],
        "marketID": "SYNX", "sector": assets["sector"], "industry": None, "timestamp": START_DATE,
    })
    tx = pd.DataFrame({
        "customerID": transactions["customer_id"], "ISIN": transactions["asset_id"],
        "transactionID": np.arange(1, len(transactions) + 1), "transactionType": transactions["transaction_type"],
        "timestamp": transactions["transaction_date"], "totalValue": transactions["transaction_value"],
        "units": transactions["quantity"], "channel": transactions["channel"], "marketID": "SYNX",
    })
    close = pd.DataFrame({
        "ISIN": np.repeat(assets["asset_id"].to_numpy(), len(market["dates"])),
        "timestamp": np.tile(market["date_str"], len(assets)),
        "closePrice": market["prices"].ravel(),
    })
    return {"customer_information.csv": info, "asset_information.csv": asset_info, "transactions.csv": tx,
            "close_prices.csv": close}


def kaggle_export(customers: pd.DataFrame) -> pd.DataFrame:
    """The same population in the Kaggle personal-finance file format, so the EXISTING expense loader
    (`load_kaggle_primary(dir)` + `engineer_expense_features`) reads it unchanged. Kaggle's own ratio definitions
    are kept: debt_to_income_ratio = monthly EMI / monthly income, savings_to_income_ratio = savings / annual
    income (both rounded to 2 dp, as in the source). Amounts are this population's INR amounts under the format's
    fixed `_usd` column names -- no exchange conversion. Columns this population does not have stay empty."""
    loans = customers[["home_loan_debt", "auto_loan_debt", "personal_loan_debt"]]
    loan_amount = _round(loans.sum(axis=1))
    loan_type = loans.idxmax(axis=1).map({"home_loan_debt": "Home", "auto_loan_debt": "Car",
                                         "personal_loan_debt": "Personal"}).where(loan_amount > 0)
    return pd.DataFrame({
        "user_id": customers["customer_id"], "age": customers["age"], "gender": None,
        "education_level": customers["education_level"], "employment_status": customers["employment_status"],
        "job_title": None, "monthly_income_usd": customers["monthly_income"],
        "monthly_expenses_usd": customers["monthly_expenses"], "savings_usd": customers["cash_savings"],
        "has_loan": np.where(loan_amount > 0, "Yes", "No"), "loan_type": loan_type, "loan_amount_usd": loan_amount,
        "loan_term_months": None, "monthly_emi_usd": customers["monthly_emi"], "loan_interest_rate_pct": None,
        "debt_to_income_ratio": _round(customers["monthly_emi"] / customers["monthly_income"]),
        "credit_score": None,
        "savings_to_income_ratio": _round(customers["cash_savings"] / customers["annual_income"]),
        "region": None, "record_date": customers["feature_cutoff_date"],
    })


def _write_csv(frame: pd.DataFrame, path: Path, chunk: int = 500_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for i, start in enumerate(range(0, len(frame), chunk)):
        frame.iloc[start:start + chunk].to_csv(path, mode="w" if i == 0 else "a", header=i == 0, index=False,
                                               lineterminator="\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_population(customers_n: int, seed: int) -> dict:
    """Everything in memory, nothing written -- used by `generate` and by previews."""
    t0 = time.perf_counter()
    streams = _streams(seed)
    print("[1/5] synthetic market", flush=True)
    market = generate_market(streams["market"])
    print(f"[2/5] {customers_n:,} customers", flush=True)
    customers, internal = generate_customers(customers_n, streams, market)
    print("[3/5] transactions", flush=True)
    transactions, tx = generate_transactions(customers_n, streams, market, internal)
    customers = add_behaviour_features(customers, internal, tx, market)
    no_plan = (customers["investor_type"] == "regular_sip").to_numpy() & ~tx["has_sip_plan"]
    customers.loc[no_plan, "investor_type"] = "occasional"   # the type describes what the customer actually does
    print("[4/5] goals (production goal engine)", flush=True)
    goals = generate_goals(customers, internal, streams, market)
    missing_rates = apply_missingness(customers, streams["missing"])
    return {"market": market, "customers": customers, "transactions": transactions, "goals": goals,
            "missing_rates": missing_rates, "n_anomaly_trades": tx["n_anomaly_trades"],
            "goal_return_periods": len(market["goal_returns"]), "seconds": round(time.perf_counter() - t0, 1)}


def generate(output_dir: Path, customers_n: int, seed: int) -> dict:
    pop = build_population(customers_n, seed)
    customers, transactions, goals = pop["customers"], pop["transactions"], pop["goals"]
    if customers_n >= DEFAULT_CUSTOMERS and (len(transactions) < MIN_TRANSACTIONS or len(goals) < MIN_GOALS):
        raise SystemExit(f"only {len(transactions):,} transactions / {len(goals):,} goals generated")
    print("[5/5] writing CSV files", flush=True)
    files = {
        CUSTOMER_FILE: customers, TRANSACTION_FILE: transactions, GOAL_FILE: goals,
        **{f"{FAR_TRANS_DIR}/{k}": v for k, v in far_trans_export(customers, transactions, pop["market"]).items()},
        f"{KAGGLE_DIR}/{KAGGLE_FILE}": kaggle_export(customers),
    }
    for rel, frame in files.items():
        _write_csv(frame, output_dir / rel)
    pop["files"] = {rel: {"rows": len(frame), "columns": len(frame.columns)} for rel, frame in files.items()}
    print(f"      generated in {pop['seconds']}s", flush=True)
    return pop


def build_metadata(summary: dict, output_dir: Path, seed: int, validation: dict, statistics: dict) -> dict:
    customers, transactions, goals = summary["customers"], summary["transactions"], summary["goals"]
    dist = lambda s: {str(k): int(v) for k, v in s.value_counts(dropna=False).sort_index().items()}  # noqa: E731
    return {
        "dataset_name": "WealthPilot Synthetic Training Dataset",
        "synthetic": True,
        "training_eligible": True,
        "data_source": "synthetic_generated",
        "dataset_purpose": "ml_training",
        "not_empirical": "This dataset is synthetic and must not be represented as empirical customer financial data.",
        "currency": (f"{CURRENCY} throughout. The income bands are modelling choices for realistic variation, not "
                     "claims about any real population. The application itself uses EUR; this dataset is not read "
                     "by it. The kaggle_format copy keeps the Kaggle format's fixed `_usd` column names so the existing "
                     "loader reads it, but its amounts are the same INR amounts -- no exchange conversion anywhere."),
        "capacity_bands": (
            "investment_capacity (CAP_LT30K / CAP_30K_80K / CAP_80K_300K / CAP_GT300K) is RANK-BASED: customers are "
            "ranked by investable wealth (portfolio + cash savings) and assigned to bands in FAR-Trans's own genuine "
            "class proportions (57% / 22% / 17.4% / 3.6%). The bands are NOT fixed INR wealth thresholds -- the EUR "
            "amounts in the band names are FAR-Trans labels and are not applied. A high-income customer with little "
            "investable wealth can therefore legitimately fall in a lower band. customer_type is likewise assigned by "
            "rank to FAR-Trans's shares."),
        "random_seed": seed,
        "generator": "scripts/generate_wealthpilot_synthetic_dataset.py",
        "customer_rows": len(customers),
        "transaction_rows": len(transactions),
        "goal_rows": len(goals),
        "feature_counts": {rel: info["columns"] for rel, info in summary["files"].items()},
        "row_counts": {rel: info["rows"] for rel, info in summary["files"].items()},
        "missing_value_rates": {CUSTOMER_FILE: summary["missing_rates"]},
        "missing_value_policy": (
            "Empty CSV cells. Random missingness only in leaf columns nothing else is computed from. Structurally "
            "empty: credit_utilization without a credit card; portfolio_turnover / average_transaction_value / "
            "behaviour_volatility for customers with no trades before their cutoff (inactive investors); "
            "behavior_anomaly_month where behavior_anomaly = 0. A genuine zero (no debt, no insurance, no "
            "children's education) is written as 0; a missing value never is."),
        "label_distributions": {
            "risk_label": dist(customers["risk_label"]),
            "expense_segment": dist(customers["expense_segment"]),
            "behavior_anomaly": dist(customers["behavior_anomaly"]),
            "goal_feasibility": dist(goals["goal_feasibility"]),
        },
        "statistics": statistics,
        "date_ranges": {
            "market_and_transactions": [START_DATE, END_DATE],
            "transaction_date": [transactions["transaction_date"].min(), transactions["transaction_date"].max()],
            "onboarding_date": [customers["onboarding_date"].min(), customers["onboarding_date"].max()],
            "feature_cutoff_date": [customers["feature_cutoff_date"].min(), customers["feature_cutoff_date"].max()],
            "goal_target_date": [goals["target_date"].min(), goals["target_date"].max()],
        },
        "generation_method": (
            "Life stage -> career -> income -> household -> housing & debt -> spending -> savings & wealth -> risk -> "
            "behaviour -> goals, each step derived from the previous ones plus independent noise (see the generator "
            "docstring and README). Income: log-normal around education x city tier x experience curve x "
            "background, re-drawn (not clipped) outside 0.25 lakh-5 crore. Debt: annuity instalments at sampled "
            "rates/tenures/elapsed time. risk_label = ordinal thresholds (shares 13/42/33/12%) on 0.45*tolerance + "
            "0.25*capacity + 0.15*horizon + 0.10*stability + 0.05*experience + N(0, 0.5). expense_segment drawn from "
            "prudence / lifestyle / leverage before the spending, debt and savings it shapes. behavior_anomaly = the "
            "2.5% most impulsive active investors, each with one injected burst of 10-30 large buys. "
            "goal_feasibility from the production goal engine (core/goals.py) at 500 Monte Carlo paths per goal "
            "(the application uses 10,000); emergency-fund requirement from the production assess_emergency_fund."),
        "latent_variables": ["socio_economic_background", "prudence", "risk_tolerance", "leverage_propensity",
                             "lifestyle", "stability", "investing_experience", "impulsivity"],
        "target_side_columns": {CUSTOMER_FILE: TARGET_SIDE_CUSTOMER_COLUMNS,
                                GOAL_FILE: TARGET_SIDE_GOAL_COLUMNS + ENGINE_OUTPUT_GOAL_COLUMNS},
        "leakage_controls": [
            "Every target is generated from latent variables, never from an observed column; each observed "
            "feature carries independent noise.",
            "The validator requires that no single customer feature predicts risk_label with more than 70% "
            "accuracy (majority baseline 42%) and reports the strongest single features.",
            "Customer behaviour features use only transactions on or before feature_cutoff_date (re-computed and "
            "checked by the validator).",
            "Target-side columns and goal-engine outputs (inflation-adjusted target, required contribution, "
            "contribution gap, goal_status) must not be used as features.",
            "No train/test files are produced; split customers by customer_id (grouped) and transactions by "
            "date (time-ordered), never by random row shuffling.",
        ],
        "goal_engine": {"module": "backend/wealthpilot/core/goals.py", "monte_carlo_simulations": GOAL_MC_SIMULATIONS,
                        "application_monte_carlo_simulations": 10000,
                        "return_periods_available": summary["goal_return_periods"]},
        "exports": {
            FAR_TRANS_DIR: "customer_information, asset_information, transactions, close_prices in the FAR-Trans "
                           "format (markets/limit_prices are not read by any loader and are not produced). "
                           "investmentCapacity / customerType are assigned by wealth / standing rank to FAR-Trans's "
                           "own shares; the EUR thresholds in the band names are not applied to INR amounts.",
            KAGGLE_DIR: f"{KAGGLE_FILE} in the Kaggle personal-finance format.",
            "relationship": ("All three shapes are views of ONE synthetic population. This is not a linkage of the "
                             "real FAR-Trans and Kaggle datasets, which stay separate (ADR-010, ADR-039)."),
        },
        "files": {rel: {**info, "sha256": sha256(output_dir / rel)} for rel, info in summary["files"].items()},
        "validation_status": validation.get("status", "not_run"),
        "validation_summary": validation.get("summary", {}),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "determinism_note": "Every CSV is byte-identical for the same seed and sizes; generated_at is the only "
                            "field that changes between runs.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--customers", type=int, default=DEFAULT_CUSTOMERS)
    parser.add_argument("--transactions", type=int, default=MIN_TRANSACTIONS,
                        help="minimum transaction rows required (the generator produces at least this many)")
    parser.add_argument("--goals", type=int, default=MIN_GOALS, help="minimum goal rows required")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--skip-validation", action="store_true",
                        help="only for the reproducibility check; the default always validates")
    args = parser.parse_args(argv)

    output_dir = args.output_dir.resolve()
    summary = generate(output_dir, args.customers, args.seed)
    if len(summary["transactions"]) < args.transactions or len(summary["goals"]) < args.goals:
        print(f"FAIL  generated {len(summary['transactions']):,} transactions / {len(summary['goals']):,} goals, "
              f"below the requested minimum")
        return 1

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from validate_synthetic_training_dataset import distribution_report

    statistics = distribution_report(summary["customers"], summary["transactions"], summary["goals"])
    validation: dict = {"status": "not_run"}
    if not args.skip_validation:
        print("[6/6] validating", flush=True)
        from validate_synthetic_training_dataset import validate_dataset

        errors, report = validate_dataset(output_dir, require_metadata=False)
        validation = {"status": "passed" if not errors else "failed", "summary": report}
        if errors:
            print("\n".join(f"FAIL  {e}" for e in errors))
    metadata = build_metadata(summary, output_dir, args.seed, validation, statistics)
    (output_dir / METADATA_FILE).write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(f"wrote {output_dir / METADATA_FILE} (validation: {validation['status']})")
    return 0 if validation["status"] in ("passed", "not_run") else 1


if __name__ == "__main__":
    sys.exit(main())
