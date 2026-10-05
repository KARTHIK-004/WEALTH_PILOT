"""Phase 32 -- the database itself enforces the household rules.

Every rule the API also checks is asserted here against real PostgreSQL
(TEST_DATABASE_URL, rolled back after each test), so no code path -- present
or future -- can create an invalid household or membership. Expected
violations are provoked inside a SAVEPOINT (`begin_nested`) so the failed
write is undone without discarding the test's own setup rows.
"""

from __future__ import annotations

from typing import get_args

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from wealthpilot.api.schemas import HouseholdRelationship, HouseholdRole
from wealthpilot.db.models import (
    HOUSEHOLD_RELATIONSHIPS,
    HOUSEHOLD_ROLES,
    Customer,
    Household,
    HouseholdMember,
)


def _customer(db_session, name="Household Test Customer") -> Customer:
    customer = Customer(name=name, data_source="user-entered")
    db_session.add(customer)
    db_session.flush()
    return customer


def _household(db_session, name="Test Household") -> Household:
    household = Household(name=name)
    db_session.add(household)
    db_session.flush()
    return household


def _member(household, customer, relationship="self", role="primary", is_dependent=None) -> HouseholdMember:
    return HouseholdMember(
        household_id=household.id,
        customer_id=customer.id,
        relationship_type=relationship,
        role=role,
        is_dependent=(role == "dependent") if is_dependent is None else is_dependent,
    )


def _violation(db_session, row) -> None:
    """Asserts the database rejects `row`, without poisoning the session."""
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(row)


def test_household_and_membership_round_trip(db_session):
    customer = _customer(db_session)
    household = _household(db_session)
    db_session.add(_member(household, customer))
    db_session.flush()

    fetched = db_session.scalar(select(HouseholdMember).where(HouseholdMember.customer_id == customer.id))
    assert fetched is not None
    assert (fetched.relationship_type, fetched.role, fetched.is_dependent) == ("self", "primary", False)
    assert fetched.created_at is not None and fetched.updated_at is not None
    assert fetched.household.name == "Test Household"
    assert fetched.customer.id == customer.id


def test_households_table_has_no_financial_column(db_session):
    """Identity only: nothing financial may ever be added to `households`
    or `household_members` in Phase 32."""
    inspector = inspect(db_session.connection())
    assert {c["name"] for c in inspector.get_columns("households")} == {"id", "name", "created_at", "updated_at"}
    assert {c["name"] for c in inspector.get_columns("household_members")} == {
        "id", "household_id", "customer_id", "relationship", "role", "is_dependent", "created_at", "updated_at",
    }


def test_a_customer_belongs_to_at_most_one_household(db_session):
    customer = _customer(db_session)
    first, second = _household(db_session, "First"), _household(db_session, "Second")
    db_session.add(_member(first, customer))
    db_session.flush()

    _violation(db_session, _member(second, customer))


def test_the_same_customer_cannot_appear_twice_in_one_household(db_session):
    customer = _customer(db_session)
    household = _household(db_session)
    db_session.add(_member(household, customer))
    db_session.flush()

    _violation(db_session, _member(household, customer, relationship="spouse", role="member"))


def test_a_household_has_at_most_one_primary(db_session):
    a, b = _customer(db_session, "A"), _customer(db_session, "B")
    household = _household(db_session)
    db_session.add(_member(household, a))
    db_session.flush()

    _violation(db_session, _member(household, b))  # a second (self, primary)


def test_different_households_can_each_have_a_primary(db_session):
    a, b = _customer(db_session, "A"), _customer(db_session, "B")
    db_session.add_all([_member(_household(db_session, "H1"), a), _member(_household(db_session, "H2"), b)])
    db_session.flush()  # no violation


def test_a_household_can_have_many_non_primary_members(db_session):
    primary, spouse, child = _customer(db_session, "P"), _customer(db_session, "S"), _customer(db_session, "C")
    household = _household(db_session)
    db_session.add_all([
        _member(household, primary),
        _member(household, spouse, relationship="spouse", role="member"),
        _member(household, child, relationship="child", role="dependent"),
    ])
    db_session.flush()
    count = db_session.scalar(text("SELECT count(*) FROM household_members WHERE household_id = :h"), {"h": household.id})
    assert count == 3


