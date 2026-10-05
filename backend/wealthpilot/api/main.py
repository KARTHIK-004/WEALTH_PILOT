"""FastAPI application entrypoint.

Phase 0 built the app instance, CORS, and RFC 7807 error responses. Phase
15 adds: startup model-artifact warming (`api/lifespan.py`), the full
router set (BUILD_PLAN.md section 12), and moves the RFC 7807 handlers
into `api/errors.py` so a route can raise a specific, named domain
exception (`CustomerNotFoundError`, ...) instead of building a response
inline. No financial logic lives in this file or is added by this phase
— every router only calls an existing Phase 4-14 component.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wealthpilot import __version__
from wealthpilot.api import sse
from wealthpilot.api.errors import register_exception_handlers
from wealthpilot.api.lifespan import lifespan
from wealthpilot.api.routers import (
    analysis,
    health,
    household_finances,
    household_goals,
    household_summary,
    households,
    profiles,
    qa,
    scenarios,
)
from wealthpilot.config import configure_logging, get_settings

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Educational decision-support prototype. Not licensed financial "
        "advice. See /api/health."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(profiles.router)
app.include_router(households.router)
app.include_router(household_finances.router)
app.include_router(household_summary.router)
app.include_router(household_goals.router)
# sse.router BEFORE analysis.router: FastAPI matches routes in registration
# order, and the static path "/api/analysis/stream" must be tried before
# the dynamic "/api/analysis/{analysis_id}" -- registered the other way
# around, a request for /api/analysis/stream matched {analysis_id}="stream"
# first and failed int-parsing validation (a real 422 this project's own
# test suite caught before any other symptom appeared).
app.include_router(sse.router)
app.include_router(analysis.router)
app.include_router(scenarios.router)
app.include_router(qa.router)
