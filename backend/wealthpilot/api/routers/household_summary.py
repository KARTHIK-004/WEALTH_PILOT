"""Phase 34 — the household financial summary route.

One read-only endpoint, `GET /api/households/{household_id}/financial-summary`,
deliberately kept in its own module so the Phase 33 CRUD router stays exactly
what it is: source-record storage with no calculation in it.

There is no mutation endpoint for calculations — a summary is derived from the
Phase 33 records and is never stored, so there is nothing to POST, PUT or
DELETE. The Phase 33 CRUD routes are unchanged.

Authorization is Phase 32/33's, reused unchanged: `X-Customer-Id` (asserted,
not authenticated — `docs/SECURITY.md`) and household membership. Any member
may read the summary; no primary-only restriction applies because nothing here
changes data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_acting_customer_id, get_session
from wealthpilot.api.schemas import HouseholdFinancialSummaryResponse
from wealthpilot.api.services import household_summary_service as service

router = APIRouter(tags=["household-finances"])


@router.get(
    "/api/households/{household_id}/financial-summary",
    response_model=HouseholdFinancialSummaryResponse,
)
def get_household_financial_summary(
    household_id: int,
    acting_customer_id: int = Depends(get_acting_customer_id),
    session: Session = Depends(get_session),
) -> HouseholdFinancialSummaryResponse:
    """A deterministic, factual summary of this household's own financial
    records: aggregated income, expenses, assets and liabilities, its monthly
    cash-flow view, its net position and its emergency-fund position.

    It produces no recommendation, no score, no ranking and no goal
    feasibility, and it never affects any customer's individual analysis.
    Unknown figures are `null` with a stated reason — never 0.
    """
    return service.get_financial_summary(session, household_id, acting_customer_id)
