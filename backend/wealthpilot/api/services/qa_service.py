"""Phase 15 — POST /api/qa: general financial-education Q&A via Gemini.

Reuses the SAME `google-genai` client/credentials Phase 12/13 already
established (`settings.gemini_api_key`/`settings.gemini_model`) — a new,
narrowly-scoped system prompt for a genuinely new purpose (answering a
customer's own general question), not a methodology change to any
existing phase's file (`agents/debate.py`/`agents/explanation.py` are
untouched). Gemini is never given decision authority here (section 29):
the system prompt explicitly forbids restating/recomputing a specific
number for the asking customer, recommending a strategy, or overriding a
compliance outcome — and nothing in this module parses the answer for a
decision, since none is ever extracted from it; the response is prose,
returned as-is.
"""

from __future__ import annotations

import concurrent.futures

from wealthpilot.agents.explanation import CANONICAL_DISCLAIMER
from wealthpilot.config import get_settings

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_OUTPUT_TOKENS = 1024
DEFAULT_TIMEOUT_SECONDS = 30.0

SYSTEM_INSTRUCTION = f"""You are a general financial-education assistant for an
educational decision-support prototype. You are NOT a financial advisor
and this is NOT licensed financial advice.

Rules:
1. Answer only general financial-literacy/education questions (e.g. what
   is diversification, what is a Sharpe ratio, what does "risk tolerance"
   mean).
2. Never state a specific number, recommendation, or compliance outcome
   for the asking customer. If optional context about their own analysis
   is supplied below, refer to it only in general terms (e.g. "your risk
   category" without restating or recomputing any figure) — never
   contradict it.
3. Never recommend a specific strategy, fund, or allocation.
4. Never guarantee a return or outcome.
5. Keep answers concise and educational.

{CANONICAL_DISCLAIMER}"""


class QAUnavailableError(Exception):
    """Raised when Gemini is not configured or the call fails/times out —
    mapped to HTTP 503 by the router (section 20: "missing model/service
    -> 503"), never a fabricated answer."""


def answer_question(question: str, context: dict | None = None, api_key: str | None = None, model: str | None = None) -> str:
    settings = get_settings()
    api_key = api_key or settings.gemini_api_key
    model = model or settings.gemini_model or DEFAULT_MODEL
    if not api_key:
        raise QAUnavailableError("Gemini API key not configured")

    from google import genai
    from google.genai import types

    prompt = f"Customer question: {question}"
    if context:
        prompt += f"\n\n(Optional general context only -- do not restate or recompute any figure below: {context})"

    def _run() -> str:
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=DEFAULT_TEMPERATURE,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        )
        response = client.models.generate_content(
            model=model, contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])], config=config
        )
        text = response.text
        if not text:
            raise QAUnavailableError("Gemini returned an empty response")
        return text

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run)
    try:
        result = future.result(timeout=DEFAULT_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError as exc:
        executor.shutdown(wait=False)
        raise QAUnavailableError(f"Gemini call exceeded {DEFAULT_TIMEOUT_SECONDS}s") from exc
    except QAUnavailableError:
        executor.shutdown(wait=False)
        raise
    except Exception as exc:  # noqa: BLE001 - any Gemini/network failure becomes a structured 503, never an unhandled crash
        executor.shutdown(wait=False)
        raise QAUnavailableError(str(exc)) from exc
    executor.shutdown(wait=False)
    return result
