"""Phase 15 — startup model-artifact warming (sections 15/16/17).

Reuses the EXISTING `@lru_cache(maxsize=1)`-decorated loader functions
already in `agents/nodes.py` (Phase 10) — this module adds no new
loading logic (section 17: "do not duplicate model-loading logic"); it
only TRIGGERS those caches to populate once, eagerly, at application
startup rather than lazily on the first request that happens to need
them. If a required artifact is missing/corrupted/incompatible, the
resulting exception propagates out of the lifespan context manager,
which FastAPI/uvicorn surfaces as a hard startup failure — the
application never starts serving requests with a broken/absent model
(section 16: "fail clearly rather than silently retraining"; nothing here
ever downloads a dataset, fits a preprocessor, or trains/retrains a
model).

`GEMINI_API_KEY` is deliberately NOT checked here: Phase 13's own
`run_explanation` (and this phase's own `qa_service.answer_question`)
already have an established, approved graceful-degradation path when no
key is configured (a templated fallback / a 503 on that one request) —
treating a missing Gemini key as a fatal, whole-application startup
failure would be a stricter behaviour than Phase 13 itself defines, which
this phase has no authority to introduce.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from wealthpilot.agents import nodes as N

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"


def warm_model_caches() -> None:
    """Eagerly populates Phase 10's own lru_cache'd model loaders. Never
    trains, never fits, never downloads — only `joblib.load`s already-
    serialized artifacts exactly as Phase 4/5 produced them."""
    logger.info("Warming risk model cache (models/risk/...)")
    N._risk_artifacts_cached()

    logger.info("Warming behaviour model cache (models/behaviour/...)")
    N._behaviour_artifacts_cached()

    logger.info("Warming FAR-Trans reference-table cache")
    N._far_trans_tables_cached()

    if not METRICS_PATH.exists():
        raise RuntimeError(f"required artifact missing: {METRICS_PATH}")
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    if "market" not in metrics:
        raise RuntimeError(f"{METRICS_PATH} is missing the required 'market' section")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    warm_model_caches()
    logger.info("Model artifacts warmed; application ready to serve requests.")
    yield
