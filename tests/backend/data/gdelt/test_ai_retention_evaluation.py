"""B2-U5: retention enforcement for AI-run artifacts and offline evaluation of the AI-assisted dataset. SYNTHETIC temporary
folders only. No model, no network, no real data, no sealed key. The build lock is lifted only inside a test."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import cli
from wealthpilot.data.gdelt.ai import chain, evaluation, export, queue, retention, reviewer, runner, store

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


def prepare(env, monkeypatch):
    env.enable(monkeypatch)
    env.write_cfg(env.approved(env.cfg_dict()))
    cfg = env.load()
    store.init_experiment(cfg)
    return cfg, env.authorize(cfg), store.Layout(env.dest)


def run(env, cfg, auth, prov):
    clock = Clock()
    return runner.run_suggestions(cfg, auth, prov, clock=clock, sleep=clock.sleep, env=env.process_env)


def review(layout, env, by, item_id, action, **kw):
    return reviewer.record_review(layout, items_by_id=by, protocol_id="option_B_all_items_ai_assisted",
                                  experiment_id="b2t_test_v1", blind_ids=frozenset(env.blind), item_id=item_id,
                                  action=action, reviewer_id="AB", now=T0 + timedelta(minutes=5), **kw)


def digest(root: Path, skip: tuple[str, ...] = ()) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and not any(p.relative_to(root).as_posix().startswith(s) for s in skip)}


# ================================================================ retention

@pytest.fixture()
def ran(make_ai_env, monkeypatch, scripted):
    env = make_ai_env()
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    items = store.load_snapshot_items(layout)
    queue.write_queue_csv(layout, queue.build_queue(items, layout, frozenset()))
    partial = layout.suggestions_raw.parent / "ai_suggestions_raw_v1.jsonl.partial-1"
    partial.write_bytes(b'{"half a raw provider response')
    return env, cfg, layout, partial


EXPIRABLE_PATHS = {"suggestions/ai_suggestions_valid_v1.csv", "queue/review_queue_v1.csv",
                   "suggestions/ai_suggestions_raw_v1.jsonl.partial-1"}


@pytest.mark.parametrize("good", [1, 30, 3650])
def test_valid_retention_days_are_accepted(good):
    assert retention.validate_retention_days(good) == good


@pytest.mark.parametrize("bad", [None, True, False, 0, -1, 3651, 30.5, "30", [30], float("nan")])
def test_invalid_retention_settings_are_refused_not_defaulted(bad):
    with pytest.raises(retention.RetentionError, match="retention_days must be"):
        retention.validate_retention_days(bad)


def test_the_default_is_a_dry_run_that_changes_nothing(ran):
    env, cfg, layout, partial = ran
    before = digest(layout.root)
    end, _ = retention.run_end(layout)
    out = retention.enforce(layout, 30, clock=lambda: end + timedelta(days=31))
    assert out["mode"] == "dry_run" and out["would_delete"] == 3 and "deleted" not in out
    assert {r["path"] for r in out["artifacts"]} == EXPIRABLE_PATHS and all(r["action"] == "delete" for r in out["artifacts"])
    assert digest(layout.root) == before                                      # not even an audit event was written


def test_nothing_expires_before_the_retention_period_ends(ran):
    env, cfg, layout, partial = ran
    end, _ = retention.run_end(layout)
    out = retention.enforce(layout, 30, confirm_delete=True, clock=lambda: end + timedelta(days=30) - timedelta(seconds=1))
    assert out["mode"] == "confirmed_nothing_expired" and out["would_delete"] == 0
    assert all(r["action"] == "keep" and "not expired" in r["reason"] for r in out["artifacts"])
    assert partial.exists() and layout.suggestions_valid.exists() and layout.queue.exists()


def test_confirmed_deletion_removes_only_the_designated_artifacts_and_records_it(ran):
    env, cfg, layout, partial = ran
    end, _ = retention.run_end(layout)
    protected_before = digest(layout.root, skip=("suggestions/ai_suggestions_valid", "queue/", "audit/events",
                                                 "suggestions/ai_suggestions_raw_v1.jsonl.partial"))
    source_before = digest(env.rf)
    out = retention.enforce(layout, 30, confirm_delete=True, clock=lambda: end + timedelta(days=30))
    assert out["mode"] == "deleted" and sorted(out["deleted"]) == sorted(EXPIRABLE_PATHS)
    assert not partial.exists() and not layout.suggestions_valid.exists() and not layout.queue.exists()
    protected_after = digest(layout.root, skip=("suggestions/ai_suggestions_valid", "queue/", "audit/events",
                                                "suggestions/ai_suggestions_raw_v1.jsonl.partial"))
    assert protected_after == protected_before                                # chains, snapshot, inputs, manifests intact
    assert digest(env.rf) == source_before                                    # the original files are never touched
    events = chain.ChainedJsonl(layout.audit).records()                       # the audit chain still verifies
    last = events[-1]
    assert last["event"] == "retention_deleted" and last["counts"] == {"deleted": 3} and sorted(last["detail"]) == sorted(EXPIRABLE_PATHS)
    again = retention.enforce(layout, 30, confirm_delete=True, clock=lambda: end + timedelta(days=60))
    assert again["mode"] == "confirmed_nothing_expired" and again["artifacts"] == []                    # idempotent


def test_the_raw_chain_reviews_and_audit_are_never_candidates(ran, scripted):
    env, cfg, layout, partial = ran
    by = {i.item_id: i for i in store.load_snapshot_items(layout)}
    review(layout, env, by, "D0001", "accept")
    end, _ = retention.run_end(layout)
    out = retention.plan(layout, 1, clock=lambda: end + timedelta(days=3650))
    listed = {r["path"] for r in out["artifacts"]}
    assert listed == EXPIRABLE_PATHS
    assert any("raw provider responses" in s for s in out["not_covered_by_retention"])
    retention.enforce(layout, 1, confirm_delete=True, clock=lambda: end + timedelta(days=3650))
    for p in (layout.suggestions_raw, layout.reviews, layout.audit, layout.snapshot_fingerprints, layout.historical_overlap,
              layout.inputs, layout.fingerprints, layout.run_manifest("run-test-1")):
        assert p.exists(), p.name
    assert len(store.SuggestionStore(layout).records()) == 6 and len(store.ReviewStore(layout).records()) == 1


def test_no_recorded_run_means_the_clock_has_not_started(make_ai_env):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    store.init_experiment(env.load())
    layout = store.Layout(env.dest)
    (layout.suggestions_valid).write_text("item_id\n", encoding="utf-8")
    out = retention.enforce(layout, 1, confirm_delete=True, clock=lambda: T0 + timedelta(days=9999))
    assert out["run_ended_at_utc"] is None and "no AI run is recorded" in out["clock_note"]
    assert layout.suggestions_valid.exists() and out["artifacts"][0]["action"] == "keep"


def test_an_unfinished_run_never_expires_anything(ran):
    env, cfg, layout, partial = ran
    store.AuditLog(layout).emit("run_started", now=T0 + timedelta(days=1), run_id="run-test-2")      # crashed, no end event
    out = retention.enforce(layout, 1, confirm_delete=True, clock=lambda: T0 + timedelta(days=9999))
    assert out["run_ended_at_utc"] is None and "has not finished" in out["clock_note"]
    assert partial.exists() and layout.suggestions_valid.exists()


def test_a_missing_or_invalid_end_time_never_expires_anything(ran):
    env, cfg, layout, partial = ran
    chain.ChainedJsonl(layout.audit).append({"event": "run_finished", "at_utc": "not a time"})
    out = retention.enforce(layout, 1, confirm_delete=True, clock=lambda: T0 + timedelta(days=9999))
    assert "missing or invalid" in out["clock_note"] and partial.exists() and layout.suggestions_valid.exists()
    chain.ChainedJsonl(layout.audit).append({"event": "run_stopped"})                                 # no time at all
    assert "missing or invalid" in retention.plan(layout, 1)["clock_note"]


def test_file_times_are_not_used_as_the_clock(ran):
    env, cfg, layout, partial = ran
    import os
    old = (T0 - timedelta(days=4000)).timestamp()
    os.utime(layout.suggestions_valid, (old, old))                           # an ancient file time changes nothing
    end, _ = retention.run_end(layout)
    out = retention.plan(layout, 30, clock=lambda: end + timedelta(days=1))
    assert all(r["action"] == "keep" for r in out["artifacts"])


def test_a_directory_in_place_of_an_expirable_file_is_never_touched(ran):
    env, cfg, layout, partial = ran
    layout.queue.unlink()
    layout.queue.mkdir()
    (layout.queue / "keep.txt").write_text("x", encoding="utf-8")
    end, _ = retention.run_end(layout)
    out = retention.enforce(layout, 1, confirm_delete=True, clock=lambda: end + timedelta(days=5))
    row = next(r for r in out["artifacts"] if r["path"] == "queue/review_queue_v1.csv")
    assert row["action"] == "keep" and "not a regular file" in row["reason"] and (layout.queue / "keep.txt").exists()


def test_a_folder_that_is_not_an_ai_experiment_is_refused_and_decoys_survive(tmp_path):
    decoys = {"annotation_A.csv": "a", "backup/annotation_A.build.csv": "b", "key_sealed.csv": "k",
              "suggestions/ai_suggestions_valid_v1.csv": "decoy", "queue/review_queue_v1.csv": "decoy"}
    for rel, text in decoys.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    before = digest(tmp_path)
    with pytest.raises(retention.RetentionError, match="not an AI experiment folder"):
        retention.enforce(store.Layout(tmp_path), 1, confirm_delete=True, clock=lambda: T0 + timedelta(days=9999))
    assert digest(tmp_path) == before


def test_the_original_review_folder_is_refused(make_ai_env):
    env = make_ai_env()
    before = digest(env.rf)
    with pytest.raises(retention.RetentionError, match="not an AI experiment folder"):
        retention.enforce(store.Layout(env.rf), 1, confirm_delete=True)
    assert digest(env.rf) == before


def test_invalid_retention_days_stop_before_anything_is_listed(ran):
    env, cfg, layout, partial = ran
    with pytest.raises(retention.RetentionError):
        retention.enforce(layout, 0, confirm_delete=True)
    assert partial.exists()


def test_a_tampered_audit_chain_stops_retention(ran):
    env, cfg, layout, partial = ran
    layout.audit.write_bytes(layout.audit.read_bytes().replace(b"run_finished", b"run_fxnished", 1))
    with pytest.raises(chain.ChainError):
        retention.enforce(layout, 1, confirm_delete=True, clock=lambda: T0 + timedelta(days=9999))
    assert partial.exists()


def test_cli_retention_is_a_dry_run_by_default(ran, capsys):
    env, cfg, layout, partial = ran
    assert cli.main(["ai", "retention", "--experiment", str(env.yaml_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "dry_run" and out["retention_days"] == 30 and partial.exists()


def test_cli_retention_without_an_experiment_folder_fails_without_creating_one(make_ai_env, capsys):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict())
    assert cli.main(["ai", "retention", "--experiment", str(env.yaml_path), "--confirm-delete"]) == 1
    assert "not an AI experiment folder" in capsys.readouterr().err and not env.dest.exists()


def test_cli_retention_rejects_an_unset_retention_setting(make_ai_env, capsys):
    env = make_ai_env()
    d = env.cfg_dict(filled=False)
    env.write_cfg(d)
    store.init_experiment(env.load())
    assert cli.main(["ai", "retention", "--experiment", str(env.yaml_path)]) == 1
    assert "retention_days must be" in capsys.readouterr().err


# ================================================================ evaluation

def provenance(ids=("D0002", "D0004"), **over):
    p = {"experiment_id": "b2t_test_v1", "selection_rule": "synthetic rule for tests", "item_ids": list(ids),
         "selection_fingerprint_sha256": evaluation.blind_subset_fingerprint(list(ids)),
         "committed_at_utc": "2026-10-19T11:00:00Z"}
    p.update(over)
    return p


@pytest.fixture()
def exported(make_ai_env, monkeypatch, scripted):
    """D0001, D0002, D0004 are original overlap items; D0002 and D0004 are the registered blind subset."""
    env = make_ai_env(overlap=("D0001", "D0002", "D0004"), blind=("D0002", "D0004"))
    cfg, auth, layout = prepare(env, monkeypatch)
    run(env, cfg, auth, scripted(default=lambda req: env.good(req.item_id)))
    by = {i.item_id: i for i in store.load_snapshot_items(layout)}
    review(layout, env, by, "D0002", "blind", labels={**BASE, "rel_rates": "RL", "pol_rates": ""})   # disagrees with the AI
    review(layout, env, by, "D0004", "blind", labels=BASE)                                            # agrees
    for iid in ("D0001", "D0003", "D0005", "D0006"):
        review(layout, env, by, iid, "accept")
    export.export_dataset(layout, cfg, list(by.values()), clock=Clock())
    rows, problems = evaluation.read_export(layout.export / "annotation_b2t_v1.csv")
    assert problems == []
    sug = store.SuggestionStore(layout)
    valid = {k: v for k, v in sug.terminal().items() if v["terminal_status"] == "valid"}
    ctx = dict(universe_ids=set(by), overlap_ids=frozenset(env.overlap), valid_suggestions=valid,
               first_suggestion_at=evaluation.first_suggestion_time(sug.records()), experiment_id="b2t_test_v1")
    return env, cfg, layout, rows, ctx


def ev(rows, ctx, prov=None, schema_problems=()):
    return evaluation.evaluate(rows, list(schema_problems), provenance=prov, **ctx)


def kinds(report):
    return set(report["problems_by_kind"])


def test_a_clean_dataset_passes_every_integrity_check(exported):
    env, cfg, layout, rows, ctx = exported
    r = ev(rows, ctx)
    assert r["integrity_ok"] and r["problems"] == [] and r["status"] == evaluation.STATUS
    assert r["universe_items"] == 6 and r["summary"]["records"] == 6


def test_the_summary_separates_human_only_ai_assisted_and_ai_exposed_labels(exported):
    env, cfg, layout, rows, ctx = exported
    s = ev(rows, ctx)["summary"]
    assert s["by_label_origin"] == {"human_blind": 2, "accepted_ai": 4}
    c = s["conditions"]
    assert c == {"human_only_no_ai_exposure": 2, "independent_human_candidates_blind": 2, "ai_assisted_accepted_or_edited": 4,
                 "ai_exposed_total": 4, "ai_exposed_other_after_seeing": 0}
    assert s["historical_overlap_items_ai_exposed"] == 1                     # D0001 is overlap and was seen
    assert s["acceptance_among_ai_exposed"]["n"] == 4 and s["acceptance_among_ai_exposed"]["wilson_95"] is not None
    assert "none is independent" in s["ai_exposed_note"]


def test_no_claims_of_agreement_quality_or_validity_are_made(exported):
    env, cfg, layout, rows, ctx = exported
    r = ev(rows, ctx, provenance())
    assert {"model quality", "research validity"} <= set(r["claims_not_made"])
    assert any("ambiguous" in d for d in r["decisions_required_before_statistical_evaluation"])
    assert any("polarity" in d for d in r["decisions_required_before_statistical_evaluation"])
    assert any("one human annotator" in s for s in r["limitations"]) and any("Wilson" in s for s in r["limitations"])
    text = json.dumps(r)
    assert "cohen_kappa" not in text and "gwet_ac1" not in text          # no unapproved statistic is computed


def test_without_provenance_no_blind_comparison_is_reported(exported):
    env, cfg, layout, rows, ctx = exported
    r = ev(rows, ctx)
    assert r["blind_comparison"]["valid"] is False and r["blind_comparison"]["comparison"] is None
    assert "no blind-subset provenance" in r["blind_comparison"]["problems"][0]


def test_a_validated_blind_subset_gives_counts_denominators_and_intervals(exported):
    env, cfg, layout, rows, ctx = exported
    c = ev(rows, ctx, provenance())["blind_comparison"]
    assert c["valid"] and "not accuracy" in c["note"]
    comp = c["comparison"]
    assert (comp["blind_items"], comp["with_valid_suggestion"], comp["without_valid_suggestion"]) == (2, 2, 0)
    rates = comp["per_field"]["rel_rates"]
    assert (rates["all_pairs"]["n"], rates["all_pairs"]["agree"], rates["all_pairs"]["raw_agreement"]) == (2, 1, 0.5)
    lo, hi = rates["all_pairs"]["wilson_95"]
    assert 0 < lo < 0.5 < hi < 1
    assert rates["excluding_pairs_with_A"]["n"] == 2 and rates["excluding_pairs_with_A"]["excluded"] == 0
    assert rates["excluding_pairs_with_A"]["reporting_floor"] == "counts_only"
    assert (rates["R_versus_not_R"]["n"], rates["R_versus_not_R"]["agree"]) == (2, 1)
    assert rates["confusion_human_rows_by_ai_cols"] == {"RL": {"R": 1}, "R": {"R": 1}}
    assert comp["per_field"]["rel_equity"]["all_pairs"]["agree"] == 2 and comp["per_field"]["company_notice"]["all_pairs"]["n"] == 2


def test_ambiguous_pairs_are_counted_and_excluded_only_in_the_stated_view(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(overlap=("D0002", "D0004"), blind=("D0002", "D0004"))
    cfg, auth, layout = prepare(env, monkeypatch)
    amb = env.good("D0002", rel_gold="A", amb_code="A1", uncertainty={"rel_equity": "low", "rel_rates": "low", "rel_gold": "high"})
    run(env, cfg, auth, scripted({"D0002": [amb]}, default=lambda req: env.good(req.item_id)))
    by = {i.item_id: i for i in store.load_snapshot_items(layout)}
    review(layout, env, by, "D0002", "blind", labels=BASE)
    review(layout, env, by, "D0004", "blind", labels=BASE)
    for iid in ("D0001", "D0003", "D0005", "D0006"):
        review(layout, env, by, iid, "accept")
    export.export_dataset(layout, cfg, list(by.values()), clock=Clock())
    rows, _ = evaluation.read_export(layout.export / "annotation_b2t_v1.csv")
    sug = store.SuggestionStore(layout)
    valid = {k: v for k, v in sug.terminal().items() if v["terminal_status"] == "valid"}
    ctx = dict(universe_ids=set(by), overlap_ids=frozenset(env.overlap), valid_suggestions=valid,
               first_suggestion_at=evaluation.first_suggestion_time(sug.records()), experiment_id="b2t_test_v1")
    gold = ev(rows, ctx, provenance())["blind_comparison"]["comparison"]["per_field"]["rel_gold"]
    assert gold["all_pairs"]["n"] == 2 and gold["all_pairs"]["agree"] == 1
    assert gold["excluding_pairs_with_A"]["n"] == 1 and gold["excluding_pairs_with_A"]["excluded"] == 1


@pytest.mark.parametrize("edit,fragment", [
    (lambda p: p.update(selection_fingerprint_sha256="0" * 64), "fingerprint does not match"),
    (lambda p: p.update(committed_at_utc="2026-10-19T13:00:00Z"), "not committed before the first AI suggestion"),
    (lambda p: p.update(committed_at_utc="yesterday"), "committed_at_utc is missing or not"),
    (lambda p: p.update(experiment_id="another"), "different experiment"),
    (lambda p: p.update(selection_rule=""), "must state the selection rule"),
    (lambda p: p.update(item_ids=["D0002", "D0002"]), "unique item IDs"),
    (lambda p: p.update(item_ids=[]), "unique item IDs"),
    (lambda p: p.pop("committed_at_utc"), "missing"),
    (lambda p: p.update(item_ids=["D0002", "D0003"], selection_fingerprint_sha256=evaluation.blind_subset_fingerprint(["D0002", "D0003"])),
     "must be original overlap items"),
    (lambda p: p.update(item_ids=["D0002"], selection_fingerprint_sha256=evaluation.blind_subset_fingerprint(["D0002"])),
     "labelled blind but is not in the registered subset")])
def test_invalid_blind_provenance_blocks_the_comparison(exported, edit, fragment):
    env, cfg, layout, rows, ctx = exported
    p = provenance()
    edit(p)
    c = ev(rows, ctx, p)["blind_comparison"]
    assert c["valid"] is False and c["comparison"] is None and any(fragment in x for x in c["problems"]), c["problems"]


def test_a_non_record_provenance_is_refused(exported):
    env, cfg, layout, rows, ctx = exported
    assert ev(rows, ctx, ["D0002"])["blind_comparison"]["valid"] is False


def test_an_ai_exposed_item_cannot_be_registered_as_blind(exported):
    env, cfg, layout, rows, ctx = exported
    p = provenance(("D0001", "D0002", "D0004"))                  # D0001 is an original overlap item that was AI-seen
    c = ev(rows, ctx, p)["blind_comparison"]
    assert c["valid"] is False and any("D0001 is not an unexposed blind label" in x for x in c["problems"])


def test_relabelling_an_exposed_row_as_blind_is_caught(exported):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    next(r for r in bad if r["item_id"] == "D0001")["label_origin"] = "human_blind"          # still ai_exposure = seen
    r = ev(bad, ctx, provenance())
    assert not r["integrity_ok"] and "origin_exposure_mismatch" in kinds(r)
    assert r["blind_comparison"]["valid"] is False and r["blind_comparison"]["comparison"] is None


def test_clearing_the_exposure_flag_of_an_accepted_row_is_caught(exported):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    row = next(r for r in bad if r["item_id"] == "D0003")
    row["ai_exposure"] = "none"
    r = ev(bad, ctx)
    assert {"origin_exposure_mismatch", "suggestion_ref_inconsistent"} <= kinds(r)


def test_a_blind_row_that_cites_a_suggestion_is_inconsistent(exported):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    next(r for r in bad if r["item_id"] == "D0002")["suggestion_ref"] = "0" * 64
    assert "suggestion_ref_inconsistent" in kinds(ev(bad, ctx))


def test_an_accepted_row_must_cite_its_own_valid_suggestion(exported):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    next(r for r in bad if r["item_id"] == "D0003")["suggestion_ref"] = "f" * 64
    next(r for r in bad if r["item_id"] == "D0005")["suggestion_ref"] = ""
    r = ev(bad, ctx)
    assert sum(p["kind"] == "suggestion_ref_inconsistent" for p in r["problems"]) == 2


def test_a_no_suggestion_label_is_refused_when_a_valid_suggestion_exists(exported):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    row = next(r for r in bad if r["item_id"] == "D0003")
    row.update(label_origin="human_no_suggestion", ai_exposure="none", suggestion_ref="")
    assert any("a valid suggestion exists" in p["detail"] for p in ev(bad, ctx)["problems"])


def test_duplicate_missing_and_unknown_records_are_reported_not_raised(exported):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    bad.append(copy.deepcopy(bad[0]))                                         # a duplicate record
    bad = [r for r in bad if r["item_id"] != "D0005"]                         # a missing record
    stray = copy.deepcopy(bad[1])
    stray["item_id"] = "D9999"                                                # an unknown item
    bad.append(stray)
    r = ev(bad, ctx)
    assert {"duplicate_item", "missing_item", "unknown_item"} <= kinds(r)
    assert [p["item_id"] for p in r["problems"] if p["kind"] == "missing_item"] == ["D0005"]
    assert r["blind_comparison"]["valid"] is False


@pytest.mark.parametrize("field,value,fragment", [
    ("rel_rates", "X", "must be R, RL, I or A"), ("pol_rates", "", "pol_rates is required"),
    ("company_notice", "Y", "never R"), ("amb_code", "A1", "amb_code must be blank"),
    ("annotator_type", "ai", "annotator_type must be 'human'"), ("insufficient_evidence", "maybe", "insufficient_evidence"),
    ("reviewed_at_utc", "", "reviewed_at_utc"), ("label_origin", "made_up", "unknown label_origin"),
    ("ai_exposure", "partly", "ai_exposure must be")])
def test_malformed_rows_are_reported_with_the_reason(exported, field, value, fragment):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    next(r for r in bad if r["item_id"] == "D0003")[field] = value
    r = ev(bad, ctx)
    assert not r["integrity_ok"] and any(fragment in p["detail"] for p in r["problems"]), r["problems"]


@pytest.mark.parametrize("ref", ["D9999", "D0003", "x"])
def test_invalid_duplicate_references_are_reported(exported, ref):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    next(r for r in bad if r["item_id"] == "D0003")["near_dup_of"] = ref
    assert "near_dup_invalid" in kinds(ev(bad, ctx))


def test_a_valid_duplicate_reference_is_counted(exported):
    env, cfg, layout, rows, ctx = exported
    ok = copy.deepcopy(rows)
    next(r for r in ok if r["item_id"] == "D0003")["near_dup_of"] = "D0005"
    r = ev(ok, ctx)
    assert r["integrity_ok"] and r["summary"]["near_dup_references"] == 1


def test_a_wrong_header_is_a_schema_problem_and_nothing_else_is_computed(exported, tmp_path):
    env, cfg, layout, rows, ctx = exported
    bad = tmp_path / "bad.csv"
    bad.write_text("item_id,rel_equity\nD0001,R\n", encoding="utf-8")
    got, problems = evaluation.read_export(bad)
    assert got == [] and problems[0]["kind"] == "schema"
    r = ev(got, ctx, provenance(), schema_problems=problems)
    assert r["summary"] is None and not r["integrity_ok"] and r["blind_comparison"]["valid"] is False


def test_an_unreadable_file_is_a_schema_problem(tmp_path):
    rows, problems = evaluation.read_export(tmp_path / "missing.csv")
    assert rows == [] and problems[0]["kind"] == "schema" and "cannot read" in problems[0]["detail"]


def test_integrity_problems_withhold_the_comparison(exported):
    env, cfg, layout, rows, ctx = exported
    bad = copy.deepcopy(rows)
    next(r for r in bad if r["item_id"] == "D0003")["rel_rates"] = "X"
    c = ev(bad, ctx, provenance())["blind_comparison"]
    assert c["valid"] is False and "integrity problems" in c["problems"][0]


def test_evaluation_changes_no_input_and_names_no_sealed_file(exported):
    env, cfg, layout, rows, ctx = exported
    before = digest(layout.root)
    ev(rows, ctx, provenance())
    assert digest(layout.root) == before
    assert "key_sealed" not in Path(evaluation.__file__).read_text(encoding="utf-8")


def test_the_blind_fingerprint_is_order_independent_and_content_sensitive():
    assert evaluation.blind_subset_fingerprint(["D0002", "D0001"]) == evaluation.blind_subset_fingerprint(["D0001", "D0002"])
    assert evaluation.blind_subset_fingerprint(["D0001"]) != evaluation.blind_subset_fingerprint(["D0002"])


def test_cli_evaluate_reads_the_export_and_validates_the_provenance(exported, tmp_path, capsys):
    env, cfg, layout, rows, ctx = exported
    path = tmp_path / "blind_provenance.json"
    path.write_text(json.dumps(provenance()), encoding="utf-8")
    assert cli.main(["ai", "evaluate", "--experiment", str(env.yaml_path), "--blind-provenance", str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["integrity_ok"] and out["blind_comparison"]["valid"] and out["status"] == evaluation.STATUS
    path.write_text(json.dumps(provenance(selection_fingerprint_sha256="0" * 64)), encoding="utf-8")
    assert cli.main(["ai", "evaluate", "--experiment", str(env.yaml_path), "--blind-provenance", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["blind_comparison"]["valid"] is False


def test_cli_evaluate_without_an_export_reports_the_problem_and_exits_1(make_ai_env, capsys):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    store.init_experiment(env.load())
    assert cli.main(["ai", "evaluate", "--experiment", str(env.yaml_path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["integrity_ok"] is False and out["problems"][0]["kind"] == "schema" and out["summary"] is None


def test_cli_evaluate_on_a_missing_experiment_fails_cleanly(make_ai_env, capsys):
    env = make_ai_env()
    env.write_cfg(env.cfg_dict(filled=False))
    assert cli.main(["ai", "evaluate", "--experiment", str(env.yaml_path)]) == 1
    assert not env.dest.exists()
