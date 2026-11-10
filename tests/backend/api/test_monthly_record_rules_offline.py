"""The monthly-record rules the Financial Behaviour page relies on, checked WITHOUT a database (the DB-backed route tests in `test_monthly_records.py` need the hosted test database and are not run
here): the request model refuses negative, non-finite and over-precise amounts and unknown fields; the period parser accepts only a past-or-current calendar month; and the table itself declares the
uniqueness and non-negativity that prevent a duplicate month and an impossible amount. Nothing here reads or writes any data."""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint

from wealthpilot.api.errors import InvalidRequestError
from wealthpilot.api.schemas import MonthlyRecordUpdate
from wealthpilot.api.services.monthly_records_service import parse_period
from wealthpilot.db.models import MonthlyFinancialRecord


@pytest.mark.parametrize("field", ["income", "expenses", "savings", "investment_contribution"])
def test_a_negative_amount_is_refused(field):
    with pytest.raises(ValidationError):
        MonthlyRecordUpdate(**{field: -1})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "ten", True, [1], {"a": 1}])
def test_a_non_number_or_non_finite_amount_is_refused(value):
    with pytest.raises(ValidationError):
        MonthlyRecordUpdate(income=value)


def test_more_than_two_decimal_places_and_an_unknown_field_are_refused():
    with pytest.raises(ValidationError):
        MonthlyRecordUpdate(income=100.123)
    with pytest.raises(ValidationError):
        MonthlyRecordUpdate(income=100, favourite_colour="blue")
    with pytest.raises(ValidationError):
        MonthlyRecordUpdate(income=100, income_basis="estimated")


def test_zero_two_decimals_and_a_missing_field_are_accepted_and_missing_stays_none():
    record = MonthlyRecordUpdate(income=0, expenses=1234.56)
    assert record.income == 0 and record.expenses == 1234.56 and record.savings is None and record.investment_contribution is None


@pytest.mark.parametrize("bad", ["", "2026", "2026-13", "2026-00", "26-05", "2026-5", "May 2026", "2026-05-01", " 2026-05", "2026/05"])
def test_a_period_must_be_a_calendar_month_written_yyyy_mm(bad):
    with pytest.raises(InvalidRequestError):
        parse_period(bad, today=date(2026, 11, 2))


def test_a_future_month_and_an_implausibly_old_month_are_refused_and_the_current_month_is_accepted():
    today = date(2026, 11, 2)
    assert parse_period("2026-11", today=today) == date(2026, 11, 1)
    assert parse_period("2026-03", today=today) == date(2026, 3, 1)
    with pytest.raises(InvalidRequestError):
        parse_period("2026-12", today=today)
    with pytest.raises(InvalidRequestError):
        parse_period("1999-12", today=today)


def test_the_table_prevents_a_duplicate_month_and_an_impossible_amount():
    args = MonthlyFinancialRecord.__table_args__
    unique = {c.name: [col.name for col in c.columns] for c in args if isinstance(c, UniqueConstraint)}
    checks = {c.name for c in args if isinstance(c, CheckConstraint)}
    assert unique["uq_monthly_records_customer_period"] == ["customer_id", "period_month"]               # a month is stored once per customer
    assert {"ck_monthly_records_period_first_of_month", "ck_monthly_records_income_non_negative", "ck_monthly_records_expenses_non_negative", "ck_monthly_records_savings_non_negative"} <= checks
