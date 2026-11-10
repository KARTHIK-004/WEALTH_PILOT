"""Anthropic Messages API adapter for ``claude-haiku-5-5``: standard library only, **written and tested offline, NOT registered**.

Authorised by the project owner on 2026-10-19 for writing and fake-transport testing only (decision log, B2-U12). It does
not approve provider use, a network request, data transmission, registration, execution or any gate. ``provider.ADAPTERS`` is
not touched here; ``build`` refuses unless the build lock is lifted and a gate-issued authorisation exists, and the only
transport that can reach the network (``UrllibTransport``) is never created by a test.

What the provider documentation (platform.claude.com, read 2026-10-19) says, and what this module does about it:

- ``POST https://api.anthropic.com/v1/messages`` with ``x-api-key``, ``anthropic-version: 2023-06-01`` and
  ``content-type: application/json``. The URL is a constant and the transport refuses any other host or scheme.
- ``claude-haiku-5-5`` is a fixed model ID (no date suffix, no alias). Claude Haiku 5.5 accepts ``temperature`` only as 1;
  any other value returns HTTP 400. The adapter sends exactly ``1`` and refuses any other approved temperature.
- Thinking is on by default and its tokens count toward ``max_tokens`` (the pipeline's cap is small), so the adapter sends
  ``thinking: {"type": "disabled"}``, which Claude Haiku 5.5 accepts at default effort. No prefill, no tools, no sampling
  parameters other than temperature 1.
- Success: HTTP 200 with ``type: "message"``, ``role: "assistant"``, ``model``, ``content`` (text blocks), ``stop_reason`` and
  ``usage`` (``input_tokens``, ``output_tokens``, optional cache fields). A refusal is HTTP 200 with
  ``stop_reason: "refusal"`` and ``stop_details``; it is never retried. Anything other than ``end_turn`` is unusable.
- Errors: JSON ``{"type": "error", "error": {"type", "message"}, "request_id"}``; 400 ``invalid_request_error`` (also a spend
  limit set by the owner), 401, 402, 403, 404, 413, 429 ``rate_limit_error`` (a tier spend-cap 429 has no ``retry-after`` and
  keeps failing, so it is not retried), 500 ``api_error``, 504 ``timeout_error``, 529 ``overloaded_error``.

Not verified (so the adapter fails safely instead of guessing): the exact text of any error message (never used), whether the
response ever carries a thinking block when thinking is disabled (any non-text block is treated as malformed), and the
real-world rate-limit numbers for the owner's account tier.

**One attempt per ``suggest``.** Retries, back-off, attempt caps and the request, token and cost caps belong to the runner
(``run_suggestions``); this adapter never retries or sleeps, so it cannot loop. It classifies each failure as retryable
(``timeout``, ``rate_limited``, ``server_error``) or not (``refused``, ``auth``, ``bad_request``, ``unknown``), following
``provider.RETRYABLE_KINDS``.

**Secrets.** The key is held only in the instance, sent only in the ``x-api-key`` header, never stored in an exception, a
detail string or ``repr``, and any detail is scrubbed of the key and of key-shaped strings. Error details contain only the
HTTP status, a documented error type and a fixed phrase, never the provider's message and never any request or response text.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from wealthpilot.data import gdelt as pkg
from wealthpilot.data.gdelt.ai.config import ExperimentConfig, RunAuthorization, is_gate_issued
from wealthpilot.data.gdelt.ai.provider import ExecutionBlocked, ProviderError, ProviderResponse, SuggestionRequest

PROVIDER_NAME = "anthropic"
MODEL_ID = "claude-haiku-5-5"
API_URL = "https://api.anthropic.com/v1/messages"
API_HOST = "api.anthropic.com"
API_VERSION = "2023-06-01"
REQUIRED_TEMPERATURE = 1.0
MAX_OUTPUT_TOKENS_CEILING = 2048        # a hard ceiling in the adapter; the configured limit (400) is enforced by the runner
MAX_REQUEST_BYTES = 262_144             # far below the API's 32 MB; a request this large is a bug, not an item
MAX_RESPONSE_BYTES = 1_048_576
REGISTERED = False                      # this module never registers itself; see provider.ADAPTERS

_KEY_SHAPED = re.compile(r"sk-ant-[A-Za-z0-9_\-]{6,}|x-api-key\s*[:=]\s*\S+|Bearer\s+\S+", re.IGNORECASE)
_ERROR_TYPE = re.compile(r"^[a-z_]{1,40}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
_CATEGORIES = frozenset({"cyber", "bio", "frontier_llm", "reasoning_extraction", "general_harms"})
_DETAIL_MAX = 200


# ---------------------------------------------------------------- transport (injected; the default is never created by a test)

@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class TransportTimeout(Exception):
    """The request did not complete in time."""


class TransportFailure(Exception):
    """The request failed before a response (DNS, connection, TLS). ``kind`` is a short class name, never a message."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


class Transport(Protocol):
    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> TransportResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:          # a redirect would resend the key elsewhere
        return None


