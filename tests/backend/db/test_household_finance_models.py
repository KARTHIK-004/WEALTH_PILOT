"""Phase 33 -- the database itself enforces the household financial-data rules.

Every rule the API also checks is asserted here against real PostgreSQL
(TEST_DATABASE_URL, rolled back after each test), so no code path can store an
invalid financial record. Expected violations are provoked inside a SAVEPOINT
(`begin_nested`) so the failed write does not discard the test's own setup rows
-- the same technique `test_household_models.py` uses.

These tables hold SOURCE DATA only: the tests also assert their exact column
sets, so no aggregate/derived column (total, net worth, ratio, score) can be
added here without failing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import get_args

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from wealthpilot.api.schemas import (
    HouseholdAssetType,
    HouseholdExpenseCategory,
    HouseholdFinanceFrequency,
    HouseholdLiabilityType,
)
from wealthpilot.db.models import (
    HOUSEHOLD_ASSET_TYPES,
    HOUSEHOLD_EXPENSE_CATEGORIES,
    HOUSEHOLD_FINANCE_FREQUENCIES,
    HOUSEHOLD_LIABILITY_TYPES,
    Customer,
    Household,
    HouseholdAsset,
    HouseholdExpense,
    HouseholdIncome,
    HouseholdLiability,
    HouseholdMember,
)

FINANCE_TABLES = ("household_incomes", "household_expenses", "household_assets", "household_liabilities")


def _household(db_session, name="Finance Test Household") -> Household:
    household = Household(name=name)
    db_session.add(household)
    db_session.flush()
    customer = Customer(name=f"{name} primary", data_source="user-entered")
    db_session.add(customer)
    db_session.flush()
    db_session.add(
        HouseholdMember(
            household_id=household.id, customer_id=customer.id,
            relationship_type="self", role="primary", is_dependent=False,
        )
    )
    db_session.flush()
    return household


def _violation(db_session, row) -> None:
    """Asserts the database rejects `row`, without poisoning the session."""
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(row)


def _income(household, **overrides) -> HouseholdIncome:
    values = dict(household_id=household.id, source="Salary", amount=Decimal("5000.00"), frequency="monthly", is_active=True)
    values.update(overrides)
    return HouseholdIncome(**values)


def _expense(household, **overrides) -> HouseholdExpense:
    values = dict(household_id=household.id, category="housing", description="Rent", amount=Decimal("1200.00"),
                  frequency="monthly", is_essential=True, is_active=True)
    values.update(overrides)
    return HouseholdExpense(**values)


def _asset(household, **overrides) -> HouseholdAsset:
    values = dict(household_id=household.id, name="Savings account", asset_type="bank_account",
                  current_value=Decimal("15000.00"), is_liquid=True)
    values.update(overrides)
    return HouseholdAsset(**values)


def _liability(household, **overrides) -> HouseholdLiability:
    values = dict(household_id=household.id, name="Home loan", liability_type="mortgage",
                  outstanding_amount=Decimal("150000.00"), monthly_payment=Decimal("900.00"))
    values.update(overrides)
    return HouseholdLiability(**values)


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------


def test_all_four_tables_exist(db_session):
    tables = set(inspect(db_session.connection()).get_table_names())
    assert set(FINANCE_TABLES) <= tables


def test_tables_have_exactly_the_intended_columns_and_no_derived_column(db_session):
    """Source data only: no total, sum, net worth, ratio or score column."""
    inspector = inspect(db_session.connection())
    # Phase 35 (migration a7c41e9b6f30) added only optional FACTUAL metadata --
    # `notes` everywhere, `description` on assets/liabilities, `interest_rate`
    # on liabilities. Still no derived column, and still no `customer_id`.
    expected = {
        "household_incomes": {"id", "household_id", "source", "amount", "frequency", "is_active", "notes", "created_at", "updated_at"},
        "household_expenses": {"id", "household_id", "category", "description", "amount", "frequency", "is_essential", "is_active", "notes", "created_at", "updated_at"},
        "household_assets": {"id", "household_id", "name", "asset_type", "current_value", "is_liquid", "description", "notes", "created_at", "updated_at"},
        "household_liabilities": {"id", "household_id", "name", "liability_type", "outstanding_amount", "monthly_payment", "interest_rate", "description", "notes", "created_at", "updated_at"},
    }
    forbidden = ("total", "sum", "net_worth", "ratio", "score", "savings", "cash_flow", "aggregate", "emergency")
    for table, columns in expected.items():
        actual = {c["name"] for c in inspector.get_columns(table)}
        assert actual == columns, table
        assert not any(word in name for name in actual for word in forbidden), table


def test_money_columns_use_the_projects_numeric_convention(db_session):
    """Numeric(14, 2), the same as `financial_inputs`/`financial_goals` -- never float."""
    inspector = inspect(db_session.connection())
    money = {
        "household_incomes": ["amount"],
        "household_expenses": ["amount"],
        "household_assets": ["current_value"],
        "household_liabilities": ["outstanding_amount", "monthly_payment"],
    }
    for table, columns in money.items():
        by_name = {c["name"]: c for c in inspector.get_columns(table)}
        for column in columns:
            type_ = by_name[column]["type"]
            assert type_.__class__.__name__ == "NUMERIC", (table, column, type_)
            assert (type_.precision, type_.scale) == (14, 2), (table, column)


def test_nullability_matches_the_contract(db_session):
    """Exactly these columns are optional -- an absent optional value stays NULL,
    never 0 or an empty string. Phase 33 made `description` (expenses) and
    `monthly_payment` optional; every Phase 35 metadata column is optional too,
    so no existing row needed a backfill. Every financial FACT stays required."""
    inspector = inspect(db_session.connection())
    nullable = {
        (c["name"], t) for t in FINANCE_TABLES for c in inspector.get_columns(t) if c["nullable"]
    }
    assert nullable == {
        # Phase 33
        ("description", "household_expenses"),
        ("monthly_payment", "household_liabilities"),
        # Phase 35
        ("notes", "household_incomes"),
        ("notes", "household_expenses"),
        ("description", "household_assets"),
        ("notes", "household_assets"),
        ("interest_rate", "household_liabilities"),
        ("description", "household_liabilities"),
        ("notes", "household_liabilities"),
    }


def test_is_active_defaults_to_true_at_the_database_level(db_session):
    household = _household(db_session)
    db_session.execute(text(
        "INSERT INTO household_incomes (household_id, source, amount, frequency) VALUES (:h, 'Salary', 100, 'monthly')"
    ), {"h": household.id})
    db_session.execute(text(
        "INSERT INTO household_expenses (household_id, category, amount, frequency, is_essential)"
        " VALUES (:h, 'food', 50, 'monthly', true)"
    ), {"h": household.id})
    assert db_session.scalar(text("SELECT is_active FROM household_incomes WHERE household_id = :h"), {"h": household.id}) is True
    assert db_session.scalar(text("SELECT is_active FROM household_expenses WHERE household_id = :h"), {"h": household.id}) is True


def test_every_table_indexes_and_foreign_keys_its_household(db_session):
    inspector = inspect(db_session.connection())
    for table in FINANCE_TABLES:
        fks = inspector.get_foreign_keys(table)
        assert [(f["constrained_columns"], f["referred_table"], f["options"].get("ondelete")) for f in fks] == [
            (["household_id"], "households", "CASCADE")
        ], table
        assert any(i["column_names"] == ["household_id"] for i in inspector.get_indexes(table)), table


# ---------------------------------------------------------------------------
# Round trip and ownership
# ---------------------------------------------------------------------------


def test_all_four_records_round_trip(db_session):
    household = _household(db_session)
    db_session.add_all([_income(household), _expense(household), _asset(household), _liability(household)])
    db_session.flush()

    income = db_session.scalar(select(HouseholdIncome).where(HouseholdIncome.household_id == household.id))
    assert (income.source, income.amount, income.frequency, income.is_active) == ("Salary", Decimal("5000.00"), "monthly", True)
    assert income.created_at is not None and income.updated_at is not None
    expense = db_session.scalar(select(HouseholdExpense).where(HouseholdExpense.household_id == household.id))
    assert (expense.category, expense.description, expense.is_essential) == ("housing", "Rent", True)
    asset = db_session.scalar(select(HouseholdAsset).where(HouseholdAsset.household_id == household.id))
    assert (asset.name, asset.asset_type, asset.current_value, asset.is_liquid) == ("Savings account", "bank_account", Decimal("15000.00"), True)
    liability = db_session.scalar(select(HouseholdLiability).where(HouseholdLiability.household_id == household.id))
    assert (liability.liability_type, liability.outstanding_amount, liability.monthly_payment) == ("mortgage", Decimal("150000.00"), Decimal("900.00"))


def test_a_record_requires_an_existing_household(db_session):
    class Fake:
        id = 999_999_999
    _violation(db_session, _income(Fake()))
    _violation(db_session, _expense(Fake()))
    _violation(db_session, _asset(Fake()))
    _violation(db_session, _liability(Fake()))


def test_deleting_a_household_cascades_its_financial_records(db_session):
    """Integrity only -- Phase 32/33 expose no household deletion API."""
    household = _household(db_session)
    db_session.add_all([_income(household), _expense(household), _asset(household), _liability(household)])
    db_session.flush()

    db_session.execute(text("DELETE FROM households WHERE id = :id"), {"id": household.id})
    for table in FINANCE_TABLES:
        assert db_session.scalar(text(f"SELECT count(*) FROM {table} WHERE household_id = :h"), {"h": household.id}) == 0


def test_records_of_two_households_stay_separate(db_session):
    a, b = _household(db_session, "A"), _household(db_session, "B")
    db_session.add_all([_income(a, source="A salary"), _income(b, source="B salary")])
    db_session.flush()
    rows = db_session.scalars(select(HouseholdIncome).where(HouseholdIncome.household_id == a.id)).all()
    assert [r.source for r in rows] == ["A salary"]


# ---------------------------------------------------------------------------
# Value constraints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-0.01"), Decimal("-100")])
def test_income_amount_must_be_strictly_positive(db_session, amount):
    _violation(db_session, _income(_household(db_session), amount=amount))


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-0.01")])
def test_expense_amount_must_be_strictly_positive(db_session, amount):
    _violation(db_session, _expense(_household(db_session), amount=amount))


def test_asset_value_may_be_zero_but_never_negative(db_session):
    household = _household(db_session)
    db_session.add(_asset(household, current_value=Decimal("0")))
    db_session.flush()  # a stated zero is valid
    _violation(db_session, _asset(household, name="Negative", current_value=Decimal("-1")))


def test_liability_amounts_may_be_zero_but_never_negative(db_session):
    household = _household(db_session)
    db_session.add(_liability(household, outstanding_amount=Decimal("0"), monthly_payment=Decimal("0")))
    db_session.flush()
    _violation(db_session, _liability(household, name="Neg outstanding", outstanding_amount=Decimal("-1")))
    _violation(db_session, _liability(household, name="Neg payment", monthly_payment=Decimal("-1")))


def test_liability_monthly_payment_may_be_null_which_is_not_zero(db_session):
    household = _household(db_session)
    db_session.add(_liability(household, monthly_payment=None))
    db_session.flush()
    row = db_session.scalar(select(HouseholdLiability).where(HouseholdLiability.household_id == household.id))
    assert row.monthly_payment is None  # "not provided", distinct from Decimal("0")


def test_blank_free_text_identifiers_are_rejected(db_session):
    household = _household(db_session)
    _violation(db_session, _income(household, source="   "))
    _violation(db_session, _asset(household, name=""))
    _violation(db_session, _liability(household, name="  "))


@pytest.mark.parametrize("frequency", ["weekly", "Monthly", "", "daily"])
def test_unsupported_frequency_is_rejected(db_session, frequency):
    household = _household(db_session)
    _violation(db_session, _income(household, frequency=frequency))
    _violation(db_session, _expense(household, frequency=frequency))


@pytest.mark.parametrize("category", ["groceries", "Housing", "", "travel"])
def test_unsupported_expense_category_is_rejected(db_session, category):
    _violation(db_session, _expense(_household(db_session), category=category))


@pytest.mark.parametrize("asset_type", ["crypto", "Cash", "", "art"])
def test_unsupported_asset_type_is_rejected(db_session, asset_type):
    _violation(db_session, _asset(_household(db_session), asset_type=asset_type))


@pytest.mark.parametrize("liability_type", ["payday_loan", "Mortgage", "", "overdraft"])
def test_unsupported_liability_type_is_rejected(db_session, liability_type):
    _violation(db_session, _liability(_household(db_session), liability_type=liability_type))


def test_every_vocabulary_value_is_actually_accepted(db_session):
    """The controlled lists are usable end to end, not just restrictive."""
    household = _household(db_session)
    for frequency in HOUSEHOLD_FINANCE_FREQUENCIES:
        db_session.add(_income(household, source=f"src-{frequency}", frequency=frequency))
    for category in HOUSEHOLD_EXPENSE_CATEGORIES:
        db_session.add(_expense(household, category=category))
    for asset_type in HOUSEHOLD_ASSET_TYPES:
        db_session.add(_asset(household, asset_type=asset_type))
    for liability_type in HOUSEHOLD_LIABILITY_TYPES:
        db_session.add(_liability(household, liability_type=liability_type))
    db_session.flush()
    assert db_session.scalar(text("SELECT count(*) FROM household_expenses WHERE household_id = :h"), {"h": household.id}) == len(HOUSEHOLD_EXPENSE_CATEGORIES)


def test_python_vocabularies_match_the_api_literals_and_the_check_constraints(db_session):
    assert set(HOUSEHOLD_FINANCE_FREQUENCIES) == set(get_args(HouseholdFinanceFrequency))
    assert set(HOUSEHOLD_EXPENSE_CATEGORIES) == set(get_args(HouseholdExpenseCategory))
    assert set(HOUSEHOLD_ASSET_TYPES) == set(get_args(HouseholdAssetType))
    assert set(HOUSEHOLD_LIABILITY_TYPES) == set(get_args(HouseholdLiabilityType))

    inspector = inspect(db_session.connection())
    checks = {t: {c["name"]: c["sqltext"] for c in inspector.get_check_constraints(t)} for t in FINANCE_TABLES}
    for value in HOUSEHOLD_FINANCE_FREQUENCIES:
        assert f"'{value}'" in checks["household_incomes"]["ck_household_incomes_frequency"]
    for value in HOUSEHOLD_EXPENSE_CATEGORIES:
        assert f"'{value}'" in checks["household_expenses"]["ck_household_expenses_category"]
    for value in HOUSEHOLD_ASSET_TYPES:
        assert f"'{value}'" in checks["household_assets"]["ck_household_assets_type"]
    for value in HOUSEHOLD_LIABILITY_TYPES:
        assert f"'{value}'" in checks["household_liabilities"]["ck_household_liabilities_type"]


# ---------------------------------------------------------------------------
# Nothing else changed
# ---------------------------------------------------------------------------


def test_phase_32_and_existing_tables_are_unchanged(db_session):
    """Phase 33 adds tables; it does not touch any existing one."""
    inspector = inspect(db_session.connection())
    assert {c["name"] for c in inspector.get_columns("households")} == {"id", "name", "created_at", "updated_at"}
    assert {c["name"] for c in inspector.get_columns("household_members")} == {
        "id", "household_id", "customer_id", "relationship", "role", "is_dependent", "created_at", "updated_at",
    }
    assert {c["name"] for c in inspector.get_columns("customers")} == {
        "id", "name", "age", "income", "employment_status", "customer_type", "investment_capacity",
        "risk_inputs", "data_source", "created_at",
    }
    assert {c["name"] for c in inspector.get_columns("financial_inputs")} == {
        "id", "customer_id", "monthly_essential_expenses", "current_liquid_assets", "contribution_amount",
        "annual_return_rate", "annual_inflation_rate", "contribution_periods_per_year", "created_at", "updated_at",
    }


def test_household_financial_records_are_not_linked_to_a_customer(db_session):
    """Ownership runs household -> membership -> customer, never straight to a
    customer: no financial table may have a customer_id column."""
    inspector = inspect(db_session.connection())
    for table in FINANCE_TABLES:
        assert "customer_id" not in {c["name"] for c in inspector.get_columns(table)}, table
