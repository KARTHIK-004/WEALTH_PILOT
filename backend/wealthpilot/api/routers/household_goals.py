"""Phase 36 — household goal routes (stored facts only).

List / get / create / update / delete under an existing household. Thin routes
only: validation lives in the Pydantic schemas, and every rule and
authorization decision in `api/services/household_goal_service.py`.

Authorization is Phase 32/33's, reused unchanged: the caller's associated
customer arrives in `X-Customer-Id` (asserted, not authenticated — see
`docs/SECURITY.md`), any member of the household may read, and only the
primary member may create, update or delete. `household_id` always comes from
the path, never from a payload.

These routes compute nothing: no projection, required contribution or
feasibility is derived from a household goal (`docs/DECISIONS.md` ADR-035).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_acting_customer_id, get_session
from wealthpilot.api.schemas import HouseholdGoalCreate, HouseholdGoalResponse, HouseholdGoalUpdate
from wealthpilot.api.services import household_goal_service as service

router = APIRouter(tags=["household-goals"])


@router.get("/api/households/{household_id}/goals", response_model=list[HouseholdGoalResponse])
def list_household_goals(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> list[HouseholdGoalResponse]:
    """Every goal of this household, as stored, in id order (never ranked)."""
    return service.list_goals(session, household_id, acting_customer_id)


@router.get("/api/households/{household_id}/goals/{goal_id}", response_model=HouseholdGoalResponse)
def get_household_goal(
    household_id: int,
    goal_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdGoalResponse:
    """One goal of this household. A goal of another household is a 404."""
    return service.get_goal(session, household_id, acting_customer_id, goal_id)


@router.post("/api/households/{household_id}/goals", response_model=HouseholdGoalResponse, status_code=201)
def create_household_goal(
    household_id: int,
    payload: HouseholdGoalCreate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdGoalResponse:
    return service.create_goal(session, household_id, acting_customer_id, payload)


@router.put("/api/households/{household_id}/goals/{goal_id}", response_model=HouseholdGoalResponse)
def update_household_goal(
    household_id: int,
    goal_id: int,
    payload: HouseholdGoalUpdate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdGoalResponse:
    """Updates only the fields supplied. A goal of another household is a 404."""
    return service.update_goal(session, household_id, acting_customer_id, goal_id, payload)


@router.delete("/api/households/{household_id}/goals/{goal_id}", status_code=204)
def delete_household_goal(
    household_id: int,
    goal_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> Response:
    service.delete_goal(session, household_id, acting_customer_id, goal_id)
    return Response(status_code=204)
