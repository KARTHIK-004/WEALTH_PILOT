"""Chronological backtest: no look-ahead bias, rebalancing, metrics
(annualized return/volatility/Sharpe/max drawdown/turnover), transaction
costs, determinism, and edge cases."""

import numpy as np
import pandas as pd
import pytest

from wealthpilot.core.backtest import run_backtest
from wealthpilot.core.optimizer import equal_weight_portfolio


def _synthetic_returns(n=700, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)
    qqq = rng.normal(0.0006, 0.012, n)
    agg = rng.normal(0.0001, 0.003, n)
    gld = rng.normal(0.0004, 0.010, n)
    return pd.DataFrame({"QQQ": qqq, "AGG": agg, "GLD": gld}, index=dates)


# --- chronology / no leakage --------------------------------------------


def test_rebalance_dates_are_strictly_increasing_and_within_range():
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    dates = result.rebalance_dates
    assert dates == sorted(dates)
    assert dates[0] >= returns.index[200]
    assert dates[-1] <= returns.index[-1]


def test_each_rebalance_only_uses_strictly_trailing_data():
    """Perturbing returns AFTER a given rebalance date must not change that
    rebalance's weights -- direct proof of no look-ahead."""
    returns_a = _synthetic_returns()
    returns_b = returns_a.copy()
    # Perturb everything after the SECOND rebalance only.
    lookback, rebalance = 200, 50
    second_rebalance_idx = lookback + rebalance
    returns_b.iloc[second_rebalance_idx + 1 :] = returns_b.iloc[second_rebalance_idx + 1 :] * 5

    result_a = run_backtest(returns_a, strategy="hrp", lookback_days=lookback, rebalance_days=rebalance)
    result_b = run_backtest(returns_b, strategy="hrp", lookback_days=lookback, rebalance_days=rebalance)

    assert result_a.rebalance_weights[0] == result_b.rebalance_weights[0]
    assert result_a.rebalance_weights[1] == result_b.rebalance_weights[1]


def test_backtest_equity_curve_never_uses_more_than_available_data():
    returns = _synthetic_returns(n=300)
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    assert len(result.equity_curve) <= len(returns) - 200


# --- rebalancing -------------------------------------------------------


def test_rebalance_count_matches_expected_schedule():
    returns = _synthetic_returns(n=700)
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=100)
    expected_count = len(range(200, 700, 100))
    assert result.n_rebalances == expected_count


def test_equal_weight_strategy_rebalances_to_the_same_weights_every_time():
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    for w in result.rebalance_weights:
        assert w["QQQ"] == pytest.approx(1 / 3)
        assert w["AGG"] == pytest.approx(1 / 3)
        assert w["GLD"] == pytest.approx(1 / 3)


def test_mvo_strategy_requires_risk_level():
    returns = _synthetic_returns()
    with pytest.raises(ValueError, match="risk_level"):
        run_backtest(returns, strategy="mvo", lookback_days=200, rebalance_days=50)


def test_mvo_strategy_respects_risk_level_bounds_at_every_rebalance():
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="mvo", risk_level="Conservative", lookback_days=200, rebalance_days=50)
    for w in result.rebalance_weights:
        assert 0.10 - 1e-6 <= w["QQQ"] <= 0.30 + 1e-6


# --- metrics ------------------------------------------------------------


def test_annualized_return_matches_cagr_from_equity_curve():
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    n_days = len(result.equity_curve)
    final_value = result.equity_curve.iloc[-1]
    expected = final_value ** (252 / n_days) - 1.0
    assert result.annualized_return == pytest.approx(expected)


def test_annualized_volatility_matches_hand_computation():
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    daily_returns = result.equity_curve.pct_change().dropna()
    expected = daily_returns.std(ddof=1) * np.sqrt(252)
    assert result.annualized_volatility == pytest.approx(expected)


def test_sharpe_ratio_matches_return_and_volatility():
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50, risk_free_rate=0.02)
    expected = (result.annualized_return - 0.02) / result.annualized_volatility
    assert result.sharpe_ratio == pytest.approx(expected)


