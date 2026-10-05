"""TVM formulas against hand-computed/spreadsheet-verified values, inflation
adjustment, required contribution, and the goal-already-achieved / short-
and long-horizon edge cases."""

from datetime import date

import pytest

from wealthpilot.core.goals import (
    GoalAssumptions,
    GoalInput,
    analyze_goal_funding,
    future_value,
    inflation_adjusted_target,
    n_periods_between,
    periodic_rate_from_annual,
    present_value,
    required_periodic_contribution,
    years_between,
)


# --- future_value --------------------------------------------------------


def test_future_value_lump_sum_only_matches_hand_computation():
    # $10,000 at 6%/year for 10 years, no contributions: 10000 * 1.06^10
    fv = future_value(present_value=10_000, periodic_rate=0.06, n_periods=10, periodic_contribution=0.0)
    assert fv == pytest.approx(10_000 * (1.06**10), rel=1e-12)
    assert fv == pytest.approx(17908.4768, abs=1e-3)  # spreadsheet-verified


def test_future_value_annuity_only_matches_hand_computation():
    # $500/month for 24 months at 1%/month, PV=0: 500 * [(1.01^24-1)/0.01]
    fv = future_value(present_value=0, periodic_rate=0.01, n_periods=24, periodic_contribution=500)
    expected = 500 * (((1.01**24) - 1) / 0.01)
    assert fv == pytest.approx(expected, rel=1e-12)
    assert fv == pytest.approx(13486.73, abs=1e-2)  # spreadsheet-verified: 500 * ((1.01^24 - 1) / 0.01)


def test_future_value_combined_pv_and_pmt():
    fv = future_value(present_value=1000, periodic_rate=0.01, n_periods=12, periodic_contribution=100)
    expected = 1000 * (1.01**12) + 100 * (((1.01**12) - 1) / 0.01)
    assert fv == pytest.approx(expected, rel=1e-12)


def test_future_value_zero_rate_is_simple_addition():
    fv = future_value(present_value=1000, periodic_rate=0.0, n_periods=12, periodic_contribution=100)
    assert fv == pytest.approx(1000 + 100 * 12)


def test_future_value_zero_periods_returns_present_value_unchanged():
    fv = future_value(present_value=5000, periodic_rate=0.08, n_periods=0, periodic_contribution=999)
    assert fv == 5000


def test_future_value_negative_return_shrinks_the_balance():
    fv = future_value(present_value=1000, periodic_rate=-0.05, n_periods=1, periodic_contribution=0)
    assert fv == pytest.approx(950.0)


def test_future_value_rejects_rate_at_or_below_negative_one():
    with pytest.raises(ValueError):
        future_value(1000, -1.0, 12)
    with pytest.raises(ValueError):
        future_value(1000, -1.5, 12)


def test_future_value_rejects_negative_periods():
    with pytest.raises(ValueError):
        future_value(1000, 0.05, -1)


# --- present_value ---------------------------------------------------


def test_present_value_matches_hand_computation():
    pv = present_value(future_value_amount=17908.4768, periodic_rate=0.06, n_periods=10)
    assert pv == pytest.approx(10_000, abs=1e-2)


def test_present_value_zero_periods_returns_future_value_unchanged():
    assert present_value(5000, 0.08, 0) == 5000


def test_present_value_and_future_value_are_inverses():
    fv = future_value(present_value=2500, periodic_rate=0.005, n_periods=36, periodic_contribution=0)
    pv = present_value(fv, 0.005, 36)
    assert pv == pytest.approx(2500, rel=1e-9)


# --- required_periodic_contribution -----------------------------------


def test_required_contribution_solves_back_to_known_pmt():
    fv = future_value(present_value=1000, periodic_rate=0.01, n_periods=12, periodic_contribution=100)
    pmt = required_periodic_contribution(1000, fv, 0.01, 12)
    assert pmt == pytest.approx(100.0, abs=1e-8)


def test_required_contribution_zero_rate_solves_back():
    fv = future_value(present_value=1000, periodic_rate=0.0, n_periods=12, periodic_contribution=250)
    pmt = required_periodic_contribution(1000, fv, 0.0, 12)
    assert pmt == pytest.approx(250.0, abs=1e-8)


def test_required_contribution_can_be_negative_when_pv_alone_overshoots():
    # PV of 1,000,000 for 1 year at 10% already exceeds a 1,050,000 target.
    pmt = required_periodic_contribution(1_000_000, 1_050_000, 0.10, 1)
    assert pmt < 0


