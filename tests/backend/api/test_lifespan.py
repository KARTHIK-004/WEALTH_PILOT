"""Phase 15 sections 15/16/43: model artifacts load once at startup, never
per request, and a missing/corrupted artifact fails startup clearly."""

from __future__ import annotations

import joblib
import pytest
from fastapi.testclient import TestClient

from wealthpilot.agents import nodes as N
from wealthpilot.api.lifespan import warm_model_caches
from wealthpilot.api.main import app


def test_application_starts():
    with TestClient(app) as started_client:
        response = started_client.get("/api/health")
        assert response.status_code == 200


def test_model_artifacts_are_not_reloaded_per_request(monkeypatch):
    """`joblib.load` must be called at most once per artifact across many
    requests -- proven by clearing the lru_caches, counting real
    `joblib.load` calls during startup warming, then issuing several
    requests and asserting the count does not increase."""
    N._risk_artifacts_cached.cache_clear()
    N._behaviour_artifacts_cached.cache_clear()
    N._far_trans_tables_cached.cache_clear()

    calls = {"n": 0}
    real_load = joblib.load

    def _counting_load(*args, **kwargs):
        calls["n"] += 1
        return real_load(*args, **kwargs)

    monkeypatch.setattr(N.joblib, "load", _counting_load)

    warm_model_caches()
    after_warm = calls["n"]
    assert after_warm > 0  # risk preprocessor + risk classifier + behaviour iforest

    # Simulate several "requests" needing the cached artifacts again.
    for _ in range(5):
        N._risk_artifacts_cached()
        N._behaviour_artifacts_cached()
        N._far_trans_tables_cached()

    assert calls["n"] == after_warm  # no additional joblib.load calls


def test_missing_artifact_fails_startup_clearly(monkeypatch, tmp_path):
    """Section 16: a missing required artifact must fail the application
    startup, not silently retrain, substitute another model, or fabricate
    output."""
    N._risk_artifacts_cached.cache_clear()
    monkeypatch.setattr(N, "RISK_MODELS_DIR", tmp_path / "does_not_exist")

    with pytest.raises(FileNotFoundError):
        warm_model_caches()

    # Restore the real cache for any test that runs after this one.
    N._risk_artifacts_cached.cache_clear()
