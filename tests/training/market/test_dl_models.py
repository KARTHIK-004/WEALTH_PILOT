"""LSTM/GRU sequence construction, training-only scaler fitting, and no
temporal shuffling."""

import numpy as np
import pandas as pd

from training.market.dl_models import SEQUENCE_LENGTHS, _make_sequences, fit_and_forecast


def test_make_sequences_is_chronological_not_shuffled():
    values = np.arange(30, dtype="float32")
    X, y = _make_sequences(values, window_length=5)
    # Sequence 0 must be [0,1,2,3,4] -> target 5; sequence 1 is [1,2,3,4,5] -> target 6, etc.
    np.testing.assert_array_equal(X[0], [0, 1, 2, 3, 4])
    assert y[0] == 5
    np.testing.assert_array_equal(X[1], [1, 2, 3, 4, 5])
    assert y[1] == 6


def test_make_sequences_target_never_appears_inside_its_own_input():
    values = np.arange(50, dtype="float32")
    X, y = _make_sequences(values, window_length=10)
    for i in range(len(X)):
        assert y[i] not in X[i]


def _synthetic_returns(n, seed=42):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0, 0.01, n))


def test_scaler_is_fit_only_on_training_window():
    """Changing test-period values must not change the chosen sequence
    length's scaler parameters -- proof scaling never sees test data."""
    train = _synthetic_returns(120, seed=1)
    context_a = pd.concat([train, _synthetic_returns(15, seed=2)], ignore_index=True)
    context_b = context_a.copy()
    context_b.iloc[-1] = 999.0  # huge change, test-period only

    result_a = fit_and_forecast("lstm", train, context_a, n_steps=15)
    result_b = fit_and_forecast("lstm", train, context_b, n_steps=15)

    # Scaler fitted mean/scale must be identical -- it never saw the changed value.
    np.testing.assert_allclose(result_a["scaler"].mean_, result_b["scaler"].mean_)
    np.testing.assert_allclose(result_a["scaler"].scale_, result_b["scaler"].scale_)


def test_sequence_length_is_selected_from_the_documented_grid():
    train = _synthetic_returns(120)
    context = pd.concat([train, _synthetic_returns(15, seed=99)], ignore_index=True)
    result = fit_and_forecast("gru", train, context, n_steps=15)
    assert result["window_length"] in SEQUENCE_LENGTHS


def test_insufficient_training_data_returns_nan_not_a_fabricated_forecast():
    """A training window too small for even the shortest sequence length
    (20) must honestly report no forecast, never silently produce one."""
    train = _synthetic_returns(15)  # smaller than the shortest window_length + slack
    context = pd.concat([train, _synthetic_returns(5, seed=7)], ignore_index=True)
    result = fit_and_forecast("lstm", train, context, n_steps=5)
    assert result["window_length"] is None
    assert np.isnan(result["forecast"]).all()


def test_forecast_uses_real_context_values_not_the_models_own_predictions():
    """The rolling forecast for day 2 of the test window must depend on the
    REAL day-1 test value, not on the model's own day-1 forecast --
    verified by checking that changing ONLY the day-1 context value (while
    keeping everything else fixed) changes later forecasts."""
    train = _synthetic_returns(120, seed=1)
    context_a = pd.concat([train, _synthetic_returns(25, seed=2)], ignore_index=True)
    context_b = context_a.copy()
    context_b.iloc[len(train)] = context_b.iloc[len(train)] + 0.5  # perturb the FIRST test-day value

    result_a = fit_and_forecast("lstm", train, context_a, n_steps=25)
    result_b = fit_and_forecast("lstm", train, context_b, n_steps=25)

    # Forecasts at later steps (which include the perturbed day in their
    # input window) must differ from the unperturbed run.
    window_length = result_a["window_length"]
    if window_length is not None and window_length < 25:
        assert not np.allclose(result_a["forecast"][window_length:], result_b["forecast"][window_length:])
