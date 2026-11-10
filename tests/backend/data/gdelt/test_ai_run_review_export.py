"""AI-assisted annotation pipeline (built, DISABLED): the gated suggestion run (driven only by a scripted fake provider
with the build lock lifted INSIDE the test), resume, retries, caps, provenance, review queue, human review rules,
interactive reviewer and export. SYNTHETIC; offline; the shipped build is never enabled."""

from __future__ import annotations

import ast
import csv
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import wealthpilot.data.gdelt as gdelt_pkg
from wealthpilot.data.gdelt.ai import chain, export, prompt, provider, queue, reviewer, runner, store
from wealthpilot.data.gdelt.ai.provider import ProviderError

T0 = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
BASE_LABELS = {"rel_equity": "I", "rel_rates": "R", "rel_gold": "I", "amb_code": "", "company_notice": "N",
               "pol_equity": "", "pol_rates": "NEG", "pol_gold": ""}


class Clock:
    def __init__(self):
        self.now, self.sleeps = T0, []

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)


def prepare(env, monkeypatch, *, limits=None):
    """init + approvals + authorization, with the build lock lifted for THIS test only."""
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["limits"].update(limits or {})
    env.write_cfg(env.approved(d))
    cfg = env.load()
    store.init_experiment(cfg)
    return cfg, env.authorize(cfg), store.Layout(env.dest)


def run(env, cfg, auth, prov, clock=None, **kw):
    clock = clock or Clock()
    return runner.run_suggestions(cfg, auth, prov, clock=clock, sleep=clock.sleep, env=env.process_env, **kw)


def provider_for(env, scripted, **script):
    return scripted(script, default=lambda req: env.good(req.item_id))


def tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- the run