@pytest.mark.parametrize("relationship", ["cousin", "Self", "", "SPOUSE"])
def test_unsupported_relationship_value_is_rejected(db_session, relationship):
    customer = _customer(db_session)
    _violation(db_session, _member(_household(db_session), customer, relationship=relationship, role="member", is_dependent=False))


@pytest.mark.parametrize("role", ["owner", "Primary", "", "admin"])
def test_unsupported_role_value_is_rejected(db_session, role):
    customer = _customer(db_session)
    _violation(db_session, _member(_household(db_session), customer, relationship="other", role=role, is_dependent=False))


def test_a_primary_must_have_relationship_self(db_session):
    customer = _customer(db_session)
    _violation(db_session, _member(_household(db_session), customer, relationship="spouse", role="primary"))


def test_self_can_never_be_a_dependent(db_session):
    customer = _customer(db_session)
    _violation(db_session, _member(_household(db_session), customer, relationship="self", role="dependent"))


def test_is_dependent_must_match_the_role(db_session):
    a, b = _customer(db_session, "A"), _customer(db_session, "B")
    household = _household(db_session)
    _violation(db_session, _member(household, a, relationship="child", role="member", is_dependent=True))
    _violation(db_session, _member(household, b, relationship="child", role="dependent", is_dependent=False))


def test_membership_requires_an_existing_household_and_customer(db_session):
    customer = _customer(db_session)
    household = _household(db_session)
    _violation(db_session, HouseholdMember(household_id=999_999_999, customer_id=customer.id, relationship_type="other", role="member", is_dependent=False))
    _violation(db_session, HouseholdMember(household_id=household.id, customer_id=999_999_999, relationship_type="other", role="member", is_dependent=False))


def test_deleting_a_customer_removes_only_their_membership(db_session):
    primary, spouse = _customer(db_session, "P"), _customer(db_session, "S")
    household = _household(db_session)
    db_session.add_all([_member(household, primary), _member(household, spouse, relationship="spouse", role="member")])
    db_session.flush()

    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": spouse.id})
    remaining = db_session.execute(text("SELECT customer_id FROM household_members WHERE household_id = :h"), {"h": household.id}).scalars().all()
    assert remaining == [primary.id]


def test_deleting_a_household_removes_its_memberships_and_leaves_customers(db_session):
    customer = _customer(db_session)
    household = _household(db_session)
    db_session.add(_member(household, customer))
    db_session.flush()

    db_session.execute(text("DELETE FROM households WHERE id = :id"), {"id": household.id})
    assert db_session.scalar(text("SELECT count(*) FROM household_members WHERE customer_id = :c"), {"c": customer.id}) == 0
    assert db_session.scalar(text("SELECT count(*) FROM customers WHERE id = :c"), {"c": customer.id}) == 1


def test_the_customers_table_is_unchanged_by_households(db_session):
    """The existing customer model stays as it was: no household column."""
    columns = {c["name"] for c in inspect(db_session.connection()).get_columns("customers")}
    assert columns == {
        "id", "name", "age", "income", "employment_status", "customer_type", "investment_capacity",
        "risk_inputs", "data_source", "created_at",
    }


def test_python_vocabularies_match_the_api_literals_and_the_check_constraints(db_session):
    assert set(HOUSEHOLD_RELATIONSHIPS) == set(get_args(HouseholdRelationship))
    assert set(HOUSEHOLD_ROLES) == set(get_args(HouseholdRole))
    constraints = {c["name"]: c["sqltext"] for c in inspect(db_session.connection()).get_check_constraints("household_members")}
    for value in HOUSEHOLD_RELATIONSHIPS:
        assert f"'{value}'" in constraints["ck_household_members_relationship"]
    for value in HOUSEHOLD_ROLES:
        assert f"'{value}'" in constraints["ck_household_members_role"]
