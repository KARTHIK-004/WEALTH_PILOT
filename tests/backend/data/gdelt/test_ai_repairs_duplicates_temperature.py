"""B2-U5 repairs: the reviewer's duplicate answer is kept and validated, temperature is explicit and bound to Gate B, the
polarity decision must be recorded, and every run writes an auditable manifest. SYNTHETIC; offline; the build lock is lifted
only inside a test and only for a scripted fake provider."""

from __future__ import annotations

import csv
import dataclasses
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import wealthpilot.data.gdelt as gdelt_pkg
from wealthpilot.data.gdelt import cli
from wealthpilot.data.gdelt.ai import chain, config as aic, export, reviewer, runner, store
from wealthpilot.data.gdelt.errors import ConfigError

T0 = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
BASE = {"rel_equity": "I", "rel_rates": "R", "rel_gold": "I", "amb_code": "", "company_notice": "N",
        "pol_equity": "", "pol_rates": "NEG", "pol_gold": ""}
P1 = "P1_required_as_in_existing_rubric"


class Clock:
    def __init__(self):
        self.now, self.sleeps = T0, []

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)


def prepare(env, monkeypatch, *, edit=None):
    env.enable(monkeypatch)
    d = env.cfg_dict()
    if edit:
        edit(d)
    env.write_cfg(env.approved(d))
    cfg = env.load()
    store.init_experiment(cfg)
    return cfg, env.authorize(cfg), store.Layout(env.dest)


def run(env, cfg, auth, prov, clock=None):
    clock = clock or Clock()
    return runner.run_suggestions(cfg, auth, prov, clock=clock, sleep=clock.sleep, env=env.process_env)


def review(layout, env, by, item_id, action, **kw):
    kw.setdefault("reviewer_id", "AB")
    kw.setdefault("now", T0 + timedelta(minutes=5))
    return reviewer.record_review(layout, items_by_id=by, protocol_id="option_B_all_items_ai_assisted",
                                  experiment_id="b2t_test_v1", blind_ids=frozenset(env.blind), item_id=item_id,
                                  action=action, **kw)


