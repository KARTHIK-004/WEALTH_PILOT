"""B2-U18: rule-based validation, the AI-only suggestion store, and the metric-status report. SYNTHETIC fixtures only.

No provider, network, real label, real headline or sealed key is involved (the ``_no_network`` fixture blocks sockets).
Everything here shows that model output can never become an independent reference and that, with no independent labels, no
accuracy metric is available and the decision is INSUFFICIENT_EVIDENCE.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import ai_only, annotate, annotation_rules as ar, decision, metric_status, provenance
from wealthpilot.data.gdelt import evaluate as ev
from wealthpilot.data.gdelt.ai.chain import ChainError
from wealthpilot.data.gdelt.annotate import AnnotationError, Paths
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

REPO = Path(__file__).resolve().parents[4]
PKG = REPO / "backend/wealthpilot/data/gdelt"
CFG = "c" * 64
BASE = {"rel_equity": "I", "rel_rates": "R", "rel_gold": "I", "amb_code": "", "company_notice": "N",
        "pol_equity": "", "pol_rates": "NEG", "pol_gold": "", "near_dup_of": "", "note": ""}


def row(item_id="D0001", **over):
    r = {"item_id": item_id, **{c: "" for c in annotate.LABEL_COLUMNS}, **BASE, "annotator_id": "AB", "annotator_type": "human",
         "label_basis": "own", "labelled_at_utc": "2026-10-20T09:00:00Z"}
    r.update(over)
    return r


def kinds(rep) -> set[str]:
    return rep.kinds


# ================================================================ 1. rule-based validation

def test_a_valid_human_row_passes():
    assert ar.check_rows([row()], expected_ids={"D0001"}).ok


@pytest.mark.parametrize("over,kind", [
    ({"rel_gold": "X"}, "enum_invalid"), ({"company_notice": "Q"}, "enum_invalid"), ({"amb_code": "Z9"}, "enum_invalid"),
    ({"pol_rates": "GREAT"}, "enum_invalid"), ({"pol_rates": ""}, "polarity_missing"),
    ({"pol_gold": "POS"}, "polarity_unexpected"), ({"rel_equity": "A"}, "amb_missing"),
    ({"amb_code": "A1"}, "amb_unexpected"), ({"company_notice": "Y"}, "company_conflict"),
    ({"near_dup_of": "D0001"}, "near_dup_self"), ({"near_dup_of": "D9999"}, "near_dup_unknown"),
    ({"near_dup_of": "dup"}, "near_dup_malformed"),
])
def test_label_rule_violations_are_named(over, kind):
    assert kind in kinds(ar.check_rows([row(**over)], expected_ids={"D0001", "D0002"}))


def test_a_polarity_rule_holds_for_every_relevant_theme():
    for theme, pol in (("rel_equity", "pol_equity"), ("rel_rates", "pol_rates"), ("rel_gold", "pol_gold")):
        neutral = {"rel_equity": "I", "rel_rates": "I", "rel_gold": "I", "pol_equity": "", "pol_rates": "", "pol_gold": ""}
        r = row(**{**neutral, theme: "R", pol: ""})
        assert "polarity_missing" in kinds(ar.check_rows([r], expected_ids={"D0001"}))
        ok = row(**{**neutral, theme: "R", pol: "UNC"})
        assert ar.check_rows([ok], expected_ids={"D0001"}).ok


def test_duplicate_missing_unknown_and_malformed_ids_are_reported():
    rows = [row("D0001"), row("D0001"), row("D0003"), row("bad")]
    rep = ar.check_rows(rows, expected_ids={"D0001", "D0002", "D0003"})
    assert {"duplicate_item", "missing_item", "unknown_item", "malformed_item_id"} <= kinds(rep)


def test_circular_duplicate_references_are_contradictory():
    rows = [row("D0001", near_dup_of="D0002"), row("D0002", near_dup_of="D0001")]
    assert "near_dup_cycle" in kinds(ar.check_rows(rows, expected_ids={"D0001", "D0002"}))
    chain = [row("D0001", near_dup_of="D0002"), row("D0002", near_dup_of="D0003"), row("D0003")]
    assert "near_dup_cycle" not in kinds(ar.check_rows(chain, expected_ids={"D0001", "D0002", "D0003"}))


def test_provenance_consistency_source_fields_and_overlap_membership():
    src = {c: "orig" for c in annotate.SOURCE_COLUMNS if c != "item_id"}
    original = {"D0001": {**src, "item_id": "D0001", "overlap_subset": "N"}}
    r = row(**{**src, "overlap_subset": "N"})
    assert ar.check_rows([r], expected_ids={"D0001"}, originals=original, overlap_ids=set()).ok
    changed = row(**{**src, "title": "CHANGED", "overlap_subset": "N"})
    assert "source_changed" in kinds(ar.check_rows([changed], expected_ids={"D0001"}, originals=original))
    flagged = row(**{**src, "overlap_subset": "Y"})
    assert "membership_conflict" in kinds(ar.check_rows([flagged], expected_ids={"D0001"}, originals=original, overlap_ids=set()))


@pytest.mark.parametrize("over,kind", [
    ({"annotator_type": "ai"}, "ai_only_contamination"), ({"label_basis": "ai_only"}, "ai_only_contamination"),
    ({"annotator_type": "robot"}, "non_human_annotator"), ({"annotator_type": ""}, "non_human_annotator"),
    ({"label_basis": "guess"}, "basis_invalid"), ({"annotator_id": ""}, "annotator_missing")])
def test_human_reference_rows_cannot_carry_a_model_or_unknown_origin(over, kind):
    assert kind in kinds(ar.check_rows([row(**over)], expected_ids={"D0001"}))


def test_only_labelled_skips_rows_that_are_not_labelled_yet():
    empty = {"item_id": "D0001", **{c: "" for c in annotate.LABEL_COLUMNS}}
    assert ar.check_rows([empty], expected_ids={"D0001"}, only_labelled=True).ok
    assert not ar.check_rows([empty], expected_ids={"D0001"}).ok


# ================================================================ 2. the AI-only schema, store and ingestion

@pytest.fixture()
def items(make_ai_env):
    env = make_ai_env(n=6, overlap=("D0002",))
    by = {i.item_id: i for i in env.source_items()}
    return env, by


_UNSET = object()


def ingest(store, env, by, item_id="D0001", raw=_UNSET, **kw):
    raw = env.good(item_id) if raw is _UNSET else raw
    return store.ingest(raw, by[item_id], by, model_id="claude-haiku-5-5", prompt_version="b2t_prompt_v1", config_sha256=CFG, **kw)


def test_a_valid_response_is_stored_as_a_non_independent_ai_only_suggestion(tmp_path, items):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    res = ingest(store, env, by)
    assert res.accepted and not res.duplicate
    rec = res.record
    assert (rec["schema"], rec["origin"], rec["independent"], rec["annotator_type"]) == \
        ("b2_ai_only_suggestion_v1", "ai_only", False, "ai")
    assert rec["statement"] == ai_only.NON_INDEPENDENT and "NOT an independent label" in rec["statement"]
    assert rec["raw_response_sha256"] == hashlib.sha256(env.good("D0001").encode()).hexdigest()
    assert "raw_response" not in rec and "evidence_excerpts" not in json.dumps(rec)            # the text is not stored
    assert len(store.records(by)) == 1


@pytest.mark.parametrize("raw,part", [
    ("not json", "not a single JSON object"), ("[1]", "not a single JSON object"), ("{}", "missing fields"),
    ("", "not a single JSON object"), (None, "not text")])
def test_malformed_output_is_rejected_and_nothing_is_stored(tmp_path, items, raw, part):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    res = ingest(store, env, by, raw=raw)
    assert not res.accepted and any(part in e for e in res.errors) and res.record is None
    assert store.records(by) == []


def _good(env, item_id="D0001", **over):
    body = json.loads(env.good(item_id))
    body.update(over)
    return json.dumps(body)


@pytest.mark.parametrize("over,part", [
    ({"pol_rates": ""}, "pol_rates"),                                   # invalid polarity: R without polarity
    ({"pol_rates": "GREAT"}, "pol_rates"),
    ({"pol_equity": "POS"}, "pol_equity"),                               # polarity on a non-relevant theme
    ({"company_notice": "Y"}, "company"),                                # contradictory: a notice labelled relevant
    ({"insufficient_evidence": True}, "insufficient_evidence"),          # contradictory: no theme labelled A
    ({"rel_gold": "X"}, "rel_gold"), ({"item_id": "D0003"}, "does not match"),
    ({"evidence_excerpts": []}, "evidence excerpt"), ({"extra": 1}, "unexpected fields"),
    ({"evidence_basis": "full_article"}, "evidence_basis"), ({"amb_code": "A1"}, "amb_code")])
def test_invalid_or_contradictory_labels_are_rejected(tmp_path, items, over, part):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    res = ingest(store, env, by, raw=_good(env, **over))
    assert not res.accepted and any(part in e for e in res.errors), res.errors
    assert store.records(by) == []


def test_a_response_missing_a_field_is_rejected(tmp_path, items):
    env, by = items
    body = json.loads(env.good("D0001"))
    body.pop("company_notice")
    res = ingest(ai_only.AiOnlyStore(tmp_path / "ai_only" / "x"), env, by, raw=json.dumps(body))
    assert not res.accepted and any("missing fields" in e for e in res.errors)


def test_an_overlap_item_never_gets_an_ai_only_suggestion(tmp_path, items):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    res = ingest(store, env, by, item_id="D0002")
    assert not res.accepted and any("overlap" in e for e in res.errors) and store.records(by) == []


def test_an_unsendable_item_or_an_unknown_item_is_refused(tmp_path, make_ai_env):
    env = make_ai_env(n=4, overlap=("D0002",), unsendable=("D0003",))
    by = {i.item_id: i for i in env.source_items()}
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    assert not store.ingest(env.good("D0003"), by["D0003"], by, model_id="m", prompt_version="v", config_sha256=CFG).accepted
    other = copy.copy(by["D0001"])
    ghost = type(other)("D9999", other.fields, other.fingerprint, False, "ORIGINAL")
    assert not store.ingest(env.good("D0001"), ghost, by, model_id="m", prompt_version="v", config_sha256=CFG).accepted


def test_ingestion_is_idempotent_and_a_resume_adds_nothing(tmp_path, items):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    first = ingest(store, env, by)
    again = ingest(store, env, by)
    assert first.accepted and again.accepted and again.duplicate and again.record == first.record
    assert len(store.records(by)) == 1
    changed = ingest(store, env, by, raw=_good(env, note="a different note"))                     # a different output: a new record
    assert changed.accepted and not changed.duplicate and len(store.records(by)) == 2


def test_the_store_chain_detects_tampering_and_re_reads_every_record(tmp_path, items):
    env, by = items
    root = tmp_path / "ai_only" / "exp"
    store = ai_only.AiOnlyStore(root)
    ingest(store, env, by)
    path = root / ai_only.FILE_NAME
    path.write_bytes(path.read_bytes().replace(b'"independent": false', b'"independent": true', 1))
    with pytest.raises(ChainError):
        ai_only.AiOnlyStore(root).records(by)


def test_a_forged_record_that_claims_independence_is_refused_on_write(tmp_path, items):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    rec = dict(ingest(store, env, by).record)
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    for field, value in (("independent", True), ("origin", "human_only"), ("annotator_type", "human"),
                         ("statement", "this is a human label"), ("schema", "b2t_review_v1")):
        bad = {**rec, field: value}
        with pytest.raises(ai_only.AiOnlyError):
            store.append(bad, by)
    bad = {**rec, "labels": {**rec["labels"], "rel_gold": "R"}}                       # labels changed, hash not
    with pytest.raises(ai_only.AiOnlyError, match="output_sha256"):
        store.append(bad, by)
    bad = {**rec, "item_id": "D0002"}                                                  # an overlap item
    with pytest.raises(ai_only.AiOnlyError, match="overlap"):
        store.append(bad, by)
    bad = {**rec, "input_fingerprint": "f" * 64}
    with pytest.raises(ai_only.AiOnlyError, match="different input"):
        store.append(bad, by)
    bad = {**rec, "extra": 1}
    with pytest.raises(ai_only.AiOnlyError, match="fields differ"):
        store.append(bad, by)


def test_a_record_with_a_self_or_unknown_duplicate_reference_is_refused(tmp_path, items):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    rec = dict(ingest(store, env, by).record)
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    for ref, kind in (("D0001", "near_dup_self"), ("D9999", "near_dup_unknown"), ("zz", "near_dup_malformed")):
        labels = {**rec["labels"], "near_dup_of": ref}
        bad = {**rec, "labels": labels, "output_sha256": ai_only.output_hash(labels)}
        with pytest.raises(ai_only.AiOnlyError, match=kind):
            store.append(bad, by)


# ================================================================ 3. strict separation from the human reference

def test_the_store_refuses_any_location_inside_or_beside_a_review_folder(tmp_path, make_ai_env):
    env = make_ai_env(n=3)
    for bad in (env.rf, env.rf / "ai_only", env.rf / "working" / "x", env.rf.parent / "review_files" / "ai_only"):
        with pytest.raises(ai_only.AiOnlyError, match="review folder"):
            ai_only.AiOnlyStore(bad)
    (tmp_path / "hold").mkdir()
    ai_only.AiOnlyStore(tmp_path / "hold" / "ai_only")                                  # a separate location is fine


def test_the_default_location_is_outside_the_review_folder(tmp_path):
    root = ai_only.default_root(tmp_path / "english_gkg_v1", "exp-1")
    assert root == tmp_path / "english_gkg_v1" / "ai_only" / "exp-1" and "review" not in root.parts
    with pytest.raises(ai_only.AiOnlyError):
        ai_only.default_root(tmp_path, "../escape")


def _import_lines(path: Path) -> str:
    return "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith(("import ", "from ")))


def test_no_evaluation_or_reference_module_imports_the_ai_only_store_and_it_imports_none_of_them():
    for name in ("evaluate.py", "annotate.py", "provenance.py", "ai_bridge.py", "ai_origin.py", "overlap_lock.py", "decision.py",
                 "estimators.py", "labeller.py", "ai/export.py", "ai/runner.py", "ai/reviewer.py", "annotation_rules.py"):
        assert "ai_only" not in _import_lines(PKG / name), name
        assert "import ai_only" not in (PKG / name).read_text(encoding="utf-8"), name
    imports = _import_lines(PKG / "ai_only.py")
    for forbidden in ("evaluate", "ai_bridge", "ai_origin", "overlap_lock", "provenance", "labeller", "review", "metric_status",
                      "runner", "cli", "urllib", "socket", "requests"):
        assert forbidden not in imports, forbidden
    text = (PKG / "ai_only.py").read_text(encoding="utf-8")
    for forbidden in ("_working_rows", "Paths(", "save_item", "key_sealed", "annotation_A.working", "atomic_write"):
        assert forbidden not in text, forbidden


def test_the_store_never_writes_outside_its_own_folder(tmp_path, items):
    env, by = items
    before = {str(f): f.stat().st_mtime_ns for f in env.root.rglob("*") if f.is_file()}
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "exp")
    ingest(store, env, by)
    assert {str(f): f.stat().st_mtime_ns for f in env.root.rglob("*") if f.is_file()} == before     # the review folder is untouched
    assert sorted(p.name for p in (tmp_path / "ai_only" / "exp").iterdir()) == [ai_only.FILE_NAME]


# ---- a small labelled folder for the provenance and freeze checks

def _csv(columns, rows) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def logged_write(p: Paths, working) -> None:
    data = annotate._csv_bytes(ANNOTATION_COLUMNS, working)
    p.working.write_bytes(data)
    annotate._log(p, {"event": "label", "working_sha256": hashlib.sha256(data).hexdigest()})


def folder(root: Path, *, labelled: bool = True, n: int = 8, overlap=("D0002",)) -> Paths:
    rf = root / "review_files"
    rf.mkdir(parents=True)
    rows, keys = [], []
    for i in range(1, n + 1):
        iid = f"D{i:04d}"
        rows.append({"item_id": iid, "gkg_record_id": f"2022-{i}", "batch_ts": "20220301120000", "batch_date_utc": "2022-03-01",
                     "available_at_utc": "2022-03-01T12:15:00Z", "source_domain": "example.com", "url": f"https://example.com/{i}",
                     "title": f"SYNTHETIC ROW {i}", "mech_dup": "ORIGINAL", "overlap_subset": "Y" if iid in overlap else "N"})
        keys.append({"item_id": iid, "gkg_record_id": f"2022-{i}", "batch_ts": "20220301120000", "cell": "C1", "cell_rows": n,
                     "cell_items": n, "member_equity_us": 0, "member_rates_us": 0, "member_gold": 1})
    original = _csv(ANNOTATION_COLUMNS, rows)
    manifest = _csv(ANNOTATION_COLUMNS, [r for r in rows if r["overlap_subset"] == "Y"])
    key = _csv(list(keys[0]), keys)
    (rf / "annotation_A.csv").write_bytes(original)
    (rf / "annotation_B.csv").write_bytes(manifest)
    (rf / "key_sealed.csv").write_bytes(key)
    (rf / "selection_log.json").write_text(json.dumps({"files_sha256": {
        "annotation_A.csv": hashlib.sha256(original).hexdigest(), "annotation_B.csv": hashlib.sha256(manifest).hexdigest(),
        "key_sealed.csv": hashlib.sha256(key).hexdigest()}}), encoding="utf-8")
    p = Paths(rf)
    annotate.init(p)
    if labelled:
        working = annotate._working_rows(p)
        for r in working:
            r.update({"rel_equity": "I", "rel_rates": "I", "rel_gold": "R", "company_notice": "N", "pol_gold": "POS",
                      "annotator_id": "AB", "annotator_type": "human", "label_basis": "own", "labelled_at_utc": "2026-10-20T09:00:00Z"})
        logged_write(p, working)
    return p


@pytest.fixture()
def no_key_reads(monkeypatch):
    calls = []
    monkeypatch.setattr(ev, "_read_key", lambda p: calls.append(1) or pytest.fail("the sealed key was read"))
    return calls


def test_an_ai_only_label_in_the_working_copy_blocks_provenance_and_the_freeze(tmp_path, no_key_reads):
    p = folder(tmp_path)
    working = annotate._working_rows(p)
    working[2]["label_basis"] = "ai_only"
    logged_write(p, working)
    rep = provenance.verify(p)
    assert not rep.ok and "ai_only_contamination" in {x["kind"] for x in rep.problems}
    with pytest.raises(AnnotationError):
        ev.freeze(p)
    assert not ev.freeze_path(p).exists() and no_key_reads == []


def test_an_ai_annotator_or_missing_annotator_type_blocks_provenance(tmp_path):
    for value, kind in (("ai", "ai_only_contamination"), ("", "non_human_annotator"), ("robot", "non_human_annotator")):
        p = folder(tmp_path / value.replace("", "x") / "f")
        working = annotate._working_rows(p)
        working[3]["annotator_type"] = value
        logged_write(p, working)
        assert kind in {x["kind"] for x in provenance.verify(p).problems}


def test_a_provenance_mismatch_blocks_the_metric_status_as_invalid(tmp_path):
    p = folder(tmp_path)
    working = annotate._working_rows(p)
    working[0]["title"] = "CHANGED"
    p.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, working))                 # outside the logged workflow
    rep = metric_status.report(p)
    assert rep["overall_status"] == "invalid_provenance"
    assert all(m["status"] == "invalid_provenance" and not m["computable"] for m in rep["metrics"].values())
    assert {d["outcome"] for d in rep["decision_by_series"].values()} == {"INVALID_EVALUATION"}


def test_pointing_the_freeze_at_an_ai_only_store_changes_nothing(tmp_path, items, no_key_reads):
    env, by = items
    store = ai_only.AiOnlyStore(tmp_path / "ai_only" / "export")                             # even a directory named "export"
    ingest(store, env, by)
    p = folder(tmp_path / "ref", labelled=False)
    with pytest.raises(AnnotationError, match="cannot freeze"):
        ev.freeze(p, tmp_path / "ai_only" / "export")
    assert not ev.freeze_path(p).exists() and no_key_reads == []


# ================================================================ 4 and 5. metric status and the decision

def test_with_no_labels_every_accuracy_metric_is_unavailable_and_every_decision_is_insufficient(tmp_path):
    p = folder(tmp_path, labelled=False)
    rep = metric_status.report(p)
    assert rep["overall_status"] == "unavailable" and rep["reads_sealed_key"] is False and rep["writes_files"] is False
    assert set(rep["metrics"]) == {"precision", "bootstrap_lower_bound", "pooled_recall", "capture_recall", "reporting_floor",
                                   "unique_story_precision", "per_cell_wilson"}
    for m in rep["metrics"].values():
        assert m["status"] == "unavailable" and not m["independent_labels_available"] and not m["computable"]
        assert not m["uncertainty_defensible"] and not m["authoritative_decision_permitted"]
        assert m["estimand"] and m["data_required"] and m["limitation"]
    for s, d in rep["decision_by_series"].items():
        assert d["outcome"] == "INSUFFICIENT_EVIDENCE" and d["authoritative"] is False and not d["authorizes_execution_or_deployment"]
    assert "not independent evidence" in rep["statement"]


def test_perfect_ai_only_suggestions_do_not_create_an_accuracy_result(tmp_path, items):
    env, by = items
    root = tmp_path / "ai_only" / "exp"
    store = ai_only.AiOnlyStore(root)
    for i in ("D0001", "D0003", "D0004", "D0005", "D0006"):
        assert ingest(store, env, by, item_id=i).accepted
    p = Paths(env.rf)                                        # the reference folder these items came from (no labels)
    rep = metric_status.report(p, ai_only_root=root)
    ao = rep["evidence"]["ai_only"]
    assert ao["records"] == 5 and ao["role"] == "exploratory_only" and ao["independent"] is False and ao["valid"] is True
    assert ao["kind"] == "diagnostic_only" and "ambiguity_rate" in ao
    assert rep["evidence"]["independent_human_only_labelled"] == 0 and rep["overall_status"] == "unavailable"
    assert all(d["outcome"] == "INSUFFICIENT_EVIDENCE" for d in rep["decision_by_series"].values())
    assert all(not m["computable"] and not m["authoritative_decision_permitted"] for m in rep["metrics"].values())


def test_a_corrupt_ai_only_store_is_reported_not_trusted(tmp_path, items):
    env, by = items
    root = tmp_path / "ai_only" / "exp"
    ingest(ai_only.AiOnlyStore(root), env, by)
    path = root / ai_only.FILE_NAME
    path.write_bytes(path.read_bytes().replace(b"claude-haiku-5-5", b"someone-else", 1))
    rep = metric_status.report(Paths(env.rf), ai_only_root=root)
    assert rep["evidence"]["ai_only"]["valid"] is False and "ChainError" in rep["evidence"]["ai_only"]["problem"]
    assert rep["overall_status"] == "unavailable"


def test_ai_exposed_labels_alone_are_not_independent_evidence(tmp_path):
    p = folder(tmp_path, n=6, overlap=("D0002",), labelled=False)
    working = annotate._working_rows(p)
    for r in working:
        if r["overlap_subset"] == "N":
            r.update({"rel_equity": "I", "rel_rates": "I", "rel_gold": "R", "company_notice": "N", "pol_gold": "POS",
                      "annotator_id": "AB", "annotator_type": "human", "label_basis": "accepted_ai",
                      "labelled_at_utc": "2026-10-20T09:00:00Z"})
    logged_write(p, working)
    rep = metric_status.report(p)
    assert rep["evidence"]["ai_exposed_labelled"] == 5 and rep["evidence"]["independent_human_only_labelled"] == 0
    assert rep["overall_status"] == "unavailable"
    assert all(d["outcome"] == "INSUFFICIENT_EVIDENCE" for d in rep["decision_by_series"].values())


def test_with_independent_labels_the_metrics_still_need_the_frozen_evaluation(tmp_path):
    rep = metric_status.report(folder(tmp_path))
    assert rep["overall_status"] == "requires_frozen_evaluation"
    assert rep["evidence"]["independent_human_only_labelled"] == 8
    for m in rep["metrics"].values():
        assert m["independent_labels_available"] is True and m["computable"] is False and not m["authoritative_decision_permitted"]
    assert all(d is None for d in rep["decision_by_series"].values())                         # nothing is estimated here


def test_the_metric_status_is_read_only_and_never_touches_the_key(tmp_path, no_key_reads):
    p = folder(tmp_path)
    before = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in p.review_files.rglob("*") if f.is_file()}
    metric_status.report(p)
    after = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in p.review_files.rglob("*") if f.is_file()}
    assert before == after and no_key_reads == []
    text = (PKG / "metric_status.py").read_text(encoding="utf-8")
    assert "key_sealed" not in text.replace("sealed key", "") and "_read_key" not in text and "write_" not in text


@pytest.mark.parametrize("numbers", [
    {"precision": 0.99, "lower_bound": 0.95, "pooled_recall": 0.99, "non_ambiguous_members": 5000},
    {"precision": 1.0, "lower_bound": 1.0, "pooled_recall": 1.0, "non_ambiguous_members": 10**6}])
def test_no_numbers_can_turn_the_no_evidence_decision_into_a_pass(numbers):
    d = decision.decide_without_independent_evidence()
    assert d["outcome"] == "INSUFFICIENT_EVIDENCE" and d["authoritative"] is False
    assert decision.decide_without_independent_evidence("because").get("criteria_results") == []
    # the same perfect numbers do pass the arithmetic when evidence is independent, which is exactly why they are not accepted here
    arithmetic = decision.decide_series(integrity_ok=True, **numbers)
    assert arithmetic["outcome"] == "PASS" and d["outcome"] != arithmetic["outcome"]


@pytest.mark.parametrize("guard_status", ["not_evaluable", "failed"])
def test_a_would_be_pass_cannot_survive_a_missing_or_failed_independent_check(guard_status):
    base = decision.decide_series(integrity_ok=True, non_ambiguous_members=500, precision=0.99, lower_bound=0.95, pooled_recall=0.99)
    assert base["outcome"] == "PASS"
    guard = decision.consistency_guard(ai_precision=0.99, reference_precision=None, ai_exposed_items=500,
                                       reference_refusal=["no independent labels"]) if guard_status == "not_evaluable" else \
        decision.consistency_guard(ai_precision=0.99, reference_precision=0.5, ai_exposed_items=500)
    assert decision.combine(base, guard)["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_the_approved_criteria_and_their_fingerprint_are_untouched():
    assert decision.CRITERIA == {"precision_min": 0.70, "precision_lower_bound_min": 0.60, "pooled_recall_min": 0.90,
                                 "reporting_floor_non_ambiguous": 100}
    assert decision.GUARD["tolerance"] == 0.10 and decision.criteria_authoritative() is True
    assert decision.APPROVED_CRITERIA_SHA256 == decision.criteria_sha256()


def test_the_cli_exposes_metric_status_and_no_approval_option():
    text = (PKG / "cli.py").read_text(encoding="utf-8")
    assert '"metric-status"' in text and "--ai-only-store" in text
    from wealthpilot.data.gdelt.ai import provider
    import wealthpilot.data.gdelt as pkg
    assert dict(provider.ADAPTERS) == {} and pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False
