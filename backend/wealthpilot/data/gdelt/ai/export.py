"""Export the separately versioned dataset (``b2t_annotation_v1``) for later evaluation.

The export refuses until every item has a human review record, never overwrites, and is read-only once written.
Every row carries ``ai_exposure`` and ``label_origin`` so an AI-seen label can never be mistaken for an independent human
label, and the manifest repeats that statement and the historical overlap membership.

The original annotation CSV and the human working copy are not touched, and this export is not read by the existing
``annotate freeze`` / ``annotate evaluate`` (which work on the original dataset only).
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.ai import DATASET_SCHEMA
from wealthpilot.data.gdelt.ai.chain import ChainedJsonl
from wealthpilot.data.gdelt.ai.config import ExperimentConfig
from wealthpilot.data.gdelt.ai.reviewer import CONTENT
from wealthpilot.data.gdelt.ai.schema import SourceItem
from wealthpilot.data.gdelt.ai.store import AuditLog, Layout, ReviewStore, StoreError, SuggestionStore, sha_file, utc
from wealthpilot.data.gdelt.output import atomic_write

B2T_COLUMNS = (*annotate.SOURCE_COLUMNS, "protocol_id", *CONTENT, "near_dup_of", "note", "insufficient_evidence",
               "annotator_id", "annotator_type", "reviewed_at_utc", "label_origin", "ai_exposure", "suggestion_ref",
               "edit_reason_code", "review_seconds", "review_record_sha256")


def export_dataset(layout: Layout, cfg: ExperimentConfig, items: list[SourceItem], *,
                   clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    csv_path, manifest_path = layout.export / "annotation_b2t_v1.csv", layout.export / "EXPORT_MANIFEST.json"
    if csv_path.exists() or manifest_path.exists():
        raise StoreError("the export already exists and is never overwritten")
    reviews = ReviewStore(layout).current()
    missing = [i.item_id for i in items if i.item_id not in reviews]
    if missing:
        raise StoreError(f"cannot export: {len(missing)} of {len(items)} items have no review record "
                         f"(first: {missing[:5]})")
    ids = {i.item_id for i in items}
    bad_refs = [i.item_id for i in items
                if reviews[i.item_id]["labels"]["near_dup_of"]
                and (reviews[i.item_id]["labels"]["near_dup_of"] not in ids
                     or reviews[i.item_id]["labels"]["near_dup_of"] == i.item_id)]
    if bad_refs:
        raise StoreError(f"cannot export: invalid near_dup_of references on {bad_refs[:5]}; they are never dropped or repaired")
    with open(layout.snapshot / "annotation_A.csv", newline="", encoding="utf-8-sig") as f:
        source = {r["item_id"]: r for r in csv.DictReader(f)}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(B2T_COLUMNS), lineterminator="\n")
    w.writeheader()
    for it in items:
        r = reviews[it.item_id]
        row = {c: source[it.item_id][c] for c in annotate.SOURCE_COLUMNS}
        row.update({"protocol_id": r["protocol_id"], **{k: r["labels"][k] for k in CONTENT},
                    "near_dup_of": r["labels"]["near_dup_of"], "note": r["labels"]["note"],
                    "insufficient_evidence": r["insufficient_evidence"], "annotator_id": r["reviewer_id"],
                    "annotator_type": "human", "reviewed_at_utc": r["reviewed_at_utc"], "label_origin": r["label_origin"],
                    "ai_exposure": r["ai_exposure"], "suggestion_ref": r["suggestion_ref"] or "",
                    "edit_reason_code": r["edit_reason_code"] or "",
                    "review_seconds": "" if r["review_seconds"] is None else f"{r['review_seconds']:.1f}",
                    "review_record_sha256": r["record_sha256"]})
        w.writerow(row)
    csv_sha = atomic_write(csv_path, buf.getvalue().encode("utf-8"))
    os.chmod(csv_path, 0o444)
    recs = SuggestionStore(layout).records()
    overlap_items = [i.item_id for i in items if i.historical_overlap]
    manifest = {
        "schema": DATASET_SCHEMA, "experiment_id": cfg.experiment_id, "protocol_id": cfg.protocol_id,
        "created_at_utc": utc(clock()), "rows": len(items), "csv_sha256": csv_sha,
        "by_label_origin": dict(Counter(r["label_origin"] for r in reviews.values())),
        "by_ai_exposure": dict(Counter(r["ai_exposure"] for r in reviews.values())),
        "near_dup_references": sum(bool(r["labels"]["near_dup_of"]) for r in reviews.values()),
        "temperatures": sorted({r["params"].get("temperature") for r in recs if r.get("params")} - {None}),
        "historical_overlap_items": len(overlap_items),
        "historical_overlap_ai_exposed": sum(reviews[i]["ai_exposure"] == "seen" for i in overlap_items),
        "historical_overlap_blind_human": sum(reviews[i]["label_origin"] == "human_blind" for i in overlap_items),
        "prompt_versions": sorted({r["prompt_version"] for r in recs}), "rubric_versions": sorted({r["rubric_version"] for r in recs}),
        "models": sorted({f"{r['provider']['model_id']}@{r['provider'].get('model_version')}" for r in recs}),
        "chain_heads": {"suggestions": ChainedJsonl(layout.suggestions_raw).head(), "reviews": ChainedJsonl(layout.reviews).head(),
                        "audit": ChainedJsonl(layout.audit).head()},
        "snapshot_fingerprints_sha256": sha_file(layout.snapshot_fingerprints),
        "independence_statement": ("Rows with ai_exposure = 'seen' are human labels made after seeing an AI suggestion. "
                                   "They are NOT independent human labels and must not be reported as such. Only rows "
                                   "with ai_exposure = 'none' were made without AI exposure."),
        "original_dataset": "unchanged; this export is a separate, versioned dataset",
    }
    atomic_write(manifest_path, json.dumps(manifest, indent=1, sort_keys=True).encode("utf-8"))
    os.chmod(manifest_path, 0o444)
    AuditLog(layout).emit("export_created", now=clock(), experiment_id=cfg.experiment_id, sha256=csv_sha,
                          counts={"rows": len(items)})
    return manifest
