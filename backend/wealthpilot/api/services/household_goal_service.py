"""Phase 36 — household goals (stored facts only).

A household goal belongs to a household through `household_id` alone and is a
separate concept from the individual `financial_goals`: nothing here reads,
writes, converts or merges an individual goal.

This module stores and returns what a household states about its goals. It
computes **nothing**: no inflation-adjusted target, required contribution,
contribution gap, probability or feasibility. `core/goals.py` can only produce
those from a `GoalAssumptions` (explicit return and inflation rates, a
contribution amount), a current date and a historical return series — none of
which exists for a household, and inventing any of them is forbidden
(`docs/DECISIONS.md` ADR-035). An `emergency_fund` goal's `target_amount` is the
household's own stated target; the calculated requirement stays exactly where
Phase 34 put it, in the financial summary, so there is never a second source of
truth for it.

Ownership and authorization reuse Phase 33's helpers unchanged — the same
single implementation of "scoped by BOTH ids, a record of another household is
a 404", and Phase 32's membership checks: any member may read, only the
primary may create, update or delete.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from wealthpilot.api.schemas import HouseholdGoalCreate, HouseholdGoalResponse, HouseholdGoalUpdate
from wealthpilot.api.services.household_finance_service import (
    _create_row,
    _delete_row,
    _list_rows,
    _money,
    _owned_row,
    _Resource,
    _update_row,
)
from wealthpilot.api.services.household_service import require_member
from wealthpilot.db.models import HouseholdGoal

_GOAL = _Resource(HouseholdGoal, "household goal")


def _goal_out(row: HouseholdGoal) -> HouseholdGoalResponse:
    return HouseholdGoalResponse(
        id=row.id, household_id=row.household_id, name=row.name, goal_type=row.goal_type,
        target_amount=_money(row.target_amount),
        # `None` stays `None` -- "not provided" is never reported as 0.
        current_savings=_money(row.current_savings),
        target_date=row.target_date, notes=row.notes, is_active=row.is_active,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def list_goals(session: Session, household_id: int, acting_customer_id: int) -> list[HouseholdGoalResponse]:
    """Every goal of this household, active or not, in id order — a
    deterministic order, never a ranking."""
    return [_goal_out(row) for row in _list_rows(session, _GOAL, household_id, acting_customer_id)]


def get_goal(session: Session, household_id: int, acting_customer_id: int, goal_id: int) -> HouseholdGoalResponse:
    require_member(session, household_id, acting_customer_id)
    return _goal_out(_owned_row(session, _GOAL, household_id, goal_id))


def create_goal(
    session: Session, household_id: int, acting_customer_id: int, payload: HouseholdGoalCreate
) -> HouseholdGoalResponse:
    return _goal_out(_create_row(session, _GOAL, household_id, acting_customer_id, payload.model_dump()))


def update_goal(
    session: Session, household_id: int, acting_customer_id: int, goal_id: int, payload: HouseholdGoalUpdate
) -> HouseholdGoalResponse:
    return _goal_out(
        _update_row(session, _GOAL, household_id, acting_customer_id, goal_id, payload.model_dump(exclude_unset=True))
    )


def delete_goal(session: Session, household_id: int, acting_customer_id: int, goal_id: int) -> None:
    _delete_row(session, _GOAL, household_id, acting_customer_id, goal_id)
