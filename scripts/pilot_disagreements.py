"""Rubric dry-run helper (ADR-044 preparation): list where annotators' sheets differ and which rules they flagged as unclear.

Standard library only. It validates allowed values, then prints, per text and field, the labels each annotator gave. It does NOT vote, adjudicate, compute accuracy or agreement
scores, import the sentiment baseline, or read the author's challenge map. The output is a worklist for a rubric discussion, not a result.

Usage:  python scripts/pilot_disagreements.py sheetA.csv sheetB.csv [sheetC.csv ...]
        python scripts/pilot_disagreements.py --blind sheetA.csv sheetB.csv     # adjudicator worklist: annotators appear as S1, S2 (order varies per text), notes unsigned

Run the plain form first to check the sheets (it names annotators); give the adjudicator only the --blind output.
"""

from __future__ import annotations

import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

SENTIMENTS = {"positive", "negative", "neutral", "mixed", "uncertain"}
TONES = {"concerned", "hopeful"}
TOPICS = {"investment_risk", "saving", "debt", "goals", "liquidity"}
PREFERENCES = {"capital_preservation", "growth_seeking", "liquidity_access", "debt_reduction"}
BOOLS = {"", "true", "false"}
SET_FIELDS = {"emotional_tone_proposed": TONES, "topics": TOPICS, "preferences": PREFERENCES}
COMPARED = ("sentiment", "emotional_tone", "emotional_tone_proposed", "topics", "preferences", "contradictory", "ambiguous_tone", "language", "hedged", "negation", "difficulty")


def _parts(value: str) -> frozenset[str]:
    return frozenset(p.strip() for p in value.split("|") if p.strip())


def check_row(row: dict[str, str]) -> list[str]:
    errors = []
    if row["sentiment"] not in SENTIMENTS | {""}:
        errors.append(f"sentiment={row['sentiment']!r}")
    if row["emotional_tone"] not in TONES | {""}:
        errors.append(f"emotional_tone={row['emotional_tone']!r} (one value only)")
    for name, allowed in SET_FIELDS.items():
        bad = _parts(row[name]) - allowed
        if bad:
            errors.append(f"{name} has {sorted(bad)}")
    for name in ("contradictory", "ambiguous_tone", "hedged", "negation", "rubric_unclear"):
        if row[name].lower() not in BOOLS:
            errors.append(f"{name}={row[name]!r}")
    if row["language"] not in {"", "en", "unsupported"} or row["difficulty"] not in {"", "easy", "moderate", "hard"}:
        errors.append("language/difficulty value")
    return errors


def load(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def report(sheets: dict[str, dict[str, dict[str, str]]], blind: bool = False) -> tuple[list[str], int]:
    lines: list[str] = []
    invalid = 0
    for who, rows in sheets.items():
        for tid, row in rows.items():
            for e in check_row(row):
                invalid += 1
                lines.append(f"INVALID  {'sheet' if blind else who} {tid}: {e}")
    ids = sorted(set().union(*(set(r) for r in sheets.values())))
    unclear: dict[str, list[str]] = defaultdict(list)
    for tid in ids:
        # blind mode: neutral names whose order is shuffled per text, so no annotator can be recognised across texts
        alias = {w: f"S{i + 1}" for i, w in enumerate(sorted(sheets, key=lambda w: hashlib.sha256(f"{tid}|{w}".encode()).hexdigest()))} if blind else {w: w for w in sheets}
        for who, rows in sheets.items():
            row = rows.get(tid)
            if row and row["rubric_unclear"].lower() == "true":
                unclear[tid].append(f"{alias[who]}: {row['note'] or '(no note)'}")
        for field in COMPARED:
            given = {who: (_parts(rows[tid][field]) if field in SET_FIELDS else rows[tid][field]) for who, rows in sheets.items() if tid in rows}
            if len({v for v in given.values()}) > 1:
                shown = "; ".join(f"{alias[w]}={'|'.join(sorted(v)) if isinstance(v, frozenset) else v or '(blank)'}" for w, v in sorted(given.items(), key=lambda kv: alias[kv[0]]))
                lines.append(f"DIFFER   {tid} {field}: {shown}")
    for tid, notes in sorted(unclear.items()):
        lines.append(f"UNCLEAR  {tid}: " + " | ".join(notes))
    return lines, invalid


def main(argv: list[str]) -> int:
    blind = "--blind" in argv
    paths = [Path(a) for a in argv if a != "--blind"]
    if len(paths) < 2:
        print(__doc__)
        return 2
    sheets: dict[str, dict[str, dict[str, str]]] = {}
    for p in paths:
        rows = load(p)
        first = next(iter(rows.values()), {})
        sheets[first.get("annotator_id") or p.stem] = rows
    lines, invalid = report(sheets, blind)
    print("\n".join(lines) if lines else "No differences and no unclear flags (check the sheets were actually filled).")
    print("\nThis is a worklist for a rubric discussion. It is not accuracy, agreement or validation.")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
