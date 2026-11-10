"""B2-U13: the Anthropic adapter, tested OFFLINE with a fake transport and SYNTHETIC fixtures only.

No request leaves the machine (the ``_no_network`` fixture in conftest blocks sockets and DNS), no real key, headline, URL or
label is used, and the adapter is never registered outside a test (``monkeypatch`` registers and removes it). Passing these
tests is not permission to execute anything.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import wealthpilot.data.gdelt as pkg
from wealthpilot.data.gdelt.ai import config as aic
from wealthpilot.data.gdelt.ai import provider as aprov
from wealthpilot.data.gdelt.ai import runner, store
from wealthpilot.data.gdelt.ai.adapters import anthropic as ad
from wealthpilot.data.gdelt.ai.provider import ExecutionBlocked, ProviderError, SuggestionRequest

KEY = "sk-ant-api03-SYNTHETIC-CANARY-KEY-0123456789"      # a made-up value; no real key is ever read
SYSTEM = "SYNTHETIC rubric text."
USER = 'Label this item using the rubric. Item fields (JSON):\n{"item_id":"D0001","title":"SYNTHETIC headline"}\n'
REPO = Path(__file__).resolve().parents[4]


def req(**over) -> SuggestionRequest:
    base = dict(item_id="D0001", system=SYSTEM, user=USER, response_schema={}, max_output_tokens=400, temperature=1.0)
    base.update(over)
    return SuggestionRequest(**base)


def message(text='{"ok": true}', *, model=ad.MODEL_ID, stop="end_turn", usage=None, content=None, **extra):
    body = {"id": "msg_SYN", "type": "message", "role": "assistant", "model": model,
            "content": content if content is not None else [{"type": "text", "text": text}],
            "stop_reason": stop, "stop_sequence": None, "stop_details": None,
            "usage": usage if usage is not None else {"input_tokens": 1000, "output_tokens": 50}}
    body.update(extra)
    return body


def ok(body=None, *, headers=None) -> ad.TransportResponse:
    return ad.TransportResponse(200, headers if headers is not None else {"request-id": "req_SYN123"},
                                json.dumps(body if body is not None else message()).encode())


def err(status, error_type=None, *, details=None, headers=None) -> ad.TransportResponse:
    body = {"type": "error", "error": {"type": error_type or "api_error", "message": f"SECRET-ECHO {KEY} synthetic headline"}}
    if details:
        body["error"]["details"] = details
    return ad.TransportResponse(status, headers or {}, json.dumps(body).encode())


class FakeTransport:
    """Scripted responses or exceptions, consumed in order (the last repeats). Records every call."""

    def __init__(self, *script, responder=None):
        self.script, self.responder, self.calls = list(script), responder, []

    def post(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": json.loads(body.decode()), "timeout": timeout})
        if self.responder is not None:
            return self.responder(self.calls[-1])
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, BaseException):
            raise item
        return item


def provider(*script, **kw) -> tuple[ad.AnthropicProvider, FakeTransport]:
    t = FakeTransport(*script, **{k: kw.pop(k) for k in ("responder",) if k in kw})
    return ad.AnthropicProvider(KEY, transport=t, **kw), t


# ================================================================ 1. request schema, headers, pinned model

def test_the_request_is_the_documented_messages_call_with_the_pinned_model():
    p, t = provider(ok())
    p.suggest(req())
    c = t.calls[0]
    assert c["url"] == "https://api.anthropic.com/v1/messages" and c["timeout"] == 60.0
    assert c["headers"] == {"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    assert set(c["body"]) == {"model", "max_tokens", "temperature", "thinking", "system", "messages"}
    assert c["body"]["model"] == "claude-haiku-5-5" == ad.MODEL_ID
    assert c["body"]["system"] == SYSTEM and c["body"]["messages"] == [{"role": "user", "content": USER}]
    assert c["body"]["max_tokens"] == 400


def test_no_prefill_tools_or_other_sampling_parameters_are_sent():
    p, t = provider(ok())
    p.suggest(req())
    body = t.calls[0]["body"]
    assert body["messages"][-1]["role"] == "user" and len(body["messages"]) == 1
    assert not {"tools", "tool_choice", "top_p", "top_k", "stop_sequences", "stream", "output_config"} & set(body)


def test_only_the_pinned_model_can_be_constructed():
    with pytest.raises(ExecutionBlocked, match="pinned"):
        ad.AnthropicProvider(KEY, model_id="claude-sonnet-5-5", transport=FakeTransport(ok()))


# ================================================================ 2. temperature and disabled thinking

def test_temperature_is_exactly_one_and_thinking_is_disabled():
    p, t = provider(ok())
    p.suggest(req())
    assert t.calls[0]["body"]["temperature"] == 1 and t.calls[0]["body"]["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize("temperature", [0.0, 0.5, 1.5, 2.0, None, True])
def test_any_other_temperature_is_refused_and_nothing_is_sent(temperature):
    p, t = provider(ok())
    with pytest.raises(ProviderError) as e:
        p.suggest(req(temperature=temperature))
    assert e.value.kind == "bad_request" and not e.value.retryable and t.calls == []


@pytest.mark.parametrize("bad", [0, -1, 2049, 400.0, True, None])
def test_output_token_limit_must_be_a_sane_integer(bad):
    p, t = provider(ok())
    with pytest.raises(ProviderError) as e:
        p.suggest(req(max_output_tokens=bad))
    assert e.value.kind == "bad_request" and t.calls == []


def test_an_oversized_or_empty_request_is_refused_before_sending():
    p, t = provider(ok())
    for r in (req(user="x" * (ad.MAX_REQUEST_BYTES + 1)), req(system=" "), req(user="")):
        with pytest.raises(ProviderError) as e:
            p.suggest(r)
        assert e.value.kind == "bad_request"
    assert t.calls == []


# ================================================================ 3. success and usage

def test_a_valid_response_is_parsed_with_usage_request_id_and_latency():
    ticks = iter([10.0, 10.25])
    p, _ = provider(ok(message(usage={"input_tokens": 1000, "output_tokens": 50, "cache_creation_input_tokens": 20,
                                       "cache_read_input_tokens": 30})), clock=lambda: next(ticks))
    r = p.suggest(req())
    assert r.text == '{"ok": true}' and r.model_id == "claude-haiku-5-5" and r.model_version is None
    assert (r.input_tokens, r.output_tokens, r.latency_ms, r.request_id) == (1050, 50, 250, "req_SYN123")


def test_request_id_header_is_case_insensitive_and_invalid_ids_are_dropped():
    assert provider(ok(headers={"Request-Id": "req_ABC"}))[0].suggest(req()).request_id == "req_ABC"
    assert provider(ok(headers={"request-id": "bad id\n"}))[0].suggest(req()).request_id is None


def test_several_text_blocks_are_joined_and_exactly_one_call_is_made():
    p, t = provider(ok(message(content=[{"type": "text", "text": "{"}, {"type": "text", "text": '"a":1}'}])))
    assert p.suggest(req()).text == '{"a":1}' and len(t.calls) == 1


# ================================================================ 4. unexpected model, missing fields, malformed JSON

def test_an_unexpected_served_model_is_returned_unchanged_so_the_runner_can_stop():
    r = provider(ok(message(model="claude-something-else")))[0].suggest(req())
    assert r.model_id == "claude-something-else"


@pytest.mark.parametrize("body", [
    message(content=[]), message(content="text"), message(content=[{"type": "text", "text": 5}]),
    message(content=[{"type": "thinking", "thinking": "x", "signature": "s"}]),
    message(content=[{"type": "text", "text": "ok"}, {"type": "tool_use", "id": "t", "name": "n", "input": {}}]),
    message(text="   "), message(model=""), message(model=5), message(usage={}), message(usage={"input_tokens": 1}),
    message(usage={"input_tokens": True, "output_tokens": 1}), message(usage={"input_tokens": -1, "output_tokens": 1}),
    message(usage={"input_tokens": "1", "output_tokens": 1}),
    message(usage={"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": "x"}),
    {**message(), "type": "error"}, {**message(), "role": "user"}, [1, 2], "x", None,
])
def test_a_malformed_successful_response_is_a_non_retryable_failure(body):
    with pytest.raises(ProviderError) as e:
        provider(ad.TransportResponse(200, {}, json.dumps(body).encode()))[0].suggest(req())
    assert e.value.kind == "unknown" and not e.value.retryable


@pytest.mark.parametrize("raw", [b"", b"not json", b"\xff\xfe", b"{", b'{"type": "message"'])
def test_malformed_json_on_http_200_is_a_non_retryable_failure(raw):
    with pytest.raises(ProviderError) as e:
        provider(ad.TransportResponse(200, {}, raw))[0].suggest(req())
    assert e.value.kind == "unknown" and not e.value.retryable


def test_an_invalid_transport_object_or_oversized_body_is_a_failure():
    for bad in ("nope", ad.TransportResponse(200, {}, "str"), ad.TransportResponse(200, {}, b"x" * (ad.MAX_RESPONSE_BYTES + 1))):
        with pytest.raises(ProviderError) as e:
            provider(bad)[0].suggest(req())
        assert e.value.kind == "unknown"


@pytest.mark.parametrize("stop", ["max_tokens", "stop_sequence", "tool_use", "pause_turn", "model_context_window_exceeded", None, 7])
def test_any_stop_reason_other_than_end_turn_is_unusable_and_not_retried(stop):
    with pytest.raises(ProviderError) as e:
        provider(ok(message(stop=stop)))[0].suggest(req())
    assert e.value.kind == "unknown" and not e.value.retryable


# ================================================================ 5. refusal

def test_a_refusal_is_never_retryable_and_leaks_no_explanation():
    body = message(stop="refusal", stop_details={"type": "refusal", "category": "general_harms",
                                                  "explanation": "SECRET-EXPLANATION synthetic headline"})
    with pytest.raises(ProviderError) as e:
        provider(ok(body))[0].suggest(req())
    assert e.value.kind == "refused" and not e.value.retryable
    assert "general_harms" in e.value.detail and "SECRET-EXPLANATION" not in e.value.detail


def test_a_refusal_with_an_unknown_category_is_reported_as_unspecified():
    body = message(stop="refusal", stop_details={"type": "refusal", "category": "<script>"})
    with pytest.raises(ProviderError) as e:
        provider(ok(body))[0].suggest(req())
    assert "unspecified" in e.value.detail and "<script>" not in e.value.detail


# ================================================================ 6. HTTP errors

@pytest.mark.parametrize("status,error_type,kind,retryable", [
    (400, "invalid_request_error", "bad_request", False), (401, "authentication_error", "auth", False),
    (402, "billing_error", "auth", False), (403, "permission_error", "auth", False),
    (404, "not_found_error", "bad_request", False), (409, "conflict_error", "bad_request", False),
    (413, "request_too_large", "bad_request", False), (429, "rate_limit_error", "rate_limited", True),
    (500, "api_error", "server_error", True), (504, "timeout_error", "timeout", True),
    (529, "overloaded_error", "server_error", True), (503, None, "server_error", True), (418, None, "bad_request", False),
    (302, None, "unknown", False)])
def test_http_errors_map_to_the_projects_retry_classes(status, error_type, kind, retryable):
    with pytest.raises(ProviderError) as e:
        provider(err(status, error_type))[0].suggest(req())
    assert e.value.kind == kind and e.value.retryable is retryable and f"HTTP {status}" in e.value.detail


def test_a_spend_cap_429_is_not_retried_but_an_ordinary_429_is():
    with pytest.raises(ProviderError) as e:
        provider(err(429, "rate_limit_error", details={"error_code": "enforced_spend_limit_reached"}))[0].suggest(req())
    assert e.value.kind == "bad_request" and not e.value.retryable and "spend cap" in e.value.detail


def test_an_error_body_that_is_not_json_still_maps_by_status():
    with pytest.raises(ProviderError) as e:
        provider(ad.TransportResponse(500, {}, b"<html>oops</html>"))[0].suggest(req())
    assert e.value.kind == "server_error" and e.value.retryable


def test_the_provider_message_is_never_copied_into_an_error():
    for status in (400, 401, 429, 500):
        with pytest.raises(ProviderError) as e:
            provider(err(status))[0].suggest(req())
        assert "SECRET-ECHO" not in e.value.detail and "synthetic headline" not in e.value.detail and KEY not in e.value.detail


# ================================================================ 7. timeout, one attempt, bounded retries and back-off

def test_a_timeout_and_a_transport_failure_are_retryable_and_make_one_call_each():
    p, t = provider(ad.TransportTimeout())
    with pytest.raises(ProviderError) as e:
        p.suggest(req())
    assert e.value.kind == "timeout" and e.value.retryable and len(t.calls) == 1
    p, t = provider(ad.TransportFailure("ConnectionResetError"))
    with pytest.raises(ProviderError) as e:
        p.suggest(req())
    assert e.value.kind == "server_error" and e.value.retryable and len(t.calls) == 1


def test_the_adapter_never_retries_or_sleeps_by_itself():
    p, t = provider(err(500, "api_error"))
    for _ in range(3):
        with pytest.raises(ProviderError):
            p.suggest(req())
    assert len(t.calls) == 3                                           # exactly one transport call per suggest


def test_an_unexpected_exception_is_wrapped_without_carrying_request_data():
    class Boom(Exception):
        pass
    p, _ = provider(Boom(f"leak {KEY} synthetic headline"))
    with pytest.raises(ProviderError) as e:
        p.suggest(req())
    assert e.value.kind == "unknown" and e.value.detail == "unexpected Boom" and e.value.__cause__ is None
    assert KEY not in str(e.value) and "headline" not in str(e.value)


# ---- the runner owns retries, back-off and the caps; these run the real runner against the fake transport (lock lifted in
# ---- the test only, the adapter registered by monkeypatch and removed afterwards)

T0 = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now, self.sleeps = T0, []

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)


def world(env, monkeypatch, transport, *, limits=None):
    """A synthetic experiment configured for the adapter; the lock lifted and the adapter registered ONLY inside this test."""
    import wealthpilot.data.gdelt.ai.provider as p
    monkeypatch.setattr(pkg, "AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD", True)
    monkeypatch.setitem(p.ADAPTERS, "anthropic", lambda cfg, auth: ad.build(cfg, auth, env=env.process_env, transport=transport))
    d = env.cfg_dict()
    d["provider"].update(name="anthropic", model_id=ad.MODEL_ID, model_version="fixed-snapshot-claude-haiku-5-5", temperature=1.0)
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    d["limits"].update(limits or {})
    env.write_cfg(env.approved(d))
    cfg = env.load()
    store.init_experiment(cfg)
    auth = env.authorize(cfg)
    return cfg, auth, aprov.build_provider(cfg.provider_name, cfg, auth)


def good_responder(env):
    def respond(call):
        user = call["body"]["messages"][0]["content"]
        item_id = json.loads(user.split("\n", 1)[1])["item_id"]
        return ok(message(text=env.good(item_id)))
    return respond


def run_it(env, cfg, auth, prov):
    c = Clock()
    res = runner.run_suggestions(cfg, auth, prov, clock=c, sleep=c.sleep, env=env.process_env)
    return res, c


def test_bounded_retries_and_backoff_through_the_real_runner(make_ai_env, monkeypatch):
    env = make_ai_env(n=3, overlap=("D0002",))
    t = FakeTransport(err(500, "api_error"))                            # every call fails with a retryable error
    cfg, auth, prov = world(env, monkeypatch, t)
    res, clock = run_it(env, cfg, auth, prov)
    eligible = len(set(env.ids) - env.overlap)
    assert len(t.calls) == eligible * cfg.limits.max_attempts_per_item == eligible * 3        # 3 attempts per item, no more
    assert clock.sleeps == list(cfg.limits.backoff_seconds[:2]) * eligible and res.counts["failed"] == eligible   # bounded back-off


def test_non_retryable_failures_are_attempted_once_per_item(make_ai_env, monkeypatch):
    refusal = ok(message(stop="refusal", stop_details={"type": "refusal", "category": "cyber"}))
    for script in (refusal, err(401, "authentication_error"), err(400, "invalid_request_error"), ok(message(text=" "))):
        t = FakeTransport(script)
        env = make_ai_env(n=3, overlap=("D0002",))
        cfg, auth, prov = world(env, monkeypatch, t)
        run_it(env, cfg, auth, prov)
        assert len(t.calls) == len(set(env.ids) - env.overlap)             # one call per eligible item, never a retry


def test_the_unexpected_model_stops_the_run_through_the_runner(make_ai_env, monkeypatch):
    env = make_ai_env(n=3, overlap=("D0002",))
    t = FakeTransport(ok(message(model="claude-other")))
    cfg, auth, prov = world(env, monkeypatch, t)
    with pytest.raises(ExecutionBlocked, match="other than the approved"):
        run_it(env, cfg, auth, prov)
    assert len(t.calls) == 1


def test_a_good_run_stores_a_valid_suggestion_and_sends_only_the_eligible_items(make_ai_env, monkeypatch):
    env = make_ai_env(n=4, overlap=("D0002",))
    t = FakeTransport(responder=good_responder(env))
    cfg, auth, prov = world(env, monkeypatch, t)
    res, _ = run_it(env, cfg, auth, prov)
    sent = sorted(json.loads(c["body"]["messages"][0]["content"].split("\n", 1)[1])["item_id"] for c in t.calls)
    assert sent == sorted(set(env.ids) - env.overlap) and res.counts["valid"] == 3
    assert all(c["body"]["temperature"] == 1 and c["body"]["thinking"] == {"type": "disabled"} for c in t.calls)


# ================================================================ 8. input, output and cost limits

def test_request_input_and_cost_caps_are_enforced_by_the_runner_using_the_adapters_usage(make_ai_env, monkeypatch):
    env = make_ai_env(n=5, overlap=("D0002",))
    t = FakeTransport(responder=good_responder(env))
    cfg, auth, prov = world(env, monkeypatch, t, limits={"max_requests": 2})
    res, _ = run_it(env, cfg, auth, prov)
    assert len(t.calls) == 2 and res.stop_reason and "request cap" in res.stop_reason
    env = make_ai_env(n=5, overlap=("D0002",))
    t = FakeTransport(responder=good_responder(env))
    cfg, auth, prov = world(env, monkeypatch, t, limits={"max_input_tokens": 1})
    res, _ = run_it(env, cfg, auth, prov)
    assert len(t.calls) == 0 and "input-token cap" in res.stop_reason
    env = make_ai_env(n=5, overlap=("D0002",))
    t = FakeTransport(responder=good_responder(env))
    cfg, auth, prov = world(env, monkeypatch, t, limits={"max_cost": 0.0003, "currency": "USD", "unit_price_input_per_1k": 0.0001,
                                                         "unit_price_output_per_1k": 0.0005})
    res, _ = run_it(env, cfg, auth, prov)
    assert len(t.calls) <= 1 and "cost cap" in res.stop_reason


def test_the_output_token_limit_reaches_the_request_exactly(make_ai_env, monkeypatch):
    env = make_ai_env(n=3, overlap=("D0002",))
    t = FakeTransport(responder=good_responder(env))
    cfg, auth, prov = world(env, monkeypatch, t, limits={"max_output_tokens_per_request": 321})
    run_it(env, cfg, auth, prov)
    assert {c["body"]["max_tokens"] for c in t.calls} == {321}


# ================================================================ 9. secret redaction

def test_the_key_never_appears_in_a_repr_an_exception_or_an_error_detail():
    p, _ = provider(ad.TransportFailure(f"x{KEY}x"))
    assert KEY not in repr(p) and "<redacted>" in repr(p)
    with pytest.raises(ProviderError) as e:
        p.suggest(req())
    assert KEY not in str(e.value) and KEY not in e.value.detail and "[REDACTED]" in e.value.detail


def test_key_shaped_strings_are_scrubbed_even_when_they_are_not_the_configured_key():
    out = ad._redact("a sk-ant-api03-OTHERKEY123456 b x-api-key: abcdef Bearer tok123", [KEY])
    assert "OTHERKEY" not in out and "abcdef" not in out and "tok123" not in out and out.count("[REDACTED]") == 3


def test_a_malformed_key_is_refused_without_showing_it():
    for bad in ("", "short", "has space in it", "new\nline-key-value", None, 5):
        with pytest.raises(ExecutionBlocked) as e:
            ad.AnthropicProvider(bad, transport=FakeTransport(ok()))
        assert str(bad) not in str(e.value) or str(bad) in ("", "None", "5")


def test_the_key_stays_out_of_every_stored_record_and_audit_event(make_ai_env, monkeypatch):
    env = make_ai_env(n=3, overlap=("D0002",))
    t = FakeTransport(err(500, "api_error"))
    cfg, auth, prov = world(env, monkeypatch, t)
    run_it(env, cfg, auth, prov)
    layout = store.Layout(env.dest)
    blob = b"".join(f.read_bytes() for f in env.dest.rglob("*") if f.is_file())
    assert env.secret.encode() not in blob and KEY.encode() not in blob and b"SECRET-ECHO" not in blob
    assert layout.suggestions_raw.exists()


# ================================================================ 10. no network

def test_the_default_transport_refuses_any_other_host_or_scheme_without_a_socket():
    t = ad.UrllibTransport()
    for url in ("http://api.anthropic.com/v1/messages", "https://example.com/v1/messages", "ftp://api.anthropic.com/x"):
        with pytest.raises(ad.TransportFailure) as e:
            t.post(url, {}, b"{}", 1.0)
        assert e.value.kind == "refused_url"


def test_an_injected_transport_is_used_and_no_default_transport_is_created():
    t = FakeTransport(ok())
    assert ad.AnthropicProvider(KEY, transport=t)._transport is t


def test_the_redirect_handler_never_follows_a_redirect():
    assert ad._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.example/") is None


def test_the_adapter_source_has_no_other_network_code_and_no_secret_reading_beyond_the_named_variable():
    text = (REPO / "backend/wealthpilot/data/gdelt/ai/adapters/anthropic.py").read_text(encoding="utf-8")
    assert "requests" not in text.replace("requests per", "") and "httpx" not in text and "socket" not in text
    assert text.count("os.environ") == 1 and "dotenv" not in text and not re.search(r"\.env\b", text) and "open(" not in text.replace("opener.open(", "")


# ================================================================ 11. unregistered and disabled

def test_the_adapter_is_not_registered_and_the_build_lock_is_false():
    assert dict(aprov.ADAPTERS) == {} and "anthropic" not in aprov.ADAPTERS
    assert ad.REGISTERED is False and pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False
    for module in ("backend/wealthpilot/data/gdelt/ai/adapters/__init__.py", "backend/wealthpilot/data/gdelt/ai/adapters/anthropic.py"):
        text = (REPO / module).read_text(encoding="utf-8")
        assert "ADAPTERS[" not in text and "setitem(" not in text and "ADAPTERS.update" not in text


def test_build_refuses_while_the_lock_is_false_and_without_a_gate_issued_authorisation(make_ai_env, monkeypatch):
    env = make_ai_env(n=3)
    d = env.cfg_dict()
    d["provider"].update(name="anthropic", model_id=ad.MODEL_ID, temperature=1.0)
    env.write_cfg(d)
    cfg = env.load()
    with pytest.raises(ExecutionBlocked, match="build lock"):
        ad.build(cfg, object(), env=env.process_env, transport=FakeTransport(ok()))
    monkeypatch.setattr(pkg, "AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD", True)
    with pytest.raises(ExecutionBlocked, match="gate-issued"):
        ad.build(cfg, aic.RunAuthorization("e", "r", {}), env=env.process_env, transport=FakeTransport(ok()))


def test_build_refuses_a_wrong_provider_model_temperature_or_missing_key(make_ai_env, monkeypatch):
    env = make_ai_env(n=3, overlap=("D0002",))
    monkeypatch.setattr(pkg, "AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD", True)
    monkeypatch.setitem(aprov.ADAPTERS, "anthropic", lambda cfg, auth: None)
    d = env.cfg_dict()
    d["provider"].update(name="anthropic", model_id=ad.MODEL_ID, temperature=1.0)
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    env.write_cfg(env.approved(d))
    cfg = env.load()
    auth = env.authorize(cfg)
    for bad_env, message_part in (({}, "is not set"),):
        with pytest.raises(ExecutionBlocked, match=message_part) as e:
            ad.build(cfg, auth, env=bad_env, transport=FakeTransport(ok()))
        assert env.secret not in str(e.value)
    import dataclasses
    for change, part in ((dict(model_id="claude-sonnet-5-5"), "serves only"), (dict(provider_name="other"), "serves only"),
                         (dict(temperature=0.0), "exactly 1.0"), (dict(temperature=None), "exactly 1.0"),
                         (dict(credentials_env_var=None), "credentials_env_var")):
        with pytest.raises(ExecutionBlocked, match=part):
            ad.build(dataclasses.replace(cfg, **change), auth, env=env.process_env, transport=FakeTransport(ok()))


# ================================================================ 12. no approvals, no records, the draft stays unapproved

def test_the_draft_config_is_unapproved_and_consistent_with_the_adapter():
    cfg = aic.load_experiment(REPO / "config/gdelt/b2t_haiku55_DRAFT_UNAPPROVED.yaml")
    assert cfg.approvals == {} and cfg.provider_data_terms_reviewed is False and cfg.retention_days is None
    assert cfg.run_id is None and cfg.overlap_labels_sha256 is None
    assert (cfg.provider_name, cfg.model_id, cfg.temperature) == (ad.PROVIDER_NAME, ad.MODEL_ID, ad.REQUIRED_TEMPERATURE)
    assert cfg.provider_exclusion == "overlap_and_blind" and cfg.blind_item_ids == ()
    assert not cfg.destination.exists()


def test_the_adapter_work_created_no_gate_record_experiment_folder_or_freeze():
    review = REPO / "datasets/raw/gdelt/english_gkg_v1/review"
    assert sorted(p.name for p in review.iterdir()) == ["b2i_review_v1"]
    assert not list((review / "b2i_review_v1" / "review_files").glob("freeze_record.json"))
    assert sorted(p.name for p in (REPO / "config/gdelt").iterdir()) == ["b2t_haiku55_DRAFT_UNAPPROVED.yaml"]
    text = (REPO / "config/gdelt/b2t_haiku55_DRAFT_UNAPPROVED.yaml").read_text(encoding="utf-8")
    assert "approved: true" not in text and "approvals: {A: null, B: null, C: null, D: null}" in text
