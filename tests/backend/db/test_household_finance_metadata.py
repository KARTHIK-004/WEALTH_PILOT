"""Phase 35 — the optional factual metadata columns on the household financial
tables, checked against real PostgreSQL (TEST_DATABASE_URL, rolled back).

Migration `a7c41e9b6f30` added `notes` (all four tables), `description` (assets,
liabilities) and `interest_rate` (liabilities). Every one is optional and none
is read by any calculation. These tests prove the database stores them as
facts, keeps an absent value NULL rather than 0 or "", and that the Phase 33
constraints they sit beside were not weakened (ADR-032, ADR-034).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from wealthpilot.db.models import (
    Customer,
    Household,
    HouseholdAsset,
    HouseholdExpense,
    HouseholdIncome,
    HouseholdLiability,
    HouseholdMember,
)


def _household(db_session, name="Metadata Household") -> Household:
    household = Household(name=name)
    db_session.add(household)
    db_session.flush()
    customer = Customer(name=f"{name} primary", data_source="user-entered")
    db_session.add(customer)
    db_session.flush()
    db_session.add(HouseholdMember(household_id=household.id, customer_id=customer.id,
                                   relationship_type="self", role="primary", is_dependent=False))
    db_session.flush()
    return household


def _violation(db_session, row) -> None:
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(row)


def _liability(household, **overrides) -> HouseholdLiability:
    values = dict(household_id=household.id, name="Home loan", liability_type="mortgage",
                  outstanding_amount=Decimal("150000.00"), monthly_payment=Decimal("900.00"))
    values.update(overrides)
    return HouseholdLiability(**values)


# ------------------------------------------------------------------ schema


def test_the_database_is_fully_migrated_past_phase_35(db_session):
    """The test database is at the script head, and that head descends from the
    Phase 35 revision. (Pinning the exact head here would go stale the moment a
    later phase adds a migration -- `test_migration_history.py` pins it once.)"""
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parents[3] / "backend"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    db_head = db_session.execute(text("select version_num from alembic_version")).scalar()
    assert [db_head] == scripts.get_heads()
    assert "a7c41e9b6f30" in {rev.revision for rev in scripts.iterate_revisions(db_head, "base")}


def test_metadata_columns_have_the_intended_types(db_session):
    inspector = inspect(db_session.connection())
    types = {
        (table, c["name"]): c["type"]
        for table in ("household_incomes", "household_expenses", "household_assets", "household_liabilities")
        for c in inspector.get_columns(table)
    }
    for table in ("household_incomes", "household_expenses", "household_assets", "household_liabilities"):
        assert types[(table, "notes")].length == 500, table
    for table in ("household_assets", "household_liabilities"):
        assert types[(table, "description")].length == 200, table
    rate = types[("household_liabilities", "interest_rate")]
    assert rate.__class__.__name__ == "NUMERIC"
    assert (rate.precision, rate.scale) == (6, 4)  # the project's existing rate convention


def test_interest_rate_has_a_non_negative_check(db_session):
    checks = {c["name"] for c in inspect(db_session.connection()).get_check_constraints("household_liabilities")}
    assert "ck_household_liabilities_interest_non_negative" in checks


# --------------------------------------------------------------- behaviour


def test_metadata_round_trips_exactly(db_session):
    household = _household(db_session)
    rows = [
        HouseholdIncome(household_id=household.id, source="Salary", amount=Decimal("5000.00"),
                        frequency="monthly", notes="Paid on the 25th"),
        HouseholdExpense(household_id=household.id, category="housing", amount=Decimal("1200.00"),
                         frequency="monthly", is_essential=True, notes="Includes service charge"),
        HouseholdAsset(household_id=household.id, name="Savings", asset_type="bank_account",
                       current_value=Decimal("15000.00"), is_liquid=True,
                       description="Joint instant-access account", notes="Opened 2019"),
        _liability(household, interest_rate=Decimal("0.0425"), description="Fixed until 2028",
                   notes="Remortgage due"),
    ]
    db_session.add_all(rows)
    db_session.flush()
    for row in rows:
        db_session.expire(row)
    assert rows[0].notes == "Paid on the 25th"
    assert rows[1].notes == "Includes service charge"
    assert (rows[2].description, rows[2].notes) == ("Joint instant-access account", "Opened 2019")
    assert rows[3].interest_rate == Decimal("0.0425")
    assert (rows[3].description, rows[3].notes) == ("Fixed until 2028", "Remortgage due")


def test_absent_metadata_stays_null_never_zero_or_empty(db_session):
    household = _household(db_session)
    liability = _liability(household)
    asset = HouseholdAsset(household_id=household.id, name="Cash", asset_type="cash",
                           current_value=Decimal("100.00"), is_liquid=True)
    db_session.add_all([liability, asset])
    db_session.flush()
    raw = db_session.execute(
        text("select interest_rate, description, notes from household_liabilities where id = :id"),
        {"id": liability.id},
    ).one()
    assert raw == (None, None, None)
    raw = db_session.execute(
        text("select description, notes from household_assets where id = :id"), {"id": asset.id}
    ).one()
    assert raw == (None, None)


def test_a_zero_interest_rate_is_a_known_zero(db_session):
    """An interest-free loan is a fact, distinct from "rate not recorded"."""
    household = _household(db_session)
    liability = _liability(household, interest_rate=Decimal("0"))
    db_session.add(liability)
    db_session.flush()
    db_session.expire(liability)
    assert liability.interest_rate == Decimal("0")


def test_a_negative_interest_rate_is_rejected_by_the_database(db_session):
    _violation(db_session, _liability(_household(db_session), interest_rate=Decimal("-0.0100")))


# ------------------------------------------------ existing rules unchanged


def test_the_phase_33_amount_rule_is_not_weakened(db_session):
    """ADR-032 kept `amount > 0`; Phase 35 did not relax it to `>= 0`."""
    household = _household(db_session)
    _violation(db_session, HouseholdIncome(household_id=household.id, source="Zero", amount=Decimal("0"),
                                           frequency="monthly"))
    _violation(db_session, HouseholdExpense(household_id=household.id, category="food", amount=Decimal("0"),
                                            frequency="monthly", is_essential=True))


def test_monthly_payment_is_still_optional(db_session):
    """ADR-032 kept `monthly_payment` nullable; Phase 35 did not make it required."""
    household = _household(db_session)
    liability = _liability(household, monthly_payment=None)
    db_session.add(liability)
    db_session.flush()
    db_session.expire(liability)
    assert liability.monthly_payment is None


def test_existing_rows_are_preserved_with_null_metadata(db_session):
    """A row written without the Phase 35 columns -- as every pre-Phase-35 row
    was -- reads back with NULL metadata and its facts intact."""
    household = _household(db_session)
    db_session.execute(
        text("insert into household_incomes (household_id, source, amount, frequency) "
             "values (:h, 'Legacy salary', 3000.00, 'monthly')"),
        {"h": household.id},
    )
    row = db_session.scalars(select(HouseholdIncome).where(HouseholdIncome.household_id == household.id)).one()
    assert (row.source, row.amount, row.frequency, row.is_active, row.notes) == (
        "Legacy salary", Decimal("3000.00"), "monthly", True, None
    )


def test_metadata_is_deleted_with_its_household(db_session):
    """Integrity only -- there is no household deletion API. The database's own
    `ON DELETE CASCADE` is what is under test, so the household is deleted with
    raw SQL, exactly as Phase 33's cascade test does (an ORM `session.delete`
    would instead try to null out `household_members.household_id` first)."""
    household = _household(db_session)
    db_session.add(_liability(household, notes="to be cascaded", interest_rate=Decimal("0.05")))
    db_session.flush()
    db_session.execute(text("DELETE FROM households WHERE id = :id"), {"id": household.id})
    remaining = db_session.execute(
        text("select count(*) from household_liabilities where household_id = :h"), {"h": household.id}
    ).scalar()
    assert remaining == 0
