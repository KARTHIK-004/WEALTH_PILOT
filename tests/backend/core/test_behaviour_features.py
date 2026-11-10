"""Phase B1 -- `core/behaviour_features.py`: pure, deterministic financial
behaviour features. No database, no clock."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wealthpilot.core.behaviour_features import (
    CONSISTENCY_WINDOW_MONTHS,
    FEATURE_SET_VERSION,
    MIN_CONSISTENCY_OBSERVATIONS,
    MonthlyObservation,
    compute_behaviour_features,
)

D = Decimal


def obs(month: int, year: int = 2026, **kw) -> MonthlyObservation:
    return MonthlyObservation(period=date(year, month, 1), **kw)


# --------------------------------------------------------------------- empty / sparse


def test_no_observations_everything_unavailable_with_reasons():
    f = compute_behaviour_features([])
    assert f.feature_set_version == FEATURE_SET_VERSION
    assert f.observation_count == 0 and f.latest_period is None
    for feature in (f.latest_ratios.expense_to_income, f.expenses_change.absolute_change,
                    f.savings_consistency.share_with_amount):
        assert feature.value is None and feature.unavailable_reason


def test_all_fields_omitted_in_a_month_gives_no_ratio_never_zero():
    f = compute_behaviour_features([obs(9)])
    for ratio in (f.latest_ratios.expense_to_income, f.latest_ratios.savings_to_income,
                  f.latest_ratios.investment_contribution_to_income):
        assert ratio.value is None
        assert "Income was not reported" in ratio.unavailable_reason


def test_partial_input_computes_only_what_is_known():
    f = compute_behaviour_features([obs(9, income=D("100000"), expenses=D("40000"))])
    assert f.latest_ratios.expense_to_income.value == pytest.approx(0.4)
    assert f.latest_ratios.savings_to_income.value is None
    assert "Savings was not reported" in f.latest_ratios.savings_to_income.unavailable_reason


# --------------------------------------------------------------------- zero vs missing


def test_explicit_zero_numerator_is_a_real_zero_ratio():
    f = compute_behaviour_features([obs(9, income=D("100000"), investment_contribution=D("0"))])
    assert f.latest_ratios.investment_contribution_to_income.value == 0.0
    assert f.latest_ratios.investment_contribution_to_income.unavailable_reason is None


def test_missing_numerator_is_not_zero():
    f = compute_behaviour_features([obs(9, income=D("100000"))])
    assert f.latest_ratios.investment_contribution_to_income.value is None


def test_zero_income_never_divides():
    f = compute_behaviour_features([obs(9, income=D("0"), expenses=D("1000"))])
    assert f.latest_ratios.expense_to_income.value is None
    assert "zero" in f.latest_ratios.expense_to_income.unavailable_reason


def test_missing_income_gives_no_ratio():
    f = compute_behaviour_features([obs(9, expenses=D("1000"))])
    assert f.latest_ratios.expense_to_income.value is None


# --------------------------------------------------------------------- units and currency


def test_ratio_uses_the_same_month_income_not_another_months():
    f = compute_behaviour_features([
        obs(8, income=D("50000"), expenses=D("10000")),
        obs(9, income=D("100000"), expenses=D("10000")),
    ])
    assert f.latest_ratios.expense_to_income.value == pytest.approx(0.1)  # not 0.2


def test_mixed_currencies_are_rejected_not_combined():
    with pytest.raises(ValueError, match="currencies"):
        compute_behaviour_features([obs(8, income=D("1"), currency="INR"), obs(9, income=D("1"), currency="EUR")])


# --------------------------------------------------------------------- malformed inputs


@pytest.mark.parametrize("bad", [D("-1"), D("NaN"), D("Infinity")])
def test_negative_nan_and_infinite_amounts_are_rejected(bad):
    with pytest.raises(ValueError):
        compute_behaviour_features([obs(9, income=bad)])


def test_float_amount_is_rejected_decimal_required():
    with pytest.raises(ValueError, match="Decimal"):
        compute_behaviour_features([obs(9, income=1000.0)])  # type: ignore[arg-type]


def test_duplicate_period_is_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        compute_behaviour_features([obs(9, income=D("1")), obs(9, income=D("2"))])


def test_period_must_be_first_of_month():
    with pytest.raises(ValueError, match="first day"):
        compute_behaviour_features([MonthlyObservation(period=date(2026, 9, 15), income=D("1"))])


def test_unknown_income_basis_is_rejected():
    with pytest.raises(ValueError, match="income_basis"):
        compute_behaviour_features([obs(9, income=D("1"), income_basis="after-tax")])


# --------------------------------------------------------------------- changes


def test_change_needs_the_immediately_previous_month():
    f = compute_behaviour_features([obs(7, expenses=D("1000")), obs(9, expenses=D("1500"))])  # August missing
    assert f.expenses_change.absolute_change.value is None
    assert "month before" in f.expenses_change.absolute_change.unavailable_reason


def test_single_observation_has_no_change_or_consistency():
    f = compute_behaviour_features([obs(9, income=D("100"), expenses=D("10"), savings=D("5"), investment_contribution=D("5"))])
    assert f.expenses_change.absolute_change.value is None
    assert f.savings_consistency.share_with_amount.value is None
    assert f.investment_contribution_consistency.known_months == 1


def test_consecutive_months_give_absolute_and_relative_change():
    f = compute_behaviour_features([obs(8, expenses=D("1000")), obs(9, expenses=D("1500"))])
    assert f.expenses_change.absolute_change.value == 500.0
    assert f.expenses_change.relative_change.value == pytest.approx(0.5)


def test_relative_change_undefined_from_zero_previous():
    f = compute_behaviour_features([obs(8, savings=D("0")), obs(9, savings=D("500"))])
    assert f.savings_change.absolute_change.value == 500.0
    assert f.savings_change.relative_change.value is None


def test_change_is_unavailable_if_either_month_did_not_report_the_amount():
    f = compute_behaviour_features([obs(8, income=D("1")), obs(9, savings=D("500"))])
    assert f.savings_change.absolute_change.value is None  # previous month never reported savings, not zero


# --------------------------------------------------------------------- consistency


def test_consistency_needs_enough_known_months():
    f = compute_behaviour_features([obs(m, investment_contribution=D("100")) for m in (8, 9)])
    assert MIN_CONSISTENCY_OBSERVATIONS == 3
    assert f.investment_contribution_consistency.share_with_amount.value is None


def test_consistency_is_share_of_known_months_with_an_amount_and_ignores_unreported_months():
    f = compute_behaviour_features([
        obs(5, investment_contribution=D("100")),
        obs(6, investment_contribution=D("0")),
        # July unreported -- not counted as zero activity
        obs(8, investment_contribution=D("200")),
        obs(9, investment_contribution=D("300")),
    ])
    c = f.investment_contribution_consistency
    assert c.known_months == 4 and c.window_months == CONSISTENCY_WINDOW_MONTHS
    assert c.share_with_amount.value == pytest.approx(0.75)  # 3 of 4 known months, not 3 of 5


def test_consistency_window_excludes_older_months():
    old = [obs(m, year=2024, savings=D("10")) for m in range(1, 7)]
    f = compute_behaviour_features(old + [obs(9, savings=D("1"))])
    assert f.savings_consistency.known_months == 1
    assert f.savings_consistency.share_with_amount.value is None


# --------------------------------------------------------------------- double counting / data quality


def test_outflows_exceeding_income_are_flagged_not_corrected():
    f = compute_behaviour_features([obs(9, income=D("100"), expenses=D("60"), savings=D("30"), investment_contribution=D("20"))])
    assert any("exceed income" in n for n in f.data_quality_notes)
    assert f.latest_ratios.savings_to_income.value == pytest.approx(0.3)  # values untouched


def test_outflows_within_income_raise_no_flag():
    f = compute_behaviour_features([obs(9, income=D("100"), expenses=D("50"), savings=D("30"), investment_contribution=D("20"))])
    assert f.data_quality_notes == []


def test_no_flag_when_an_outflow_is_unknown():
    f = compute_behaviour_features([obs(9, income=D("100"), expenses=D("90"), savings=D("30"))])
    assert f.data_quality_notes == []  # cannot conclude anything from a missing amount


def test_mixed_income_bases_are_noted():
    f = compute_behaviour_features([obs(8, income=D("1"), income_basis="net"), obs(9, income=D("1"), income_basis="gross")])
    assert any("net and gross" in n for n in f.data_quality_notes)


def test_unstated_basis_is_noted_when_others_state_it():
    f = compute_behaviour_features([obs(8, income=D("1"), income_basis="net"), obs(9, income=D("1"))])
    assert any("not stated" in n for n in f.data_quality_notes)


# --------------------------------------------------------------------- determinism


def test_result_is_independent_of_input_order():
    rows = [obs(7, expenses=D("1")), obs(8, expenses=D("2")), obs(9, expenses=D("3"))]
    assert compute_behaviour_features(rows) == compute_behaviour_features(list(reversed(rows)))
