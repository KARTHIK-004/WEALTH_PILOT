"""Shared utilities for Phase 5 expense-segmentation training scripts.

**Data source and scope, decided explicitly with the user on 2026-09-14**:
FAR-Trans has no income/expense/savings fields at all (verified directly —
`customer_information.csv` and `transactions.csv` contain only risk-profile
and investment-transaction data). Expense segmentation therefore clusters
the Kaggle **primary** dataset's own population
(`datasets/raw/kaggle/synthetic_personal_finance_dataset.csv`,
`miadul/personal-finance-ml-dataset`, confirmed as primary in Phase 2) —
NOT any FAR-Trans customer. No synthetic customer linkage between the two
datasets is created here; that remains the deferred synthetic-assembly
decision. This module's output characterizes the Kaggle population only.

**Feature granularity**: PROJECT_PLAN.md section 2.2 describes clustering on
"every expense category ... as a share of monthly income" to avoid
rediscovering income level instead of spending behaviour. This dataset has
no category-level expense breakdown (groceries/rent/etc.) — only a single
aggregate `monthly_expenses_usd` figure, plus loan/savings/debt fields. The
same core principle (never cluster on raw currency; normalize by income
first) is applied at the granularity this dataset actually supports:
expense-to-income, savings-to-income, debt-to-income, and EMI-to-income
ratios — a real, non-fabricated income-normalized behavioural profile, just
coarser than a category-level one.
"""

from __future__ import annotations

import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from wealthpilot.data.acquisition import KAGGLE_DIR

# common.py -> expense/ -> training/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models" / "expense"
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"
REPORTS_DIR = REPO_ROOT / "reports"

RANDOM_STATE = 42
KAGGLE_PRIMARY_FILENAME = "synthetic_personal_finance_dataset.csv"

FEATURE_COLUMNS = [
    "expense_to_income_ratio",
    "savings_to_income_ratio",
    "debt_to_income_ratio",
    "emi_to_income_ratio",
]


def load_kaggle_primary(kaggle_dir: Path = KAGGLE_DIR) -> pd.DataFrame:
    path = kaggle_dir / KAGGLE_PRIMARY_FILENAME
    if not path.is_file():
        raise FileNotFoundError(
            f"Expected the Kaggle primary dataset at {path} (see docs/PROJECT_PLAN.md "
            "Part 0) — it must not be silently substituted with the alternative dataset."
        )
    return pd.read_csv(path)


def engineer_expense_features(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per Kaggle user_id, income-normalized behavioural ratios.

    Rows with non-positive `monthly_income_usd` are excluded (documented,
    not silently zero-filled or imputed) — a zero/negative income makes
    every income-normalized ratio undefined, and none currently exist in
    the real data (verified: min income is $500), but the guard is real,
    not decorative, and is exercised by a dedicated test.

    `emi_to_income_ratio` is log1p-transformed. Investigated directly: at
    k=2 (the raw sweep's silhouette-best k), the "clusters" found were 587
    extreme-leverage outliers (mean EMI ratio 22.3, max 90.7) against
    31,837 everyone-else customers (mean 0.8) — the same "raw magnitude
    dominates the clustering" trap PROJECT_PLAN.md section 2.2 warns about
    for un-normalized currency amounts, just manifesting through a heavily
    right-skewed, zero-inflated ratio (0 for the ~60% with no loan) instead
    of raw dollars. log1p keeps zeros at zero and compresses the tail so
    the clustering reflects relative differences in leverage rather than a
    handful of extreme magnitudes.
    """
    df = raw.copy()
    positive_income = df["monthly_income_usd"] > 0
    excluded = int((~positive_income).sum())
    df = df[positive_income].copy()

    df["expense_to_income_ratio"] = df["monthly_expenses_usd"] / df["monthly_income_usd"]
    df["emi_to_income_ratio"] = np.log1p(df["monthly_emi_usd"] / df["monthly_income_usd"])
    # savings_to_income_ratio and debt_to_income_ratio are already provided
    # by the dataset — used as-is, not recomputed, to avoid silently
    # disagreeing with the source's own definition of those ratios.

    features = df.set_index("user_id")[FEATURE_COLUMNS]
    return features, excluded


def library_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