class UrllibTransport:
    """The only code here that can reach the network. HTTPS to ``api.anthropic.com`` only, no redirects, certificate
    verification on (urllib's default). Tests never construct or call it."""

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> TransportResponse:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or parts.hostname != API_HOST:
            raise TransportFailure("refused_url")
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(request, timeout=timeout) as resp:             # noqa: S310 (scheme and host checked above)
                return TransportResponse(resp.status, dict(resp.headers.items()), resp.read(MAX_RESPONSE_BYTES + 1))
        except urllib.error.HTTPError as exc:
            return TransportResponse(exc.code, dict(exc.headers.items()), exc.read(MAX_RESPONSE_BYTES + 1))
        except TimeoutError as exc:
            raise TransportTimeout() from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TransportTimeout() from exc
            raise TransportFailure(type(exc.reason).__name__) from None
        except OSError as exc:
            raise TransportFailure(type(exc).__name__) from None



# ---------------------------------------------------------------- helpers

def _redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s and len(s) >= 4:
            text = text.replace(s, "[REDACTED]")
    return _KEY_SHAPED.sub("[REDACTED]", text)[:_DETAIL_MAX]


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() == name and isinstance(v, str):
            return v
    return None


class AnthropicProvider:
    """One provider call per ``suggest``. Implements ``provider.SuggestionProvider``. Never registered by this module."""

    name = PROVIDER_NAME

    def __init__(self, api_key: str, *, model_id: str = MODEL_ID, timeout_seconds: float = 60.0,
                 transport: Transport | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        if model_id != MODEL_ID:
            raise ExecutionBlocked(f"this adapter is pinned to {MODEL_ID}; it refuses model {model_id!r}")
        if not isinstance(api_key, str) or len(api_key) < 8 or not api_key.isprintable() or any(c.isspace() for c in api_key):
            raise ExecutionBlocked("the API key is missing or malformed (its value is never shown)")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 600:
            raise ExecutionBlocked("timeout_seconds must be a number above 0 and at most 600")
        self._key = api_key
        self._timeout = float(timeout_seconds)
        self._transport: Transport = transport if transport is not None else UrllibTransport()
        self._clock = clock

    def __repr__(self) -> str:
        return f"AnthropicProvider(model={MODEL_ID!r}, key=<redacted>)"

    # ---- request

    def build_body(self, request: SuggestionRequest) -> bytes:
        """The exact request body. Raises ``ProviderError('bad_request')`` (nothing sent) if the request is not acceptable."""
        if not isinstance(request, SuggestionRequest):
            raise ProviderError("bad_request", "not a SuggestionRequest")
        if request.temperature is None or isinstance(request.temperature, bool) or float(request.temperature) != REQUIRED_TEMPERATURE:
            raise ProviderError("bad_request", "temperature must be exactly 1.0 for claude-haiku-5-5; nothing was sent")
        if not isinstance(request.max_output_tokens, int) or isinstance(request.max_output_tokens, bool) \
                or not 1 <= request.max_output_tokens <= MAX_OUTPUT_TOKENS_CEILING:
            raise ProviderError("bad_request", f"max_output_tokens must be 1 to {MAX_OUTPUT_TOKENS_CEILING}; nothing was sent")
        if not isinstance(request.system, str) or not request.system.strip() or not isinstance(request.user, str) \
                or not request.user.strip():
            raise ProviderError("bad_request", "system and user text are required; nothing was sent")
        payload = {"model": MODEL_ID, "max_tokens": request.max_output_tokens, "temperature": 1,
                   "thinking": {"type": "disabled"}, "system": request.system,
                   "messages": [{"role": "user", "content": request.user}]}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise ProviderError("bad_request", "the request exceeds the adapter's size ceiling; nothing was sent")
        return body

    def build_headers(self) -> dict[str, str]:
        return {"x-api-key": self._key, "anthropic-version": API_VERSION, "content-type": "application/json"}

    # ---- call

    def suggest(self, request: SuggestionRequest) -> ProviderResponse:
        secrets = [self._key]
        try:
            body = self.build_body(request)
            started = self._clock()
            try:
                response = self._transport.post(API_URL, self.build_headers(), body, self._timeout)
            except TransportTimeout:
                raise ProviderError("timeout", "the request timed out") from None
            except TransportFailure as exc:
                raise ProviderError("server_error", _redact(f"transport failure: {exc.kind}", secrets)) from None
            latency_ms = max(0, int((self._clock() - started) * 1000))
            return self._parse(response, latency_ms)
        except ProviderError as exc:
            raise ProviderError(exc.kind, _redact(exc.detail, secrets)) from None
        except Exception as exc:                                              # never let a stray error carry request data
            raise ProviderError("unknown", f"unexpected {type(exc).__name__}") from None

    # ---- response

    def _parse(self, response: TransportResponse, latency_ms: int) -> ProviderResponse:
        if not isinstance(response, TransportResponse) or not _is_count(response.status) or not isinstance(response.body, bytes):
            raise ProviderError("unknown", "the transport returned an invalid response object")
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise ProviderError("unknown", "the response exceeded the size ceiling")
        if response.status != 200:
            raise self._http_error(response)
        try:
            data = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ProviderError("unknown", "HTTP 200 with a body that is not valid JSON") from None
        if not isinstance(data, dict) or data.get("type") != "message" or data.get("role") != "assistant":
            raise ProviderError("unknown", "HTTP 200 but not an assistant message")
        model = data.get("model")
        if not isinstance(model, str) or not model:
            raise ProviderError("unknown", "the response has no model")
        stop = data.get("stop_reason")
        if stop == "refusal":
            details = data.get("stop_details")
            category = details.get("category") if isinstance(details, dict) else None
            raise ProviderError("refused", f"the provider declined to answer (category: "
                                           f"{category if category in _CATEGORIES else 'unspecified'}); never retried")
        if stop != "end_turn":
            raise ProviderError("unknown", f"unusable stop_reason {stop if isinstance(stop, str) and _ERROR_TYPE.match(stop) else 'invalid'}")
        content = data.get("content")
        if not isinstance(content, list) or not content:
            raise ProviderError("unknown", "the response has no content")
        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text" or not isinstance(block.get("text"), str):
                raise ProviderError("unknown", "the response has a content block that is not plain text")
            texts.append(block["text"])
        text = "".join(texts)
        if not text.strip():
            raise ProviderError("unknown", "the response text is empty")
        usage = data.get("usage")
        if not isinstance(usage, dict) or not _is_count(usage.get("input_tokens")) or not _is_count(usage.get("output_tokens")):
            raise ProviderError("unknown", "the response has no valid token usage")
        extra = 0
        for k in ("cache_creation_input_tokens", "cache_read_input_tokens"):
            v = usage.get(k)
            if v is not None and not _is_count(v):
                raise ProviderError("unknown", f"the response has an invalid {k}")
            extra += v or 0
        request_id = _header(response.headers, "request-id")
        if request_id is not None and not _REQUEST_ID.match(request_id):
            request_id = None
        return ProviderResponse(text, model, None, request_id, usage["input_tokens"] + extra, usage["output_tokens"], latency_ms)

    @staticmethod
    def _http_error(response: TransportResponse) -> ProviderError:
        status = response.status
        error_type: str | None = None
        spend_cap = False
        try:
            body = json.loads(response.body.decode("utf-8"))
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict):
                t = err.get("type")
                error_type = t if isinstance(t, str) and _ERROR_TYPE.match(t) else None
                det = err.get("details")
                spend_cap = isinstance(det, dict) and det.get("error_code") == "enforced_spend_limit_reached"
        except (UnicodeDecodeError, ValueError):
            pass
        label = f"HTTP {status}" + (f" {error_type}" if error_type else "")
        if status == 429:
            if spend_cap:
                return ProviderError("bad_request", f"{label}: the monthly spend cap is reached; retrying cannot help")
            return ProviderError("rate_limited", f"{label}: rate limited")
        if status == 504:
            return ProviderError("timeout", f"{label}: the provider timed out")
        if status in (401, 402, 403):
            return ProviderError("auth", f"{label}: authentication, billing or permission problem")
        if status == 400:
            return ProviderError("bad_request", f"{label}: the request was rejected (limit set by you, or invalid)")
        if 500 <= status <= 599:
            return ProviderError("server_error", f"{label}: provider error")
        if 400 <= status <= 499:
            return ProviderError("bad_request", f"{label}: the request was rejected")
        return ProviderError("unknown", f"{label}: unexpected status (redirects are never followed)")


