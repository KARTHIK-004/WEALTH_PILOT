"""GoalInput / GoalAssumptions validation, invalid-input handling, and the
creation-vs-analysis date-boundary distinction."""

from datetime import date

import pytest
from pydantic import ValidationError

from wealthpilot.core.goals import GoalAssumptions, GoalInput, validate_goal_for_creation


def _goal(**overrides):
    defaults = dict(
        customer_id=1,
        goal_type="House Purchase",
        target_amount=5_000_000,
        current_savings=1_000_000,
        target_date=date(2031, 9, 14),
    )
    defaults.update(overrides)
    return GoalInput(**defaults)


def test_valid_goal_constructs_successfully():
    goal = _goal()
    assert goal.goal_type == "House Purchase"
    assert goal.priority == 1  # default


def test_target_amount_must_be_positive():
    with pytest.raises(ValidationError):
        _goal(target_amount=0)
    with pytest.raises(ValidationError):
        _goal(target_amount=-100)


def test_current_savings_must_be_non_negative():
    with pytest.raises(ValidationError):
        _goal(current_savings=-1)


def test_current_savings_of_zero_is_valid():
    goal = _goal(current_savings=0)
    assert goal.current_savings == 0


def test_blank_goal_type_is_rejected():
    with pytest.raises(ValidationError):
        _goal(goal_type="   ")


def test_goal_type_is_stripped_of_surrounding_whitespace():
    goal = _goal(goal_type="  Retirement  ")
    assert goal.goal_type == "Retirement"


def test_customer_id_must_be_positive():
    with pytest.raises(ValidationError):
        _goal(customer_id=0)
    with pytest.raises(ValidationError):
        _goal(customer_id=-5)


def test_priority_must_be_at_least_one():
    with pytest.raises(ValidationError):
        _goal(priority=0)


def test_invalid_date_type_is_rejected():
    with pytest.raises(ValidationError):
        GoalInput(
            customer_id=1,
            goal_type="Car",
            target_amount=1000,
            current_savings=0,
            target_date="not-a-date",
        )


def test_target_date_after_current_date_is_valid_for_creation():
    goal = _goal(target_date=date(2027, 1, 1))
    validate_goal_for_creation(goal, current_date=date(2026, 9, 14))  # must not raise


def test_target_date_equal_to_current_date_is_rejected_for_creation():
    goal = _goal(target_date=date(2026, 9, 14))
    with pytest.raises(ValueError, match="after current_date"):
        validate_goal_for_creation(goal, current_date=date(2026, 9, 14))


def test_target_date_in_the_past_is_rejected_for_creation():
    goal = _goal(target_date=date(2020, 1, 1))
    with pytest.raises(ValueError, match="after current_date"):
        validate_goal_for_creation(goal, current_date=date(2026, 9, 14))


def test_validate_goal_for_creation_defaults_current_date_to_today():
    goal = _goal(target_date=date(2099, 1, 1))
    validate_goal_for_creation(goal)  # must not raise, uses date.today() internally


# --- GoalAssumptions ---------------------------------------------------


def test_assumptions_require_explicit_return_and_inflation_rate():
    """Neither annual_return_rate nor annual_inflation_rate has a default —
    both must be supplied explicitly (never invented by the engine)."""
    with pytest.raises(ValidationError):
        GoalAssumptions(contribution_amount=1000, annual_return_rate=0.08)  # missing inflation
    with pytest.raises(ValidationError):
        GoalAssumptions(contribution_amount=1000, annual_inflation_rate=0.06)  # missing return


def test_assumptions_accept_explicit_zero_return_and_inflation():
    a = GoalAssumptions(contribution_amount=1000, annual_return_rate=0.0, annual_inflation_rate=0.0)
    assert a.annual_return_rate == 0.0
    assert a.annual_inflation_rate == 0.0


def test_assumptions_reject_return_at_or_below_negative_one():
    with pytest.raises(ValidationError):
        GoalAssumptions(contribution_amount=1000, annual_return_rate=-1.0, annual_inflation_rate=0.0)
    with pytest.raises(ValidationError):
        GoalAssumptions(contribution_amount=1000, annual_return_rate=-1.5, annual_inflation_rate=0.0)


def test_assumptions_allow_negative_return_above_negative_one():
    a = GoalAssumptions(contribution_amount=1000, annual_return_rate=-0.10, annual_inflation_rate=0.0)
    assert a.annual_return_rate == -0.10


def test_contribution_periods_per_year_defaults_to_monthly():
    a = GoalAssumptions(contribution_amount=1000, annual_return_rate=0.08, annual_inflation_rate=0.06)
    assert a.contribution_periods_per_year == 12


def test_contribution_periods_per_year_must_be_positive():
    with pytest.raises(ValidationError):
        GoalAssumptions(
            contribution_amount=1000,
            contribution_periods_per_year=0,
            annual_return_rate=0.08,
            annual_inflation_rate=0.06,
        )


def test_contribution_amount_must_be_non_negative():
    with pytest.raises(ValidationError):
        GoalAssumptions(contribution_amount=-1, annual_return_rate=0.08, annual_inflation_rate=0.06)
