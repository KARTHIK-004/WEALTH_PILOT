"""Phase 15 — questionnaire parsing for GET /api/questionnaire.

`datasets/raw/FAR-Trans/questionnaires.csv` is raw MiFID II questionnaire
text (one column, tab-indented section/question/option lines) — not a
structured table, and not `data/`-layer training input (nothing here
feeds a model; this is presentation-only). Parsed once at import time
(BUILD_PLAN.md section 12: "seeded at startup") and cached in memory --
never re-parsed per request, never written back to `datasets/raw/`
(read-only, matching every other phase's raw-dataset-immutability rule).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
QUESTIONNAIRE_PATH = REPO_ROOT / "datasets" / "raw" / "FAR-Trans" / "questionnaires.csv"

_QUESTION_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_OPTION_RE = re.compile(r"^([a-e])\.\s+(.*)$")


def _parse(text: str) -> list[dict]:
    sections: list[dict] = []
    current_section: dict | None = None
    current_question: dict | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if not raw_line[0].isspace():
            current_section = {"name": stripped, "questions": []}
            sections.append(current_section)
            current_question = None
            continue

        match = _QUESTION_RE.match(stripped)
        if match:
            current_question = {"number": int(match.group(1)), "text": match.group(2), "options": []}
            if current_section is not None:
                current_section["questions"].append(current_question)
            continue

        match = _OPTION_RE.match(stripped)
        if match and current_question is not None:
            current_question["options"].append({"key": match.group(1), "text": match.group(2)})
            continue

        # A wrapped continuation line of the previous question/option text
        # (e.g. question 20 in the source file spans three lines).
        if current_question is None:
            continue
        if current_question["options"]:
            current_question["options"][-1]["text"] += " " + stripped
        else:
            current_question["text"] += " " + stripped

    return sections


@lru_cache(maxsize=1)
def get_questionnaire_sections() -> list[dict]:
    if not QUESTIONNAIRE_PATH.exists():
        return []
    text = QUESTIONNAIRE_PATH.read_text(encoding="utf-8")
    return _parse(text)


def is_valid_answer(question_number: int, option_key: str) -> bool:
    """Phase 23 — True iff `question_number` is a real question in the
    parsed questionnaire and `option_key` is one of THAT question's real
    option keys. Used by `POST /api/profiles/{id}/questionnaire` to reject
    an invalid question/option reference before it ever reaches the
    database (BUILD_PLAN.md Phase 23 section 4: "validate ... selected
    option belongs to that question")."""
    for section in get_questionnaire_sections():
        for question in section["questions"]:
            if question["number"] == question_number:
                return any(option["key"] == option_key for option in question["options"])
    return False
