"""Estimators (hand-computed examples), agreement arithmetic, and the freeze -> evaluate gate.

Everything here is synthetic: tiny hand-built tables, a synthetic key written to a temporary folder. The real
sealed key is never read, and no real label exists to evaluate.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import annotate, evaluate as ev, estimators as est, overlap_lock
from wealthpilot.data.gdelt.annotate import AnnotationError, Paths
from wealthpilot.data.gdelt.estimators import Scored
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

NONE = {"equity": False, "rates": False, "gold": False}


def it(item, batch, cell, n_rows, n_items, rel, member=(), company="N"):
    full = {"equity": "I", "rates": "I", "gold": "I", **rel}
    return Scored(item, batch, cell, n_rows, n_items, full, company, {**NONE, **{t: True for t in member}})


# ---------------------------------------------------------------- estimators on a hand-computed table

def rates_table(c7_has_r=False):
    return [
        it("r1", "b1", "C1", 2, 2, {"rates": "R"}, ["rates"]),                      # w = 1
        it("a", "b2", "C2", 100, 4, {"rates": "R"}, ["rates"]),                      # w = 25
        it("b", "b2", "C2", 100, 4, {"rates": "R"}, ["rates"]),
        it("c", "b3", "C2", 100, 4, {"rates": "RL"}, ["rates"]),
        it("d", "b3", "C2", 100, 4, {"rates": "A"}, ["rates"]),
        it("e", "b4", "C5", 1000, 10, {"rates": "R"}),                               # w = 100, not a member
        it("f", "b4", "C6", 2000, 20, {"rates": "R"}),                               # w = 100, not a member
        it("g", "b5", "C7", 300, 3, {"rates": "R" if c7_has_r else "I"}),            # w = 100
        it("h", "b5", "C7", 300, 3, {"rates": "I"}),
        it("i", "b6", "C7", 300, 3, {"rates": "I"}),
    ]


def test_precision_excludes_ambiguous_and_brackets_it():
    p = est.precision(rates_table(), "rates")
    assert p["precision"] == pytest.approx(51 / 76)                       # R 51 of non-ambiguous 76
    assert p["bounds_ambiguous_as_not_R_to_R"] == (pytest.approx(51 / 101), pytest.approx(76 / 101))
    assert p["lenient_R_or_RL"] == pytest.approx(1.0)                     # (51 + 25) / 76
    assert p["counts"] == {"R": 3, "RL": 1, "I": 0, "A": 1} and p["non_ambiguous"] == 4
    assert p["reporting"] == "counts_only"                                # fewer than 30 non-ambiguous


def test_pooled_recall_uses_cells_c1_to_c6_only():
    assert est.pooled_recall(rates_table(), "rates") == pytest.approx(51 / 251)   # 51 / (1+25+25+100+100)


def test_capture_recall_is_a_lower_bound_when_c7_has_no_r():
    c = est.capture_recall(rates_table(), "rates")
    assert c["lower_bound"] is True
    assert c["recall"] == pytest.approx(151 / (151 + 100 + 300))          # rule of three: 300 * 3 / 3 = 300
    d = est.capture_recall(rates_table(c7_has_r=True), "rates")
    assert d["lower_bound"] is False and d["recall"] == pytest.approx(151 / (151 + 100 + 100))


def test_undefined_estimates_are_none_not_zero():
    assert est.precision([it("x", "b", "C7", 10, 1, {})], "gold")["precision"] is None
    assert est.pooled_recall([it("x", "b", "C7", 10, 1, {})], "gold") is None
    assert est.capture_recall([], "gold")["recall"] is None


def test_company_statistics():
    items = [it("c4a", "b1", "C4", 1560, 2, {}, company="Y"), it("c4b", "b1", "C4", 1560, 2, {}, company="N"),
             it("m1", "b2", "C2", 20, 2, {"rates": "R"}, ["rates"], company="Y"),
             it("m2", "b2", "C2", 20, 2, {"rates": "R"}, ["rates"], company="N")]
    s = est.company_stats(items)
    assert s["share_labelled_Y"] == 0.5
    assert s["leakage_weighted_share_of_series_members_labelled_Y"]["rates"] == 0.5
    assert s["leakage_weighted_share_of_series_members_labelled_Y"]["gold"] is None


def test_wilson_and_reporting_floors():
    lo, hi = est.wilson(0, 10)
    assert abs(lo) < 1e-3 and hi == pytest.approx(0.2776, abs=1e-3)
    assert est.wilson(5, 0) is None
    assert [est.reporting_floor(n) for n in (0, 29, 30, 99, 100)] == ["counts_only", "counts_only", "indicative",
                                                                    "indicative", "estimate"]


def test_cluster_bootstrap_is_deterministic_and_resamples_whole_batches():
    items = rates_table()
    stat = lambda s: est.precision(s, "rates")["precision"]
    a = est.cluster_bootstrap(items, stat, n_resamples=200)
    b = est.cluster_bootstrap(items, stat, n_resamples=200)
    assert a == b and a["batches"] == 6 and a["resamples_used"] + a["resamples_undefined"] == 200
    lo, hi = a["ci_95"]
    assert 0.0 <= lo <= hi <= 1.0
    one_batch = [it(str(k), "only", "C1", 4, 4, {"gold": "R"}, ["gold"]) for k in range(4)]
    c = est.cluster_bootstrap(one_batch, lambda s: est.precision(s, "gold")["precision"], n_resamples=50)
    assert c["ci_95"] == (1.0, 1.0)


def test_proposed_thresholds_are_labelled_proposed_and_checked_literally():
    ok = est.proposed_thresholds(0.75, 0.65, 0.95)
    assert ok["all_met"] and "PROPOSED" in ok["status"]
    low = est.proposed_thresholds(0.75, 0.55, 0.95)
    assert not low["all_met"] and low["checks"]["bootstrap_lower_bound_at_least_0.60"] is False
    assert est.proposed_thresholds(None, None, None)["all_met"] is False


# ---------------------------------------------------------------- agreement arithmetic (not wired to any dataset)

def test_agreement_matches_hand_calculation():
    r = est.agreement(["R", "R", "I", "I"], ["R", "I", "I", "I"])
    assert r["raw_agreement"] == 0.75 and r["cohen_kappa"] == pytest.approx(0.5)
    assert r["gwet_ac1"] == pytest.approx(0.28125 / 0.53125)
    perfect = est.agreement(["R", "I", "RL"], ["R", "I", "RL"])
    assert perfect["raw_agreement"] == 1.0 and perfect["cohen_kappa"] == pytest.approx(1.0)


def test_agreement_excludes_ambiguous_pairs_and_counts_them():
    r = est.agreement(["R", "A", "I", "I"], ["R", "I", "I", "A"], exclude=frozenset({"A"}))
    assert r["pairs"] == 2 and r["excluded_pairs"] == 2 and r["raw_agreement"] == 1.0


def test_agreement_degenerate_cases_are_none_not_one():
    assert est.agreement(["I", "I"], ["I", "I"])["cohen_kappa"] is None            # no variation: undefined
    assert est.agreement([], [])["raw_agreement"] is None
    with pytest.raises(ValueError):
        est.agreement(["R"], [])


# ---------------------------------------------------------------- the freeze -> evaluate gate (synthetic folder)

N = 8
OVERLAP = {"D0002", "D0005", "D0007"}
# (cell, cell_rows, cell_items, gold label) for D0001..D0008
PLAN = [("C1", 2, 2, "R"), ("C1", 2, 2, "I"), ("C5", 20, 2, "I"), ("C5", 20, 2, "I"),
        ("C7", 40, 4, "I"), ("C7", 40, 4, "I"), ("C7", 40, 4, "I"), ("C7", 40, 4, "I")]


def _csv(columns, rows) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    return buf.getvalue().encode("utf-8")


def logged_write(p: Paths, working) -> None:
    """A write the logged workflow would have made: the working copy and a merge-log record of its hash."""
    sha = hashlib.sha256(annotate._csv_bytes(ANNOTATION_COLUMNS, working)).hexdigest()
    p.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, working))
    annotate._log(p, {"event": "label", "working_sha256": sha})


def make_folder(root: Path, *, labelled: bool, key_hash_ok: bool = True) -> Paths:
    rf = root / "review_files"
    rf.mkdir(parents=True)
    rows, keys = [], []
    for i in range(1, N + 1):
        iid, batch = f"D{i:04d}", f"20220301{12 + i // 4:02d}0000"
        rows.append({"item_id": iid, "gkg_record_id": f"{batch}-{i}", "batch_ts": batch, "batch_date_utc": "2022-03-01",
                     "available_at_utc": "2022-03-01T12:15:00Z", "source_domain": "example.com",
                     "url": f"https://example.com/{i}", "title": f"SYNTHETIC ROW {i}", "mech_dup": "ORIGINAL",
                     "overlap_subset": "Y" if iid in OVERLAP else "N"})
        cell, n_rows, n_items, gold = PLAN[i - 1]
        keys.append({"item_id": iid, "gkg_record_id": f"{batch}-{i}", "batch_ts": batch, "cell": cell,
                     "cell_rows": n_rows, "cell_items": n_items, "member_equity_us": 0, "member_rates_us": 0,
                     "member_gold": 1 if cell == "C1" else 0})
    original = _csv(ANNOTATION_COLUMNS, rows)
    key = _csv(list(keys[0].keys()), keys)
    (rf / "annotation_A.csv").write_bytes(original)
    overlap_manifest = _csv(ANNOTATION_COLUMNS, [r for r in rows if r["overlap_subset"] == "Y"])
    (rf / "annotation_B.csv").write_bytes(overlap_manifest)             # the overlap membership manifest
    (rf / "key_sealed.csv").write_bytes(key)
    key_sha = hashlib.sha256(key).hexdigest() if key_hash_ok else "0" * 64
    (rf / "selection_log.json").write_text(json.dumps({"files_sha256": {
        "annotation_A.csv": hashlib.sha256(original).hexdigest(), "annotation_B.csv": hashlib.sha256(overlap_manifest).hexdigest(),
        "key_sealed.csv": key_sha}}), encoding="utf-8")
    p = Paths(rf)
    annotate.init(p)
    if labelled:
        working = annotate._working_rows(p)
        for r, (cell, _n, _k, gold) in zip(working, PLAN):
            r.update({"rel_equity": "I", "rel_rates": "I", "rel_gold": gold, "company_notice": "N",
                      "pol_gold": "POS" if gold == "R" else "", "annotator_id": "AB", "annotator_type": "human",
                      "label_basis": "own", "labelled_at_utc": "2026-10-16T09:00:00Z"})
        logged_write(p, working)
    return p


@pytest.fixture()
def no_key_reads(monkeypatch):
    calls = []
    monkeypatch.setattr(ev, "_read_key", lambda p: calls.append(1) or pytest.fail("the sealed key was read"))
    return calls


def test_freeze_refuses_incomplete_labels_and_never_touches_the_key(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=False)
    with pytest.raises(AnnotationError, match="0 of 8 items labelled"):
        ev.freeze(p)
    assert not ev.freeze_path(p).exists() and no_key_reads == []


def test_evaluate_refuses_without_a_freeze_and_never_reads_the_key(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    with pytest.raises(AnnotationError, match="not frozen"):
        ev.evaluate(p)
    assert no_key_reads == [] and not ev.results_path(p).exists()


def test_freeze_records_the_labels_once_and_is_read_only(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    rec = ev.freeze(p)
    assert rec["rows"] == 8 and rec["label_basis_counts"] == {"own": 8} and rec["ai_labels_present"] is False
    assert rec["working_sha256"] == hashlib.sha256(p.working.read_bytes()).hexdigest()
    assert ev.freeze_path(p).stat().st_mode & 0o200 == 0
    with pytest.raises(AnnotationError, match="never overwritten"):
        ev.freeze(p)
    assert no_key_reads == []


def test_evaluate_refuses_when_labels_change_after_the_freeze(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    working = annotate._working_rows(p)
    working[2]["rel_gold"] = "R"
    working[2]["pol_gold"] = "POS"
    p.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, working))
    with pytest.raises(AnnotationError, match="changed after the freeze"):
        ev.evaluate(p)
    assert no_key_reads == []


def test_evaluate_refuses_a_key_that_does_not_match_its_build_fingerprint(tmp_path):
    p = make_folder(tmp_path, labelled=True, key_hash_ok=False)
    ev.freeze(p)
    with pytest.raises(AnnotationError, match="does not match the fingerprint"):
        ev.evaluate(p, n_resamples=10)
    assert not ev.results_path(p).exists()


def test_evaluate_computes_aggregates_only_and_never_overwrites(tmp_path):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    out = ev.evaluate(p, n_resamples=60)
    gold = out["themes"]["gold"]
    assert gold["precision"]["precision"] == pytest.approx(0.5)                   # one R, one I among two members
    assert gold["pooled_recall"] == pytest.approx(1.0)
    assert gold["capture_recall"]["recall"] == pytest.approx(1 / 31) and gold["capture_recall"]["lower_bound"]
    assert out["themes"]["equity"]["precision"]["precision"] is None                # no members: undefined, not zero
    assert out["independence"] == "all labels are human labels made without AI suggestions"
    assert "not computed" in out["agreement"] and "approved" in out["status"]
    text = ev.results_path(p).read_text(encoding="utf-8")
    assert "D0001" not in text and "SYNTHETIC" not in text and "gkg_record_id" not in text   # aggregates only
    assert ev.results_path(p).stat().st_mode & 0o200 == 0
    with pytest.raises(AnnotationError, match="never overwritten"):
        ev.evaluate(p, n_resamples=10)


def test_ai_based_labels_are_flagged_as_not_independent(tmp_path, write_export):
    p = make_folder(tmp_path, labelled=True)
    working = annotate._working_rows(p)
    working[2]["label_basis"] = "accepted_ai"                                    # D0003 is a non-overlap item
    logged_write(p, working)
    cols = ["item_id", "annotator_type", "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice",
            "pol_equity", "pol_rates", "pol_gold", "note"]
    p.ai_suggestions.write_bytes(_csv(cols, [{"item_id": "D0003", "annotator_type": "ai", "rel_equity": "I",
                                               "rel_rates": "I", "rel_gold": "I", "company_notice": "N"}]))
    exp = write_export(p, tmp_path / "export", seen={"D0003": "accepted_ai"})
    overlap_lock.create(p)
    rec = ev.freeze(p, exp)
    assert rec["ai_labels_present"] and rec["ai_suggestions_sha256"]
    out = ev.evaluate(p, n_resamples=10, ai_origin_dir=exp)
    assert "NOT independent" in out["independence"] and out["label_basis_counts"] == {"accepted_ai": 1, "own": 7}


def test_an_unusable_key_is_refused_after_the_checks(tmp_path):
    p = make_folder(tmp_path, labelled=True)
    key = (p.review_files / "key_sealed.csv")
    bad = key.read_bytes().replace(b"D0001", b"D9999", 1)          # the key is damaged and re-recorded BEFORE the freeze
    key.write_bytes(bad)
    log = json.loads(p.selection_log.read_text())
    log["files_sha256"]["key_sealed.csv"] = hashlib.sha256(bad).hexdigest()
    p.selection_log.write_text(json.dumps(log), encoding="utf-8")
    ev.freeze(p)
    with pytest.raises(AnnotationError, match="do not cover the same items"):
        ev.evaluate(p, n_resamples=10)


def test_only_the_build_and_the_evaluation_module_refer_to_the_sealed_key():
    pkg = Path(ev.__file__).resolve().parent
    mentions = sorted(f.name for f in pkg.glob("*.py") if "key_sealed" in f.read_text(encoding="utf-8"))
    assert mentions == ["evaluate.py", "review.py"]
    assert "ai_suggestions" not in Path(estimators_path := est.__file__).read_text(encoding="utf-8")
    assert os.path.exists(estimators_path)


# ---------------------------------------------------------------- B2-U7: freeze ordering, provenance and decision output

def _unlock(path):
    os.chmod(path, 0o666)


def test_a_freeze_records_the_evaluation_fingerprint_and_provenance_counts(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    rec = ev.freeze(p)
    fp = rec["evaluation_fingerprint"]
    assert set(fp) == {"code", "protocol", "inputs", "combined_sha256"} and set(fp["code"]) == set(ev.FINGERPRINT_CODE)
    assert fp["protocol"]["criteria_status"] == "APPROVED" and fp["protocol"]["bootstrap"]["generator"] == "random.Random"
    assert fp["inputs"]["annotation_B.csv"] and rec["provenance_counts"]["by_origin"] == {"human_only": 8}
    assert no_key_reads == []


def test_a_freeze_is_refused_while_provenance_is_blocked_and_the_key_stays_closed(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    (p.review_files / "annotation_B.csv").unlink()
    with pytest.raises(AnnotationError, match="provenance is BLOCKED"):
        ev.freeze(p)
    assert not ev.freeze_path(p).exists() and no_key_reads == []


def test_a_freeze_is_refused_when_the_working_copy_was_changed_outside_the_log(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    working = annotate._working_rows(p)
    working[0]["rel_equity"] = "R"
    working[0]["pol_equity"] = "POS"
    p.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, working))                 # no log record
    with pytest.raises(AnnotationError, match="history_mismatch"):
        ev.freeze(p)
    assert no_key_reads == []


def test_a_stale_freeze_after_a_protocol_change_is_refused_before_the_key(tmp_path, no_key_reads, monkeypatch):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    monkeypatch.setattr(ev.decision, "CRITERIA", {**ev.decision.CRITERIA, "precision_min": 0.65})
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation protocol changed"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == [] and not ev.results_path(p).exists()


def test_a_stale_freeze_after_a_bootstrap_generator_seed_change_is_refused(tmp_path, no_key_reads, monkeypatch):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    monkeypatch.setattr(est, "BOOTSTRAP_SEED", 43)
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation protocol"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == []


def test_a_stale_freeze_after_an_implementation_change_is_refused(tmp_path, no_key_reads, monkeypatch):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    monkeypatch.setattr(ev, "FINGERPRINT_CODE", ("estimators.py", "evaluate.py"))          # stands for a changed code set
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation code changed"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == []


def test_a_stale_freeze_after_a_membership_manifest_change_is_refused(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    b = p.review_files / "annotation_B.csv"
    b.write_bytes(b.read_bytes() + b"\n")
    with pytest.raises(AnnotationError, match="stale freeze: the evaluation inputs changed"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == []


def test_a_freeze_record_without_a_fingerprint_is_stale(tmp_path, no_key_reads):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    path = ev.freeze_path(p)
    _unlock(path)
    rec = json.loads(path.read_text(encoding="utf-8"))
    rec.pop("evaluation_fingerprint")
    path.write_text(json.dumps(rec), encoding="utf-8")
    with pytest.raises(AnnotationError, match="records no evaluation fingerprint"):
        ev.evaluate(p, n_resamples=5)
    assert no_key_reads == []


def test_the_evaluation_report_is_complete_and_a_small_sample_can_never_pass(tmp_path):
    p = make_folder(tmp_path, labelled=True)
    ev.freeze(p)
    out = ev.evaluate(p, n_resamples=10)
    assert out["criteria_status"] == "APPROVED" and out["provenance"]["status"] == "VERIFIED"
    assert out["label_origin_counts"] == {"human_only": 8} and out["annotator_near_dup_references"] == 0
    assert out["bootstrap"]["seed"] == 42 and "random.Random" in out["bootstrap"]["generator"]
    assert len(out["evaluation_fingerprint_sha256"]) == 64
    for theme, res in out["themes"].items():
        dec = res["decision"]
        assert dec["outcome"] == "INSUFFICIENT_EVIDENCE" and dec["authoritative"] is True         # 8 items: below the floor
        assert res["unique_story_precision"]["available"] is True
        assert set(res["cell_wilson_unweighted"]) == {"C1", "C2", "C3", "C4", "C5", "C6", "C7"}
        assert set(res["precision_by_label_origin"]["strata"]) == {"human_only", "ai_exposed"}
        assert res["precision_by_label_origin"]["strata"]["ai_exposed"] is None                  # absent, not zero
        assert "capture_recall" in res and dec["capture_recall_reported_separately"] == res["capture_recall"]
    assert out["themes"]["gold"]["precision"]["reporting"] != "estimate"


def test_ai_exposed_labels_are_a_separate_stratum_never_independent(tmp_path, write_export):
    p = make_folder(tmp_path, labelled=True)
    working = annotate._working_rows(p)
    working[2]["label_basis"] = "accepted_ai"                                           # D0003: a non-overlap item
    logged_write(p, working)
    cols = ["item_id", "annotator_type", "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice",
            "pol_equity", "pol_rates", "pol_gold", "note"]
    p.ai_suggestions.write_bytes(_csv(cols, [{"item_id": "D0003", "annotator_type": "ai", "rel_equity": "I",
                                               "rel_rates": "I", "rel_gold": "I", "company_notice": "N"}]))
    exp = write_export(p, tmp_path / "export", seen={"D0003": "accepted_ai"})
    overlap_lock.create(p)
    ev.freeze(p, exp)
    out = ev.evaluate(p, n_resamples=10, ai_origin_dir=exp)
    assert out["label_origin_counts"] == {"human_only": 7, "ai_exposed": 1}
    strata = out["themes"]["gold"]["precision_by_label_origin"]["strata"]
    assert strata["ai_exposed"] is not None and strata["human_only"] is not None            # both strata exist and are separate
    assert strata["ai_exposed"]["members_labelled"] <= 1 and strata["human_only"]["members_labelled"] >= 1
    assert "NOT independent" in out["independence"]

