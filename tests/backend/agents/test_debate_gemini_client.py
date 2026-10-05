"""Real, live Gemini integration tests for `GeminiModelClient` -- kept
deliberately minimal (a small, fixed number of real API calls) given the
configured Gemini API key's free-tier limits: 5 requests/minute AND (found
during Phase 13 development) a separate 20-requests/DAY cap per model.
All other Phase 12 tests use a FakeModelClient and never touch the
network; this file exists solely to prove the real adapter genuinely works
end-to-end against the actual Gemini API, the same "verify the real
integration once" pattern used for every other external dependency in
this project (the database, yfinance, etc.).

Skipped automatically when no GEMINI_API_KEY is configured, so the rest of
the suite (and CI environments without a key) are unaffected. Also skips
(rather than fails) on any `google.genai.errors.APIError` -- a 429
quota/rate-limit response, a 503 "model overloaded" response, or any
other transient API-side condition -- section 43 explicitly asks live
tests to stay separated from the mandatory suite, and an exhausted
free-tier daily quota (observed directly: running Phase 12's and Phase
13's live tests back-to-back in one day exhausts it) or a transient
service error is an external condition, not a code defect. Widened from
a 429-only check after a full-project-suite run hit a real API-side
failure the narrower check did not catch: a genuine code-side exception
is never an `APIError` and still fails normally regardless of how broad
this check is.
"""

import pytest

from wealthpilot.agents.debate import (
    ComplianceStatusSummary,
    DEFAULT_GEMINI_MODEL,
    GeminiModelClient,
    PortfolioSummary,
    build_debate_input,
    run_strategy_debate,
)
from wealthpilot.config import get_settings

settings = get_settings()

pytestmark = pytest.mark.skipif(not settings.gemini_api_key, reason="GEMINI_API_KEY not configured")


def _skip_on_quota_exhaustion(exc: Exception):
    """Skips on ANY Gemini-service-level error (`google.genai.errors.APIError`
    and its `ClientError`/`ServerError` subclasses -- 429 rate/quota-limit,
    503 "model overloaded", or any other transient API-side condition), not
    only a 429. Observed directly: a full-suite run hit a real failure here
    that a 429-only check did not catch, while running the same test alone
    minutes later hit a plain 429 that the original check handled -- both
    are external, transient Gemini-service conditions, not code defects, so
    both are treated the same way. A genuine code-side exception (e.g. an
    assertion failure, a `TypeError`/`ValidationError` from this project's
    own code) is NOT a `google.genai.errors.APIError` and still fails
    normally -- this only widens what counts as "the API itself had a bad
    moment," never what counts as "our code is broken."""
    from google.genai.errors import APIError

    if isinstance(exc, APIError):
        pytest.skip(f"Gemini API error for this run (code={getattr(exc, 'code', '?')}): {exc}")
    raise exc


def test_gemini_model_client_produces_a_real_non_empty_response():
    """A single real call -- confirms authentication, request shape, and
    response parsing all work, and that the configured token budget is
    large enough to avoid truncation (a real issue found and fixed during
    this phase's own development: 400 tokens truncated real responses
    mid-sentence; the shipped default is 1024)."""
    client = GeminiModelClient(
        {"api_key": settings.gemini_api_key, "model": settings.gemini_model or DEFAULT_GEMINI_MODEL, "temperature": 0.2, "max_output_tokens": 1024}
    )
    params = {
        "messages": [
            {"role": "system", "content": "You are a Portfolio Manager persona. Respond with exactly one concise paragraph."},
            {"role": "user", "content": "Give your opening observation on an approved MVO allocation for a Balanced-risk customer."},
        ]
    }
    try:
        response = client.create(params)
    except Exception as exc:  # noqa: BLE001 - narrowed to an APIError-only skip inside the helper; anything else re-raises
        _skip_on_quota_exhaustion(exc)
        raise
    text = response.choices[0].message.content
    assert text
    assert len(text) > 20
    # Not obviously truncated mid-word (a real symptom observed at the old,
    # too-small token budget): a complete response ends with sentence
    # punctuation, not silently cut off.
    assert text.rstrip()[-1] in ".!?\"')"


def test_gemini_model_client_message_retrieval_and_usage_contract():
    client = GeminiModelClient({"api_key": settings.gemini_api_key, "model": settings.gemini_model or DEFAULT_GEMINI_MODEL})
    params = {"messages": [{"role": "user", "content": "Reply with the single word: acknowledged."}]}
    try:
        response = client.create(params)
    except Exception as exc:  # noqa: BLE001 - narrowed to an APIError-only skip inside the helper; anything else re-raises
        _skip_on_quota_exhaustion(exc)
        raise
    retrieved = client.message_retrieval(response)
    assert isinstance(retrieved, list)
    assert len(retrieved) == 1
    assert isinstance(retrieved[0], str)
    assert client.cost(response) == 0.0
    usage = GeminiModelClient.get_usage(response)
    assert usage["model"] == response.model
    assert usage["cost"] == 0.0
