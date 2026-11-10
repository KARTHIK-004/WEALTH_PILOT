"""Input items, the model's output schema, and strict validation.

Validation reuses the existing rubric validator (``annotate.content_errors``) so a suggestion is held to the same
rubric as a human label. Nothing is ever repaired: a response that does not validate is recorded as invalid with its
reasons, and the item goes to a human with no suggestion.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.ai.fingerprints import item_fingerprint
from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS

APPROVED_INPUT_FIELDS = ("item_id", "batch_date_utc", "source_domain", "url", "title")
REL_FIELDS = ("rel_equity", "rel_rates", "rel_gold")
POL_FIELDS = ("pol_equity", "pol_rates", "pol_gold")
OUTPUT_KEYS = ("item_id", *REL_FIELDS, "amb_code", "company_notice", *POL_FIELDS, "note", "evidence_excerpts",
               "insufficient_evidence", "uncertainty", "evidence_basis")
UNCERTAINTY_VALUES = ("low", "medium", "high")
EVIDENCE_BASIS = "headline_url_only"
MAX_NOTE, MAX_EXCERPT = 300, 200
ITEM_ID_RE = re.compile(r"^D\d{4}$")
SHORT_TITLE_CHARS = 20


class SchemaError(GdeltToolError):
    code = "ai_schema_error"


@dataclass(frozen=True)
class SourceItem:
    item_id: str
    fields: dict[str, str]                 # exactly the approved input fields
    fingerprint: str
    historical_overlap: bool               # the ORIGINAL overlap membership, kept as provenance
    mech_dup: str                          # pipeline duplicate mark, carried for the review queue only
    input_problems: tuple[str, ...] = ()   # a non-empty tuple means: never sent to a provider

    @property
    def sendable(self) -> bool:
        return not self.input_problems


def _control_chars(text: str) -> bool:
    return any(unicodedata.category(ch)[0] == "C" for ch in text)


def validate_input(fields: dict[str, Any]) -> list[str]:
    """Problems that make an item unsafe to send. Titles are never silently edited."""
    problems: list[str] = []
    if set(fields) != set(APPROVED_INPUT_FIELDS):
        problems.append(f"input fields must be exactly {list(APPROVED_INPUT_FIELDS)}")
        return problems
    for k in APPROVED_INPUT_FIELDS:
        if not isinstance(fields[k], str):
            problems.append(f"{k} is not text")
        elif _control_chars(fields[k]):
            problems.append(f"{k} contains control or format characters")
    if isinstance(fields["item_id"], str) and not ITEM_ID_RE.match(fields["item_id"]):
        problems.append("item_id has an unexpected format")
    if isinstance(fields.get("url"), str) and not fields["url"].strip():
        problems.append("url is empty")
    return problems


def load_items(path: Path) -> list[SourceItem]:
    """Load the ORIGINAL annotation file (no labels). Refuses a file that holds labels, duplicate IDs or the
    wrong columns, so the human working copy can never be passed by mistake."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = tuple(reader.fieldnames or ())
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise SchemaError(f"cannot read {path.name}: {type(exc).__name__}") from exc
    if header != ANNOTATION_COLUMNS:
        raise SchemaError(f"{path.name} does not have the b2o_annotation_v1 columns")
    labelled = [r["item_id"] for r in rows if any((r.get(c) or "").strip() for c in annotate.LABEL_COLUMNS)]
    if labelled:
        raise SchemaError(f"{path.name} contains labels ({len(labelled)} rows): the source must be the original, "
                          "unlabelled file")
    ids = [(r.get("item_id") or "").strip() for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup or not all(ids):
        raise SchemaError(f"item IDs must be present and unique (duplicates: {dup[:5]})")
    items = []
    for r in rows:
        fields = {k: r[k] for k in APPROVED_INPUT_FIELDS}
        if r["overlap_subset"] not in ("Y", "N"):
            raise SchemaError(f"{r['item_id']}: overlap_subset must be Y or N")
        items.append(SourceItem(r["item_id"], fields, item_fingerprint(fields), r["overlap_subset"] == "Y",
                                r["mech_dup"], tuple(validate_input(fields))))
    return items


# ---------------------------------------------------------------- output

def output_json_schema() -> dict[str, Any]:
    """Provider-neutral description of the expected output (for structured-output features). Our own validator
    below is authoritative: a provider's schema enforcement is never trusted."""
    rel = {"type": "string", "enum": sorted(annotate.REL_VALUES)}
    pol = {"type": "string", "enum": sorted(annotate.POL_VALUES) + [""]}
    unc = {"type": "string", "enum": list(UNCERTAINTY_VALUES)}
    return {
        "type": "object", "additionalProperties": False, "required": list(OUTPUT_KEYS),
        "properties": {
            "item_id": {"type": "string"}, **{k: rel for k in REL_FIELDS},
            "amb_code": {"type": "string", "enum": sorted(annotate.AMB_CODES) + [""]},
            "company_notice": {"type": "string", "enum": sorted(annotate.COMPANY_VALUES)},
            **{k: pol for k in POL_FIELDS}, "note": {"type": "string", "maxLength": MAX_NOTE},
            "evidence_excerpts": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["field", "excerpt"],
                "properties": {"field": {"type": "string", "enum": list(REL_FIELDS)},
                               "excerpt": {"type": "string", "maxLength": MAX_EXCERPT}}}},
            "insufficient_evidence": {"type": "boolean"},
            "uncertainty": {"type": "object", "additionalProperties": False, "required": list(REL_FIELDS),
                            "properties": {k: unc for k in REL_FIELDS}},
            "evidence_basis": {"type": "string", "enum": [EVIDENCE_BASIS]},
        },
    }