# ---------------------------------------------------------------- the factory (NOT registered)

def build(cfg: ExperimentConfig, auth: RunAuthorization, *, env: Mapping[str, str] | None = None,
          transport: Transport | None = None, clock: Callable[[], float] = time.monotonic) -> AnthropicProvider:
    """Build the provider for a gate-issued authorisation. Refuses unless the build lock is lifted. It reads the key from the
    environment variable NAMED in the config, and only here: this is the first moment the value is touched, and the pipeline
    only gets here in an authorised run. It is not in ``provider.ADAPTERS``; registering it is a separate owner decision."""
    if not pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD:
        raise ExecutionBlocked("build lock: AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False; this adapter cannot be built")
    if not is_gate_issued(auth):
        raise ExecutionBlocked("no gate-issued authorisation")
    if cfg.provider_name != PROVIDER_NAME or cfg.model_id != MODEL_ID:
        raise ExecutionBlocked(f"this adapter serves only provider {PROVIDER_NAME!r} and model {MODEL_ID!r}")
    if cfg.temperature is None or float(cfg.temperature) != REQUIRED_TEMPERATURE:
        raise ExecutionBlocked("the approved temperature must be exactly 1.0 for this model")
    if not cfg.credentials_env_var:
        raise ExecutionBlocked("provider.credentials_env_var is not set")
    source = os.environ if env is None else env
    key = source.get(cfg.credentials_env_var)
    if not key:
        raise ExecutionBlocked(f"environment variable {cfg.credentials_env_var} is not set")
    return AnthropicProvider(key, timeout_seconds=cfg.timeout_seconds, transport=transport, clock=clock)
