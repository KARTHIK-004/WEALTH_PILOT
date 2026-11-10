"""B2-U9: the read-only bridge from a B2-T suggestion store and review export to the existing merge, freeze and evaluation.

SYNTHETIC only. The experiment is built by the real pipeline code with a scripted fake provider (the build lock is lifted
inside a test, never for real data); no real label, suggestion, key or provider is involved. The legacy validator is
exercised unchanged alongside the bridge.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import ai_bridge, ai_origin, annotate, cli, overlap_lock, provenance
from wealthpilot.data.gdelt import evaluate as ev
from wealthpilot.data.gdelt.ai import export as aexport
from wealthpilot.data.gdelt.ai import reviewer, runner, store
from wealthpilot.data.gdelt.annotate import AnnotationError, Paths

T0 = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
OVERLAP = ("D0002", "D0004", "D0006")
BASE = {"rel_equity": "I", "rel_rates": "R", "rel_gold": "I", "amb_code": "", "company_notice": "N",
        "pol_equity": "", "pol_rates": "NEG", "pol_gold": ""}
EDIT = {**BASE, "rel_gold": "R", "pol_gold": "POS"}


def _clock():
    now = [T0]

    def tick():
        now[0] += timedelta(seconds=1)
        return now[0]
    return tick


class World:
    """A synthetic experiment taken through suggestion, review and export, with the working copy still unlabelled."""

    def __init__(self, env, monkeypatch, scripted, *, review: bool = True, edit=("D0005",), uncertain=()):
        self.env = env
        env.enable(monkeypatch)
        # M2, overlap first (D13): the human-only overlap labels are made and locked BEFORE any suggestion exists
        p0 = Paths(env.rf)
        for iid in sorted(env.overlap):
            annotate.save_item(p0, iid, {**BASE, "near_dup_of": "", "annotator_id": "AB", "annotator_type": "human",
                                         "label_basis": "own", "labelled_at_utc": "2026-10-19T12:00:00Z", "note": ""})
        stand_in = overlap_lock.record_path(env.rf)
        os.chmod(stand_in, 0o666)
        stand_in.unlink()
        self.lock = overlap_lock.create(p0)
        d = env.cfg_dict()
        d["protocol"]["provider_exclusion"] = "overlap_and_blind"
        d["protocol"]["overlap_labels_sha256"] = self.lock["overlap_labels_sha256"]
        env.write_cfg(env.approved(d))
        self.cfg = env.load()
        store.init_experiment(self.cfg)
        self.layout = store.Layout(env.dest)
        auth = env.authorize(self.cfg)
        self.prov = scripted(default=lambda r: env.good(r.item_id))
        clock = _clock()
        runner.run_suggestions(self.cfg, auth, self.prov, clock=clock, sleep=lambda s: None, env=env.process_env)
        self.p = Paths(env.rf)
        self.items = store.load_snapshot_items(self.layout)
        self.excluded = frozenset(env.overlap)
        self.export_dir = self.layout.export
        if review:
            self.review(edit=edit, uncertain=uncertain)

    def rev(self, item_id, action, **kw):
        by = {i.item_id: i for i in self.items}
        return reviewer.record_review(self.layout, items_by_id=by, protocol_id=self.cfg.protocol_id,
                                      experiment_id=self.cfg.experiment_id, blind_ids=frozenset(),
                                      excluded_ids=self.excluded, item_id=item_id, action=action, reviewer_id="AB",
                                      now=T0, **kw)

    def review(self, *, edit=(), uncertain=()):
        for i in self.env.ids:
            if i in self.env.overlap:
                self.rev(i, "no_suggestion", labels=BASE)
            elif i in edit:
                self.rev(i, "edit", labels=EDIT, reason_code="rubric_boundary")
            elif i in uncertain:
                self.rev(i, "uncertain", labels={**BASE, "rel_gold": "A", "amb_code": "A1"}, reason_note="unclear")
            else:
                self.rev(i, "accept")
        aexport.export_dataset(self.layout, self.cfg, self.items, clock=_clock())

    def merge_all(self):
        labels, refused = ai_bridge.labels_for_merge(self.p, self.export_dir)
        batch = annotate.export_batch(self.p, size=50, overlap_only=False)
        path = Path(batch["file"])
        rows = annotate._read_csv(path)
        for r in rows:
            if r["item_id"] in labels:
                r.update(labels[r["item_id"]])
        path.write_bytes(annotate._csv_bytes(annotate.BATCH_COLUMNS, rows))
        b = ai_bridge.load(self.p, self.export_dir)
        return annotate.merge(self.p, path, ai_suggestions=b.suggestions), labels, refused


@pytest.fixture()
def world(make_ai_env, monkeypatch, scripted):
    env = make_ai_env(n=8, overlap=OVERLAP)
    return World(env, monkeypatch, scripted)


def _tree(root: Path) -> dict[str, str]:
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(root.rglob("*")) if f.is_file()}


def _kinds(rep) -> set[str]:
    return {x["kind"] for x in rep.problems}


# ================================================================ the bridge supplies a VERIFIED suggestion set

def test_the_formats_are_column_compatible_and_the_store_verifies(world):
    legacy = set(annotate.AI_SUGGESTION_COLUMNS)
    assert legacy <= set(store.VALID_CSV_COLUMNS)                       # the derived CSV is a superset of the legacy columns
    b = ai_bridge.load(world.p, world.export_dir)
    assert b.suggestions.present and b.suggestions.problems == ()
    assert b.suggestions.valid_ids == frozenset(world.env.ids) - frozenset(OVERLAP)
    assert set(b.records) == set(b.suggestions.valid_ids) and b.chain_sha256


def test_there_is_no_bridge_without_a_b2t_suggestion_chain(make_ai_env):
    env = make_ai_env(n=6)
    assert ai_bridge.load(Paths(env.rf), None) is None
    assert ai_bridge.load(Paths(env.rf), env.root / "nowhere" / "export") is None      # no chain: the legacy source applies
    assert ai_bridge.load(Paths(env.rf), env.root / "not_named_export") is None


def test_loading_the_bridge_writes_nothing(world):
    before = (_tree(world.layout.root), _tree(world.env.rf))
    ai_bridge.load(world.p, world.export_dir)
    ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert (_tree(world.layout.root), _tree(world.env.rf)) == before


def test_a_tampered_raw_chain_rejects_the_whole_set(world):
    path = world.layout.suggestions_raw
    lines = path.read_bytes().split(b"\n")
    lines[0] = lines[0].replace(b"R", b"I", 1)
    os.chmod(path, 0o666)
    path.write_bytes(b"\n".join(lines))
    b = ai_bridge.load(world.p, world.export_dir)
    assert b.suggestions.valid_ids == frozenset() and "cannot be verified" in b.suggestions.problems[0]


def test_a_hand_edited_derived_csv_is_rejected(world):
    path = world.layout.suggestions_valid
    os.chmod(path, 0o666)
    path.write_bytes(path.read_bytes().replace(b",R,", b",I,", 1))
    b = ai_bridge.load(world.p, world.export_dir)
    assert b.suggestions.valid_ids == frozenset() and any("derived" in m for m in b.suggestions.problems)


def test_a_snapshot_of_a_different_original_is_rejected(world):
    snap = world.layout.snapshot / "annotation_A.csv"
    os.chmod(snap, 0o666)
    snap.write_bytes(snap.read_bytes() + b"\n")
    b = ai_bridge.load(world.p, world.export_dir)
    assert b.suggestions.valid_ids == frozenset() and "snapshot" in b.suggestions.problems[0]


def test_a_suggestion_for_an_overlap_item_in_the_store_is_rejected(world):
    rec = dict(store.SuggestionStore(world.layout).records()[0])
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    rec["item_id"] = "D0004"
    store.SuggestionStore(world.layout).append(rec)
    b = ai_bridge.load(world.p, world.export_dir)
    assert b.suggestions.valid_ids == frozenset() and any("overlap item" in m for m in b.suggestions.problems)


def test_a_suggestion_made_for_different_input_is_rejected(world):
    rec = dict(store.SuggestionStore(world.layout).records()[0])
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    rec["input_fingerprint"] = "f" * 64
    store.SuggestionStore(world.layout).append(rec)
    b = ai_bridge.load(world.p, world.export_dir)
    assert b.suggestions.valid_ids == frozenset() and any("different input" in m for m in b.suggestions.problems)


def test_a_suggestion_that_fails_the_rubric_is_rejected(world):
    rec = dict(store.SuggestionStore(world.layout).records()[0])
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    rec["parsed"] = {**rec["parsed"], "rel_rates": "R", "pol_rates": ""}      # R with no polarity
    store.SuggestionStore(world.layout).append(rec)
    b = ai_bridge.load(world.p, world.export_dir)
    assert b.suggestions.valid_ids == frozenset() and any("pol_rates" in m for m in b.suggestions.problems)


# ================================================================ the legacy validator is unchanged and still strict

def test_the_legacy_validator_alone_still_refuses_ai_based_labels(world):
    working = annotate._working_rows(world.p)
    working[0].update({**BASE, "annotator_id": "AB", "annotator_type": "human", "label_basis": "accepted_ai",
                       "labelled_at_utc": "2026-10-19T12:00:00Z"})
    world.p.working.write_bytes(annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working))
    rep = annotate.validate(world.p)                                        # no supplied suggestions, no legacy file
    assert not rep.complete and "needs a valid suggestion" in " ".join(rep.errors["D0001"])


def test_the_bridge_accepts_an_ai_label_only_for_an_item_with_a_verified_suggestion(world):
    working = annotate._working_rows(world.p)
    for r in working:
        if r["item_id"] in ("D0001", "D0002"):
            r.update({**BASE, "annotator_id": "AB", "annotator_type": "human", "label_basis": "accepted_ai",
                      "labelled_at_utc": "2026-10-19T12:00:00Z"})
    world.p.working.write_bytes(annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working))
    rep = annotate.validate(world.p, ai_suggestions=ai_bridge.load(world.p, world.export_dir).suggestions)
    assert "D0001" not in rep.errors                                       # verified suggestion exists
    assert "D0002" in rep.errors                                           # overlap item: own only, whatever the source


def test_two_suggestion_sources_at_once_are_refused(world):
    world.p.ai_suggestions.write_bytes(b"item_id,annotator_type\n")
    working = annotate._working_rows(world.p)
    working[0].update({**BASE, "annotator_id": "AB", "annotator_type": "human", "label_basis": "accepted_ai",
                       "labelled_at_utc": "2026-10-19T12:00:00Z"})
    world.p.working.write_bytes(annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working))
    rep = annotate.validate(world.p, ai_suggestions=ai_bridge.load(world.p, world.export_dir).suggestions)
    assert any("ambiguous" in m for m in rep.integrity_errors) and not rep.ok


def test_a_rejected_suggestion_set_accepts_no_ai_label(world):
    path = world.layout.suggestions_valid
    os.chmod(path, 0o666)
    path.write_bytes(path.read_bytes() + b"x\n")
    working = annotate._working_rows(world.p)
    working[0].update({**BASE, "annotator_id": "AB", "annotator_type": "human", "label_basis": "accepted_ai",
                       "labelled_at_utc": "2026-10-19T12:00:00Z"})
    world.p.working.write_bytes(annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working))
    rep = annotate.validate(world.p, ai_suggestions=ai_bridge.load(world.p, world.export_dir).suggestions)
    assert not rep.complete and rep.integrity_errors and "D0001" in rep.errors


# ================================================================ labels_for_merge: mapping, refusals, no invention

def test_reviewed_labels_map_to_a_basis_and_nothing_is_invented(world):
    labels, refused = ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert set(labels) == set(world.env.ids) - set(OVERLAP)                       # the 3 overlap items are already labelled
    assert {r["item_id"] for r in refused} == set(OVERLAP) and all("already labelled" in r["reason"] for r in refused)
    assert labels["D0005"]["label_basis"] == "corrected_ai" and labels["D0001"]["label_basis"] == "accepted_ai"
    assert labels["D0005"]["rel_gold"] == "R" and labels["D0005"]["pol_gold"] == "POS"          # the human's edit, not the AI's
    assert labels["D0001"]["rel_gold"] == "I" and all(v["annotator_type"] == "human" and v["annotator_id"] == "AB"
                                                      for v in labels.values())
    assert set(labels["D0001"]) == set(annotate.LABEL_COLUMNS)


def test_a_review_origin_without_an_approved_basis_is_refused_not_guessed(make_ai_env, monkeypatch, scripted):
    w = World(make_ai_env(n=8, overlap=OVERLAP), monkeypatch, scripted, uncertain=("D0003",))
    labels, refused = ai_bridge.labels_for_merge(w.p, w.export_dir)
    assert "D0003" not in labels and len(labels) == 4
    unmapped = [r for r in refused if r["item_id"] == "D0003"]
    assert len(unmapped) == 1 and "protocol decision" in unmapped[0]["reason"]


def test_an_item_already_labelled_is_refused_not_overwritten(world):
    working = annotate._working_rows(world.p)
    working[0].update({**BASE, "annotator_id": "AB", "annotator_type": "human", "label_basis": "accepted_ai",
                       "labelled_at_utc": "2026-10-19T12:00:00Z"})
    annotate._log(world.p, {"event": "label", "working_sha256": hashlib.sha256(
        annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working)).hexdigest()})
    world.p.working.write_bytes(annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working))
    labels, refused = ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert "D0001" not in labels and len(labels) == 4
    assert any(r["item_id"] == "D0001" and "already labelled" in r["reason"] for r in refused)


def test_a_human_only_label_that_contradicts_the_review_blocks_the_whole_export(world):
    working = annotate._working_rows(world.p)
    working[0].update({**BASE, "annotator_id": "AB", "annotator_type": "human", "label_basis": "own",
                       "labelled_at_utc": "2026-10-19T12:00:00Z"})
    annotate._log(world.p, {"event": "label", "working_sha256": hashlib.sha256(
        annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working)).hexdigest()})
    world.p.working.write_bytes(annotate._csv_bytes(annotate.ANNOTATION_COLUMNS, working))
    labels, refused = ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert labels == {} and any("origin_conflict" in r["reason"] for r in refused)


def test_an_export_that_does_not_verify_yields_no_labels(world):
    path = world.export_dir / "annotation_b2t_v1.csv"
    os.chmod(path, 0o666)
    path.write_bytes(path.read_bytes() + b"\n")
    labels, refused = ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert labels == {} and refused and "ai_origin_unverifiable" in refused[0]["reason"]


def _rewrite_export(world, mutate):
    """Rewrite the export CSV and its manifest hash consistently, as a forger who knows the format would."""
    csv_path, man = world.export_dir / "annotation_b2t_v1.csv", world.export_dir / "EXPORT_MANIFEST.json"
    for f in (csv_path, man):
        os.chmod(f, 0o666)
    rows = list(csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8"))))
    for r in rows:
        mutate(r)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(aexport.B2T_COLUMNS), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    data = buf.getvalue().encode("utf-8")
    csv_path.write_bytes(data)
    m = json.loads(man.read_text())
    m["csv_sha256"] = hashlib.sha256(data).hexdigest()
    man.write_text(json.dumps(m), encoding="utf-8")


def test_a_forged_export_is_caught_against_the_store(world):
    # an "accepted" label that is not the suggestion
    _rewrite_export(world, lambda r: r.update(rel_gold="R", pol_gold="POS") if r["item_id"] == "D0001" else None)
    labels, refused = ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert labels == {} and any("differs from the suggestion" in r["reason"] for r in refused)


def test_a_forged_citation_is_caught_against_the_store(world):
    _rewrite_export(world, lambda r: r.update(suggestion_ref="e" * 64) if r["item_id"] == "D0001" else None)
    labels, refused = ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert labels == {} and any("not the verified valid suggestion" in r["reason"] for r in refused)


def test_a_review_claiming_no_suggestion_when_the_store_holds_one_is_caught(world):
    _rewrite_export(world, lambda r: r.update(label_origin="human_no_suggestion", ai_exposure="none", suggestion_ref="")
                    if r["item_id"] == "D0001" else None)
    labels, refused = ai_bridge.labels_for_merge(world.p, world.export_dir)
    assert labels == {} and any("holds one" in r["reason"] for r in refused)


# ================================================================ the whole path: store -> merge -> verify -> freeze -> evaluate

def test_the_whole_offline_path_works_on_synthetic_data_and_the_legacy_merge_alone_cannot(world):
    # the legacy merge, given the same labels, refuses them: it has no verified suggestion source
    labels, _ = ai_bridge.labels_for_merge(world.p, world.export_dir)
    batch = annotate.export_batch(world.p, size=50, overlap_only=False)
    path = Path(batch["file"])
    rows = annotate._read_csv(path)
    for r in rows:
        r.update(labels[r["item_id"]])
    path.write_bytes(annotate._csv_bytes(annotate.BATCH_COLUMNS, rows))
    assert annotate.merge(world.p, path)["merged"] == 0                 # legacy source: nothing accepted
    assert annotate.merge(world.p, path, ai_suggestions=ai_bridge.load(world.p, world.export_dir).suggestions)["merged"] == 5
    rep = ai_origin.verified(world.p, world.export_dir)
    assert rep.ok, rep.problems
    assert rep.counts["by_origin"] == {"human_only": 3, "ai_exposed": 5} and rep.counts["ai_origin"]["verified"]
    assert provenance.verify(world.p).counts["overlap"] == 3


def test_freeze_and_evaluate_consume_the_bridge_and_bind_the_chain(world, monkeypatch):
    world.merge_all()
    rec = ev.freeze(world.p, world.export_dir)
    assert rec["ai_suggestions_source"] == "b2t_suggestion_chain" and rec["ai_suggestions_sha256"]
    assert rec["evaluation_fingerprint"]["inputs"]["ai_origin/suggestions_raw_chain"]
    # a synthetic key (real key never touched); 8 items, one cell
    rf = world.env.rf
    keys = [{"item_id": i, "gkg_record_id": f"20220301120000-{n}", "batch_ts": "20220301120000", "cell": "C1",
             "cell_rows": 8, "cell_items": 8, "member_equity_us": 0, "member_rates_us": 1, "member_gold": 1}
            for n, i in enumerate(world.env.ids, start=1)]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(keys[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(keys)
    (rf / "key_sealed.csv").write_bytes(buf.getvalue().encode())
    # recording the key's hash changes selection_log.json, which the fingerprint binds: the freeze is now stale
    log = json.loads((rf / "selection_log.json").read_text())
    log["files_sha256"]["key_sealed.csv"] = hashlib.sha256(buf.getvalue().encode()).hexdigest()
    (rf / "selection_log.json").write_text(json.dumps(log), encoding="utf-8")
    with pytest.raises(AnnotationError, match="stale freeze"):
        ev.evaluate(world.p, n_resamples=5, ai_origin_dir=world.export_dir)
    os.chmod(ev.freeze_path(world.p), 0o666)
    ev.freeze_path(world.p).unlink()
    ev.freeze(world.p, world.export_dir)
    out = ev.evaluate(world.p, n_resamples=10, ai_origin_dir=world.export_dir)
    assert out["provenance"]["status"] == "VERIFIED" and out["label_origin_counts"] == {"human_only": 3, "ai_exposed": 5}
    ref = out["themes"]["rates"]["independent_reference"]
    assert ref["items"] == 3 and ref["evaluation_mode"] == "BLOCKED" and ref["refused"] is True
    dec = out["themes"]["rates"]["decision"]
    assert dec["authoritative"] is True and dec["consistency_guard"]["status"] == "not_evaluable"
    assert dec["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert out["themes"]["rates"]["items"] == 8                          # exploratory scope keeps all, and decides nothing


def test_a_changed_suggestion_store_after_the_freeze_is_a_stale_freeze(world):
    world.merge_all()
    ev.freeze(world.p, world.export_dir)
    path = world.layout.suggestions_raw
    os.chmod(path, 0o666)
    recorded = json.loads(ev.freeze_path(world.p).read_text())["evaluation_fingerprint"]["combined_sha256"]
    assert ev.evaluation_fingerprint(world.p, world.export_dir)["combined_sha256"] == recorded          # still fresh
    rec = dict(store.SuggestionStore(world.layout).records()[0])
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    rec["attempt"] = 99
    store.SuggestionStore(world.layout).append(rec)
    assert ev.evaluation_fingerprint(world.p, world.export_dir)["combined_sha256"] != recorded          # the chain is bound
    with pytest.raises(AnnotationError, match="stale freeze|no longer complete"):                       # and refused either way
        ev.evaluate(world.p, n_resamples=5, ai_origin_dir=world.export_dir)


def test_freeze_refuses_when_the_suggestion_store_is_tampered_and_creates_nothing(world):
    world.merge_all()
    path = world.layout.suggestions_valid
    os.chmod(path, 0o666)
    path.write_bytes(path.read_bytes() + b"x\n")
    with pytest.raises(AnnotationError, match="cannot freeze"):
        ev.freeze(world.p, world.export_dir)
    assert not ev.freeze_path(world.p).exists()


def test_merging_with_a_rejected_store_changes_nothing(world):
    labels, _ = ai_bridge.labels_for_merge(world.p, world.export_dir)
    batch = annotate.export_batch(world.p, size=50, overlap_only=False)
    path = Path(batch["file"])
    rows = annotate._read_csv(path)
    for r in rows:
        r.update(labels[r["item_id"]])
    path.write_bytes(annotate._csv_bytes(annotate.BATCH_COLUMNS, rows))
    vp = world.layout.suggestions_valid
    os.chmod(vp, 0o666)
    vp.write_bytes(vp.read_bytes() + b"x\n")
    before = world.p.working.read_bytes()
    out = annotate.merge(world.p, path, ai_suggestions=ai_bridge.load(world.p, world.export_dir).suggestions)
    assert out["merged"] == 0 and out["errors"] and out["ai_suggestions_problems"]
    assert world.p.working.read_bytes() == before


def test_the_bridge_never_touches_the_original_or_the_backup(world):
    before = {n: hashlib.sha256(f.read_bytes()).hexdigest() for n, f in
              (("a", world.p.original), ("b", world.p.backup), ("sel", world.p.selection_log))}
    world.merge_all()
    assert {n: hashlib.sha256(f.read_bytes()).hexdigest() for n, f in
            (("a", world.p.original), ("b", world.p.backup), ("sel", world.p.selection_log))} == before


# ================================================================ the CLI and the closed gates

def test_the_cli_passes_the_experiment_to_validate_and_merge():
    import argparse
    seen = {}
    real = argparse.ArgumentParser.parse_args

    def capture(self, *a, **k):
        seen["parser"] = self
        raise SystemExit(0)
    argparse.ArgumentParser.parse_args = capture                          # type: ignore[assignment]
    try:
        with pytest.raises(SystemExit):
            cli.main(["status"])
    finally:
        argparse.ArgumentParser.parse_args = real                         # type: ignore[assignment]
    text = (Path(cli.__file__)).read_text(encoding="utf-8")
    assert "_ai_suggestions(paths, args)" in text and text.count("ai_suggestions=_ai_suggestions(paths, args)") == 2


def test_the_bridge_modules_have_no_provider_or_network_path():
    root = Path(ai_bridge.__file__).parent
    for name in ("ai_bridge.py", "ai_origin.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "ADAPTERS" not in text and ".suggest(" not in text and "urllib" not in text and "requests" not in text, name
        assert "write_bytes" not in text and "write_text" not in text and "atomic_write" not in text, name
    import wealthpilot.data.gdelt as pkg
    from wealthpilot.data.gdelt.ai import provider
    assert pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False and dict(provider.ADAPTERS) == {}


# ================================================================ B2-U12 batch 1: F1, F2, F3 (SYNTHETIC; read-only checks)

def _kinds_of(world) -> set[str]:
    return {x["kind"] for x in ai_origin.verified(world.p, world.export_dir).problems}


def _rewrite_manifest(world, mutate):
    man = world.export_dir / "EXPORT_MANIFEST.json"
    os.chmod(man, 0o666)
    m = json.loads(man.read_text())
    mutate(m)
    man.write_text(json.dumps(m), encoding="utf-8")


@pytest.fixture()
def mworld(world):
    world.merge_all()
    return world


def test_f1_a_non_terminal_append_to_the_suggestion_chain_after_export_is_refused(mworld):
    assert ai_origin.verified(mworld.p, mworld.export_dir).ok
    rec = dict(store.SuggestionStore(mworld.layout).records()[0])
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    rec["terminal"], rec["attempt"] = False, 7
    rec.pop("terminal_status", None)
    store.SuggestionStore(mworld.layout).append(rec)
    assert ai_bridge.load(mworld.p, mworld.export_dir).suggestions.problems == ()        # the store itself still verifies
    assert "chain_changed_after_export" in _kinds_of(mworld)


def test_f1_a_manifest_without_chain_heads_is_refused_when_a_bridge_exists(mworld):
    _rewrite_manifest(mworld, lambda m: m.pop("chain_heads"))
    assert "chain_heads_missing" in _kinds_of(mworld)


def test_f2_an_edited_review_chain_is_refused(mworld):
    p = mworld.layout.reviews
    os.chmod(p, 0o666)
    p.write_bytes(p.read_bytes().replace(b'"reviewer_id": "AB"', b'"reviewer_id": "ZZ"', 1))
    assert "review_chain_unverifiable" in _kinds_of(mworld)


def test_f2_a_forged_review_hash_in_a_self_consistent_export_is_refused(mworld):
    _rewrite_export(mworld, lambda r: r.update(review_record_sha256="d" * 64) if r["item_id"] == "D0001" else None)
    assert "review_record_mismatch" in _kinds_of(mworld)


def test_f2_a_review_superseded_after_export_is_refused(mworld):
    mworld.rev("D0001", "accept", correction_reason="re-checked after export")
    assert "review_record_mismatch" in _kinds_of(mworld)


def test_f2_an_exported_row_without_any_review_record_is_refused(mworld):
    _rewrite_export(mworld, lambda r: r.update(item_id="D0001") if r["item_id"] == "D0001" else None)   # unchanged row stays valid
    assert ai_origin.verified(mworld.p, mworld.export_dir).ok
    p = mworld.layout.reviews
    os.chmod(p, 0o666)
    p.write_bytes(b"")                                      # an emptied review chain verifies as empty, so every row is unbacked
    assert "review_record_missing" in _kinds_of(mworld)


def test_f2_a_review_or_audit_head_that_is_not_in_its_chain_is_refused(mworld):
    _rewrite_manifest(mworld, lambda m: m["chain_heads"].update(audit="e" * 64, reviews="f" * 64))
    kinds = _kinds_of(mworld)
    assert "chain_changed_after_export" in kinds
    msgs = " ".join(x["detail"] for x in ai_origin.verified(mworld.p, mworld.export_dir).problems)
    assert "audit head" in msgs and "review head" in msgs


def test_f2_the_audit_head_in_the_manifest_is_only_an_ancestor_of_the_current_audit_head(mworld):
    from wealthpilot.data.gdelt.ai.chain import ChainedJsonl
    man = json.loads((mworld.export_dir / "EXPORT_MANIFEST.json").read_text())
    assert man["chain_heads"]["audit"] != ChainedJsonl(mworld.layout.audit).head()       # export_created came after
    assert ai_origin.verified(mworld.p, mworld.export_dir).ok                             # and a valid export still verifies


def test_f3_a_missing_suggestion_chain_in_a_real_layout_is_refused_not_a_fallback(mworld):
    os.chmod(mworld.layout.suggestions_raw, 0o666)
    mworld.layout.suggestions_raw.unlink()
    b = ai_bridge.load(mworld.p, mworld.export_dir)
    assert b is not None and b.suggestions.valid_ids == frozenset() and "missing" in b.suggestions.problems[0]
    assert "suggestions_unverifiable" in _kinds_of(mworld)


def test_f3_an_experiment_that_never_recorded_a_suggestion_may_have_no_chain(mworld):
    from wealthpilot.data.gdelt.ai.chain import GENESIS
    _rewrite_manifest(mworld, lambda m: m["chain_heads"].update(suggestions=GENESIS))
    os.chmod(mworld.layout.suggestions_raw, 0o666)
    mworld.layout.suggestions_raw.unlink()
    assert ai_bridge.load(mworld.p, mworld.export_dir) is None


def test_f3_a_directory_that_is_not_a_b2t_layout_keeps_the_legacy_behaviour(make_ai_env):
    env = make_ai_env(n=6)
    assert ai_bridge.load(Paths(env.rf), env.root / "x" / "export") is None


# ================================================================ B2-U12 batch 4: D13 in the AI package and across the real path (SYNTHETIC)

def test_d13_the_run_manifest_carries_the_locked_hash_and_freeze_accepts_it(world):
    world.merge_all()
    for m in sorted((world.layout.audit.parent).glob("run_manifest_*.json")):
        assert json.loads(m.read_text())["overlap_labels_sha256"] == world.lock["overlap_labels_sha256"]
    rec = ev.freeze(world.p, world.export_dir)                                     # lock, labels and manifests all agree
    assert rec["evaluation_fingerprint"]["inputs"]["overlap_lock_record"]


def test_d13_a_run_manifest_made_under_a_different_lock_blocks_the_freeze(world):
    world.merge_all()
    m = sorted((world.layout.audit.parent).glob("run_manifest_*.json"))[0]
    os.chmod(m, 0o666)
    data = json.loads(m.read_text())
    data["overlap_labels_sha256"] = "9" * 64
    m.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AnnotationError, match="not made under the locked overlap labels"):
        ev.freeze(world.p, world.export_dir)


def test_d13_an_unset_hash_missing_record_or_mismatch_each_block_execution(make_ai_env):
    from wealthpilot.data.gdelt.ai import config as aic
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    d["protocol"]["overlap_labels_sha256"] = None
    env.write_cfg(env.approved(d))
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            confirm_ai_run=True, env=env.process_env, overlap_item_ids=frozenset(env.overlap))
    assert any("overlap_labels_sha256 is not set" in x for x in problems)
    d["protocol"]["overlap_labels_sha256"] = "cd" * 32                              # the record says "ab" * 32
    env.write_cfg(env.approved(d))
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            confirm_ai_run=True, env=env.process_env, overlap_item_ids=frozenset(env.overlap))
    assert any("differs from the lock record's hash" in x for x in problems)
    rec = overlap_lock.record_path(env.rf)
    os.chmod(rec, 0o666)
    rec.unlink()
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            confirm_ai_run=True, env=env.process_env, overlap_item_ids=frozenset(env.overlap))
    assert any("lock record does not exist" in x for x in problems)


@pytest.mark.parametrize("bad", ["", "abc", "AB" * 32, "zz" * 32, 5, ["ab" * 32], True])
def test_d13_a_malformed_hash_is_rejected_not_coerced(make_ai_env, bad):
    from wealthpilot.data.gdelt.errors import ConfigError
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    d["protocol"]["overlap_labels_sha256"] = bad
    env.write_cfg(d)
    with pytest.raises(ConfigError, match="overlap_labels_sha256"):
        env.load()


def test_d13_the_hash_is_part_of_gate_d_and_a_change_makes_the_approval_stale(make_ai_env):
    from wealthpilot.data.gdelt.ai import config as aic
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    env.write_cfg(d)

    def gate_d():
        return aic.bindings(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            overlap_item_ids=frozenset(env.overlap))["D"]
    first = gate_d()
    d["protocol"]["overlap_labels_sha256"] = "cd" * 32
    env.write_cfg(d)
    assert gate_d() != first


def test_d13_a_run_is_refused_when_the_lock_record_changes_after_authorisation(make_ai_env, monkeypatch, scripted):
    from wealthpilot.data.gdelt.ai import provider as aprov
    env = make_ai_env(n=8, overlap=OVERLAP)
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    env.write_cfg(env.approved(d))
    cfg = env.load()
    store.init_experiment(cfg)
    auth = env.authorize(cfg)
    rec = overlap_lock.record_path(env.rf)
    os.chmod(rec, 0o666)
    rec.unlink()                                                                    # the record disappears before the run
    prov = scripted(default=lambda r: env.good(r.item_id))
    with pytest.raises(aprov.ExecutionBlocked, match="overlap-first control"):
        runner.run_suggestions(cfg, auth, prov, clock=_clock(), sleep=lambda s: None, env=env.process_env)
    assert prov.calls == []                                                          # nothing was sent


def test_d13_the_dry_run_reports_the_lock_state_and_calls_nothing(make_ai_env):
    env = make_ai_env(n=8, overlap=OVERLAP)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    d["protocol"]["overlap_labels_sha256"] = "cd" * 32
    env.write_cfg(d)
    out = runner.dry_run(env.load(), env=env.process_env)
    assert out["overlap_lock"]["configured"] is True and out["overlap_lock"]["problems"]
    assert out["provider_called"] is False and out["data_sent"] is False and out["files_written"] is False


def test_d13_the_ai_package_reads_only_the_record_never_a_label():
    root = Path(ai_bridge.__file__).parent
    text = (root / "ai" / "config.py").read_text(encoding="utf-8") + (root / "ai" / "runner.py").read_text(encoding="utf-8")
    assert "read_record" in text and "labels_hash" not in text and "_working_rows" not in text
    assert "annotation_A.working" not in text
