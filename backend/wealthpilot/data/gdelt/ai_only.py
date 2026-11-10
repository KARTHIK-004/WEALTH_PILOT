"""AI-only suggestions: a separate schema and store, **permanently non-independent** (B2-U18). Offline; it calls no provider.

A model-generated suggestion that no human has reviewed is not a label. It is never ground truth and never an independent
reference. This module gives such output a home that cannot be mistaken for the human reference:

- **Its own schema** (``b2_ai_only_suggestion_v1``) with ``origin = "ai_only"``, ``independent = false`` and
  ``annotator_type = "ai"``, each checked on every write and every read. A record that says anything else is rejected.
- **Its own storage path**, a hash-chained file ``ai_only/ai_only_suggestions_v1.jsonl`` that must lie outside every annotation
  review folder (a folder holding ``annotation_A.csv`` or a ``working`` directory). The store refuses such a location.
- **No route into the reference.** This module imports nothing that writes the working copy, merges, freezes or evaluates, and
  none of those modules imports this one (tests check both directions). The only reader outside it is the metric-status report,
  which counts AI-only records as ``exploratory`` and never as independent evidence.

Ingestion fails closed. A raw model response goes through the existing strict output validator (``schema.validate_output``:
no repair, no fence stripping), then the cross-row rules in ``annotation_rules``. A malformed, incomplete, contradictory or
rubric-invalid response is rejected and nothing is stored. An overlap item is refused (the overlap items are never sent, D2).
The raw response text is **not** stored, only its SHA-256 (retention: the text is the part that cannot expire).

Writes are idempotent: the same item with the same output hash is not appended twice, so a resumed run adds nothing.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import annotation_rules
from wealthpilot.data.gdelt.ai.chain import ChainedJsonl
from wealthpilot.data.gdelt.ai.fingerprints import sha256_obj, sha256_text
from wealthpilot.data.gdelt.ai.schema import SourceItem, validate_output
from wealthpilot.data.gdelt.annotate import LABEL_COLUMNS
from wealthpilot.data.gdelt.errors import GdeltToolError

SCHEMA = "b2_ai_only_suggestion_v1"
ORIGIN = "ai_only"
STORE_DIR = "ai_only"
FILE_NAME = "ai_only_suggestions_v1.jsonl"
NON_INDEPENDENT = ("AI-only suggestion: model-generated and unreviewed. It is NOT an independent label, NOT ground truth and "
                   "must never be used to estimate precision, recall or any accuracy.")
CONTENT_KEYS = ("rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice", "pol_equity", "pol_rates", "pol_gold",
                "near_dup_of", "note")
_REQUIRED = {"schema", "origin", "independent", "annotator_type", "item_id", "labels", "flags", "uncertainty",
             "insufficient_evidence", "model_id", "prompt_version", "config_sha256", "input_fingerprint", "output_sha256",
             "raw_response_sha256", "created_at_utc", "statement"}
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class AiOnlyError(GdeltToolError):
    code = "ai_only_error"


def default_root(output_root: Path, experiment_id: str) -> Path:
    """The recommended location: a sibling of ``review/``, never inside an annotation review folder."""
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$", experiment_id):
        raise AiOnlyError("experiment_id must be 1-64 letters, digits, '.', '_' or '-'")
    return Path(output_root) / STORE_DIR / experiment_id


def _outside_review_folders(root: Path) -> None:
    resolved = Path(root).resolve()
    for folder in (resolved, *resolved.parents):
        if (folder / "annotation_A.csv").exists() or (folder / "working").is_dir() or folder.name == "review_files":
            raise AiOnlyError(f"{root} is inside or beside an annotation review folder ({folder.name}); the AI-only store "
                              "must never share a location with the human reference")


def output_hash(labels: Mapping[str, str]) -> str:
    return sha256_obj({k: labels[k] for k in CONTENT_KEYS})


def validate_record(rec: Any, items_by_id: Mapping[str, SourceItem]) -> list[str]:
    """Every problem with one stored or about-to-be-stored record (empty means valid)."""
    if not isinstance(rec, dict):
        return ["the record is not an object"]
    errs: list[str] = []
    body = {k: v for k, v in rec.items() if k not in ("prev_sha256", "record_sha256")}
    if set(body) != _REQUIRED:
        errs.append(f"fields differ from the schema (missing {sorted(_REQUIRED - set(body))}, extra {sorted(set(body) - _REQUIRED)})")
        return errs
    if body["schema"] != SCHEMA:
        errs.append(f"schema must be {SCHEMA}")
    if body["origin"] != ORIGIN:
        errs.append("origin must be 'ai_only'")
    if body["independent"] is not False:
        errs.append("independent must be false: an AI-only suggestion is never independent")
    if body["annotator_type"] != "ai":
        errs.append("annotator_type must be 'ai'")
    if body["statement"] != NON_INDEPENDENT:
        errs.append("the non-independence statement is missing or altered")
    for key in ("config_sha256", "input_fingerprint", "output_sha256", "raw_response_sha256"):
        if not (isinstance(body[key], str) and _SHA.match(body[key])):
            errs.append(f"{key} must be a SHA-256")
    for key in ("model_id", "prompt_version"):
        if not (isinstance(body[key], str) and body[key].strip()):
            errs.append(f"{key} is required")
    if not (isinstance(body["created_at_utc"], str) and _TS.match(body["created_at_utc"])):
        errs.append("created_at_utc must be a UTC timestamp")
    item = items_by_id.get(body["item_id"]) if isinstance(body["item_id"], str) else None
    if item is None:
        errs.append("the item is not in the dataset")
    else:
        if item.historical_overlap:
            errs.append("an overlap item must never have an AI suggestion (it is never sent)")
        if body["input_fingerprint"] != item.fingerprint:
            errs.append("the suggestion was made for different input than the dataset holds")
    labels = body["labels"]
    if not isinstance(labels, dict) or set(labels) != set(CONTENT_KEYS) or any(not isinstance(v, str) for v in labels.values()):
        errs.append("labels must hold exactly the content fields, as text")
        return errs
    if body["output_sha256"] != output_hash(labels):
        errs.append("output_sha256 does not match the labels")
    rep = annotation_rules.check_rows([{**{c: "" for c in LABEL_COLUMNS}, **labels, "item_id": body["item_id"]}],
                                      expected_ids=set(items_by_id), mode=annotation_rules.CONTENT_ONLY)
    errs += [f"{p['kind']}: {p['detail']}" for p in rep.problems if p["kind"] not in ("missing_item",)]
    return errs


@dataclass(frozen=True)
class IngestResult:
    accepted: bool
    errors: tuple[str, ...]
    record: dict[str, Any] | None = None
    duplicate: bool = False


class AiOnlyStore:
    """The append-only, hash-chained AI-only store. It never touches the review folder, the working copy or the key."""

    def __init__(self, root: Path) -> None:
        _outside_review_folders(Path(root))
        self.root = Path(root)
        self.chain = ChainedJsonl(self.root / FILE_NAME)

    def records(self, items_by_id: Mapping[str, SourceItem]) -> list[dict[str, Any]]:
        """All records, with the chain verified and every record re-validated. Any problem raises (fail closed)."""
        out = self.chain.records()
        for rec in out:
            errs = validate_record(rec, items_by_id)
            if errs:
                raise AiOnlyError(f"a stored AI-only record is invalid: {'; '.join(errs[:3])}")
        return out

    def append(self, record: dict[str, Any], items_by_id: Mapping[str, SourceItem]) -> dict[str, Any]:
        errs = validate_record(record, items_by_id)
        if errs:
            raise AiOnlyError("the AI-only record is invalid: " + "; ".join(errs[:3]))
        return self.chain.append(record)

    def ingest(self, raw_response: str, item: SourceItem, items_by_id: Mapping[str, SourceItem], *, model_id: str,
               prompt_version: str, config_sha256: str,
               clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> IngestResult:
        """Validate one raw model response and store it as an AI-only suggestion. Rejections store nothing."""
        if not isinstance(raw_response, str):
            return IngestResult(False, ("the response is not text",))
        known = items_by_id.get(item.item_id)
        if known is None or known.fingerprint != item.fingerprint:
            return IngestResult(False, ("the item is not in the dataset",))
        if item.historical_overlap:
            return IngestResult(False, ("an overlap item must never have an AI suggestion (it is never sent)",))
        if not item.sendable:
            return IngestResult(False, ("the item has input problems and is never sent",))
        v = validate_output(raw_response, item)
        if not v.ok or v.parsed is None:
            return IngestResult(False, tuple(v.errors))
        p = v.parsed
        labels = {**{k: p[k].strip() for k in CONTENT_KEYS if k in p and k != "near_dup_of"}, "near_dup_of": ""}
        record = {"schema": SCHEMA, "origin": ORIGIN, "independent": False, "annotator_type": "ai", "item_id": item.item_id,
                  "labels": labels, "flags": list(v.flags), "uncertainty": dict(p["uncertainty"]),
                  "insufficient_evidence": bool(p["insufficient_evidence"]), "model_id": model_id,
                  "prompt_version": prompt_version, "config_sha256": config_sha256, "input_fingerprint": item.fingerprint,
                  "output_sha256": output_hash(labels), "raw_response_sha256": sha256_text(raw_response),
                  "created_at_utc": clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "statement": NON_INDEPENDENT}
        errs = validate_record(record, items_by_id)
        if errs:
            return IngestResult(False, tuple(errs))
        for existing in self.records(items_by_id):
            if existing["item_id"] == item.item_id and existing["output_sha256"] == record["output_sha256"] \
                    and existing["config_sha256"] == config_sha256:
                return IngestResult(True, (), existing, duplicate=True)      # a resumed run adds nothing
        return IngestResult(True, (), self.chain.append(record))


def diagnostics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Descriptive counts only. They say how the model labelled, never whether it was right."""
    n = len(records)
    out: dict[str, Any] = {"records": n, "kind": "diagnostic_only", "independent": False, "statement": NON_INDEPENDENT}
    if not n:
        return out
    out["items"] = len({r["item_id"] for r in records})
    out["ambiguity_rate"] = sum("A" in (r["labels"][k] for k in annotation_rules.REL_FIELDS) for r in records) / n
    out["insufficient_evidence_rate"] = sum(bool(r["insufficient_evidence"]) for r in records) / n
    out["label_counts"] = {k: dict(Counter(r["labels"][k] for r in records)) for k in annotation_rules.REL_FIELDS}
    out["models"] = sorted({r["model_id"] for r in records})
    return out
