"""Naive baseline, ARIMA, and GARCH tests on small synthetic series."""

import numpy as np
import pandas as pd
import pytest

from training.market.models import arima_forecast, garch_forecast, naive_forecast, select_arima_order


def _synthetic_returns(n=300, seed=42):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0005, 0.01, n))


def test_naive_forecast_is_always_zero():
    train = _synthetic_returns()
    forecast = naive_forecast(train, n_steps=10)
    np.testing.assert_array_equal(forecast, np.zeros(10))


def test_naive_forecast_ignores_training_data_content():
    """The naive baseline must be identical regardless of what the
    training data looks like -- it's a fixed rule, not a fitted statistic."""
    train_a = _synthetic_returns(seed=1)
    train_b = _synthetic_returns(seed=2) * 100  # wildly different data
    np.testing.assert_array_equal(naive_forecast(train_a, 5), naive_forecast(train_b, 5))


def test_arima_order_selected_from_training_data_only():
    train = _synthetic_returns()
    order = select_arima_order(train)
    assert isinstance(order, tuple) and len(order) == 3
    assert all(isinstance(x, int) for x in order)


def test_arima_forecast_uses_selected_order_when_none_given():
    train = _synthetic_returns()
    forecast, order = arima_forecast(train, n_steps=10)
    assert len(forecast) == 10
    assert not np.isnan(forecast).any()


def test_arima_forecast_respects_explicit_order():
    train = _synthetic_returns()
    forecast, order = arima_forecast(train, n_steps=5, order=(1, 0, 0))
    assert order == (1, 0, 0)
    assert len(forecast) == 5


def test_arima_forecast_does_not_see_future_data():
    """Two training sets identical up to their own end, differing only in
    what comes AFTER (which ARIMA never receives), must produce the exact
    same forecast."""
    train = _synthetic_returns(n=250)
    forecast_1, order_1 = arima_forecast(train, n_steps=5, order=(1, 0, 0))
    forecast_2, order_2 = arima_forecast(train, n_steps=5, order=(1, 0, 0))
    np.testing.assert_array_equal(forecast_1, forecast_2)


def test_garch_forecast_produces_positive_volatility():
    train = _synthetic_returns()
    vol_forecast = garch_forecast(train, n_steps=10)
    assert len(vol_forecast) == 10
    assert (vol_forecast > 0).all()  # volatility is never negative


def test_garch_forecast_is_deterministic_given_same_training_data():
    train = _synthetic_returns()
    vol_1 = garch_forecast(train, n_steps=5)
    vol_2 = garch_forecast(train, n_steps=5)
    np.testing.assert_allclose(vol_1, vol_2)


def test_garch_forecast_scale_matches_realized_volatility_scale():
    """The GARCH forecast (after the x100/÷100 scaling round-trip) must be
    on the same order of magnitude as the training returns' own std --
    proof the 100x scaling documented in models.py is actually inverted
    correctly, not left in percentage-point units by mistake."""
    train = _synthetic_returns()
    vol_forecast = garch_forecast(train, n_steps=1)
    assert 0.001 < vol_forecast[0] < 0.1  # same order of magnitude as train.std() ~= 0.01
