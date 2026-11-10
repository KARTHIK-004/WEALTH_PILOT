"""Offline integrity checks and methodology-neutral aggregation for the AI-assisted dataset (B2-U5).

This module reads only the exported ``annotation_b2t_v1.csv``, the snapshot's item list, the recorded original overlap list
and the suggestion records. It never reads the sealed evaluation key and never calls anything.

**What it does:** validates the dataset (schema, item identity, rubric validity, the link between ``label_origin`` and
``ai_exposure``, suggestion references, duplicate references); counts items by condition; and, only when a blind-subset
provenance record validates, compares the blind human labels with the raw AI suggestions with raw agreement counts and
Wilson intervals.

**What it does not do, and the output says so:** it does not call anything agreement *quality*, model *accuracy* or
research *validity*. Cohen's kappa, Gwet's AC1 and the treatment of ambiguous (``A``) labels are left out until the
methodology is approved (both ways of treating ``A`` are shown, with neither designated primary). A label made after seeing
an AI suggestion is never counted as an independent human label.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.ai.export import B2T_COLUMNS
from wealthpilot.data.gdelt.ai.reviewer import CONTENT, ORIGIN
from wealthpilot.data.gdelt.ai.schema import REL_FIELDS
from wealthpilot.data.gdelt.estimators import confusion, reporting_floor, wilson

STATUS = "DATA-INTEGRITY CHECKS AND METHODOLOGY-NEUTRAL AGGREGATION ONLY"
CLAIMS_NOT_MADE = ("human-AI agreement as a measure of accuracy", "model quality", "research validity",
                   "agreement between two independent humans")
DECISIONS_BEFORE_STATISTICAL_EVALUATION = (
    "how ambiguous (A) labels are treated in the primary analysis",
    "whether Cohen's kappa and Gwet's AC1 are reported, and how",
    "how batch clustering is handled (a clustered bootstrap), because Wilson intervals ignore it",
    "whether AI-assisted labels may be used for the B2-I section 4.7 filter decision (an amendment)",
    "the polarity option (B2-U4 package section 6.2)")
ORIGINS = frozenset(ORIGIN.values())
UNEXPOSED_ORIGINS = frozenset({"human_blind", "human_no_suggestion"})
_TS = "%Y-%m-%dT%H:%M:%SZ"
_AGREEMENT_FIELDS = (*REL_FIELDS, "company_notice")
LIMITATIONS = (
    "one human annotator: this is never agreement between two humans",
    "Wilson intervals treat items as independent; items in a batch are correlated, so the true intervals are wider",
    "headline-only evidence limits any labeller",
    "agreement is not accuracy: neither side is a reference label",
    "small denominators are reported as counts; see the reporting floor per theme")


def blind_subset_fingerprint(item_ids: list[str] | tuple[str, ...]) -> str:
    """SHA-256 of the sorted item IDs joined by newlines. The blind-subset provenance must carry this value."""
    return hashlib.sha256("\n".join(sorted(item_ids)).encode("utf-8")).hexdigest()


def first_suggestion_time(records: list[dict[str, Any]]) -> datetime | None:
    """The earliest suggestion attempt recorded, or None if there is none (or a time is unreadable)."""
    times = [_parse_ts(r.get("started_at_utc")) for r in records]
    return None if not times or any(t is None for t in times) else min(t for t in times if t is not None)


def _problem(kind: str, item_id: str | None, detail: str) -> dict[str, Any]:
    return {"kind": kind, "item_id": item_id, "detail": detail}


def _parse_ts(value: Any) -> datetime | None:
    try:
        return datetime.strptime(str(value), _TS).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read_export(path: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Rows and schema problems. A wrong header means the rows are not read at all."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = tuple(reader.fieldnames or ())
            if header != B2T_COLUMNS:
                return [], [_problem("schema", None, f"{Path(path).name} does not have the b2t_annotation_v1 columns")]
            return list(reader), []
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return [], [_problem("schema", None, f"cannot read {Path(path).name}: {type(exc).__name__}")]


def check_rows(rows: list[dict[str, str]], universe_ids: set[str],
               valid_suggestions: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Every problem found, none stopping the others. ``valid_suggestions`` maps item ID to its valid suggestion record."""
    problems: list[dict[str, Any]] = []
    seen_ids = Counter(r.get("item_id", "") for r in rows)
    for item_id, n in sorted(seen_ids.items()):
        if n > 1:
            problems.append(_problem("duplicate_item", item_id, f"{n} records for one item"))
    for item_id in sorted(set(seen_ids) - universe_ids):
        problems.append(_problem("unknown_item", item_id, "not in the annotation universe of this experiment"))
    for item_id in sorted(universe_ids - set(seen_ids)):
        problems.append(_problem("missing_item", item_id, "no annotation record"))
    for r in rows:
        iid = r.get("item_id", "")
        v = {c: "" for c in annotate.LABEL_COLUMNS}
        v.update({k: (r.get(k) or "").strip() for k in (*CONTENT, "note", "near_dup_of")})
        for err in annotate.content_errors(v, item_id=iid, all_ids=universe_ids):
            kind = "near_dup_invalid" if err.startswith("near_dup_of") else "malformed"
            problems.append(_problem(kind, iid, err))
        if r.get("annotator_type") != "human":
            problems.append(_problem("malformed", iid, f"annotator_type must be 'human' (got {r.get('annotator_type')!r})"))
        if r.get("insufficient_evidence") not in ("Y", "N"):
            problems.append(_problem("malformed", iid, "insufficient_evidence must be Y or N"))
        if _parse_ts(r.get("reviewed_at_utc")) is None:
            problems.append(_problem("malformed", iid, "reviewed_at_utc is missing or not YYYY-MM-DDTHH:MM:SSZ"))
        origin, exposure = r.get("label_origin"), r.get("ai_exposure")
        if origin not in ORIGINS:
            problems.append(_problem("malformed", iid, f"unknown label_origin {origin!r}"))
        elif exposure not in ("seen", "none"):
            problems.append(_problem("malformed", iid, f"ai_exposure must be 'seen' or 'none' (got {exposure!r})"))
        else:
            expected = "none" if origin in UNEXPOSED_ORIGINS else "seen"
            if exposure != expected:
                problems.append(_problem("origin_exposure_mismatch", iid,
                                         f"label_origin {origin} requires ai_exposure {expected}, not {exposure}: an "
                                         "AI-exposed label is never treated as an independent human label"))
            ref = r.get("suggestion_ref") or ""
            if exposure == "none" and ref:
                problems.append(_problem("suggestion_ref_inconsistent", iid, "an unexposed label must not cite a suggestion"))
            if exposure == "seen" and not ref:
                problems.append(_problem("suggestion_ref_inconsistent", iid, "an AI-seen label must cite its suggestion"))
            if valid_suggestions is not None:
                sug = valid_suggestions.get(iid)
                if exposure == "seen" and sug is not None and ref and ref != sug["record_sha256"]:
                    problems.append(_problem("suggestion_ref_inconsistent", iid, "the cited suggestion is not this item's valid suggestion"))
                if exposure == "seen" and sug is None:
                    problems.append(_problem("suggestion_ref_inconsistent", iid, "an AI-seen label but no valid suggestion exists"))
                if origin == "human_no_suggestion" and sug is not None:
                    problems.append(_problem("origin_exposure_mismatch", iid, "marked 'no suggestion' but a valid suggestion exists"))
    return problems