@pytest.fixture()
def flow(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(blind=("D0002",))
    cfg, auth, layout = prepare(env, monkeypatch)
    prov = scripted(default=lambda req: env.good(req.item_id))
    run(env, cfg, auth, prov)
    by = {i.item_id: i for i in store.load_snapshot_items(layout)}
    return env, cfg, auth, layout, by, prov


# ================================================================ the dropped duplicate answer

def test_accept_can_carry_a_duplicate_reference_and_it_is_stored(flow):
    env, cfg, auth, layout, by, _ = flow
    rec = review(layout, env, by, "D0001", "accept", labels={"near_dup_of": "D0003"})
    assert rec["labels"]["near_dup_of"] == "D0003" and rec["label_origin"] == "accepted_ai" and rec["changed_fields"] == []
    sug = store.SuggestionStore(layout).terminal()["D0001"]
    assert {k: rec["labels"][k] for k in BASE} == {k: sug["parsed"][k] for k in BASE}      # content is still the suggestion
    assert store.ReviewStore(layout).current()["D0001"]["labels"]["near_dup_of"] == "D0003"


@pytest.mark.parametrize("given", [None, "", "   "])
def test_no_duplicate_is_the_empty_string(flow, given):
    env, cfg, auth, layout, by, _ = flow
    labels = None if given is None else {"near_dup_of": given}
    rec = review(layout, env, by, "D0001", "accept", labels=labels)
    assert rec["labels"]["near_dup_of"] == reviewer.NEAR_DUP_NONE == ""


def test_the_reference_is_trimmed(flow):
    env, cfg, auth, layout, by, _ = flow
    assert review(layout, env, by, "D0001", "accept", labels={"near_dup_of": "  D0004 "})["labels"]["near_dup_of"] == "D0004"


@pytest.mark.parametrize("bad", ["d0004", "X0004", "D004", "D00045", "D0004;D0005", "0004", "D 0004", "../D0004"])
def test_a_malformed_reference_is_rejected_and_nothing_is_written(flow, bad):
    env, cfg, auth, layout, by, _ = flow
    with pytest.raises(reviewer.ReviewError, match="near_dup_of must be an item ID"):
        review(layout, env, by, "D0001", "accept", labels={"near_dup_of": bad})
    assert store.ReviewStore(layout).records() == []


def test_a_non_text_reference_is_rejected(flow):
    env, cfg, auth, layout, by, _ = flow
    with pytest.raises(reviewer.ReviewError, match="must be text"):
        review(layout, env, by, "D0001", "accept", labels={"near_dup_of": 4})


def test_an_unknown_item_is_rejected(flow):
    env, cfg, auth, layout, by, _ = flow
    with pytest.raises(reviewer.ReviewError, match="another existing item_id"):
        review(layout, env, by, "D0001", "accept", labels={"near_dup_of": "D9999"})
    assert store.ReviewStore(layout).records() == []


def test_a_self_reference_is_rejected(flow):
    env, cfg, auth, layout, by, _ = flow
    with pytest.raises(reviewer.ReviewError, match="another existing item_id"):
        review(layout, env, by, "D0003", "accept", labels={"near_dup_of": "D0003"})


def test_accept_still_takes_no_content_labels(flow):
    env, cfg, auth, layout, by, _ = flow
    with pytest.raises(reviewer.ReviewError, match="takes no labels"):
        review(layout, env, by, "D0001", "accept", labels={**BASE, "near_dup_of": "D0003"})
    with pytest.raises(reviewer.ReviewError, match="takes no labels"):
        review(layout, env, by, "D0001", "accept", labels={"rel_rates": "I"})


def test_every_action_records_the_duplicate(flow, make_ai_env, monkeypatch, scripted):
    env, cfg, auth, layout, by, _ = flow
    edited = {**BASE, "rel_rates": "RL", "pol_rates": "", "near_dup_of": "D0005"}
    assert review(layout, env, by, "D0001", "edit", labels=edited, reason_code="rubric_boundary")["labels"]["near_dup_of"] == "D0005"
    assert review(layout, env, by, "D0003", "reject", labels={**edited, "near_dup_of": "D0006"},
                  reason_code="url_context")["labels"]["near_dup_of"] == "D0006"
    amb = {**BASE, "rel_gold": "A", "amb_code": "A1", "near_dup_of": "D0001"}
    assert review(layout, env, by, "D0004", "uncertain", labels=amb, reason_note="x")["labels"]["near_dup_of"] == "D0001"
    assert review(layout, env, by, "D0002", "blind", labels={**BASE, "near_dup_of": "D0006"})["labels"]["near_dup_of"] == "D0006"


def test_no_suggestion_items_can_record_a_duplicate(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, scripted(default=lambda req: "not json"))
    by = {i.item_id: i for i in store.load_snapshot_items(layout)}
    rec = review(layout, env, by, "D0001", "no_suggestion", labels={**BASE, "near_dup_of": "D0002"})
    assert (rec["label_origin"], rec["labels"]["near_dup_of"]) == ("human_no_suggestion", "D0002")


def test_changing_a_recorded_duplicate_is_a_correction_with_a_reason(flow):
    env, cfg, auth, layout, by, _ = flow
    first = review(layout, env, by, "D0001", "accept", labels={"near_dup_of": "D0003"})
    with pytest.raises(reviewer.ReviewError, match="needs a correction_reason"):
        review(layout, env, by, "D0001", "accept", labels={"near_dup_of": "D0004"})
    second = review(layout, env, by, "D0001", "accept", labels={"near_dup_of": "D0004"}, correction_reason="wrong item")
    assert second["supersedes"] == first["record_sha256"] and len(store.ReviewStore(layout).records()) == 2


def review_all(env, layout, by, dup_for=None):
    dup_for = dup_for or {}
    for iid in by:
        labels = {"near_dup_of": dup_for[iid]} if iid in dup_for else None
        if iid in env.blind:
            review(layout, env, by, iid, "blind", labels={**BASE, **(labels or {})})
        else:
            review(layout, env, by, iid, "accept", labels=labels)


def test_the_duplicate_reaches_the_exported_dataset_and_manifest(flow):
    env, cfg, auth, layout, by, _ = flow
    review_all(env, layout, by, dup_for={"D0001": "D0003", "D0002": "D0006"})
    m = export.export_dataset(layout, cfg, list(by.values()), clock=Clock())
    rows = {r["item_id"]: r for r in csv.DictReader(open(layout.export / "annotation_b2t_v1.csv", newline="", encoding="utf-8"))}
    assert (rows["D0001"]["near_dup_of"], rows["D0002"]["near_dup_of"], rows["D0003"]["near_dup_of"]) == ("D0003", "D0006", "")
    assert m["near_dup_references"] == 2


@pytest.mark.parametrize("ref", ["D9999", "D0003"])
def test_export_refuses_an_invalid_reference_it_finds_in_the_records(flow, ref):
    env, cfg, auth, layout, by, _ = flow
    review_all(env, layout, by)
    # a record that bypassed the recording function (for example a hand-edited chain rebuilt by someone): export re-checks
    rs = store.ReviewStore(layout)
    last = rs.records()[2]
    body = {k: v for k, v in last.items() if k not in ("prev_sha256", "record_sha256")}
    body["labels"] = {**body["labels"], "near_dup_of": ref if ref != "D0003" else body["item_id"]}
    body["supersedes"], body["correction_reason"] = last["record_sha256"], "test"
    rs.append(body)
    with pytest.raises(store.StoreError, match="invalid near_dup_of references"):
        export.export_dataset(layout, cfg, list(by.values()), clock=Clock())
    assert not (layout.export / "annotation_b2t_v1.csv").exists()


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


def test_interactive_accept_with_a_duplicate(flow):
    env, cfg, auth, layout, by, _ = flow
    summary, out = interactive(layout, env, by, ["AB", "d", "D0003"], ["D0001"])
    assert summary["saved"] == 1
    rec = store.ReviewStore(layout).current()["D0001"]
    assert (rec["label_origin"], rec["labels"]["near_dup_of"]) == ("accepted_ai", "D0003")


def test_interactive_duplicate_prompt_rejects_the_item_itself_and_unknown_ids(flow):
    env, cfg, auth, layout, by, _ = flow
    interactive(layout, env, by, ["AB", "d", "D0001", "D9999", "D0004"], ["D0001"])
    assert store.ReviewStore(layout).current()["D0001"]["labels"]["near_dup_of"] == "D0004"


def test_interactive_edit_keeps_the_answer_to_same_story_as_item(flow):
    env, cfg, auth, layout, by, _ = flow
    # 2 = change rates relevance to RL (the polarity row disappears, so the rows renumber); 5 = same story as item
    interactive(layout, env, by, ["AB", "e", "2", "RL", "5", "D0004", "Y", "url_context", ""], ["D0001"])
    rec = store.ReviewStore(layout).current().get("D0001")
    assert rec is not None and rec["labels"]["near_dup_of"] == "D0004" and rec["label_origin"] == "edited_ai"
    assert rec["labels"]["note"] == "" and rec["labels"]["rel_rates"] == "RL"


def test_interactive_blind_item_keeps_the_duplicate_answer(flow):
    env, cfg, auth, layout, by, _ = flow
    interactive(layout, env, by, ["AB", "R", "I", "I", "POS", "N", "D0004", "", "Y"], ["D0002"])
    rec = store.ReviewStore(layout).current()["D0002"]
    assert (rec["label_origin"], rec["labels"]["near_dup_of"]) == ("human_blind", "D0004")


def test_the_original_human_only_dataset_and_its_columns_are_untouched(flow):
    from wealthpilot.data.gdelt import annotate
    env, cfg, auth, layout, by, _ = flow
    assert "near_dup_of" in annotate.LABEL_COLUMNS and "label_origin" not in annotate.LABEL_COLUMNS
    assert env.sha("annotation_A.csv") == store.sha_file(layout.snapshot / "annotation_A.csv")


# ================================================================ temperature

@pytest.mark.parametrize("value,expected", [(0, 0.0), (0.0, 0.0), (1, 1.0), (0.7, 0.7), (2, 2.0)])
def test_valid_temperatures_load_as_floats(make_ai_env, value, expected):
    env = make_ai_env()
    d = env.cfg_dict()
    d["provider"]["temperature"] = value
    env.write_cfg(d)
    t = env.load().temperature
    assert t == expected and isinstance(t, float)


@pytest.mark.parametrize("bad", [-0.1, 2.01, 10, True, False, "0.5", "", [0], {"v": 0}])
def test_invalid_temperatures_are_rejected_not_adjusted(make_ai_env, bad):
    env = make_ai_env()
    d = env.cfg_dict()
    d["provider"]["temperature"] = bad
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="provider.temperature"):
        env.load()


