"""Offline annotation workflow: backup, working copy, batches, validated merge, status.

Synthetic review folder only: titles start with "SYNTHETIC". No labels are invented for real data.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.annotate import AnnotationError, Paths
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

N, OVERLAP = 8, {"D0002", "D0005", "D0007"}


def _write(path: Path, rows: list[dict], columns=ANNOTATION_COLUMNS) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    data = buf.getvalue().encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


@pytest.fixture()
def folder(tmp_path) -> Paths:
    rows = []
    for i in range(1, N + 1):
        iid = f"D{i:04d}"
        rows.append({"item_id": iid, "gkg_record_id": f"20220301120000-{i}", "batch_ts": "20220301120000",
                     "batch_date_utc": "2022-03-01", "available_at_utc": "2022-03-01T12:15:00Z",
                     "page_pub_ts_utc": "", "source_domain": "example.com", "url": f"https://example.com/{i}",
                     "title": f"SYNTHETIC TEST ROW {i}", "mech_dup": "ORIGINAL",
                     "overlap_subset": "Y" if iid in OVERLAP else "N"})
    rf = tmp_path / "review_files"
    data = _write(rf / "annotation_A.csv", rows)
    (rf / "selection_log.json").write_text(json.dumps({"files_sha256": {
        "annotation_A.csv": hashlib.sha256(data).hexdigest()}}), encoding="utf-8")
    return Paths(rf)


GOOD = {"rel_equity": "R", "rel_rates": "I", "rel_gold": "I", "company_notice": "N", "pol_equity": "POS",
        "annotator_id": "AB", "annotator_type": "human", "label_basis": "own", "labelled_at_utc": "2026-10-14"}


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def label_batch(path: Path, values: dict, only: set[str] | None = None) -> None:
    rows = read(path)
    for r in rows:
        if only is None or r["item_id"] in only:
            r.update(values)
    _write(path, rows, columns=tuple(rows[0].keys()))


def test_init_backs_up_and_never_overwrites(folder):
    before = folder.original.read_bytes()
    out = annotate.init(folder)
    assert out["rows"] == N and out["overlap_rows"] == 3
    assert folder.backup.read_bytes() == before == folder.working.read_bytes() == folder.original.read_bytes()
    with pytest.raises(AnnotationError, match="never overwritten"):
        annotate.init(folder)


def test_tampered_generated_file_is_refused(folder):
    folder.original.write_bytes(folder.original.read_bytes().replace(b"SYNTHETIC TEST ROW 3", b"EDITED"))
    with pytest.raises(AnnotationError, match="differs from the hash"):
        annotate.init(folder)


def test_export_gives_overlap_rows_first_with_safe_columns_only(folder):
    annotate.init(folder)
    out = annotate.export_batch(folder, size=2)
    rows = read(Path(out["file"]))
    assert [r["item_id"] for r in rows] == ["D0002", "D0005"] and out["overlap_rows_in_batch"] == 2
    assert "gkg_record_id" not in rows[0] and "batch_ts" not in rows[0]       # provenance stays in the working copy
    assert all(not r["rel_equity"] for r in rows)                                # nothing prefilled
    mixed = annotate.export_batch(folder, size=3, overlap_only=False)
    assert [r["item_id"] for r in read(Path(mixed["file"]))][0] == "D0002"      # overlap still first


def test_valid_merge_updates_only_label_columns(folder):
    annotate.init(folder)
    b = Path(annotate.export_batch(folder, size=3)["file"])
    label_batch(b, GOOD)
    rows = read(b)
    rows[0]["batch_date_utc"] = "01/03/2022"                     # a spreadsheet reformatted context: ignored
    _write(b, rows, columns=tuple(rows[0].keys()))
    out = annotate.merge(folder, b)
    assert out["merged"] == 3 and out["corrections"] == 0
    rep = annotate.validate(folder)
    assert rep.ok and rep.labelled == 3 and rep.overlap_labelled == 3 and not rep.complete
    original = {r["item_id"]: r for r in read(folder.original)}
    for w in read(folder.working):
        assert all(w[c] == original[w["item_id"]][c] for c in annotate.SOURCE_COLUMNS)
    assert folder.original.read_bytes() == folder.backup.read_bytes()            # original untouched


@pytest.mark.parametrize("change,needle", [
    ({"rel_rates": "X"}, "rel_rates must be"),
    ({"rel_gold": "A"}, "amb_code is required"),
    ({"rel_gold": "A", "amb_code": "A2"}, "US themes only"),
    ({"rel_gold": "A", "amb_code": "A9"}, "explained in note"),
    ({"amb_code": "A1"}, "must be blank unless"),
    ({"pol_equity": ""}, "pol_equity is required"),
    ({"pol_rates": "NEG"}, "pol_rates must be blank"),
    ({"pol_equity": "UP"}, "pol_equity is required"),
    ({"company_notice": "Y"}, "never R"),
    ({"company_notice": ""}, "company_notice must be"),
    ({"near_dup_of": "D9999"}, "near_dup_of"),
    ({"annotator_id": ""}, "annotator_id"),
    ({"annotator_id": "me@example.org"}, "never an email"),
    ({"annotator_type": "ai"}, "annotator_type must be 'human'"),
    ({"label_basis": "accepted_ai"}, "overlap rows must be labelled without AI"),
    ({"label_basis": "guess"}, "label_basis must be"),
    ({"labelled_at_utc": "14/10/2026"}, "labelled_at_utc"),
])
def test_merge_rejects_rubric_violations_and_merges_nothing(folder, change, needle):
    annotate.init(folder)
    b = Path(annotate.export_batch(folder, size=3)["file"])
    label_batch(b, {**GOOD, **change})
    out = annotate.merge(folder, b)
    assert out["merged"] == 0 and any(needle in e for errs in out["errors"].values() for e in errs)
    assert annotate.validate(folder).labelled == 0


def test_ai_basis_needs_a_valid_suggestion_for_the_item_and_never_applies_to_overlap(folder):
    annotate.init(folder)
    b = Path(annotate.export_batch(folder, size=5, overlap_only=False)["file"])
    non_overlap = {r["item_id"] for r in read(b) if r["overlap_subset"] == "N"}
    label_batch(b, {**GOOD, "label_basis": "accepted_ai"}, only=non_overlap)
    label_batch(b, GOOD, only=OVERLAP)
    out = annotate.merge(folder, b)
    assert out["merged"] == 0 and any("needs a valid suggestion" in e for errs in out["errors"].values() for e in errs)
    # a stand-in header-only file used to satisfy every item; it must not any more (2026-10-16 fix)
    folder.ai_suggestions.write_text(chr(10).join(["item_id"]) + chr(10), encoding="utf-8")
    assert annotate.merge(folder, b)["merged"] == 0
    # a real, valid suggestion for each non-overlap item in the batch does satisfy those items
    rows = ["item_id,annotator_type,rel_equity,rel_rates,rel_gold,amb_code,company_notice,pol_equity,pol_rates,pol_gold,note"]
    rows += [f"{i},ai,R,I,I,,N,POS,,," for i in sorted(non_overlap)]
    folder.ai_suggestions.write_text(chr(10).join(rows) + chr(10), encoding="utf-8")
    assert annotate.merge(folder, b)["merged"] == 5


def test_batch_ids_cannot_change_and_blank_rows_are_skipped(folder):
    annotate.init(folder)
    b = Path(annotate.export_batch(folder, size=3)["file"])
    rows = read(b)
    rows[0]["item_id"] = "D0001"
    _write(b, rows, columns=tuple(rows[0].keys()))
    with pytest.raises(AnnotationError, match="differ from the exported batch"):
        annotate.merge(folder, b)
    b2 = Path(annotate.export_batch(folder, size=3)["file"])
    label_batch(b2, GOOD, only={"D0002"})
    out = annotate.merge(folder, b2)
    assert out["merged"] == 1 and out["skipped_blank"] == 2


def test_corrections_need_a_note_and_labels_cannot_be_blanked(folder):
    annotate.init(folder)
    b = Path(annotate.export_batch(folder, size=1)["file"])
    label_batch(b, GOOD)
    annotate.merge(folder, b)
    label_batch(b, {**GOOD, "pol_equity": "NEG"})
    out = annotate.merge(folder, b)
    assert out["merged"] == 0 and "reason to note" in str(out["errors"])
    label_batch(b, {**GOOD, "pol_equity": "NEG", "note": "misread the headline direction"})
    assert annotate.merge(folder, b)["corrections"] == 1
    label_batch(b, {c: "" for c in annotate.LABEL_COLUMNS})
    assert "cannot be deleted" in str(annotate.merge(folder, b)["errors"])


def test_tampered_working_copy_and_non_utf8_batch_are_caught(folder):
    annotate.init(folder)
    b = Path(annotate.export_batch(folder, size=1)["file"])
    b.write_bytes(b.read_bytes().replace(b"SYNTHETIC", "SYNTHÉTIC".encode("cp1252")))
    with pytest.raises(AnnotationError, match="not UTF-8"):
        annotate.merge(folder, b)
    folder.working.write_bytes(folder.working.read_bytes().replace(b"https://example.com/4", b"https://example.com/x"))
    rep = annotate.validate(folder)
    assert not rep.ok and "D0004: source fields changed: url" in rep.integrity_errors[0]
    with pytest.raises(AnnotationError, match="integrity"):
        annotate.export_batch(folder)


def test_status_and_completion(folder):
    annotate.init(folder)
    b = Path(annotate.export_batch(folder, size=8, overlap_only=False)["file"])
    label_batch(b, GOOD)
    annotate.merge(folder, b)
    s = annotate.status(folder)
    assert s["labelled"] == 8 and s["overlap_labelled"] == 3 and s["complete"] and s["label_basis"] == {"own": 8}


def test_annotation_helper_never_refers_to_the_sealed_key():
    src = Path(annotate.__file__).read_text(encoding="utf-8")
    assert "key_sealed" not in src and "urlopen" not in src and "transport" not in src


# ---------------------------------------------------------------- B2-R: current behaviour on the six open points
# These tests pin what the validator does TODAY. They change no rule; see reports/phaseB2R_annotation_rubric_addendum.md.

def _errs(row_update: dict, *, item="D0001", overlap="N") -> list[str]:
    row = {"item_id": item, "overlap_subset": overlap, "title": "SYNTHETIC TEST ROW", **GOOD, **row_update}
    ids = {f"D{i:04d}" for i in range(1, N + 1)}
    return annotate.row_errors(row, all_ids=ids)


def test_b2r_point1_only_a_single_bare_ambiguity_code_is_accepted_today():
    assert _errs({"rel_equity": "A", "rel_gold": "A", "pol_equity": "", "amb_code": "A3"}) == []
    multi = _errs({"rel_equity": "A", "rel_gold": "A", "pol_equity": "", "amb_code": "equity:A2;gold:A4"})
    assert any("amb_code is required" in e for e in multi)                  # proposal 1 is NOT supported yet


def test_b2r_point2_near_dup_direction_is_not_enforced_today():
    assert _errs({"near_dup_of": "D0008"}, item="D0001") == []              # a later file position is accepted
    assert _errs({"near_dup_of": "D0001"}, item="D0008") == []
    assert _errs({"near_dup_of": "D0001"}, item="D0001") != []              # never itself


@pytest.mark.parametrize("ts,ok", [
    ("2026-10-14", True), ("2026-10-14T09:30Z", True), ("2026-10-14T09:30:15Z", True),
    ("2026-10-14T09:30:15+05:30", False), ("2026-10-14 09:30", False), ("14-10-2026", False),
])
def test_b2r_point3_timestamp_forms_accepted_today(ts, ok):
    assert (_errs({"labelled_at_utc": ts}) == []) is ok


def test_b2r_point4_uncertain_company_status_with_relevant_is_accepted_today():
    assert _errs({"company_notice": "U"}) == []                              # R + U allowed
    assert any("never R" in e for e in _errs({"company_notice": "Y"}))      # R + Y refused (rubric)


def test_b2r_point6_validator_never_reads_the_title():
    empty_a1 = {"rel_equity": "A", "rel_rates": "A", "rel_gold": "A", "pol_equity": "", "amb_code": "A1"}
    row = {"item_id": "D0001", "overlap_subset": "N", "title": "", **GOOD, **empty_a1}
    assert annotate.row_errors(row, all_ids={"D0001"}) == []
