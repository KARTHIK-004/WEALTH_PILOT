"""ADR-043 -- the synthetic rubric examples are well-formed, match the code's taxonomy, are clearly synthetic, and are never read by the backend (so they cannot become
tuning or validation data). Offline; no baseline accuracy is computed or claimed."""

from __future__ import annotations

import json
from pathlib import Path

from wealthpilot.core.user_text_sentiment import EMOTIONS, PREFERENCES, SENTIMENTS, TOPICS, VALIDATION_STATUS

ROOT = Path(__file__).resolve().parents[3]
FILE = ROOT / "datasets" / "rubric_examples" / "user_text_rubric_examples_v0.jsonl"
RUBRIC = ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md"


def rows() -> list[dict]:
    return [json.loads(line) for line in FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_examples_follow_the_code_taxonomy_and_are_synthetic():
    data = rows()
    assert len(data) >= 15 and len({r["id"] for r in data}) == len(data)
    for r in data:
        assert r["source"] == "synthetic_rubric" and r["split"] == "rubric_walkthrough" and r["annotator_id"].endswith("illustrative")
        lab = r["labels"]
        assert lab["sentiment"] in SENTIMENTS and lab["emotional_tone"] in (*EMOTIONS, None)
        assert set(lab["topics"]) <= set(TOPICS) and set(lab["preferences"]) <= set(PREFERENCES)
        assert r["flags"]["difficulty"] in ("easy", "moderate", "hard") and 0 < len(r["text"]) <= 1000


def test_the_set_covers_the_hard_cases_the_rubric_names():
    data = rows()
    assert {r["labels"]["sentiment"] for r in data} == set(SENTIMENTS) - {"insufficient_evidence"}   # every ANNOTATION class incl. uncertain and mixed (abstention is pipeline-only, ADR-050)
    assert any(r["flags"]["negation"] for r in data) and any(r["flags"]["hedged"] for r in data)
    assert any(r["labels"]["emotional_tone"] and not r["labels"]["preferences"] for r in data)      # a feeling is not a preference
    assert all(not r["labels"]["preferences"] for r in data if r["labels"]["sentiment"] == "uncertain")
    assert any(r["flags"]["contradictory"] and len(r["labels"]["preferences"]) == 2 for r in data)    # opposing wants: both tagged, not one picked
    assert any(r["flags"]["language"] == "unsupported" and r["labels"]["sentiment"] == "uncertain" for r in data)
    assert any(r["flags"]["ambiguous_tone"] for r in data)                                            # two emotions vs a one-value field (open decision O6)


def test_proposed_multi_tone_is_recorded_without_changing_the_production_fields():
    data = rows()
    proposed = [r for r in data if "proposed_emotional_tones" in r]
    assert proposed and all(set(r["proposed_emotional_tones"]) <= set(EMOTIONS) for r in proposed)
    assert all(r["labels"]["emotional_tone"] in (*EMOTIONS, None) for r in data)                      # production taxonomy: still one value or none
    assert "PROPOSED (O6" in RUBRIC.read_text(encoding="utf-8") and "PROPOSED:** for the initial validation" in RUBRIC.read_text(encoding="utf-8")


def test_the_rubric_states_it_is_a_proposal_and_the_baseline_stays_unvalidated():
    text = RUBRIC.read_text(encoding="utf-8")
    assert "PROPOSED" in text and "UNVALIDATED_BASELINE" in text and VALIDATION_STATUS == "UNVALIDATED_BASELINE"
    assert "Never" in text and "accuracy evaluation" in text
    for needed in ("Open owner decisions", "blind adjudication", "Freeze before evaluation", "Contradictory statements", "Unsupported language"):
        assert needed in text, needed


def test_no_backend_code_reads_the_rubric_examples():
    for path in (ROOT / "backend" / "wealthpilot").rglob("*.py"):
        assert "rubric_examples" not in path.read_text(encoding="utf-8", errors="ignore"), path
