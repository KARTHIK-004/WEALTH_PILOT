"""Offline annotation workflow helper: backup, working copy, small batches, validated merge, status.

Design rules:

- **Originals never change:** the generated ``annotation_A.csv`` is verified against
  ``selection_log.json`` and copied to ``backup/``. Labelling happens in
  ``working/annotation_A.working.csv``, which only this module writes.
- **Batches hold only safe columns:** batch files carry the item ID, read-only context and the label
  columns. If a spreadsheet reformats the context, nothing is lost: ``merge`` reads only ``item_id``
  and the label columns, and provenance stays in the working copy.
- **Validation follows the rubric** of B2-I section 3, ``ANNOTATION_INSTRUCTIONS.md`` and the B2-O
  schema. It invents no new label value.
- **The sealed key is never read.** This module never refers to it (a test enforces that), and it
  makes no network request and produces no AI suggestion.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.output import atomic_write
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

LABEL_COLUMNS = ("rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice", "pol_equity", "pol_rates",
                 "pol_gold", "near_dup_of", "annotator_id", "annotator_type", "label_basis", "labelled_at_utc", "note")
SOURCE_COLUMNS = tuple(c for c in ANNOTATION_COLUMNS if c not in LABEL_COLUMNS)
BATCH_CONTEXT = ("batch_date_utc", "source_domain", "url", "title", "mech_dup", "overlap_subset")
BATCH_COLUMNS = ("item_id", *BATCH_CONTEXT, *LABEL_COLUMNS)
THEMES = (("rel_equity", "pol_equity", True), ("rel_rates", "pol_rates", True), ("rel_gold", "pol_gold", False))
REL_VALUES = {"R", "RL", "I", "A"}
AMB_CODES = {"A1", "A2", "A3", "A4", "A5", "A6", "A9"}
COMPANY_VALUES = {"Y", "N", "U"}
POL_VALUES = {"POS", "NEG", "NEU", "MIX", "UNC"}
BASIS_VALUES = {"own", "accepted_ai", "corrected_ai", "rejected_ai"}
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z)?$")
_ID_RE = re.compile(r"^D\d{4}$")


class AnnotationError(GdeltToolError):
    code = "annotation_error"


@dataclass(frozen=True)
class Paths:
    review_files: Path

    @property
    def original(self) -> Path:
        return self.review_files / "annotation_A.csv"

    @property
    def selection_log(self) -> Path:
        return self.review_files / "selection_log.json"

    @property
    def backup(self) -> Path:
        return self.review_files / "backup" / "annotation_A.build.csv"

    @property
    def working(self) -> Path:
        return self.review_files / "working" / "annotation_A.working.csv"

    @property
    def batches(self) -> Path:
        return self.review_files / "working" / "batches"

    @property
    def merge_log(self) -> Path:
        return self.review_files / "working" / "merge_log.jsonl"

    @property
    def ai_suggestions(self) -> Path:
        return self.review_files / "ai_suggestions_A.csv"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:   # tolerate a BOM added by an editor
            return [dict(r) for r in csv.DictReader(f)]
    except UnicodeDecodeError as exc:
        raise AnnotationError(f"{path.name} is not UTF-8; save it as 'CSV UTF-8' and try again") from exc


def _csv_bytes(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n", extrasaction="raise")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    return buf.getvalue().encode("utf-8")


def _original_rows(p: Paths) -> list[dict[str, str]]:
    """The generated file, verified against the hash the build recorded."""
    data = p.original.read_bytes()
    recorded = json.loads(p.selection_log.read_text(encoding="utf-8"))["files_sha256"]["annotation_A.csv"]
    if _sha(data) != recorded:
        raise AnnotationError("annotation_A.csv differs from the hash in selection_log.json; the generated file "
                              "must stay unchanged. Restore it from backup/ before continuing")
    rows = _read_csv(p.original)
    if not rows or tuple(rows[0].keys()) != ANNOTATION_COLUMNS:
        raise AnnotationError("annotation_A.csv does not have the b2o_annotation_v1 columns")
    return rows


# ---------------------------------------------------------------- init

def init(p: Paths) -> dict[str, object]:
    """Back up the generated file and create the working copy. Refuses to overwrite an existing one."""
    rows = _original_rows(p)
    if p.working.exists():
        raise AnnotationError(f"working copy already exists: {p.working}; it is never overwritten")
    data = p.original.read_bytes()
    if p.backup.exists():
        if _sha(p.backup.read_bytes()) != _sha(data):
            raise AnnotationError(f"backup differs from the generated file: {p.backup}")
    else:
        atomic_write(p.backup, data)
    working_sha = atomic_write(p.working, data)
    _log(p, {"event": "init", "working_sha256": working_sha, "rows": len(rows)})
    return {"rows": len(rows), "overlap_rows": sum(r["overlap_subset"] == "Y" for r in rows),
            "backup": str(p.backup), "working": str(p.working), "working_sha256": working_sha}


def _log(p: Paths, record: dict[str, object]) -> None:
    p.merge_log.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **record}
    with open(p.merge_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def _working_rows(p: Paths) -> list[dict[str, str]]:
    if not p.working.exists():
        raise AnnotationError("no working copy yet; run `annotate init` first")
    return _read_csv(p.working)


# ---------------------------------------------------------------- validation

def is_labelled(row: dict[str, str]) -> bool:
    return any((row.get(c) or "").strip() for c in LABEL_COLUMNS)


def content_errors(v: dict[str, str], *, item_id: str | None, all_ids: set[str]) -> list[str]:
    """The rubric's content rules (relevance, ambiguity, polarity, company notice, near duplicate).

    Shared by human labels and by AI-suggestion rows, so both are held to the same rubric. ``v`` holds the
    stripped label columns. Annotator, basis and timestamp rules live in ``row_errors``.
    """
    errs: list[str] = []
    rels = {}
    for rel, pol, us_theme in THEMES:
        if v[rel] not in REL_VALUES:
            errs.append(f"{rel} must be R, RL, I or A (got {v[rel]!r})")
        rels[rel] = v[rel]
        if v[rel] == "R":
            if v[pol] not in POL_VALUES:
                errs.append(f"{pol} is required when {rel} is R: POS, NEG, NEU, MIX or UNC (got {v[pol]!r})")
        elif v[pol]:
            errs.append(f"{pol} must be blank unless {rel} is R")
    ambiguous = [rel for rel, val in rels.items() if val == "A"]
    if ambiguous:
        if v["amb_code"] not in AMB_CODES:
            errs.append(f"amb_code is required when a theme is A: one of A1-A6, A9 (got {v['amb_code']!r})")
        elif v["amb_code"] == "A2" and ambiguous == ["rel_gold"]:
            errs.append("amb_code A2 (country unclear) applies to the US themes only, not to gold alone")
        elif v["amb_code"] == "A9" and not v["note"]:
            errs.append("amb_code A9 must be explained in note")
    elif v["amb_code"]:
        errs.append("amb_code must be blank unless a theme is A")
    if v["company_notice"] not in COMPANY_VALUES:
        errs.append(f"company_notice must be Y, N or U (got {v['company_notice']!r})")
    elif v["company_notice"] == "Y" and "R" in rels.values():
        errs.append("company and fund notices are never R (company_notice is Y)")
    if v["near_dup_of"]:
        if v["near_dup_of"] not in all_ids or v["near_dup_of"] == item_id:
            errs.append(f"near_dup_of must be another existing item_id (got {v['near_dup_of']!r})")
    return errs


def row_errors(row: dict[str, str], *, all_ids: set[str],
               ai_suggested_ids: frozenset[str] = frozenset()) -> list[str]:
    """Rubric errors for one labelled row. An entirely empty row has none (it is just not labelled yet).

    ``ai_suggested_ids`` is the set of item IDs that have a **valid** entry in ``ai_suggestions_A.csv``
    (from ``load_ai_suggestions``). It defaults to empty, so an AI-based ``label_basis`` fails closed: it
    is accepted only for an item that actually has a valid suggestion, never because some file exists.
    """
    if not is_labelled(row):
        return []
    v = {c: (row.get(c) or "").strip() for c in LABEL_COLUMNS}
    errs = content_errors(v, item_id=row.get("item_id"), all_ids=all_ids)
    if not v["annotator_id"]:
        errs.append("annotator_id (your initials) is required")
    elif "@" in v["annotator_id"]:
        errs.append("annotator_id must be initials, never an email")
    if v["annotator_type"] != "human":
        errs.append(f"annotator_type must be 'human' in the annotation file (got {v['annotator_type']!r}); "
                    "AI suggestions live only in ai_suggestions_A.csv")
    if v["label_basis"] not in BASIS_VALUES:
        errs.append(f"label_basis must be own, accepted_ai, corrected_ai or rejected_ai (got {v['label_basis']!r})")
    elif row.get("overlap_subset") == "Y" and v["label_basis"] != "own":
        errs.append("overlap rows must be labelled without AI suggestions: label_basis must be 'own'")
    elif v["label_basis"] != "own" and row.get("item_id") not in ai_suggested_ids:
        errs.append(f"label_basis {v['label_basis']!r} needs a valid suggestion for this item in "
                    "ai_suggestions_A.csv, and none exists")
    if not _TS_RE.match(v["labelled_at_utc"]):
        errs.append("labelled_at_utc must be YYYY-MM-DD or YYYY-MM-DDTHH:MM[:SS]Z (UTC)")
    return errs


AI_BASES = frozenset(BASIS_VALUES - {"own"})
# Minimal schema the validator enforces for ai_suggestions_A.csv. Extra provenance columns are allowed. The richer
# B2-T provenance fields (model, rubric version, time, input fingerprint) are NOT required: that schema is
# part of a methodology that has not been approved.
AI_SUGGESTION_COLUMNS = ("item_id", "annotator_type", "rel_equity", "rel_rates", "rel_gold", "amb_code",
                         "company_notice", "pol_equity", "pol_rates", "pol_gold", "note")


@dataclass(frozen=True)
class AiSuggestions:
    present: bool
    valid_ids: frozenset[str]          # items with exactly one valid suggestion
    problems: tuple[str, ...]          # one line per rejected row, or one for a file-level failure


def load_ai_suggestions(p: Paths, *, all_ids: set[str], overlap_ids: set[str]) -> AiSuggestions:
    """Read and validate ``ai_suggestions_A.csv``. Fails closed: a bad file or row yields no valid ID.

    A row is valid only if its ``item_id`` is a known item, appears exactly once, is not an overlap item,
    is marked ``annotator_type = ai``, and satisfies the same rubric content rules as a human label.
    This function never writes and is called only when some label claims an AI basis.
    """
    path = p.ai_suggestions
    if not path.exists():
        return AiSuggestions(False, frozenset(), ())
    if path.is_symlink() or not path.is_file():
        return AiSuggestions(True, frozenset(), (f"{path.name} is not a regular file",))
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = tuple(reader.fieldnames or ())
            rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        return AiSuggestions(True, frozenset(), (f"{path.name} is unreadable ({type(exc).__name__})",))
    missing = [c for c in AI_SUGGESTION_COLUMNS if c not in header]
    if missing or len(set(header)) != len(header):
        why = f"missing columns: {', '.join(missing)}" if missing else "duplicate column names"
        return AiSuggestions(True, frozenset(), (f"{path.name} header invalid ({why})",))
    counts = Counter((r.get("item_id") or "").strip() for r in rows)
    valid: set[str] = set()
    problems: list[str] = []
    for line, r in enumerate(rows, start=2):
        iid = (r.get("item_id") or "").strip()
        bad: list[str] = []
        if None in r or any(v is None for v in r.values()):
            bad.append("wrong number of fields")
        if not iid:
            bad.append("empty item_id")
        elif iid not in all_ids:
            bad.append("unknown item_id")
        elif counts[iid] > 1:
            bad.append("more than one suggestion for this item")
        elif iid in overlap_ids:
            bad.append("an overlap item must not have an AI suggestion")
        if (r.get("annotator_type") or "").strip() != "ai":
            bad.append("annotator_type must be 'ai'")
        if not bad:
            v = {c: (r.get(c) or "").strip() for c in LABEL_COLUMNS}
            bad += content_errors(v, item_id=iid, all_ids=all_ids)
        if bad:
            problems.append(f"line {line} ({iid or '?'}): " + "; ".join(bad))
        else:
            valid.add(iid)
    return AiSuggestions(True, frozenset(valid), tuple(problems))


def _suggested_ids(p: Paths, rows: list[dict[str, str]], *, needed: bool,
                   supplied: AiSuggestions | None = None) -> tuple[frozenset[str], list[str]]:
    """Valid suggestion IDs plus file-level messages, read only when a label claims an AI basis.

    ``supplied`` is a suggestion set verified by ``ai_bridge`` from the B2-T store. It replaces the legacy
    ``ai_suggestions_A.csv`` only if that file is absent: two sources for one item set are ambiguous, so both present is
    an error and nothing is accepted. With ``supplied`` left ``None`` the behaviour is exactly the legacy one.
    """
    if not needed:
        return frozenset(), []
    if supplied is not None:
        if p.ai_suggestions.exists():
            return frozenset(), ["ai_suggestions_A.csv exists alongside a B2-T suggestion store: two sources for the same "
                                 "items are ambiguous, so no AI-based label is accepted"]
        shown = [f"b2t suggestion store: {m}" for m in supplied.problems[:5]]
        if len(supplied.problems) > 5:
            shown.append(f"b2t suggestion store: and {len(supplied.problems) - 5} more problems")
        return (supplied.valid_ids if supplied.present else frozenset()), shown
    ids = {r["item_id"] for r in rows}
    overlap = {r["item_id"] for r in rows if r.get("overlap_subset") == "Y"}
    sug = load_ai_suggestions(p, all_ids=ids, overlap_ids=overlap)
    shown = [f"ai_suggestions_A.csv: {m}" for m in sug.problems[:5]]
    if len(sug.problems) > 5:
        shown.append(f"ai_suggestions_A.csv: and {len(sug.problems) - 5} more problems")
    return sug.valid_ids, shown


def human_only_errors(row: dict[str, str], all_ids: set[str]) -> list[str]:
    """The same rubric validator, for human-only labelling: no AI suggestion can exist for the item,
    so an AI-based ``label_basis`` is always an error here."""
    return row_errors(row, all_ids=all_ids, ai_suggested_ids=frozenset())


@dataclass
class Report:
    rows: int = 0
    labelled: int = 0
    overlap_rows: int = 0
    overlap_labelled: int = 0
    errors: dict[str, list[str]] = field(default_factory=dict)
    integrity_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.integrity_errors

    @property
    def complete(self) -> bool:
        return self.ok and self.labelled == self.rows


def validate(p: Paths, *, ai_suggestions: AiSuggestions | None = None) -> Report:
    """Check the working copy: provenance identical to the generated file, and every labelled row valid."""
    original = _original_rows(p)
    working = _working_rows(p)
    rep = Report(rows=len(original))
    if [r.get("item_id") for r in working] != [r["item_id"] for r in original]:
        rep.integrity_errors.append("item IDs or their order differ from the generated file")
    if working and tuple(working[0].keys()) != ANNOTATION_COLUMNS:
        rep.integrity_errors.append("working copy columns differ from b2o_annotation_v1")
    by_id = {r["item_id"]: r for r in original}
    for w in working:
        o = by_id.get(w.get("item_id", ""))
        if o is None:
            continue
        changed = [c for c in SOURCE_COLUMNS if w.get(c) != o[c]]
        if changed:
            rep.integrity_errors.append(f"{w['item_id']}: source fields changed: {', '.join(changed)}")
    ids = {r["item_id"] for r in original}
    needs_ai = any((w.get("label_basis") or "").strip() in AI_BASES for w in working)
    suggested, ai_messages = _suggested_ids(p, working, needed=needs_ai, supplied=ai_suggestions)
    rep.integrity_errors.extend(ai_messages)
    for w in working:
        if w.get("overlap_subset") == "Y":
            rep.overlap_rows += 1
        if is_labelled(w):
            rep.labelled += 1
            rep.overlap_labelled += w.get("overlap_subset") == "Y"
        errs = row_errors(w, all_ids=ids, ai_suggested_ids=suggested)
        if errs:
            rep.errors[w.get("item_id", "?")] = errs
    return rep


# ---------------------------------------------------------------- batches

def export_batch(p: Paths, *, size: int = 50, overlap_only: bool = True) -> dict[str, object]:
    """Write the next ``size`` unlabelled rows (overlap rows first) to a new batch file."""
    if size < 1 or size > 200:
        raise AnnotationError("batch size must be between 1 and 200")
    rep = validate(p)
    if rep.integrity_errors:
        raise AnnotationError("working copy failed integrity checks; run `annotate validate`")
    working = _working_rows(p)
    pending = [r for r in working if not is_labelled(r) and (r["overlap_subset"] == "Y" or not overlap_only)]
    if not overlap_only:
        pending.sort(key=lambda r: r["overlap_subset"] != "Y")   # overlap rows always come first
    take = pending[:size]
    if not take:
        return {"rows": 0, "file": None, "message": "nothing left to export for this selection"}
    p.batches.mkdir(parents=True, exist_ok=True)
    n = len(list(p.batches.glob("batch_*.csv"))) + 1
    kind = "overlap" if all(r["overlap_subset"] == "Y" for r in take) else "mixed"
    path = p.batches / f"batch_{n:03d}_{kind}.csv"
    if path.exists():
        raise AnnotationError(f"{path} already exists")
    sha = atomic_write(path, _csv_bytes(BATCH_COLUMNS, take))
    manifest = {"batch": path.name, "item_ids": [r["item_id"] for r in take], "sha256_at_export": sha}
    atomic_write(path.with_suffix(".manifest.json"), json.dumps(manifest, indent=1).encode("utf-8"))
    _log(p, {"event": "export", "batch": path.name, "rows": len(take), "sha256": sha})
    return {"rows": len(take), "file": str(path), "first": take[0]["item_id"], "last": take[-1]["item_id"],
            "overlap_rows_in_batch": sum(r["overlap_subset"] == "Y" for r in take)}


def merge(p: Paths, batch_path: Path, *, ai_suggestions: AiSuggestions | None = None) -> dict[str, object]:
    """Validate a labelled batch and copy its label columns into the working copy (atomic, all or nothing)."""
    batch_path = Path(batch_path)
    manifest_path = batch_path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        raise AnnotationError(f"no manifest for {batch_path.name}; only exported batches can be merged")
    expected_ids = json.loads(manifest_path.read_text(encoding="utf-8"))["item_ids"]
    rows = _read_csv(batch_path)
    if not rows or "item_id" not in rows[0] or any(c not in rows[0] for c in LABEL_COLUMNS):
        raise AnnotationError("batch file lost its item_id or label columns")
    got_ids = [(r.get("item_id") or "").strip() for r in rows]
    if sorted(got_ids) != sorted(expected_ids) or len(set(got_ids)) != len(got_ids):
        raise AnnotationError("batch item IDs differ from the exported batch (rows added, removed, duplicated "
                              "or IDs edited)")
    rep = validate(p, ai_suggestions=ai_suggestions)
    if rep.integrity_errors:
        raise AnnotationError("working copy failed integrity checks; run `annotate validate`")
    working = _working_rows(p)
    by_id = {r["item_id"]: r for r in working}
    ids = set(by_id)
    batch_ai = any((r.get("label_basis") or "").strip() in AI_BASES for r in rows)
    suggested, ai_messages = _suggested_ids(p, working, needed=batch_ai, supplied=ai_suggestions)
    errors: dict[str, list[str]] = {}
    updates: dict[str, dict[str, str]] = {}
    corrections, skipped = 0, 0
    for r in rows:
        iid = r["item_id"].strip()
        labels = {c: (r.get(c) or "").strip() for c in LABEL_COLUMNS}
        current = by_id[iid]
        candidate = {**current, **labels}
        if not is_labelled(candidate):
            if is_labelled(current):
                errors[iid] = ["labels cannot be deleted by merging a blank row; edit and give a reason in note"]
            else:
                skipped += 1
            continue
        errs = row_errors(candidate, all_ids=ids, ai_suggested_ids=suggested)
        if is_labelled(current) and any(current[c] != labels[c] for c in LABEL_COLUMNS):
            if labels["note"] == current["note"] or not labels["note"]:
                errs.append("this changes existing labels: add the reason to note (rubric: corrections)")
            corrections += 1
        if errs:
            errors[iid] = errs
        else:
            updates[iid] = labels
    if errors:
        out: dict[str, object] = {"merged": 0, "errors": errors,
                                  "message": "nothing merged; fix the listed rows and merge again"}
        if ai_messages:
            out["ai_suggestions_problems"] = ai_messages
        return out
    for iid, labels in updates.items():
        by_id[iid].update(labels)
    sha = atomic_write(p.working, _csv_bytes(ANNOTATION_COLUMNS, working))
    _log(p, {"event": "merge", "batch": batch_path.name, "batch_sha256": _sha(batch_path.read_bytes()),
             "rows_merged": len(updates), "corrections": corrections, "skipped_blank": skipped,
             "working_sha256": sha})
    return {"merged": len(updates), "corrections": corrections, "skipped_blank": skipped, "working_sha256": sha}


def save_item(p: Paths, item_id: str, labels: dict[str, str], *, event: str = "label") -> dict[str, object]:
    """Validate one item's complete labels and write them into the working copy atomically.

    Same rules as ``merge``: the rubric validator must pass; changing existing labels needs a new,
    non-empty ``note``; labels can never be blanked. Raises ``AnnotationError`` (nothing written) on
    any failure. AI suggestions are never consulted here (no suggested IDs are passed), so only
    ``label_basis = own`` can pass.
    """
    if set(labels) != set(LABEL_COLUMNS):
        raise AnnotationError("labels must provide every label column")
    rep = validate(p)
    if rep.integrity_errors:
        raise AnnotationError("working copy failed integrity checks; run `annotate validate`")
    working = _working_rows(p)
    by_id = {r["item_id"]: r for r in working}
    if item_id not in by_id:
        raise AnnotationError(f"unknown item {item_id}")
    current = by_id[item_id]
    clean = {c: (labels[c] or "").strip() for c in LABEL_COLUMNS}
    candidate = {**current, **clean}
    if not is_labelled(candidate):
        raise AnnotationError("labels cannot be blank")
    errs = row_errors(candidate, all_ids=set(by_id), ai_suggested_ids=frozenset())
    correction = is_labelled(current) and any(current[c] != clean[c] for c in LABEL_COLUMNS)
    if correction and (not clean["note"] or clean["note"] == current["note"]):
        errs.append("this changes existing labels: add the reason to note (rubric: corrections)")
    if errs:
        raise AnnotationError("; ".join(errs))
    current.update(clean)
    sha = atomic_write(p.working, _csv_bytes(ANNOTATION_COLUMNS, working))
    _log(p, {"event": event, "item_id": item_id, "correction": correction, "working_sha256": sha})
    return {"item_id": item_id, "correction": correction, "working_sha256": sha}


def status(p: Paths) -> dict[str, object]:
    rep = validate(p)
    working = _working_rows(p)
    labelled = [r for r in working if is_labelled(r)]
    return {
        "rows": rep.rows, "labelled": rep.labelled, "overlap_rows": rep.overlap_rows,
        "overlap_labelled": rep.overlap_labelled, "rows_with_errors": len(rep.errors),
        "integrity_ok": not rep.integrity_errors, "complete": rep.complete,
        "label_basis": dict(Counter(r["label_basis"] for r in labelled)),
        "working_sha256": _sha(p.working.read_bytes()),
    }