def norm(text: str) -> str:
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class OutputValidation:
    ok: bool
    parsed: dict[str, Any] | None
    errors: tuple[str, ...]
    flags: tuple[str, ...]


def validate_output(raw: str, item: SourceItem, *, require_evidence_for: tuple[str, ...] = ("R", "RL")) -> OutputValidation:
    """Strictly validate one raw response for ``item``. No repair, no fence stripping, no guessing."""
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return OutputValidation(False, None, ("response is not a single JSON object",), ())
    if not isinstance(parsed, dict):
        return OutputValidation(False, None, ("response is not a single JSON object",), ())
    errs: list[str] = []
    missing = [k for k in OUTPUT_KEYS if k not in parsed]
    extra = sorted(set(parsed) - set(OUTPUT_KEYS))
    if missing:
        errs.append(f"missing fields: {', '.join(missing)}")
    if extra:
        errs.append(f"unexpected fields: {', '.join(extra)}")
    if missing:
        return OutputValidation(False, parsed, tuple(errs), ())
    if parsed["item_id"] != item.item_id:
        errs.append(f"item_id {parsed['item_id']!r} does not match the requested item")
    text_fields = ("amb_code", "company_notice", *REL_FIELDS, *POL_FIELDS, "note", "evidence_basis")
    bad_types = [k for k in text_fields if not isinstance(parsed[k], str)]
    if bad_types:
        errs.append(f"fields must be text: {', '.join(bad_types)}")
    if not isinstance(parsed["insufficient_evidence"], bool):
        errs.append("insufficient_evidence must be true or false")
    if errs:
        return OutputValidation(False, parsed, tuple(errs), ())
    if parsed["evidence_basis"] != EVIDENCE_BASIS:
        errs.append(f"evidence_basis must be {EVIDENCE_BASIS!r}: only the supplied headline context may be claimed")
    if len(parsed["note"]) > MAX_NOTE:
        errs.append(f"note is longer than {MAX_NOTE} characters")
    unc = parsed["uncertainty"]
    if not isinstance(unc, dict) or set(unc) != set(REL_FIELDS) or any(unc[k] not in UNCERTAINTY_VALUES for k in unc):
        errs.append("uncertainty must give low, medium or high for each theme")
    v = {c: "" for c in annotate.LABEL_COLUMNS}
    v.update({k: parsed[k].strip() for k in ("amb_code", "company_notice", *REL_FIELDS, *POL_FIELDS, "note")})
    errs += annotate.content_errors(v, item_id=item.item_id, all_ids={item.item_id})
    rels = {k: v[k] for k in REL_FIELDS}
    if parsed["insufficient_evidence"] and "A" not in rels.values():
        errs.append("insufficient_evidence is true but no theme is labelled A")
    context = [norm(item.fields[k]) for k in ("title", "url", "source_domain")]
    excerpts = parsed["evidence_excerpts"]
    covered: set[str] = set()
    if not isinstance(excerpts, list):
        errs.append("evidence_excerpts must be a list")
        excerpts = []
    for n, ex in enumerate(excerpts, start=1):
        if not (isinstance(ex, dict) and set(ex) == {"field", "excerpt"} and isinstance(ex["field"], str)
                and isinstance(ex["excerpt"], str)):
            errs.append(f"evidence excerpt {n} is malformed")
            continue
        if ex["field"] not in REL_FIELDS:
            errs.append(f"evidence excerpt {n} names an unknown field")
            continue
        text = norm(ex["excerpt"])
        if not text or len(ex["excerpt"]) > MAX_EXCERPT:
            errs.append(f"evidence excerpt {n} is empty or too long")
        elif not any(text in c for c in context):
            errs.append(f"evidence excerpt {n} does not appear in the supplied context")
        else:
            covered.add(ex["field"])
    for k in REL_FIELDS:
        if rels[k] in require_evidence_for and k not in covered:
            errs.append(f"{k} is {rels[k]} but has no supported evidence excerpt")
    if errs:
        return OutputValidation(False, parsed, tuple(errs), ())
    flags = []
    if "A" in rels.values():
        flags.append("ambiguous")
    if parsed["insufficient_evidence"]:
        flags.append("insufficient_evidence")
    if v["company_notice"] == "U" and "R" in rels.values():
        flags.append("company_unclear_with_r")
    if sum(x == "R" for x in rels.values()) >= 2:
        flags.append("multi_theme_relevant")
    if "high" in unc.values():
        flags.append("high_uncertainty_self_reported")
    if len(item.fields["title"].strip()) < SHORT_TITLE_CHARS:
        flags.append("short_or_empty_title")
    return OutputValidation(True, parsed, (), tuple(flags))
