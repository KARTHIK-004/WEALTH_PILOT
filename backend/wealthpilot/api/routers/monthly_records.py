"""Optional monthly financial records and the read-only behaviour features
derived from them (Research Enhancement Track B1, ADR-042).

Thin routes only; rules live in `api/schemas.py` and
`api/services/monthly_records_service.py`. Scoped by `profile_id` exactly like
the other per-customer profile routes (ADR-024: data scoping, not
authorization). Nothing here is read by `POST /api/analysis`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.schemas import (
    BehaviourFeaturesResponse,
    MonthlyRecordListResponse,
    MonthlyRecordResponse,
    MonthlyRecordUpdate,
)
from wealthpilot.api.services import monthly_records_service as service

router = APIRouter(tags=["monthly-financial-records"])


@router.get("/api/profiles/{profile_id}/monthly-financial-records", response_model=MonthlyRecordListResponse)
def list_monthly_records(profile_id: int, session: Session = Depends(get_session)) -> MonthlyRecordListResponse:
    """Every reported month for this customer, newest first. No records is a
    normal state (an empty list), not an error."""
    return service.list_records(session, profile_id)


@router.get("/api/profiles/{profile_id}/monthly-financial-records/{period}", response_model=MonthlyRecordResponse)
def get_monthly_record(profile_id: int, period: str, session: Session = Depends(get_session)) -> MonthlyRecordResponse:
    return service.get_record(session, profile_id, period)


@router.put("/api/profiles/{profile_id}/monthly-financial-records/{period}", response_model=MonthlyRecordResponse)
def put_monthly_record(
    profile_id: int, period: str, payload: MonthlyRecordUpdate, session: Session = Depends(get_session)
) -> MonthlyRecordResponse:
    """Creates or corrects one month (`period` is `YYYY-MM`). Omitted fields are
    untouched; an explicit null clears a field back to "not reported"."""
    return service.upsert_record(session, profile_id, period, payload)


@router.delete("/api/profiles/{profile_id}/monthly-financial-records/{period}", status_code=204)
def delete_monthly_record(profile_id: int, period: str, session: Session = Depends(get_session)) -> Response:
    service.delete_record(session, profile_id, period)
    return Response(status_code=204)


@router.get("/api/profiles/{profile_id}/behaviour-features", response_model=BehaviourFeaturesResponse)
def get_behaviour_features(profile_id: int, session: Session = Depends(get_session)) -> BehaviourFeaturesResponse:
    """Read-only features from the customer's own monthly records. Each feature
    is a number or the reason it is unavailable; nothing is a score and no
    recommendation reads them."""
    return service.behaviour_features(session, profile_id)