def summarise(rows: list[dict[str, str]], overlap_ids: frozenset[str]) -> dict[str, Any]:
    """Counts by condition. Rows are taken as given: run ``check_rows`` first and read its problems alongside."""
    origin = Counter(r.get("label_origin") for r in rows)
    exposure = Counter(r.get("ai_exposure") for r in rows)
    seen = exposure.get("seen", 0)
    ai_assisted = origin.get("accepted_ai", 0) + origin.get("edited_ai", 0)
    by_group: dict[str, dict[str, dict[str, int]]] = {}
    for group, pred in (("ai_exposed", lambda r: r.get("ai_exposure") == "seen"), ("not_ai_exposed", lambda r: r.get("ai_exposure") == "none")):
        by_group[group] = {f: dict(Counter(r.get(f) for r in rows if pred(r))) for f in _AGREEMENT_FIELDS}
    accepted = origin.get("accepted_ai", 0)
    accept_ci = wilson(accepted, seen) if 0 <= accepted <= seen else None      # inconsistent rows must not crash the report
    return {
        "records": len(rows), "by_label_origin": dict(origin), "by_ai_exposure": dict(exposure),
        "conditions": {
            "human_only_no_ai_exposure": exposure.get("none", 0),
            "independent_human_candidates_blind": origin.get("human_blind", 0),
            "ai_assisted_accepted_or_edited": ai_assisted,
            "ai_exposed_total": seen,
            "ai_exposed_other_after_seeing": seen - ai_assisted},
        "ai_exposed_note": "every AI-exposed label is a human label made after seeing a suggestion; none is independent",
        "acceptance_among_ai_exposed": {"accepted": accepted, "n": seen,
                                        "wilson_95": list(accept_ci) if accept_ci else None},
        "near_dup_references": sum(bool((r.get("near_dup_of") or "").strip()) for r in rows),
        "historical_overlap_items_ai_exposed": sum(1 for r in rows if r.get("item_id") in overlap_ids and r.get("ai_exposure") == "seen"),
        "label_distribution_by_exposure": by_group}


