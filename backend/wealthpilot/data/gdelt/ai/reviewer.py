"""Human review of AI suggestions: the validated recording core and a thin interactive layer.

Every record says whether the AI was **seen** before the human's label was saved, and what the human did with it:

| action | label_origin | AI seen | meaning |
| --- | --- | --- | --- |
| accept | accepted_ai | yes | the human checked the suggestion and accepted it unchanged |
| edit | edited_ai | yes | the human changed some fields (reason code required) |
| reject | rejected_ai_after_seeing | yes | the human labelled from scratch after seeing it (reason code required) |
| uncertain | human_uncertain | yes | the human marks the item uncertain (at least one theme A; note required) |
| insufficient_evidence | human_insufficient_evidence | yes | the supplied headline context is not enough (note required) |
| no_suggestion | human_no_suggestion | no | no valid suggestion existed, so the human labelled unaided |
| blind | human_blind | no | the item is in the blind subset: labelled before any suggestion is shown |

An AI-seen label is **never** described as an independent human label. Nothing here is saved automatically, and a
suggestion is never turned into a human label without an explicit action by a named reviewer. A repeat review of an
item is a correction: it needs a reason, supersedes the earlier record, and leaves it in the history.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.ai import REVIEW_SCHEMA
from wealthpilot.data.gdelt.ai.schema import POL_FIELDS, REL_FIELDS, SourceItem
from wealthpilot.data.gdelt.ai.store import AuditLog, Layout, ReviewStore, SuggestionStore, utc
from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.labeller import Back, Labeller, Quit, Skip, safe_text
from wealthpilot.data.gdelt.annotate import Paths

CONTENT = (*REL_FIELDS, "amb_code", "company_notice", *POL_FIELDS)
ACTIONS = ("accept", "edit", "reject", "uncertain", "insufficient_evidence", "no_suggestion", "blind")
ORIGIN = {"accept": "accepted_ai", "edit": "edited_ai", "reject": "rejected_ai_after_seeing",
          "uncertain": "human_uncertain", "insufficient_evidence": "human_insufficient_evidence",
          "no_suggestion": "human_no_suggestion", "blind": "human_blind"}
AI_SEEN = {"accept", "edit", "reject", "uncertain", "insufficient_evidence"}
REASON_CODES = ("title_misread", "url_context", "rubric_boundary", "other")
LONG_REVIEW_SECONDS = 1800
NEAR_DUP_NONE = ""                      # the representation of "no duplicate": an empty string, as in the human dataset
_ITEM_ID_RE = re.compile(r"^D\d{4}$")


class ReviewError(GdeltToolError):
    code = "ai_review_error"


def _near_dup_reference(labels: dict[str, str] | None, item_id: str) -> str:
    """The reviewer's "same story as item" answer. Empty means no duplicate. A malformed value is an error: it is never
    dropped. Whether the ID exists, and that it is not this item, is checked by the shared rubric validator."""
    raw = (labels or {}).get("near_dup_of", NEAR_DUP_NONE)
    if not isinstance(raw, str):
        raise ReviewError("near_dup_of must be text")
    ref = raw.strip()
    if ref and not _ITEM_ID_RE.match(ref):
        raise ReviewError(f"near_dup_of must be an item ID such as D0001, or empty for none (got {ref!r})")
    return ref


def record_review(layout: Layout, *, items_by_id: dict[str, SourceItem], protocol_id: str, experiment_id: str,
                  blind_ids: frozenset[str], item_id: str, action: str, labels: dict[str, str] | None = None,
                  excluded_ids: frozenset[str] = frozenset(), reviewer_id: str, reason_code: str | None = None, reason_note: str = "", correction_reason: str = "",
                  shown_at: datetime | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Validate one review action and append it. Raises ``ReviewError`` (nothing written) on any problem."""
    now = now or datetime.now(timezone.utc)
    if action not in ACTIONS:
        raise ReviewError(f"unknown action {action!r}")
    item = items_by_id.get(item_id)
    if item is None:
        raise ReviewError(f"unknown item {item_id}")
    if not reviewer_id or "@" in reviewer_id or len(reviewer_id) > 20:
        raise ReviewError("reviewer_id must be short initials, never an email")
    store, reviews = SuggestionStore(layout), ReviewStore(layout)
    prior = reviews.current().get(item_id)
    if prior is not None and not correction_reason.strip():
        raise ReviewError(f"{item_id} is already reviewed; changing it is a correction and needs a correction_reason")
    term = store.terminal().get(item_id)
    suggestion = term if term and term.get("terminal_status") == "valid" else None
    blind = item_id in blind_ids
    if item_id in excluded_ids and (term is not None or action in AI_SEEN):
        raise ReviewError(f"{item_id} is excluded from provider submission: it can have no AI suggestion, so an AI-seen "
                          "action or a stored suggestion is refused")
    if blind and action != "blind":
        raise ReviewError(f"{item_id} is in the blind subset: label it blind, before any suggestion is shown")
    if not blind and action == "blind":
        raise ReviewError(f"{item_id} is not in the blind subset")
    if action in AI_SEEN and suggestion is None:
        raise ReviewError(f"{item_id} has no valid suggestion to review; use no_suggestion")
    if action == "no_suggestion" and suggestion is not None:
        raise ReviewError(f"{item_id} has a valid suggestion, so a label made without it would not be 'no suggestion'")

    near_dup = _near_dup_reference(labels, item_id)
    if action == "accept":
        if set(labels or {}) - {"near_dup_of", "note"}:
            raise ReviewError("accept takes no labels: the suggestion is accepted exactly as it is "
                              "(only near_dup_of and note may accompany it)")
        content = {k: suggestion["parsed"][k] for k in CONTENT}
    else:
        if not labels:
            raise ReviewError(f"{action} needs the reviewer's labels")
        unknown = set(labels) - set(CONTENT) - {"note", "near_dup_of"}
        if unknown:
            raise ReviewError(f"unexpected label fields: {sorted(unknown)}")
        content = {k: (labels.get(k) or "").strip() for k in CONTENT}
    v = {c: "" for c in annotate.LABEL_COLUMNS}
    v.update(content)
    v["near_dup_of"] = near_dup
    errs = annotate.content_errors(v, item_id=item_id, all_ids=set(items_by_id))
    if errs:
        raise ReviewError("; ".join(errs))
    changed = sorted(k for k in CONTENT if suggestion is not None and content[k] != suggestion["parsed"][k])
    if action in ("edit", "reject"):
        if not changed:
            raise ReviewError("the labels are identical to the suggestion: use accept")
        if reason_code not in REASON_CODES:
            raise ReviewError(f"a reason code is required: {', '.join(REASON_CODES)}")
        if reason_code == "other" and not reason_note.strip():
            raise ReviewError("reason code 'other' needs an explanation in reason_note")
    if action in ("uncertain", "insufficient_evidence"):
        if "A" not in {content[k] for k in REL_FIELDS}:
            raise ReviewError(f"{action} needs at least one theme labelled A, with its ambiguity code")
        if not reason_note.strip():
            raise ReviewError(f"{action} needs a note saying why")
    seconds = max(0.0, (now - shown_at).total_seconds()) if shown_at else None
    insufficient = ("Y" if action == "insufficient_evidence"
                    else "Y" if action == "accept" and suggestion["parsed"]["insufficient_evidence"] else "N")
    record = {
        "schema": REVIEW_SCHEMA, "experiment_id": experiment_id, "protocol_id": protocol_id, "item_id": item_id,
        "action": action, "label_origin": ORIGIN[action], "ai_exposure": "seen" if action in AI_SEEN else "none",
        "labels": {**content, "near_dup_of": near_dup, "note": str((labels or {}).get("note") or "").strip()},
        "insufficient_evidence": insufficient, "changed_fields": changed,
        # the suggestion SHOWN to the reviewer (B2-T): a blind label cites none, even though a hidden suggestion may exist
        "suggestion_ref": suggestion["record_sha256"] if suggestion is not None and action in AI_SEEN else None,
        "edit_reason_code": reason_code if action in ("edit", "reject") else None,
        "reason_note": reason_note.strip(), "reviewer_id": reviewer_id, "annotator_type": "human",
        "reviewed_at_utc": utc(now), "shown_at_utc": utc(shown_at) if shown_at else None,
        "review_seconds": seconds, "long_gap_flag": bool(seconds is not None and seconds > LONG_REVIEW_SECONDS),
        "historical_overlap": item.historical_overlap,
        "supersedes": prior["record_sha256"] if prior else None, "correction_reason": correction_reason.strip(),
    }
    saved = reviews.append(record)
    AuditLog(layout).emit("review_saved", now=now, item_id=item_id, status=action, sha256=saved["record_sha256"])
    return saved


