"""Expected returns, covariance, box constraints, MVO, 1/N, HRP, and the
efficient frontier -- against synthetic data with mathematically
verifiable properties, not just "runs without error"."""

import numpy as np
import pandas as pd
import pytest

from wealthpilot.core.optimizer import (
    GENERAL_SINGLE_ASSET_CAP,
    RISK_LEVEL_QQQ_BANDS,
    covariance_ledoit_wolf,
    effective_bounds,
    efficient_frontier,
    equal_weight_portfolio,
    expected_returns_historical,
    hrp_weights,
    min_variance_for_target_return,
    mvo_max_sharpe,
    portfolio_return,
    portfolio_volatility,
    sample_covariance,
    sharpe_ratio,
)


def _synthetic_returns(n=600, seed=1, corr_gld_agg_qqq=True):
    rng = np.random.default_rng(seed)
    qqq = rng.normal(0.0006, 0.012, n)
    agg = rng.normal(0.0001, 0.003, n)
    gld = rng.normal(0.0004, 0.010, n)
    return pd.DataFrame({"QQQ": qqq, "AGG": agg, "GLD": gld})


# --- expected returns / covariance --------------------------------------


def test_expected_returns_matches_hand_computation():
    returns = pd.DataFrame({"A": [0.01, 0.02, -0.01], "B": [0.0, 0.0, 0.0]})
    mu = expected_returns_historical(returns)
    assert mu["A"] == pytest.approx(((0.01 + 0.02 - 0.01) / 3) * 252)
    assert mu["B"] == pytest.approx(0.0)


def test_ledoit_wolf_covariance_is_positive_semidefinite():
    returns = _synthetic_returns()
    cov, shrinkage = covariance_ledoit_wolf(returns)
    eigvals = np.linalg.eigvalsh(cov.to_numpy())
    assert (eigvals >= -1e-8).all()
    assert 0.0 <= shrinkage <= 1.0


def test_ledoit_wolf_shrinks_toward_a_more_conservative_estimate_than_sample():
    """Shrinkage should reduce the spread between the largest and smallest
    eigenvalues relative to the sample covariance -- the defining property
    of shrinkage estimators (stabilizing extreme eigenvalues)."""
    returns = _synthetic_returns()
    lw_cov, shrinkage = covariance_ledoit_wolf(returns)
    sample_cov = sample_covariance(returns)
    assert shrinkage > 0.0  # some genuine shrinkage occurred
    lw_spread = np.linalg.eigvalsh(lw_cov.to_numpy()).ptp()
    sample_spread = np.linalg.eigvalsh(sample_cov.to_numpy()).ptp()
    assert lw_spread <= sample_spread + 1e-9


def test_covariance_matrix_is_symmetric():
    returns = _synthetic_returns()
    cov, _ = covariance_ledoit_wolf(returns)
    np.testing.assert_allclose(cov.to_numpy(), cov.to_numpy().T)


def test_sample_covariance_matches_pandas_cov_annualized():
    returns = _synthetic_returns()
    expected = returns.cov() * 252
    actual = sample_covariance(returns)
    pd.testing.assert_frame_equal(actual, expected)


# --- box constraints -----------------------------------------------------


def test_effective_bounds_intersects_qqq_band_with_general_cap():
    """Aggressive's nominal 80% QQQ ceiling must be tightened to the 70%
    general cap, not silently allowed to exceed it."""
    bounds = effective_bounds("Aggressive")
    assert bounds["QQQ"] == (0.55, GENERAL_SINGLE_ASSET_CAP)


def test_effective_bounds_matches_approved_bands_when_looser_than_cap():
    bounds = effective_bounds("Conservative")
    assert bounds["QQQ"] == RISK_LEVEL_QQQ_BANDS["Conservative"]


def test_effective_bounds_agg_gets_min_cash_allocation_as_lower_bound():
    bounds = effective_bounds("Balanced", min_cash_allocation=0.15)
    assert bounds["AGG"][0] == pytest.approx(0.15)


def test_effective_bounds_gld_has_no_dedicated_band():
    bounds = effective_bounds("Balanced")
    assert bounds["GLD"] == (0.0, GENERAL_SINGLE_ASSET_CAP)


