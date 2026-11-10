"""Versioned destination, immutable snapshot of the original experiment, and the append-only stores.

Layout (a sibling of the original review folder, never inside it)::

    <destination>/
      snapshot/            read-only copies of the original files + SNAPSHOT_FINGERPRINTS.json + historical_overlap.json
      inputs/ai_input_v1.jsonl             one fingerprint per item (read-only)
      suggestions/ai_suggestions_raw_v1.jsonl     append-only chain: every attempt, raw responses verbatim
      suggestions/ai_suggestions_valid_v1.csv     derived from the raw chain (rebuilt, never hand-edited)
      review/reviews_v1.jsonl              append-only chain of human review actions
      audit/events_v1.jsonl                append-only chain of run-level events
      queue/review_queue_v1.csv            derived review queue
      export/                              the versioned dataset for evaluation (read-only once written)
      fingerprints.json                    experiment-level hashes

The sealed key is never copied or referenced. The human working copy is copied **as it was at snapshot time** for
provenance only and is never read by the pipeline afterwards.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt.ai import SUGGESTION_SCHEMA
from wealthpilot.data.gdelt.ai.chain import ChainedJsonl
from wealthpilot.data.gdelt.ai.config import ExperimentConfig
from wealthpilot.data.gdelt.ai.fingerprints import itemset_fingerprint
from wealthpilot.data.gdelt.ai.schema import SourceItem, load_items
from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.output import atomic_write

IMMUTABLE_ORIGINALS = ("annotation_A.csv", "annotation_B.csv", "selection_log.json", "backup/annotation_A.build.csv")
SNAPSHOT_FILES = ("annotation_A.csv", "annotation_B.csv", "selection_log.json", "ANNOTATION_INSTRUCTIONS.md",
                  "backup/annotation_A.build.csv", "working/annotation_A.working.csv", "working/merge_log.jsonl")
AUDIT_KEYS = frozenset({"event", "run_id", "item_id", "status", "outcome", "reason", "counts", "sha256", "limit",
                        "gate", "experiment_id", "requests_used", "tokens_in", "tokens_out", "detail"})


class StoreError(GdeltToolError):
    code = "ai_store_error"


def utc(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Layout:
    root: Path

    @property
    def snapshot(self) -> Path:
        return self.root / "snapshot"

    @property
    def snapshot_fingerprints(self) -> Path:
        return self.snapshot / "SNAPSHOT_FINGERPRINTS.json"

    @property
    def historical_overlap(self) -> Path:
        return self.snapshot / "historical_overlap.json"

    @property
    def inputs(self) -> Path:
        return self.root / "inputs" / "ai_input_v1.jsonl"

    @property
    def suggestions_raw(self) -> Path:
        return self.root / "suggestions" / "ai_suggestions_raw_v1.jsonl"

    @property
    def suggestions_valid(self) -> Path:
        return self.root / "suggestions" / "ai_suggestions_valid_v1.csv"

    @property
    def reviews(self) -> Path:
        return self.root / "review" / "reviews_v1.jsonl"

    @property
    def audit(self) -> Path:
        return self.root / "audit" / "events_v1.jsonl"

    @property
    def queue(self) -> Path:
        return self.root / "queue" / "review_queue_v1.csv"

    @property
    def export(self) -> Path:
        return self.root / "export"

    @property
    def fingerprints(self) -> Path:
        return self.root / "fingerprints.json"

    def run_manifest(self, run_id: str) -> Path:
        return self.audit.parent / f"run_manifest_{run_id}.json"


def _readonly(path: Path) -> None:
    os.chmod(path, 0o444)


# ---------------------------------------------------------------- Stage A: snapshot

def init_experiment(cfg: ExperimentConfig, *, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    """Create the new versioned destination and snapshot the original experiment. Writes nothing to the source."""
    layout = Layout(cfg.destination)
    if layout.root.exists():
        raise StoreError(f"{layout.root} already exists; a versioned destination is never reused or overwritten")
    src = cfg.source_review_files
    for rel in IMMUTABLE_ORIGINALS:
        if not (src / rel).is_file():
            raise StoreError(f"required original file missing: {rel}")
    log = json.loads((src / "selection_log.json").read_text(encoding="utf-8"))["files_sha256"]
    for name in ("annotation_A.csv", "annotation_B.csv"):
        if sha_file(src / name) != log.get(name):
            raise StoreError(f"{name} does not match the fingerprint recorded in selection_log.json; refusing to snapshot")
    items = load_items(src / "annotation_A.csv")              # also proves the source holds no labels
    overlap = sorted(i.item_id for i in items if i.historical_overlap)
    with open(src / "annotation_B.csv", newline="", encoding="utf-8-sig") as f:
        b_ids = sorted(r["item_id"] for r in csv.DictReader(f))
    if b_ids != overlap:
        raise StoreError("annotation_B.csv does not match the overlap items of annotation_A.csv")
    unknown_blind = sorted(set(cfg.blind_item_ids) - set(overlap))
    if unknown_blind:
        raise StoreError(f"protocol.blind_item_ids must be original overlap items; not overlap: {unknown_blind[:5]}")

    for d in (layout.snapshot, layout.inputs.parent, layout.suggestions_raw.parent, layout.reviews.parent,
              layout.audit.parent, layout.queue.parent, layout.export):
        d.mkdir(parents=True, exist_ok=True)
    copied: dict[str, dict[str, Any]] = {}
    for rel in SNAPSHOT_FILES:
        s = src / rel
        if not s.is_file():
            continue
        dest = layout.snapshot / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, dest)
        if sha_file(dest) != sha_file(s):
            raise StoreError(f"copy of {rel} does not match its source")
        _readonly(dest)
        copied[rel] = {"sha256": sha_file(dest), "bytes": dest.stat().st_size,
                       "immutable_original": rel in IMMUTABLE_ORIGINALS,
                       "as_of_snapshot_only": rel.startswith("working/")}
    now = utc(clock())
    atomic_write(layout.historical_overlap, json.dumps({
        "note": "The ORIGINAL human-only overlap design, kept as historical provenance. Any AI exposure of these "
                "items under the new protocol does not make their labels independent human labels.",
        "count": len(overlap), "item_ids": overlap, "annotation_B_sha256": copied["annotation_B.csv"]["sha256"],
        "annotation_A_sha256": copied["annotation_A.csv"]["sha256"]}, indent=1).encode("utf-8"))
    _readonly(layout.historical_overlap)
    atomic_write(layout.snapshot_fingerprints, json.dumps({
        "created_at_utc": now, "source_review_files": str(src), "files": copied,
        "sealed_key": "not copied, not read; its recorded fingerprint stays in the original selection_log.json"},
        indent=1, sort_keys=True).encode("utf-8"))
    _readonly(layout.snapshot_fingerprints)
    itemset = itemset_fingerprint((i.item_id, i.fingerprint) for i in items)
    lines = [json.dumps({"item_id": i.item_id, "fingerprint": i.fingerprint, "historical_overlap": i.historical_overlap,
                         "sendable": i.sendable, "input_problems": list(i.input_problems)}, sort_keys=True)
             for i in items]
    atomic_write(layout.inputs, ("\n".join(lines) + "\n").encode("utf-8"))
    _readonly(layout.inputs)
    summary = {"experiment_id": cfg.experiment_id, "created_at_utc": now, "items": len(items),
               "historical_overlap": len(overlap), "sendable_items": sum(i.sendable for i in items),
               "itemset_sha256": itemset, "protocol_id": cfg.protocol_id, "blind_items": len(cfg.blind_item_ids)}
    atomic_write(layout.fingerprints, json.dumps(summary, indent=1, sort_keys=True).encode("utf-8"))
    AuditLog(layout).emit("experiment_initialized", experiment_id=cfg.experiment_id,
                          counts={"items": len(items), "historical_overlap": len(overlap)}, sha256=itemset, now=clock())
    return summary


def verify_snapshot(cfg: ExperimentConfig) -> None:
    """Fail if a snapshot file changed, or an ORIGINAL immutable file changed after the snapshot."""
    layout = Layout(cfg.destination)
    if not layout.snapshot_fingerprints.exists():
        raise StoreError("no snapshot: run `ai init` first")
    rec = json.loads(layout.snapshot_fingerprints.read_text(encoding="utf-8"))["files"]
    problems = []
    for rel, meta in rec.items():
        p = layout.snapshot / rel
        if not p.is_file() or sha_file(p) != meta["sha256"]:
            problems.append(f"snapshot copy changed or missing: {rel}")
        if meta["immutable_original"]:
            o = cfg.source_review_files / rel
            if not o.is_file() or sha_file(o) != meta["sha256"]:
                problems.append(f"ORIGINAL file changed since the snapshot: {rel}")
    if problems:
        raise StoreError("; ".join(problems))


def load_snapshot_items(layout: Layout) -> list[SourceItem]:
    """Items from the snapshot's original file, checked against the recorded per-item fingerprints."""
    items = load_items(layout.snapshot / "annotation_A.csv")
    recorded = {}
    for line in layout.inputs.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        recorded[r["item_id"]] = r["fingerprint"]
    if set(recorded) != {i.item_id for i in items} or any(recorded[i.item_id] != i.fingerprint for i in items):
        raise StoreError("item fingerprints differ from the recorded inputs: the snapshot or input file changed")
    return items


