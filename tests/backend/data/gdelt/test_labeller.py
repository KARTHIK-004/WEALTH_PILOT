"""Interactive human labelling of overlap items (`annotate label`). Scripted answers, synthetic folder.

These tests type labels *as a scripted annotator* to exercise the prompts; no real item is labelled.
B2-U added: early company-notice conflict handling, back navigation, a review screen, answers preserved
across a failed validation, and a save that happens only when the existing validator is satisfied.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt import annotate, labeller
from wealthpilot.data.gdelt.annotate import AnnotationError, Paths
from wealthpilot.data.gdelt.labeller import Labeller
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

N, OVERLAP = 8, ["D0002", "D0005", "D0007"]
CLOCK = datetime(2026, 10, 14, 9, 30, 15, tzinfo=timezone.utc)


def _write(path: Path, rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(ANNOTATION_COLUMNS), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in ANNOTATION_COLUMNS})
    data = buf.getvalue().encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def make_folder(root: Path, title_for: dict[str, str] | None = None) -> Paths:
    rows = []
    for i in range(1, N + 1):
        iid = f"D{i:04d}"
        rows.append({"item_id": iid, "gkg_record_id": f"20220301120000-{i}", "batch_ts": "20220301120000",
                     "batch_date_utc": "2022-03-01", "available_at_utc": "2022-03-01T12:15:00Z",
                     "source_domain": "example.com", "url": f"https://example.com/{i}",
                     "title": (title_for or {}).get(iid, f"SYNTHETIC TEST ROW {i}"), "mech_dup": "ORIGINAL",
                     "overlap_subset": "Y" if iid in OVERLAP else "N"})
    rf = root / "review_files"
    data = _write(rf / "annotation_A.csv", rows)
    (rf / "selection_log.json").write_text(json.dumps({"files_sha256": {
        "annotation_A.csv": hashlib.sha256(data).hexdigest()}}), encoding="utf-8")
    p = Paths(rf)
    annotate.init(p)
    return p


@pytest.fixture()
def folder(tmp_path) -> Paths:
    return make_folder(tmp_path)


def session(p: Paths, answers: list):
    queue, out = list(answers), []

    def fake_input(prompt: str) -> str:
        out.append(prompt)
        if not queue:
            raise EOFError
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    return Labeller(p, input_fn=fake_input, output_fn=out.append, clock=lambda: CLOCK), out


def rows_by_id(p: Paths) -> dict[str, dict]:
    with open(p.working, newline="", encoding="utf-8") as f:
        return {r["item_id"]: r for r in csv.DictReader(f)}


# one complete item for D0002: equity R/POS, rates I, gold I, company N, no duplicate, no note, then Y at review
SIMPLE = ["R", "I", "I", "POS", "N", "", "", "Y"]


def index_of(out: list[str], needle: str, start: int = 0) -> int:
    return next(i for i in range(start, len(out)) if needle in out[i])


# ---------------------------------------------------------------- basic flow (unchanged behaviour)

def test_labels_an_overlap_item_and_records_only_session_facts(folder):
    before = rows_by_id(folder)
    lab, out = session(folder, ["AB", *SIMPLE, "q"])
    summary = lab.run()
    row = rows_by_id(folder)["D0002"]
    assert (row["rel_equity"], row["rel_rates"], row["rel_gold"], row["pol_equity"], row["company_notice"]) == \
        ("R", "I", "I", "POS", "N")
    assert (row["annotator_id"], row["annotator_type"], row["label_basis"], row["labelled_at_utc"]) == \
        ("AB", "human", "own", "2026-10-14T09:30:15Z")
    after = rows_by_id(folder)
    assert all(after[i] == before[i] for i in after if i != "D0002")             # nothing else touched
    assert all(row[c] == before["D0002"][c] for c in annotate.SOURCE_COLUMNS)
    assert summary["saved_this_session"] == 1 and summary["stopped_early"] and summary["overlap_labelled"] == 1
    assert annotate.validate(folder).ok


def test_invalid_answers_are_asked_again_and_lowercase_is_accepted(folder):
    lab, out = session(folder, ["AB", "X", "r", "maybe", "i", "I", "up", "pos", "n", "", "", "Y", "q"])
    lab.run()
    assert sum("Not allowed" in o for o in out) == 3
    assert rows_by_id(folder)["D0002"]["pol_equity"] == "POS"


def test_ambiguity_and_polarity_are_asked_only_when_required(folder):
    lab, out = session(folder, ["AB", "A", "I", "I", "A4", "N", "", "", "Y", "q"])
    lab.run()
    row = rows_by_id(folder)["D0002"]
    assert row["amb_code"] == "A4" and not any(row[c] for c in ("pol_equity", "pol_rates", "pol_gold"))
    assert not any("polarity" in o for o in out)
    lab2, out2 = session(folder, ["AB", "A", "I", "I", "A9", "N", "", "", "subject unclear", "Y", "q"])
    lab2.run()                                                                     # D0005: A9 needs a note
    assert sum("A value is required" in o for o in out2) == 1
    assert rows_by_id(folder)["D0005"]["note"] == "subject unclear"


def test_a2_is_not_offered_when_only_gold_is_ambiguous(folder):
    lab, out = session(folder, ["AB", "I", "I", "A", "A2", "A3", "N", "", "", "Y", "q"])
    lab.run()
    assert sum("Not allowed" in o for o in out) == 1
    assert rows_by_id(folder)["D0002"]["amb_code"] == "A3"


def test_near_duplicate_must_name_an_existing_other_item_at_the_prompt(folder):
    lab, out = session(folder, ["AB", "R", "I", "I", "POS", "N", "D9999", "D0002", "d0005", "", "Y", "q"])
    lab.run()
    assert sum("Not allowed" in o for o in out) == 2                               # unknown ID, and itself
    assert rows_by_id(folder)["D0002"]["near_dup_of"] == "D0005"


# ---------------------------------------------------------------- B2-U: company notice vs R

def test_company_y_with_r_explains_the_rule_and_asks_to_reconsider_each_r_theme(folder):
    lab, out = session(folder, [
        "AB", "R", "I", "R", "POS", "NEG",           # equity R, rates I, gold R, both polarities
        "Y",                                         # company notice Y: conflicts with two R themes
        "RL",                                        # reconsider equity -> RL
        "",                                          # reconsider gold: Enter keeps R (nothing silent)
        "", "",                                      # near duplicate, note
        "Y",                                         # review: refused, a conflict remains
        "company_notice", "N",                       # user changes the company notice
        "Y", "q"])                                   # review clean: save
    lab.run()
    text = "\n".join(out)
    assert "Conflict: company_notice is Y, but these themes are R" in text
    assert "at most RL for every theme" in text and "Nothing is changed for you" in text
    assert sum("Reconsider" in o and "relevance (now R)" in o for o in out) == 2     # one prompt per R theme
    assert "US equity / Nasdaq polarity no longer applies and was cleared" in text   # RL clears its polarity
    refused = index_of(out, "Fix the listed problems first")
    saved = index_of(out, "Saved D0002")
    assert refused < saved
    row = rows_by_id(folder)["D0002"]
    assert (row["rel_equity"], row["rel_gold"], row["pol_gold"], row["pol_equity"], row["company_notice"]) == \
        ("RL", "R", "NEG", "", "N")


def test_nothing_is_changed_silently_when_the_user_keeps_every_conflicting_answer(folder):
    lab, out = session(folder, ["AB", "R", "I", "I", "POS", "Y", "", "", "", "Y", "q"])   # keep R
    summary = lab.run()
    assert summary["saved_this_session"] == 0 and not annotate.is_labelled(rows_by_id(folder)["D0002"])
    assert any("Still conflicting" in o for o in out) and any("Cannot be saved yet" in o for o in out)
    assert not any("Saved D0002" in o for o in out)


def test_entering_r_after_company_y_warns_at_once(folder):
    lab, out = session(folder, ["AB", "I", "I", "I", "Y", "", "", "1", "R", "NEG", "q"])
    lab.run()
    assert any("Conflict: company_notice is Y" in o for o in out)
    assert not annotate.is_labelled(rows_by_id(folder)["D0002"])


# ---------------------------------------------------------------- B2-U: back, edit, preserved answers

def test_back_changes_the_previous_answer_without_losing_the_others(folder):
    lab, out = session(folder, ["AB", "R", "I", "I", "POS", "<", "NEG", "N", "", "", "Y", "q"])
    lab.run()
    row = rows_by_id(folder)["D0002"]
    assert (row["rel_equity"], row["rel_rates"], row["rel_gold"], row["pol_equity"], row["company_notice"]) == \
        ("R", "I", "I", "NEG", "N")
    first_item = out[:index_of(out, "Saved D0002")]
    assert sum("US equity / Nasdaq relevance [R/RL/I/A]" in o for o in first_item) == 1          # never restarted
    assert any("Enter keeps POS" in o for o in out)


def test_back_at_the_first_question_is_harmless(folder):
    lab, out = session(folder, ["AB", "<", *SIMPLE, "q"])
    lab.run()
    assert any("first question" in o for o in out) and annotate.is_labelled(rows_by_id(folder)["D0002"])


def test_review_edit_by_number_keeps_every_other_answer_and_clears_only_what_no_longer_applies(folder):
    lab, out = session(folder, ["AB", "R", "I", "I", "POS", "N", "", "", "1", "RL", "Y", "q"])
    lab.run()
    row = rows_by_id(folder)["D0002"]
    assert (row["rel_equity"], row["rel_rates"], row["rel_gold"], row["company_notice"]) == ("RL", "I", "I", "N")
    assert row["pol_equity"] == ""
    assert any("no longer applies and was cleared" in o for o in out)


def test_review_lists_every_answer_and_the_problems_before_saving(folder):
    lab, out = session(folder, ["AB", *SIMPLE[:-1], "q"])        # stop at the review screen
    lab.run()
    text = "\n".join(out)
    assert "--- Review D0002 (nothing is saved until you type Y) ---" in text
    for label in ("US equity / Nasdaq relevance", "Company or fund notice", "Note"):
        assert label in text
    assert not annotate.is_labelled(rows_by_id(folder)["D0002"])


# ---------------------------------------------------------------- B2-U: validator authority and atomic save

def test_the_review_uses_the_real_validator_and_blocks_saving(folder, monkeypatch):
    monkeypatch.setattr(annotate, "row_errors", lambda *a, **k: ["injected rubric error"])
    lab, out = session(folder, ["AB", "R", "I", "I", "POS", "N", "", "", "Y", "q"])
    summary = lab.run()
    text = "\n".join(out)
    assert "injected rubric error" in text and "Fix the listed problems first" in text
    assert summary["saved_this_session"] == 0 and folder.working.read_bytes() == folder.backup.read_bytes()


def test_a_failed_save_keeps_every_answer_and_returns_to_review(folder, monkeypatch):
    real, calls = annotate.save_item, []

    def flaky(p, item_id, labels, **kw):
        calls.append(labels)
        if len(calls) == 1:
            raise AnnotationError("simulated validator refusal")
        return real(p, item_id, labels, **kw)

    monkeypatch.setattr(annotate, "save_item", flaky)
    lab, out = session(folder, ["AB", "R", "I", "I", "POS", "N", "", "", "Y", "Y", "q"])
    lab.run()
    assert any("Not saved: simulated validator refusal" in o for o in out)
    assert any("Your answers are kept" in o for o in out)
    first_item = out[:index_of(out, "Saved D0002")]
    assert sum("US equity / Nasdaq relevance [R/RL/I/A]" in o for o in first_item) == 1          # no re-asking
    assert calls[0] == calls[1] and rows_by_id(folder)["D0002"]["pol_equity"] == "POS"


def test_save_is_atomic_when_the_write_fails(folder, monkeypatch):
    before = folder.working.read_bytes()

    def boom(*a, **k):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(annotate, "atomic_write", boom)
    lab, _ = session(folder, ["AB", *SIMPLE])
    with pytest.raises(OSError):
        lab.run()
    assert folder.working.read_bytes() == before


def test_the_validator_itself_still_refuses_company_y_with_r(folder):
    labels = {c: "" for c in annotate.LABEL_COLUMNS}
    labels.update(rel_equity="R", rel_rates="I", rel_gold="I", pol_equity="POS", company_notice="Y",
                  annotator_id="AB", annotator_type="human", label_basis="own", labelled_at_utc="2026-10-14")
    with pytest.raises(AnnotationError, match="never R"):
        annotate.save_item(folder, "D0002", labels)
    assert folder.working.read_bytes() == folder.backup.read_bytes()


# ---------------------------------------------------------------- resume, skip, quit

def test_quit_mid_item_and_mid_review_saves_nothing_and_the_next_session_resumes(folder):
    before = folder.working.read_bytes()
    lab, _ = session(folder, ["AB", "R", "q"])
    assert lab.run()["saved_this_session"] == 0 and folder.working.read_bytes() == before
    lab2, _ = session(folder, ["AB", "R", "I", "I", "POS", "N", "", "", "q"])           # quit at the review screen
    assert lab2.run()["saved_this_session"] == 0 and folder.working.read_bytes() == before
    lab3, out3 = session(folder, ["AB", *SIMPLE, "q"])
    lab3.run()
    assert any("=== D0002" in o for o in out3) and annotate.is_labelled(rows_by_id(folder)["D0002"])


@pytest.mark.parametrize("interrupt", [EOFError(), KeyboardInterrupt()])
def test_end_of_input_and_ctrl_c_quit_safely(folder, interrupt):
    before = folder.working.read_bytes()
    lab, _ = session(folder, ["AB", "R", interrupt])
    assert lab.run()["stopped_early"] and folder.working.read_bytes() == before


def test_skip_leaves_the_item_unlabelled_and_moves_on(folder):
    lab, out = session(folder, ["AB", "s", *SIMPLE, "q"])
    summary = lab.run()
    rows = rows_by_id(folder)
    assert not annotate.is_labelled(rows["D0002"]) and annotate.is_labelled(rows["D0005"])
    assert summary["skipped_this_session"] == 1


def test_existing_valid_annotations_are_untouched_by_later_sessions(folder):
    session(folder, ["AB", *SIMPLE, "q"])[0].run()
    saved = rows_by_id(folder)["D0002"]
    session(folder, ["CD", "R", "I", "q"])[0].run()                                    # a later partial session
    assert rows_by_id(folder)["D0002"] == saved


def test_help_explains_the_company_notice_rule(folder):
    lab, out = session(folder, ["AB", "?", "q"])
    lab.run()
    text = "\n".join(out)
    assert "Y can not be combined with R" in text and "dividend declaration" in text


# ---------------------------------------------------------------- overlap-only, revisit, exposure

def test_only_overlap_items_are_offered_and_others_are_refused(folder):
    lab, out = session(folder, ["AB", *SIMPLE, *SIMPLE, *SIMPLE])
    summary = lab.run()
    shown = [o.split()[1] for o in out if o.startswith("=== ")]
    assert shown == OVERLAP and summary["overlap_labelled"] == 3
    assert not any(annotate.is_labelled(r) for i, r in rows_by_id(folder).items() if i not in OVERLAP)
    lab2, _ = session(folder, ["AB"])
    with pytest.raises(AnnotationError, match="not an overlap item"):
        lab2.revisit("D0001")


def test_revisit_starts_from_the_current_labels_and_needs_a_correction_reason(folder):
    session(folder, ["AB", *SIMPLE, "q"])[0].run()
    unchanged = folder.working.read_bytes()
    lab, _ = session(folder, ["AB", "N"])
    lab.revisit("D0002")
    assert folder.working.read_bytes() == unchanged                                   # declined
    lab1, out1 = session(folder, ["AB", "Y", "Y"])                                     # confirm, then Y without edits
    lab1.revisit("D0002")
    assert folder.working.read_bytes() == unchanged and any("Nothing changed" in o for o in out1)
    lab2, out2 = session(folder, ["AB", "Y", "pol_equity", "NEG", "Y", "", "misread direction"])
    lab2.revisit("D0002")
    row = rows_by_id(folder)["D0002"]
    assert row["pol_equity"] == "NEG" and row["note"] == "correction: misread direction"
    assert row["rel_equity"] == "R" and row["company_notice"] == "N"                  # other answers kept
    assert any("A value is required" in o for o in out2)                              # an empty reason is refused
    log = [json.loads(line) for line in folder.merge_log.read_text().splitlines()]
    assert log[-1]["event"] == "label" and log[-1]["correction"] is True


def test_tampered_working_copy_is_refused(folder):
    folder.working.write_bytes(folder.working.read_bytes().replace(b"https://example.com/2", b"https://x.org/2"))
    lab, _ = session(folder, ["AB"])
    with pytest.raises(AnnotationError, match="integrity"):
        lab.run()


def test_no_sealed_key_or_ai_suggestion_content_is_ever_shown(tmp_path):
    p = make_folder(tmp_path, {"D0002": "SYNTHETIC \x1b[31mred\x1b[0m TITLE‮"})
    (p.review_files / "key_sealed.csv").write_text("item_id,cell\nD0002,KEYMARKER_C1\n", encoding="utf-8")
    p.ai_suggestions.write_text("item_id,rel_equity\nD0002,AIMARKER_R\n", encoding="utf-8")
    lab, out = session(p, ["AB", "R", "I", "R", "POS", "NEG", "Y", "", "", "", "", "?", "<", "q"])
    lab.run()                                                                         # also exercises the new screens
    text = "\n".join(out)
    assert "KEYMARKER" not in text and "AIMARKER" not in text            # planted data never appears
    assert "No AI suggestions are shown for these items" in text         # the notice is the only mention
    assert "\x1b" not in text and "‮" not in text and "SYNTHETIC" in text      # control chars stripped
    assert not any(w in text for w in ("cell", "member_", "captured", "weight"))
    src = Path(labeller.__file__).read_text(encoding="utf-8")
    assert "key_sealed" not in src and "ai_suggestions" not in src and "urlopen" not in src


def test_cli_label_runs_offline_and_quits_cleanly(tmp_path, monkeypatch, capsys):
    from wealthpilot.data.gdelt.cli import main
    root = tmp_path / "out"
    make_folder(root / "review" / "b2i_review_v1")
    cfg = tmp_path / "run.yaml"
    cfg.write_text(f"output_root: {root.as_posix()}\n", encoding="utf-8")
    answers = iter(["AB", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert main(["annotate", "label", "--config", str(cfg)]) == 0
    assert '"saved_this_session": 0' in capsys.readouterr().out


@pytest.mark.parametrize("encoding", ["cp437", "cp1252", "utf-8"])
def test_titles_that_the_console_cannot_encode_never_crash_the_labeller(tmp_path, encoding):
    """Real GDELT headlines are international. Under a legacy Windows console encoding, printing one must
    not raise (the CLI replaces unprintable characters), and a quit at the first prompt saves nothing."""
    import os
    import subprocess
    import sys

    root = tmp_path / "out"
    p = make_folder(root / "review" / "b2i_review_v1", {"D0002": "SYNTHETIC \u65e5\u672c\u8a9e headline \U0001F600 caf\u00e9"})
    cfg = tmp_path / "run.yaml"
    cfg.write_text(f"output_root: {root.as_posix()}\n", encoding="utf-8")
    repo = Path(__file__).resolve().parents[4]
    env = {**os.environ, "PYTHONIOENCODING": encoding, "PYTHONPATH": str(repo / "backend")}
    before = p.working.read_bytes()
    run = subprocess.run([sys.executable, "-m", "wealthpilot.data.gdelt", "annotate", "label", "--config", str(cfg)],
                         input=b"AB\nq\n", capture_output=True, env=env, timeout=120, cwd=repo)
    assert run.returncode == 0, run.stderr.decode(errors="replace")[-400:]
    assert b"Traceback" not in run.stderr and b"UnicodeEncodeError" not in run.stderr
    assert "=== D0002" in run.stdout.decode(encoding, errors="replace")
    assert p.working.read_bytes() == before
