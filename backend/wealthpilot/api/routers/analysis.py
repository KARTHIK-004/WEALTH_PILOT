"""POST /api/analysis, GET /api/analysis/{id} (BUILD_PLAN.md section 12).

Thin routes: request -> validation -> `api/services/analysis_service.py`
(which itself only calls the existing `agents/graph.py`,
`agents/recommendation.py`, `agents/explanation.py`) -> response schema.
No financial calculation, no node sequencing, and no compliance/
savings-first/recommendation decision logic lives in this file.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.errors import AnalysisNotFoundError
from wealthpilot.api.schemas import AnalysisRequest, AnalysisResult
from wealthpilot.api.services.analysis_service import get_or_run_analysis
from wealthpilot.db.models import AnalysisRun

router = APIRouter(tags=["analysis"])


@router.post("/api/analysis", response_model=AnalysisResult)
def run_analysis(payload: AnalysisRequest, session: Session = Depends(get_session)) -> AnalysisResult:
    run = get_or_run_analysis(session, payload.profile_id, portfolio_strategy=payload.portfolio_strategy)
    return AnalysisResult.model_validate(run.result)


@router.get("/api/analysis/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: int, session: Session = Depends(get_session)) -> AnalysisResult:
    run = session.get(AnalysisRun, analysis_id)
    if run is None or run.result is None:
        raise AnalysisNotFoundError(f"No completed analysis with id={analysis_id}")
    return AnalysisResult.model_validate(run.result)
