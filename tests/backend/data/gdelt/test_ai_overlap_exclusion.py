"""B2-U7: the fail-closed control that keeps the original overlap items (and any blind items) away from a provider.
SYNTHETIC folders only; the build lock is lifted inside a test, for a scripted fake provider, never for real data."""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from wealthpilot.data.gdelt import cli
from wealthpilot.data.gdelt.ai import config as aic
from wealthpilot.data.gdelt.ai import queue, reviewer, runner, store
from wealthpilot.data.gdelt.errors import ConfigError

T0 = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
BASE = {"rel_equity": "I", "rel_rates": "R", "rel_gold": "I", "amb_code": "", "company_notice": "N",
        "pol_equity": "", "pol_rates": "NEG", "pol_gold": ""}


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now

    def sleep(self, s):
        pass


def prepare(env, monkeypatch, mode, *, blind_in_cfg=True):
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = mode
    env.write_cfg(env.approved(d))
    cfg = env.load()
    store.init_experiment(cfg)
    return cfg, env.authorize(cfg), store.Layout(env.dest)


def run(env, cfg, auth, prov):
    clock = Clock()
    return runner.run_suggestions(cfg, auth, prov, clock=clock, sleep=clock.sleep, env=env.process_env)


def sent(prov):
    return sorted({c.item_id for c in prov.calls})


def blockers(env, cfg):
    return aic.blockers(cfg, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(), confirm_ai_run=True,
                        env=env.process_env, overlap_item_ids=frozenset(env.overlap))


# ---------------------------------------------------------------- configuration is explicit and fail-closed

def test_the_pure_exclusion_function_never_guesses():
    f = aic.excluded_item_ids
    ov = frozenset({"D0002", "D0004"})
    assert f("overlap_and_blind", ["D0002"], ov) == ov
    assert f("overlap_and_blind", ["D0009"], ov) == ov | {"D0009"}               # blind items are always included
    assert f("blind_only", ["D0002"], ov) == {"D0002"}
    assert f("none", ["D0002"], ov) == frozenset()
    assert f(None, ["D0002"], ov) is None                                       # unset: undeterminable
    assert f("overlap_and_blind", [], None) is None                             # unverified membership: undeterminable
    assert f("bogus", [], ov) is None


def test_an_unset_exclusion_blocks_execution(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = None
    env.write_cfg(env.approved(d))
    problems = blockers(env, env.load())
    assert len(problems) == 1 and "provider_exclusion is not set" in problems[0]


@pytest.mark.parametrize("bad", ["overlap", "all", "", 1, True, "OVERLAP_AND_BLIND"])
def test_an_unknown_exclusion_mode_is_refused(make_ai_env, bad):
    env = make_ai_env()
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = bad
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="provider_exclusion"):
        env.load()


