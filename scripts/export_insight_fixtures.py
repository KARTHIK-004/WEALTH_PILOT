"""Export REAL backend responses of `POST /api/profiles/{id}/personalized-insights` as fixtures for the frontend component tests (frontend/tests/fixtures/*.json).

    python scripts/export_insight_fixtures.py            # (re)write the fixtures
    python scripts/export_insight_fixtures.py --check    # exit 1 if the saved fixtures differ from what the backend returns now

The responses are produced by the actual route, schemas and core functions -- not hand-written -- from SYNTHETIC monthly figures and a synthetic stored assessment, with the database
session replaced by a stub that fails on any use (no database, no network). Only `analysis_timestamp` is fixed so the files are deterministic. The texts are invented sentences, not user
text, and nothing here is a label, a gold standard or an accuracy figure: it only lets the UI tests render exactly what the backend sends. tests/backend/api/test_insight_fixtures.py
fails if a fixture drifts from the backend.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

FIXTURE_DIR = REPO / "frontend" / "tests" / "fixtures"
FIXED_TIMESTAMP = "2026-01-01T00:00:00Z"

# name -> (synthetic customer id, request body). Customer 1: two months of records and an Aggressive assessment; 2: no records; 3: no stored assessment; 4: Conservative assessment;
# 5: neither records nor an assessment.
SCENARIOS: dict[str, tuple[int, dict]] = {
    "records-only": (1, {"text": None}),
    "conflict": (1, {"text": "I'm worried about losing my savings, and I want to invest more safely."}),
    "uncertain": (1, {"text": "The train was late today."}),
    "mixed-language-cue": (1, {"text": "Mujhe naye plan ke baare mein bahut excited hoon."}),
    "no-records-no-text": (2, {"text": None}),
    "no-records-with-text": (2, {"text": "I feel confident about my savings plan."}),
    "no-assessment": (3, {"text": "I want higher returns."}),
    "conservative-growth": (4, {"text": "I want higher returns."}),
    "nothing-available": (5, {"text": None}),
    # The multi-stage interpretation (ADR-050): every state the page must render.
    "mixed-growth-conflict": (4, {"text": "I am nervous about the market, but I am comfortable taking long-term risk."}),
    "capital-preservation": (4, {"text": "I want to protect my savings and avoid losing money."}),
    "unrelated": (1, {"text": "The weather is beautiful."}),
    "ambiguous": (1, {"text": "I had a good day today."}),
    "negated": (1, {"text": "I am not worried about losing money."}),
    "weak-neutral": (1, {"text": "I want to save for a house."}),
    "too-short": (1, {"text": "Money."}),
    "fallback-rules": (1, {"text": "I am nervous about the market."}),
    # The trained-model states (ADR-052). NO trained model exists: these responses come from the real route and pipeline with a TEST DOUBLE named "test_double_not_a_real_model", so the page can
    # be rendered in every state. They say nothing about any real model's accuracy.
    "model-validated-double": (4, {"text": "I am worried about losing my savings, and I want to invest more safely."}),
    "model-disagreement-double": (1, {"text": "I am nervous about the market."}),
    "model-below-threshold": (1, {"text": "I am nervous about the market."}),
    "model-unavailable-fallback": (1, {"text": "I am nervous about the market."}),
    "model-unavailable-no-fallback": (1, {"text": "I am nervous about the market."}),
}
# Scenarios answered while a model is made to fail, to show the rules-baseline fallback.
FAILING_MODEL = {"fallback-rules"}
# name -> how the model double behaves ("valid" | "disagree" | "low"), or the reason code of an unusable configured model.
MODEL_DOUBLES = {"model-validated-double": "valid", "model-disagreement-double": "disagree", "model-below-threshold": "low"}
UNAVAILABLE = {"model-unavailable-fallback": "dependencies_missing", "model-unavailable-no-fallback": "dependencies_missing"}
NO_FALLBACK = {"model-unavailable-no-fallback"}


def _stubs():
    from wealthpilot.api.errors import CustomerNotFoundError
    from wealthpilot.core.behaviour_features import MonthlyObservation, compute_behaviour_features
    from wealthpilot.core.personalized_insight import RiskProfileView

    def features_for(customer_id: int):
        if customer_id == 404:
            raise CustomerNotFoundError("No customer with id=404")
        if customer_id in (2, 5):
            return compute_behaviour_features([])
        base = 1000 * customer_id
        return compute_behaviour_features([
            MonthlyObservation(period=date(2026, 1, 1), income=Decimal(base * 10), expenses=Decimal(base * 4), savings=Decimal(base * 2)),
            MonthlyObservation(period=date(2026, 2, 1), income=Decimal(base * 10), expenses=Decimal(base * 5), savings=Decimal(base * 2)),
        ])

    def risk_for(customer_id: int):
        if customer_id in (3, 5):
            return None
        return RiskProfileView("Aggressive" if customer_id == 1 else "Conservative", "stored risk assessment of the latest analysis", None)

    return features_for, risk_for


class NoDb:
    def __getattr__(self, name):                                                    # pragma: no cover - only reached on a violation
        raise AssertionError(f"the route used the database session ({name})")


def generate() -> dict[str, dict]:
    from fastapi.testclient import TestClient

    from wealthpilot.api.dependencies import get_session
    from wealthpilot.api.main import app
    from wealthpilot.api.services import personalized_insight_service as svc

    features_for, risk_for = _stubs()
    class FailingModel:
        def interpret(self, text: str):
            raise RuntimeError("the sentiment model is unavailable")

    from wealthpilot.core.sentiment_model import SentimentModelConfig
    from wealthpilot.core.user_text_sentiment import ModelReading

    def double(kind: str):
        class Double:
            def interpret(self, text: str):
                if kind == "valid":
                    return ModelReading("negative", 0.88, True, "sentiment-double-1", "validated", 0.6, (0.6, 0.85), {"positive": 0.04, "negative": 0.88, "neutral": 0.08}, -0.72, "test_double_not_a_real_model")
                if kind == "disagree":
                    return ModelReading("positive", 0.93, True, "sentiment-double-1", "validated", 0.6, (0.6, 0.85), {"positive": 0.93, "negative": 0.03, "neutral": 0.04}, None, "test_double_not_a_real_model")
                return ModelReading("negative", 0.41, True, "sentiment-double-1", "validated", 0.6, (0.6, 0.85), {"positive": 0.29, "negative": 0.41, "neutral": 0.30}, None, "test_double_not_a_real_model")

        return Double()

    original = (svc.monthly_records_service.core_features, svc._risk_profile, svc.get_sentiment_model, svc.sentiment_unavailable_reason, svc._config)
    svc.monthly_records_service.core_features = lambda session, cid: features_for(cid)
    svc._risk_profile = lambda session, cid: risk_for(cid)
    current: list[str] = []
    svc.get_sentiment_model = lambda: FailingModel() if current and current[0] in FAILING_MODEL else double(MODEL_DOUBLES[current[0]]) if current and current[0] in MODEL_DOUBLES else None
    svc.sentiment_unavailable_reason = lambda: UNAVAILABLE.get(current[0]) if current else None
    svc._config = lambda: (SentimentModelConfig(enabled=True, allow_fallback=not (current and current[0] in NO_FALLBACK), max_tokens=128), True)
    app.dependency_overrides[get_session] = lambda: NoDb()
    try:
        client = TestClient(app)
        out = {}
        for name, (customer_id, body) in SCENARIOS.items():
            current[:] = [name]
            response = client.post(f"/api/profiles/{customer_id}/personalized-insights", json=body)
            assert response.status_code == 200, (name, response.status_code)
            payload = response.json()
            payload["analysis_timestamp"] = FIXED_TIMESTAMP
            out[name] = payload
        return out
    finally:
        app.dependency_overrides.pop(get_session, None)
        svc.monthly_records_service.core_features, svc._risk_profile, svc.get_sentiment_model, svc.sentiment_unavailable_reason, svc._config = original


def render(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    fixtures = generate()
    stale = [name for name, payload in fixtures.items() if not (FIXTURE_DIR / f"{name}.json").is_file() or (FIXTURE_DIR / f"{name}.json").read_bytes().replace(b"\r\n", b"\n") != render(payload).encode("utf-8")]
    if check:
        print("fixtures match the backend" if not stale else f"fixtures differ from the backend: {stale}")
        return 1 if stale else 0
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, payload in fixtures.items():
        (FIXTURE_DIR / f"{name}.json").write_text(render(payload), encoding="utf-8", newline="\n")
    print(f"wrote {len(fixtures)} fixtures to {FIXTURE_DIR.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
