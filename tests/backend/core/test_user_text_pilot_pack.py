"""ADR-043/044 -- the fictional pilot pack is synthetic, unlabelled for annotators, keeps the author's map out of the annotator folder, agrees with the rubric's fields and allowed values,
is disjoint from the rubric examples, is never read by backend code or fed to the baseline, and its helper script computes no accuracy. Offline; no baseline output is produced."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

from wealthpilot.core.user_text_sentiment import EMOTIONS, PREFERENCES, SENTIMENTS, TOPICS

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "datasets" / "rubric_examples" / "pilot_pack_v0"
ANNOTATOR = PACK / "annotator"
AUTHOR = PACK / "author_only"
EXAMPLES = ROOT / "datasets" / "rubric_examples" / "user_text_rubric_examples_v0.jsonl"
RUBRIC = ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md"
SCRIPT = ROOT / "scripts" / "pilot_disagreements.py"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def helper():
    spec = importlib.util.spec_from_file_location("pilot_disagreements", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pilot_texts_are_synthetic_unlabelled_and_distinct_from_rubric_examples():
    texts = jsonl(ANNOTATOR / "pilot_texts.jsonl")
    assert len(texts) == 30 and len({t["id"] for t in texts}) == 30
    for t in texts:
        assert set(t) == {"id", "text", "source", "split"}                           # no label, flag or annotator field can reach an annotator
        assert t["source"] == "synthetic_pilot" and t["split"] == "pilot_preparation" and 0 < len(t["text"]) <= 1000
    assert not {t["text"] for t in texts} & {r["text"] for r in jsonl(EXAMPLES)}      # rubric examples and pilot pack never overlap


def test_the_annotator_folder_holds_no_author_material():
    assert sorted(p.name for p in ANNOTATOR.iterdir()) == ["INSTRUCTIONS.md", "annotation_template.csv", "pilot_texts.jsonl"]
    for p in ANNOTATOR.iterdir():
        body = p.read_text(encoding="utf-8").lower()
        assert "challenge" not in body and "author_only" not in body and "code_mixed" not in body, p.name
    assert sorted(p.name for p in AUTHOR.iterdir()) == ["DRAFT_MANIFEST.json", "author_challenge_map.json", "participant_register_TEMPLATE.csv", "pre_annotation_ambiguities.md"]


def test_the_template_matches_the_pack_the_rubric_and_is_blank():
    with (ANNOTATOR / "annotation_template.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        columns = reader.fieldnames
    assert [r["id"] for r in rows] == [t["id"] for t in jsonl(ANNOTATOR / "pilot_texts.jsonl")]
    assert all(not any(v for k, v in r.items() if k != "id") for r in rows)           # nothing pre-filled, no purported labels
    assert {"sentiment", "emotional_tone", "emotional_tone_proposed", "topics", "preferences", "contradictory", "ambiguous_tone", "language", "rubric_unclear"} <= set(columns)
    rubric = RUBRIC.read_text(encoding="utf-8")
    h = helper()
    for value in (*h.SENTIMENTS, *h.TONES, *h.TOPICS, *h.PREFERENCES):               # the rubric names every allowed value the sheet uses
        assert value in rubric, value
    # The ANNOTATION scheme is the frozen v0 taxonomy. ADR-050 added pipeline-only values (abstention, extra tones / topics / one preference) that annotators are not asked to label and that
    # the draft rubric deliberately does not name (the rubric and package are not edited by that change): the scheme must equal the production taxonomy minus exactly those additions.
    assert (h.SENTIMENTS, h.TONES, h.TOPICS, h.PREFERENCES) == (
        set(SENTIMENTS) - {"insufficient_evidence"}, set(EMOTIONS) - {"frustrated", "calm", "neutral", "unknown"}, set(TOPICS) - {"market", "retirement", "emergency_fund"},
        set(PREFERENCES) - {"balanced_growth"})                                                                    # script cannot drift from the code taxonomy
    assert all(h.check_row({c: "" for c in columns}) == [] for _ in rows[:1])         # blank/missing is accepted, never turned into a label


def test_the_author_map_covers_the_requested_challenge_types_and_holds_no_labels():
    data = json.loads((AUTHOR / "author_challenge_map.json").read_text(encoding="utf-8"))
    tags = {t for v in data["challenges"].values() for t in v}
    assert {"neutral", "mixed", "contradictory", "unclear", "code_mixed", "unsupported_language"} <= tags
    assert set(data["challenges"]) == {t["id"] for t in jsonl(ANNOTATOR / "pilot_texts.jsonl")}
    assert "sentiment" not in json.dumps(data["challenges"]) and "Not labels" in data["note"]


def test_the_readme_says_it_is_preparation_not_validation():
    text = (PACK / "README.md").read_text(encoding="utf-8")
    for needed in ("NOT independent validation", "UNVALIDATED_BASELINE", "never be merged", "never an accuracy figure", "annotation has NOT started", "**not frozen**", "did not annotate", "undecided"):
        assert needed in text, needed


def test_the_helper_reports_differences_and_unclear_flags_but_no_scores(tmp_path, capsys):
    h = helper()
    cols = ["id", "annotator_id", "sentiment", "emotional_tone", "emotional_tone_proposed", "topics", "preferences", "contradictory", "ambiguous_tone", "language", "hedged", "negation", "difficulty", "rubric_unclear", "note"]

    def sheet(name, sentiment, unclear, tone="", extra=""):
        path = tmp_path / f"{name}.csv"                                               # fabricated only inside this test, to exercise the code path; never stored in the repo
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerow({**{c: "" for c in cols}, "id": "pilot-001", "annotator_id": name, "sentiment": sentiment, "rubric_unclear": unclear, "emotional_tone": tone, "note": extra})
        return path

    a, b = sheet("A", "neutral", "true", extra="not sure about rule 2"), sheet("B", "mixed", "")
    assert h.main([str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "DIFFER   pilot-001 sentiment: A=neutral; B=mixed" in out and "UNCLEAR  pilot-001: A: not sure about rule 2" in out
    for banned in ("accuracy:", "kappa", "precision", "recall", "f1"):
        assert banned not in out.lower().replace("not accuracy, agreement or validation", "")
    bad = sheet("C", "ecstatic", "", tone="concerned|hopeful")                         # production tone takes one value; sentiment must be in the taxonomy
    assert h.main([str(a), str(bad)]) == 1 and "INVALID" in capsys.readouterr().out


def test_no_backend_code_reads_the_pilot_pack_and_no_test_or_script_runs_the_baseline_on_it():
    for path in (ROOT / "backend" / "wealthpilot").rglob("*.py"):
        assert "pilot_pack" not in path.read_text(encoding="utf-8", errors="ignore"), path
    assert "user_text_sentiment" not in SCRIPT.read_text(encoding="utf-8") and "wealthpilot" not in SCRIPT.read_text(encoding="utf-8")
    assert "author_challenge_map" not in SCRIPT.read_text(encoding="utf-8")
    for path in [*(ROOT / "tests").rglob("*.py"), *(ROOT / "scripts").glob("*.py")]:
        if path.name == Path(__file__).name:
            continue
        body = path.read_text(encoding="utf-8", errors="ignore")
        assert not ("pilot_pack" in body and "analyse_user_text" in body), path


SHEET = ROOT / "docs" / "USER_TEXT_VALIDATION_DECISION_SHEET.md"


def test_the_decision_packet_has_seven_stable_ids_each_with_a_blank_owner_row():
    sheet = SHEET.read_text(encoding="utf-8")
    for n in range(1, 8):
        assert f"\n## O{n} " in sheet, n
    assert sheet.count("| Owner decision |") == 7
    rows = {n: next(line for line in sheet.split(f"## O{n} ")[1].split("\n## ")[0].splitlines() if line.startswith("| Owner decision |")) for n in range(1, 8)}
    for n in (2, 3, 5, 6, 7):                                                                    # the owner has not decided these: cells stay empty
        assert rows[n] == "| Owner decision | |", n
    assert rows[1].startswith("| Owner decision | ACCEPTED, limited (owner, 2026-10-20): fictional notes only")
    assert "all independent of the rubric author" in rows[4] and "self-annotation must not be substituted or called independent" in rows[4]
    for field in ("| Status |", "| Recommended default |", "| Consequences |", "| Prerequisites |"):
        assert sheet.count(field) == 7, field
    assert "The only accepted decisions are the owner's limited approvals of 2026-10-20" in sheet
    for n in (5, 6):                                                                             # the owner's proposals stay proposals
        block = sheet.split(f"## O{n} ")[1].split("\n## ")[0]
        assert "PROPOSED" in block and "not accepted" in block, n
    assert "UNVALIDATED_BASELINE" in sheet


def test_the_packet_invents_no_numeric_threshold():
    import re

    sheet = SHEET.read_text(encoding="utf-8")
    assert not re.search(r"\d+(\.\d+)?\s*%|\b0\.\d+|[<>≤≥]=?\s*\d|\b(at least|minimum of|no fewer than) (\d+|two|three|five|ten)\b", sheet, re.IGNORECASE)
    assert "no consent, retention, agreement, sample-size or acceptance threshold is invented" in sheet.lower()
    assert "none is given here" in sheet.lower() and "no number is set here" in sheet.lower()                  # the owner supplies the numbers


def test_the_documented_contradictions_stay_fixed_in_the_rubric_and_instructions():
    rubric = RUBRIC.read_text(encoding="utf-8")
    assert "Rubric version: **v0-draft, not frozen**" in rubric and "SHA-256" in rubric
    assert "`source_batch`" in rubric and "`consented_source_id` " not in rubric.replace("`consented_source_id`, `collected_on`", "")   # no person/consent link field in the record format
    assert "means one thing" in rubric and "two stated emotions are simply both listed" in rubric                                   # ambiguous_tone has one definition
    flat = rubric.replace("\n", " ")
    for needed in ("SHA-256 of the rubric and of the texts file", "annotator and adjudicator codes", "baseline's `METHOD_VERSION`", "NOT STARTED"):
        assert needed in flat, needed
    instructions = (ANNOTATOR / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "no information about who wrote it" in instructions and "automatic reading" in instructions and "RUBRIC_EXCERPT.md" in instructions and "you need nothing else" in instructions
    sheet = SHEET.read_text(encoding="utf-8")
    for cid in ("C1", "C2", "C3", "C4", "C5", "C6"):
        assert f"| {cid} |" in sheet, cid
    assert "Open, owner decision" in sheet.replace("**", "") and "blocker for any future real-text collection" in sheet                                                                      # the withdrawal-vs-no-link conflict is left to the owner


def test_the_rubric_keeps_proposals_marked_and_o5_o6_unimplemented():
    assert "PROPOSED" in RUBRIC.read_text(encoding="utf-8")
    from wealthpilot.core.user_text_sentiment import METHOD_VERSION, VALIDATION_STATUS

    assert (METHOD_VERSION, VALIDATION_STATUS) == ("user_text_rules_v1", "UNVALIDATED_BASELINE")     # v1 = ADR-050 pipeline; still unvalidated
    assert "emotional_tones" not in (ROOT / "backend" / "wealthpilot" / "api" / "schemas.py").read_text(encoding="utf-8")       # single-tone production schema unchanged