def test_happy_path_records_provenance_and_leaves_the_originals_untouched(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    before = tree(env.rf)
    prov = provider_for(env, scripted)
    res = run(env, cfg, auth, prov)
    assert res.outcome == "completed" and res.counts == {"valid": 6, "invalid": 0, "failed": 0, "pending": 0}
    assert res.requests_used == 6 == len(prov.calls)
    assert tree(env.rf) == before                                              # the original experiment is untouched
    recs = store.SuggestionStore(layout).records()
    r = recs[0]
    for key in ("run_id", "item_id", "input_fingerprint", "attempt", "prompt_version", "prompt_sha256", "rubric_version",
                "rubric_sha256", "params", "provider", "tokens", "latency_ms", "raw_response", "raw_response_sha256",
                "parsed", "validation", "started_at_utc", "finished_at_utc", "terminal_status", "prev_sha256",
                "record_sha256"):
        assert key in r, key
    assert r["run_id"] == "run-test-1" and r["provider"]["model_id"] == "fake-model-1"
    assert r["raw_response"] == env.good("D0001")                                # stored verbatim
    assert r["raw_response_sha256"] == hashlib.sha256(r["raw_response"].encode("utf-8")).hexdigest()
    assert r["input_fingerprint"] == {i.item_id: i.fingerprint for i in env.source_items()}["D0001"]


def test_requests_contain_only_approved_fields_and_never_the_secret(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(dup=("D0006",))
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted)
    run(env, cfg, auth, prov)
    for req in prov.calls:
        payload = json.loads(req.user.split("(JSON):\n", 1)[1].splitlines()[0])
        assert set(payload) == {"item_id", "batch_date_utc", "source_domain", "url", "title"}
        assert "EXACT_DUP" not in req.user and "overlap" not in req.user
    for p in layout.root.rglob("*"):
        if p.is_file():
            assert env.secret.encode() not in p.read_bytes(), p.name


def test_the_derived_valid_csv_is_ai_typed_and_every_review_is_still_empty(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, provider_for(env, scripted))
    rows = list(csv.DictReader(open(layout.suggestions_valid, newline="", encoding="utf-8")))
    assert len(rows) == 6 and {r["annotator_type"] for r in rows} == {"ai"}
    assert store.ReviewStore(layout).current() == {}                           # no automatic acceptance, ever
    assert not layout.reviews.exists()


def test_resume_never_repeats_a_terminal_item(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, provider_for(env, scripted))
    first = store.SuggestionStore(layout).records()
    prov2 = provider_for(env, scripted)
    res = run(env, cfg, auth, prov2)
    assert prov2.calls == [] and res.requests_used == 0 and store.SuggestionStore(layout).records() == first


def test_an_interrupted_run_resumes_without_rerunning_finished_items(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    crash = provider_for(env, scripted, D0003=[RuntimeError("machine went to sleep")])
    with pytest.raises(RuntimeError):
        run(env, cfg, auth, crash)
    assert sorted(store.SuggestionStore(layout).terminal()) == ["D0001", "D0002"]      # nothing recorded for D0003
    assert layout.suggestions_valid.exists()                                          # derived file still written
    prov = provider_for(env, scripted)
    res = run(env, cfg, auth, prov)
    assert [c.item_id for c in prov.calls] == ["D0003", "D0004", "D0005", "D0006"]
    assert res.counts["valid"] == 6 and len(store.SuggestionStore(layout).records()) == 6


def test_a_partial_trailing_write_is_recovered_on_resume(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, )
    run(env, cfg, auth, provider_for(env, scripted, ), clock=Clock(), )
    raw = layout.suggestions_raw
    lines = raw.read_bytes().splitlines(keepends=True)
    raw.write_bytes(b"".join(lines[:3]) + lines[3][:40])                          # a crash while writing record 4
    prov = provider_for(env, scripted)
    run(env, cfg, auth, prov)
    assert [c.item_id for c in prov.calls] == ["D0004", "D0005", "D0006"]
    assert len(store.SuggestionStore(layout).terminal()) == 6
    assert (layout.suggestions_raw.parent / "ai_suggestions_raw_v1.jsonl.partial-1").exists()


def test_a_tampered_suggestion_chain_stops_the_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, provider_for(env, scripted))
    layout.suggestions_raw.write_bytes(layout.suggestions_raw.read_bytes().replace(b'"rel_rates": "R"', b'"rel_rates": "I"', 1))
    with pytest.raises(chain.ChainError):
        run(env, cfg, auth, provider_for(env, scripted))


def test_unsendable_items_are_never_sent(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(unsendable=("D0005",))
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted)
    res = run(env, cfg, auth, prov)
    assert "D0005" not in [c.item_id for c in prov.calls] and res.counts["valid"] == 5
    items = store.load_snapshot_items(layout)
    prog = queue.progress(items, layout, frozenset())
    assert prog["never_sent"] == 1 and prog["sendable"] == 5


# ---------------------------------------------------------------- provider errors, retries, re-asks

def test_a_retryable_error_is_retried_with_backoff_then_succeeds(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted, D0001=[ProviderError("rate_limited", "slow down"), env.good("D0001")])
    clock = Clock()
    res = run(env, cfg, auth, prov, clock)
    attempts = store.SuggestionStore(layout).attempts_for("D0001")
    assert [a["status"] for a in attempts] == ["provider_error", "valid"] and attempts[0]["terminal"] is False
    assert attempts[0]["error"] == {"kind": "rate_limited", "retryable": True, "detail": "slow down"}
    assert clock.sleeps == [1] and res.counts["valid"] == 6


def test_retries_stop_at_the_attempt_limit_and_the_item_is_marked_failed(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted, D0001=[ProviderError("timeout", "t")])
    clock = Clock()
    res = run(env, cfg, auth, prov, clock)
    attempts = store.SuggestionStore(layout).attempts_for("D0001")
    assert len(attempts) == 3 == sum(c.item_id == "D0001" for c in prov.calls)           # max_attempts_per_item
    assert attempts[-1]["terminal_status"] == "failed" and clock.sleeps[:2] == [1, 2]
    assert res.counts["failed"] == 1 and res.counts["valid"] == 5


@pytest.mark.parametrize("kind", ["auth", "refused", "bad_request"])
def test_a_non_retryable_error_is_not_retried(make_ai_env, monkeypatch, scripted, kind):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted, D0002=[ProviderError(kind, "no")])
    run(env, cfg, auth, prov)
    assert sum(c.item_id == "D0002" for c in prov.calls) == 1
    assert store.SuggestionStore(layout).terminal()["D0002"]["terminal_status"] == "failed"


