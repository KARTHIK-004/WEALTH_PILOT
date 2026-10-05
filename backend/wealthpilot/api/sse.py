"""GET /api/analysis/stream (BUILD_PLAN.md section 12/16).

Streams the SAME `PipelineRun.events()` mechanism `api/services/
analysis_service.py`'s synchronous `/api/analysis` endpoint uses, so
there is one execution path for the graph + recommendation + explanation
sequence, not two. Every event forwarded here is already a `NodeEvent` —
node name, status, duration, a short templated summary, and a model
version (this project's own established `analysis_service.NodeEvent`
contract, section 22's "consistent machine-readable SSE structure") —
never a prompt, a reasoning trace, or a raw exception (sections 21/23).

**Session lifecycle**: uses `api/dependencies.py::get_session_factory`
(a plain, non-generator dependency returning a zero-arg session
constructor) instead of `get_session`. FastAPI resolves a `Depends()`
GENERATOR's cleanup once the route function itself returns — for a
`StreamingResponse`, that happens before the body generator is actually
drained by the ASGI server, which would close/commit the session while
the pipeline is still mid-run. `stream_events` below constructs its own
session from the factory and closes/commits it itself, exactly mirroring
`get_session`'s commit-on-success/rollback-on-exception policy inline.

**No separate `AnalysisRun`/`AgentLog` persistence here** (unlike POST
/api/analysis): this endpoint is a live view of one run, not the
canonical cached-result writer, so writing a second, parallel history of
the same run would only create duplicate rows with no way to reconcile
them against POST /api/analysis's cache-by-profile-hash lookup. Phase
14's `recommendation_engine_node` still persists its own `Recommendation`
row exactly as designed (unmodified) whenever the run reaches `approved`
— that is Phase 14's own already-approved behaviour, not something added
here.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Generator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from wealthpilot.api.dependencies import get_session_factory
from wealthpilot.api.services.analysis_service import NodeEvent, PipelineRun

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


def _format_event(event: NodeEvent) -> str:
    data = {
        "node": event.node,
        "status": event.status,
        "duration_ms": event.duration_ms,
        "summary": event.summary,
        "model_version": event.model_version,
    }
    return f"event: node_progress\ndata: {json.dumps(data)}\n\n"


def _format_error() -> str:
    # Never the exception message/type/trace (section 25/49) -- a fixed,
    # safe, public string only.
    return 'event: error\ndata: {"title": "Analysis failed", "detail": "An unexpected error occurred."}\n\n'


def stream_events(profile_id: int, portfolio_strategy: str | None, session_factory: Callable[[], Session]) -> Generator[str, None, None]:
    session = session_factory()
    try:
        pipeline = PipelineRun(session=session, customer_id=profile_id, portfolio_strategy=portfolio_strategy)
        try:
            for event in pipeline.events():
                yield _format_event(event)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("SSE analysis stream failed", extra={"profile_id": profile_id})
            yield _format_error()
    finally:
        session.close()


@router.get("/api/analysis/stream")
def get_analysis_stream(
    profile_id: int = Query(...),
    portfolio_strategy: str | None = Query(default=None),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
) -> StreamingResponse:
    return StreamingResponse(
        stream_events(profile_id, portfolio_strategy, session_factory),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
