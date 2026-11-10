"""Label freeze and the gated evaluation against the sealed key (B2-I section 4.4, B2-P).

**Order is enforced in code:**

1. ``freeze`` succeeds only when every one of the 1,493 items is labelled and valid. It records the working
   copy's SHA-256 in a new ``freeze_record.json`` and never overwrites one.
2. ``evaluate`` first checks the freeze record, that the working copy still matches it, and that the labels are
   still complete and valid. **Only then** does it read the sealed key (``_read_key``), verify the key against
   the fingerprint recorded at build time, and compute aggregate estimates.

**The key is never printed or returned row by row.** Results are aggregates written to a new
``evaluation_results.json`` (never overwritten).

**Scopes (B2-U8).** Every series is reported over *all labelled items* as an exploratory description (it may include
AI-exposed labels, which are not independent) and, separately, over the ``human_only`` reference items. Only the second
scope gets a decision, and only when provenance (including the AI-origin export, ``ai_origin.py``) is verified; below the
reporting floor the scope is ``BLOCKED``. An outcome is authoritative only while the approved criteria are intact; it authorizes
nothing.

**What is not computed:** human-versus-AI agreement. Which label sets count as independent is part of an
unapproved methodology decision (B2-T proposal), so the pure agreement functions in ``estimators.py`` are not
wired to any dataset here. AI-based labels, if any exist, are counted and flagged as not independent.

This module is the only place besides the build (``review.py``) that refers to the sealed key.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import ai_bridge, ai_origin, annotate, overlap_lock, decision, estimators
from wealthpilot.data.gdelt.annotate import AI_BASES, AnnotationError, Paths
from wealthpilot.data.gdelt.output import atomic_write

KEY_COLUMNS_NEEDED = ("item_id", "gkg_record_id", "batch_ts", "cell", "cell_rows", "cell_items", "member_equity_us",
                      "member_rates_us", "member_gold")
MEMBER_COLUMN = {"equity": "member_equity_us", "rates": "member_rates_us", "gold": "member_gold"}


def freeze_path(p: Paths) -> Path:
    return p.working.parent / "freeze_record.json"


def results_path(p: Paths) -> Path:
    return p.working.parent / "evaluation_results.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


FINGERPRINT_CODE = ("estimators.py", "evaluate.py", "decision.py", "provenance.py", "ai_origin.py", "ai_bridge.py",
                    "overlap_lock.py", "annotate.py", "review.py")


def evaluation_fingerprint(p: Paths, ai_origin_dir: Path | None = None) -> dict[str, Any]:
    """What a freeze is bound to: the evaluation implementation, the protocol constants and the membership and
    source inputs. A change to any of them makes an earlier freeze stale (it is refused before the key is touched)."""
    pkg = Path(__file__).resolve().parent
    code = {n: hashlib.sha256((pkg / n).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for n in FINGERPRINT_CODE}
    protocol = {"criteria": decision.CRITERIA, "criteria_status": decision.CRITERIA_STATUS,
                "criteria_approval_reference": decision.CRITERIA_APPROVAL_REFERENCE, "consistency_guard": decision.GUARD,
                "proposed_thresholds": estimators.PROPOSED_THRESHOLDS,
                "bootstrap": {"generator": estimators.BOOTSTRAP_GENERATOR, "seed": estimators.BOOTSTRAP_SEED,
                              "resamples": estimators.BOOTSTRAP_RESAMPLES}, "rule_of_three": estimators.RULE_OF_THREE}
    b = p.review_files / "annotation_B.csv"
    inputs = {"annotation_A.csv": _sha(p.original) if p.original.exists() else None,
              "annotation_B.csv": _sha(b) if b.exists() else None,
              "selection_log.json": _sha(p.selection_log) if p.selection_log.exists() else None,
              "backup": _sha(p.backup) if p.backup.exists() else None,
              "overlap_lock_record": (overlap_lock.read_record(p.review_files)[0] or {}).get("record_sha256"),
              "ai_origin_export_supplied": ai_origin_dir is not None, **{f"ai_origin/{k}": v for k, v in ai_origin.file_fingerprints(ai_origin_dir).items()}}
    body = {"code": code, "protocol": protocol, "inputs": inputs}
    combined = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {**body, "combined_sha256": combined}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- freeze

def freeze(p: Paths, ai_origin_dir: Path | None = None) -> dict[str, Any]:
    """Record the complete, valid labels. Refuses unless all items are labelled and valid; never overwrites."""
    target = freeze_path(p)
    if target.exists():
        raise AnnotationError(f"already frozen ({target.name}); a freeze record is never overwritten")
    bridge = ai_bridge.load(p, ai_origin_dir)
    rep = annotate.validate(p, ai_suggestions=bridge.suggestions if bridge else None)
    if not rep.complete:
        raise AnnotationError(
            f"cannot freeze: {rep.labelled} of {rep.rows} items labelled, {len(rep.errors)} rows with errors, "
            f"{len(rep.integrity_errors)} integrity problems. Every item must be labelled and valid")
    prov = ai_origin.verified(p, ai_origin_dir)
    if not prov.ok:
        raise AnnotationError("cannot freeze: provenance is BLOCKED ("
                              + "; ".join(f"{x['kind']}: {x['detail']}" for x in prov.problems[:5]) + ")")
    working = annotate._working_rows(p)
    basis = Counter(r["label_basis"] for r in working)
    ai_used = any(b in AI_BASES for b in basis)
    _require_overlap_lock(p, prov, ai_origin_dir, action="freeze")
    from wealthpilot.data.gdelt.preflight import code_fingerprint  # local import: avoids loading preflight otherwise
    record = {
        "frozen_at_utc": _now(), "working_file": "working/annotation_A.working.csv", "working_sha256": _sha(p.working),
        "rows": rep.rows, "overlap_rows": rep.overlap_rows, "label_basis_counts": dict(sorted(basis.items())),
        "ai_labels_present": ai_used,
        "ai_suggestions_sha256": (bridge.chain_sha256 if bridge else _sha(p.ai_suggestions) if ai_used and p.ai_suggestions.exists() else None),
        "ai_suggestions_source": "b2t_suggestion_chain" if bridge else "legacy_ai_suggestions_A.csv" if ai_used else None,
        "annotation_schema": "b2o_annotation_v1", "tool_code_sha256": code_fingerprint(),
        "evaluation_fingerprint": evaluation_fingerprint(p, ai_origin_dir), "provenance_counts": prov.counts,
        "note": "labels frozen before the sealed key is opened (B2-I section 4.4); AI-based labels, if any, are "
                "flagged and are not independent human labels",
    }
    atomic_write(target, json.dumps(record, indent=1, sort_keys=True).encode("utf-8"))
    os.chmod(target, 0o444)
    return record


def _require_overlap_lock(p: Paths, prov: Any, ai_origin_dir: Path | None, *, action: str) -> None:
    """D13: when any label is AI-exposed, the overlap-labels lock must exist, still verify against the current labels, and
    every run manifest must carry its hash. Checked before the key is read."""
    if not any(v["origin"] == "ai_exposed" for v in prov.items.values()):
        return
    problems = overlap_lock.verify(p) or overlap_lock.verify_runs(p, ai_origin_dir)
    if problems:
        raise AnnotationError(f"cannot {action}: the overlap-first control is not satisfied ("
                              + "; ".join(problems[:4]) + "); the sealed key stays closed")


def _load_freeze(p: Paths) -> dict[str, Any]:
    target = freeze_path(p)
    if not target.exists():
        raise AnnotationError("labels are not frozen: run `annotate freeze` first. The sealed key stays closed")
    try:
        rec = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnnotationError(f"freeze record unreadable ({type(exc).__name__}); the sealed key stays closed") from exc
    if rec.get("working_sha256") != _sha(p.working):
        raise AnnotationError("the working copy changed after the freeze; the sealed key stays closed")
    return rec


# ---------------------------------------------------------------- the key (read only after the checks above)

def _read_key(p: Paths) -> tuple[list[dict[str, str]], str]:
    path = p.review_files / "key_sealed.csv"
    data = path.read_bytes()
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f)), hashlib.sha256(data).hexdigest()


def _join(p: Paths, working: list[dict[str, str]], key_rows: list[dict[str, str]]) -> list[estimators.Scored]:
    missing = [c for c in KEY_COLUMNS_NEEDED if not key_rows or c not in key_rows[0]]
    if missing:
        raise AnnotationError(f"the key lacks required columns: {', '.join(missing)}")
    by_item = {r["item_id"]: r for r in key_rows}
    if len(by_item) != len(key_rows) or set(by_item) != {r["item_id"] for r in working}:
        raise AnnotationError("key and labels do not cover the same items (duplicates, extras or gaps)")
    scored = []
    for w in working:
        k = by_item[w["item_id"]]
        if k["gkg_record_id"] != w["gkg_record_id"] or k["batch_ts"] != w["batch_ts"]:
            raise AnnotationError(f"provenance mismatch between key and labels for {w['item_id']}")
        scored.append(estimators.Scored(
            item_id=w["item_id"], batch_ts=w["batch_ts"], cell=k["cell"], cell_rows=int(k["cell_rows"]),
            cell_items=int(k["cell_items"]), company=w["company_notice"], label_basis=w["label_basis"],
            rel={t: w[estimators.REL[t]] for t in estimators.THEMES},
            member={t: k[MEMBER_COLUMN[t]] == "1" for t in estimators.THEMES},
            mech_dup=w.get("mech_dup"), near_dup_of=(w.get("near_dup_of") or "").strip()))
    return scored


def _metrics(items: list[estimators.Scored], t: str, n_resamples: int) -> dict[str, Any]:
    """The descriptive metrics for one series over ``items``. Nothing here decides anything."""
    prec = estimators.precision(items, t)
    point_ci = estimators.cluster_bootstrap(items, lambda s: estimators.precision(s, t)["precision"], n_resamples=n_resamples)
    recall_ci = estimators.cluster_bootstrap(items, lambda s: estimators.pooled_recall(s, t), n_resamples=n_resamples)
    pooled = estimators.pooled_recall(items, t)
    lower = point_ci["ci_95"][0] if point_ci["ci_95"] else None
    return {
        "items": len(items), "precision": prec, "precision_bootstrap": point_ci, "pooled_recall": pooled,
        "pooled_recall_bootstrap": recall_ci, "capture_recall": estimators.capture_recall(items, t),
        "unique_story_precision": estimators.unique_story_precision(items, t),
        "cell_wilson_unweighted": estimators.cell_wilson(items, t),
        "proposed_threshold_checks": estimators.proposed_thresholds(prec["precision"], lower, pooled)}


def _reweighted(subset: list[estimators.Scored]) -> list[estimators.Scored]:
    """Realised-cell reweighting (D3, F4b): each item of the subset weighs N_c / n'_c, where n'_c is the number of subset items
    actually in its cell. This is B2-I's w = N / n with n the items labelled in the cell, applied to the subset, so the subset
    estimates the same population quantity as the full sample. Within every cell the subset's weights sum to N_c."""
    counts = Counter(i.cell for i in subset)
    return [replace(i, cell_items=counts[i.cell]) for i in subset]


