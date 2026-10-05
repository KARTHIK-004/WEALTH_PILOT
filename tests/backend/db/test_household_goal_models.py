"""Phase 36 — the `household_goals` table, checked against real PostgreSQL
(TEST_DATABASE_URL, rolled back after each test).

Proves the database itself enforces the goal contract: stored facts only, no
derived column, no `customer_id`, `target_amount > 0`, an optional
`current_savings` that stays NULL rather than 0, the controlled goal-type
vocabulary, and a cascading, indexed `household_id` — and that the individual
`financial_goals` table is untouched (ADR-035).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import get_args

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from wealthpilot.api.schemas import HouseholdGoalType
from wealthpilot.db.models import HOUSEHOLD_GOAL_TYPES, Customer, Household, HouseholdGoal, HouseholdMember


def _household(db_session, name="Goal Household") -> Household:
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


def _goal(household, **overrides) -> HouseholdGoal:
    values = dict(household_id=household.id, name="New home", goal_type="house",
                  target_amount=Decimal("60000.00"), target_date=date(2030, 6, 30))
    values.update(overrides)
    return HouseholdGoal(**values)


def _violation(db_session, row) -> None:
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(row)


# ------------------------------------------------------------------- schema


def test_the_table_exists(db_session):
    assert "household_goals" in inspect(db_session.connection()).get_table_names()


def test_the_table_has_exactly_the_intended_columns_and_no_derived_column(db_session):
    """Facts only: no inflation-adjusted target, required contribution, gap,
    probability, feasibility or emergency-fund requirement -- and no
    `customer_id`, because a goal belongs to the household."""
    actual = {c["name"] for c in inspect(db_session.connection()).get_columns("household_goals")}
    assert actual == {"id", "household_id", "name", "goal_type", "target_amount", "current_savings",
                      "target_date", "notes", "is_active", "created_at", "updated_at"}
    forbidden = ("inflation", "adjusted", "required", "contribution", "gap", "probability", "feasib",
                 "priority", "score", "rank", "customer_id", "status")
    assert not [c for c in actual if any(word in c for word in forbidden)]


def test_nullability_matches_the_contract(db_session):
    nullable = {c["name"] for c in inspect(db_session.connection()).get_columns("household_goals") if c["nullable"]}
    assert nullable == {"current_savings", "notes"}


def test_money_uses_the_projects_numeric_convention(db_session):
    by_name = {c["name"]: c["type"] for c in inspect(db_session.connection()).get_columns("household_goals")}
    for column in ("target_amount", "current_savings"):
        assert by_name[column].__class__.__name__ == "NUMERIC"
        assert (by_name[column].precision, by_name[column].scale) == (14, 2)
    assert by_name["target_date"].__class__.__name__ == "DATE"


def test_household_id_is_indexed_and_cascades(db_session):
    inspector = inspect(db_session.connection())
    fks = inspector.get_foreign_keys("household_goals")
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "households" and fks[0]["constrained_columns"] == ["household_id"]
    assert fks[0]["options"].get("ondelete") == "CASCADE"
    assert any(ix["column_names"] == ["household_id"] for ix in inspector.get_indexes("household_goals"))


def test_is_active_defaults_to_true_at_the_database_level(db_session):
    household = _household(db_session)
    db_session.execute(
        text("insert into household_goals (household_id, name, goal_type, target_amount, target_date) "
             "values (:h, 'Raw', 'other', 100, '2031-01-01')"),
        {"h": household.id},
    )
    assert db_session.execute(text("select is_active from household_goals where household_id = :h"),
                              {"h": household.id}).scalar() is True


# ------------------------------------------------------------ vocabulary


def test_python_literal_and_check_constraint_vocabularies_agree(db_session):
    assert set(HOUSEHOLD_GOAL_TYPES) == set(get_args(HouseholdGoalType))
    check = next(c for c in inspect(db_session.connection()).get_check_constraints("household_goals")
                 if c["name"] == "ck_household_goals_goal_type")
    for goal_type in HOUSEHOLD_GOAL_TYPES:
        assert f"'{goal_type}'" in check["sqltext"]


@pytest.mark.parametrize("goal_type", HOUSEHOLD_GOAL_TYPES)
def test_every_goal_type_is_accepted(db_session, goal_type):
    household = _household(db_session)
    db_session.add(_goal(household, goal_type=goal_type))
    db_session.flush()


@pytest.mark.parametrize("goal_type", ["", "House", "vacation", "emergency", "retirement "])
def test_an_unknown_goal_type_is_rejected(db_session, goal_type):
    _violation(db_session, _goal(_household(db_session), goal_type=goal_type))


# -------------------------------------------------------------- values


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1.00")])
def test_target_amount_must_be_strictly_positive(db_session, amount):
    _violation(db_session, _goal(_household(db_session), target_amount=amount))


def test_current_savings_may_be_a_recorded_zero(db_session):
    household = _household(db_session)
    goal = _goal(household, current_savings=Decimal("0"))
    db_session.add(goal)
    db_session.flush()
    db_session.expire(goal)
    assert goal.current_savings == Decimal("0")


def test_current_savings_absent_stays_null_never_zero(db_session):
    household = _household(db_session)
    goal = _goal(household)
    db_session.add(goal)
    db_session.flush()
    raw = db_session.execute(text("select current_savings from household_goals where id = :id"), {"id": goal.id}).scalar()
    assert raw is None


def test_negative_current_savings_is_rejected(db_session):
    _violation(db_session, _goal(_household(db_session), current_savings=Decimal("-0.01")))


@pytest.mark.parametrize("name", ["", "   "])
def test_a_blank_name_is_rejected(db_session, name):
    _violation(db_session, _goal(_household(db_session), name=name))


def test_a_goal_round_trips_exactly(db_session):
    household = _household(db_session)
    goal = _goal(household, current_savings=Decimal("12500.50"), notes="Deposit for a flat", is_active=False)
    db_session.add(goal)
    db_session.flush()
    db_session.expire(goal)
    assert (goal.name, goal.goal_type, goal.target_amount, goal.current_savings, goal.target_date,
            goal.notes, goal.is_active) == (
        "New home", "house", Decimal("60000.00"), Decimal("12500.50"), date(2030, 6, 30),
        "Deposit for a flat", False,
    )


def test_goals_are_deleted_with_their_household(db_session):
    """Integrity only -- there is no household deletion API."""
    household = _household(db_session)
    db_session.add_all([_goal(household), _goal(household, name="Travel", goal_type="travel")])
    db_session.flush()
    db_session.execute(text("DELETE FROM households WHERE id = :id"), {"id": household.id})
    assert db_session.execute(text("select count(*) from household_goals where household_id = :h"),
                              {"h": household.id}).scalar() == 0


def test_goals_of_two_households_stay_separate(db_session):
    a, b = _household(db_session, "Goal A"), _household(db_session, "Goal B")
    db_session.add_all([_goal(a, name="A house"), _goal(b, name="B house")])
    db_session.flush()
    names = dict(db_session.execute(text(
        "select household_id, name from household_goals where household_id in (:a, :b)"), {"a": a.id, "b": b.id}).all())
    assert names == {a.id: "A house", b.id: "B house"}


# -------------------------------------------------- individual goals intact


def test_the_individual_financial_goals_table_is_unchanged(db_session):
    """Phase 36 must not touch the individual goal model at all."""
    columns = {c["name"]: c for c in inspect(db_session.connection()).get_columns("financial_goals")}
    assert set(columns) == {"id", "customer_id", "goal_type", "target_amount", "target_date",
                            "current_savings", "priority", "created_at"}
    fks = inspect(db_session.connection()).get_foreign_keys("financial_goals")
    assert [fk["referred_table"] for fk in fks] == ["customers"]
