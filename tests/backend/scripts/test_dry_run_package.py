"""The fictional dry run's annotator package, DRAFT manifest, independence gate and blind adjudication worklist (scripts/build_dry_run_package.py, scripts/pilot_disagreements.py).

Offline and file-only: the builder is pointed at a temporary directory for writes, registers and annotator sheets are fabricated inside the tests (never stored), the baseline is never imported or run,
and nothing here measures accuracy or freezes the rubric.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "datasets" / "rubric_examples" / "pilot_pack_v0"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load("build_dry_run_package")
helper = load("pilot_disagreements")


def register(tmp_path, rows, header=builder.REGISTER_COLUMNS):
    path = tmp_path / "register.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


GOOD = [("A-01", "annotator", "yes", "2026-10-21"), ("A-02", "annotator", "yes", "2026-10-21"), ("J-01", "adjudicator", "yes", "2026-10-21")]


# ------------------------------------------------------------------ the independence gate

def test_without_a_register_distribution_is_blocked_and_says_why():
    blockers = builder.check_register(None)
    assert len(blockers) == 1 and "not yet identified" in blockers[0]


def test_two_independent_annotators_and_one_adjudicator_pass_the_gate(tmp_path):
    assert builder.check_register(register(tmp_path, GOOD)) == []


@pytest.mark.parametrize("rows, expected", [
    (GOOD[:1] + GOOD[2:], "need 2 independent annotators, register has 1"),
    (GOOD[:2], "need 1 independent adjudicator, register has 0"),
    ([GOOD[0], GOOD[1], ("J-01", "adjudicator", "no", "2026-10-21")], "J-01 is not attested independent of the rubric author"),
    ([GOOD[0], GOOD[1], ("J-01", "adjudicator", "", "2026-10-21")], "J-01 is not attested independent"),
    ([GOOD[0], ("A-01", "annotator", "yes", "x"), GOOD[2]], "unique"),
    ([GOOD[0], GOOD[1], ("J-01", "reviewer", "yes", "x")], "must be annotator or adjudicator"),
])
def test_an_incomplete_or_unattested_register_is_refused(tmp_path, rows, expected):
    assert any(expected in b for b in builder.check_register(register(tmp_path, rows)))


def test_a_malformed_or_missing_register_is_refused(tmp_path):
    assert "exactly the columns" in builder.check_register(register(tmp_path, [], header=("name", "role")))[0]
    assert "not found" in builder.check_register(tmp_path / "nope.csv")[0]


# ------------------------------------------------------------------ package and DRAFT manifest

def test_the_annotator_excerpt_holds_only_the_marked_rubric_parts():
    excerpt = builder.extract_annotator_rubric((ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md").read_text(encoding="utf-8"))
    assert excerpt.startswith("# Annotation rules (rubric v0-draft: labelling rules and flag definitions)") and "## 1. Scope" in excerpt and "### Flags" in excerpt
    for later in ("## 4. Record format", "## 5. Separation of data", "## 6.", "## 7.", "## 8.", "Open owner decisions", "freeze manifest", "provenance"):
        assert later not in excerpt, later


def test_building_writes_only_the_allowed_files_and_a_draft_unfrozen_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "PACKAGE", tmp_path / "package")
    monkeypatch.setattr(builder, "AUTHOR", tmp_path / "author_only")
    monkeypatch.setattr(builder, "MANIFEST", tmp_path / "author_only" / "DRAFT_MANIFEST.json")
    manifest = builder.build(None)
    assert sorted(p.name for p in (tmp_path / "package").iterdir()) == sorted(builder.PACKAGE_FILES)
    assert manifest["manifest_status"] == "DRAFT" and manifest["frozen"] is False and manifest["freeze_process_completed"] is False
    assert manifest["rubric_version"] == "v0-draft" and manifest["annotation_status"] == "NOT STARTED" and manifest["text_count"] == 30
    assert manifest["distribution_ready"] is False and manifest["distribution_blockers"] and "withdraw" in manifest["future_real_text_blocker"]
    assert manifest["baseline_status"].startswith("UNVALIDATED_BASELINE") and manifest["baseline_method_version_recorded_only"] == "user_text_rules_v1"
    assert manifest["owner_decisions_in_force"]["O2"] == manifest["owner_decisions_in_force"]["O3"] == manifest["owner_decisions_in_force"]["O7"] == "unresolved"
    assert manifest["owner_decisions_in_force"]["O5"].startswith("PROPOSED") and manifest["owner_decisions_in_force"]["O6"].startswith("PROPOSED")
    assert "FICTIONAL" in manifest["data_kind"] and len(manifest["freeze_steps_remaining"]) >= 4
    ready = builder.build(register(tmp_path, GOOD))
    assert ready["distribution_ready"] is True and ready["frozen"] is False                  # an independence attestation distributes the package; it never freezes the rubric


def test_the_committed_package_matches_its_manifest_and_leaks_nothing_author_only():
    assert builder.verify() == []
    package = PACK / "package"
    assert sorted(p.name for p in package.iterdir()) == sorted(builder.PACKAGE_FILES)
    for p in package.iterdir():
        body = p.read_text(encoding="utf-8").lower()
        for word in ("author_challenge_map", "author_only", "pre_annotation", "draft_manifest", "participant_register", "owner decision", "user_text_rules"):
            assert word not in body, (p.name, word)
    manifest = json.loads((PACK / "author_only" / "DRAFT_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["frozen"] is False and manifest["manifest_status"] == "DRAFT" and manifest["distribution_ready"] is False
    assert (package / "pilot_texts.jsonl").read_bytes() == (PACK / "annotator" / "pilot_texts.jsonl").read_bytes()


def test_verification_catches_tampering_and_a_changed_rubric(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "PACKAGE", tmp_path / "package")
    monkeypatch.setattr(builder, "AUTHOR", tmp_path / "author_only")
    monkeypatch.setattr(builder, "MANIFEST", tmp_path / "author_only" / "DRAFT_MANIFEST.json")
    builder.build(None)
    assert builder.verify() == []
    (tmp_path / "package" / "challenge_map.json").write_text("{}", encoding="utf-8")
    assert any("package files are" in p for p in builder.verify())
    (tmp_path / "package" / "challenge_map.json").unlink()
    (tmp_path / "package" / "INSTRUCTIONS.md").write_text("see author_only/challenge notes", encoding="utf-8")
    problems = builder.verify()
    assert any("author-only wording" in p for p in problems) and any("differs from the manifest hash" in p for p in problems)
    manifest = json.loads((tmp_path / "author_only" / "DRAFT_MANIFEST.json").read_text(encoding="utf-8"))
    manifest["frozen"] = True
    (tmp_path / "author_only" / "DRAFT_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert any("must stay a DRAFT" in p for p in builder.verify())


def test_the_builder_never_runs_or_imports_the_baseline_and_computes_no_score():
    source = (ROOT / "scripts" / "build_dry_run_package.py").read_text(encoding="utf-8")
    imports = "\n".join(line for line in source.splitlines() if line.startswith(("import ", "from ")))
    assert "wealthpilot" not in imports and "user_text_sentiment" not in imports
    for word in ("accuracy", "precision", "recall", "kappa"):
        assert word not in source.lower().replace("no score", ""), word


# ------------------------------------------------------------------ blind adjudication

COLS = ["id", "annotator_id", "sentiment", "emotional_tone", "emotional_tone_proposed", "topics", "preferences", "contradictory", "ambiguous_tone", "language", "hedged", "negation", "difficulty", "rubric_unclear", "note"]


def sheet(tmp_path, who, labels, notes=None):
    path = tmp_path / f"{who}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for tid, sentiment in labels.items():
            w.writerow({**{c: "" for c in COLS}, "id": tid, "annotator_id": who, "sentiment": sentiment, "rubric_unclear": "true" if notes and tid in notes else "", "note": (notes or {}).get(tid, "")})
    return path


def test_blind_mode_hides_annotator_identities_and_varies_the_order_per_text(tmp_path, capsys):
    ids = {f"pilot-{i:03d}": ("neutral" if i % 2 else "mixed") for i in range(1, 25)}
    flipped = {k: ("mixed" if v == "neutral" else "neutral") for k, v in ids.items()}
    a = sheet(tmp_path, "ANN-RED", ids, {"pilot-001": "signed ANN-RED note"})
    b = sheet(tmp_path, "ANN-BLUE", flipped)
    assert helper.main(["--blind", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "ANN-RED" not in out.replace("signed ANN-RED note", "") and "ANN-BLUE" not in out
    assert "S1=" in out and "S2=" in out
    first_s1 = {line.split()[2] for line in out.splitlines() if line.startswith("DIFFER") and "S1=neutral" in line}
    first_s1_other = {line.split()[2] for line in out.splitlines() if line.startswith("DIFFER") and "S1=mixed" in line}
    assert first_s1 and first_s1_other                                                       # S1 is sometimes one annotator and sometimes the other
    assert helper.main([str(a), str(b)]) == 0
    assert "ANN-RED=" in capsys.readouterr().out                                             # the non-blind check names annotators for the owner


def test_the_dry_run_files_state_the_limits_and_the_blocker():
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    for needed in ("annotation has NOT started", "did not annotate", "AI-generated labels are not accepted", "withdrawal and unlinkability", "scripts/build_dry_run_package.py"):
        assert needed in readme, needed
    ambiguities = (PACK / "author_only" / "pre_annotation_ambiguities.md").read_text(encoding="utf-8")
    assert "hypotheses" in ambiguities and "not results" in ambiguities and all(f"| A{n} |" in ambiguities for n in range(1, 12))
    adjudicator = (PACK / "adjudicator" / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "without annotator identities" in adjudicator and "rubric_gap" in adjudicator


def _review():
    text = (PACK / "author_only" / "pre_annotation_ambiguities.md").read_text(encoding="utf-8")
    review = text.split("## Review of the proposals")[1]
    tables = [[line for line in block.splitlines() if line.startswith("| A")] for block in review.split("| Id |")[1:]]
    return review, tables


def test_each_ambiguity_is_classified_and_reviewed_as_a_proposal_with_the_five_required_fields():
    review, (summary, detail) = _review()
    assert "PROPOSALS ONLY" in review and "not accepted" in review and "no human agreement exists" in review
    keys = [f"A{n}" for n in range(1, 12)]
    assert [row.split("|")[1].strip() for row in summary] == keys and [row.split("|")[1].strip() for row in detail] == keys
    classes = {row.split("|")[1].strip(): (row.split("|")[2].strip(), row.split("|")[3].strip()) for row in summary}
    assert {k: v[0] for k, v in classes.items()} == {"A1": "C", "A2": "C", "A3": "C", "A4": "C", "A5": "P", "A6": "P", "A7": "T", "A8": "C", "A9": "C", "A10": "P", "A11": "C"}
    assert "T (" in classes["A1"][1] and "H" in classes["A5"][1] and "H" in classes["A6"][1] and "H" in classes["A10"][1] and "C (" in classes["A7"][1]
    for row in detail:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        assert len(cells) == 5 and all(cells), row                                  # id, current rule, proposed wording, likely disagreement, downstream implications
    by_id = {row.split("|")[1].strip(): row for row in detail}
    assert "under-labelling implicit distress" in by_id["A6"] and "absence of a negative label as the absence of distress" in by_id["A6"]
    assert "Missing finance-related categories" in by_id["A7"].replace("**", "")
    assert "Loanwords" in by_id["A10"].replace("**", "") and "EMI" in by_id["A10"] and "threshold the owner must supply" in by_id["A10"] and "No boundary is invented" in by_id["A10"]
    assert "outside-list emotions have no baseline counterpart" in by_id["A1"]
    assert "removes" in by_id["A5"] and "partly by construction" in by_id["A5"]
    assert "None of A1-A11 changes a label value or the production taxonomy as proposed" in review


def test_no_proposal_is_applied_to_the_rubric_or_the_package_and_open_decisions_stay_open():
    review, _ = _review()
    for open_item in ("O2, O3, O7", "withdrawal-versus-unlinkability", "O5 and O6 remain PROPOSED"):
        assert open_item in review, open_item
    rubric = (ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md").read_text(encoding="utf-8")
    excerpt = (PACK / "package" / "RUBRIC_EXCERPT.md").read_text(encoding="utf-8")
    for proposed in ("topic_gap", "never becomes its opposite", "one `hedged` flag per text", "no \"obvious sarcasm\" judgement", "`implicit`"):
        assert proposed not in excerpt and proposed not in rubric, proposed
    assert "flips or removes the cue" in rubric and "flips or removes the cue" in excerpt                    # the current rule is still the one annotators see
    assert builder.verify() == []


def test_statuses_and_terms_agree_across_rubric_excerpt_decision_sheet_and_review():
    rubric = (ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md").read_text(encoding="utf-8")
    excerpt = (PACK / "package" / "RUBRIC_EXCERPT.md").read_text(encoding="utf-8")
    sheet = (ROOT / "docs" / "USER_TEXT_VALIDATION_DECISION_SHEET.md").read_text(encoding="utf-8")
    assert "language you cannot read" not in rubric and "language you cannot read" not in excerpt                 # rule 2 no longer contradicts rule 9
    assert "text not written entirely in English, see rule 9" in excerpt and "whether or not you can read it" in excerpt
    assert "O1 and O4 are accepted in limited form" in rubric and "O2, O3 and O7 are open" in rubric
    assert "already the behaviour" not in rubric and "does **not**: it labels from any English cue word" in rubric   # the baseline is not claimed to treat code-mixed text as `uncertain`
    assert "| C7 |" in sheet and "| C8 |" in sheet
    steps = sheet.split("## Next decisions: the smallest useful sequence")[1]
    for n in range(1, 6):
        assert f"| {n} |" in steps, n
    assert "Run `v0-draft` unchanged first" in steps and "Only before any real text: O2, O3, O7" in steps
    assert "no number is proposed" in steps.lower()
    assert sheet.count("| Owner decision | |") == 5 and "| Owner decision | ACCEPTED, limited" in sheet            # O2, O3, O5, O6, O7 still blank
    manifest = json.loads((PACK / "author_only" / "DRAFT_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["frozen"] is False and manifest["annotation_status"] == "NOT STARTED" and manifest["distribution_ready"] is False
