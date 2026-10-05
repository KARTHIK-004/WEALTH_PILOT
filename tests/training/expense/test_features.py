"""Tests for expense feature engineering: income-normalization, the
zero/negative-income guard, and the log1p leverage-ratio transform."""

import numpy as np
import pandas as pd

from training.expense.common import FEATURE_COLUMNS, engineer_expense_features


def _raw_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"user_id": "U1", "monthly_income_usd": 4000.0, "monthly_expenses_usd": 2000.0,
             "monthly_emi_usd": 400.0, "savings_to_income_ratio": 5.0, "debt_to_income_ratio": 0.3},
            {"user_id": "U2", "monthly_income_usd": 1000.0, "monthly_expenses_usd": 500.0,
             "monthly_emi_usd": 0.0, "savings_to_income_ratio": 2.0, "debt_to_income_ratio": 0.0},
            # Zero income -> every ratio is undefined; must be excluded, not fabricated.
            {"user_id": "U3", "monthly_income_usd": 0.0, "monthly_expenses_usd": 300.0,
             "monthly_emi_usd": 0.0, "savings_to_income_ratio": 0.0, "debt_to_income_ratio": 0.0},
            # Negative income (data-quality edge case) -> also excluded.
            {"user_id": "U4", "monthly_income_usd": -100.0, "monthly_expenses_usd": 300.0,
             "monthly_emi_usd": 0.0, "savings_to_income_ratio": 0.0, "debt_to_income_ratio": 0.0},
        ]
    )


def test_income_normalization_not_raw_currency():
    """Two users with identical raw expense/EMI amounts but different
    incomes must get DIFFERENT ratios — proving the features are
    income-normalized, not raw currency (PROJECT_PLAN.md section 2.2's
    central warning)."""
    raw = pd.DataFrame(
        [
            {"user_id": "RICH", "monthly_income_usd": 10000.0, "monthly_expenses_usd": 2000.0,
             "monthly_emi_usd": 0.0, "savings_to_income_ratio": 1.0, "debt_to_income_ratio": 0.1},
            {"user_id": "POOR", "monthly_income_usd": 2500.0, "monthly_expenses_usd": 2000.0,
             "monthly_emi_usd": 0.0, "savings_to_income_ratio": 1.0, "debt_to_income_ratio": 0.1},
        ]
    )
    features, _ = engineer_expense_features(raw)
    # Same raw expense (2000) but very different expense_to_income_ratio.
    assert features.loc["RICH", "expense_to_income_ratio"] == pytest_approx(0.2)
    assert features.loc["POOR", "expense_to_income_ratio"] == pytest_approx(0.8)
    assert features.loc["RICH", "expense_to_income_ratio"] != features.loc["POOR", "expense_to_income_ratio"]


def test_zero_and_negative_income_rows_are_excluded_not_fabricated():
    features, excluded = engineer_expense_features(_raw_fixture())
    assert excluded == 2
    assert set(features.index) == {"U1", "U2"}
    assert not features.isna().any().any()


def test_feature_columns_present_and_finite():
    features, _ = engineer_expense_features(_raw_fixture())
    assert list(features.columns) == FEATURE_COLUMNS
    assert np.isfinite(features.to_numpy()).all()


def test_emi_ratio_is_log1p_transformed():
    """A user with EMI ratio 0 stays 0 (log1p(0)=0); a user with a large
    raw ratio gets compressed, not left at its raw magnitude."""
    raw = pd.DataFrame(
        [
            {"user_id": "NOLOAN", "monthly_income_usd": 1000.0, "monthly_expenses_usd": 500.0,
             "monthly_emi_usd": 0.0, "savings_to_income_ratio": 1.0, "debt_to_income_ratio": 0.0},
            {"user_id": "BIGLOAN", "monthly_income_usd": 1000.0, "monthly_expenses_usd": 500.0,
             "monthly_emi_usd": 9000.0, "savings_to_income_ratio": 1.0, "debt_to_income_ratio": 0.5},
        ]
    )
    features, _ = engineer_expense_features(raw)
    assert features.loc["NOLOAN", "emi_to_income_ratio"] == pytest_approx(0.0)
    raw_ratio = 9000.0 / 1000.0  # 9.0
    assert features.loc["BIGLOAN", "emi_to_income_ratio"] == pytest_approx(np.log1p(raw_ratio))
    assert features.loc["BIGLOAN", "emi_to_income_ratio"] < raw_ratio  # compressed, not raw


def pytest_approx(value, **kwargs):
    import pytest

    return pytest.approx(value, **kwargs)