def validate_blind_provenance(prov: Any, *, overlap_ids: frozenset[str], rows: list[dict[str, str]],
                              first_suggestion_at: datetime | None, experiment_id: str | None = None) -> list[str]:
    """Why a blind-subset comparison cannot be trusted, or an empty list. Nothing is inferred or repaired."""
    if not isinstance(prov, dict):
        return ["blind-subset provenance was not supplied as a record"]
    need = {"experiment_id", "selection_rule", "item_ids", "selection_fingerprint_sha256", "committed_at_utc"}
    if need - set(prov):
        return [f"provenance is missing: {sorted(need - set(prov))}"]
    out: list[str] = []
    ids = prov["item_ids"]
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        return ["provenance item_ids must be a non-empty list of unique item IDs"]
    if experiment_id is not None and prov["experiment_id"] != experiment_id:
        out.append("provenance belongs to a different experiment")
    if not isinstance(prov["selection_rule"], str) or not prov["selection_rule"].strip():
        out.append("provenance must state the selection rule")
    if prov["selection_fingerprint_sha256"] != blind_subset_fingerprint(ids):
        out.append("the selection fingerprint does not match the listed item IDs")
    outside = sorted(set(ids) - overlap_ids)
    if outside:
        out.append(f"blind items must be original overlap items; not overlap: {outside[:5]}")
    committed = _parse_ts(prov["committed_at_utc"])
    if committed is None:
        out.append("committed_at_utc is missing or not YYYY-MM-DDTHH:MM:SSZ")
    elif first_suggestion_at is not None and not committed < first_suggestion_at:
        out.append("the subset was not committed before the first AI suggestion was generated")
    by_id = {r["item_id"]: r for r in rows}
    for i in ids:
        r = by_id.get(i)
        if r is None:
            out.append(f"blind item {i} has no annotation record")
        elif r.get("label_origin") != "human_blind" or r.get("ai_exposure") != "none":
            out.append(f"blind item {i} is not an unexposed blind label ({r.get('label_origin')}, ai_exposure {r.get('ai_exposure')})")
    for r in rows:
        if r.get("label_origin") == "human_blind" and r.get("item_id") not in ids:
            out.append(f"{r['item_id']} is labelled blind but is not in the registered subset")
    return out