def _subset_refusals(all_items: list[estimators.Scored], subset: list[estimators.Scored], theme: str) -> list[str]:
    """Why a subset estimate must be refused (D3): fewer than 30 non-ambiguous series members, or a cell the metrics use
    (every cell present in the full sample: precision uses the member cells, pooled recall C1 to C6, capture recall C1 to C7)
    with no subset item. Either condition refuses the whole subset estimate."""
    out: list[str] = []
    members = estimators.precision(subset, theme)["non_ambiguous"]
    if members < decision.GUARD["min_reference_members"]:
        out.append(f"{members} non-ambiguous human-only series members; the subset minimum is {decision.GUARD['min_reference_members']}")
    missing = sorted({i.cell for i in all_items} - {i.cell for i in subset})
    if missing:
        out.append("no human-only item in cell(s) " + ", ".join(missing) + ", which the metrics use")
    return out


def _independent_reference(m: dict[str, Any] | None, ref_items: int, *, integrity_ok: bool, refusal: list[str] | None = None,
                           reweighting: str = "") -> dict[str, Any]:
    """The scope of items whose label was made with no AI exposure (``human_only``).

    Under D12(c) this scope takes **no decision** of its own: it is the independent check against which the consistency guard
    compares the AI-exposed stratum. ``INDEPENDENT_REFERENCE`` needs verified provenance and the reporting floor of
    non-ambiguous members; otherwise the scope is ``BLOCKED`` (insufficient evidence, invalid provenance or a refused subset
    estimate). A refused subset has no estimates at all.
    """
    if m is None:                                         # the subset estimate was refused (D3)
        return {"items": ref_items, "scope": "human_only_reference", "evaluation_mode": "BLOCKED", "refused": True,
                "refusal_reasons": list(refusal or []), "mode_reasons": list(refusal or []), "reweighting": reweighting}
    prec = m["precision"]
    reasons: list[str] = []
    if not integrity_ok:
        reasons.append("provenance did not verify")
    if ref_items == 0:
        reasons.append("there are no human-only reference labels")
    elif prec["non_ambiguous"] < decision.CRITERIA["reporting_floor_non_ambiguous"]:
        reasons.append(f"{prec['non_ambiguous']} non-ambiguous human-only series members; the reporting floor is "
                       f"{decision.CRITERIA['reporting_floor_non_ambiguous']}")
    mode = "BLOCKED" if reasons else "INDEPENDENT_REFERENCE"
    return {**m, "scope": "human_only_reference", "evaluation_mode": mode, "mode_reasons": reasons,
            "refused": False, "reweighting": reweighting}


