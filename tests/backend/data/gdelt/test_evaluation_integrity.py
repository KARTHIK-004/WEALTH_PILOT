"""B2-U7: the four-way threshold decision, verified provenance, estimator additions and bootstrap reproducibility.
SYNTHETIC only. No sealed key, no real label, no provider."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import annotate, decision, estimators as est, provenance
from wealthpilot.data.gdelt.annotate import Paths
from wealthpilot.data.gdelt.estimators import Scored
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

# ================================================================ the decision function

GOOD = dict(integrity_ok=True, non_ambiguous_members=100, precision=0.70, lower_bound=0.60, pooled_recall=0.90)


def d(**over):
    return decision.decide_series(**{**GOOD, **over})


def test_exact_boundaries_pass_and_the_next_value_below_fails():
    assert d()["outcome"] == "PASS"
    assert d(precision=0.6999)["outcome"] == "FAIL"
    assert d(lower_bound=0.5999)["outcome"] == "FAIL"
    assert d(pooled_recall=0.8999)["outcome"] == "FAIL"
    assert d(precision=1.0, lower_bound=1.0, pooled_recall=1.0)["outcome"] == "PASS"


@pytest.mark.parametrize("n,expected", [(0, "INSUFFICIENT_EVIDENCE"), (99, "INSUFFICIENT_EVIDENCE"), (100, "PASS"), (101, "PASS")])
def test_the_reporting_floor_of_100_is_enforced_at_the_boundary(n, expected):
    assert d(non_ambiguous_members=n)["outcome"] == expected


def test_below_the_floor_even_a_perfect_precision_cannot_pass():
    out = d(non_ambiguous_members=99, precision=1.0, lower_bound=1.0)
    assert out["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert any("reporting floor is 100" in r for r in out["reasons"])


@pytest.mark.parametrize("field", ["precision", "lower_bound", "pooled_recall", "non_ambiguous_members"])
def test_a_missing_metric_never_passes(field):
    out = d(**{field: None})
    assert out["outcome"] == "INSUFFICIENT_EVIDENCE" and out["outcome"] != "PASS"


def test_a_determinable_failure_is_a_fail_even_if_another_metric_is_missing():
    assert d(pooled_recall=0.5, lower_bound=None)["outcome"] == "FAIL"
    assert d(non_ambiguous_members=50, pooled_recall=0.5)["outcome"] == "FAIL"           # recall needs no floor


def test_a_precision_below_threshold_with_too_few_members_is_insufficient_not_fail():
    assert d(non_ambiguous_members=40, precision=0.5, lower_bound=0.3)["outcome"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize("field,bad", [("precision", math.nan), ("precision", math.inf), ("precision", 1.2), ("lower_bound", -0.1),
                                       ("pooled_recall", "0.95"), ("pooled_recall", True), ("non_ambiguous_members", -3),
                                       ("non_ambiguous_members", 99.5), ("non_ambiguous_members", "100")])
def test_invalid_values_are_an_invalid_evaluation_never_a_pass_or_fail(field, bad):
    out = d(**{field: bad})
    assert out["outcome"] == "INVALID_EVALUATION" and out["criteria_results"] == []


def test_failed_integrity_or_provenance_is_invalid_whatever_the_numbers_say():
    out = d(integrity_ok=False, integrity_problems=["history_mismatch: the working copy changed"])
    assert out["outcome"] == "INVALID_EVALUATION" and "history_mismatch" in out["reasons"][0]
    assert d(integrity_ok=False, precision=1.0, lower_bound=1.0, pooled_recall=1.0)["outcome"] == "INVALID_EVALUATION"
    assert d(integrity_ok=False)["reasons"]                                              # a default reason is given


def test_insufficient_and_invalid_can_never_be_reported_as_pass():
    for kw in ({"precision": None}, {"non_ambiguous_members": 5}, {"integrity_ok": False}, {"pooled_recall": math.nan},
               {"lower_bound": None, "pooled_recall": None}):
        assert d(**kw)["outcome"] in ("INSUFFICIENT_EVIDENCE", "INVALID_EVALUATION")
    assert set(decision.OUTCOMES) == {"PASS", "FAIL", "INSUFFICIENT_EVIDENCE", "INVALID_EVALUATION"}


def test_capture_recall_is_reported_separately_and_never_decides():
    cap = {"recall": 0.01, "lower_bound": True, "note": "rule-of-three bound"}
    out = d(capture_recall=cap)
    assert out["outcome"] == "PASS" and out["capture_recall_reported_separately"] == cap
    assert "never decide" in out["capture_recall_note"]
    assert d(capture_recall=None)["capture_recall_reported_separately"] is None
    assert all(r["criterion"] != "capture_recall" for r in out["criteria_results"])


def test_the_approved_criteria_match_b2i_and_every_decision_says_so():
    assert decision.CRITERIA_STATUS == "APPROVED" and decision.CRITERIA_APPROVAL_REFERENCE
    assert decision.CRITERIA == {"precision_min": 0.70, "precision_lower_bound_min": 0.60, "pooled_recall_min": 0.90,
                                 "reporting_floor_non_ambiguous": 100}
    for out in (d(), d(precision=0.1), d(precision=None), d(integrity_ok=False)):
        assert out["authoritative"] is True and out["criteria_status"] == "APPROVED"
        assert out["authorizes_execution_or_deployment"] is False and out["criteria_sha256"] == decision.criteria_sha256()
    assert est.PROPOSED_THRESHOLDS == {"precision_min": 0.70, "precision_lower_bound_min": 0.60,
                                       "pooled_capture_recall_min": decision.CRITERIA["pooled_recall_min"]}


def test_authority_needs_both_an_approved_status_and_a_recorded_reference(monkeypatch):
    monkeypatch.setattr(decision, "CRITERIA_STATUS", "APPROVED")
    monkeypatch.setattr(decision, "CRITERIA_APPROVAL_REFERENCE", None)
    assert decision.criteria_authoritative() is False and d()["authoritative"] is False   # no reference: still not authoritative
    assert "not an acceptance decision" in d()["statement"]
    monkeypatch.setattr(decision, "CRITERIA_APPROVAL_REFERENCE", "owner decision record")
    assert decision.criteria_authoritative() is True and "statement" not in d()
    monkeypatch.setattr(decision, "CRITERIA_STATUS", "PROPOSED_NOT_APPROVED")
    assert decision.criteria_authoritative() is False                                    # a reference alone is not approval
    monkeypatch.setattr(decision, "CRITERIA_STATUS", "APPROVED")
    monkeypatch.setattr(decision, "APPROVED_CRITERIA_SHA256", None)
    assert decision.criteria_authoritative() is False                                    # no frozen hash: not approved


# ================================================================ estimator additions

NONE = {"equity": False, "rates": False, "gold": False}


def sc(item, cell, rel_gold, *, member=True, mech="ORIGINAL", dup="", batch="b1", rows=100, items=10):
    return Scored(item, batch, cell, rows, items, {"equity": "I", "rates": "I", "gold": rel_gold}, "N",
                  {**NONE, "gold": member}, "own", mech, dup)


def test_unique_story_precision_excludes_marked_duplicates_and_near_duplicates():
    items = [sc("D1", "C1", "R"), sc("D2", "C1", "R", mech="DUP_SAME_BATCH"), sc("D3", "C1", "I"),
             sc("D4", "C1", "R", dup="D1"), sc("D5", "C1", "I", mech="SYNDICATED_SAME_BATCH")]
    out = est.unique_story_precision(items, "gold")
    assert out["available"] and out["members_total"] == 5 and out["members_unique_story"] == 2
    assert out["counts"] == {"R": 1, "RL": 0, "I": 1, "A": 0} and out["precision"] == 0.5
    assert est.precision(items, "gold")["precision"] == 0.6                              # all items, for contrast


def test_unique_story_precision_is_unavailable_not_guessed_when_information_is_missing():
    items = [sc("D1", "C1", "R"), Scored("D2", "b1", "C1", 100, 10, {"equity": "I", "rates": "I", "gold": "R"}, "N",
                                        {**NONE, "gold": True})]
    out = est.unique_story_precision(items, "gold")
    assert out == {"available": False, "reason": "duplicate information was not supplied for every series member"}
    assert est.near_dup_count(items) is None


def test_near_dup_count_counts_references_and_zero_is_a_real_zero():
    assert est.near_dup_count([sc("D1", "C1", "R", dup="D2"), sc("D2", "C1", "I")]) == 1
    assert est.near_dup_count([sc("D1", "C1", "R")]) == 0


def test_per_cell_wilson_reports_counts_and_none_for_an_empty_cell():
    items = [sc(f"D{i}", "C1", "R") for i in range(8)] + [sc("D9", "C1", "I"), sc("D10", "C1", "A")]
    out = est.cell_wilson(items, "gold")
    assert out["C1"]["non_ambiguous"] == 9 and out["C1"]["R"] == 8                       # the ambiguous item is excluded
    assert out["C1"]["wilson_95"] == est.wilson(8, 9)
    assert out["C2"] == {"non_ambiguous": 0, "R": 0, "wilson_95": None}                  # missing, not zero


def test_pooled_recall_and_capture_recall_stay_distinct_quantities():
    cells = [sc("D1", "C1", "R", rows=10, items=10), sc("D2", "C2", "R", member=False, rows=10, items=10),
             sc("D3", "C7", "I", member=False, rows=1000, items=10)]
    pooled, capture = est.pooled_recall(cells, "gold"), est.capture_recall(cells, "gold")
    assert pooled == 10 / 20                                                             # C1 to C6 only
    assert capture["lower_bound"] is True and capture["recall"] < pooled                 # the C7 rule-of-three bound lowers it
    assert est.RULE_OF_THREE == 3.0


# ================================================================ bootstrap reproducibility (the CURRENT method)

def boot_items():
    return [sc(f"D{i}", "C1", "R" if (i * 7) % 5 < 3 else "I", batch=f"b{i // 4}") for i in range(40)]


def stat(sample):
    return est.precision(sample, "gold")["precision"]


def test_the_bootstrap_is_the_stdlib_generator_seed_42_and_says_so():
    assert (est.BOOTSTRAP_GENERATOR, est.BOOTSTRAP_SEED, est.BOOTSTRAP_RESAMPLES) == ("random.Random", 42, 2000)
    src = (Path(est.__file__)).read_text(encoding="utf-8")
    assert "random.Random(seed)" in src and "import numpy" not in src and "from numpy" not in src
    assert "does NOT give the same resamples" in src


def test_the_bootstrap_is_deterministic_for_a_seed_and_changes_with_it():
    a = est.cluster_bootstrap(boot_items(), stat, n_resamples=300)
    b = est.cluster_bootstrap(boot_items(), stat, n_resamples=300)
    assert a == b and a["seed"] == 42 and a["batches"] == 10 and a["resamples_used"] == 300

    def sequence(seed):
        seen = []
        est.cluster_bootstrap(boot_items(), lambda s: seen.append(stat(s)) or stat(s), n_resamples=50, seed=seed)
        return seen

    assert sequence(42) == sequence(42) and sequence(42) != sequence(7)


def test_the_bootstrap_matches_an_independent_stdlib_reimplementation_value_for_value():
    items = boot_items()
    groups: dict[str, list] = {}
    for i in items:
        groups.setdefault(i.batch_ts, []).append(i)
    keys = sorted(groups)
    rng = random.Random(42)
    values = []
    for _ in range(200):
        sample = []
        for _k in keys:
            sample.extend(groups[rng.choice(keys)])
        values.append(stat(sample))
    values.sort()
    ref = (est.quantile(values, 0.025), est.quantile(values, 0.975))
    assert est.cluster_bootstrap(items, stat, n_resamples=200)["ci_95"] == ref


def test_the_bootstrap_resamples_whole_batches():
    seen = []

    def spy(sample):
        seen.append({i.batch_ts: sum(1 for j in sample if j.batch_ts == i.batch_ts) for i in sample})
        return 0.5

    est.cluster_bootstrap(boot_items(), spy, n_resamples=20)
    original = {f"b{k}": sum(1 for i in boot_items() if i.batch_ts == f"b{k}") for k in range(10)}
    for counts in seen:
        for batch, n in counts.items():
            assert n % original[batch] == 0                                              # a batch is drawn whole, 0..k times


def test_a_golden_interval_pins_the_current_generator():
    """If this fails, the generator, the seed or the resampling changed. That is a methodology decision and also changes
    the evaluation fingerprint; it must not happen silently."""
    ci = est.cluster_bootstrap(boot_items(), stat, n_resamples=2000)["ci_95"]
    assert ci == pytest.approx(GOLDEN, abs=1e-12)


# Values produced by running the current implementation once (a pin, not an independent validation).
GOLDEN = (0.525, 0.675)


# ================================================================ verified provenance

PLAN = [("D0001", "N"), ("D0002", "Y"), ("D0003", "N"), ("D0004", "Y"), ("D0005", "N"), ("D0006", "N")]


def _csv_bytes(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(ANNOTATION_COLUMNS), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in ANNOTATION_COLUMNS})
    return buf.getvalue().encode("utf-8")


@pytest.fixture()
def folder(tmp_path) -> Paths:
    rf = tmp_path / "review_files"
    rf.mkdir()
    rows = [{"item_id": iid, "gkg_record_id": f"20220301120000-{n}", "batch_ts": "20220301120000",
             "batch_date_utc": "2022-03-01", "available_at_utc": "2022-03-01T12:15:00Z", "source_domain": "example.com",
             "url": f"https://example.com/{n}", "title": f"SYNTHETIC ROW {n}", "mech_dup": "ORIGINAL", "overlap_subset": ov}
            for n, (iid, ov) in enumerate(PLAN, start=1)]
    original = _csv_bytes(rows)
    overlap = _csv_bytes([r for r in rows if r["overlap_subset"] == "Y"])
    (rf / "annotation_A.csv").write_bytes(original)
    (rf / "annotation_B.csv").write_bytes(overlap)
    (rf / "selection_log.json").write_text(json.dumps({"files_sha256": {
        "annotation_A.csv": hashlib.sha256(original).hexdigest(), "annotation_B.csv": hashlib.sha256(overlap).hexdigest()}}),
        encoding="utf-8")
    p = Paths(rf)
    annotate.init(p)
    return p


LABELS = {"rel_equity": "R", "rel_rates": "I", "rel_gold": "I", "amb_code": "", "company_notice": "N", "pol_equity": "POS",
          "pol_rates": "", "pol_gold": "", "near_dup_of": "", "annotator_id": "AB", "annotator_type": "human",
          "label_basis": "own", "labelled_at_utc": "2026-10-19", "note": ""}


def kinds(rep):
    return {p["kind"] for p in rep.problems}


def rewrite(p: Paths, fn, *, log=True):
    rows = annotate._working_rows(p)
    fn(rows)
    data = annotate._csv_bytes(ANNOTATION_COLUMNS, rows)
    p.working.write_bytes(data)
    if log:
        annotate._log(p, {"event": "label", "working_sha256": hashlib.sha256(data).hexdigest()})


def test_a_clean_untouched_dataset_verifies_and_reports_the_real_structure(folder):
    rep = provenance.verify(folder)
    assert rep.ok and rep.problems == [] and rep.status == "VERIFIED"
    assert rep.counts["items"] == 6 and rep.counts["overlap"] == 2 and rep.counts["non_overlap"] == 4
    assert rep.counts["by_origin"] == {"unlabelled": 6} and rep.counts["independent_candidates"] == 0


def test_labels_made_through_the_workflow_keep_their_origin_and_correction_history(folder):
    annotate.save_item(folder, "D0002", dict(LABELS))                                    # overlap, human-only
    annotate.save_item(folder, "D0001", dict(LABELS))
    annotate.save_item(folder, "D0001", {**LABELS, "rel_equity": "RL", "pol_equity": "", "note": "reread the headline"})
    rep = provenance.verify(folder)
    assert rep.ok
    assert rep.items["D0002"]["origin"] == "human_only" and rep.items["D0002"]["independent_candidate"] is True
    assert rep.items["D0001"]["origin"] == "human_only" and rep.items["D0001"]["independent_candidate"] is False
    assert rep.items["D0001"]["corrections"] == 1 and rep.counts["corrections_logged"] == 1
    assert rep.items["D0003"]["origin"] == "unlabelled"


def test_an_unlogged_change_to_the_working_copy_blocks(folder):
    rewrite(folder, lambda rows: rows[0].update(LABELS), log=False)
    rep = provenance.verify(folder)
    assert not rep.ok and "history_mismatch" in kinds(rep)
    folder.merge_log.unlink()                                                            # no history at all, yet labels exist
    assert "history_missing" in kinds(provenance.verify(folder))
    folder.merge_log.parent.mkdir(exist_ok=True)
    folder.merge_log.write_text("", encoding="utf-8")
    folder.working.write_bytes(folder.backup.read_bytes())
    annotate.save_item(folder, "D0003", dict(LABELS))
    rewrite(folder, lambda rows: rows[4].update(LABELS), log=False)                      # edited behind the log's back
    assert "history_mismatch" in kinds(provenance.verify(folder))


@pytest.mark.parametrize("name", ["annotation_B.csv", "selection_log.json", "annotation_A.csv"])
def test_a_missing_required_artifact_blocks_without_inventing_anything(folder, name):
    (folder.review_files / name).unlink()
    rep = provenance.verify(folder)
    assert not rep.ok and kinds(rep) == {"missing_artifact"} and rep.items == {}


def test_a_missing_backup_or_working_copy_blocks(folder):
    folder.backup.unlink()
    assert "missing_artifact" in kinds(provenance.verify(folder))


def test_the_recorded_fingerprints_must_match_the_files(folder):
    (folder.review_files / "annotation_B.csv").write_bytes(b"x")
    assert "fingerprint_mismatch" in kinds(provenance.verify(folder))


def test_the_backup_must_equal_the_original(folder):
    os_chmod = __import__("os").chmod
    os_chmod(folder.backup, 0o666)
    folder.backup.write_bytes(folder.backup.read_bytes() + b"\n")
    assert any("backup differs" in p["detail"] for p in provenance.verify(folder).problems)


def test_a_wrong_overlap_manifest_blocks(folder):
    original = folder.original.read_bytes()
    bad_b = _csv_bytes([r for r in csv.DictReader(io.StringIO(original.decode("utf-8"))) if r["item_id"] in ("D0002",)])
    (folder.review_files / "annotation_B.csv").write_bytes(bad_b)
    log = json.loads(folder.selection_log.read_text())
    log["files_sha256"]["annotation_B.csv"] = hashlib.sha256(bad_b).hexdigest()
    folder.selection_log.write_text(json.dumps(log), encoding="utf-8")
    assert "membership_conflict" in kinds(provenance.verify(folder))


def test_duplicate_missing_and_unknown_working_records_block(folder):
    rows = annotate._working_rows(folder)
    dup, missing, stray = dict(rows[0]), rows[1:], dict(rows[0], item_id="D0099")
    for variant, kind in ((rows + [dup], "duplicate_item"), (missing, "missing_item"), (rows + [stray], "unknown_item")):
        folder.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, variant))
        annotate._log(folder, {"event": "label", "working_sha256": hashlib.sha256(folder.working.read_bytes()).hexdigest()})
        assert kind in kinds(provenance.verify(folder)), kind


def test_changed_source_fields_in_the_working_copy_block(folder):
    rewrite(folder, lambda rows: rows[2].update(title="EDITED", overlap_subset="Y"))
    rep = provenance.verify(folder)
    assert "source_changed" in kinds(rep)


def test_an_ai_based_label_on_an_overlap_item_is_a_conflict_not_a_stratum(folder):
    rewrite(folder, lambda rows: rows[1].update({**LABELS, "label_basis": "accepted_ai"}))     # D0002 is an overlap item
    rep = provenance.verify(folder)
    assert not rep.ok and "overlap_ai_exposed" in kinds(rep)
    assert rep.items["D0002"]["origin"] == "ai_exposed" and rep.items["D0002"]["independent_candidate"] is False


def test_an_ai_based_label_on_a_non_overlap_item_is_ai_exposed_and_not_independent(folder):
    rewrite(folder, lambda rows: rows[2].update({**LABELS, "label_basis": "corrected_ai"}))
    rep = provenance.verify(folder)
    assert rep.ok and rep.items["D0003"]["origin"] == "ai_exposed" and rep.counts["independent_candidates"] == 0


def test_an_unrecognised_label_basis_is_invalid(folder):
    rewrite(folder, lambda rows: rows[2].update({**LABELS, "label_basis": "blind_magic"}))
    assert "origin_invalid" in kinds(provenance.verify(folder))


@pytest.mark.parametrize("ref", ["D9999", "D0003", "x1"])
def test_invalid_duplicate_references_block(folder, ref):
    rewrite(folder, lambda rows: rows[2].update({**LABELS, "near_dup_of": ref}))
    assert "near_dup_invalid" in kinds(provenance.verify(folder))


def test_a_valid_duplicate_reference_is_counted(folder):
    annotate.save_item(folder, "D0003", {**LABELS, "near_dup_of": "D0005"})
    rep = provenance.verify(folder)
    assert rep.ok and rep.counts["near_dup_references"] == 1 and rep.items["D0003"]["near_dup_of"] == "D0005"


def test_a_corrupt_merge_log_blocks(folder):
    folder.merge_log.write_text(folder.merge_log.read_text() + "not json\n{}\n", encoding="utf-8")
    assert "history_unreadable" in kinds(provenance.verify(folder))


def export_row(item, exposure, origin="accepted_ai"):
    return {"item_id": item, "ai_exposure": exposure, "label_origin": origin}


def test_ai_origin_metadata_that_agrees_is_accepted(folder):
    rewrite(folder, lambda rows: rows[2].update({**LABELS, "label_basis": "accepted_ai"}))
    rewrite(folder, lambda rows: rows[0].update(LABELS))
    rep = provenance.merge_ai_origin(provenance.verify(folder), [export_row("D0003", "seen"), export_row("D0001", "none", "human_no_suggestion")])
    assert rep.ok


@pytest.mark.parametrize("rows,kind", [
    ([export_row("D0001", "seen")], "origin_conflict"),                       # working copy says own, export says AI seen
    ([export_row("D0003", "none", "human_no_suggestion")], "origin_conflict"),   # working copy says AI basis, export says none
    ([export_row("D0002", "seen")], "overlap_ai_exposed"),
    ([export_row("D9999", "none")], "unknown_item"),
    ([export_row("D0001", "maybe")], "origin_invalid"),
    ([export_row("D0001", "none", "human_no_suggestion"), export_row("D0001", "none", "human_no_suggestion")], "duplicate_item"),
    ([export_row("D0001", "seen", "human_blind")], "origin_conflict")])
def test_ai_origin_metadata_that_disagrees_blocks(folder, rows, kind):
    rewrite(folder, lambda r: r[2].update({**LABELS, "label_basis": "accepted_ai"}))
    rewrite(folder, lambda r: r[0].update(LABELS))
    assert kind in kinds(provenance.merge_ai_origin(provenance.verify(folder), rows))


def test_an_already_blocked_report_is_never_unblocked_or_extended(folder):
    (folder.review_files / "annotation_B.csv").unlink()
    rep = provenance.verify(folder)
    out = provenance.merge_ai_origin(rep, [export_row("D0001", "none", "human_no_suggestion")])
    assert out is rep and not out.ok and out.items == {}