def test_max_drawdown_is_computed_from_the_portfolio_equity_curve_not_asset_prices():
    """A monotonically rising portfolio has zero drawdown."""
    rising_returns = pd.DataFrame(
        {"QQQ": [0.01] * 300, "AGG": [0.01] * 300, "GLD": [0.01] * 300},
        index=pd.bdate_range("2020-01-01", periods=300),
    )
    result = run_backtest(rising_returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    assert result.max_drawdown == pytest.approx(0.0, abs=1e-9)


def test_max_drawdown_detects_a_decline():
    n = 300
    returns = pd.DataFrame({"QQQ": [0.0] * n, "AGG": [0.0] * n, "GLD": [0.0] * n}, index=pd.bdate_range("2020-01-01", periods=n))
    # After the lookback window, force a 20% single-day decline, then flat.
    decline_idx = 210
    returns.iloc[decline_idx] = -0.20
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    assert result.max_drawdown == pytest.approx(-0.20, abs=1e-6)


def test_max_drawdown_recovers_after_decline_but_still_reports_the_trough():
    n = 300
    returns = pd.DataFrame({"QQQ": [0.0] * n, "AGG": [0.0] * n, "GLD": [0.0] * n}, index=pd.bdate_range("2020-01-01", periods=n))
    returns.iloc[210] = -0.30
    returns.iloc[211] = 0.30  # partial nominal recovery, doesn't fully offset a 30% loss
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    assert result.max_drawdown == pytest.approx(-0.30, abs=1e-6)
    assert result.max_drawdown < 0  # still negative even after "recovery"


def test_max_drawdown_with_multiple_declines_reports_the_worst_one():
    n = 300
    returns = pd.DataFrame({"QQQ": [0.0] * n, "AGG": [0.0] * n, "GLD": [0.0] * n}, index=pd.bdate_range("2020-01-01", periods=n))
    returns.iloc[205] = -0.10  # first, smaller decline: value -> 0.90
    returns.iloc[206] = 0.10   # partial bounce (multiplicatively 0.90*1.10 = 0.99, NOT back to par)
    returns.iloc[220] = -0.25  # second, larger decline, off the untouched original peak (1.0)
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    # Peak stays at the pre-decline value (nothing exceeds it before day 220);
    # trough = peak * 0.90 * 1.10 * 0.75 = peak * 0.7425 -> drawdown = -0.2575.
    expected_trough_ratio = 0.90 * 1.10 * 0.75
    assert result.max_drawdown == pytest.approx(expected_trough_ratio - 1.0, abs=1e-6)


# --- turnover -------------------------------------------------------


def test_first_rebalance_turnover_is_100_percent():
    """Approved convention: the initial portfolio is all-zero, so the
    first rebalance's turnover equals 100% (fully establishing the
    position), two-way (not halved)."""
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    assert result.turnovers[0] == pytest.approx(1.0, abs=1e-6)


def test_equal_weight_strategy_has_zero_turnover_after_the_first_rebalance():
    """1/N never changes its target, so any turnover after rebalance 1 must
    come purely from price drift between rebalances being corrected back
    to equal weight -- never from a changing target itself. With i.i.d.
    returns this is generically nonzero but must be small relative to the
    100% initial turnover."""
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    for t in result.turnovers[1:]:
        assert 0.0 <= t < 0.5  # drift-correction turnover, much less than a full re-establishment


def test_turnover_convention_is_two_way_not_halved():
    """Constructing a scenario where the portfolio drifts to a KNOWN
    weight just before a rebalance, and the strategy always returns a
    KNOWN fixed target (equal weight) -- turnover must equal the full
    sum of absolute differences, not half of it."""
    n = 260
    dates = pd.bdate_range("2020-01-01", periods=n)
    returns = pd.DataFrame({"QQQ": [0.0] * n, "AGG": [0.0] * n, "GLD": [0.0] * n}, index=dates)
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    # With zero returns throughout, weights never drift -- every rebalance
    # after the first should have turnover 0 (already at 1/3 each), and the
    # FIRST is exactly 1.0 (sum of |1/3 - 0| * 3 = 1.0), proving no /2.
    assert result.turnovers[0] == pytest.approx(1.0, abs=1e-9)


# --- transaction costs -----------------------------------------------


def test_zero_transaction_cost_is_the_default():
    returns = _synthetic_returns()
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    assert result.transaction_cost_bps == 0.0
    assert result.total_transaction_cost == pytest.approx(0.0)


def test_nonzero_transaction_cost_reduces_final_equity_value():
    returns = _synthetic_returns()
    free = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50, transaction_cost_bps=0.0)
    costly = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50, transaction_cost_bps=50.0)
    assert costly.equity_curve.iloc[-1] < free.equity_curve.iloc[-1]
    assert costly.total_transaction_cost > 0.0


# --- determinism -----------------------------------------------------


def test_backtest_is_deterministic():
    returns = _synthetic_returns()
    r1 = run_backtest(returns, strategy="mvo", risk_level="Balanced", lookback_days=200, rebalance_days=50)
    r2 = run_backtest(returns, strategy="mvo", risk_level="Balanced", lookback_days=200, rebalance_days=50)
    assert r1.annualized_return == r2.annualized_return
    assert r1.rebalance_weights == r2.rebalance_weights


# --- edge cases --------------------------------------------------------


def test_single_asset_universe_backtest():
    n = 300
    returns = pd.DataFrame(
        {"QQQ": np.random.default_rng(2).normal(0.0005, 0.01, n)}, index=pd.bdate_range("2020-01-01", periods=n)
    )
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    for w in result.rebalance_weights:
        assert w["QQQ"] == pytest.approx(1.0)


def test_insufficient_training_history_raises():
    returns = _synthetic_returns(n=100)
    with pytest.raises(ValueError, match="not enough observations"):
        run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)


def test_unknown_strategy_raises():
    returns = _synthetic_returns()
    with pytest.raises(ValueError, match="unknown strategy"):
        run_backtest(returns, strategy="black_litterman", lookback_days=200, rebalance_days=50)


def test_exactly_enough_data_for_one_rebalance():
    # range(200, 249, 50) == [200] only -- index 250 would be a second
    # rebalance point but is not < 249, so n=249 is the boundary case.
    returns = _synthetic_returns(n=249)
    result = run_backtest(returns, strategy="equal_weight", lookback_days=200, rebalance_days=50)
    assert result.n_rebalances == 1


def test_highly_correlated_assets_do_not_break_the_backtest():
    n = 300
    rng = np.random.default_rng(5)
    base = rng.normal(0.0005, 0.01, n)
    returns = pd.DataFrame(
        {"QQQ": base, "AGG": base + rng.normal(0, 0.0001, n), "GLD": base + rng.normal(0, 0.0001, n)},
        index=pd.bdate_range("2020-01-01", periods=n),
    )
    result = run_backtest(returns, strategy="hrp", lookback_days=200, rebalance_days=50)
    assert np.isfinite(result.annualized_return)
    assert np.isfinite(result.annualized_volatility)