def test_effective_bounds_rejects_unknown_risk_level():
    with pytest.raises(ValueError, match="unknown risk_level"):
        effective_bounds("SuperAggressive")


def test_effective_bounds_rejects_infeasible_lower_bounds():
    with pytest.raises(ValueError, match="infeasible"):
        effective_bounds("Balanced", min_cash_allocation=0.99)  # AGG floor + QQQ floor > 1


def test_effective_bounds_no_short_selling_every_lower_bound_non_negative():
    for risk_level in RISK_LEVEL_QQQ_BANDS:
        bounds = effective_bounds(risk_level)
        for asset, (lower, upper) in bounds.items():
            assert lower >= 0.0
            assert upper <= 1.0


# --- MVO -------------------------------------------------------------


def test_mvo_weights_sum_to_one():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Balanced")
    w = mvo_max_sharpe(mu, cov, bounds)
    assert w.sum() == pytest.approx(1.0, abs=1e-6)


def test_mvo_weights_satisfy_box_constraints():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    for risk_level, bounds in {rl: effective_bounds(rl) for rl in RISK_LEVEL_QQQ_BANDS}.items():
        w = mvo_max_sharpe(mu, cov, bounds)
        for asset, (lower, upper) in bounds.items():
            assert lower - 1e-6 <= w[asset] <= upper + 1e-6, f"{risk_level}/{asset}: {w[asset]} not in [{lower},{upper}]"


def test_mvo_has_no_short_positions():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Aggressive")
    w = mvo_max_sharpe(mu, cov, bounds)
    assert (w >= -1e-9).all()


def test_mvo_is_deterministic():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Balanced")
    w1 = mvo_max_sharpe(mu, cov, bounds)
    w2 = mvo_max_sharpe(mu, cov, bounds)
    pd.testing.assert_series_equal(w1, w2)


def test_mvo_with_uniform_returns_and_diagonal_covariance_matches_analytic_inverse_variance_weights():
    """A known-solution sanity check: with EQUAL expected returns across
    assets, w.mu is constant (= mu) regardless of weights (since
    sum(w)=1), so maximizing Sharpe degenerates to minimizing variance.
    For a DIAGONAL covariance, the unconstrained minimum-variance solution
    has a closed form: w_i is proportional to 1/variance_i (NOT a 100%
    corner solution in the lowest-variance asset -- diversifying into the
    other uncorrelated assets still reduces total variance further)."""
    variances = {"QQQ": 0.09, "AGG": 0.01, "GLD": 0.04}
    mu = pd.Series({k: 0.05 for k in variances})
    cov = pd.DataFrame(np.diag(list(variances.values())), index=list(variances), columns=list(variances))
    bounds = {k: (0.0, 1.0) for k in variances}
    w = mvo_max_sharpe(mu, cov, bounds)

    inv_var = {k: 1.0 / v for k, v in variances.items()}
    total = sum(inv_var.values())
    analytic = {k: v / total for k, v in inv_var.items()}
    for asset in variances:
        assert w[asset] == pytest.approx(analytic[asset], abs=1e-4)


def test_min_variance_for_target_return_hits_the_target():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Balanced")
    target = float(mu.mean())
    w = min_variance_for_target_return(mu, cov, bounds, target)
    assert portfolio_return(w, mu) == pytest.approx(target, abs=1e-4)
    assert w.sum() == pytest.approx(1.0, abs=1e-6)


# --- 1/N -------------------------------------------------------------


def test_equal_weight_is_exactly_one_over_n():
    w = equal_weight_portfolio(["QQQ", "AGG", "GLD"])
    assert w["QQQ"] == pytest.approx(1 / 3)
    assert w.sum() == pytest.approx(1.0)


def test_equal_weight_ignores_risk_level_entirely():
    """1/N must be identical regardless of any risk-level concept -- it
    takes no risk_level argument at all, by design."""
    w1 = equal_weight_portfolio(["QQQ", "AGG", "GLD"])
    w2 = equal_weight_portfolio(["QQQ", "AGG", "GLD"])
    pd.testing.assert_series_equal(w1, w2)


def test_equal_weight_rejects_empty_universe():
    with pytest.raises(ValueError):
        equal_weight_portfolio([])


# --- HRP -------------------------------------------------------------


