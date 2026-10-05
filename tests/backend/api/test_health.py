"""Phase 0 completion criterion: GET /api/health returns 200. Phase 15
extends this with the `model_versions` shape (BUILD_PLAN.md section 12)
without removing anything Phase 0 already asserted."""

from fastapi.testclient import TestClient

from wealthpilot.api.main import app

client = TestClient(app)


def test_health_returns_200_with_expected_shape():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "WealthPilot AI"
    assert "version" in body


def test_cors_allows_vite_dev_origin():
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_health_reports_loaded_model_versions():
    with TestClient(app) as started_client:
        response = started_client.get("/api/health")

    assert response.status_code == 200
    versions = response.json()["model_versions"]
    assert versions["risk"] == "v1"
    assert versions["behaviour"] == "v1"
    assert versions["market"] == "v1"
    assert versions["portfolio"] == "v1"
    assert versions["compliance_rules"] == "v1"


def test_health_never_exposes_secrets_or_internal_paths():
    response = client.get("/api/health")
    body_text = response.text.lower()
    for forbidden in ("api_key", "gemini_api_key", "database_url", "postgresql://", "c:\\users", "/home/"):
        assert forbidden not in body_text
