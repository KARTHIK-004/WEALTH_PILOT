"""Liveness/readiness endpoint.

Phase 15 extends the Phase 0 shape with `model_versions` (BUILD_PLAN.md
section 12: health's output is "status, loaded model versions") without
removing or renaming any existing field — `test_health.py`'s Phase 0
assertions on `status`/`app_name`/`version` still pass unchanged.

Reads version STRINGS only (constants and small config/metrics files) —
never touches the `@lru_cache`d binary model artifacts themselves (those
are warmed once at startup by `api/lifespan.py`, not on every health
check), keeping this endpoint lightweight per section 4: "must not train
models... must not run the full analysis pipeline"."""

import json

from fastapi import APIRouter

from wealthpilot import __version__
from wealthpilot.agents.nodes import BEHAVIOUR_MODEL_VERSION, PORTFOLIO_CONFIG_VERSION, RISK_MODEL_VERSION
from wealthpilot.api.lifespan import METRICS_PATH
from wealthpilot.api.schemas import HealthResponse, ModelVersions
from wealthpilot.config import get_settings
from wealthpilot.core.compliance import load_rules

router = APIRouter(tags=["health"])


def _market_model_version() -> str | None:
    if not METRICS_PATH.exists():
        return None
    try:
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return (metrics.get("market") or {}).get("model_version")


def _compliance_rules_version() -> str | None:
    try:
        return load_rules().version
    except (OSError, ValueError):
        return None


@router.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.environment,
        model_versions=ModelVersions(
            risk=RISK_MODEL_VERSION,
            behaviour=BEHAVIOUR_MODEL_VERSION,
            market=_market_model_version(),
            portfolio=PORTFOLIO_CONFIG_VERSION,
            compliance_rules=_compliance_rules_version(),
        ),
    )