def verified_overlap(layout: Layout) -> frozenset[str]:
    """The original overlap membership, **verified** against the snapshot, or an error. Used to decide which items may
    never be sent. It never infers membership from item IDs or order: it needs the recorded manifest, the snapshot's
    ``overlap_subset`` column and ``annotation_B.csv`` to agree exactly."""
    if not layout.historical_overlap.is_file():
        raise StoreError("the overlap manifest (historical_overlap.json) is missing; membership cannot be verified")
    try:
        rec = json.loads(layout.historical_overlap.read_text(encoding="utf-8"))
        ids = rec["item_ids"]
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids) \
                or rec["count"] != len(ids):
            raise ValueError
        b_sha = rec["annotation_B_sha256"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StoreError("the overlap manifest is malformed or inconsistent") from exc
    b_path = layout.snapshot / "annotation_B.csv"
    if not b_path.is_file() or sha_file(b_path) != b_sha:
        raise StoreError("annotation_B.csv in the snapshot is missing or differs from the recorded overlap manifest")
    derived = {i.item_id for i in load_items(layout.snapshot / "annotation_A.csv") if i.historical_overlap}
    with open(b_path, newline="", encoding="utf-8-sig") as f:
        b_ids = {r["item_id"] for r in csv.DictReader(f)}
    if set(ids) != derived or set(ids) != b_ids:
        raise StoreError("the overlap manifest, the snapshot's overlap_subset column and annotation_B.csv disagree")
    return frozenset(ids)


def source_overlap_ids(src: Path) -> frozenset[str]:
    """The same verification against the ORIGINAL review folder (before a snapshot exists), for a dry run or gate check."""
    log = json.loads((src / "selection_log.json").read_text(encoding="utf-8"))["files_sha256"]
    items = load_items(src / "annotation_A.csv")
    if sha_file(src / "annotation_B.csv") != log.get("annotation_B.csv"):
        raise StoreError("annotation_B.csv does not match the fingerprint in selection_log.json")
    derived = {i.item_id for i in items if i.historical_overlap}
    with open(src / "annotation_B.csv", newline="", encoding="utf-8-sig") as f:
        b_ids = {r["item_id"] for r in csv.DictReader(f)}
    if derived != b_ids:
        raise StoreError("annotation_B.csv does not list exactly the original overlap items")
    return frozenset(derived)


def historical_overlap_ids(layout: Layout) -> tuple[frozenset[str], str]:
    rec = json.loads(layout.historical_overlap.read_text(encoding="utf-8"))
    return frozenset(rec["item_ids"]), rec["annotation_B_sha256"]


# ---------------------------------------------------------------- stores

class AuditLog:
    def __init__(self, layout: Layout) -> None:
        self.chain = ChainedJsonl(layout.audit)

    def emit(self, event: str, *, now: datetime | None = None, **fields: Any) -> dict[str, Any]:
        unknown = set(fields) - AUDIT_KEYS
        if unknown:
            raise StoreError(f"audit keys not allowed (titles and free text stay out of the log): {sorted(unknown)}")
        return self.chain.append({"event": event, "at_utc": utc(now or datetime.now(timezone.utc)), **fields})


class SuggestionStore:
    """Append-only raw attempts. An item is *terminal* once a record says so; terminal items are never re-run."""

    def __init__(self, layout: Layout) -> None:
        self.layout = layout
        self.chain = ChainedJsonl(layout.suggestions_raw)

    def records(self) -> list[dict[str, Any]]:
        return self.chain.records()

    def terminal(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in self.records():
            if r.get("terminal"):
                out[r["item_id"]] = r          # a later terminal record (none is written today) would supersede
        return out

    def attempts_for(self, item_id: str) -> list[dict[str, Any]]:
        return [r for r in self.records() if r["item_id"] == item_id]

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        if record.get("schema") != SUGGESTION_SCHEMA:
            raise StoreError("suggestion record has the wrong schema")
        return self.chain.append(record)


class ReviewStore:
    """Append-only human review records. The latest record per item is current; earlier ones stay as history."""

    def __init__(self, layout: Layout) -> None:
        self.chain = ChainedJsonl(layout.reviews)

    def records(self) -> list[dict[str, Any]]:
        return self.chain.records()

    def current(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in self.records():
            out[r["item_id"]] = r
        return out

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        return self.chain.append(record)


VALID_CSV_COLUMNS = ("item_id", "annotator_type", "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice",
                     "pol_equity", "pol_rates", "pol_gold", "note", "insufficient_evidence", "uncertainty_equity",
                     "uncertainty_rates", "uncertainty_gold", "evidence_excerpts", "flags", "input_fingerprint",
                     "run_id", "model_id", "model_version", "prompt_version", "rubric_version", "generated_at_utc",
                     "record_sha256")


def write_valid_csv(layout: Layout, store: SuggestionStore) -> int:
    """Rebuild the derived CSV of valid suggestions from the raw chain. ``annotator_type`` is always ``ai``."""
    data, n = render_valid_csv(store)
    atomic_write(layout.suggestions_valid, data)
    return n


def render_valid_csv(store: SuggestionStore) -> tuple[bytes, int]:
    """The derived CSV's exact bytes and row count, computed from the raw chain without writing anything."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(VALID_CSV_COLUMNS), lineterminator="\n")
    w.writeheader()
    n = 0
    for item_id, r in sorted(store.terminal().items()):
        if r.get("terminal_status") != "valid":
            continue
        p = r["parsed"]
        w.writerow({
            "item_id": item_id, "annotator_type": "ai", **{k: p[k] for k in (
                "rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice", "pol_equity", "pol_rates",
                "pol_gold", "note")},
            "insufficient_evidence": "Y" if p["insufficient_evidence"] else "N",
            "uncertainty_equity": p["uncertainty"]["rel_equity"], "uncertainty_rates": p["uncertainty"]["rel_rates"],
            "uncertainty_gold": p["uncertainty"]["rel_gold"],
            "evidence_excerpts": json.dumps(p["evidence_excerpts"], ensure_ascii=False, sort_keys=True),
            "flags": ";".join(r["validation"]["flags"]), "input_fingerprint": r["input_fingerprint"],
            "run_id": r["run_id"], "model_id": r["provider"]["model_id"], "model_version": r["provider"]["model_version"],
            "prompt_version": r["prompt_version"], "rubric_version": r["rubric_version"],
            "generated_at_utc": r["finished_at_utc"], "record_sha256": r["record_sha256"]})
        n += 1
    return buf.getvalue().encode("utf-8"), n
