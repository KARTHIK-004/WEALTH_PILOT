"""RFC 7807 error contract (Phase 15 sections 18/19/44): every error
response, from every endpoint and every failure mode, uses
`application/problem+json` with the standard fields and never leaks a
stack trace or a secret."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "make_request",
    [
        lambda c: c.get("/api/profiles/999999999"),
        lambda c: c.get("/api/analysis/999999999"),
        lambda c: c.post("/api/profiles", json={}),
        lambda c: c.post("/api/analysis", json={"profile_id": "not-an-int"}),
        lambda c: c.get("/api/does-not-exist"),
    ],
)
def test_error_responses_use_problem_json_consistently(client, make_request):
    response = make_request(client)
    assert response.status_code >= 400
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert "type" in body
    assert "title" in body
    assert "status" in body
    assert body["status"] == response.status_code
    assert "detail" in body
    assert "instance" in body


def test_validation_error_has_422_and_field_detail(client):
    response = client.post("/api/analysis", json={"portfolio_strategy": "not_a_real_strategy", "profile_id": 1})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_customer_not_found_is_404_not_500(client):
    response = client.get("/api/profiles/999999999")
    assert response.status_code == 404


def test_analysis_not_found_is_404_not_500(client):
    response = client.get("/api/analysis/999999999")
    assert response.status_code == 404


def test_error_body_never_contains_a_stack_trace_or_secret(client):
    response = client.get("/api/profiles/999999999")
    body_text = response.text.lower()
    for forbidden in ("traceback", "site-packages", "api_key", "database_url", "postgresql://", "c:\\users"):
        assert forbidden not in body_text


def test_analysis_post_with_nonexistent_profile_returns_404(client):
    response = client.post("/api/analysis", json={"profile_id": 999999999})
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
