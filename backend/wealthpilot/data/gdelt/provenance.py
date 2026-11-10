"""Verified provenance for evaluation: original items, overlap membership, human working copy and merge history.

``verify`` ties together the original ``annotation_A.csv``, the ``annotation_B.csv`` overlap manifest, the build backup,
the human working copy and ``merge_log.jsonl``, and refuses (status ``BLOCKED``) on anything missing, duplicated,
conflicting or unverifiable. Nothing is repaired or invented. It reads no sealed key and writes nothing.

An item's **label origin** comes from its recorded ``label_basis``:

- ``human_only``: ``own``, a label made without an AI suggestion;
- ``ai_exposed``: ``accepted_ai``, ``corrected_ai`` or ``rejected_ai`` (a human label made after seeing a suggestion,
  **never independent**);
- ``unlabelled``.

An AI-exposed label on an overlap item is a conflict, not a stratum. ``merge_ai_origin`` checks AI-assisted metadata (the
``b2t_annotation_v1`` export) against these records and refuses any disagreement; ``ai_origin.attach`` (B2-U8) calls it
and adds the file, row and coverage checks that freeze and evaluation use.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.annotate import AI_BASES, LABEL_COLUMNS, SOURCE_COLUMNS, Paths
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

_ID_RE = re.compile(r"^D\d{4}$")
VERIFIED, BLOCKED = "VERIFIED", "BLOCKED"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _problem(kind: str, item_id: str | None, detail: str) -> dict[str, Any]:
    return {"kind": kind, "item_id": item_id, "detail": detail}


@dataclass
class ProvenanceReport:
    status: str = VERIFIED
    problems: list[dict[str, Any]] = field(default_factory=list)
    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    counts: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == VERIFIED

    def add(self, kind: str, item_id: str | None, detail: str) -> None:
        self.problems.append(_problem(kind, item_id, detail))
        self.status = BLOCKED

    def summary(self) -> dict[str, Any]:
        kinds = Counter(p["kind"] for p in self.problems)
        return {"status": self.status, "problems_by_kind": dict(kinds), "problems": self.problems[:50],
                "problems_total": len(self.problems), "counts": self.counts}


def _read(path: Path, report: ProvenanceReport, label: str) -> list[dict[str, str]] | None:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != ANNOTATION_COLUMNS:
                report.add("schema", None, f"{label} does not have the b2o_annotation_v1 columns")
                return None
            return list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        report.add("unreadable", None, f"cannot read {label}: {type(exc).__name__}")
        return None


def _ids(rows: list[dict[str, str]], report: ProvenanceReport, label: str) -> list[str]:
    ids = [(r.get("item_id") or "").strip() for r in rows]
    for i in sorted({x for x in ids if ids.count(x) > 1}):
        report.add("duplicate_item", i, f"{label} lists this item more than once")
    for i in ids:
        if not _ID_RE.match(i):
            report.add("malformed_item_id", i or None, f"{label} has an item ID that is empty or malformed")
    return ids


def verify(p: Paths) -> ProvenanceReport:
    rep = ProvenanceReport()
    b_path = p.review_files / "annotation_B.csv"
    for label, path in (("annotation_A.csv", p.original), ("annotation_B.csv", b_path), ("selection_log.json", p.selection_log),
                        ("the build backup", p.backup), ("the working copy", p.working)):
        if not path.is_file():
            rep.add("missing_artifact", None, f"{label} is missing; provenance cannot be verified")
    if not rep.ok:
        return rep
    try:
        recorded = json.loads(p.selection_log.read_text(encoding="utf-8"))["files_sha256"]
    except (OSError, ValueError, KeyError, TypeError):
        rep.add("unreadable", None, "selection_log.json is unreadable or has no files_sha256")
        return rep
    for name, path in (("annotation_A.csv", p.original), ("annotation_B.csv", b_path)):
        if recorded.get(name) != _sha(path):
            rep.add("fingerprint_mismatch", None, f"{name} does not match the fingerprint in selection_log.json")
    if _sha(p.backup) != _sha(p.original):
        rep.add("fingerprint_mismatch", None, "the build backup differs from the original annotation_A.csv")

    original, working, b_rows = _read(p.original, rep, "annotation_A.csv"), _read(p.working, rep, "the working copy"), \
        _read(b_path, rep, "annotation_B.csv")
    if original is None or working is None or b_rows is None:
        return rep
    o_ids, w_ids, b_ids = _ids(original, rep, "annotation_A.csv"), _ids(working, rep, "the working copy"), \
        _ids(b_rows, rep, "annotation_B.csv")
    for i in sorted(set(o_ids) - set(w_ids)):
        rep.add("missing_item", i, "in the original but not in the working copy")
    for i in sorted(set(w_ids) - set(o_ids)):
        rep.add("unknown_item", i, "in the working copy but not in the original")
    by_o, by_w = {r["item_id"]: r for r in original}, {r["item_id"]: r for r in working}
    overlap = {i for i, r in by_o.items() if r["overlap_subset"] == "Y"}
    for i, r in by_o.items():
        if r["overlap_subset"] not in ("Y", "N"):
            rep.add("membership_invalid", i, "overlap_subset must be Y or N in the original")
        if any((r.get(c) or "").strip() for c in LABEL_COLUMNS):
            rep.add("original_not_clean", i, "the original annotation file carries label values")
    if set(b_ids) != overlap:
        rep.add("membership_conflict", None, "annotation_B.csv does not list exactly the original overlap items")
    for i in sorted(set(by_o) & set(by_w)):
        o, w = by_o[i], by_w[i]
        changed = [c for c in SOURCE_COLUMNS if o[c] != w[c]]
        if changed:
            rep.add("source_changed", i, f"the working copy changed original source fields: {changed}")

    # history: the working copy must be exactly what the logged workflow last wrote
    events: list[dict[str, Any]] = []
    if p.merge_log.exists():
        for n, line in enumerate(p.merge_log.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                ev = json.loads(line)
            except ValueError:
                rep.add("history_unreadable", None, f"merge_log.jsonl line {n} is not valid JSON")
                continue
            if not isinstance(ev, dict) or "event" not in ev:
                rep.add("history_unreadable", None, f"merge_log.jsonl line {n} is not an event record")
                continue
            events.append(ev)
    with_sha = [e for e in events if e.get("working_sha256")]
    if with_sha:
        if with_sha[-1]["working_sha256"] != _sha(p.working):
            rep.add("history_mismatch", None, "the working copy changed outside the logged workflow "
                                             "(its hash differs from the last logged write)")
    elif _sha(p.working) != _sha(p.backup):
        rep.add("history_missing", None, "the working copy differs from the build backup but no logged write explains it")
    corrections = Counter(e["item_id"] for e in events if e.get("correction") and e.get("item_id"))

    items: dict[str, dict[str, Any]] = {}
    for i in sorted(set(by_o) & set(by_w)):
        w = by_w[i]
        labelled = annotate.is_labelled(w)
        basis = (w.get("label_basis") or "").strip()
        if labelled and ((w.get("annotator_type") or "").strip() == "ai" or basis == "ai_only"):
            rep.add("ai_only_contamination", i, "an AI-only label is in the human working copy; it can never be a reference label")
        elif labelled and (w.get("annotator_type") or "").strip() != "human":
            rep.add("non_human_annotator", i, "a labelled row must have annotator_type 'human'")
        origin = "unlabelled" if not labelled else "ai_exposed" if basis in AI_BASES else \
            "human_only" if basis == "own" else "invalid"
        if origin == "invalid":
            rep.add("origin_invalid", i, f"label_basis {basis!r} is not a recognised origin")
        if i in overlap and origin == "ai_exposed":
            rep.add("overlap_ai_exposed", i, "an overlap item carries an AI-based label; it is not an independent label")
        ref = (w.get("near_dup_of") or "").strip()
        if ref and (ref not in by_o or ref == i or not _ID_RE.match(ref)):
            rep.add("near_dup_invalid", i, f"near_dup_of must name another item of this dataset (got {ref!r})")
        items[i] = {"overlap": i in overlap, "label_basis": basis or None, "origin": origin,
                    "independent_candidate": i in overlap and origin == "human_only", "corrections": corrections.get(i, 0),
                    "near_dup_of": ref, "labels": {c: (w.get(c) or "").strip() for c in LABEL_COLUMNS},
                    "source": {c: by_o[i][c] for c in SOURCE_COLUMNS}}
    rep.items = items
    rep.counts = {"items": len(items), "overlap": len(overlap), "non_overlap": len(items) - len(overlap),
                  "by_origin": dict(Counter(v["origin"] for v in items.values())),
                  "independent_candidates": sum(v["independent_candidate"] for v in items.values()),
                  "corrections_logged": sum(corrections.values()),
                  "near_dup_references": sum(bool(v["near_dup_of"]) for v in items.values())}
    return rep


def merge_ai_origin(report: ProvenanceReport, export_rows: list[dict[str, str]]) -> ProvenanceReport:
    """Check future AI-assisted metadata against the verified records. Any disagreement blocks; nothing is overwritten.

    ``ai_exposure = seen`` on an item the working copy records as ``own`` (or the reverse) is a conflict: the two records
    cannot both be true, so the item's independence is unverifiable.
    """
    if not report.ok:
        return report
    seen: Counter[str] = Counter()
    for r in export_rows:
        iid = (r.get("item_id") or "").strip()
        seen[iid] += 1
        rec = report.items.get(iid)
        if rec is None:
            report.add("unknown_item", iid or None, "the AI-assisted export names an item that is not in the dataset")
            continue
        exposure, origin = r.get("ai_exposure"), r.get("label_origin")
        if exposure not in ("seen", "none"):
            report.add("origin_invalid", iid, "ai_exposure must be 'seen' or 'none'")
        elif exposure == "seen" and rec["origin"] == "human_only":
            report.add("origin_conflict", iid, "the export says the label was made after seeing AI output; the working "
                                               "copy says it is human-only")
        elif exposure == "none" and rec["origin"] == "ai_exposed":
            report.add("origin_conflict", iid, "the working copy records an AI-based label; the export says no AI exposure")
        if exposure == "seen" and rec["overlap"]:
            report.add("overlap_ai_exposed", iid, "an overlap item is AI-exposed in the export; it is not independent")
        if origin in ("human_blind",) and exposure == "seen":
            report.add("origin_conflict", iid, "a blind label cannot be AI-exposed")
    for iid, n in sorted(seen.items()):
        if n > 1:
            report.add("duplicate_item", iid, "the AI-assisted export lists this item more than once")
    return report
