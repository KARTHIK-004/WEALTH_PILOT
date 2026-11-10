"""B2-U8: AI-origin evidence wired into freeze and evaluation, the independent-reference scope, and the M2 partition.

SYNTHETIC folders and exports only. The sealed key is a synthetic file written to a temporary folder; the real key, the real
data, every provider and every network are untouched. Where a test lifts the build lock it does so for a scripted fake
provider, never for real data.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path

import pytest

from wealthpilot.data import gdelt as pkg
from wealthpilot.data.gdelt import ai_origin, annotate, cli, decision, overlap_lock, provenance
from wealthpilot.data.gdelt import evaluate as ev
from wealthpilot.data.gdelt.ai import config as aic
from wealthpilot.data.gdelt.ai import provider as aprov
from wealthpilot.data.gdelt.ai import queue, reviewer, runner, store
from wealthpilot.data.gdelt.annotate import AnnotationError, Paths
from wealthpilot.data.gdelt.errors import ConfigError
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS


# ---------------------------------------------------------------- a synthetic labelled folder of any size

def _csv(columns, rows) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def logged_write(p: Paths, working) -> None:
    sha = hashlib.sha256(annotate._csv_bytes(ANNOTATION_COLUMNS, working)).hexdigest()
    p.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, working))
    annotate._log(p, {"event": "label", "working_sha256": sha})


def build(root: Path, *, members: int = 110, others: int = 10, overlap=("D0005", "D0050", "D0100"),
          every_nth_irrelevant: int = 5, labelled: bool = True) -> Paths:
    """``members`` C1 items (all gold series members, weight 1) then ``others`` C7 items (weight 10); gold is R except
    every ``every_nth_irrelevant``-th member."""
    rf = root / "review_files"
    rf.mkdir(parents=True)
    n = members + others
    rows, keys, gold = [], [], {}
    for i in range(1, n + 1):
        iid, batch = f"D{i:04d}", f"20220301{i // 4:04d}00"
        rows.append({"item_id": iid, "gkg_record_id": f"{batch}-{i}", "batch_ts": batch, "batch_date_utc": "2022-03-01",
                     "available_at_utc": "2022-03-01T12:15:00Z", "source_domain": "example.com",
                     "url": f"https://example.com/{i}", "title": f"SYNTHETIC ROW {i}", "mech_dup": "ORIGINAL",
                     "overlap_subset": "Y" if iid in overlap else "N"})
        is_member = i <= members
        gold[iid] = "I" if (not is_member or i % every_nth_irrelevant == 0) else "R"
        keys.append({"item_id": iid, "gkg_record_id": f"{batch}-{i}", "batch_ts": batch,
                     "cell": "C1" if is_member else "C7", "cell_rows": members if is_member else others * 10,
                     "cell_items": members if is_member else others, "member_equity_us": 0, "member_rates_us": 0,
                     "member_gold": 1 if is_member else 0})
    original = _csv(ANNOTATION_COLUMNS, rows)
    key = _csv(list(keys[0].keys()), keys)
    manifest = _csv(ANNOTATION_COLUMNS, [r for r in rows if r["overlap_subset"] == "Y"])
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
            g = gold[r["item_id"]]
            r.update({"rel_equity": "I", "rel_rates": "I", "rel_gold": g, "company_notice": "N",
                      "pol_gold": "POS" if g == "R" else "", "annotator_id": "AB", "annotator_type": "human",
                      "label_basis": "own", "labelled_at_utc": "2026-10-16T09:00:00Z"})
        logged_write(p, working)
    return p


def expose(p: Paths, ids, *, gold: str | None = None, basis: dict[str, str] | None = None) -> None:
    """Mark non-overlap items as labelled after seeing an AI suggestion (optionally forcing their gold label)."""
    working = annotate._working_rows(p)
    for r in working:
        if r["item_id"] in ids:
            r["label_basis"] = (basis or {}).get(r["item_id"], "accepted_ai")
            if gold:
                r["rel_gold"], r["pol_gold"] = gold, "POS" if gold == "R" else ""
    logged_write(p, working)
    # the existing validator requires a matching suggestion file for an AI-based label (legacy ai_suggestions_A.csv)
    cols = ["item_id", "annotator_type", "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice",
            "pol_equity", "pol_rates", "pol_gold", "note"]
    existing = []
    if p.ai_suggestions.exists():
        with open(p.ai_suggestions, newline="", encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
    rows = existing + [{**{c: r[c] for c in cols if c in r}, "annotator_type": "ai"} for r in working if r["item_id"] in ids]
    p.ai_suggestions.write_bytes(_csv(cols, rows))
    if not overlap_lock.record_path(p.review_files).exists():       # D13: the overlap labels are locked before any freeze
        overlap_lock.create(p)


@pytest.fixture()
def no_key_reads(monkeypatch):
    calls = []
    monkeypatch.setattr(ev, "_read_key", lambda p: calls.append(1) or pytest.fail("the sealed key was read"))
    return calls


def kinds(rep) -> set[str]:
    return {x["kind"] for x in rep.problems}


# ================================================================ AI-origin evidence against the provenance bridge

def test_all_human_labels_need_no_export_and_the_counts_say_so(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    rep = ai_origin.verified(p, None)
    assert rep.ok and rep.counts["ai_origin"] == {"required": False, "export_supplied": False, "ai_exposed_items": 0}


def test_ai_exposed_labels_without_an_export_are_unverifiable(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    rep = ai_origin.verified(p, None)
    assert not rep.ok and kinds(rep) == {"ai_origin_missing"} and "D0003" in rep.problems[0]["detail"]


def test_a_valid_export_verifies_and_is_counted(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003", "D0004"}, basis={"D0004": "corrected_ai"})
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai", "D0004": "edited_ai"}))
    assert rep.ok, rep.problems
    ao = rep.counts["ai_origin"]
    assert ao["verified"] and ao["rows"] == 8 and ao["by_ai_exposure"] == {"seen": 2, "none": 6}
    assert rep.counts["by_origin"] == {"human_only": 6, "ai_exposed": 2}


@pytest.mark.parametrize("breakage,expected", [
    ("hash", "ai_origin_unverifiable"), ("schema", "ai_origin_unverifiable"), ("rows", "ai_origin_unverifiable"),
])
def test_an_export_that_does_not_match_its_manifest_is_unverifiable(tmp_path, write_export, breakage, expected):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    kwargs = {"hash": {"rehash": False}, "schema": {"mutate_manifest": lambda m: m.update(schema="other_v9")},
              "rows": {"mutate_manifest": lambda m: m.update(rows=99)}}[breakage]
    assert kinds(ai_origin.verified(p, write_export(p, tmp_path / "x", **kwargs))) == {expected}


def test_a_missing_or_malformed_export_is_unverifiable(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    assert kinds(ai_origin.verified(p, tmp_path / "nowhere")) == {"ai_origin_unverifiable"}
    d = write_export(p, tmp_path / "x")
    (d / "EXPORT_MANIFEST.json").write_text("[1, 2]", encoding="utf-8")
    assert kinds(ai_origin.verified(p, d)) == {"ai_origin_unverifiable"}
    (d / "EXPORT_MANIFEST.json").write_text("{broken", encoding="utf-8")
    assert kinds(ai_origin.verified(p, d)) == {"ai_origin_unverifiable"}


def test_an_export_with_the_wrong_columns_is_unverifiable(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    d = write_export(p, tmp_path / "x")
    data = (d / "annotation_b2t_v1.csv").read_bytes().replace(b"review_record_sha256", b"review_record_hash", 1)
    (d / "annotation_b2t_v1.csv").write_bytes(data)
    m = json.loads((d / "EXPORT_MANIFEST.json").read_text())
    m["csv_sha256"] = hashlib.sha256(data).hexdigest()
    (d / "EXPORT_MANIFEST.json").write_text(json.dumps(m), encoding="utf-8")
    rep = ai_origin.verified(p, d)
    assert kinds(rep) == {"ai_origin_unverifiable"} and "columns" in rep.problems[0]["detail"]


def test_a_missing_non_overlap_review_record_makes_the_dataset_incomplete(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"}, drop=frozenset({"D0006"})))
    assert kinds(rep) == {"ai_origin_incomplete"} and "D0006" in rep.problems[0]["detail"]


def test_an_overlap_item_may_be_absent_from_the_export(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    assert ai_origin.verified(p, write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"},
                                              drop=frozenset({"D0002"}))).ok


def test_a_duplicate_or_unknown_export_record_is_refused(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    assert "duplicate_item" in kinds(ai_origin.verified(p, write_export(p, tmp_path / "a", duplicate=frozenset({"D0003"}))))

    def ghost(row):
        if row["item_id"] == "D0008":
            row["item_id"] = "D9999"
    rep = ai_origin.verified(p, write_export(p, tmp_path / "b", mutate_row=ghost))
    assert "unknown_item" in kinds(rep)


def test_an_export_that_contradicts_the_working_copys_origin_is_a_conflict(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    # the working copy says AI-based, the export says unexposed
    assert "origin_conflict" in kinds(ai_origin.verified(p, write_export(p, tmp_path / "a")))
    # the working copy says human-only, the export says AI-seen
    assert "origin_conflict" in kinds(ai_origin.verified(p, write_export(p, tmp_path / "b",
                                                                         seen={"D0003": "accepted_ai", "D0004": "accepted_ai"})))


def test_an_exposure_that_contradicts_its_own_origin_or_citation_is_a_conflict(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))

    def contradict(row):
        if row["item_id"] == "D0003":
            row["ai_exposure"] = "seen"                              # human_no_suggestion cannot be AI-seen
    assert "origin_conflict" in kinds(ai_origin.verified(p, write_export(p, tmp_path / "a", mutate_row=contradict)))

    def cites(row):
        if row["item_id"] == "D0004":
            row["suggestion_ref"] = "b" * 64                         # an unexposed label citing a suggestion
    assert "origin_conflict" in kinds(ai_origin.verified(p, write_export(p, tmp_path / "b", mutate_row=cites)))

    expose(p, {"D0005"})

    def uncited(row):
        if row["item_id"] == "D0005":
            row["suggestion_ref"] = ""                               # an AI-seen label citing nothing
    assert "origin_conflict" in kinds(ai_origin.verified(p, write_export(p, tmp_path / "c", seen={"D0005": "accepted_ai"},
                                                                         mutate_row=uncited)))


def test_an_unrecognised_origin_is_invalid(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", mutate_row=lambda r: r.update(label_origin="human_gold_star")
                                             if r["item_id"] == "D0003" else None))
    assert "origin_invalid" in kinds(rep)


@pytest.mark.parametrize("field,value", [("annotator_type", "ai"), ("annotator_id", ""), ("reviewed_at_utc", "yesterday"),
                                         ("review_record_sha256", "xyz")])
def test_an_unreviewed_or_malformed_review_state_is_refused(tmp_path, write_export, field, value):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", mutate_row=lambda r: r.update({field: value})
                                             if r["item_id"] == "D0003" else None))
    assert "review_invalid" in kinds(rep)


def test_fabricated_label_content_or_source_fields_are_refused(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    rep = ai_origin.verified(p, write_export(p, tmp_path / "a", mutate_row=lambda r: r.update(rel_gold="R" if r["rel_gold"] == "I"
                                             else "I") if r["item_id"] == "D0003" else None))
    assert "label_mismatch" in kinds(rep)
    rep = ai_origin.verified(p, write_export(p, tmp_path / "b", mutate_row=lambda r: r.update(title="INVENTED")
                                             if r["item_id"] == "D0003" else None))
    assert "source_changed" in kinds(rep)
    rep = ai_origin.verified(p, write_export(p, tmp_path / "c", mutate_row=lambda r: r.update(overlap_subset="Y")
                                             if r["item_id"] == "D0003" else None))
    assert {"source_changed", "membership_conflict"} & kinds(rep)


def test_a_label_in_the_export_for_an_unlabelled_item_is_not_accepted(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    d = write_export(p, tmp_path / "x")
    working = annotate._working_rows(p)
    working[2].update({c: "" for c in ("rel_equity", "rel_rates", "rel_gold", "company_notice", "pol_gold", "annotator_id",
                                       "annotator_type", "label_basis", "labelled_at_utc")})
    logged_write(p, working)
    rep = ai_origin.verified(p, d)
    assert "label_mismatch" in kinds(rep)                     # a missing label is never filled from the export


def test_an_invalid_duplicate_reference_in_the_export_is_refused_not_dropped(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", mutate_row=lambda r: r.update(near_dup_of="D0003")
                                             if r["item_id"] == "D0003" else None))
    assert {"near_dup_invalid", "label_mismatch"} & kinds(rep)


def test_an_overlap_item_that_cites_a_suggestion_is_refused(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", mutate_row=lambda r: r.update(suggestion_ref="c" * 64)
                                             if r["item_id"] == "D0002" else None))
    assert "overlap_ai_exposed" in kinds(rep)


def test_an_ai_exposed_overlap_label_is_a_conflict_even_with_an_export(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    working = annotate._working_rows(p)
    working[1]["label_basis"] = "accepted_ai"                       # D0002 is an overlap item
    logged_write(p, working)
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", seen={"D0002": "accepted_ai"}))
    assert "overlap_ai_exposed" in kinds(rep)


def test_the_export_manifest_must_agree_on_the_overlap_count(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x", mutate_manifest=lambda m: m.update(historical_overlap_items=5)))
    assert "membership_conflict" in kinds(rep)


def test_a_blocked_bridge_is_returned_unchanged_and_the_export_is_not_consulted(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    (p.review_files / "annotation_B.csv").unlink()
    rep = ai_origin.verified(p, write_export(p, tmp_path / "x"))
    assert not rep.ok and kinds(rep) == {"missing_artifact"}


# ================================================================ freeze and evaluation consume the verified evidence

def test_freeze_with_ai_exposed_labels_needs_the_verified_export_and_leaves_the_key_closed(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    with pytest.raises(AnnotationError, match="ai_origin_missing"):
        ev.freeze(p)
    assert not ev.freeze_path(p).exists() and no_key_reads == []


def test_freeze_with_a_conflicting_export_is_refused_and_creates_nothing(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    bad = write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"}, drop=frozenset({"D0006"}))
    with pytest.raises(AnnotationError, match="ai_origin_incomplete"):
        ev.freeze(p, bad)
    assert not ev.freeze_path(p).exists() and no_key_reads == []


def test_freeze_is_refused_for_incomplete_labels_even_with_a_valid_export(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    d = write_export(p, tmp_path / "x")
    working = annotate._working_rows(p)
    working[5].update({c: "" for c in ("rel_equity", "rel_rates", "rel_gold", "company_notice", "pol_gold", "annotator_id",
                                       "annotator_type", "label_basis", "labelled_at_utc")})
    logged_write(p, working)
    with pytest.raises(AnnotationError, match="cannot freeze"):
        ev.freeze(p, d)
    assert not ev.freeze_path(p).exists() and no_key_reads == []


def test_the_freeze_binds_the_export_into_the_fingerprint_and_the_record(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    d = write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"})
    rec = ev.freeze(p, d)
    fp = rec["evaluation_fingerprint"]["inputs"]
    assert fp["ai_origin_export_supplied"] is True
    assert fp["ai_origin/annotation_b2t_v1.csv"] and fp["ai_origin/EXPORT_MANIFEST.json"]
    assert rec["provenance_counts"]["ai_origin"]["verified"] is True and rec["ai_labels_present"] is True
    assert no_key_reads == []


def test_the_fingerprint_changes_with_the_export_and_with_whether_one_is_supplied(tmp_path, write_export):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    base = ev.evaluation_fingerprint(p)["combined_sha256"]
    d = write_export(p, tmp_path / "x")
    with_export = ev.evaluation_fingerprint(p, d)["combined_sha256"]
    assert with_export != base
    d2 = write_export(p, tmp_path / "y", mutate_row=lambda r: r.update(annotator_id="ZZ"))
    assert ev.evaluation_fingerprint(p, d2)["combined_sha256"] != with_export


def test_the_fingerprint_binds_the_new_provenance_code(tmp_path):
    assert "ai_origin.py" in ev.FINGERPRINT_CODE and "provenance.py" in ev.FINGERPRINT_CODE
    assert "decision.py" in ev.FINGERPRINT_CODE


def test_a_changed_export_after_the_freeze_is_a_stale_freeze_refused_before_the_key(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    d = write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"})
    ev.freeze(p, d)
    write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"}, mutate_row=lambda r: r.update(annotator_id="ZZ"))
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation inputs changed"):
        ev.evaluate(p, n_resamples=5, ai_origin_dir=d)
    assert no_key_reads == [] and not ev.results_path(p).exists()


def test_evaluating_without_the_export_the_freeze_was_bound_to_is_stale(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    expose(p, {"D0003"})
    d = write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"})
    ev.freeze(p, d)
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation inputs changed"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == []


def test_a_freeze_without_an_export_cannot_be_evaluated_against_a_later_export(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    ev.freeze(p)
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation inputs changed"):
        ev.evaluate(p, n_resamples=5, ai_origin_dir=write_export(p, tmp_path / "x"))
    assert no_key_reads == []


def test_evaluation_refuses_invalid_provenance_before_reading_the_key(tmp_path, write_export, no_key_reads, monkeypatch):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    ev.freeze(p)
    # the verification, not just the hash comparison, runs before the key: force it to block
    real = ai_origin.verified

    def blocked(paths, d):
        rep = real(paths, d)
        rep.add("origin_conflict", "D0003", "forced for the test")
        return rep
    monkeypatch.setattr(ai_origin, "verified", blocked)
    with pytest.raises(AnnotationError, match="provenance is BLOCKED"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == [] and not ev.results_path(p).exists()


def test_ai_exposed_items_are_excluded_from_the_independent_reference_and_move_the_floor(tmp_path, write_export):
    p = build(tmp_path)                                                   # 110 gold members, 10 others
    ids = {f"D{i:04d}" for i in range(11, 31)}                            # 20 non-overlap members become AI-exposed
    expose(p, ids, gold="R")
    d = write_export(p, tmp_path / "x", seen={i: "accepted_ai" for i in ids})
    ev.freeze(p, d)
    out = ev.evaluate(p, n_resamples=20, ai_origin_dir=d)
    gold = out["themes"]["gold"]
    assert gold["items"] == 120 and gold["precision"]["non_ambiguous"] == 110       # exploratory: every labelled member
    ref = gold["independent_reference"]
    assert ref["items"] == 100 and ref["precision"]["non_ambiguous"] == 90         # AI-exposed labels are not counted
    assert ref["evaluation_mode"] == "BLOCKED" and "reporting floor" in ref["mode_reasons"][0]
    assert out["reference_items"] == 100
    assert ref["precision"]["precision"] < gold["precision"]["precision"]          # the forced-R AI labels do not lift it
    assert out["label_origin_counts"] == {"human_only": 100, "ai_exposed": 20}
    assert gold["scope"] == "all_labelled" and ref["scope"] == "human_only_reference"
    assert "decision" not in ref                                                   # the reference scope takes no decision (D12c)
    dec = gold["decision"]                                                         # the decision uses all labels, gated
    assert dec["base_outcome"] == "PASS" and dec["consistency_guard"]["status"] == "failed"
    assert dec["outcome"] == "INSUFFICIENT_EVIDENCE" and dec["evidence_basis"]["ai_exposed"] == 20
    assert dec["consistency_guard"]["gap"] > 0.10 and dec["authoritative"] is True


def test_a_sufficient_human_only_reference_is_scored_but_never_authoritative(tmp_path):
    p = build(tmp_path)                                                   # precision 88/110 = 0.8
    ev.freeze(p)
    out = ev.evaluate(p, n_resamples=60)
    ref = out["themes"]["gold"]["independent_reference"]
    assert ref["evaluation_mode"] == "INDEPENDENT_REFERENCE" and ref["mode_reasons"] == []
    dec = out["themes"]["gold"]["decision"]
    assert dec["consistency_guard"]["status"] == "not_applicable"                  # no AI-exposed label: all labels independent
    assert ref["precision"]["precision"] == pytest.approx(0.8) and ref["pooled_recall"] == pytest.approx(1.0)
    assert dec["outcome"] == "PASS" and dec["authoritative"] is True and dec["criteria_status"] == "APPROVED"
    assert dec["authorizes_execution_or_deployment"] is False and "statement" not in dec
    assert out["authoritative"] is True and out["approvals_unresolved"] and out["evaluation_modes"]["gold"] == ref["evaluation_mode"]
    # a series with no members at all is blocked and undetermined, never a pass or a zero
    eq = out["themes"]["equity"]["independent_reference"]
    assert eq["evaluation_mode"] == "BLOCKED" and out["themes"]["equity"]["decision"]["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_a_low_precision_reference_fails_and_capture_recall_is_reported_separately(tmp_path):
    p = build(tmp_path, every_nth_irrelevant=2)                           # precision 0.5
    ev.freeze(p)
    gold = ev.evaluate(p, n_resamples=40)["themes"]["gold"]
    ref, dec = gold["independent_reference"], gold["decision"]
    assert dec["outcome"] == "FAIL" and dec["authoritative"] is True
    assert dec["capture_recall_reported_separately"] == ref["capture_recall"]
    assert ref["capture_recall"]["lower_bound"] is True and "pooled_recall" in ref
    assert all(c["criterion"] != "capture_recall" for c in dec["criteria_results"])     # capture recall never decides


def test_the_results_report_both_recalls_in_every_scope(tmp_path):
    p = build(tmp_path, members=12, others=4, overlap=("D0002",))
    ev.freeze(p)
    out = ev.evaluate(p, n_resamples=10)
    g = out["themes"]["gold"]
    for scope in (g, g["independent_reference"]):
        assert "pooled_recall" in scope and "pooled_recall_bootstrap" in scope and "capture_recall" in scope


def test_a_missing_label_is_never_scored_as_negative(tmp_path, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",), labelled=False)
    with pytest.raises(AnnotationError, match="0 of 8 items labelled"):
        ev.freeze(p)
    assert no_key_reads == []


# ================================================================ no outcome authorizes anything; criteria cannot be approved by input

@pytest.mark.parametrize("outcome_kwargs", [
    {"integrity_ok": True, "non_ambiguous_members": 500, "precision": 0.9, "lower_bound": 0.85, "pooled_recall": 0.95},
    {"integrity_ok": True, "non_ambiguous_members": 500, "precision": 0.1, "lower_bound": 0.05, "pooled_recall": 0.2},
    {"integrity_ok": True, "non_ambiguous_members": 10, "precision": 0.9, "lower_bound": 0.85, "pooled_recall": 0.95},
    {"integrity_ok": False, "non_ambiguous_members": 500, "precision": 0.9, "lower_bound": 0.85, "pooled_recall": 0.95},
])
def test_no_outcome_authorizes_execution_deployment_or_approval(outcome_kwargs):
    d = decision.decide_series(**outcome_kwargs)
    assert d["outcome"] in decision.OUTCOMES and d["authorizes_execution_or_deployment"] is False and d["authoritative"] is True


def test_all_four_outcomes_exist_and_remain_the_only_ones():
    assert decision.OUTCOMES == ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE", "INVALID_EVALUATION")


def test_nothing_in_the_environment_or_the_command_line_approves_the_criteria(monkeypatch):
    for name in ("CRITERIA_STATUS", "CRITERIA_APPROVED", "GDELT_CRITERIA_APPROVED", "B2_CRITERIA_APPROVAL_REFERENCE"):
        monkeypatch.setenv(name, "APPROVED")
    assert decision.criteria_authoritative() is True                       # the approval is in the code, not in the environment
    assert decision.CRITERIA_STATUS == "APPROVED" and "D8" in decision.CRITERIA_APPROVAL_REFERENCE
    parser_help = _all_option_strings()
    assert not [o for o in parser_help if "approv" in o.lower() or "authoritative" in o.lower()
                or "criteria" in o.lower()], parser_help


def _all_option_strings() -> list[str]:
    import argparse
    holder = {}
    real = argparse.ArgumentParser.parse_args

    def capture(self, *a, **k):
        holder["parser"] = self
        raise SystemExit(0)
    argparse.ArgumentParser.parse_args = capture                                 # type: ignore[assignment]
    try:
        with pytest.raises(SystemExit):
            cli.main(["status"])
    finally:
        argparse.ArgumentParser.parse_args = real                                # type: ignore[assignment]
    out: list[str] = []

    def walk(parser):
        for action in parser._actions:
            out.extend(action.option_strings)
            for sub in getattr(action, "choices", None) or {}:
                if hasattr(action.choices, "get") and hasattr(action.choices[sub], "_actions"):
                    walk(action.choices[sub])
    walk(holder["parser"])
    return out


def test_a_criteria_file_cannot_flip_the_status_and_the_modules_read_no_config_for_it():
    root = Path(decision.__file__).parent
    for name in ("decision.py", "evaluate.py", "ai_origin.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "os.environ" not in text and "yaml" not in text.lower() and "getenv" not in text, name


def test_the_evaluation_modules_have_no_provider_path():
    root = Path(decision.__file__).parent
    for name in ("decision.py", "evaluate.py", "ai_origin.py", "provenance.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "ADAPTERS" not in text and ".suggest(" not in text and "requests" not in text and "urllib" not in text, name
    assert pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False and dict(aprov.ADAPTERS) == {}


# ================================================================ the CLI passes the export, and only an experiment file

def test_the_annotate_command_exposes_one_new_option_that_names_an_experiment_file():
    opts = _all_option_strings()
    assert "--ai-experiment" in opts


# ================================================================ the M2 partition (proposed, never chosen)

ALL = frozenset(f"D{i:04d}" for i in range(1, 11))
OVERLAP = frozenset({"D0002", "D0004", "D0006"})


def test_the_m2_partition_separates_reference_blind_and_eligible_items():
    part = aic.protocol_partition("overlap_and_blind", ["D0002"], OVERLAP, ALL)
    assert part["matches_proposed_m2"] is True and part["approved"] is False and part["problems"] == []
    assert (part["human_only_reference_items"], part["blind_items"], part["ai_eligible_items"]) == (3, 1, 7)
    assert part["ai_eligible_item_ids_sha256"] == aic.protocol_partition("overlap_and_blind", ["D0002"], OVERLAP, ALL)[
        "ai_eligible_item_ids_sha256"]


def test_other_modes_are_not_described_as_m2_and_none_is_never_a_default():
    assert aic.protocol_partition("blind_only", ["D0002"], OVERLAP, ALL)["matches_proposed_m2"] is False
    none = aic.protocol_partition("none", [], OVERLAP, ALL)
    assert none["matches_proposed_m2"] is False and none["ai_eligible_items"] == 10
    unset = aic.protocol_partition(None, [], OVERLAP, ALL)
    assert unset["ai_eligible_items"] is None and unset["ai_eligible_item_ids_sha256"] is None
    assert any("not set" in x for x in unset["problems"])


def test_a_changed_membership_changes_the_eligible_set_hash():
    a = aic.protocol_partition("overlap_and_blind", [], OVERLAP, ALL)
    b = aic.protocol_partition("overlap_and_blind", [], OVERLAP | {"D0008"}, ALL)
    assert a["ai_eligible_item_ids_sha256"] != b["ai_eligible_item_ids_sha256"]


@pytest.mark.parametrize("blind,overlap,message", [
    (["D0001"], OVERLAP, "must all be original overlap items"),
    (["D9999"], OVERLAP, "not in the dataset"),
    ([], OVERLAP | {"D9999"}, "overlap names items that are not in the dataset"),
    ([], None, "overlap membership is not verified"),
])
def test_an_inconsistent_partition_reports_the_problem(blind, overlap, message):
    part = aic.protocol_partition("overlap_and_blind", blind, overlap, ALL)
    assert any(message in x for x in part["problems"]), part["problems"]


# ---- the same policy on every path, with a scripted fake provider and a lifted lock for a SYNTHETIC folder only

def _prepare(env, monkeypatch, mode, blind=()):
    env.enable(monkeypatch)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = mode
    d["protocol"]["blind_item_ids"] = list(blind)
    env.write_cfg(env.approved(d))
    cfg = env.load()
    store.init_experiment(cfg)
    return cfg, env.authorize(cfg), store.Layout(env.dest)


def _run(env, cfg, auth, prov):
    from datetime import datetime, timedelta, timezone
    now = [datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)]

    def clock():
        now[0] += timedelta(seconds=1)
        return now[0]
    return runner.run_suggestions(cfg, auth, prov, clock=clock, sleep=lambda s: None, env=env.process_env)


def test_m2_submission_resume_queue_review_and_store_validation_apply_one_policy(make_ai_env, scripted, monkeypatch):
    env = make_ai_env(n=8, overlap=("D0002", "D0004", "D0006"), blind=("D0002",))
    cfg, auth, layout = _prepare(env, monkeypatch, "overlap_and_blind", blind=("D0002",))
    eligible = set(env.ids) - env.overlap
    prov = scripted(default=lambda r: env.good(r.item_id))
    _run(env, cfg, auth, prov)
    assert {c.item_id for c in prov.calls} == eligible and len(prov.calls) == len(eligible)      # submission
    again = scripted(default=lambda r: env.good(r.item_id))
    _run(env, cfg, auth, again)
    assert again.calls == []                                                                      # resume: nothing sent
    excluded = frozenset(env.overlap)
    items = store.load_snapshot_items(layout)
    rows = {r["item_id"]: r for r in queue.build_queue(items, layout, frozenset({"D0002"}), excluded_ids=excluded)}
    assert {i: rows[i]["reasons"] for i in ("D0004", "D0006")} == {i: "excluded_from_provider" for i in ("D0004", "D0006")}
    by = {i.item_id: i for i in items}
    with pytest.raises(reviewer.ReviewError, match="excluded from provider submission"):          # review
        reviewer.record_review(layout, items_by_id=by, protocol_id="p", experiment_id="b2t_test_v1", blind_ids=frozenset(),
                               excluded_ids=excluded, item_id="D0004", action="accept", reviewer_id="AB")
    rec = dict(store.SuggestionStore(layout).records()[0])                                        # store validation
    for k in ("prev_sha256", "record_sha256"):
        rec.pop(k)
    rec["item_id"] = "D0004"
    store.SuggestionStore(layout).append(rec)
    with pytest.raises(aprov.ExecutionBlocked, match="contaminated"):
        _run(env, cfg, auth, scripted(default=lambda r: env.good(r.item_id)))


def test_a_dry_run_reports_the_partition_and_never_calls_anything(make_ai_env, monkeypatch):
    env = make_ai_env(n=8, overlap=("D0002", "D0004", "D0006"), blind=("D0002",))
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    d["protocol"]["blind_item_ids"] = ["D0002"]
    env.write_cfg(d)
    out = runner.dry_run(env.load(), env=env.process_env)
    part = out["protocol_partition"]
    assert out["provider_called"] is False and out["data_sent"] is False and out["files_written"] is False
    assert part["matches_proposed_m2"] and (part["human_only_reference_items"], part["ai_eligible_items"]) == (3, 5)
    assert out["sendable_items"] == 5 and not env.dest.exists()


def test_a_dry_run_with_an_unknown_blind_item_lists_it_among_the_unmet_prerequisites(make_ai_env):
    env = make_ai_env(n=8, overlap=("D0002", "D0004"), blind=())
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    d["protocol"]["blind_item_ids"] = ["D0099"]
    env.write_cfg(d)
    out = runner.dry_run(env.load(), env=env.process_env)
    assert any("D0099" in x or "overlap items" in x for x in out["unmet_prerequisites"])


def test_without_a_lifted_lock_every_run_stays_blocked_with_the_lock_and_adapter_named(make_ai_env):
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    d["protocol"]["provider_exclusion"] = "overlap_and_blind"
    env.write_cfg(env.approved(d))
    problems = aic.blockers(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            confirm_ai_run=True, env=env.process_env, overlap_item_ids=frozenset(env.overlap))
    assert any("build lock" in x for x in problems) and any("no adapter exists" in x for x in problems)
    with pytest.raises(aprov.ExecutionBlocked):
        aic.authorize_run(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                          confirm_ai_run=True, env=env.process_env, overlap_item_ids=frozenset(env.overlap))


# ================================================================ polarity: recorded, never defaulted, never silently valid

def test_a_missing_polarity_option_blocks_and_is_not_defaulted(make_ai_env):
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    d["protocol"]["polarity_option"] = None
    env.write_cfg(env.approved(d))
    cfg = env.load()
    assert cfg.polarity_option is None
    problems = aic.blockers(cfg, itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                            confirm_ai_run=True, env=env.process_env, overlap_item_ids=frozenset(env.overlap))
    assert any("polarity" in x for x in problems)


@pytest.mark.parametrize("value", ["", " ", "p1_required_as_in_existing_rubric", "P1_required_as_in_existing_rubric ", "P2",
                                   "none", "default", 1, True, ["P1_required_as_in_existing_rubric"], {"option": "P1"}])
def test_an_invalid_polarity_option_is_rejected_not_coerced(make_ai_env, value):
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    d["protocol"]["polarity_option"] = value
    env.write_cfg(d)
    with pytest.raises((ConfigError, TypeError)):
        env.load()


def test_the_only_implemented_polarity_option_is_recorded_not_approved(make_ai_env):
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    assert aic.POLARITY_OPTIONS == ("P1_required_as_in_existing_rubric",)
    env.write_cfg(d)
    cfg = env.load()
    assert cfg.polarity_option == aic.POLARITY_OPTIONS[0] and cfg.approvals == {}          # recorded; no approval record exists


def test_the_polarity_option_is_hashed_into_gate_a(make_ai_env):
    env = make_ai_env(n=6)
    d = env.cfg_dict()
    env.write_cfg(d)
    with_option = aic.bindings(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                               overlap_item_ids=frozenset(env.overlap))["A"]
    d["protocol"]["polarity_option"] = None
    env.write_cfg(d)
    assert aic.bindings(env.load(), itemset_sha256=env.itemset(), original_overlap_sha256=env.overlap_sha(),
                        overlap_item_ids=frozenset(env.overlap))["A"] != with_option


def test_the_polarity_rule_for_labels_is_unchanged_a_relevant_theme_needs_polarity(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    working = annotate._working_rows(p)
    working[0]["rel_gold"], working[0]["pol_gold"] = "R", ""                 # R with no polarity
    p.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, working))
    rep = annotate.validate(p)
    assert not rep.complete and rep.errors                                    # the existing validator still refuses it


# ================================================================ B2-U12 batches 2 and 3: D3, F4b, D12(c) guard (SYNTHETIC)

from wealthpilot.data.gdelt import estimators as est                      # noqa: E402  (grouped with the new tests)

CELLS = {"C1": (193, 193), "C2": (2848, 200), "C3": (1953, 200), "C4": (1560, 100), "C5": (20300, 200), "C6": (24492, 300),
         "C7": (193590, 300)}                    # (rows N, items n): the real pre-registered cell sizes, public in selection_log.json


def _synthetic(counts: dict[str, int], *, parent: bool):
    """Best-case items: every captured-cell item is R, every other item I. ``parent`` keeps the parent n_c as cell_items."""
    out = []
    for c, (n_rows, n_items) in CELLS.items():
        for k in range(counts[c]):
            rel = "R" if c in ("C1", "C2", "C3", "C4", "C5") else "I"
            out.append(est.Scored(f"{c}-{k}", f"b{k % 40}", c, n_rows, n_items if parent else counts[c],
                                  {"equity": "I", "rates": "I", "gold": rel}, "N",
                                  {"equity": False, "rates": False, "gold": c == "C1"}))
    return out


def test_realised_reweighting_sums_to_the_parent_cell_size_in_every_cell():
    sub = _synthetic({c: round(n * 0.2) for c, (_, n) in CELLS.items()}, parent=True)
    rw = ev._reweighted(sub)
    for c, (n_rows, _) in CELLS.items():
        assert sum(i.weight for i in rw if i.cell == c) == pytest.approx(n_rows)            # w = N_c / n'_c over n'_c items


def test_reweighting_the_whole_sample_changes_nothing():
    full = _synthetic({c: n for c, (_, n) in CELLS.items()}, parent=True)
    assert [i.weight for i in ev._reweighted(full)] == [i.weight for i in full]


def test_the_capture_recall_best_cases_match_the_independent_derivation():
    full = _synthetic({c: n for c, (_, n) in CELLS.items()}, parent=True)
    k20 = {c: round(n * 0.2) for c, (_, n) in CELLS.items()}                                  # n'_C7 = 60
    assert est.capture_recall(full, "gold")["recall"] == pytest.approx(0.9328, abs=5e-5)
    assert est.capture_recall(ev._reweighted(_synthetic(k20, parent=True)), "gold")["recall"] == pytest.approx(0.7351, abs=5e-5)
    assert est.capture_recall(_synthetic(k20, parent=True), "gold")["recall"] == pytest.approx(0.3569, abs=5e-5)   # the old artefact


def test_a_subset_with_thirty_members_and_every_cell_is_not_refused_and_twenty_nine_is():
    full = _synthetic({c: n for c, (_, n) in CELLS.items()}, parent=True)
    k = {c: 5 for c in CELLS}
    assert ev._subset_refusals(full, ev._reweighted(_synthetic({**k, "C1": 30}, parent=True)), "gold") == []
    assert any("subset minimum is 30" in m for m in
               ev._subset_refusals(full, ev._reweighted(_synthetic({**k, "C1": 29}, parent=True)), "gold"))


def test_a_subset_missing_a_cell_the_metrics_use_is_refused():
    full = _synthetic({c: n for c, (_, n) in CELLS.items()}, parent=True)
    k = {c: 40 for c in CELLS}
    no_c7 = ev._reweighted(_synthetic({**k, "C7": 0}, parent=True))
    assert any("C7" in m for m in ev._subset_refusals(full, no_c7, "gold"))


def test_the_guard_is_precision_only_one_directional_and_equality_passes():
    g = decision.consistency_guard
    assert g(ai_precision=0.80, reference_precision=0.70, ai_exposed_items=100)["status"] == "passed"        # exactly 0.10
    assert g(ai_precision=0.81, reference_precision=0.70, ai_exposed_items=100)["status"] == "failed"
    low = g(ai_precision=0.50, reference_precision=0.90, ai_exposed_items=100)                              # AI lower: not flagged
    assert low["status"] == "passed" and low["gap"] == pytest.approx(-0.40)
    out = g(ai_precision=0.9, reference_precision=0.7, ai_exposed_items=5)
    assert out["metric"] == "precision" and out["significance_test"] is None and out["tolerance"] == 0.10
    assert "not a statistically validated boundary" in out["tolerance_status"] and "equivalence" in out["note"]


def test_the_guard_is_not_applicable_without_ai_exposure_and_not_evaluable_without_an_estimate():
    g = decision.consistency_guard
    assert g(ai_precision=None, reference_precision=0.9, ai_exposed_items=0)["status"] == "not_applicable"
    assert g(ai_precision=0.9, reference_precision=None, ai_exposed_items=3)["status"] == "not_evaluable"
    assert g(ai_precision=0.9, reference_precision=0.8, ai_exposed_items=3, reference_refusal=["x"])["status"] == "not_evaluable"
    assert g(ai_precision=float("nan"), reference_precision=0.8, ai_exposed_items=3)["status"] == "not_evaluable"


@pytest.mark.parametrize("base_outcome,guard_status,expected", [
    ("PASS", "failed", "INSUFFICIENT_EVIDENCE"), ("FAIL", "failed", "INSUFFICIENT_EVIDENCE"),
    ("PASS", "not_evaluable", "INSUFFICIENT_EVIDENCE"), ("PASS", "passed", "PASS"), ("FAIL", "passed", "FAIL"),
    ("PASS", "not_applicable", "PASS"), ("INVALID_EVALUATION", "failed", "INVALID_EVALUATION"),
    ("INSUFFICIENT_EVIDENCE", "failed", "INSUFFICIENT_EVIDENCE")])
def test_a_failed_or_unevaluable_guard_maps_to_insufficient_evidence_and_the_base_outcome_is_kept(base_outcome, guard_status, expected):
    base = {"outcome": base_outcome, "reasons": [], "authoritative": False}
    out = decision.combine(base, {"status": guard_status, "reasons": ["r"]})
    assert out["outcome"] == expected and out["base_outcome"] == base_outcome and out["authoritative"] is False


def test_the_guard_settings_are_in_the_fingerprint_and_a_change_makes_a_freeze_stale(tmp_path, monkeypatch, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    assert ev.evaluation_fingerprint(p)["protocol"]["consistency_guard"]["tolerance"] == 0.10
    ev.freeze(p)
    monkeypatch.setattr(decision, "GUARD", {**decision.GUARD, "tolerance": 0.2})
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation protocol changed"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == []


def _m2_world(tmp_path, write_export, *, overlap_c1: int, overlap_c7: int, ai_gold):
    """Overlap = the first ``overlap_c1`` C1 items and ``overlap_c7`` C7 items; every other item is AI-exposed."""
    ov = tuple(f"D{i:04d}" for i in range(1, overlap_c1 + 1)) + tuple(f"D{i:04d}" for i in range(111, 111 + overlap_c7))
    p = build(tmp_path, overlap=ov)
    ids = {f"D{i:04d}" for i in range(1, 121)} - set(ov)
    expose(p, ids, gold=ai_gold)
    d = write_export(p, tmp_path / "x", seen={i: "accepted_ai" for i in ids})
    ev.freeze(p, d)
    return ev.evaluate(p, n_resamples=30, ai_origin_dir=d)["themes"]["gold"]


def test_m2_end_to_end_a_consistent_independent_subset_lets_the_base_outcome_stand(tmp_path, write_export):
    gold = _m2_world(tmp_path, write_export, overlap_c1=40, overlap_c7=2, ai_gold=None)
    ref, dec = gold["independent_reference"], gold["decision"]
    assert ref["refused"] is False and ref["evaluation_mode"] == "BLOCKED"                      # 40 members < the 100 floor
    assert ref["reweighting"].startswith("realised cell counts")
    assert dec["consistency_guard"]["status"] == "passed" and dec["base_outcome"] == dec["outcome"] == "PASS"
    assert dec["evidence_basis"]["human_only"] == 42 and dec["evidence_basis"]["ai_exposed"] == 78
    assert "NOT independent" in dec["evidence_basis"]["statement"]


def test_m2_end_to_end_inflated_ai_exposed_precision_fails_the_guard(tmp_path, write_export):
    gold = _m2_world(tmp_path, write_export, overlap_c1=40, overlap_c7=2, ai_gold="R")
    dec = gold["decision"]
    assert dec["consistency_guard"]["status"] == "failed" and dec["consistency_guard"]["gap"] > 0.10
    assert dec["base_outcome"] == "PASS" and dec["outcome"] == "INSUFFICIENT_EVIDENCE"
    strata = gold["precision_by_label_origin"]["strata"]
    assert strata["ai_exposed"]["precision"] > strata["human_only"]["precision"]


def test_m2_end_to_end_too_few_human_only_members_refuses_the_subset_estimate(tmp_path, write_export):
    gold = _m2_world(tmp_path, write_export, overlap_c1=20, overlap_c7=2, ai_gold=None)
    ref, dec = gold["independent_reference"], gold["decision"]
    assert ref["refused"] is True and "precision" not in ref and any("subset minimum is 30" in m for m in ref["refusal_reasons"])
    assert dec["consistency_guard"]["status"] == "not_evaluable" and dec["outcome"] == "INSUFFICIENT_EVIDENCE"


def test_m2_end_to_end_a_cell_without_a_human_only_item_refuses_the_subset_estimate(tmp_path, write_export):
    gold = _m2_world(tmp_path, write_export, overlap_c1=40, overlap_c7=0, ai_gold=None)
    ref = gold["independent_reference"]
    assert ref["refused"] is True and any("C7" in m for m in ref["refusal_reasons"])
    assert gold["decision"]["outcome"] == "INSUFFICIENT_EVIDENCE"


# ================================================================ B2-U12 batch 4: D13 overlap-first lock (SYNTHETIC)

def _locked(tmp_path, **kw):
    p = build(tmp_path, members=6, others=2, overlap=("D0002", "D0004", "D0007"), **kw)
    return p, overlap_lock.create(p)


def test_the_lock_records_a_verified_hash_of_the_overlap_labels_and_is_read_only(tmp_path):
    p, rec = _locked(tmp_path)
    assert rec["overlap_items"] == 3 and len(rec["overlap_labels_sha256"]) == 64 and rec["schema"] == overlap_lock.SCHEMA
    assert overlap_lock.read_record(p.review_files)[0]["record_sha256"] == rec["record_sha256"]
    assert not os.access(overlap_lock.record_path(p.review_files), os.W_OK)
    assert overlap_lock.verify(p) == []
    with pytest.raises(AnnotationError, match="never overwritten"):
        overlap_lock.create(p)


def test_the_hash_depends_on_the_labels_not_on_the_time(tmp_path):
    from datetime import datetime, timezone
    a = build(tmp_path / "a", members=6, others=2, overlap=("D0002", "D0004", "D0007"))
    b = build(tmp_path / "b", members=6, others=2, overlap=("D0002", "D0004", "D0007"))
    ra = overlap_lock.create(a, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    rb = overlap_lock.create(b, now=datetime(2030, 6, 6, tzinfo=timezone.utc))
    assert ra["locked_at_utc"] != rb["locked_at_utc"] and ra["overlap_labels_sha256"] == rb["overlap_labels_sha256"]


def test_the_lock_is_refused_while_an_overlap_item_is_unlabelled(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002", "D0004"), labelled=False)
    with pytest.raises(AnnotationError, match="cannot lock the overlap labels"):
        overlap_lock.create(p)
    assert not overlap_lock.record_path(p.review_files).exists()


def test_the_lock_is_refused_for_an_ai_based_or_rubric_invalid_overlap_label(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002", "D0004", "D0007"))
    working = annotate._working_rows(p)
    working[1]["label_basis"] = "accepted_ai"                                    # D0002 is an overlap item
    logged_write(p, working)
    with pytest.raises(AnnotationError, match="overlap"):
        overlap_lock.create(p)
    working[1]["label_basis"] = "own"
    working[1].update({"rel_gold": "R", "pol_gold": ""})                          # R with no polarity: invalid under the rubric
    logged_write(p, working)
    with pytest.raises(AnnotationError, match="pol_gold"):
        overlap_lock.create(p)


def test_the_lock_is_refused_when_the_working_copy_changed_outside_the_log_or_the_source_changed(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002", "D0004", "D0007"))
    working = annotate._working_rows(p)
    working[0]["title"] = "CHANGED"                                              # an original source field, no log record
    p.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, working))
    with pytest.raises(AnnotationError, match="provenance"):
        overlap_lock.create(p)


def test_the_lock_is_refused_when_the_selection_log_disagrees_on_the_overlap_count(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002", "D0004", "D0007"))
    log = json.loads(p.selection_log.read_text())
    log["overlap_items"] = 312
    p.selection_log.write_text(json.dumps(log), encoding="utf-8")
    with pytest.raises(AnnotationError, match="records 312 overlap items"):
        overlap_lock.create(p)


def test_a_changed_overlap_label_after_the_lock_is_detected_but_other_labels_are_not_part_of_the_hash(tmp_path):
    p, _ = _locked(tmp_path)
    working = annotate._working_rows(p)
    working[0]["rel_equity"] = "RL"                                              # D0001: not an overlap item
    working[0]["note"] = "later correction"
    logged_write(p, working)
    assert overlap_lock.verify(p) == []
    working[1]["note"] = "an overlap label edited after the lock"                # D0002
    logged_write(p, working)
    assert any("changed after they were locked" in m for m in overlap_lock.verify(p))


def test_an_edited_or_missing_lock_record_is_refused(tmp_path):
    p, rec = _locked(tmp_path)
    path = overlap_lock.record_path(p.review_files)
    os.chmod(path, 0o666)
    path.write_text(path.read_text().replace(rec["overlap_labels_sha256"], "0" * 64), encoding="utf-8")
    assert overlap_lock.read_record(p.review_files)[0] is None and overlap_lock.verify(p)
    path.unlink()
    assert "does not exist" in overlap_lock.verify(p)[0]


def test_verify_runs_needs_a_manifest_carrying_the_locked_hash(tmp_path):
    p, rec = _locked(tmp_path)
    exp = tmp_path / "dest" / "export"
    (tmp_path / "dest" / "snapshot").mkdir(parents=True)
    exp.mkdir(parents=True)
    assert "no run manifest" in overlap_lock.verify_runs(p, exp)[0]
    audit = tmp_path / "dest" / "audit"
    audit.mkdir()
    (audit / "run_manifest_r1.json").write_text(json.dumps({"overlap_labels_sha256": "1" * 64}), encoding="utf-8")
    assert "not made under the locked overlap labels" in overlap_lock.verify_runs(p, exp)[0]
    (audit / "run_manifest_r1.json").write_text(json.dumps({"overlap_labels_sha256": rec["overlap_labels_sha256"]}), encoding="utf-8")
    assert overlap_lock.verify_runs(p, exp) == []
    assert overlap_lock.verify_runs(p, tmp_path / "not_a_layout") == []           # not a B2-T folder: nothing to bind


def test_freeze_with_ai_exposed_labels_needs_the_lock_and_leaves_the_key_closed(tmp_path, write_export, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    working = annotate._working_rows(p)
    working[2]["label_basis"] = "accepted_ai"
    logged_write(p, working)
    cols = ["item_id", "annotator_type", "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice",
            "pol_equity", "pol_rates", "pol_gold", "note"]
    p.ai_suggestions.write_bytes(_csv(cols, [{**{c: working[2].get(c, "") for c in cols}, "item_id": "D0003", "annotator_type": "ai"}]))
    d = write_export(p, tmp_path / "x", seen={"D0003": "accepted_ai"})
    with pytest.raises(AnnotationError, match="overlap-first control is not satisfied"):
        ev.freeze(p, d)
    assert not ev.freeze_path(p).exists() and no_key_reads == []
    overlap_lock.create(p)
    ev.freeze(p, d)                                                              # now satisfied
    working = annotate._working_rows(p)
    working[1]["note"] = "edited after the lock"                                 # D0002, an overlap item
    logged_write(p, working)
    os.chmod(ev.freeze_path(p), 0o666)
    ev.freeze_path(p).unlink()
    with pytest.raises(AnnotationError, match="changed after they were locked"):
        ev.freeze(p, d)


def test_an_all_human_freeze_does_not_need_the_lock(tmp_path, no_key_reads):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    ev.freeze(p)                                                                 # no AI-exposed label: nothing to protect
    assert no_key_reads == []


def test_the_lock_record_is_part_of_the_fingerprint(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002", "D0004"))
    before = ev.evaluation_fingerprint(p)["combined_sha256"]
    overlap_lock.create(p)
    after = ev.evaluation_fingerprint(p)
    assert after["combined_sha256"] != before and after["inputs"]["overlap_lock_record"]
    assert "overlap_lock.py" in ev.FINGERPRINT_CODE


def test_the_annotate_command_offers_lock_overlap_and_no_approval_option():
    assert "lock-overlap" in (Path(cli.__file__).read_text(encoding="utf-8"))
    assert not [o for o in _all_option_strings() if "approv" in o.lower()]


# ================================================================ B2-U12 D8: the approved criteria and their freeze (SYNTHETIC inputs)

def test_d8_the_approved_values_are_exactly_the_b2i_section_4_7_criteria_and_the_reporting_floor():
    assert decision.CRITERIA == {"precision_min": 0.70, "precision_lower_bound_min": 0.60, "pooled_recall_min": 0.90,
                                 "reporting_floor_non_ambiguous": 100}
    assert decision.RECALL_GATE == "pooled_recall"                      # D4: capture recall is reported, never a criterion
    assert decision.GUARD["tolerance"] == 0.10 and decision.GUARD["failed_outcome"] == "INSUFFICIENT_EVIDENCE"
    assert est.PROPOSED_THRESHOLDS["precision_min"] == decision.CRITERIA["precision_min"]
    assert est.PROPOSED_THRESHOLDS["precision_lower_bound_min"] == decision.CRITERIA["precision_lower_bound_min"]
    assert est.PROPOSED_THRESHOLDS["pooled_capture_recall_min"] == decision.CRITERIA["pooled_recall_min"]
    assert est.BOOTSTRAP_GENERATOR == "random.Random" and est.BOOTSTRAP_SEED == 42 and est.BOOTSTRAP_RESAMPLES == 2000


def test_d8_the_freeze_binds_the_exact_approved_content():
    assert decision.criteria_authoritative() is True
    assert decision.APPROVED_CRITERIA_SHA256 == decision.criteria_sha256()


@pytest.mark.parametrize("change", [("CRITERIA", "precision_min", 0.65), ("CRITERIA", "precision_lower_bound_min", 0.55),
                                    ("CRITERIA", "pooled_recall_min", 0.85), ("CRITERIA", "reporting_floor_non_ambiguous", 50),
                                    ("GUARD", "tolerance", 0.15), ("GUARD", "min_reference_members", 20)])
def test_d8_changing_any_approved_threshold_without_a_new_approval_removes_the_authority(monkeypatch, change):
    name, key, value = change
    monkeypatch.setattr(decision, name, {**getattr(decision, name), key: value})
    assert decision.criteria_authoritative() is False
    out = decision.decide_series(integrity_ok=True, non_ambiguous_members=500, precision=0.9, lower_bound=0.8, pooled_recall=0.95)
    assert out["authoritative"] is False and "not an acceptance decision" in out["statement"]
    assert any("not approved, or changed since approval" in x for x in decision.pending_approvals())


def test_d8_changing_the_recall_gate_removes_the_authority(monkeypatch):
    monkeypatch.setattr(decision, "RECALL_GATE", "capture_recall")
    assert decision.criteria_authoritative() is False


def test_d8_an_authoritative_outcome_still_authorizes_nothing_and_the_open_approvals_stay_listed():
    out = decision.decide_series(integrity_ok=True, non_ambiguous_members=500, precision=0.9, lower_bound=0.8, pooled_recall=0.95)
    assert out["outcome"] == "PASS" and out["authoritative"] is True and out["authorizes_execution_or_deployment"] is False
    pending = " ".join(decision.pending_approvals())
    assert "completion wording" in pending and "provider" in pending and "acquisition" in pending
    assert "acceptance criteria" not in pending


def test_d8_the_freeze_does_not_create_an_experiment_freeze(tmp_path):
    p = build(tmp_path, members=6, others=2, overlap=("D0002",))
    assert not ev.freeze_path(p).exists() and not ev.results_path(p).exists()      # approving criteria writes no record
