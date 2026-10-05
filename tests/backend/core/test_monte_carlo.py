"""Monte Carlo goal simulation: reproducibility, output shape, success
probability behaviour, edge cases, and proof that the simulated balance
paths never depend on the goal's own target (no leakage of the thing being
evaluated into the thing generating the evidence)."""

import numpy as np
import pytest

from wealthpilot.core.goals import MONTE_CARLO_SIMULATIONS, RANDOM_STATE, run_goal_monte_carlo


def _returns(n=252, seed=1):
    return np.random.default_rng(seed).normal(0.0004, 0.01, n)  # synthetic daily-ish returns


# --- reproducibility -----------------------------------------------------


def test_same_seed_and_inputs_produce_identical_results():
    hist = _returns()
    r1 = run_goal_monte_carlo(1_000_000, 35_000, 60, 5_000_000, hist, random_state=42)
    r2 = run_goal_monte_carlo(1_000_000, 35_000, 60, 5_000_000, hist, random_state=42)
    assert r1.success_probability == r2.success_probability
    assert r1.median_ending_value == r2.median_ending_value
    assert r1.downside_percentile_value == r2.downside_percentile_value
    assert r1.upside_percentile_value == r2.upside_percentile_value


def test_different_seed_produces_a_different_result():
    hist = _returns()
    r1 = run_goal_monte_carlo(1_000_000, 35_000, 60, 5_000_000, hist, random_state=1)
    r2 = run_goal_monte_carlo(1_000_000, 35_000, 60, 5_000_000, hist, random_state=2)
    assert r1.median_ending_value != r2.median_ending_value


def test_default_random_state_is_42():
    assert RANDOM_STATE == 42


# --- output shape ----------------------------------------------------


def test_output_reports_requested_simulation_and_period_counts():
    result = run_goal_monte_carlo(100_000, 5_000, 24, 200_000, _returns(), n_simulations=2_000)
    assert result.n_simulations == 2_000
    assert result.n_periods == 24


def test_default_simulation_count_is_10000():
    assert MONTE_CARLO_SIMULATIONS == 10_000
    result = run_goal_monte_carlo(100_000, 5_000, 12, 200_000, _returns())
    assert result.n_simulations == 10_000


def test_percentiles_are_correctly_ordered():
    result = run_goal_monte_carlo(500_000, 10_000, 36, 1_000_000, _returns())
    assert result.downside_percentile_value <= result.median_ending_value <= result.upside_percentile_value


def test_success_probability_is_within_unit_interval():
    result = run_goal_monte_carlo(500_000, 10_000, 36, 1_000_000, _returns())
    assert 0.0 <= result.success_probability <= 1.0


# --- success probability behaviour -----------------------------------


def test_higher_contribution_never_decreases_success_probability():
    hist = _returns()
    low = run_goal_monte_carlo(500_000, 1_000, 60, 1_000_000, hist, random_state=42)
    high = run_goal_monte_carlo(500_000, 50_000, 60, 1_000_000, hist, random_state=42)
    assert high.success_probability >= low.success_probability
    assert high.median_ending_value > low.median_ending_value


def test_easier_target_never_decreases_success_probability():
    hist = _returns()
    hard = run_goal_monte_carlo(500_000, 10_000, 60, 5_000_000, hist, random_state=42)
    easy = run_goal_monte_carlo(500_000, 10_000, 60, 100, hist, random_state=42)
    assert easy.success_probability >= hard.success_probability
    assert easy.success_probability == pytest.approx(1.0)


def test_trivially_unreachable_target_gives_near_zero_probability():
    hist = _returns()
    result = run_goal_monte_carlo(0, 0, 12, 10_000_000_000, hist, random_state=42)
    assert result.success_probability == pytest.approx(0.0)


# --- edge cases --------------------------------------------------------


