"""Fictional demonstration data for the Financial Behaviour & Sentiment page (development / demo mode only).

`POST /api/demo/financial-behaviour` answers only when `DEMO_MODE_ENABLED=true`; otherwise it is a 404 problem (fail closed). It takes NO database session, so it cannot read or write a
customer record; the optional text is analysed in memory by the rules baseline and never stored or logged; nothing here reaches any tamper-evident record store, an external anchor, a model or the analysis pipeline.
A backend that is down is still an ordinary unreachable error for the frontend: this route never substitutes fake data for a failure.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from wealthpilot.api.errors import DemoModeDisabledError
from wealthpilot.api.schemas import DemoFamilyFinancialBehaviourResponse, DemoFinancialBehaviourResponse, PersonalizedInsightRequest
from wealthpilot.api.services import demo_behaviour_service
from wealthpilot.config import get_settings

router = APIRouter(tags=["demo"])


def require_demo_mode() -> None:
    if not get_settings().demo_mode_enabled:
        raise DemoModeDisabledError("The demonstration data is switched off on this server. Set DEMO_MODE_ENABLED=true in the backend environment (development only) and restart the backend.")


@router.post("/api/demo/financial-behaviour", response_model=DemoFinancialBehaviourResponse)
def create_demo_financial_behaviour(payload: PersonalizedInsightRequest, _: None = Depends(require_demo_mode)) -> DemoFinancialBehaviourResponse:
    """Fictional months with their calculated ratios and changes, plus the rules-baseline reading of the optional text (an unusable text is a 400 that never echoes it). Demo mode only."""
    return demo_behaviour_service.build_demo(payload.text)


@router.post("/api/demo/family-financial-behaviour", response_model=DemoFamilyFinancialBehaviourResponse)
def create_demo_family_financial_behaviour(payload: PersonalizedInsightRequest, _: None = Depends(require_demo_mode)) -> DemoFamilyFinancialBehaviourResponse:
    """A fictional family (three members and a household) with calculated ratios, changes and household totals, plus the rules-baseline reading of the optional text (the primary member's note).
    Demo mode only."""
    return demo_behaviour_service.build_family_demo(payload.text)