def _agree(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    n = len(pairs)
    k = sum(a == b for a, b in pairs)
    ci = wilson(k, n)
    return {"n": n, "agree": k, "raw_agreement": (k / n) if n else None, "wilson_95": list(ci) if ci else None}


def compare_blind(rows: list[dict[str, str]], valid_suggestions: dict[str, dict[str, Any]], prov: Any, *,
                  overlap_ids: frozenset[str], first_suggestion_at: datetime | None,
                  experiment_id: str | None = None) -> dict[str, Any]:
    """Blind human labels against the raw AI suggestions. Refuses (returns the reasons) unless the provenance validates."""
    problems = validate_blind_provenance(prov, overlap_ids=overlap_ids, rows=rows, first_suggestion_at=first_suggestion_at,
                                         experiment_id=experiment_id)
    if problems:
        return {"valid": False, "problems": problems, "comparison": None,
                "note": "no independent human-versus-AI comparison is reported"}
    by_id = {r["item_id"]: r for r in rows}
    ids = sorted(prov["item_ids"])
    paired = [i for i in ids if i in valid_suggestions]
    out: dict[str, Any] = {"blind_items": len(ids), "with_valid_suggestion": len(paired),
                           "without_valid_suggestion": len(ids) - len(paired), "per_field": {}}
    for f in _AGREEMENT_FIELDS:
        human = [by_id[i][f] for i in paired]
        ai = [valid_suggestions[i]["parsed"][f] for i in paired]
        pairs = list(zip(human, ai))
        non_a = [(a, b) for a, b in pairs if "A" not in (a, b)] if f != "company_notice" else pairs
        entry: dict[str, Any] = {"all_pairs": _agree(pairs), "confusion_human_rows_by_ai_cols": confusion(human, ai)}
        if f in REL_FIELDS:
            entry["excluding_pairs_with_A"] = {**_agree(non_a), "excluded": len(pairs) - len(non_a),
                                               "reporting_floor": reporting_floor(len(non_a))}
            entry["R_versus_not_R"] = _agree([(a == "R", b == "R") for a, b in pairs])  # type: ignore[misc]
        out["per_field"][f] = entry
    return {"valid": True, "problems": [], "comparison": out,
            "note": "descriptive agreement of one human with one model on a pre-registered blind subset; not accuracy"}


def evaluate(rows: list[dict[str, str]], schema_problems: list[dict[str, Any]], *, universe_ids: set[str],
             overlap_ids: frozenset[str], valid_suggestions: dict[str, dict[str, Any]],
             first_suggestion_at: datetime | None, provenance: Any = None, experiment_id: str | None = None) -> dict[str, Any]:
    problems = [*schema_problems, *check_rows(rows, universe_ids, valid_suggestions)] if not schema_problems else schema_problems
    kinds = Counter(p["kind"] for p in problems)
    report: dict[str, Any] = {
        "status": STATUS, "claims_not_made": list(CLAIMS_NOT_MADE), "integrity_ok": not problems,
        "universe_items": len(universe_ids), "problems_by_kind": dict(kinds), "problems": problems,
        "limitations": list(LIMITATIONS),
        "decisions_required_before_statistical_evaluation": list(DECISIONS_BEFORE_STATISTICAL_EVALUATION)}
    if schema_problems:
        report.update(summary=None, blind_comparison={"valid": False, "problems": ["dataset schema is invalid"],
                                                      "comparison": None})
        return report
    report["summary"] = summarise(rows, overlap_ids)
    if provenance is None:
        report["blind_comparison"] = {"valid": False, "problems": ["no blind-subset provenance was supplied"],
                                      "comparison": None, "note": "no independent human-versus-AI comparison is reported"}
    elif problems:
        report["blind_comparison"] = {"valid": False, "problems": ["the dataset has integrity problems; fix them first"],
                                      "comparison": None, "note": "no independent human-versus-AI comparison is reported"}
    else:
        report["blind_comparison"] = compare_blind(rows, valid_suggestions, provenance, overlap_ids=overlap_ids,
                                                   first_suggestion_at=first_suggestion_at, experiment_id=experiment_id)
    return report
