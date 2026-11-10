"""The overlap-first control (D13, approved 2026-10-19). Offline; reads no key, calls no provider.

M2 requires the 312 human-only reference labels to be complete, and their hash recorded, **before** any AI suggestion is
generated or shown. This module makes that a verified record instead of a procedure.

``create`` verifies the overlap items' label rows and then writes a read-only record holding their SHA-256:

- **against the original:** the overlap membership is the verified one, the items exist once in ``annotation_A.csv`` and their
  source fields are unchanged (``provenance.verify``); the hash also binds the original rows of those items;
- **against the approved label schema:** every overlap item is labelled and passes the human-only rubric validator
  (``annotate.human_only_errors``): ``label_basis = own``, a human annotator, valid relevance, polarity, ambiguity, company
  and duplicate fields;
- **against the provenance records:** every overlap item has origin ``human_only`` (never AI-exposed), and the working copy is
  exactly what the logged workflow last wrote;
- **against the recorded hash:** ``verify`` recomputes the hash from the current working copy and compares it with the record.

The record is bound into Gate D through ``protocol.overlap_labels_sha256``, copied into every run manifest, and revalidated at
freeze and at evaluation. **Timestamps are recorded but never relied on**: the control rests on content hashes and bindings.

The AI package reads only the record file (``read_record``), never the labels, so the existing rule that the pipeline never
sees the human working copy still holds. It cannot prove from the record alone that the labels are unchanged since: that is
re-verified at freeze, where the labels are legitimately read.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import annotate, provenance
from wealthpilot.data.gdelt.annotate import LABEL_COLUMNS, AnnotationError, Paths
from wealthpilot.data.gdelt.output import atomic_write

SCHEMA = "b2_overlap_labels_lock_v1"
RECORD_NAME = "overlap_labels_lock.json"


def record_path(review_files: Path) -> Path:
    return Path(review_files) / "working" / RECORD_NAME


def _sha_obj(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _rows(p: Paths) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    return ({r["item_id"]: r for r in annotate._read_csv(p.original)},
            {r["item_id"]: r for r in annotate._working_rows(p)})


def labels_hash(p: Paths, overlap_ids: list[str]) -> tuple[str, str]:
    """(hash of the overlap items' label rows, hash of their original rows). Canonical: sorted by item ID, stripped values."""
    original, working = _rows(p)
    labels = [{"item_id": i, **{c: (working[i].get(c) or "").strip() for c in LABEL_COLUMNS}} for i in sorted(overlap_ids)]
    sources = [{k: original[i][k] for k in sorted(original[i]) if k not in LABEL_COLUMNS} for i in sorted(overlap_ids)]
    return _sha_obj(labels), _sha_obj(sources)


def verify_labels(p: Paths) -> tuple[list[str], list[str]]:
    """(problems, overlap item IDs). Every check refuses; nothing is repaired or defaulted."""
    rep = provenance.verify(p)
    problems = [f"provenance {x['kind']}: {x['detail']}" for x in rep.problems]
    if not rep.ok:
        return problems, []
    overlap = sorted(i for i, v in rep.items.items() if v["overlap"])
    if not overlap:
        problems.append("the original has no overlap items")
        return problems, []
    try:
        expected = json.loads(p.selection_log.read_text(encoding="utf-8")).get("overlap_items")
    except (OSError, ValueError):
        expected = None
    if expected is not None and expected != len(overlap):     # the count is checked when the log records one
        problems.append(f"selection_log.json records {expected} overlap items; the verified membership has {len(overlap)}")
    _, working = _rows(p)
    all_ids = set(working)
    for i in overlap:
        v = rep.items[i]
        if v["origin"] != "human_only":
            problems.append(f"{i}: origin is {v['origin']!r}; an overlap item must be a labelled, human-only item")
            continue
        errs = annotate.human_only_errors(working[i], all_ids)
        if errs:
            problems.append(f"{i}: " + "; ".join(errs))
    return problems, overlap


def create(p: Paths, *, now: datetime | None = None) -> dict[str, Any]:
    """Verify the overlap labels and write the read-only record. Never overwrites; refuses on any problem."""
    target = record_path(p.review_files)
    if target.exists():
        raise AnnotationError(f"{target.name} already exists and is never overwritten")
    problems, overlap = verify_labels(p)
    if problems:
        raise AnnotationError("cannot lock the overlap labels: " + "; ".join(problems[:5])
                              + (f" (and {len(problems) - 5} more)" if len(problems) > 5 else ""))
    labels_sha, sources_sha = labels_hash(p, overlap)
    body = {"schema": SCHEMA, "overlap_items": len(overlap), "overlap_item_ids_sha256": _sha_obj(overlap),
            "overlap_labels_sha256": labels_sha, "original_rows_sha256": sources_sha,
            "working_sha256": hashlib.sha256(p.working.read_bytes()).hexdigest(),
            "annotation_A_sha256": hashlib.sha256(p.original.read_bytes()).hexdigest(),
            "locked_at_utc": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "timestamps are recorded, never relied on: the control rests on these hashes and on Gate D"}
    record = {**body, "record_sha256": _sha_obj(body)}
    atomic_write(target, json.dumps(record, indent=1, sort_keys=True).encode("utf-8"))
    os.chmod(target, 0o444)
    return record


def read_record(review_files: Path) -> tuple[dict[str, Any] | None, str]:
    """The record, or (None, reason). Checks only the record's own integrity; reads no label. Used by the AI package."""
    path = record_path(review_files)
    if not path.is_file() or path.is_symlink():
        return None, "the overlap-labels lock record does not exist"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        body = {k: v for k, v in rec.items() if k != "record_sha256"}
        if rec.get("schema") != SCHEMA or _sha_obj(body) != rec.get("record_sha256"):
            return None, "the overlap-labels lock record is malformed or was edited"
        if not isinstance(rec.get("overlap_labels_sha256"), str) or len(rec["overlap_labels_sha256"]) != 64:
            return None, "the overlap-labels lock record has no valid hash"
    except (OSError, ValueError, AttributeError):
        return None, "the overlap-labels lock record is unreadable"
    return rec, "ok"


def verify(p: Paths) -> list[str]:
    """Re-verify at freeze or evaluation: the record is intact, the overlap labels still pass every check, and their hash
    equals the recorded one. Returns the problems (empty means verified)."""
    rec, why = read_record(p.review_files)
    if rec is None:
        return [why]
    problems, overlap = verify_labels(p)
    if problems:
        return [f"the overlap labels no longer verify: {m}" for m in problems[:5]]
    labels_sha, sources_sha = labels_hash(p, overlap)
    out = []
    if rec["overlap_item_ids_sha256"] != _sha_obj(overlap):
        out.append("the overlap membership differs from the locked membership")
    if labels_sha != rec["overlap_labels_sha256"]:
        out.append("the overlap labels changed after they were locked")
    if sources_sha != rec["original_rows_sha256"]:
        out.append("the original rows of the overlap items differ from the locked ones")
    return out


def verify_runs(p: Paths, export_dir: Path | None) -> list[str]:
    """Every run manifest of the AI experiment must carry the locked hash. With a B2-T export, at least one run must exist."""
    from wealthpilot.data.gdelt import ai_bridge
    rec, why = read_record(p.review_files)
    if rec is None:
        return [why]
    layout = ai_bridge.layout_for_export(export_dir)
    if layout is None or not layout.snapshot.is_dir():          # not a B2-T experiment folder: no run to bind
        return []
    manifests = sorted(layout.audit.parent.glob("run_manifest_*.json")) if layout.audit.parent.is_dir() else []
    if not manifests:
        return ["no run manifest exists, so the overlap-first binding of the run cannot be verified"]
    out = []
    for m in manifests:
        try:
            if json.loads(m.read_text(encoding="utf-8")).get("overlap_labels_sha256") != rec["overlap_labels_sha256"]:
                out.append(f"{m.name} was not made under the locked overlap labels")
        except (OSError, ValueError):
            out.append(f"{m.name} is unreadable")
    return out
