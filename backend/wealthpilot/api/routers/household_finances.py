"""Phase 33 — household financial data routes (source records only).

Four independent resources under an existing household: income, expenses,
assets and liabilities, each with list / create / update / delete. Thin routes
only — validation lives in the Pydantic schemas and every rule and
authorization decision in `api/services/household_finance_service.py`.

Authorization is Phase 32's, reused unchanged: the caller's associated
customer arrives in `X-Customer-Id` (asserted, not authenticated — see
`docs/SECURITY.md`), any member of the household may read, and only the
primary member may create, update or delete. `household_id` always comes from
the path, never from a payload, so a record cannot be moved between
households.

Nothing in this module computes anything from the stored values: these routes
store and return source records and nothing more (`docs/DECISIONS.md`
ADR-032). Phase 34 added the one read-only aggregation endpoint,
`GET /api/households/{household_id}/financial-summary`, in its own module
(`routers/household_summary.py`, ADR-033) — no total, ratio or derived figure
belongs here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_acting_customer_id, get_session
from wealthpilot.api.schemas import (
    HouseholdAssetCreate,
    HouseholdAssetResponse,
    HouseholdAssetUpdate,
    HouseholdExpenseCreate,
    HouseholdExpenseResponse,
    HouseholdExpenseUpdate,
    HouseholdIncomeCreate,
    HouseholdIncomeResponse,
    HouseholdIncomeUpdate,
    HouseholdLiabilityCreate,
    HouseholdLiabilityResponse,
    HouseholdLiabilityUpdate,
)
from wealthpilot.api.services import household_finance_service as service

router = APIRouter(tags=["household-finances"])


# --------------------------------------------------------------------- income


@router.get("/api/households/{household_id}/income", response_model=list[HouseholdIncomeResponse])
def list_household_income(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> list[HouseholdIncomeResponse]:
    """Every income record of this household, as stored. No total is returned."""
    return service.list_income(session, household_id, acting_customer_id)


@router.post("/api/households/{household_id}/income", response_model=HouseholdIncomeResponse, status_code=201)
def create_household_income(
    household_id: int,
    payload: HouseholdIncomeCreate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdIncomeResponse:
    return service.create_income(session, household_id, acting_customer_id, payload)


@router.put("/api/households/{household_id}/income/{income_id}", response_model=HouseholdIncomeResponse)
def update_household_income(
    household_id: int,
    income_id: int,
    payload: HouseholdIncomeUpdate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdIncomeResponse:
    """Updates only the fields supplied. A record of another household is a 404."""
    return service.update_income(session, household_id, acting_customer_id, income_id, payload)


@router.delete("/api/households/{household_id}/income/{income_id}", status_code=204)
def delete_household_income(
    household_id: int,
    income_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> Response:
    service.delete_income(session, household_id, acting_customer_id, income_id)
    return Response(status_code=204)


# ------------------------------------------------------------------- expenses


@router.get("/api/households/{household_id}/expenses", response_model=list[HouseholdExpenseResponse])
def list_household_expenses(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> list[HouseholdExpenseResponse]:
    return service.list_expenses(session, household_id, acting_customer_id)


@router.post("/api/households/{household_id}/expenses", response_model=HouseholdExpenseResponse, status_code=201)
def create_household_expense(
    household_id: int,
    payload: HouseholdExpenseCreate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdExpenseResponse:
    return service.create_expense(session, household_id, acting_customer_id, payload)


@router.put("/api/households/{household_id}/expenses/{expense_id}", response_model=HouseholdExpenseResponse)
def update_household_expense(
    household_id: int,
    expense_id: int,
    payload: HouseholdExpenseUpdate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdExpenseResponse:
    return service.update_expense(session, household_id, acting_customer_id, expense_id, payload)


@router.delete("/api/households/{household_id}/expenses/{expense_id}", status_code=204)
def delete_household_expense(
    household_id: int,
    expense_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> Response:
    service.delete_expense(session, household_id, acting_customer_id, expense_id)
    return Response(status_code=204)


# --------------------------------------------------------------------- assets


@router.get("/api/households/{household_id}/assets", response_model=list[HouseholdAssetResponse])
def list_household_assets(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> list[HouseholdAssetResponse]:
    """Self-reported holdings, as stored — never priced, revalued or optimized."""
    return service.list_assets(session, household_id, acting_customer_id)


@router.post("/api/households/{household_id}/assets", response_model=HouseholdAssetResponse, status_code=201)
def create_household_asset(
    household_id: int,
    payload: HouseholdAssetCreate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdAssetResponse:
    return service.create_asset(session, household_id, acting_customer_id, payload)


@router.put("/api/households/{household_id}/assets/{asset_id}", response_model=HouseholdAssetResponse)
def update_household_asset(
    household_id: int,
    asset_id: int,
    payload: HouseholdAssetUpdate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdAssetResponse:
    return service.update_asset(session, household_id, acting_customer_id, asset_id, payload)


@router.delete("/api/households/{household_id}/assets/{asset_id}", status_code=204)
def delete_household_asset(
    household_id: int,
    asset_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> Response:
    service.delete_asset(session, household_id, acting_customer_id, asset_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- liabilities


@router.get("/api/households/{household_id}/liabilities", response_model=list[HouseholdLiabilityResponse])
def list_household_liabilities(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> list[HouseholdLiabilityResponse]:
    """As stored. `monthly_payment` stays `null` when it was not provided —
    never 0, which would mean "explicitly no payment"."""
    return service.list_liabilities(session, household_id, acting_customer_id)


@router.post("/api/households/{household_id}/liabilities", response_model=HouseholdLiabilityResponse, status_code=201)
def create_household_liability(
    household_id: int,
    payload: HouseholdLiabilityCreate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdLiabilityResponse:
    return service.create_liability(session, household_id, acting_customer_id, payload)


@router.put("/api/households/{household_id}/liabilities/{liability_id}", response_model=HouseholdLiabilityResponse)
def update_household_liability(
    household_id: int,
    liability_id: int,
    payload: HouseholdLiabilityUpdate,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdLiabilityResponse:
    return service.update_liability(session, household_id, acting_customer_id, liability_id, payload)


@router.delete("/api/households/{household_id}/liabilities/{liability_id}", status_code=204)
def delete_household_liability(
    household_id: int,
    liability_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> Response:
    service.delete_liability(session, household_id, acting_customer_id, liability_id)
    return Response(status_code=204)
