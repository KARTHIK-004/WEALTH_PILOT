"""AI-suggestion validation (the 2026-10-16 fix of the gap found in the B2-T proposal).

Before the fix, the validator checked only that `ai_suggestions_A.csv` *existed*, so any file (even one
holding only a header) satisfied an AI-based `label_basis` for every item. These tests, all on synthetic
folders in temporary directories, prove that an AI basis now needs a valid suggestion **for that item**.

No suggestion file is ever created in the real dataset folder, and no suggestion is generated: the
fixtures below are hand-written synthetic rows.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import annotate, labeller
from wealthpilot.data.gdelt.annotate import Paths, load_ai_suggestions, row_errors
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

N = 8
OVERLAP = {"D0002", "D0005", "D0007"}
ALL_IDS = {f"D{i:04d}" for i in range(1, N + 1)}
SUG_COLS = ["item_id", "annotator_type", "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice",
            "pol_equity", "pol_rates", "pol_gold", "note"]
GOOD_SUG = {"annotator_type": "ai", "rel_equity": "R", "rel_rates": "I", "rel_gold": "I", "amb_code": "",
            "company_notice": "N", "pol_equity": "POS", "pol_rates": "", "pol_gold": "", "note": ""}
HUMAN = {"rel_equity": "R", "rel_rates": "I", "rel_gold": "I", "company_notice": "N", "pol_equity": "POS",
         "annotator_id": "AB", "annotator_type": "human", "labelled_at_utc": "2026-10-16"}


def _csv(columns: list[str], rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    return buf.getvalue().encode("utf-8")


@pytest.fixture()
def folder(tmp_path) -> Paths:
    rows = [{"item_id": f"D{i:04d}", "gkg_record_id": f"20220301120000-{i}", "batch_ts": "20220301120000",
             "batch_date_utc": "2022-03-01", "available_at_utc": "2022-03-01T12:15:00Z",
             "source_domain": "example.com", "url": f"https://example.com/{i}", "title": f"SYNTHETIC ROW {i}",
             "mech_dup": "ORIGINAL", "overlap_subset": "Y" if f"D{i:04d}" in OVERLAP else "N"}
            for i in range(1, N + 1)]
    rf = tmp_path / "review_files"
    rf.mkdir()
    data = _csv(list(ANNOTATION_COLUMNS), rows)
    (rf / "annotation_A.csv").write_bytes(data)
    (rf / "selection_log.json").write_text(json.dumps({"files_sha256": {
        "annotation_A.csv": hashlib.sha256(data).hexdigest()}}), encoding="utf-8")
    p = Paths(rf)
    annotate.init(p)
    return p


def suggestions(p: Paths, rows: list[dict], columns: list[str] = SUG_COLS) -> None:
    p.ai_suggestions.write_bytes(_csv(columns, rows))


def sug(item_id: str, **over) -> dict:
    return {"item_id": item_id, **GOOD_SUG, **over}


def load(p: Paths):
    return load_ai_suggestions(p, all_ids=ALL_IDS, overlap_ids=OVERLAP)


def ai_row_errors(item_id: str, valid: frozenset[str], basis: str = "accepted_ai",
                  overlap: str = "N") -> list[str]:
    row = {"item_id": item_id, "overlap_subset": overlap, **HUMAN, "label_basis": basis}
    return row_errors(row, all_ids=ALL_IDS, ai_suggested_ids=valid)


# ---------------------------------------------------------------- the original defect

def test_a_header_only_file_satisfies_no_item(folder):
    suggestions(folder, [], columns=["item_id"])
    res = load(folder)
    assert res.present and res.valid_ids == frozenset() and res.problems
    assert ai_row_errors("D0003", res.valid_ids)


def test_one_items_suggestion_cannot_satisfy_another_item(folder):
    suggestions(folder, [sug("D0003")])
    res = load(folder)
    assert res.valid_ids == {"D0003"} and not res.problems
    assert ai_row_errors("D0003", res.valid_ids) == []
    assert any("needs a valid suggestion for this item" in e for e in ai_row_errors("D0004", res.valid_ids))


def test_an_ai_basis_fails_closed_when_no_ids_are_supplied():
    errs = row_errors({"item_id": "D0003", "overlap_subset": "N", **HUMAN, "label_basis": "accepted_ai"},
                      all_ids=ALL_IDS)
    assert any("needs a valid suggestion" in e for e in errs)


@pytest.mark.parametrize("basis", ["accepted_ai", "corrected_ai", "rejected_ai"])
def test_each_ai_basis_needs_the_items_own_valid_suggestion(basis):
    assert ai_row_errors("D0003", frozenset({"D0003"}), basis) == []
    assert ai_row_errors("D0003", frozenset({"D0004"}), basis)


def test_an_overlap_row_never_accepts_an_ai_basis_even_with_a_suggestion():
    errs = ai_row_errors("D0002", frozenset({"D0002"}), overlap="Y")
    assert any("overlap rows must be labelled without AI" in e for e in errs)


# ---------------------------------------------------------------- file and row validation (all fail closed)

@pytest.mark.parametrize("row,needle", [
    (sug("D9999"), "unknown item_id"),
    (sug("D0002"), "overlap item must not have an AI suggestion"),
    (sug("D0003", annotator_type="human"), "annotator_type must be 'ai'"),
    (sug("D0003", annotator_type=""), "annotator_type must be 'ai'"),
    (sug("D0003", company_notice="Y"), "never R"),
    (sug("D0003", rel_equity="X"), "rel_equity must be"),
    (sug("D0003", pol_equity=""), "pol_equity is required"),
    (sug("D0003", rel_gold="A"), "amb_code is required"),
    (sug("D0003", amb_code="A1"), "amb_code must be blank"),
    (sug("", rel_equity="R"), "empty item_id"),
])
def test_an_invalid_suggestion_row_is_rejected_and_listed(folder, row, needle):
    suggestions(folder, [row, sug("D0004")])
    res = load(folder)
    assert any(needle in p for p in res.problems)
    assert res.valid_ids == {"D0004"}                              # the good row is unaffected


def test_duplicate_suggestions_for_one_item_invalidate_every_copy(folder):
    suggestions(folder, [sug("D0003"), sug("D0003", rel_equity="RL", pol_equity=""), sug("D0004")])
    res = load(folder)
    assert res.valid_ids == {"D0004"} and sum("more than one suggestion" in p for p in res.problems) == 2


def test_missing_columns_or_duplicate_headers_invalidate_the_whole_file(folder):
    suggestions(folder, [sug("D0003")], columns=[c for c in SUG_COLS if c != "company_notice"])
    res = load(folder)
    assert res.valid_ids == frozenset() and "missing columns: company_notice" in res.problems[0]
    folder.ai_suggestions.write_bytes((",".join(SUG_COLS + ["note"]) + chr(10)).encode())
    assert load(folder).valid_ids == frozenset()


def test_extra_provenance_columns_are_allowed(folder):
    suggestions(folder, [{**sug("D0003"), "model_id": "synthetic-model", "generated_at_utc": "2026-10-16T00:00:00Z"}],
                columns=SUG_COLS + ["model_id", "generated_at_utc"])
    assert load(folder).valid_ids == {"D0003"}


def test_wrong_field_counts_and_bad_encodings_fail_closed(folder):
    header = ",".join(SUG_COLS)
    short = "D0003,ai,R,I"
    folder.ai_suggestions.write_bytes((header + chr(10) + short + chr(10)).encode())
    res = load(folder)
    assert res.valid_ids == frozenset() and "wrong number of fields" in res.problems[0]
    long_row = ",".join(["D0003", "ai", "R", "I", "I", "", "N", "POS", "", "", "", "extra"])
    folder.ai_suggestions.write_bytes((header + chr(10) + long_row + chr(10)).encode())
    assert load(folder).valid_ids == frozenset()
    folder.ai_suggestions.write_bytes(header.encode() + chr(10).encode() + b"D0003,ai,R,I,I,,N,POS,,,\xff\xfe" + chr(10).encode())
    res = load(folder)
    assert res.valid_ids == frozenset() and "unreadable" in res.problems[0]


def test_a_byte_order_mark_is_tolerated(folder):
    folder.ai_suggestions.write_bytes(b"\xef\xbb\xbf" + _csv(SUG_COLS, [sug("D0003")]))
    assert load(folder).valid_ids == {"D0003"}


def test_a_directory_at_the_suggestion_path_is_refused(folder):
    folder.ai_suggestions.mkdir()
    res = load(folder)
    assert res.present and res.valid_ids == frozenset() and "not a regular file" in res.problems[0]


def test_a_missing_file_is_reported_as_absent(folder):
    res = load(folder)
    assert not res.present and res.valid_ids == frozenset() and res.problems == ()


# ---------------------------------------------------------------- wiring: validate, merge, human-only flow

def labelled_working(folder: Paths, item: str, basis: str) -> None:
    rows = annotate._working_rows(folder)
    row = next(r for r in rows if r["item_id"] == item)
    row.update({"rel_equity": "R", "rel_rates": "I", "rel_gold": "I", "company_notice": "N", "pol_equity": "POS",
                "annotator_id": "AB", "annotator_type": "human", "label_basis": basis,
                "labelled_at_utc": "2026-10-16"})
    folder.working.write_bytes(annotate._csv_bytes(ANNOTATION_COLUMNS, rows))


def test_validate_flags_an_ai_basis_without_that_items_suggestion(folder):
    labelled_working(folder, "D0003", "accepted_ai")
    suggestions(folder, [sug("D0004")])
    rep = annotate.validate(folder)
    assert "D0003" in rep.errors and not rep.ok
    suggestions(folder, [sug("D0003")])
    assert annotate.validate(folder).ok


def test_validate_reports_file_problems_when_an_ai_label_depends_on_the_file(folder):
    labelled_working(folder, "D0003", "accepted_ai")
    suggestions(folder, [sug("D0003"), sug("D0002")])
    rep = annotate.validate(folder)
    assert any("ai_suggestions_A.csv" in e and "overlap item" in e for e in rep.integrity_errors)


def test_merge_reports_the_suggestion_file_problems(folder):
    b = Path(annotate.export_batch(folder, size=5, overlap_only=False)["file"])
    rows = list(csv.DictReader(b.open(newline="", encoding="utf-8")))
    for r in rows:
        r.update(rel_equity="R", rel_rates="I", rel_gold="I", company_notice="N", pol_equity="POS",
                 annotator_id="AB", annotator_type="human", label_basis="own" if r["overlap_subset"] == "Y" else
                 "accepted_ai", labelled_at_utc="2026-10-16")
    b.write_bytes(_csv(list(rows[0].keys()), rows))
    suggestions(folder, [sug("D0003", annotator_type="human")])
    out = annotate.merge(folder, b)
    assert out["merged"] == 0 and any("annotator_type must be 'ai'" in m for m in out["ai_suggestions_problems"])


def test_the_human_only_flow_never_reads_the_suggestion_file(folder, monkeypatch):
    suggestions(folder, [sug("D0003")])                                     # present, but nothing needs it
    calls = []
    monkeypatch.setattr(annotate, "load_ai_suggestions", lambda *a, **k: calls.append(1) or pytest.fail("read"))
    assert annotate.validate(folder).ok
    assert annotate.status(folder)["integrity_ok"]
    annotate.export_batch(folder, size=2)
    answers = iter(["AB", "R", "I", "I", "POS", "N", "", "", "Y", "q"])
    lab = labeller.Labeller(folder, input_fn=lambda prompt: next(answers), output_fn=lambda text: None)
    assert lab.run()["saved_this_session"] == 1
    assert calls == []


def test_a_corrupt_suggestion_file_does_not_block_human_only_work(folder):
    folder.ai_suggestions.write_bytes(b"\xff\xfe not a csv")
    assert annotate.validate(folder).ok
    assert annotate.export_batch(folder, size=1)["rows"] == 1


def test_save_item_still_refuses_every_ai_basis(folder):
    suggestions(folder, [sug("D0003")])                                     # even a valid suggestion
    labels = {c: "" for c in annotate.LABEL_COLUMNS}
    labels.update(rel_equity="R", rel_rates="I", rel_gold="I", pol_equity="POS", company_notice="N",
                  annotator_id="AB", annotator_type="human", label_basis="accepted_ai", labelled_at_utc="2026-10-16")
    with pytest.raises(annotate.AnnotationError, match="needs a valid suggestion"):
        annotate.save_item(folder, "D0003", labels)