def test_zero_periods_already_sufficient_balance_is_certain_success():
    result = run_goal_monte_carlo(1_000_000, 0, 0, 500_000, _returns())
    assert result.success_probability == 1.0
    assert result.median_ending_value == 1_000_000


def test_zero_periods_insufficient_balance_is_certain_failure():
    result = run_goal_monte_carlo(100_000, 0, 0, 500_000, _returns())
    assert result.success_probability == 0.0
    assert result.median_ending_value == 100_000


def test_zero_current_savings_and_zero_contribution_never_grows():
    result = run_goal_monte_carlo(0, 0, 24, 1, _returns(), random_state=42)
    assert result.median_ending_value == pytest.approx(0.0)
    assert result.success_probability == pytest.approx(0.0)


def test_negative_returns_shrink_the_balance():
    negative_hist = np.full(50, -0.02)  # constant -2% every period, no randomness
    result = run_goal_monte_carlo(100_000, 0, 12, 50_000, negative_hist, n_simulations=100)
    assert result.median_ending_value == pytest.approx(100_000 * (0.98**12), rel=1e-9)


def test_rejects_negative_n_periods():
    with pytest.raises(ValueError):
        run_goal_monte_carlo(100_000, 1_000, -1, 200_000, _returns())


def test_rejects_empty_historical_returns():
    with pytest.raises(ValueError, match="non-empty"):
        run_goal_monte_carlo(100_000, 1_000, 12, 200_000, np.array([]))


def test_rejects_non_positive_simulation_count():
    with pytest.raises(ValueError):
        run_goal_monte_carlo(100_000, 1_000, 12, 200_000, _returns(), n_simulations=0)


def test_single_valued_historical_returns_is_deterministic_growth():
    hist = np.array([0.01])  # every draw must be exactly 1%
    result = run_goal_monte_carlo(100_000, 0, 5, 100_000, hist, n_simulations=10)
    assert result.median_ending_value == pytest.approx(100_000 * (1.01**5), rel=1e-9)


# --- no leakage: target_amount must not influence the simulated paths ----


def test_target_amount_does_not_influence_the_ending_value_distribution():
    hist = _returns()
    cheap_target = run_goal_monte_carlo(500_000, 10_000, 48, 1, hist, random_state=42)
    expensive_target = run_goal_monte_carlo(500_000, 10_000, 48, 999_999_999, hist, random_state=42)
    # Only the comparison against target should differ -- the underlying
    # balance distribution (median/percentiles) must be identical, proving
    # the goal's own target never leaks into how the paths are generated.
    assert cheap_target.median_ending_value == expensive_target.median_ending_value
    assert cheap_target.downside_percentile_value == expensive_target.downside_percentile_value
    assert cheap_target.upside_percentile_value == expensive_target.upside_percentile_value
    assert cheap_target.success_probability != expensive_target.success_probability


def test_bootstrap_resampling_is_order_independent():
    """Since resampling is i.i.d. with replacement, the ORDER of values
    inside historical_returns must not change the STATISTICAL distribution
    of outcomes -- only their multiset of values and the random_state do.
    This confirms no hidden temporal/sequential dependency leaks into the
    simulation. Not an exact-equality check: the same random_state draws
    the same sequence of ARRAY INDICES, but those indices land on different
    values in a reordered array, so individual sampled values (and hence
    the exact ending balances) legitimately differ path-by-path -- only the
    aggregate distribution converges. A large n_simulations keeps the
    comparison tight and non-flaky."""
    hist = _returns()
    forward = run_goal_monte_carlo(500_000, 10_000, 48, 1_000_000, hist, n_simulations=50_000, random_state=42)
    reversed_hist = hist[::-1].copy()
    backward = run_goal_monte_carlo(
        500_000, 10_000, 48, 1_000_000, reversed_hist, n_simulations=50_000, random_state=42
    )
    assert forward.median_ending_value == pytest.approx(backward.median_ending_value, rel=0.01)
    assert forward.success_probability == pytest.approx(backward.success_probability, abs=0.02)