def test_unverified_overlap_membership_blocks_and_never_matches_an_approval(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    env.write_cfg(env.approved(d))
    cfg = env.load()
    unverified = aic.blockers(cfg, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                              confirm_ai_run=True, env=env.process_env, overlap_item_ids=None)
    assert any("could not be verified" in p for p in unverified) and any(p.startswith("gate D") for p in unverified)
    assert blockers(env, cfg) == []


def test_blind_items_must_be_original_overlap_items(make_ai_env, monkeypatch):
    env = make_ai_env()                                                         # overlap is D0002, D0004
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"].update(provider_exclusion="blind_only", blind_item_ids=["D0001"])
    env.write_cfg(env.approved(d))
    assert any("blind_item_ids must all be original overlap items" in p for p in blockers(env, env.load()))


def test_the_exclusion_is_bound_by_gate_a_and_the_excluded_set_by_gate_d(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    d = env.approved(d)
    assert blockers(env, (env.write_cfg(d), env.load())[1]) == []
    d["protocol"]["provider_exclusion"] = "blind_only"                          # changed after approval
    env.write_cfg(d)
    gates = sorted(p[5] for p in blockers(env, env.load()) if p.startswith("gate "))
    assert gates == ["A", "D"]                                                  # the old approvals cannot authorise it
    d["protocol"]["provider_exclusion"] = "none"
    env.write_cfg(d)
    assert sorted(p[5] for p in blockers(env, env.load()) if p.startswith("gate ")) == ["A", "D"]


def test_the_same_mode_over_a_different_overlap_set_changes_gate_d(make_ai_env):
    a, b = make_ai_env(overlap=("D0002", "D0004")), make_ai_env(overlap=("D0002", "D0005"))
    out = []
    for env in (a, b):
        d = env.cfg_dict()
        d["protocol"]["provider_exclusion"] = "overlap_and_blind"
        env.write_cfg(d)
        out.append(aic.bindings(env.load(), itemset_sha256="x" * 64, original_overlap_sha256="y" * 64,
                                overlap_item_ids=frozenset(env.overlap)))
    assert out[0]["D"] != out[1]["D"] and out[0]["A"] == out[1]["A"]


# ---------------------------------------------------------------- the provider never receives an excluded item

@pytest.mark.parametrize("mode,blind,expected_sent", [
    ("overlap_and_blind", ("D0002",), ["D0001", "D0003", "D0005", "D0006"]),
    ("blind_only", ("D0002",), ["D0001", "D0003", "D0004", "D0005", "D0006"]),
    ("none", ("D0002",), ["D0001", "D0002", "D0003", "D0004", "D0005", "D0006"])])
def test_each_mode_sends_exactly_the_allowed_items(make_ai_env, monkeypatch, scripted, mode, blind, expected_sent):
    env = make_ai_env(blind=blind)
    cfg, auth, layout = prepare(env, monkeypatch, mode)
    prov = scripted(default=lambda req: env.good(req.item_id))
    run(env, cfg, auth, prov)
    assert sent(prov) == expected_sent
    assert sorted(store.SuggestionStore(layout).terminal()) == expected_sent


def test_membership_is_not_inferred_from_ids_or_order(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(overlap=("D0005", "D0006"))                               # the LAST items, not the first
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    prov = scripted(default=lambda req: env.good(req.item_id))
    run(env, cfg, auth, prov)
    assert sent(prov) == ["D0001", "D0002", "D0003", "D0004"]


def test_resume_and_a_repeated_run_never_reach_an_excluded_item(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    crash = scripted({"D0003": [RuntimeError("interrupted")]}, default=lambda req: env.good(req.item_id))
    with pytest.raises(RuntimeError):
        run(env, cfg, auth, crash)
    again = scripted(default=lambda req: env.good(req.item_id))
    res = run(env, cfg, auth, again)
    assert sent(again) == ["D0003", "D0005", "D0006"] and res.counts["pending"] == 0
    third = scripted(default=lambda req: env.good(req.item_id))
    run(env, cfg, auth, third)
    assert third.calls == []
    assert not ({"D0002", "D0004"} & {c.item_id for c in crash.calls + again.calls})


def test_retries_and_reasks_stay_inside_the_allowed_set(make_ai_env, monkeypatch, scripted):
    from wealthpilot.data.gdelt.ai.provider import ProviderError
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    prov = scripted({"D0001": [ProviderError("timeout", "t")], "D0003": ["not json"]},
                    default=lambda req: env.good(req.item_id))
    run(env, cfg, auth, prov)
    assert {c.item_id for c in prov.calls} == {"D0001", "D0003", "D0005", "D0006"}
    assert not ({"D0002", "D0004"} & {r["item_id"] for r in store.SuggestionStore(layout).records()})


def test_a_store_that_already_holds_a_suggestion_for_an_excluded_item_refuses_the_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    prov = scripted(default=lambda req: env.good(req.item_id))
    run(env, cfg, auth, prov)
    rec = dict(store.SuggestionStore(layout).records()[0])
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    rec["item_id"] = "D0004"                                                    # an excluded (overlap) item
    store.SuggestionStore(layout).append(rec)
    prov2 = scripted(default=lambda req: env.good(req.item_id))
    with pytest.raises(runner.ExecutionBlocked, match="contaminated"):
        run(env, cfg, auth, prov2)
    assert prov2.calls == []


def test_the_guard_refuses_an_excluded_request_even_if_some_other_path_builds_it(make_ai_env, scripted):
    from wealthpilot.data.gdelt.ai.provider import SuggestionRequest
    inner = scripted(default=lambda req: "{}")
    guard = runner._ExclusionGuard(inner, frozenset({"D0004"}))
    assert guard.name == inner.name
    with pytest.raises(runner.ExecutionBlocked, match="excluded from provider submission"):
        guard.suggest(SuggestionRequest("D0004", "s", "u", {}, 10, 0.0))
    assert inner.calls == []
    guard.suggest(SuggestionRequest("D0001", "s", "u", {}, 10, 0.0))
    assert [c.item_id for c in inner.calls] == ["D0001"]


def test_a_changed_exclusion_after_authorization_cannot_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    widened = dataclasses.replace(cfg, provider_exclusion="none")
    prov = scripted(default=lambda req: env.good(req.item_id))
    with pytest.raises(runner.ExecutionBlocked, match="changed after authorization"):
        run(env, widened, auth, prov)
    assert prov.calls == []


# ---------------------------------------------------------------- missing or corrupt membership manifests fail closed

def _manifest(layout):
    path = layout.historical_overlap
    os.chmod(path, 0o666)
    return path, json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("damage,fragment", [
    (lambda path, m: path.unlink(), "missing"),
    (lambda path, m: path.write_text("not json", encoding="utf-8"), "malformed"),
    (lambda path, m: path.write_text(json.dumps({**m, "count": 99}), encoding="utf-8"), "malformed"),
    (lambda path, m: path.write_text(json.dumps({**m, "item_ids": m["item_ids"] + m["item_ids"], "count": 4}), encoding="utf-8"), "malformed"),
    (lambda path, m: path.write_text(json.dumps({**m, "item_ids": ["D0004"], "count": 1}), encoding="utf-8"), "disagree"),
    (lambda path, m: path.write_text(json.dumps({**m, "item_ids": ["D0002", "D0004", "D0001"], "count": 3}), encoding="utf-8"), "disagree"),
    (lambda path, m: path.write_text(json.dumps({**m, "annotation_B_sha256": "0" * 64}), encoding="utf-8"), "differs"),
    (lambda path, m: path.write_text(json.dumps({k: v for k, v in m.items() if k != "item_ids"}), encoding="utf-8"), "malformed")])
def test_a_missing_or_inconsistent_manifest_blocks_the_run_before_any_call(make_ai_env, monkeypatch, scripted, damage, fragment):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    path, m = _manifest(layout)
    damage(path, m)
    prov = scripted(default=lambda req: env.good(req.item_id))
    with pytest.raises(store.StoreError, match=fragment):
        run(env, cfg, auth, prov)
    assert prov.calls == []


def test_a_changed_snapshot_membership_is_caught_by_the_snapshot_check(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    snap = layout.snapshot / "annotation_B.csv"
    os.chmod(snap, 0o666)
    snap.write_bytes(snap.read_bytes() + b"\n")
    prov = scripted(default=lambda req: env.good(req.item_id))
    with pytest.raises(store.StoreError):
        run(env, cfg, auth, prov)
    assert prov.calls == []


def test_the_source_membership_check_rejects_a_mismatched_manifest(make_ai_env):
    env = make_ai_env()
    assert store.source_overlap_ids(env.rf) == frozenset(env.overlap)
    b = env.rf / "annotation_B.csv"
    b.write_bytes(b.read_bytes() + b"\n")
    with pytest.raises(store.StoreError, match="fingerprint"):
        store.source_overlap_ids(env.rf)


def test_init_still_refuses_blind_items_that_are_not_overlap_items(make_ai_env):
    env = make_ai_env(blind=("D0001",))
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "blind_only"
    env.write_cfg(d)
    with pytest.raises(store.StoreError, match="must be original overlap items"):
        store.init_experiment(env.load())


# ---------------------------------------------------------------- queue, review and dry run honour the exclusion

def test_the_queue_and_progress_never_expect_a_suggestion_for_an_excluded_item(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(blind=("D0002",))
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    items = store.load_snapshot_items(layout)
    excluded = aic.excluded_item_ids("overlap_and_blind", cfg.blind_item_ids, store.verified_overlap(layout))
    rows = {r["item_id"]: r for r in queue.build_queue(items, layout, frozenset(env.blind), excluded_ids=excluded)}
    assert rows["D0004"]["tier_name"] == "no_valid_suggestion" and rows["D0004"]["reasons"] == "excluded_from_provider"
    assert rows["D0002"]["tier_name"] == "blind_label_first"
    prog = queue.progress(items, layout, frozenset(env.blind), excluded)
    assert prog["excluded_from_provider"] == 2 and prog["sendable"] == 4 and prog["suggestions"] == {"valid": 4}
    layout.suggestions_valid.unlink()                                          # queue reconstruction from scratch
    again = {r["item_id"]: r["reasons"] for r in queue.build_queue(items, layout, frozenset(env.blind), excluded_ids=excluded)}
    assert again["D0004"] == "excluded_from_provider"


def test_an_excluded_item_cannot_be_reviewed_as_ai_seen_and_is_labelled_unaided(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "overlap_and_blind")
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    by = {i.item_id: i for i in store.load_snapshot_items(layout)}
    ex = frozenset({"D0002", "D0004"})

    def rev(item_id, action, **kw):
        return reviewer.record_review(layout, items_by_id=by, protocol_id="p", experiment_id="b2t_test_v1",
                                      blind_ids=frozenset(), excluded_ids=ex, item_id=item_id, action=action,
                                      reviewer_id="AB", now=T0, **kw)

    with pytest.raises(reviewer.ReviewError, match="excluded from provider submission"):
        rev("D0004", "accept")
    rec = rev("D0004", "no_suggestion", labels=BASE)
    assert (rec["label_origin"], rec["ai_exposure"], rec["suggestion_ref"]) == ("human_no_suggestion", "none", None)


def test_a_stray_suggestion_for_an_excluded_item_is_refused_at_review_too(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, "none")                       # D0004 got a suggestion under 'none'
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    by = {i.item_id: i for i in store.load_snapshot_items(layout)}
    with pytest.raises(reviewer.ReviewError, match="excluded from provider submission"):
        reviewer.record_review(layout, items_by_id=by, protocol_id="p", experiment_id="e", blind_ids=frozenset(),
                               excluded_ids=frozenset({"D0004"}), item_id="D0004", action="no_suggestion", labels=BASE,
                               reviewer_id="AB", now=T0)


def test_the_dry_run_counts_only_what_would_be_sent_and_writes_nothing(make_ai_env):
    env = make_ai_env(blind=("D0002",))
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    env.write_cfg(d)
    before = sorted(p.relative_to(env.root).as_posix() for p in env.root.rglob("*"))
    out = runner.dry_run(env.load(), env=env.process_env)
    assert sorted(p.relative_to(env.root).as_posix() for p in env.root.rglob("*")) == before
    assert (out["items"], out["sendable_items"], out["excluded_from_provider"], out["provider_exclusion"]) == (6, 4, 2, "overlap_and_blind")
    assert (out["provider_called"], out["data_sent"], out["files_written"]) == (False, False, False)
    d["protocol"]["provider_exclusion"] = "none"
    env.write_cfg(d)
    full = runner.dry_run(env.load(), env=env.process_env)
    assert full["sendable_items"] == 6
    assert out["estimates"]["input_tokens_estimated_chars_div_4"] < full["estimates"]["input_tokens_estimated_chars_div_4"]
    assert out["approval_bindings_to_approve"]["D"] != full["approval_bindings_to_approve"]["D"]


def test_the_dry_run_reports_unverifiable_membership_as_a_problem(make_ai_env):
    env = make_ai_env()
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    env.write_cfg(d)
    (env.rf / "annotation_B.csv").write_bytes(b"tampered")
    out = runner.dry_run(env.load(), env=env.process_env)
    assert any("overlap membership could not be verified" in p for p in out["unmet_prerequisites"])
    assert out["excluded_from_provider"] is None


# ---------------------------------------------------------------- nothing was enabled

def test_the_shipped_build_stays_locked_and_the_cli_run_is_blocked(make_ai_env, capsys):
    import wealthpilot.data.gdelt as gdelt_pkg
    assert gdelt_pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False and runner.ExecutionBlocked
    from wealthpilot.data.gdelt.ai import provider
    assert provider.ADAPTERS == {}
    env = make_ai_env()
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    env.write_cfg(env.approved(d))
    assert cli.main(["ai", "run", "--experiment", str(env.yaml_path), "--confirm-ai-run"]) == 3
    err = capsys.readouterr().err
    assert "build lock" in err and "no adapter exists" in err and not env.dest.exists()
