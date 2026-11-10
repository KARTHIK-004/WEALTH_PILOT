"""Export REAL responses of the fictional demo route `POST /api/demo/financial-behaviour` as fixtures for the frontend component tests (frontend/tests/fixtures/demo/*.json).

    python scripts/export_demo_fixtures.py            # (re)write the fixtures
    python scripts/export_demo_fixtures.py --check    # exit 1 if the saved fixtures differ from what the backend returns now

The responses come from the actual route, schemas and core functions (the demo flag is switched on in-process, the database session is replaced by a stub that fails on any use, nothing
touches the network). The months and the sentence are FICTIONAL. Only `analysis_timestamp` is fixed so the files are deterministic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

FIXTURE_DIR = REPO / "frontend" / "tests" / "fixtures" / "demo"
FIXED_TIMESTAMP = "2026-01-01T00:00:00Z"
EXAMPLE = "I feel more confident about saving this month, but I am still watching my expenses."
SCENARIOS: dict[str, str | None] = {
    "demo-records-only": None,
    "demo-example-text": EXAMPLE,
    "demo-quoted": 'My friend said "I hate my debt" yesterday.',
    "demo-third-person": "My brother is terrified about his mortgage.",
    "demo-hypothetical": "If I lost my job I would panic about my savings.",
    "demo-unrelated": "The weather is lovely and the football was great.",
}
FAMILY_SCENARIOS: dict[str, str | None] = {"family-records-only": None, "family-example-text": EXAMPLE, "family-quoted": 'My friend said "I hate my debt" yesterday.'}


def produce() -> dict[str, str]:
    from fastapi.testclient import TestClient

    from wealthpilot.api.dependencies import get_session
    from wealthpilot.api.main import app
    from wealthpilot.config import get_settings
    from wealthpilot.core import sentiment_model as sentiment_model_module

    # `sentiment_model.dependencies_available` reports whether torch / transformers import ON THIS MACHINE. It is pinned to False while the fixtures are produced (and restored afterwards), so the
    # saved responses, and the test that compares them with the route, do not change from machine to machine.
    real_dependencies_available = sentiment_model_module.dependencies_available
    sentiment_model_module.dependencies_available = lambda: False

    class NoDb:
        def __getattr__(self, name):
            raise AssertionError(f"the demo route used the database session ({name})")

    settings = get_settings()
    previous = settings.demo_mode_enabled
    settings.demo_mode_enabled = True
    app.dependency_overrides[get_session] = lambda: NoDb()
    try:
        client = TestClient(app)
        out = {}
        for name, text in SCENARIOS.items():
            response = client.post("/api/demo/financial-behaviour", json={"text": text})
            assert response.status_code == 200, (name, response.status_code)
            body = response.json()
            body["insight"]["analysis_timestamp"] = FIXED_TIMESTAMP
            out[name] = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
        for name, text in FAMILY_SCENARIOS.items():
            response = client.post("/api/demo/family-financial-behaviour", json={"text": text})
            assert response.status_code == 200, (name, response.status_code)
            body = response.json()
            for member in body["members"]:
                member["insight"]["analysis_timestamp"] = FIXED_TIMESTAMP
            out[name] = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
        return out
    finally:
        settings.demo_mode_enabled = previous
        sentiment_model_module.dependencies_available = real_dependencies_available
        app.dependency_overrides.pop(get_session, None)


def main() -> int:
    produced = produce()
    if "--check" in sys.argv:
        drift = [n for n, text in produced.items() if not (FIXTURE_DIR / f"{n}.json").exists() or (FIXTURE_DIR / f"{n}.json").read_text(encoding="utf-8").replace("\r\n", "\n") != text]
        print("fixtures match the backend" if not drift else f"DRIFT: {', '.join(drift)}")
        return 1 if drift else 0
    for name, text in produced.items():
        (FIXTURE_DIR / f"{name}.json").write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(produced)} fixtures to {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