@pytest.mark.parametrize("literal", [".nan", ".inf", "-.inf"])
def test_non_finite_temperatures_are_rejected(make_ai_env, literal):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict())
    text = env.yaml_path.read_text(encoding="utf-8").replace("temperature: 0.0", f"temperature: {literal}")
    env.yaml_path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="provider.temperature"):
        env.load()


def test_a_missing_temperature_blocks_execution_and_no_default_is_substituted(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["provider"]["temperature"] = None
    env.write_cfg(env.approved(d))
    cfg = env.load()
    assert cfg.temperature is None
    problems = aic.blockers(cfg, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap),
                            confirm_ai_run=True, env=env.process_env)
    assert problems == ["provider.temperature is not set (approval Gate B); no default is substituted"]


def test_the_temperature_is_part_of_gate_b_and_nothing_else(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.approved(env.cfg_dict())                       # approved at temperature 0.0
    d["provider"]["temperature"] = 0.2                     # changed afterwards
    env.write_cfg(d)
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap),
                            confirm_ai_run=True, env=env.process_env)
    assert [p[5] for p in problems if p.startswith("gate ")] == ["B"]
    d["approvals"] = {g: None for g in "ABCD"}
    env.write_cfg(env.approved(d))                         # re-approved at 0.2: clean again
    assert aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap),
                        confirm_ai_run=True, env=env.process_env) == []


