"""Which D8 metrics can be reported at all, given the evidence that exists (B2-U18). Read-only and key-free.

For every accuracy metric the report records the estimand, the data it needs, whether valid **independent** labels exist,
whether it is computable, whether its uncertainty can be defended, and whether an authoritative decision is permitted. When no
valid independent labels exist the metric is ``unavailable`` and the decision is ``INSUFFICIENT_EVIDENCE``, whatever any model
produced. AI-only suggestions, AI-exposed labels and agreement between models are listed as exploratory or descriptive and are
never counted as independent evidence.

It reads the working copy through the provenance bridge and, optionally, an AI-only store. It never reads the sealed key, never
writes a file and never changes a threshold, a guard or an approval.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import ai_only, decision, provenance
from wealthpilot.data.gdelt.ai.schema import load_items
from wealthpilot.data.gdelt.annotate import Paths

SERIES = ("equity", "rates", "gold")
# metric -> (estimand, data it needs)
METRICS = {
    "precision": ("share of a series' members (stage-D rows, cell-weighted) that are relevant (R), ambiguous excluded",
                  "independent human relevance labels on series members, plus the sealed key's membership and cells at evaluation"),
    "bootstrap_lower_bound": ("2.5th percentile of the batch-clustered bootstrap of precision",
                              "the same labels, with batch identity"),
    "pooled_recall": ("weighted R among a series' members over weighted R across cells C1-C6",
                      "independent labels across C1-C6 (not only members) and the key's cells"),
    "capture_recall": ("weighted R in captured cells over weighted R in all cells, with the rule-of-three bound",
                       "independent labels across C1-C7 and the key's cells"),
    "reporting_floor": ("at least 100 non-ambiguous members labelled per series",
                        "independent labels on at least 100 non-ambiguous members per series"),
    "unique_story_precision": ("precision over unique stories", "independent labels and annotator duplicate links"),
    "per_cell_wilson": ("unweighted Wilson interval of relevance per cell", "independent labels and the key's cells"),
}
STATEMENT = ("Model agreement, AI-only suggestions and AI-exposed labels are not independent evidence. Without valid independent "
             "human labels no accuracy metric is available and no authoritative decision is possible.")


def _metric_rows(status: str, independent: int, reason: str) -> dict[str, Any]:
    rows = {}
    for name, (estimand, data) in METRICS.items():
        rows[name] = {"estimand": estimand, "data_required": data, "independent_labels_available": independent > 0,
                      "computable": False, "uncertainty_defensible": False, "authoritative_decision_permitted": False,
                      "status": status, "limitation": reason}
    return rows


def report(p: Paths, *, ai_only_root: Path | None = None) -> dict[str, Any]:
    """The metric-status report for the review folder ``p`` (and an optional AI-only store). Writes nothing."""
    prov = provenance.verify(p)
    by_origin = dict(prov.counts.get("by_origin", {})) if prov.ok else {}
    independent = by_origin.get("human_only", 0)
    exposed = by_origin.get("ai_exposed", 0)
    ai_section: dict[str, Any] = {"store_supplied": ai_only_root is not None, "records": 0, "role": "exploratory_only",
                                  "independent": False, "statement": ai_only.NON_INDEPENDENT}
    if ai_only_root is not None:
        try:
            items = {i.item_id: i for i in load_items(p.original)}
            records = ai_only.AiOnlyStore(ai_only_root).records(items)
            ai_section.update(ai_only.diagnostics(records))
            ai_section["valid"] = True
        except Exception as exc:                                  # a bad store is reported, never trusted
            ai_section.update({"valid": False, "problem": f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"})
    if not prov.ok:
        status, reason = "invalid_provenance", "provenance did not verify: " + "; ".join(
            f"{x['kind']}: {x['detail']}" for x in prov.problems[:3])
        dec = decision.decide_series(integrity_ok=False, integrity_problems=[reason], non_ambiguous_members=None,
                                     precision=None, lower_bound=None, pooled_recall=None)
        series = {s: dec for s in SERIES}
    elif independent == 0:
        status, reason = "unavailable", "no valid independent human labels exist (human-only labelled items: 0)"
        series = {s: decision.decide_without_independent_evidence(reason) for s in SERIES}
    else:
        status = "requires_frozen_evaluation"
        reason = ("independent labels exist, but a metric is computed only by `annotate freeze` and `annotate evaluate` after "
                  "every item is labelled and the approved checks pass; nothing is estimated here")
        series = {s: None for s in SERIES}
    return {
        "mode": "metric_status", "reads_sealed_key": False, "writes_files": False, "statement": STATEMENT,
        "criteria_status": decision.CRITERIA_STATUS, "criteria_authoritative": decision.criteria_authoritative(),
        "evidence": {"provenance": prov.status, "labelled_items_by_origin": by_origin,
                     "independent_human_only_labelled": independent, "ai_exposed_labelled": exposed,
                     "ai_only": ai_section},
        "overall_status": status, "metrics": _metric_rows(status, independent, reason),
        "descriptive_only": {"label_origin_counts": by_origin,
                             "note": "counts of who labelled what; descriptive, not accuracy"},
        "decision_by_series": series,
    }