# ---------------------------------------------------------------- interactive layer

SUGGESTION_BANNER = "AI-GENERATED SUGGESTION (provisional; not a human judgement; self-reported uncertainty is not a probability)"

class AiReviewer:
    """Review items one at a time. Reuses the human labeller's prompts for any label entry."""

    def __init__(self, layout: Layout, items: list[SourceItem], *, protocol_id: str, experiment_id: str,
                 blind_ids: frozenset[str], excluded_ids: frozenset[str] = frozenset(),
                 input_fn: Callable[[str], str] | None = None,
                 output_fn: Callable[[str], None] = print,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.layout, self.items, self.by_id = layout, items, {i.item_id: i for i in items}
        self.protocol_id, self.experiment_id, self.blind_ids = protocol_id, experiment_id, blind_ids
        self.excluded_ids = excluded_ids
        self.lab = Labeller(Paths(layout.root), input_fn=input_fn, output_fn=output_fn, clock=clock)
        self.lab.ids = set(self.by_id)
        self.say, self.clock = output_fn, clock

    def _show(self, item: SourceItem, suggestion: dict[str, Any] | None, index: int, total: int) -> None:
        self.say("")
        self.say(f"=== {item.item_id}  ({index} of {total}) ===")
        for k in ("batch_date_utc", "source_domain", "url", "title"):
            self.say(f"  {k:<15} {safe_text(item.fields[k])}")
        if suggestion is None:
            return
        p = suggestion["parsed"]
        self.say(f"  --- {SUGGESTION_BANNER} ---")
        self.say("  " + ", ".join(f"{k}={p[k] or '-'}" for k in (*REL_FIELDS, "amb_code", "company_notice", *POL_FIELDS)))
        self.say(f"  insufficient_evidence={p['insufficient_evidence']}; self-reported uncertainty={p['uncertainty']}")
        for ex in p["evidence_excerpts"]:
            self.say(f"  evidence ({ex['field']}): {safe_text(ex['excerpt'])}")
        if p["note"]:
            self.say(f"  AI note: {safe_text(p['note'])}")
        if suggestion["validation"]["flags"]:
            self.say(f"  flags: {', '.join(suggestion['validation']['flags'])}")

    def _answers(self, source: dict[str, str] | None) -> dict[str, str]:
        """Starting answers: the suggestion's content (for an edit) or nothing (the reviewer answers everything)."""
        if not source:
            return {}
        return {**{k: source[k] for k in CONTENT}, "near_dup_of": NEAR_DUP_NONE, "note": ""}

    def _enter(self, item: SourceItem, start: dict[str, str] | None) -> dict[str, str]:
        row = {"item_id": item.item_id, "overlap_subset": "Y" if item.historical_overlap else "N"}
        a = self._answers(start)
        self.lab._prune(a)
        self.lab.fill(a, row)
        self.lab.review(a, row)
        return {k: a.get(k, "") for k in (*CONTENT, "near_dup_of", "note")}

    def review_item(self, item: SourceItem, index: int, total: int) -> bool:
        term = SuggestionStore(self.layout).terminal().get(item.item_id)
        suggestion = term if term and term.get("terminal_status") == "valid" and item.item_id not in self.excluded_ids else None
        blind = item.item_id in self.blind_ids
        shown = self.clock()
        self._show(item, None if blind else suggestion, index, total)
        common = dict(layout=self.layout, items_by_id=self.by_id, protocol_id=self.protocol_id,
                      experiment_id=self.experiment_id, blind_ids=self.blind_ids, item_id=item.item_id,
                      excluded_ids=self.excluded_ids, reviewer_id=self.lab.initials, shown_at=shown)
        if blind or suggestion is None:
            self.say("  No AI suggestion is shown for this item." if blind else "  No valid AI suggestion exists for this item.")
            labels = self._enter(item, None)
            record_review(**common, action="blind" if blind else "no_suggestion", labels=labels, now=self.clock())
            self.say(f"  Saved {item.item_id} ({'blind' if blind else 'no suggestion'}).")
            return True
        while True:
            try:
                choice = self.lab.ask("  [Enter]=accept  d=accept+same story as another item  e=edit  r=reject  u=uncertain  "
                                      "i=insufficient  s=skip  q=quit  ?=help: ",
                                      {"", "D", "E", "R", "U", "I"}, optional=True)
            except Back:
                self.say("  There is nothing to go back to here; choose an action.")
                continue
            try:
                if choice == "":
                    record_review(**common, action="accept", now=self.clock())
                elif choice == "D":
                    dup = self.lab.ask("  Same story as item (an item ID): ", self.lab.ids - {item.item_id})
                    record_review(**common, action="accept", labels={"near_dup_of": dup}, now=self.clock())
                elif choice == "E":
                    labels = self._enter(item, suggestion["parsed"])
                    code, note = self._reason(required=True)
                    record_review(**common, action="edit", labels=labels, reason_code=code, reason_note=note, now=self.clock())
                elif choice == "R":
                    labels = self._enter(item, None)
                    code, note = self._reason(required=True)
                    record_review(**common, action="reject", labels=labels, reason_code=code, reason_note=note, now=self.clock())
                else:
                    action = "uncertain" if choice == "U" else "insufficient_evidence"
                    labels = self._enter(item, None)
                    note = self.lab.ask("  Why? (required): ", upper=False)
                    record_review(**common, action=action, labels=labels, reason_note=note, now=self.clock())
            except ReviewError as exc:
                self.say(f"  Not saved: {exc.reason}")
                continue
            self.say(f"  Saved {item.item_id}.")
            return True

    def _reason(self, *, required: bool = True) -> tuple[str, str]:
        code = self.lab.ask(f"  Reason code [{'/'.join(REASON_CODES)}]: ", {c.upper() for c in REASON_CODES}).lower()
        note = self.lab.ask("  Explanation (required for 'other'): ", optional=(code != "other"), upper=False)
        return code, note

    def run(self, queue_rows: list[dict[str, Any]]) -> dict[str, Any]:
        self.say(f"Items to review now: {len(queue_rows)}. Type ? for help, q to quit.")
        saved = skipped = 0
        try:
            if queue_rows:
                self.lab.ask_initials()
            for n, row in enumerate(queue_rows, start=1):
                try:
                    saved += bool(self.review_item(self.by_id[row["item_id"]], n, len(queue_rows)))
                except Skip:
                    skipped += 1
                    self.say("  Skipped; it stays unreviewed.")
        except Quit:
            self.say("Stopped. Everything you saved is kept; run the same command to resume.")
            return {"saved": saved, "skipped": skipped, "stopped_early": True}
        return {"saved": saved, "skipped": skipped, "stopped_early": False}
