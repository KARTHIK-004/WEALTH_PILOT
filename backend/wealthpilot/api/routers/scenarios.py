"""POST /api/scenarios/compare (BUILD_PLAN.md section 12).

Runs the SAME `analysis_service.get_or_run_analysis` twice (once per
scenario) and summarizes each already-computed `AnalysisResult` -- never
a new calculation. "Recompute" (BUILD_PLAN.md's own word for this route)
means running the existing pipeline again with a different input
parameter (`portfolio_strategy`), not deriving a new formula for the
comparison itself.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.schemas import ScenarioCompareRequest, ScenarioCompareResponse, ScenarioParameters, ScenarioSummary
from wealthpilot.api.services.analysis_service import get_or_run_analysis

router = APIRouter(tags=["scenarios"])


def _summarize(label: str, params: ScenarioParameters, session: Session) -> ScenarioSummary:
    run = get_or_run_analysis(session, params.profile_id, portfolio_strategy=params.portfolio_strategy)
    result = run.result or {}
    risk = result.get("risk") or {}
    goals = result.get("goals") or []
    portfolio = result.get("portfolio") or {}
    compliance = result.get("compliance") or {}
    recommendation = result.get("recommendation") or {}

    return ScenarioSummary(
        label=label,
        risk_category=risk.get("risk_category"),
        goal_feasibility=[g.get("feasibility") for g in goals if g.get("feasibility")],
        portfolio_strategy=portfolio.get("strategy"),
        expected_return=portfolio.get("expected_return"),
        expected_volatility=portfolio.get("expected_volatility"),
        sharpe_ratio=portfolio.get("sharpe_ratio"),
        compliance_decision=compliance.get("decision"),
        recommendation_status=recommendation.get("status"),
    )


@router.post("/api/scenarios/compare", response_model=ScenarioCompareResponse)
def compare_scenarios(payload: ScenarioCompareRequest, session: Session = Depends(get_session)) -> ScenarioCompareResponse:
    return ScenarioCompareResponse(
        scenario_a=_summarize("A", payload.scenario_a, session),
        scenario_b=_summarize("B", payload.scenario_b, session),
    )