def test_the_effective_value_is_what_is_hashed(make_ai_env):
    env = make_ai_env()
    bindings = {}
    for t in (0, 0.0, 0.2):
        d = env.cfg_dict()
        d["provider"]["temperature"] = t
        env.write_cfg(d)
        bindings[t] = aic.bindings(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap))["B"]
    assert bindings[0] == bindings[0.0] != bindings[0.2]


def test_the_provider_receives_the_approved_temperature_and_every_record_stores_it(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, edit=lambda d: d["provider"].update(temperature=0.3))
    prov = scripted(default=lambda req: env.good(req.item_id))
    run(env, cfg, auth, prov)
    assert {c.temperature for c in prov.calls} == {0.3}
    recs = store.SuggestionStore(layout).records()
    assert {r["params"]["temperature"] for r in recs} == {0.3} and {r["provider"]["model_id"] for r in recs} == {"fake-model-1"}


def test_the_run_manifest_records_the_effective_settings_and_is_read_only(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch, edit=lambda d: d["provider"].update(temperature=0.0))
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    path = layout.run_manifest("run-test-1")
    m = json.loads(path.read_text(encoding="utf-8"))
    assert (m["model_id"], m["model_version"], m["temperature"], m["run_id"], m["provider"]) == (
        "fake-model-1", "2026-01-01", 0.0, "run-test-1", "fake_provider")
    assert m["approval_bindings"] == auth.bindings and m["polarity_option"] == P1 and m["max_output_tokens"] == 400
    assert not os.access(path, os.W_OK) or os.name == "nt"
    started = [e for e in chain.ChainedJsonl(layout.audit).records() if e["event"] == "run_started"][0]
    assert started["sha256"] == store.sha_file(path)                           # the audit log pins the manifest


