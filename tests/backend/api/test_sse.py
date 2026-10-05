"""GET /api/analysis/stream (Phase 15 sections 21-26, 45)."""

from __future__ import annotations

import json

from tests.backend.api.conftest import approved_steps, patch_graph, rejected_steps

_FORBIDDEN_SUBSTRINGS = (
    "chain-of-thought", "chain_of_thought", "system_instruction", "you are a portfolio manager persona",
    "prompt", "reasoning", "autogen", "debate", "transcript", "traceback", "api_key",
)


def _parse_events(body_text: str) -> list[dict]:
    events = []
    for block in body_text.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        data_line = next((line[len("data: "):] for line in lines if line.startswith("data: ")), None)
        if data_line:
            events.append(json.loads(data_line))
    return events


def test_stream_emits_safe_node_progress_for_an_approved_run(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    response = client.get(f"/api/analysis/stream?profile_id={customer.id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_events(response.text)
    nodes = [e["node"] for e in events]

    assert nodes[0] == "analysis_started"
    assert nodes[-1] == "analysis_completed"
    assert events[-1]["status"] == "approved"
    assert "recommendation" in nodes
    assert "explanation" in nodes
    for expected in ("customer_analyzer", "risk_analyst", "compliance_analyst"):
        assert expected in nodes


def test_stream_contains_no_prohibited_internal_content(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    response = client.get(f"/api/analysis/stream?profile_id={customer.id}")
    body_lower = response.text.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in body_lower


def test_stream_stops_after_reject_no_downstream_recommendation_or_explanation(client, make_customer, monkeypatch):
    """CRITICAL (section 24/45): the stream must respect the Phase 11
    terminal REJECT — no `recommendation`/`explanation` node-progress
    event may appear after it."""
    customer = make_customer()
    patch_graph(monkeypatch, rejected_steps(customer.id))

    response = client.get(f"/api/analysis/stream?profile_id={customer.id}")
    events = _parse_events(response.text)
    nodes = [e["node"] for e in events]

    assert "recommendation" not in nodes
    assert "explanation" not in nodes
    assert nodes[-1] == "analysis_completed"
    assert events[-1]["status"] == "rejected"


def test_stream_events_have_the_documented_shape(client, make_customer, monkeypatch):
    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))

    response = client.get(f"/api/analysis/stream?profile_id={customer.id}")
    for event in _parse_events(response.text):
        assert set(event.keys()) == {"node", "status", "duration_ms", "summary", "model_version"}
