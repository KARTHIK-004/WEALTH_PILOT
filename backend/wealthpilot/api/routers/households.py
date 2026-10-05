"""Phase 32 — household identity and membership routes.

`POST /api/households`, `GET /api/households/{id}`, `GET`/`POST
/api/households/{id}/members`, `DELETE /api/households/{id}/members/
{member_id}` and `GET /api/profiles/{id}/household`. Thin routes only:
validation via the Pydantic schemas, every rule and every authorization
decision in `api/services/household_service.py`. Every route requires the
caller's associated customer in `X-Customer-Id` (`api/dependencies.py`) and
serves only households that customer belongs to.

No household financial data of any kind exists here -- Phase 32 is identity
and membership only (`docs/DECISIONS.md` ADR-031). There is deliberately no
route to delete a household.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_acting_customer_id, get_session
from wealthpilot.api.schemas import (
    HouseholdCreateRequest,
    HouseholdMemberCreateRequest,
    HouseholdMemberOut,
    HouseholdMembersResponse,
    HouseholdOut,
    ProfileHouseholdResponse,
)
from wealthpilot.api.services import household_service

router = APIRouter(tags=["households"])


@router.post("/api/households", response_model=HouseholdOut, status_code=201)
def create_household(
    payload: HouseholdCreateRequest,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdOut:
    """Creates a household with the calling customer as its `self`/`primary`
    member. 409 if that customer already belongs to a household."""
    household, _primary = household_service.create_household(session, acting_customer_id, payload.name)
    return household


@router.get("/api/households/{household_id}", response_model=HouseholdOut)
def get_household(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdOut:
    return household_service.get_household(session, household_id, acting_customer_id)


@router.get("/api/profiles/{profile_id}/household", response_model=ProfileHouseholdResponse)
def get_profile_household(
    profile_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> ProfileHouseholdResponse:
    """The calling customer's own household, or `household: null` when they
    have none (a 200 -- never an implicit creation)."""
    return household_service.get_profile_household(session, profile_id, acting_customer_id)


@router.get("/api/households/{household_id}/members", response_model=HouseholdMembersResponse)
def list_household_members(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdMembersResponse:
    return household_service.list_members(session, household_id, acting_customer_id)


@router.post("/api/households/{household_id}/members", response_model=HouseholdMemberOut, status_code=201)
def add_household_member(
    household_id: int,
    payload: HouseholdMemberCreateRequest,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdMemberOut:
    """Associates an existing customer (by `customer_id`) with the household.
    Primary member only. The association does not let anyone view or switch
    into that customer's account."""
    return household_service.add_member(session, household_id, acting_customer_id, payload)


@router.delete("/api/households/{household_id}/members/{member_id}", status_code=204)
def remove_household_member(
    household_id: int,
    member_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> Response:
    """Removes one membership (primary member only). The primary member
    itself can never be removed -- 409."""
    household_service.remove_member(session, household_id, acting_customer_id, member_id)
    return Response(status_code=204)