def test_a_resumed_run_reuses_an_identical_manifest(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    before = store.sha_file(layout.run_manifest("run-test-1"))
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    assert store.sha_file(layout.run_manifest("run-test-1")) == before


def test_a_run_manifest_that_differs_from_the_current_settings_blocks_the_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    path = layout.run_manifest("run-test-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = runner._manifest_body(cfg, auth, runner.load_rubric(cfg.rubric_version).sha256)
    path.write_text(json.dumps({**body, "temperature": 0.9}), encoding="utf-8")        # a leftover from other settings
    prov = scripted(default=lambda req: env.good(req.item_id))
    with pytest.raises(runner.ExecutionBlocked, match="manifest of this run_id differs"):
        run(env, cfg, auth, prov)
    assert prov.calls == []


def test_a_temperature_removed_after_authorization_cannot_run(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    changed = dataclasses.replace(cfg, temperature=None)
    prov = scripted(default=lambda req: env.good(req.item_id))
    with pytest.raises(runner.ExecutionBlocked):
        run(env, changed, auth, prov)
    # even with an authorization that matches the incomplete config, a missing temperature is refused
    forged = aic.RunAuthorization(cfg.experiment_id, "run-test-1",
                                  aic.bindings(changed, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap)),
                                  aic._GATE_TOKEN)
    with pytest.raises(runner.ExecutionBlocked, match="temperature is not set"):
        run(env, changed, forged, prov)
    assert prov.calls == []


def test_the_export_manifest_lists_the_temperatures_used(flow):
    env, cfg, auth, layout, by, _ = flow
    review_all(env, layout, by)
    assert export.export_dataset(layout, cfg, list(by.values()), clock=Clock())["temperatures"] == [0.0]


def test_the_dry_run_reports_temperature_polarity_and_retention_scope(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict())
    out = runner.dry_run(env.load(), env=env.process_env)
    assert out["temperature"] == 0.0 and out["polarity_option"] == P1
    ret = out["retention"]
    assert ret["retention_days"] == 30 and any("raw provider responses" in s for s in ret["not_enforced_for"])
    assert (out["provider_called"], out["data_sent"], out["files_written"]) == (False, False, False)


# ================================================================ the polarity decision is recorded, not made

def test_the_polarity_decision_must_be_recorded_before_anything_can_run(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"]["polarity_option"] = None
    env.write_cfg(env.approved(d))
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap),
                            confirm_ai_run=True, env=env.process_env)
    assert len(problems) == 1 and "polarity decision is yours" in problems[0]


@pytest.mark.parametrize("option", ["P2", "P3_not_collected", "unc_only", "", 1])
def test_an_unimplemented_polarity_option_is_refused(make_ai_env, option):
    env = make_ai_env()
    d = env.cfg_dict()
    d["protocol"]["polarity_option"] = option
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="polarity_option"):
        env.load()


def test_the_polarity_option_is_part_of_gate_a(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.approved(env.cfg_dict())
    d["protocol"]["polarity_option"] = None
    env.write_cfg(d)
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap),
                            confirm_ai_run=True, env=env.process_env)
    assert [p[5] for p in problems if p.startswith("gate ")] == ["A"]


def test_the_existing_polarity_rule_is_unchanged_and_applies_to_suggestions_and_reviews(make_ai_env):
    """Characterisation of the conflict reported in the approval package, not a decision: an R theme needs polarity."""
    from wealthpilot.data.gdelt.ai.schema import SourceItem, validate_output
    item = SourceItem("D0001", {"item_id": "D0001", "batch_date_utc": "2022-03-01", "source_domain": "example.com",
                                "url": "https://example.com/1", "title": "SYNTHETIC: Federal Reserve raises interest rates"},
                      "fp", False, "ORIGINAL", ())
    body = json.loads(make_ai_env().good("D0001"))
    body["pol_rates"] = ""
    v = validate_output(json.dumps(body), item)
    assert not v.ok and any("pol_rates is required" in e for e in v.errors)


@pytest.mark.parametrize("section,key", [("provider", "temprature"), ("provider", "enabled_model"), ("protocol", "polarity")])
def test_unknown_provider_and_protocol_keys_are_refused(make_ai_env, section, key):
    env = make_ai_env()
    d = env.cfg_dict()
    d[section][key] = 0
    env.write_cfg(d)
    with pytest.raises(ConfigError, match=f"unknown {section} keys"):
        env.load()


@pytest.mark.parametrize("run_id", ["../escape", "a b", "x" * 65, "-lead", "a/b", ""])
def test_a_run_id_that_names_a_file_must_be_safe(make_ai_env, monkeypatch, run_id):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["run_id"] = run_id
    env.write_cfg(env.approved(d))
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap),
                            confirm_ai_run=True, env=env.process_env)
    assert any("run_id" in p for p in problems)


# ================================================================ nothing was enabled

def test_the_shipped_build_is_still_locked_and_run_is_blocked_by_cli(make_ai_env, capsys):
    assert gdelt_pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False
    env = make_ai_env()
    env.write_cfg(env.approved(env.cfg_dict()))
    assert cli.main(["ai", "run", "--experiment", str(env.yaml_path), "--confirm-ai-run"]) == 3
    err = capsys.readouterr().err
    assert "build lock" in err and "no adapter exists" in err
    assert not env.dest.exists()
