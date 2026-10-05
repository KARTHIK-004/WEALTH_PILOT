"""Return calculation, chronological validation, and missing-data handling."""

import numpy as np
import pandas as pd
import pytest

from training.market.preprocessing import (
    compute_realized_volatility_target,
    compute_returns,
    validate_chronological_order,
)


def _ohlcv_fixture(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2022-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1000] * len(closes)},
        index=dates,
    )


def test_returns_are_simple_not_log():
    ohlcv = _ohlcv_fixture([100.0, 110.0, 99.0])
    returns = compute_returns(ohlcv)
    assert returns.iloc[1] == pytest.approx(0.10)  # (110-100)/100, not log(110/100)
    assert returns.iloc[2] == pytest.approx((99.0 - 110.0) / 110.0)
    assert pd.isna(returns.iloc[0])  # no prior close for the first row


def test_returns_never_forward_filled_for_missing_days():
    """A gap in the index (e.g. a holiday yfinance skips) must not be
    silently filled -- pct_change() naturally skips it, computing the
    return across whatever two real observations exist."""
    dates = pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-07"])  # Jan 5-6 missing (weekend, fine) but no fabricated Jan 5/6 rows
    ohlcv = pd.DataFrame(
        {"open": [100, 105, 110], "high": [100, 105, 110], "low": [100, 105, 110],
         "close": [100, 105, 110], "volume": [1000, 1000, 1000]},
        index=dates,
    )
    returns = compute_returns(ohlcv)
    assert len(returns) == 3  # no fabricated rows inserted
    assert returns.iloc[2] == pytest.approx((110 - 105) / 105)


def test_validate_chronological_order_accepts_sorted_index():
    ohlcv = _ohlcv_fixture([100.0, 101.0, 102.0])
    validate_chronological_order(ohlcv.index)  # must not raise


def test_validate_chronological_order_rejects_unsorted_index():
    ohlcv = _ohlcv_fixture([100.0, 101.0, 102.0])
    shuffled_index = ohlcv.index[[1, 0, 2]]
    with pytest.raises(ValueError, match="chronological"):
        validate_chronological_order(shuffled_index)


def test_validate_chronological_order_rejects_duplicate_dates():
    dates = pd.to_datetime(["2022-01-03", "2022-01-03", "2022-01-04"])
    with pytest.raises(ValueError, match="duplicate"):
        validate_chronological_order(pd.DatetimeIndex(dates))


def test_realized_volatility_target_uses_only_trailing_window():
    """Changing a value AFTER the target date must not change the target
    at that date -- realized vol at date t must only reflect returns up to
    and including t."""
    rng = np.random.default_rng(42)
    returns_a = pd.Series(rng.normal(0, 0.01, 100))
    returns_b = returns_a.copy()
    returns_b.iloc[-1] = 5.0  # huge change, but only at the very last index

    vol_a = compute_realized_volatility_target(returns_a, window=20)
    vol_b = compute_realized_volatility_target(returns_b, window=20)

    # Every value except the last (window ending exactly on the changed
    # point) must be identical.
    pd.testing.assert_series_equal(vol_a.iloc[:-1], vol_b.iloc[:-1])


def test_realized_volatility_target_requires_full_window():
    returns = pd.Series(np.random.default_rng(42).normal(0, 0.01, 10))
    vol = compute_realized_volatility_target(returns, window=20)
    assert vol.isna().all()  # fewer than `window` observations anywhere
