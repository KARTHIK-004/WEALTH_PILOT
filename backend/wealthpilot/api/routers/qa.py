"""POST /api/qa (BUILD_PLAN.md section 12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from wealthpilot.agents.explanation import CANONICAL_DISCLAIMER
from wealthpilot.api.dependencies import get_session
from wealthpilot.api.errors import AnalysisNotFoundError, ServiceUnavailableError
from wealthpilot.api.schemas import QARequest, QAResponse
from wealthpilot.api.services.qa_service import QAUnavailableError, answer_question
from wealthpilot.db.models import AnalysisRun

router = APIRouter(tags=["qa"])


@router.post("/api/qa", response_model=QAResponse)
def ask_question(payload: QARequest, session: Session = Depends(get_session)) -> QAResponse:
    context = None
    if payload.analysis_id is not None:
        run = session.get(AnalysisRun, payload.analysis_id)
        if run is None or run.result is None:
            raise AnalysisNotFoundError(f"No completed analysis with id={payload.analysis_id}")
        result = run.result
        context = {
            "risk_category": (result.get("risk") or {}).get("risk_category"),
            "compliance_decision": (result.get("compliance") or {}).get("decision"),
            "recommendation_status": (result.get("recommendation") or {}).get("status"),
        }

    try:
        answer = answer_question(payload.question, context)
    except QAUnavailableError as exc:
        raise ServiceUnavailableError(str(exc)) from exc

    return QAResponse(answer=answer, disclaimer=CANONICAL_DISCLAIMER)
