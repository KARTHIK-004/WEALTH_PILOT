"""Review queue, progress and descriptive quality control.

**Every item is reviewed by a human.** There is no automatic acceptance policy; the queue only decides *order*, using
plain rules. A model's self-reported uncertainty is shown as a hint and is never treated as a calibrated probability.
Quality-control figures are descriptive. They are not accuracy: there is no reference label in this module.
"""

from __future__ import annotations

import csv
import io
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Any

from wealthpilot.data.gdelt.ai.schema import SourceItem
from wealthpilot.data.gdelt.ai.store import Layout, ReviewStore, SuggestionStore
from wealthpilot.data.gdelt.output import atomic_write

TIERS = {-1: "blind_label_first", 0: "no_valid_suggestion", 1: "needs_attention", 2: "check_closely", 3: "routine"}
ATTENTION_FLAGS = {"ambiguous", "insufficient_evidence", "company_unclear_with_r", "short_or_empty_title"}
CLOSER_FLAGS = {"multi_theme_relevant", "high_uncertainty_self_reported"}


@dataclass(frozen=True)
class QueuePolicy:
    """Which tiers to include and how many items to list. It changes the order and size of the list only."""

    tiers: tuple[int, ...] = (-1, 0, 1, 2, 3)
    limit: int | None = None
    include_reviewed: bool = False


def classify(item: SourceItem, terminal: dict[str, Any] | None, blind: bool,
             excluded: bool = False) -> tuple[int, tuple[str, ...]]:
    if blind:
        return -1, ("blind_subset",)
    if excluded:
        return 0, ("excluded_from_provider",)
    if not item.sendable:
        return 0, ("invalid_input",)
    if terminal is None:
        return 0, ("suggestion_not_generated",)
    status = terminal.get("terminal_status")
    if status == "failed":
        return 0, ("provider_failed",)
    if status != "valid":
        return 0, ("invalid_output",)
    flags = set(terminal["validation"]["flags"])
    reasons = sorted(flags & ATTENTION_FLAGS)
    if reasons:
        return 1, tuple(reasons)
    reasons = sorted(flags & CLOSER_FLAGS)
    if item.mech_dup != "ORIGINAL":
        reasons.append("duplicate_context")
    if reasons:
        return 2, tuple(reasons)
    return 3, ("routine",)


def build_queue(items: list[SourceItem], layout: Layout, blind_ids: frozenset[str],
                policy: QueuePolicy = QueuePolicy(), excluded_ids: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    terminal = SuggestionStore(layout).terminal()
    reviewed = set(ReviewStore(layout).current())
    rows = []
    for it in items:
        tier, reasons = classify(it, terminal.get(it.item_id), it.item_id in blind_ids, it.item_id in excluded_ids)
        if tier not in policy.tiers or (it.item_id in reviewed and not policy.include_reviewed):
            continue
        rows.append({"item_id": it.item_id, "tier": tier, "tier_name": TIERS[tier], "reasons": ";".join(reasons),
                     "historical_overlap": "Y" if it.historical_overlap else "N",
                     "reviewed": "Y" if it.item_id in reviewed else "N"})
    rows.sort(key=lambda r: (r["tier"], r["item_id"]))
    return rows[: policy.limit] if policy.limit else rows


def write_queue_csv(layout: Layout, rows: list[dict[str, Any]]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["item_id", "tier", "tier_name", "reasons", "historical_overlap", "reviewed"],
                       lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    atomic_write(layout.queue, buf.getvalue().encode("utf-8"))


def progress(items: list[SourceItem], layout: Layout, blind_ids: frozenset[str],
             excluded_ids: frozenset[str] = frozenset()) -> dict[str, Any]:
    terminal = SuggestionStore(layout).terminal()
    reviews = ReviewStore(layout).current()
    sendable = [i for i in items if i.sendable and i.item_id not in excluded_ids]
    status = Counter(terminal[i.item_id].get("terminal_status") if i.item_id in terminal else "not_generated"
                     for i in sendable)
    unreviewed = [i for i in items if i.item_id not in reviews]
    tiers = Counter(TIERS[classify(i, terminal.get(i.item_id), i.item_id in blind_ids, i.item_id in excluded_ids)[0]]
                    for i in unreviewed)
    if any(i.item_id not in terminal and i.item_id not in blind_ids for i in sendable) and not reviews:
        nxt = ("generate suggestions: BLOCKED until approval gates A-D, a provider adapter and the build lock are in place; "
               "or label items without AI")
    elif unreviewed:
        nxt = f"review {len(unreviewed)} items (queue order: {dict(tiers)})"
    else:
        nxt = "export the dataset (all items reviewed)"
    return {"items": len(items), "sendable": len(sendable), "never_sent": len(items) - len(sendable),
            "excluded_from_provider": len(excluded_ids),
            "suggestions": dict(status), "reviewed": len(reviews), "unreviewed": len(unreviewed),
            "unreviewed_by_tier": dict(tiers), "by_label_origin": dict(Counter(r["label_origin"] for r in reviews.values())),
            "by_ai_exposure": dict(Counter(r["ai_exposure"] for r in reviews.values())), "next_action": nxt}


def qc_report(items: list[SourceItem], layout: Layout) -> dict[str, Any]:
    store, reviews = SuggestionStore(layout), ReviewStore(layout).current()
    recs = store.records()
    term = store.terminal()
    valid = [r for r in term.values() if r.get("terminal_status") == "valid"]
    errors = Counter()
    for r in recs:
        for e in (r.get("validation") or {}).get("errors", []):
            errors[e.split(":")[0].split(" (")[0][:60]] += 1
    dist = {k: dict(Counter(r["parsed"][k] for r in valid)) for k in ("rel_equity", "rel_rates", "rel_gold", "company_notice")}
    flags = Counter(f for r in valid for f in r["validation"]["flags"])
    seconds = [r["review_seconds"] for r in reviews.values() if r.get("review_seconds") is not None]
    origin = Counter(r["label_origin"] for r in reviews.values())
    changed = Counter(f for r in reviews.values() for f in r.get("changed_fields", []))
    n_seen = sum(1 for r in reviews.values() if r["ai_exposure"] == "seen")
    return {
        "note": "DESCRIPTIVE ONLY. These are rates of format validity and of human edits, not accuracy: no reference "
                "label is used here, and model self-reported uncertainty is not a probability.",
        "attempts": len(recs), "terminal": dict(Counter(r.get("terminal_status") for r in term.values())),
        "validation_error_kinds": dict(errors), "valid_suggestion_distribution": dist, "suggestion_flags": dict(flags),
        "reviews": len(reviews), "by_label_origin": dict(origin),
        "acceptance_rate_among_ai_seen": (origin["accepted_ai"] / n_seen) if n_seen else None,
        "fields_changed_by_reviewers": dict(changed),
        "review_seconds_median": statistics.median(seconds) if seconds else None,
        "review_seconds_note": "a coarse effort proxy: interruptions inflate it",
        "historical_overlap_items_ai_exposed": sum(1 for i in items if i.historical_overlap and i.item_id in reviews
                                                   and reviews[i.item_id]["ai_exposure"] == "seen"),
    }
