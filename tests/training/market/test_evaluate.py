"""RMSE/MAE/directional-accuracy correctness and Diebold-Mariano behaviour."""

import numpy as np
import pytest

from training.market.evaluate import diebold_mariano, directional_accuracy, mae, rmse


def test_rmse_known_value():
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.0, 2.0, 5.0])
    # errors: 0, 0, -2 -> mse = 4/3 -> rmse = sqrt(4/3)
    assert rmse(y_true, y_pred) == pytest.approx(np.sqrt(4 / 3))


def test_rmse_zero_for_perfect_forecast():
    y = np.array([0.01, -0.02, 0.03])
    assert rmse(y, y) == pytest.approx(0.0)


def test_mae_known_value():
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.0, 0.0, 5.0])
    # abs errors: 0, 2, 2 -> mean = 4/3
    assert mae(y_true, y_pred) == pytest.approx(4 / 3)


def test_directional_accuracy_all_correct():
    y_true = np.array([0.01, -0.02, 0.03, -0.01])
    y_pred = np.array([0.005, -0.001, 0.10, -0.20])
    assert directional_accuracy(y_true, y_pred) == pytest.approx(1.0)


def test_directional_accuracy_all_wrong():
    y_true = np.array([0.01, -0.02, 0.03])
    y_pred = np.array([-0.01, 0.02, -0.03])
    assert directional_accuracy(y_true, y_pred) == pytest.approx(0.0)


def test_directional_accuracy_nonzero_true_vs_zero_pred_is_a_mismatch():
    y_true = np.array([0.01, -0.02])
    y_pred = np.array([0.0, 0.0])
    assert directional_accuracy(y_true, y_pred) == pytest.approx(0.0)


def test_directional_accuracy_both_zero_is_never_counted_as_a_lucky_match():
    """The documented, conservative rule: even a true-zero-vs-pred-zero
    pair must NOT count as correct, even though np.sign(0) == np.sign(0)
    would otherwise make it look like a match."""
    y_true = np.array([0.0, 0.0, 0.01])
    y_pred = np.array([0.0, 0.0, 0.02])
    # Only the third pair (0.01 vs 0.02, both positive) is a genuine match.
    assert directional_accuracy(y_true, y_pred) == pytest.approx(1 / 3)


def test_diebold_mariano_returns_zero_statistic_for_identical_errors():
    errors = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
    result = diebold_mariano(errors, errors)
    assert result["dm_statistic"] == pytest.approx(0.0)
    assert result["p_value"] == pytest.approx(1.0)


def test_diebold_mariano_detects_clearly_worse_model():
    rng = np.random.default_rng(42)
    small_errors = rng.normal(0, 0.001, 200)  # model A: tiny errors
    large_errors = rng.normal(0, 0.5, 200)  # model B: much larger errors
    result = diebold_mariano(large_errors, small_errors)  # A=large (worse), B=small (better)
    assert result["dm_statistic"] > 0  # positive -> A's losses larger
    assert result["p_value"] < 0.05


def test_diebold_mariano_handles_too_few_observations_gracefully():
    result = diebold_mariano(np.array([0.01]), np.array([0.02]))
    assert result["n_obs"] == 1
    assert result["p_value"] == 1.0


def test_diebold_mariano_is_symmetric_in_sign():
    rng = np.random.default_rng(7)
    a = rng.normal(0, 0.02, 100)
    b = rng.normal(0, 0.01, 100)
    r_ab = diebold_mariano(a, b)
    r_ba = diebold_mariano(b, a)
    assert r_ab["dm_statistic"] == pytest.approx(-r_ba["dm_statistic"], abs=1e-9)
