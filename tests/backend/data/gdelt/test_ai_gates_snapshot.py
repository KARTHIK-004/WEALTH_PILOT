"""AI-assisted annotation pipeline (built, DISABLED): config strictness, the four hash-bound gates, fail-closed
execution, dry run, CLI, and the snapshot of the original experiment. SYNTHETIC data; offline; no provider."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path

import pytest

import wealthpilot.data.gdelt as gdelt_pkg
from wealthpilot.data.gdelt import cli
from wealthpilot.data.gdelt.ai import config as aic
from wealthpilot.data.gdelt.ai import provider, runner, store
from wealthpilot.data.gdelt.errors import ConfigError


def _blockers(env, cfg, *, confirm=True, process_env=None):
    return aic.blockers(cfg, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap),
                        confirm_ai_run=confirm, env=env.process_env if process_env is None else process_env)


# ---------------------------------------------------------------- the shipped build is locked

def test_the_build_lock_is_false_and_no_adapter_exists():
    assert gdelt_pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False
    assert provider.ADAPTERS == {}


def test_a_fully_approved_config_is_still_blocked_by_the_build_lock_and_missing_adapter(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.approved(env.cfg_dict()))
    problems = _blockers(env, env.load())
    assert any("build lock" in p for p in problems) and any("no adapter exists" in p for p in problems)
    assert not any(p.startswith("gate ") for p in problems)              # the gates themselves are satisfied
    with pytest.raises(provider.ExecutionBlocked) as info:
        env.authorize(env.load())
    assert len(info.value.problems) == 2                                  # exactly the two code-level locks


def test_every_prerequisite_is_listed_not_just_the_first(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    problems = _blockers(env, env.load(), confirm=False, process_env={})
    text = "\n".join(problems)
    for needle in ("build lock", "--confirm-ai-run", "provider.name", "environment variable", "max_requests",
                   "max_input_tokens", "provider_data_terms_reviewed", "retention_days", "run_id is not set",
                   "gate A", "gate B", "gate C", "gate D"):
        assert needle in text, needle


# ---------------------------------------------------------------- gates are hash-bound and independent

def test_with_every_other_lock_lifted_the_gates_alone_allow_authorization(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    env.write_cfg(env.approved(env.cfg_dict()))
    cfg = env.load()
    assert _blockers(env, cfg) == []
    auth = env.authorize(cfg)
    assert aic.is_gate_issued(auth) and auth.run_id == "run-test-1" and set(auth.bindings) == set("ABCD")


def test_a_hand_made_authorization_is_not_gate_issued():
    assert not aic.is_gate_issued(aic.RunAuthorization("e", "r", {}))


@pytest.mark.parametrize("gate", ["A", "B", "C", "D"])
def test_a_missing_gate_blocks_and_approving_one_never_satisfies_another(make_ai_env, monkeypatch, gate):
    env = make_ai_env()
    env.enable(monkeypatch)
    others = tuple(g for g in "ABCD" if g != gate)
    env.write_cfg(env.approved(env.cfg_dict(), gates=others))
    problems = _blockers(env, env.load())
    assert [p for p in problems if p.startswith("gate ")] == [
        f"gate {gate} ({aic.GATE_NAMES[gate]}) has no approval record"]


def test_a_gate_bound_to_other_content_is_refused(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.approved(env.cfg_dict())
    d["approvals"]["B"]["binds_sha256"] = "0" * 64
    env.write_cfg(d)
    problems = _blockers(env, env.load())
    assert len(problems) == 1 and "gate B" in problems[0] and "different content" in problems[0]


@pytest.mark.parametrize("edit,invalidated", [
    (lambda d: d["provider"].update(model_id="fake-model-2"), "B"),
    (lambda d: d["provider"].update(model_version="2027-01-01"), "B"),
    (lambda d: d["data_handling"].update(retention_days=7), "C"),
    (lambda d: d["limits"].update(max_requests=99), "D"),
    (lambda d: d.update(run_id="run-test-2"), "D"),
    (lambda d: d["protocol"].update(blind_item_ids=["D0002"]), "A")])
def test_changing_the_configuration_after_approval_invalidates_exactly_the_matching_gate(make_ai_env, monkeypatch,
                                                                                         edit, invalidated):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.approved(env.cfg_dict())
    edit(d)
    env.write_cfg(d)
    gates = [p[5] for p in _blockers(env, env.load()) if p.startswith("gate ")]
    assert gates == [invalidated]


def test_changing_the_item_set_after_approval_invalidates_gate_d(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    env.write_cfg(env.approved(env.cfg_dict()))
    src = env.rf / "annotation_A.csv"
    src.write_bytes(src.read_bytes().replace(b"SYNTHETIC 3", b"SYNTHETIC three"))        # an item's text changed
    gates = [p[5] for p in _blockers(env, env.load()) if p.startswith("gate ")]
    assert gates == ["D"]


def test_a_changed_rubric_text_invalidates_gate_b(make_ai_env, monkeypatch):
    from wealthpilot.data.gdelt.ai import rubric as rub
    env = make_ai_env()
    env.enable(monkeypatch)
    env.write_cfg(env.approved(env.cfg_dict()))
    monkeypatch.setitem(rub.REGISTRY, "b2t_rubric_v1", "1" * 64)
    problems = _blockers(env, env.load())
    assert len(problems) == 1 and problems[0].startswith("rubric:")


def test_the_unconfirmed_run_flag_and_missing_credentials_variable_block(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    env.write_cfg(env.approved(env.cfg_dict()))
    assert any("--confirm-ai-run" in p for p in _blockers(env, env.load(), confirm=False))
    missing = _blockers(env, env.load(), process_env={})
    assert len(missing) == 1 and env.env_name in missing[0] and "never read" in missing[0]


def test_a_cost_cap_without_approved_pricing_blocks(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["limits"]["max_cost"] = 5.0
    env.write_cfg(env.approved(d))
    assert any("approved pricing" in p for p in _blockers(env, env.load()))


def test_only_the_approved_transmission_fields_are_allowed(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["data_handling"]["external_transmission_fields"].append("overlap_subset")
    env.write_cfg(env.approved(d))
    assert any("external_transmission_fields must be exactly" in p for p in _blockers(env, env.load()))


# ---------------------------------------------------------------- config strictness

@pytest.mark.parametrize("path,value", [(("enabled",), True), (("protocol", "auto_accept"), True),
                                        (("protocol", "auto_approve_below"), 0.9), (("provider", "enabled"), True)])
def test_enabled_and_automatic_acceptance_keys_are_refused(make_ai_env, path, value):
    env = make_ai_env()
    d = env.cfg_dict()
    target = d
    for k in path[:-1]:
        target = target[k]
    target[path[-1]] = value
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="refused"):
        env.load()


def test_human_review_of_every_item_cannot_be_switched_off(make_ai_env):
    env = make_ai_env()
    d = env.cfg_dict()
    d["protocol"]["review_required_for_every_item"] = False
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="human-reviewed"):
        env.load()


@pytest.mark.parametrize("value", ["sk-live-abc", "lowercase_name", "A", "has space", 12345])
def test_the_credentials_field_holds_a_variable_name_never_a_secret(make_ai_env, value):
    env = make_ai_env()
    d = env.cfg_dict()
    d["provider"]["credentials_env_var"] = value
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="NAME of an environment variable"):
        env.load()


def test_unknown_keys_and_malformed_files_are_refused(make_ai_env, tmp_path):
    env = make_ai_env()
    d = env.cfg_dict()
    env.write_cfg(d | {"surprise": 1})
    with pytest.raises(ConfigError, match="unknown config keys"):
        env.load()
    d["limits"]["max_dollars"] = 1
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="unknown limit keys"):
        env.load()
    (tmp_path / "bad.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        aic.load_experiment(tmp_path / "bad.yaml")
    with pytest.raises(ConfigError, match="cannot read"):
        aic.load_experiment(tmp_path / "absent.yaml")


@pytest.mark.parametrize("mutate,match", [
    (lambda a: a.update(approved_by="x@example.org"), "no email"),
    (lambda a: a.update(approved_on="2026-10-19"), "YYYY-MM-DD"),
    (lambda a: a.pop("reference"), "reference is required"),
    (lambda a: a.update(binds_sha256="abc"), "64-hex"),
    (lambda a: a.update(extra=1), "unknown keys")])
def test_approval_records_are_validated(make_ai_env, mutate, match):
    env = make_ai_env()
    d = env.approved(env.cfg_dict())
    mutate(d["approvals"]["A"])
    env.write_cfg(d)
    with pytest.raises(ConfigError, match=match):
        env.load()


def test_only_the_yaml_boolean_true_counts_as_approved(make_ai_env):
    env = make_ai_env()
    d = env.approved(env.cfg_dict())
    d["approvals"]["A"]["approved"] = "yes"
    env.write_cfg(d)
    assert "A" not in env.load().approvals
    assert set(env.load().approvals) == {"B", "C", "D"}


def test_an_unknown_gate_name_is_refused(make_ai_env):
    env = make_ai_env()
    d = env.cfg_dict()
    d["approvals"]["E"] = None
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="approvals may only be"):
        env.load()


# ---------------------------------------------------------------- dry run

def test_dry_run_plans_without_calling_a_provider_or_writing_anything(make_ai_env, monkeypatch):
    env = make_ai_env(unsendable=("D0005",))
    env.write_cfg(env.cfg_dict())
    before = sorted(p.relative_to(env.root).as_posix() for p in env.root.rglob("*"))
    called = []
    monkeypatch.setattr(provider.DisabledProvider, "suggest", lambda *a, **k: called.append(1))
    out = runner.dry_run(env.load(), env=env.process_env)
    assert sorted(p.relative_to(env.root).as_posix() for p in env.root.rglob("*")) == before    # nothing written
    assert called == [] and not env.dest.exists()
    assert (out["provider_called"], out["data_sent"], out["files_written"]) == (False, False, False)
    assert out["items"] == 6 and out["sendable_items"] == 5 and out["historical_overlap_items"] == 2
    assert out["items_never_sent"] == [{"item_id": "D0005", "problems": ["title contains control or format characters"]}]
    assert set(out["approval_bindings_to_approve"]) == set("ABCD") and out["estimates"]["cost_upper_bound"] is None
    assert any("build lock" in p for p in out["unmet_prerequisites"])
    assert env.secret not in json.dumps(out)


def test_dry_run_prices_only_when_unit_prices_are_supplied(make_ai_env):
    env = make_ai_env()
    d = env.cfg_dict()
    d["limits"].update(currency="XXX", unit_price_input_per_1k=0.001, unit_price_output_per_1k=0.002)
    env.write_cfg(d)
    out = runner.dry_run(env.load(), env=env.process_env)
    assert out["estimates"]["cost_upper_bound"] > 0 and out["estimates"]["currency"] == "XXX"


def test_dry_run_bindings_are_what_the_gates_must_bind(make_ai_env, monkeypatch):
    env = make_ai_env()
    env.enable(monkeypatch)
    env.write_cfg(env.cfg_dict())
    bind = runner.dry_run(env.load(), env=env.process_env)["approval_bindings_to_approve"]
    d = env.cfg_dict()
    d["approvals"] = {g: {"approved": True, "approved_by": "AB", "approved_on": __import__("datetime").date(2026, 10, 19),
                          "reference": "r", "binds_sha256": bind[g]} for g in "ABCD"}
    env.write_cfg(d)
    assert _blockers(env, env.load()) == []


# ---------------------------------------------------------------- CLI (fails closed, exit codes)

def test_cli_run_is_blocked_and_lists_problems_without_touching_anything(make_ai_env, capsys):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    rc = cli.main(["ai", "run", "--experiment", str(env.yaml_path), "--confirm-ai-run"])
    err = capsys.readouterr().err
    assert rc == 3 and err.startswith("BLOCKED:") and "build lock" in err and "gate A" in err
    assert not env.dest.exists()


def test_cli_run_stays_blocked_even_with_every_approval_in_place(make_ai_env, capsys):
    env = make_ai_env()
    env.write_cfg(env.approved(env.cfg_dict()))
    rc = cli.main(["ai", "run", "--experiment", str(env.yaml_path), "--confirm-ai-run"])
    assert rc == 3 and "build lock" in capsys.readouterr().err


def test_cli_dry_run_reports_and_exits_zero(make_ai_env, capsys):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    assert cli.main(["ai", "dry-run", "--experiment", str(env.yaml_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "dry_run" and out["provider_called"] is False and not env.dest.exists()


def test_cli_reports_config_errors_with_exit_2(make_ai_env, capsys):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict() | {"enabled": True})
    assert cli.main(["ai", "dry-run", "--experiment", str(env.yaml_path)]) == 2
    assert "CONFIG ERROR" in capsys.readouterr().err


def test_the_experiment_flag_is_required():
    with pytest.raises(SystemExit):
        cli.main(["ai", "run"])


# ---------------------------------------------------------------- init: snapshot of the ORIGINAL experiment

def _tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_init_snapshots_the_originals_and_leaves_the_source_byte_identical(make_ai_env):
    env = make_ai_env(blind=("D0002",))
    env.write_cfg(env.cfg_dict(filled=False))
    before = _tree_hashes(env.rf)
    summary = store.init_experiment(env.load())
    assert _tree_hashes(env.rf) == before                                         # the original folder is untouched
    assert summary["items"] == 6 and summary["historical_overlap"] == 2 and summary["blind_items"] == 1
    layout = store.Layout(env.dest)
    ids, b_sha = store.historical_overlap_ids(layout)
    assert ids == frozenset(env.overlap) and b_sha == env.sha("annotation_B.csv")  # original overlap kept as provenance
    note = json.loads(layout.historical_overlap.read_text(encoding="utf-8"))["note"]
    assert "NOT" not in note and "independent human labels" in note
    for rel in ("annotation_A.csv", "annotation_B.csv", "selection_log.json"):
        assert (layout.snapshot / rel).read_bytes() == (env.rf / rel).read_bytes()
        assert not os.access(layout.snapshot / rel, os.W_OK) or sys.platform == "win32" and not (
            (layout.snapshot / rel).stat().st_mode & stat.S_IWRITE)
    rec = json.loads(layout.snapshot_fingerprints.read_text(encoding="utf-8"))
    assert rec["files"]["working/annotation_A.working.csv"]["as_of_snapshot_only"] is True
    assert rec["files"]["annotation_A.csv"]["immutable_original"] is True
    assert "sealed_key" in rec and not any("key_sealed" in k for k in rec["files"])
    assert not any("key_sealed" in p.name for p in layout.root.rglob("*"))
    assert store.verify_snapshot(env.load()) is None


def test_init_never_reuses_a_destination(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    store.init_experiment(env.load())
    with pytest.raises(store.StoreError, match="already exists"):
        store.init_experiment(env.load())


def test_init_refuses_a_source_that_no_longer_matches_its_recorded_fingerprint(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    src = env.rf / "annotation_A.csv"
    src.write_bytes(src.read_bytes().replace(b"SYNTHETIC 2", b"EDITED 2"))
    with pytest.raises(store.StoreError, match="does not match the fingerprint"):
        store.init_experiment(env.load())
    assert not env.dest.exists()


def test_init_refuses_labelled_sources_and_blind_items_outside_the_original_overlap(make_ai_env):
    env = make_ai_env(blind=("D0001",))                                  # D0001 was NOT in the original overlap
    env.write_cfg(env.cfg_dict(filled=False))
    with pytest.raises(store.StoreError, match="must be original overlap items"):
        store.init_experiment(env.load())
    env2 = make_ai_env()
    env2.write_cfg(env2.cfg_dict(filled=False))
    src = env2.rf / "annotation_A.csv"
    text = src.read_text(encoding="utf-8").splitlines()
    cols = text[0].split(",")
    row = text[1].split(",")
    row[cols.index("rel_equity")] = "R"
    src.write_text("\n".join([text[0], ",".join(row), *text[2:]]) + "\n", encoding="utf-8")
    log = json.loads((env2.rf / "selection_log.json").read_text())
    log["files_sha256"]["annotation_A.csv"] = hashlib.sha256(src.read_bytes()).hexdigest()
    (env2.rf / "selection_log.json").write_text(json.dumps(log), encoding="utf-8")
    with pytest.raises(Exception, match="contains labels"):
        store.init_experiment(env2.load())


def test_init_requires_b_to_equal_the_original_overlap(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    b = env.rf / "annotation_B.csv"
    lines = b.read_text(encoding="utf-8").splitlines()
    b.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")         # drop one overlap row
    log = json.loads((env.rf / "selection_log.json").read_text())
    log["files_sha256"]["annotation_B.csv"] = hashlib.sha256(b.read_bytes()).hexdigest()
    (env.rf / "selection_log.json").write_text(json.dumps(log), encoding="utf-8")
    with pytest.raises(store.StoreError, match="does not match the overlap"):
        store.init_experiment(env.load())


def test_verify_snapshot_detects_a_changed_snapshot_copy_and_a_changed_original(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    store.init_experiment(env.load())
    layout = store.Layout(env.dest)
    orig = env.rf / "annotation_A.csv"
    orig.write_bytes(orig.read_bytes() + b"\n")
    with pytest.raises(store.StoreError, match="ORIGINAL file changed"):
        store.verify_snapshot(env.load())
    orig.write_bytes((layout.snapshot / "annotation_A.csv").read_bytes())
    os.chmod(layout.snapshot / "annotation_A.csv", 0o666)
    (layout.snapshot / "annotation_A.csv").write_bytes(b"tampered")
    with pytest.raises(store.StoreError, match="snapshot copy changed"):
        store.verify_snapshot(env.load())


def test_verify_snapshot_without_init_says_so(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    with pytest.raises(store.StoreError, match="no snapshot"):
        store.verify_snapshot(env.load())


def test_snapshot_items_are_checked_against_the_recorded_fingerprints(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    store.init_experiment(env.load())
    layout = store.Layout(env.dest)
    assert [i.item_id for i in store.load_snapshot_items(layout)] == env.ids
    os.chmod(layout.inputs, 0o666)
    lines = layout.inputs.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["fingerprint"] = "0" * 64
    layout.inputs.write_text("\n".join([json.dumps(rec), *lines[1:]]) + "\n", encoding="utf-8")
    with pytest.raises(store.StoreError, match="fingerprints differ"):
        store.load_snapshot_items(layout)


def test_the_audit_log_refuses_free_text_keys(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    store.init_experiment(env.load())
    with pytest.raises(store.StoreError, match="audit keys not allowed"):
        store.AuditLog(store.Layout(env.dest)).emit("x", title="a headline")
    events = store.ChainedJsonl(store.Layout(env.dest).audit).records()
    assert events[0]["event"] == "experiment_initialized"


def test_the_pipeline_never_names_the_sealed_key_or_reads_working_labels():
    root = Path(gdelt_pkg.__file__).parent / "ai"
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "key_sealed" not in text, py.name
        assert "load_working" not in text and "_working_rows" not in text, py.name