# ---------------------------------------------------------------- evaluation

def evaluate(p: Paths, *, n_resamples: int = 2000, ai_origin_dir: Path | None = None) -> dict[str, Any]:
    rec = _load_freeze(p)                                    # 1. frozen, and unchanged since
    bridge = ai_bridge.load(p, ai_origin_dir)
    rep = annotate.validate(p, ai_suggestions=bridge.suggestions if bridge else None)   # 2. still complete and valid
    if not rep.complete:
        raise AnnotationError("labels are no longer complete and valid; the sealed key stays closed")
    recorded_fp = rec.get("evaluation_fingerprint")           # the freeze is bound to this implementation and protocol
    if not isinstance(recorded_fp, dict) or "combined_sha256" not in recorded_fp:
        raise AnnotationError("stale freeze: it records no evaluation fingerprint; the sealed key stays closed")
    current_fp = evaluation_fingerprint(p, ai_origin_dir)
    if current_fp["combined_sha256"] != recorded_fp["combined_sha256"]:
        parts = [k for k in ("code", "protocol", "inputs") if current_fp[k] != recorded_fp.get(k)]
        raise AnnotationError(f"stale freeze: the evaluation {', '.join(parts)} changed after the freeze; "
                              "the sealed key stays closed")
    prov = ai_origin.verified(p, ai_origin_dir)               # verified provenance and AI origin, before any key access
    if not prov.ok:
        raise AnnotationError("provenance is BLOCKED ("
                              + "; ".join(f"{x['kind']}: {x['detail']}" for x in prov.problems[:5])
                              + "); the sealed key stays closed")
    _require_overlap_lock(p, prov, ai_origin_dir, action="evaluate")
    target = results_path(p)
    if target.exists():
        raise AnnotationError(f"{target.name} already exists and is never overwritten")
    recorded = json.loads(p.selection_log.read_text(encoding="utf-8"))["files_sha256"].get("key_sealed.csv")
    key_rows, key_sha = _read_key(p)                         # 3. only now is the key read
    if key_sha != recorded:
        raise AnnotationError("the key does not match the fingerprint recorded at build time; nothing evaluated")
    items = _join(p, annotate._working_rows(p), key_rows)

    reference = [i for i in items if prov.items[i.item_id]["origin"] == "human_only"]
    results: dict[str, Any] = {}
    for t in estimators.THEMES:
        every = _metrics(items, t, n_resamples)
        if len(reference) == len(items):                      # the reference is the whole sample: nothing to reweight
            ref, refusal, how = every, None, "none: the reference is the whole sample"
        else:                                                  # a true subset: realised-cell reweighting, or refusal (D3)
            reweighted = _reweighted(reference)
            refusal = _subset_refusals(items, reweighted, t)
            ref = None if refusal else _metrics(reweighted, t, n_resamples)
            how = "realised cell counts: weight N_c / n'_c"
        ai_items = [i for i in items if prov.items[i.item_id]["origin"] == "ai_exposed"]
        strata = {"human_only": (estimators.precision(_reweighted(reference), t) if reference and len(reference) < len(items)
                                 else estimators.precision(reference, t) if reference else None),
                  "ai_exposed": estimators.precision(_reweighted(ai_items), t) if ai_items else None}
        lower = every["precision_bootstrap"]["ci_95"][0] if every["precision_bootstrap"]["ci_95"] else None
        base = decision.decide_series(integrity_ok=prov.ok, non_ambiguous_members=every["precision"]["non_ambiguous"],
                                      precision=every["precision"]["precision"], lower_bound=lower,
                                      pooled_recall=every["pooled_recall"], capture_recall=every["capture_recall"])
        guard = decision.consistency_guard(
            ai_precision=strata["ai_exposed"]["precision"] if strata["ai_exposed"] else None,
            reference_precision=ref["precision"]["precision"] if ref else None, ai_exposed_items=len(ai_items),
            reference_refusal=refusal or ([] if reference else ["there are no human-only reference labels"]))
        combined = decision.combine(base, guard)
        combined["evidence_basis"] = {"labels": len(items), "human_only": len(reference), "ai_exposed": len(ai_items),
                                      "statement": "the decision uses ALL labels; AI-exposed labels are disclosed by origin "
                                                   "and are NOT independent ground truth; the human-only items are the "
                                                   "independent reference"}
        results[t] = {
            **every, "scope": "all_labelled",
            "scope_note": "the D12(c) decision scope: includes AI-exposed labels (not independent), gated by the consistency guard",
            "decision": combined,
            "precision_by_label_origin": {"strata": strata,
                                          "note": "both strata use realised-cell reweighting (N_c / n'_c) when the "
                                                  "human-only items are a subset; precision only; recall is not computed "
                                                  "per stratum"},
            "independent_reference": _independent_reference(ref, len(reference), integrity_ok=prov.ok, refusal=refusal,
                                                            reweighting=how)}
    basis = Counter(i.label_basis for i in items)
    out = {
        "computed_at_utc": _now(), "freeze_record_sha256": hashlib.sha256(freeze_path(p).read_bytes()).hexdigest(),
        "working_sha256": rec["working_sha256"], "sealed_key_sha256_matches_build_record": True, "items": len(items),
        "label_basis_counts": dict(sorted(basis.items())),
        "independence": ("AI-based labels are present and are NOT independent human labels"
                         if any(b in AI_BASES for b in basis) else "all labels are human labels made without AI suggestions"),
        "agreement": "not computed: human-versus-AI agreement belongs to M3, which is not selected; independence is reported by label origin",
        "company_notice": estimators.company_stats(items), "themes": results,
        "bootstrap": {"resamples": n_resamples, "seed": estimators.BOOTSTRAP_SEED, "unit": "batch",
                      "generator": "random.Random (not numpy default_rng: package is stdlib-only)",
                      "note": "B2-I names numpy default_rng(42); a matching seed does not give the same resamples "
                              "across generators; changing the generator is a methodology decision"},
        "provenance": prov.summary(), "evaluation_fingerprint_sha256": current_fp["combined_sha256"],
        "criteria_status": decision.CRITERIA_STATUS, "authoritative": decision.criteria_authoritative(),
        "approvals_unresolved": decision.pending_approvals(),
        "evaluation_modes": {t: r["independent_reference"]["evaluation_mode"] for t, r in results.items()},
        "reference_items": len(reference), "label_origin_counts": prov.counts["by_origin"],
        "annotator_near_dup_references": estimators.near_dup_count(items),
        "status": ("aggregates only; the criteria are approved (B2-I section 4.7, D8) and the outcomes authorize nothing"
                   if decision.criteria_authoritative() else
                   "aggregates only; the criteria are not approved or changed since approval: nothing here is authoritative"),
    }
    atomic_write(target, json.dumps(out, indent=1, sort_keys=True, default=str).encode("utf-8"))
    os.chmod(target, 0o444)
    return out