def test_hrp_weights_sum_to_one():
    returns = _synthetic_returns()
    w = hrp_weights(returns)
    assert w.sum() == pytest.approx(1.0, abs=1e-9)


def test_hrp_weights_are_non_negative():
    returns = _synthetic_returns()
    w = hrp_weights(returns)
    assert (w >= 0).all()


def test_hrp_is_deterministic():
    returns = _synthetic_returns()
    w1 = hrp_weights(returns)
    w2 = hrp_weights(returns)
    pd.testing.assert_series_equal(w1, w2)


def test_hrp_single_asset_universe_gets_full_weight():
    returns = pd.DataFrame({"QQQ": _synthetic_returns()["QQQ"]})
    w = hrp_weights(returns)
    assert w["QQQ"] == pytest.approx(1.0)


def test_hrp_favors_the_lower_variance_asset_in_a_two_asset_case():
    """A textbook HRP property: with two uncorrelated assets, the lower-
    variance one should receive more weight (inverse-variance-like
    allocation within a cluster)."""
    rng = np.random.default_rng(7)
    low_vol = rng.normal(0, 0.01, 500)
    high_vol = rng.normal(0, 0.05, 500)
    returns = pd.DataFrame({"LOW": low_vol, "HIGH": high_vol})
    w = hrp_weights(returns)
    assert w["LOW"] > w["HIGH"]


def test_hrp_highly_correlated_assets_still_produces_valid_weights():
    """Near-duplicate (highly correlated) assets must not break the
    distance/clustering computation."""
    rng = np.random.default_rng(3)
    base = rng.normal(0.0005, 0.01, 500)
    near_duplicate = base + rng.normal(0, 0.0001, 500)  # almost identical
    third = rng.normal(0.0002, 0.02, 500)
    returns = pd.DataFrame({"A": base, "A_PRIME": near_duplicate, "B": third})
    w = hrp_weights(returns)
    assert w.sum() == pytest.approx(1.0, abs=1e-9)
    assert np.isfinite(w).all()


# --- Sharpe ratio helper -----------------------------------------------


def test_sharpe_ratio_matches_hand_computation():
    assert sharpe_ratio(0.10, 0.20, risk_free_rate=0.0) == pytest.approx(0.5)
    assert sharpe_ratio(0.12, 0.20, risk_free_rate=0.02) == pytest.approx(0.5)


def test_sharpe_ratio_zero_volatility_zero_excess_return_is_zero():
    assert sharpe_ratio(0.05, 0.0, risk_free_rate=0.05) == 0.0


# --- efficient frontier ---------------------------------------------


def test_frontier_points_all_satisfy_constraints():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Balanced")
    frontier = efficient_frontier(mu, cov, bounds)
    for _, row in frontier.iterrows():
        w = row["weights"]
        assert abs(sum(w.values()) - 1.0) < 1e-4
        for asset, (lower, upper) in bounds.items():
            assert lower - 1e-4 <= w[asset] <= upper + 1e-4


def test_frontier_includes_exactly_one_max_sharpe_point():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Balanced")
    frontier = efficient_frontier(mu, cov, bounds)
    assert frontier["is_max_sharpe"].sum() == 1


def test_frontier_max_sharpe_point_has_the_highest_sharpe_on_the_frontier():
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Balanced")
    frontier = efficient_frontier(mu, cov, bounds)
    max_sharpe_row = frontier[frontier["is_max_sharpe"]].iloc[0]
    assert max_sharpe_row["sharpe"] >= frontier["sharpe"].max() - 1e-6


def test_frontier_uses_the_same_covariance_and_returns_as_mvo():
    """The frontier must be generated from the SAME assumptions MVO uses --
    not a separately fabricated set of points. Verified by confirming the
    frontier's own max-Sharpe point matches a direct mvo_max_sharpe() call."""
    returns = _synthetic_returns()
    mu = expected_returns_historical(returns)
    cov, _ = covariance_ledoit_wolf(returns)
    bounds = effective_bounds("Balanced")
    frontier = efficient_frontier(mu, cov, bounds)
    max_sharpe_row = frontier[frontier["is_max_sharpe"]].iloc[0]
    direct_w = mvo_max_sharpe(mu, cov, bounds)
    for asset in mu.index:
        assert max_sharpe_row["weights"][asset] == pytest.approx(direct_w[asset], abs=1e-6)
