"""The threshold decision for one candidate series (B2-I section 4.7), with four distinguishable outcomes.

``PASS``                 every criterion is met on sufficient, valid evidence.
``FAIL``                 valid evidence exists and at least one criterion is not met.
``INSUFFICIENT_EVIDENCE``  a needed number is missing, undefined or below the reporting floor, so the criteria cannot be
                         judged. A missing metric never passes.
``INVALID_EVALUATION``   the data, its provenance or a metric is invalid. It is never a pass and never a fail.

**The criteria were approved (D8, project owner, 2026-10-19)** exactly as pre-registered in B2-I section 4.7 and the decision
document: precision at least 0.70, bootstrap lower bound at least 0.60, pooled recall at least 0.90, and the reporting floor of
100 non-ambiguous members; plus the approved D12.1 guard and D3 minimum (``GUARD``). The freeze is explicit and fails closed:
``criteria_authoritative`` is true only if the status is ``APPROVED``, a reference is recorded **and** the hash of the criteria
and guard equals ``APPROVED_CRITERIA_SHA256``. Changing any threshold afterwards, without a new approval, makes every decision
non-authoritative again. Nothing here can approve anything from data, a file, an environment variable or a command-line option.
An authoritative outcome still authorizes no execution, deployment, acquisition or provider use.

The gate metric is **pooled recall** (weighted R among series members over weighted R in cells C1-C6). Capture recall and
its rule-of-three bound are passed through for reporting and never decide anything.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from typing import Any

OUTCOMES = ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE", "INVALID_EVALUATION")
CRITERIA = {"precision_min": 0.70, "precision_lower_bound_min": 0.60, "pooled_recall_min": 0.90,
            "reporting_floor_non_ambiguous": 100}
CRITERIA_STATUS = "APPROVED"
CRITERIA_APPROVAL_REFERENCE: str | None = ("B2-U12 D8: project owner approval of 2026-10-19; see the decision log in "
                                           "reports/phaseB2U12_m2_selection_and_plan.md")
# The hash of exactly what was approved (CRITERIA, GUARD and the recall gate). A later change to any of them, without a new
# approval and a new hash here, makes the criteria non-authoritative.
APPROVED_CRITERIA_SHA256: str | None = "1c224cab9a4fb507b5f6cc3a957b1f9a234e5ba7e36a538cec443a2e5bdd4539"
RECALL_GATE = "pooled_recall"                      # D4: the gating recall; capture recall is reported separately
# D12(c) consistency guard and D3 subset minimum (approved 2026-10-19). The tolerance is a PRE-REGISTERED OPERATIONAL THRESHOLD:
# it is 0.10 because B2-I accepts a point precision of 0.70 with a bootstrap lower bound of 0.60 (a 0.10 margin), not because
# it was validated statistically or tuned to data. There is no significance test. A pass does not show equivalence.
GUARD = {"metric": "precision", "direction": "one_directional: ai_exposed minus human_only", "tolerance": 0.10,
         "significance_test": None, "failed_outcome": "INSUFFICIENT_EVIDENCE", "min_reference_members": 30,
         "min_reference_items_per_used_cell": 1, "weights": "realised cell counts, both strata"}


def consistency_guard(*, ai_precision: Any, reference_precision: Any, ai_exposed_items: int,
                      reference_refusal: Sequence[str] = ()) -> dict[str, Any]:
    """The precision-only, one-directional guard (D12.1). Flags only when the AI-exposed precision exceeds the human-only
    precision by MORE than the tolerance (equality passes). ``not_applicable`` when no label is AI-exposed (every label is
    independent); ``not_evaluable`` when the human-only estimate was refused or either precision is undefined, because the
    independent check then cannot be made; both are handled by ``combine``. The gap is never read as proof of cause (labelling
    order and reviewer mode differ between the strata) and a pass is not proof of consistency."""
    base: dict[str, Any] = {"metric": GUARD["metric"], "direction": GUARD["direction"], "tolerance": GUARD["tolerance"],
                            "significance_test": None, "tolerance_status": "pre-registered operational threshold, not a "
                            "statistically validated boundary", "note": "a pass does not establish equivalence; a gap does not "
                            "establish that AI assistance caused it"}
    if ai_exposed_items == 0:
        return {**base, "status": "not_applicable", "gap": None, "reasons": ["no label is AI-exposed"]}
    if reference_refusal:
        return {**base, "status": "not_evaluable", "gap": None, "reasons": ["the human-only estimate was refused: "
                                                                          + "; ".join(reference_refusal)]}
    sa, sr = _number(ai_precision), _number(reference_precision)
    if sa[0] != "ok" or sr[0] != "ok":
        return {**base, "status": "not_evaluable", "gap": None, "reasons": ["a stratum precision is missing or invalid"]}
    gap = sa[1] - sr[1]
    failed = round(gap, 12) > GUARD["tolerance"]          # rounding: 0.80 - 0.70 is exactly 0.10 in decimal, and passes
    return {**base, "status": "failed" if failed else "passed", "gap": gap, "ai_exposed_precision": sa[1],
            "human_only_precision": sr[1],
            "reasons": [f"AI-exposed precision exceeds human-only precision by {gap:.4f}, more than {GUARD['tolerance']}"]
            if failed else []}


def decide_without_independent_evidence(reason: str = "no valid independent human labels exist") -> dict[str, Any]:
    """The outcome when no independent evidence exists: ``INSUFFICIENT_EVIDENCE``, never authoritative, never a pass. No metric
    is read or accepted: model agreement, AI-only suggestions and AI-exposed labels are not independent evidence."""
    return {"outcome": "INSUFFICIENT_EVIDENCE", "authoritative": False, "criteria_status": CRITERIA_STATUS,
            "authorizes_execution_or_deployment": False, "criteria_results": [], "reasons": [reason],
            "statement": "no valid independent labels: nothing about accuracy can be decided or reported as established"}


def combine(base: dict[str, Any], guard: dict[str, Any]) -> dict[str, Any]:
    """D12(c): the primary decision (all labels) stands only if the guard is not failed or not evaluable. A failed or
    not-evaluable guard maps to INSUFFICIENT_EVIDENCE whatever the base outcome, except INVALID_EVALUATION, which stays.
    The base outcome is always kept in the record. Never authoritative; authorizes nothing."""
    out = {**base, "base_outcome": base["outcome"], "consistency_guard": guard}
    if guard["status"] in ("failed", "not_evaluable") and base["outcome"] != "INVALID_EVALUATION":
        out["outcome"] = "INSUFFICIENT_EVIDENCE"
        out["reasons"] = [*base.get("reasons", []), "consistency guard " + guard["status"].replace("_", " ") + ": "
                          + "; ".join(guard["reasons"])]
    return out


def criteria_sha256() -> str:
    """The hash of the criteria, the guard and the recall gate as they are now."""
    body = {"criteria": CRITERIA, "guard": GUARD, "recall_gate": RECALL_GATE}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def pending_approvals() -> list[str]:
    """What this build still records as open, listed in every evaluation so a result is never read as more than it is."""
    out = []
    if not criteria_authoritative():
        out.append("acceptance criteria: not approved, or changed since approval (status, reference or hash)")
    out += ["B2 completion wording (\"filter outcome reached, ingestion pending\"): no recorded approval",
            "provider, model, data handling, retention, gates A to D, the build lock, execution and full-window acquisition: "
            "not approved; an evaluation outcome authorizes none of them"]
    return out


def criteria_authoritative() -> bool:
    return (CRITERIA_STATUS == "APPROVED" and bool(CRITERIA_APPROVAL_REFERENCE)
            and APPROVED_CRITERIA_SHA256 == criteria_sha256())


def _number(value: Any) -> tuple[str, float | None]:
    """('missing'|'invalid'|'ok', value). A fraction must be a real number from 0 to 1."""
    if value is None:
        return "missing", None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        return "invalid", None
    return "ok", float(value)


def _criterion(name: str, state: str, value: float | None, threshold: float, reason: str) -> dict[str, Any]:
    return {"criterion": name, "status": state, "value": value, "threshold": threshold, "reason": reason}


def decide_series(*, integrity_ok: bool, integrity_problems: Sequence[str] = (), non_ambiguous_members: Any,
                  precision: Any, lower_bound: Any, pooled_recall: Any,
                  capture_recall: dict[str, Any] | None = None) -> dict[str, Any]:
    """One series' outcome. ``integrity_ok`` must come from the provenance and dataset checks, never be assumed."""
    c = CRITERIA
    base: dict[str, Any] = {
        "criteria_status": CRITERIA_STATUS, "authoritative": criteria_authoritative(),
        "criteria_approval_reference": CRITERIA_APPROVAL_REFERENCE, "criteria_sha256": criteria_sha256(),
        "criteria": dict(c), "capture_recall_reported_separately": capture_recall,
        "capture_recall_note": "capture recall and its rule-of-three bound are reported only; they never decide the outcome",
        "authorizes_execution_or_deployment": False}
    if not criteria_authoritative():
        base["statement"] = ("computed against criteria that are not approved, or changed since approval: this is not an acceptance decision "
                             "(approval is a separate recorded act by the project owner)")
    if not integrity_ok:
        return {**base, "outcome": "INVALID_EVALUATION", "criteria_results": [],
                "reasons": list(integrity_problems) or ["data integrity or provenance did not verify"]}

    n_state = "missing"
    if isinstance(non_ambiguous_members, int) and not isinstance(non_ambiguous_members, bool) and non_ambiguous_members >= 0:
        n_state = "ok"
    elif non_ambiguous_members is not None:
        n_state = "invalid"
    p_state, p = _number(precision)
    l_state, lb = _number(lower_bound)
    r_state, r = _number(pooled_recall)
    invalid = [name for name, s in (("non_ambiguous_members", n_state), ("precision", p_state),
                                    ("lower_bound", l_state), ("pooled_recall", r_state)) if s == "invalid"]
    if invalid:
        return {**base, "outcome": "INVALID_EVALUATION", "criteria_results": [],
                "reasons": [f"invalid value for: {', '.join(invalid)} (not a finite number in range)"]}

    floor_ok = n_state == "ok" and non_ambiguous_members >= c["reporting_floor_non_ambiguous"]
    floor_reason = (f"only {non_ambiguous_members} non-ambiguous members; the reporting floor is "
                    f"{c['reporting_floor_non_ambiguous']}" if n_state == "ok" else "the number of non-ambiguous members is missing")
    results = []
    for name, state, value, threshold, needs_floor in (
            ("precision", p_state, p, c["precision_min"], True),
            ("bootstrap_lower_bound", l_state, lb, c["precision_lower_bound_min"], True),
            ("pooled_recall", r_state, r, c["pooled_recall_min"], False)):
        if needs_floor and not floor_ok:
            results.append(_criterion(name, "undetermined", value, threshold, floor_reason))
        elif state == "missing":
            results.append(_criterion(name, "undetermined", None, threshold, "the metric is missing or undefined"))
        else:
            met = value >= threshold                                       # exact boundary: equal passes
            results.append(_criterion(name, "met" if met else "not_met", value, threshold,
                                      "meets the threshold" if met else "below the threshold"))
    states = {x["status"] for x in results}
    outcome = "FAIL" if "not_met" in states else "INSUFFICIENT_EVIDENCE" if "undetermined" in states else "PASS"
    return {**base, "outcome": outcome, "criteria_results": results,
            "reasons": [f"{x['criterion']}: {x['reason']}" for x in results if x["status"] != "met"]}