def test_required_contribution_zero_periods_already_achieved_returns_zero():
    pmt = required_periodic_contribution(present_value_amount=6_000_000, target_future_value=5_000_000, periodic_rate=0.08, n_periods=0)
    assert pmt == 0.0


def test_required_contribution_zero_periods_with_shortfall_raises():
    with pytest.raises(ValueError, match="no further contribution periods"):
        required_periodic_contribution(present_value_amount=1_000_000, target_future_value=5_000_000, periodic_rate=0.08, n_periods=0)


# --- inflation_adjusted_target -----------------------------------------


def test_inflation_adjustment_matches_hand_computation():
    # 5,000,000 target, 6% inflation, 5 years: 5,000,000 * 1.06^5
    adjusted = inflation_adjusted_target(5_000_000, 0.06, 5)
    assert adjusted == pytest.approx(5_000_000 * (1.06**5), rel=1e-12)
    assert adjusted == pytest.approx(6691128.0, abs=1.0)


def test_inflation_adjustment_with_zero_inflation_is_unchanged():
    assert inflation_adjusted_target(5_000_000, 0.0, 5) == pytest.approx(5_000_000)


def test_inflation_adjustment_distinguishes_nominal_from_adjusted():
    nominal = 5_000_000
    adjusted = inflation_adjusted_target(nominal, 0.06, 10)
    assert adjusted > nominal  # must actually differ, not silently equal


# --- years_between / n_periods_between ----------------------------------


def test_years_between_matches_simple_calendar_math():
    years = years_between(date(2026, 9, 14), date(2031, 9, 14))
    assert years == pytest.approx(5.0, abs=0.01)


def test_years_between_rejects_target_before_current():
    with pytest.raises(ValueError, match="before current_date"):
        years_between(date(2026, 9, 14), date(2020, 1, 1))


def test_years_between_zero_for_same_day():
    assert years_between(date(2026, 9, 14), date(2026, 9, 14)) == 0.0


def test_n_periods_between_monthly():
    periods = n_periods_between(date(2026, 9, 14), date(2031, 9, 14), periods_per_year=12)
    assert periods == 60


def test_n_periods_between_very_short_horizon():
    periods = n_periods_between(date(2026, 9, 14), date(2026, 10, 14), periods_per_year=12)
    assert periods == 1


def test_n_periods_between_very_long_horizon():
    periods = n_periods_between(date(2026, 9, 14), date(2076, 9, 14), periods_per_year=12)
    assert periods == 600


def test_periodic_rate_from_annual_is_simple_division():
    assert periodic_rate_from_annual(0.12, 12) == pytest.approx(0.01)


# --- analyze_goal_funding (integration of the above) ---------------------


def test_analyze_goal_funding_already_achieved():
    goal = GoalInput(
        customer_id=1, goal_type="Emergency Buffer", target_amount=100_000,
        current_savings=200_000, target_date=date(2027, 9, 14),
    )
    assumptions = GoalAssumptions(contribution_amount=0, annual_return_rate=0.06, annual_inflation_rate=0.0)
    result = analyze_goal_funding(goal, assumptions, current_date=date(2026, 9, 14))
    assert result.already_achieved is True
    assert result.required_periodic_contribution <= 0


def test_analyze_goal_funding_zero_contribution_and_zero_return():
    goal = GoalInput(
        customer_id=1, goal_type="Car", target_amount=120_000,
        current_savings=120_000, target_date=date(2027, 9, 14),
    )
    assumptions = GoalAssumptions(contribution_amount=0, annual_return_rate=0.0, annual_inflation_rate=0.0)
    result = analyze_goal_funding(goal, assumptions, current_date=date(2026, 9, 14))
    assert result.already_achieved is True
    assert result.required_periodic_contribution == pytest.approx(0.0)


def test_analyze_goal_funding_reports_positive_contribution_gap_when_underfunded():
    goal = GoalInput(
        customer_id=1, goal_type="House Purchase", target_amount=5_000_000,
        current_savings=1_000_000, target_date=date(2031, 9, 14),
    )
    assumptions = GoalAssumptions(contribution_amount=10_000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    result = analyze_goal_funding(goal, assumptions, current_date=date(2026, 9, 14))
    assert result.contribution_gap > 0  # 10,000/mo is not enough
    assert result.inflation_adjusted_target_amount > result.nominal_target_amount
