"""Emergency-fund calculation, shortfall, and the savings-first rule
(target: 6 months of essential expenses, approved 2026-09-14)."""

import pytest

from wealthpilot.core.goals import (
    EMERGENCY_FUND_TARGET_MONTHS,
    assess_emergency_fund,
    savings_first_required,
)


def test_default_target_is_six_months():
    assert EMERGENCY_FUND_TARGET_MONTHS == 6


def test_required_amount_is_expenses_times_target_months():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=0)
    assert status.required_amount == pytest.approx(180_000)
    assert status.target_months == 6


def test_insufficient_fund_reports_shortfall_and_flag():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=90_000)
    assert status.required_amount == pytest.approx(180_000)
    assert status.shortfall == pytest.approx(90_000)
    assert status.surplus == pytest.approx(0.0)
    assert status.sufficient is False


def test_sufficient_fund_reports_surplus_and_flag():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=250_000)
    assert status.required_amount == pytest.approx(180_000)
    assert status.shortfall == pytest.approx(0.0)
    assert status.surplus == pytest.approx(70_000)
    assert status.sufficient is True


def test_exactly_at_target_is_sufficient():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=180_000)
    assert status.sufficient is True
    assert status.shortfall == pytest.approx(0.0)


def test_zero_essential_expenses_requires_zero_fund():
    status = assess_emergency_fund(monthly_essential_expenses=0, current_liquid_assets=0)
    assert status.required_amount == 0.0
    assert status.sufficient is True


def test_custom_target_months_is_respected():
    status = assess_emergency_fund(monthly_essential_expenses=20_000, current_liquid_assets=0, target_months=3)
    assert status.required_amount == pytest.approx(60_000)
    assert status.target_months == 3


def test_rejects_negative_expenses():
    with pytest.raises(ValueError):
        assess_emergency_fund(monthly_essential_expenses=-1, current_liquid_assets=0)


def test_rejects_negative_liquid_assets():
    with pytest.raises(ValueError):
        assess_emergency_fund(monthly_essential_expenses=1000, current_liquid_assets=-1)


def test_rejects_non_positive_target_months():
    with pytest.raises(ValueError):
        assess_emergency_fund(monthly_essential_expenses=1000, current_liquid_assets=0, target_months=0)


# --- savings-first --------------------------------------------------------


def test_savings_first_is_true_when_insufficient():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=0)
    assert savings_first_required(status) is True


def test_savings_first_is_false_when_sufficient():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=200_000)
    assert savings_first_required(status) is False


def test_savings_first_is_false_exactly_at_target():
    status = assess_emergency_fund(monthly_essential_expenses=30_000, current_liquid_assets=180_000)
    assert savings_first_required(status) is False
