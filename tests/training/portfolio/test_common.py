"""Return-matrix construction: chronological ordering, date alignment,
missing-data handling, and no fabricated observations."""

import numpy as np
import pandas as pd
import pytest

from training.portfolio.common import build_return_matrix


def test_returns_are_simple_pct_change():
    prices = pd.DataFrame(
        {"A": [100.0, 110.0, 99.0]}, index=pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"])
    )
    returns = build_return_matrix(prices)
    assert len(returns) == 2  # first row (no prior price) dropped
    assert returns["A"].iloc[0] == pytest.approx(0.10)
    assert returns["A"].iloc[1] == pytest.approx((99.0 - 110.0) / 110.0)


def test_rejects_unsorted_price_index():
    prices = pd.DataFrame(
        {"A": [100.0, 101.0, 102.0]}, index=pd.to_datetime(["2022-01-05", "2022-01-03", "2022-01-04"])
    )
    with pytest.raises(ValueError, match="chronologically sorted"):
        build_return_matrix(prices)


def test_rejects_duplicate_dates():
    prices = pd.DataFrame(
        {"A": [100.0, 101.0, 102.0]}, index=pd.to_datetime(["2022-01-03", "2022-01-03", "2022-01-04"])
    )
    with pytest.raises(ValueError, match="duplicate dates"):
        build_return_matrix(prices)


def test_rows_with_any_missing_asset_are_dropped_not_imputed():
    """A date where one asset's price is NaN (e.g. that ticker didn't trade
    that day) must be dropped entirely -- never forward-filled or
    otherwise fabricated."""
    dates = pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06"])
    prices = pd.DataFrame(
        {"A": [100.0, 101.0, np.nan, 103.0], "B": [50.0, 50.5, 51.0, 51.5]}, index=dates
    )
    returns = build_return_matrix(prices)
    # Rows touching the NaN (both the NaN row itself and the row whose
    # pct_change would need it as a denominator) must not appear.
    assert not returns.isna().any().any()
    assert len(returns) == 1  # only 2022-01-03 -> 2022-01-04 is fully clean
    assert returns.index[0] == pd.Timestamp("2022-01-04")


def test_fully_aligned_matrix_keeps_every_row():
    dates = pd.bdate_range("2022-01-03", periods=10)
    prices = pd.DataFrame(
        {"A": np.linspace(100, 110, 10), "B": np.linspace(50, 55, 10), "C": np.linspace(20, 22, 10)}, index=dates
    )
    returns = build_return_matrix(prices)
    assert len(returns) == 9
    assert not returns.isna().any().any()


def test_column_order_is_preserved():
    dates = pd.bdate_range("2022-01-03", periods=5)
    prices = pd.DataFrame({"GLD": [1.0] * 5, "AGG": [1.0] * 5, "QQQ": [1.0] * 5}, index=dates)
    returns = build_return_matrix(prices)
    assert list(returns.columns) == ["GLD", "AGG", "QQQ"]
