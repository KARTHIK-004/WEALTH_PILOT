"""POST /api/qa. Mocks `qa_service.answer_question` -- no live Gemini call
in the mandatory suite (matches this project's established "a small
number of separate live tests, everything else fake/deterministic"
pattern from Phase 12/13)."""

from __future__ import annotations

from wealthpilot.api.routers import qa as qa_router
from wealthpilot.api.services.qa_service import QAUnavailableError


def test_ask_question_returns_answer_and_disclaimer(client, monkeypatch):
    monkeypatch.setattr(qa_router, "answer_question", lambda question, context=None: "Diversification means spreading investments across assets.")

    response = client.post("/api/qa", json={"question": "What is diversification?"})
    assert response.status_code == 200
    body = response.json()
    assert "Diversification" in body["answer"]
    assert "educational decision-support prototype" in body["disclaimer"]


def test_ask_question_with_analysis_context(client, make_customer, monkeypatch):
    from tests.backend.api.conftest import approved_steps, patch_graph

    customer = make_customer()
    patch_graph(monkeypatch, approved_steps(customer.id))
    created = client.post("/api/analysis", json={"profile_id": customer.id})
    analysis_id = created.json()["analysis_id"]

    captured = {}

    def _fake_answer(question, context=None):
        captured["context"] = context
        return "General answer."

    monkeypatch.setattr(qa_router, "answer_question", _fake_answer)

    response = client.post("/api/qa", json={"question": "Explain my risk category.", "analysis_id": analysis_id})
    assert response.status_code == 200
    assert captured["context"]["risk_category"] == "Balanced"


def test_ask_question_with_nonexistent_analysis_id_returns_404(client):
    response = client.post("/api/qa", json={"question": "x", "analysis_id": 999999999})
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_ask_question_gemini_unavailable_returns_503(client, monkeypatch):
    def _boom(question, context=None):
        raise QAUnavailableError("Gemini API key not configured")

    monkeypatch.setattr(qa_router, "answer_question", _boom)

    response = client.post("/api/qa", json={"question": "What is a Sharpe ratio?"})
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"


def test_ask_question_rejects_empty_question(client):
    response = client.post("/api/qa", json={"question": ""})
    assert response.status_code == 422