def test_a_secret_in_an_error_message_is_redacted_before_storage(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted, D0001=[ProviderError("auth", f"bad key {env.secret} rejected")])
    run(env, cfg, auth, prov)
    rec = store.SuggestionStore(layout).attempts_for("D0001")[0]
    assert env.secret not in json.dumps(rec) and "[REDACTED]" in rec["error"]["detail"]
    assert runner.redact("abc sk-123456 def", ["sk-123456", "ab"]) == "abc [REDACTED] def"


def test_malformed_output_gets_one_reask_and_a_valid_answer_is_kept(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted, D0001=["Sure! here is the JSON", env.good("D0001")])
    run(env, cfg, auth, prov)
    d1 = [c for c in prov.calls if c.item_id == "D0001"]
    assert len(d1) == 2 and prompt.REPAIR_INSTRUCTION in d1[1].user and prompt.REPAIR_INSTRUCTION not in d1[0].user
    attempts = store.SuggestionStore(layout).attempts_for("D0001")
    assert [(a["status"], a["kind"]) for a in attempts] == [("invalid_output", "call"), ("valid", "reask")]
    assert attempts[0]["raw_response"] == "Sure! here is the JSON" and attempts[0]["validation"]["ok"] is False


def test_output_that_stays_invalid_is_recorded_invalid_with_reasons_and_never_repaired(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    bad = env.good("D0001", company_notice="Y")                                   # company notice with an R theme
    res = run(env, cfg, auth, provider_for(env, scripted, D0001=[bad]))
    term = store.SuggestionStore(layout).terminal()["D0001"]
    assert term["terminal_status"] == "invalid" and any("never R" in e for e in term["validation"]["errors"])
    assert len(store.SuggestionStore(layout).attempts_for("D0001")) == 2           # call + one re-ask, no more
    assert res.counts["invalid"] == 1
    rows = list(csv.DictReader(open(layout.suggestions_valid, newline="", encoding="utf-8")))
    assert "D0001" not in {r["item_id"] for r in rows}


def test_a_response_for_a_different_item_is_invalid(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, provider_for(env, scripted, D0003=[env.good("D0004")]))
    term = store.SuggestionStore(layout).terminal()["D0003"]
    assert term["terminal_status"] == "invalid" and "does not match the requested item" in term["validation"]["errors"][0]


def test_a_different_served_model_stops_the_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = scripted(default=lambda req: env.good(req.item_id), model_id="some-other-model")
    with pytest.raises(provider.ExecutionBlocked, match="other than the approved"):
        run(env, cfg, auth, prov)
    recs = store.SuggestionStore(layout).records()
    assert len(recs) == 1 and recs[0]["status"] == "model_mismatch" and "terminal_status" not in recs[0]
    events = chain.ChainedJsonl(layout.audit).records()
    assert any(e.get("outcome") == "stopped_model_mismatch" for e in events)


# ---------------------------------------------------------------- caps and stop

def test_the_request_cap_stops_the_run_and_it_can_resume_only_under_a_new_approval(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, limits={"max_requests": 3})
    prov = provider_for(env, scripted)
    res = run(env, cfg, auth, prov)
    assert res.outcome == "stopped_request_cap" and res.requests_used == 3 and len(prov.calls) == 3
    assert res.counts["pending"] == 3 and "request cap" in res.stop_reason


def test_the_input_token_cap_stops_the_run_before_any_call(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, limits={"max_input_tokens": 10})
    prov = provider_for(env, scripted)
    res = run(env, cfg, auth, prov)
    assert res.outcome == "stopped_token_cap" and prov.calls == []


def test_the_cost_cap_uses_only_supplied_prices(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, limits={
        "max_cost": 0.0001, "currency": "XXX", "unit_price_input_per_1k": 1.0, "unit_price_output_per_1k": 1.0})
    prov = provider_for(env, scripted)
    res = run(env, cfg, auth, prov)
    assert res.outcome == "stopped_cost_cap" and prov.calls == []


def test_a_stop_file_halts_before_the_next_item(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    (layout.root / "STOP").write_text("", encoding="utf-8")
    prov = provider_for(env, scripted)
    res = run(env, cfg, auth, prov)
    assert res.outcome == "stopped_by_user" and prov.calls == []


# ---------------------------------------------------------------- authorization is re-checked at run time

def test_a_run_needs_a_gate_issued_authorization(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    forged = dataclasses.replace(auth, _issued_by_gate=None)
    with pytest.raises(provider.ExecutionBlocked, match="gate-issued"):
        run(env, cfg, forged, provider_for(env, scripted))


def test_a_config_change_after_authorization_blocks_the_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    changed = dataclasses.replace(cfg, run_id="a-different-run")
    prov = provider_for(env, scripted)
    with pytest.raises(provider.ExecutionBlocked, match="changed after authorization"):
        run(env, changed, auth, prov)
    assert prov.calls == []


def test_the_adapter_must_match_the_approved_provider(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = provider_for(env, scripted)
    prov.name = "someone_else"
    with pytest.raises(provider.ExecutionBlocked, match="does not match the approved provider"):
        run(env, cfg, auth, prov)


def test_an_original_file_changed_after_init_blocks_the_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    (env.rf / "annotation_B.csv").write_bytes((env.rf / "annotation_B.csv").read_bytes() + b"\n")
    with pytest.raises(store.StoreError, match="ORIGINAL file changed"):
        run(env, cfg, auth, provider_for(env, scripted))


# ---------------------------------------------------------------- review queue, progress, QC

def mixed_run(env, cfg, auth, scripted):
    two_themes = env.good("D0005", rel_equity="R", pol_equity="POS", evidence_excerpts=[
        {"field": "rel_rates", "excerpt": "raises interest rates"}, {"field": "rel_equity", "excerpt": "Federal Reserve"}])
    amb = env.good("D0002", rel_gold="A", amb_code="A1", uncertainty={"rel_equity": "low", "rel_rates": "low", "rel_gold": "high"})
    return run(env, cfg, auth, provider_for(env, scripted, D0002=[amb], D0003=["garbage"], D0004=[ProviderError("auth", "x")],
                                            D0005=[two_themes]))


def test_queue_orders_items_by_plain_rules_and_never_accepts_anything(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(dup=("D0006",), blind=("D0002",))
    cfg, auth, layout = prepare(env, monkeypatch)
    mixed_run(env, cfg, auth, scripted)
    items = store.load_snapshot_items(layout)
    rows = queue.build_queue(items, layout, frozenset(env.blind))
    got = {r["item_id"]: (r["tier_name"], r["reasons"]) for r in rows}
    assert got["D0002"] == ("blind_label_first", "blind_subset")
    assert got["D0003"] == ("no_valid_suggestion", "invalid_output")
    assert got["D0004"] == ("no_valid_suggestion", "provider_failed")
    assert got["D0005"][0] == "check_closely" and "multi_theme_relevant" in got["D0005"][1]
    assert got["D0006"] == ("check_closely", "duplicate_context")
    assert got["D0001"] == ("routine", "routine")
    assert [r["tier"] for r in rows] == sorted(r["tier"] for r in rows) and len(rows) == 6
    assert store.ReviewStore(layout).current() == {}


def test_an_ambiguous_suggestion_needs_attention_and_high_self_uncertainty_is_not_a_probability(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    mixed_run(env, cfg, auth, scripted)
    items = store.load_snapshot_items(layout)
    term = store.SuggestionStore(layout).terminal()
    assert queue.classify(items[1], term["D0002"], False)[0] == 1
    assert "high_uncertainty_self_reported" in term["D0002"]["validation"]["flags"]
    assert "not a probability" in queue.qc_report(items, layout)["note"]


def test_queue_policy_filters_tiers_limits_and_writes_a_csv(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    mixed_run(env, cfg, auth, scripted)
    items = store.load_snapshot_items(layout)
    only0 = queue.build_queue(items, layout, frozenset(), queue.QueuePolicy(tiers=(0,)))
    assert {r["item_id"] for r in only0} == {"D0003", "D0004"}
    assert len(queue.build_queue(items, layout, frozenset(), queue.QueuePolicy(limit=2))) == 2
    queue.write_queue_csv(layout, only0)
    assert [r["item_id"] for r in csv.DictReader(open(layout.queue, newline="", encoding="utf-8"))] == ["D0003", "D0004"]


def test_progress_says_generation_is_blocked_until_the_gates_are_met(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    store.init_experiment(env.load())
    layout = store.Layout(env.dest)
    prog = queue.progress(store.load_snapshot_items(layout), layout, frozenset())
    assert prog["items"] == 6 and prog["reviewed"] == 0 and prog["suggestions"] == {"not_generated": 6}
    assert "BLOCKED" in prog["next_action"]


def test_qc_report_is_descriptive_and_counts_ai_exposure_of_overlap_items(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    mixed_run(env, cfg, auth, scripted)
    items = store.load_snapshot_items(layout)
    by_id = {i.item_id: i for i in items}
    review(layout, env, by_id, "D0001", "accept")
    review(layout, env, by_id, "D0002", "edit", labels={**BASE_LABELS, "rel_gold": "I", "amb_code": ""}, reason_code="rubric_boundary")
    qc = queue.qc_report(items, layout)
    assert qc["by_label_origin"] == {"accepted_ai": 1, "edited_ai": 1} and qc["acceptance_rate_among_ai_seen"] == 0.5
    assert qc["fields_changed_by_reviewers"] == {"amb_code": 1, "rel_gold": 1}
    assert qc["historical_overlap_items_ai_exposed"] == 1                       # D0002 was in the original overlap
    assert "accuracy" not in {k for k in qc if k != "note"}


# ---------------------------------------------------------------- human review rules

def review(layout, env, by_id, item_id, action, *, blind=(), **kw):
    kw.setdefault("reviewer_id", "AB")
    kw.setdefault("now", T0 + timedelta(minutes=5))
    return reviewer.record_review(layout, items_by_id=by_id, protocol_id="option_B_all_items_ai_assisted",
                                  experiment_id="b2t_test_v1", blind_ids=frozenset(blind or env.blind), item_id=item_id,
                                  action=action, **kw)


@pytest.fixture()
def reviewed_env(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(blind=("D0002",))
    cfg, auth, layout = prepare(env, monkeypatch)
    mixed_run(env, cfg, auth, scripted)
    by_id = {i.item_id: i for i in store.load_snapshot_items(layout)}
    return env, layout, by_id


def test_accept_records_the_suggestion_exactly_and_marks_ai_exposure(reviewed_env):
    env, layout, by = reviewed_env
    rec = review(layout, env, by, "D0001", "accept", shown_at=T0)
    sug = store.SuggestionStore(layout).terminal()["D0001"]
    assert (rec["label_origin"], rec["ai_exposure"], rec["annotator_type"]) == ("accepted_ai", "seen", "human")
    assert rec["suggestion_ref"] == sug["record_sha256"] and rec["changed_fields"] == []
    assert {k: rec["labels"][k] for k in BASE_LABELS} == {k: sug["parsed"][k] for k in BASE_LABELS}
    assert rec["review_seconds"] == 300.0 and rec["long_gap_flag"] is False and rec["historical_overlap"] is False


def test_accept_takes_no_labels_and_needs_a_valid_suggestion(reviewed_env):
    env, layout, by = reviewed_env
    with pytest.raises(reviewer.ReviewError, match="takes no labels"):
        review(layout, env, by, "D0001", "accept", labels=BASE_LABELS)
    with pytest.raises(reviewer.ReviewError, match="no valid suggestion"):
        review(layout, env, by, "D0003", "accept")
    assert store.ReviewStore(layout).records() == []                           # a refused action writes nothing


def test_edit_needs_a_real_change_and_a_reason(reviewed_env):
    env, layout, by = reviewed_env
    changed = {**BASE_LABELS, "rel_rates": "RL", "pol_rates": ""}
    with pytest.raises(reviewer.ReviewError, match="reason code is required"):
        review(layout, env, by, "D0001", "edit", labels=changed)
    with pytest.raises(reviewer.ReviewError, match="needs an explanation"):
        review(layout, env, by, "D0001", "edit", labels=changed, reason_code="other")
    with pytest.raises(reviewer.ReviewError, match="use accept"):
        review(layout, env, by, "D0001", "edit", labels=BASE_LABELS, reason_code="title_misread")
    with pytest.raises(reviewer.ReviewError, match="pol_rates is required"):
        review(layout, env, by, "D0001", "edit", labels={**BASE_LABELS, "pol_rates": ""}, reason_code="title_misread")
    rec = review(layout, env, by, "D0001", "edit", labels=changed, reason_code="rubric_boundary")
    assert (rec["label_origin"], rec["ai_exposure"], rec["changed_fields"], rec["edit_reason_code"]) == (
        "edited_ai", "seen", ["pol_rates", "rel_rates"], "rubric_boundary")


def test_reject_after_seeing_is_still_ai_exposed(reviewed_env):
    env, layout, by = reviewed_env
    rec = review(layout, env, by, "D0001", "reject", labels={**BASE_LABELS, "rel_equity": "RL"}, reason_code="url_context",
                 reason_note="url says otherwise")
    assert (rec["label_origin"], rec["ai_exposure"]) == ("rejected_ai_after_seeing", "seen")


@pytest.mark.parametrize("action", ["uncertain", "insufficient_evidence"])
def test_uncertain_and_insufficient_need_an_A_theme_and_a_note(reviewed_env, action):
    env, layout, by = reviewed_env
    amb = {**BASE_LABELS, "rel_gold": "A", "amb_code": "A1"}
    with pytest.raises(reviewer.ReviewError, match="at least one theme labelled A"):
        review(layout, env, by, "D0001", action, labels=BASE_LABELS, reason_note="why")
    with pytest.raises(reviewer.ReviewError, match="needs a note"):
        review(layout, env, by, "D0001", action, labels=amb)
    rec = review(layout, env, by, "D0001", action, labels=amb, reason_note="headline too short")
    assert rec["ai_exposure"] == "seen" and rec["insufficient_evidence"] == ("Y" if action == "insufficient_evidence" else "N")


def test_no_suggestion_is_only_for_items_without_a_valid_suggestion(reviewed_env):
    env, layout, by = reviewed_env
    with pytest.raises(reviewer.ReviewError, match="would not be 'no suggestion'"):
        review(layout, env, by, "D0001", "no_suggestion", labels=BASE_LABELS)
    rec = review(layout, env, by, "D0003", "no_suggestion", labels=BASE_LABELS)       # D0003's output was invalid
    assert (rec["label_origin"], rec["ai_exposure"], rec["suggestion_ref"]) == ("human_no_suggestion", "none", None)
    with pytest.raises(reviewer.ReviewError, match="needs the reviewer's labels"):
        review(layout, env, by, "D0004", "no_suggestion")


def test_blind_items_are_labelled_before_any_suggestion_and_stay_ai_free(reviewed_env):
    env, layout, by = reviewed_env                                                   # D0002 is blind and has a suggestion
    with pytest.raises(reviewer.ReviewError, match="blind subset"):
        review(layout, env, by, "D0002", "accept")
    with pytest.raises(reviewer.ReviewError, match="not in the blind subset"):
        review(layout, env, by, "D0001", "blind", labels=BASE_LABELS)
    rec = review(layout, env, by, "D0002", "blind", labels=BASE_LABELS)
    assert (rec["label_origin"], rec["ai_exposure"], rec["historical_overlap"]) == ("human_blind", "none", True)


def test_reviewer_identity_and_actions_are_validated(reviewed_env):
    env, layout, by = reviewed_env
    for bad in ("", "a@b.org", "x" * 21):
        with pytest.raises(reviewer.ReviewError, match="initials"):
            review(layout, env, by, "D0001", "accept", reviewer_id=bad)
    with pytest.raises(reviewer.ReviewError, match="unknown action"):
        review(layout, env, by, "D0001", "approve")
    with pytest.raises(reviewer.ReviewError, match="unknown item"):
        review(layout, env, by, "D9999", "accept")
    with pytest.raises(reviewer.ReviewError, match="unexpected label fields"):
        review(layout, env, by, "D0003", "no_suggestion", labels={**BASE_LABELS, "secret": "x"})


def test_a_second_review_is_a_correction_that_supersedes_and_keeps_history(reviewed_env):
    env, layout, by = reviewed_env
    first = review(layout, env, by, "D0001", "accept")
    with pytest.raises(reviewer.ReviewError, match="needs a correction_reason"):
        review(layout, env, by, "D0001", "reject", labels={**BASE_LABELS, "rel_equity": "RL"}, reason_code="url_context")
    second = review(layout, env, by, "D0001", "reject", labels={**BASE_LABELS, "rel_equity": "RL"}, reason_code="url_context",
                    correction_reason="misread the URL")
    assert second["supersedes"] == first["record_sha256"]
    rs = store.ReviewStore(layout)
    assert rs.current()["D0001"]["record_sha256"] == second["record_sha256"] and len(rs.records()) == 2


def test_a_long_gap_is_flagged_not_hidden(reviewed_env):
    env, layout, by = reviewed_env
    rec = review(layout, env, by, "D0001", "accept", shown_at=T0 - timedelta(hours=2))
    assert rec["long_gap_flag"] is True and rec["review_seconds"] > reviewer.LONG_REVIEW_SECONDS


# ---------------------------------------------------------------- interactive reviewer (scripted input)

def interactive(layout, env, by, answers, rows):
    queue_, out = list(answers), []

    def fake_input(prompt_):
        if not queue_:
            raise EOFError
        item = queue_.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    rv = reviewer.AiReviewer(layout, list(by.values()), protocol_id="option_B_all_items_ai_assisted",
                             experiment_id="b2t_test_v1", blind_ids=frozenset(env.blind), input_fn=fake_input,
                             output_fn=out.append, clock=Clock())
    return rv.run([{"item_id": i} for i in rows]), out


SIMPLE = ["R", "I", "I", "POS", "N", "", "", "Y"]          # equity R/POS, rates I, gold I, company N, then confirm


def test_interactive_accept_labels_the_suggestion_as_provisional_and_saves_only_on_enter(reviewed_env):
    env, layout, by = reviewed_env
    summary, out = interactive(layout, env, by, ["AB", ""], ["D0001"])
    text = "\n".join(out)
    assert summary == {"saved": 1, "skipped": 0, "stopped_early": False}
    assert reviewer.SUGGESTION_BANNER in text and "AI-GENERATED SUGGESTION" in text
    assert store.ReviewStore(layout).current()["D0001"]["label_origin"] == "accepted_ai"


def test_interactive_skip_and_quit_save_nothing(reviewed_env):
    env, layout, by = reviewed_env
    summary, _ = interactive(layout, env, by, ["AB", "s", "q"], ["D0001", "D0005"])
    assert summary == {"saved": 0, "skipped": 1, "stopped_early": True}
    assert store.ReviewStore(layout).current() == {}


def test_interactive_blind_item_shows_no_suggestion_and_records_human_blind(reviewed_env):
    env, layout, by = reviewed_env
    summary, out = interactive(layout, env, by, ["AB", *SIMPLE], ["D0002"])
    text = "\n".join(out)
    assert "No AI suggestion is shown for this item." in text and reviewer.SUGGESTION_BANNER not in text
    rec = store.ReviewStore(layout).current()["D0002"]
    assert (rec["label_origin"], rec["ai_exposure"]) == ("human_blind", "none") and rec["labels"]["pol_equity"] == "POS"


def test_interactive_item_without_a_valid_suggestion_is_labelled_unaided(reviewed_env):
    env, layout, by = reviewed_env
    interactive(layout, env, by, ["AB", *SIMPLE], ["D0003"])
    rec = store.ReviewStore(layout).current()["D0003"]
    assert (rec["label_origin"], rec["ai_exposure"]) == ("human_no_suggestion", "none")


def test_interactive_edit_records_the_reason_code(reviewed_env):
    env, layout, by = reviewed_env
    # E = edit starting from the suggestion; the labeller then asks only what is not already answered
    summary, out = interactive(layout, env, by, ["AB", "e", "2", "RL", "Y", "url_context", ""], ["D0001"])
    rec = store.ReviewStore(layout).current().get("D0001")
    assert rec is not None, "\n".join(out)
    assert rec["label_origin"] == "edited_ai" and rec["edit_reason_code"] == "url_context"


# ---------------------------------------------------------------- export

def review_everything(env, layout, by):
    for iid, it in by.items():
        term = store.SuggestionStore(layout).terminal().get(iid)
        if iid in env.blind:
            review(layout, env, by, iid, "blind", labels=BASE_LABELS)
        elif term and term.get("terminal_status") == "valid":
            review(layout, env, by, iid, "accept")
        else:
            review(layout, env, by, iid, "no_suggestion", labels=BASE_LABELS)


def test_export_refuses_until_every_item_has_a_review(reviewed_env):
    env, layout, by = reviewed_env
    review(layout, env, by, "D0001", "accept")
    cfg = env.load()
    with pytest.raises(store.StoreError, match="5 of 6 items have no review record"):
        export.export_dataset(layout, cfg, list(by.values()))
    assert not (layout.export / "annotation_b2t_v1.csv").exists()


def test_export_is_a_separate_read_only_dataset_that_flags_ai_exposure(reviewed_env):
    env, layout, by = reviewed_env
    review_everything(env, layout, by)
    before = tree(env.rf)
    m = export.export_dataset(layout, env.load(), list(by.values()), clock=Clock())
    assert tree(env.rf) == before                                                  # original dataset untouched
    rows = list(csv.DictReader(open(layout.export / "annotation_b2t_v1.csv", newline="", encoding="utf-8")))
    assert [r["item_id"] for r in rows] == env.ids and tuple(rows[0]) == export.B2T_COLUMNS
    assert {r["annotator_type"] for r in rows} == {"human"}
    exposure = {r["item_id"]: r["ai_exposure"] for r in rows}
    assert exposure["D0002"] == "none" and exposure["D0001"] == "seen" and exposure["D0003"] == "none"
    assert m["by_ai_exposure"] == {"seen": 3, "none": 3} and m["rows"] == 6
    assert m["historical_overlap_items"] == 2 and m["historical_overlap_blind_human"] == 1
    assert m["historical_overlap_ai_exposed"] == 0                                 # D0002 blind, D0004 had no suggestion
    assert "NOT independent human labels" in m["independence_statement"]
    assert m["csv_sha256"] == hashlib.sha256((layout.export / "annotation_b2t_v1.csv").read_bytes()).hexdigest()
    assert not os.access(layout.export / "annotation_b2t_v1.csv", os.W_OK) or sys.platform == "win32"
    with pytest.raises(store.StoreError, match="never overwritten"):
        export.export_dataset(layout, env.load(), list(by.values()))


def test_the_existing_freeze_and_evaluate_do_not_read_the_ai_export():
    from wealthpilot.data.gdelt import annotate, evaluate
    for mod in (annotate, evaluate):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "annotation_b2t" not in src and "b2t_annotation" not in src and "gdelt.ai" not in src


# ---------------------------------------------------------------- isolation and no-network guarantees

AI_DIR = Path(gdelt_pkg.__file__).parent / "ai"


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_ai_package_imports_nothing_that_can_reach_a_network_or_a_provider():
    banned = {"socket", "ssl", "http", "urllib", "requests", "httpx", "aiohttp", "subprocess", "ftplib", "smtplib",
              "google", "anthropic", "openai", "sqlalchemy"}
    for py in AI_DIR.glob("*.py"):
        tops = {n.split(".")[0] for n in _imports(py)}
        assert not (tops & banned), f"{py.name} imports {tops & banned}"


def test_importing_the_pipeline_loads_no_provider_sdk():
    code = ("import sys, wealthpilot.data.gdelt.cli, wealthpilot.data.gdelt.ai.runner, wealthpilot.data.gdelt.ai.export;"
            "bad=[m for m in ('google','google.genai','anthropic','openai','requests','httpx') if m in sys.modules];"
            "print(bad)")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60,
                         env={**os.environ, "PYTHONPATH": str(Path(gdelt_pkg.__file__).parents[3])})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"


def test_no_api_key_value_or_provider_name_is_hard_coded_in_the_package():
    text = "\n".join(p.read_text(encoding="utf-8") for p in AI_DIR.glob("*.py"))
    for needle in ("sk-", "AIza", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        assert needle not in text, needle
    assert provider.ADAPTERS == {}
