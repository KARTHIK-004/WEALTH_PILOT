"""Read-only bridge from the B2-T suggestion store to the existing annotation validator (B2-U9). Offline; no key, no provider.

**The incompatibility it resolves.** ``annotate.validate`` accepts an AI-based ``label_basis`` only for an item with a valid
entry in ``ai_suggestions_A.csv``. The B2-T pipeline keeps its suggestions in a hash-chained store
(``suggestions/ai_suggestions_raw_v1.jsonl``) with a derived CSV whose columns are a superset of the legacy ones. The formats
agree; what was missing is a way to say "this suggestion set is the verified one" without creating a legacy file.

**What it does not do.** It writes nothing, creates no legacy file, relaxes no rule and approves nothing. The legacy validator
is unchanged and stays the default; this module only *supplies* an already verified ``AiSuggestions`` to it, and only when the
B2-T chain exists next to the export. If both sources exist, validation refuses (two sources for one item set are ambiguous).

A suggestion counts as valid here only if all of the following hold, otherwise the whole set is rejected (fail closed):
the raw chain verifies; the experiment's snapshot is of the same original file; the verified overlap membership equals the
original's; each terminal ``valid`` record is for a known, non-overlap item, carries the item's current input fingerprint and
passes the same rubric validator as a human label; and the derived CSV, if present, equals what the chain produces.

``labels_for_merge`` turns *verified reviews* into label rows for the existing batch merge. It maps each review origin to a
``label_basis`` only where the mapping is unambiguous and refuses the rest; it never guesses, never overwrites a label and
never creates a review.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.ai import SUGGESTION_SCHEMA
from wealthpilot.data.gdelt.ai.chain import GENESIS, ChainError
from wealthpilot.data.gdelt.ai.schema import SchemaError, load_items
from wealthpilot.data.gdelt.ai.store import Layout, StoreError, SuggestionStore, render_valid_csv, sha_file, verified_overlap
from wealthpilot.data.gdelt.annotate import LABEL_COLUMNS, AiSuggestions, Paths

# review origin -> the working copy's label_basis. Only unambiguous mappings; the rest are refused, not guessed.
BASIS_FOR_ORIGIN = {"human_no_suggestion": "own", "human_blind": "own", "accepted_ai": "accepted_ai",
                    "edited_ai": "corrected_ai", "rejected_ai_after_seeing": "rejected_ai"}
UNMAPPED_ORIGINS = frozenset({"human_uncertain", "human_insufficient_evidence"})   # AI seen; which basis is a protocol decision
CONTENT_KEYS = ("rel_equity", "rel_rates", "rel_gold", "amb_code", "company_notice", "pol_equity", "pol_rates", "pol_gold")


@dataclass(frozen=True)
class Bridge:
    suggestions: AiSuggestions
    records: dict[str, dict[str, Any]] = field(default_factory=dict)      # item_id -> the valid terminal suggestion record
    layout: Layout | None = None
    chain_sha256: str | None = None
    head: str = GENESIS                  # the suggestion chain's current head (record hash), for the F1 comparison


def layout_for_export(export_dir: Path | None) -> Layout | None:
    if export_dir is None or Path(export_dir).name != "export":
        return None
    return Layout(Path(export_dir).parent)


def _fail(layout: Layout, message: str) -> Bridge:
    return Bridge(AiSuggestions(True, frozenset(), (message,)), {}, layout)


def load(p: Paths, export_dir: Path | None) -> Bridge | None:
    """The verified B2-T suggestion set, or ``None`` when no B2-T suggestion chain exists next to the export (the legacy
    source then applies unchanged). Never writes."""
    layout = layout_for_export(export_dir)
    if layout is None:
        return None
    if not layout.suggestions_raw.is_file():
        # F3: a real B2-T experiment folder (it has a snapshot) whose export names a suggestion chain must still have it.
        # Only an experiment that never recorded a suggestion (genesis head) may have no chain; anything else is refused.
        if not layout.snapshot.is_dir():
            return None
        try:
            manifest = json.loads((Path(export_dir) / "EXPORT_MANIFEST.json").read_text(encoding="utf-8"))
            never = manifest["chain_heads"]["suggestions"] == GENESIS
        except (OSError, ValueError, KeyError, TypeError):
            never = False
        if never:
            return None
        return _fail(layout, "the suggestion chain is missing from this experiment folder although its export names one; "
                             "the legacy source is not used as a fallback")
    try:
        items = load_items(p.original)
    except SchemaError as exc:
        return _fail(layout, f"the original annotation file cannot be loaded ({exc.reason})")
    by_id = {i.item_id: i for i in items}
    overlap = {i.item_id for i in items if i.historical_overlap}
    snap = layout.snapshot / "annotation_A.csv"
    if not snap.is_file() or sha_file(snap) != sha_file(p.original):
        return _fail(layout, "the experiment's snapshot is not of this original annotation file")
    try:
        if set(verified_overlap(layout)) != overlap:
            return _fail(layout, "the experiment's verified overlap membership differs from the original's")
        store = SuggestionStore(layout)
        records = store.records()                                  # verifies the hash chain
        terminal = store.terminal()
        derived = render_valid_csv(store)[0]
    except (StoreError, ChainError, OSError, ValueError, KeyError) as exc:
        return _fail(layout, f"the suggestion store cannot be verified ({type(exc).__name__}: {getattr(exc, 'reason', exc)})")
    problems: list[str] = []
    for r in records:
        if r.get("schema") != SUGGESTION_SCHEMA:
            problems.append(f"a record has schema {r.get('schema')!r}, not {SUGGESTION_SCHEMA}")
        elif r.get("item_id") in overlap:
            problems.append(f"{r['item_id']}: a suggestion record exists for an overlap item")
        elif r.get("item_id") not in by_id:
            problems.append(f"{r.get('item_id')}: a suggestion record names an unknown item")
    valid: dict[str, dict[str, Any]] = {}
    for iid, r in sorted(terminal.items()):
        if r.get("terminal_status") != "valid" or iid not in by_id or iid in overlap:
            continue
        parsed = r.get("parsed")
        if not isinstance(parsed, dict) or not (r.get("validation") or {}).get("ok"):
            problems.append(f"{iid}: the valid record has no parsed output or a failed validation")
            continue
        if r.get("input_fingerprint") != by_id[iid].fingerprint:
            problems.append(f"{iid}: the suggestion was made for different input than the original now holds")
            continue
        v = {c: str(parsed.get(c, "") or "").strip() for c in LABEL_COLUMNS}
        errs = annotate.content_errors(v, item_id=iid, all_ids=set(by_id))
        if errs:
            problems.append(f"{iid}: " + "; ".join(errs))
            continue
        valid[iid] = r
    if layout.suggestions_valid.is_file() and layout.suggestions_valid.read_bytes() != derived:
        problems.append("the derived suggestions CSV differs from what the raw chain produces (hand-edited or stale)")
    head = records[-1]["record_sha256"] if records else GENESIS
    if problems:
        return Bridge(AiSuggestions(True, frozenset(), tuple(problems)), {}, layout, sha_file(layout.suggestions_raw), head)
    return Bridge(AiSuggestions(True, frozenset(valid), ()), valid, layout, sha_file(layout.suggestions_raw), head)


def labels_for_merge(p: Paths, export_dir: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    """Label rows for ``annotate merge`` from a VERIFIED export, plus every item refused and why.

    Pure: nothing is written and no label is created that a human review did not already record. Refuses the whole result
    if the bridge or the export does not verify. Items already labelled in the working copy, items whose review origin has
    no unambiguous ``label_basis``, and items absent from the export are listed as refused, never defaulted.
    """
    from wealthpilot.data.gdelt import ai_origin, provenance
    rep = provenance.verify(p)
    ai_origin.attach(rep, export_dir, premerge=True, bridge=load(p, export_dir))
    if not rep.ok:
        return {}, [{"item_id": x["item_id"] or "", "reason": f"{x['kind']}: {x['detail']}"} for x in rep.problems]
    rows = {r["item_id"]: r for r in ai_origin.read_export_rows(export_dir)}
    labels: dict[str, dict[str, str]] = {}
    refused: list[dict[str, str]] = []
    for iid, rec in sorted(rep.items.items()):
        row = rows.get(iid)
        if row is None:
            refused.append({"item_id": iid, "reason": "no review record in the export"})
        elif rec["origin"] != "unlabelled":
            refused.append({"item_id": iid, "reason": "already labelled in the working copy; a change is a correction"})
        elif row["label_origin"] in UNMAPPED_ORIGINS:
            refused.append({"item_id": iid, "reason": f"review origin {row['label_origin']!r} has no approved label_basis "
                                                      "mapping (a protocol decision)"})
        else:
            labels[iid] = {**{k: row[k] for k in CONTENT_KEYS}, "near_dup_of": row["near_dup_of"], "note": row["note"],
                           "annotator_id": row["annotator_id"], "annotator_type": "human",
                           "label_basis": BASIS_FOR_ORIGIN[row["label_origin"]], "labelled_at_utc": row["reviewed_at_utc"]}
    return labels, refused
