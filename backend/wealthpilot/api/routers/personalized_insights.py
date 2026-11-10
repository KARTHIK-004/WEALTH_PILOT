"""Financial behaviour and user-text sentiment, display only (Research Enhancement Track, ADR-043).

Thin route; rules live in `core/` and orchestration in `api/services/personalized_insight_service.py`. Scoped by `profile_id` like the other per-customer routes
(ADR-024: data scoping, not authorisation). A POST because the optional text must not travel in a URL or appear in access logs; it is analysed in memory and never stored.
Nothing here is read by `POST /api/analysis`, the recommendation, the risk profile or compliance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.schemas import PersonalizedInsightRequest, PersonalizedInsightResponse, SentimentModelStatusOut
from wealthpilot.api.services import personalized_insight_service as service

router = APIRouter(tags=["personalized-insights"])


@router.post("/api/profiles/{profile_id}/personalized-insights", response_model=PersonalizedInsightResponse)
def create_personalized_insight(profile_id: int, payload: PersonalizedInsightRequest, session: Session = Depends(get_session)) -> PersonalizedInsightResponse:
    """Behaviour facts from the customer's own monthly records, plus an optional, unvalidated reading of text they chose to write. Missing text or missing months yield
    explicit unavailable states, never a neutral label or a zero."""
    return service.build_insight(session, profile_id, payload.text)


@router.get("/api/sentiment-model/status", response_model=SentimentModelStatusOut)
def get_sentiment_model_status() -> SentimentModelStatusOut:
    """Whether a trained sentiment model is in use (ADR-052): `disabled` (the default; the rules baseline is the method), `ready` (a validated artifact is loaded) or `unavailable` (switched on
    but unusable, with a fixed reason code and the rules baseline answering). Customer-independent, read-only, and it never returns a path, a secret or any text."""
    return service.sentiment_model_status()
