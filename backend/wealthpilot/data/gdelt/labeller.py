"""Interactive human labelling of the overlap items (Part 1 of the B2 annotation workflow).

The project owner answers every label at a prompt, one item at a time. This module never generates,
infers or prefills a label. It fills only the facts of the session:

- ``annotator_id``: the initials typed once;
- ``annotator_type = human``;
- ``label_basis = own``;
- ``labelled_at_utc``: the clock at the moment of saving.

**How an item is answered (B2-U):** answers are kept in one dictionary for the whole item.

- ``<`` goes back one answer without losing the others.
- A review screen lists every answer, lists every problem the existing rubric validator finds (with the
  company-notice rule explained), and lets you change any answer by number or field name.
- Nothing is saved until the review is free of problems and you type ``Y``. A failed save keeps all
  answers and returns to the review screen.

**What it shows:** only the permitted context: item ID, date, source domain, URL, title and the
pipeline's duplicate mark.

**What it never touches:** the sealed key or any AI-suggestion file; it shows no theme, filter or cell
information. It works only on the overlap subset (``overlap_subset = Y``).

**The validator is never bypassed.** The review screen calls the same rubric validator (``annotate.human_only_errors``), and the save goes
through ``annotate.save_item``, which validates again and writes atomically.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from datetime import datetime, timezone

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.annotate import AnnotationError, Paths

RELS = ("rel_equity", "rel_rates", "rel_gold")
POL_OF = {"rel_equity": "pol_equity", "rel_rates": "pol_rates", "rel_gold": "pol_gold"}
THEME_NAME = {"rel_equity": "US equity / Nasdaq", "rel_rates": "US interest rates / bonds", "rel_gold": "Gold"}
FIELD_NAME = {
    "rel_equity": "US equity / Nasdaq relevance", "rel_rates": "US rates / bonds relevance",
    "rel_gold": "Gold relevance", "amb_code": "Primary ambiguity code",
    "pol_equity": "US equity / Nasdaq polarity", "pol_rates": "US rates / bonds polarity",
    "pol_gold": "Gold polarity", "company_notice": "Company or fund notice",
    "near_dup_of": "Same story as item", "note": "Note",
}
ORDER = ("rel_equity", "rel_rates", "rel_gold", "amb_code", "pol_equity", "pol_rates", "pol_gold",
         "company_notice", "near_dup_of", "note")
CONTEXT_FIELDS = ("batch_date_utc", "source_domain", "url", "title", "mech_dup")
COMPANY_RULE = ("Rubric: a company or fund notice (company_notice = Y) is at most RL for every theme, "
                "so Y can not be combined with R.")
HELP = (
    "Commands at any prompt:  s = skip this item | q = quit (the current item is not saved) | "
    "< = go back one answer | ? = this help\n"
    "Relevance: R = the theme's market is a main subject | RL = related or adjacent | I = irrelevant | "
    "A = ambiguous (then ONE primary code A1-A6 or A9; describe other ambiguity in the note)\n"
    "Polarity, only for an R theme: POS NEG NEU MIX UNC (UNC = the direction cannot be determined)\n"
    "company_notice: Y = a company- or fund-level notice (holdings disclosure, analyst rating or price target, "
    "insider trade, dividend declaration, one company's earnings) | N = not such a notice | U = unclear\n"
    + COMPANY_RULE + "\n"
    "Full rules: reports/phaseB2Q_annotation_quick_reference.md and the B2-R/B2-S decisions"
)


class Quit(Exception):
    pass


class Skip(Exception):
    pass


class Back(Exception):
    pass


def safe_text(value: str) -> str:
    """Strip control and format characters so an untrusted title cannot drive the terminal."""
    return "".join(ch if unicodedata.category(ch)[0] != "C" else " " for ch in value or "")


def applicable(a: dict[str, str]) -> list[str]:
    """The fields that currently apply, in asking order, given the answers so far."""
    fields = list(RELS)
    if "A" in (a.get(r) for r in RELS):
        fields.append("amb_code")
    fields += [POL_OF[r] for r in RELS if a.get(r) == "R"]
    return fields + ["company_notice", "near_dup_of", "note"]


class Labeller:
    def __init__(self, paths: Paths, *, input_fn: Callable[[str], str] | None = None,
                 output_fn: Callable[[str], None] = print,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.p = paths
        self.ask_raw = input_fn or (lambda prompt: input(prompt))   # resolved at call time
        self.say = output_fn
        self.clock = clock
        self.initials = ""
        self.ids: set[str] = set()

    # ------------------------------------------------------------ prompting
    def ask(self, prompt: str, allowed: set[str] | None = None, *, optional: bool = False,
            upper: bool = True, default: str | None = None) -> str:
        shown = prompt
        if default:
            shown = prompt.rstrip(": ") + f" (Enter keeps {default}): "
        while True:
            try:
                raw = self.ask_raw(shown)
            except (EOFError, KeyboardInterrupt):
                raise Quit() from None
            value = (raw or "").strip()
            key = value.lower()
            if key == "q":
                raise Quit()
            if key == "s":
                raise Skip()
            if key == "<":
                raise Back()
            if key == "?":
                self.say(HELP)
                continue
            if upper:
                value = value.upper()
            if not value:
                if default:
                    return default
                if optional:
                    return ""
                self.say("  A value is required (or s = skip, q = quit, < = back).")
                continue
            if value == "-" and optional and default:
                return ""
            if allowed is not None and value not in allowed:
                self.say(f"  Not allowed. Choose one of: {', '.join(sorted(allowed))}")
                continue
            return value

    def ask_initials(self) -> None:
        while not self.initials:
            try:
                raw = (self.ask_raw("Your initials for this session (no email): ") or "").strip()
            except (EOFError, KeyboardInterrupt):
                raise Quit() from None
            if raw.lower() == "q":
                raise Quit()
            if not raw or "@" in raw or len(raw) > 20:
                self.say("  Please type short initials, not an email.")
                continue
            self.initials = raw

    # ------------------------------------------------------------ display
    def show(self, row: dict[str, str], index: int, total: int) -> None:
        self.say("")
        self.say(f"=== {row['item_id']}  ({index} of {total} overlap items) ===")
        for f in CONTEXT_FIELDS:
            self.say(f"  {f:<15} {safe_text(row.get(f, ''))}")
        self.say("  (" + COMPANY_RULE + " Type ? for definitions, < to go back.)")

    def _company_conflict(self, a: dict[str, str]) -> list[str]:
        """Fields currently R while company_notice is Y (a rubric conflict the validator would refuse)."""
        if a.get("company_notice") != "Y":
            return []
        return [r for r in RELS if a.get(r) == "R"]

    def _explain_conflict(self, a: dict[str, str]) -> None:
        names = ", ".join(f"{THEME_NAME[r]} (R)" for r in self._company_conflict(a))
        self.say(f"  Conflict: company_notice is Y, but these themes are R: {names}.")
        self.say("  " + COMPANY_RULE)
        self.say("  Reconsider those themes, or change the company notice. Nothing is changed for you.")

    def _prune(self, a: dict[str, str]) -> None:
        """Drop answers to fields that no longer apply (for example polarity of a theme no longer R)."""
        keep = set(applicable(a))
        for key in [k for k in a if k not in keep]:
            if a[key]:
                self.say(f"  {FIELD_NAME[key]} no longer applies and was cleared.")
            del a[key]

    # ------------------------------------------------------------ asking one field
    def _ask_field(self, a: dict[str, str], field: str, row: dict[str, str], *, keep_default: bool) -> None:
        default = a.get(field) if keep_default and field in a else None
        if field in RELS:
            value = self.ask(f"  {FIELD_NAME[field]} [R/RL/I/A]: ", annotate.REL_VALUES, default=default)
        elif field == "amb_code":
            allowed = set(annotate.AMB_CODES)
            if [r for r in RELS if a.get(r) == "A"] == ["rel_gold"]:
                allowed.discard("A2")
                self.say("  (A2, country unclear, applies to the US themes only, so it is not offered for gold alone.)")
            value = self.ask("  Primary ambiguity code [A1-A6, A9] (describe other ambiguity in the note): ",
                             allowed, default=default)
        elif field.startswith("pol_"):
            value = self.ask(f"  {FIELD_NAME[field]} [POS/NEG/NEU/MIX/UNC]: ", annotate.POL_VALUES, default=default)
        elif field == "company_notice":
            value = self.ask("  Company or fund notice [Y/N/U] (Y means no theme may be R): ",
                             annotate.COMPANY_VALUES, default=default)
        elif field == "near_dup_of":
            value = self.ask("  Same story as item (an item ID, or Enter for none): ",
                             self.ids - {row["item_id"]}, optional=True, default=default)
        else:
            need = a.get("amb_code") == "A9"
            value = self.ask("  Note" + (" (required for A9)" if need else " (optional)") + ": ",
                             optional=not need, upper=False, default=default)
        a[field] = value
        if field in RELS:
            self._prune(a)
            if value == "R" and a.get("company_notice") == "Y":
                self._explain_conflict(a)
        elif field == "company_notice" and value == "Y" and self._company_conflict(a):
            self._reconsider(a)

    def _reconsider(self, a: dict[str, str]) -> None:
        """company_notice = Y with R themes: ask the user to reconsider each R. Enter keeps R; nothing is
        changed silently."""
        self._explain_conflict(a)
        try:
            for rel in self._company_conflict(a):
                new = self.ask(f"  Reconsider {THEME_NAME[rel]} relevance (now R) [R/RL/I/A]: ",
                               annotate.REL_VALUES, default="R")
                if new != "R":
                    a[rel] = new
                    self._prune(a)
        except Back:
            pass
        if self._company_conflict(a):
            self.say("  Still conflicting. At the review screen, change the company notice or those themes.")

    def _revisit_field(self, a: dict[str, str], field: str, row: dict[str, str]) -> None:
        """Re-ask one answered field with its current answer as the default. ``<`` steps further back."""
        while True:
            try:
                self._ask_field(a, field, row, keep_default=True)
                return
            except Back:
                order = applicable(a)
                earlier = [f for f in order[:order.index(field)] if f in a] if field in order else []
                if not earlier:
                    self.say("  That is the first question.")
                    continue
                field = earlier[-1]

    def fill(self, a: dict[str, str], row: dict[str, str]) -> None:
        """Ask every applicable field that has no answer yet. Existing answers are never re-asked."""
        while True:
            nxt = next((f for f in applicable(a) if f not in a), None)
            if nxt is None:
                return
            try:
                self._ask_field(a, nxt, row, keep_default=False)
            except Back:
                answered = [f for f in applicable(a) if f in a]
                if not answered:
                    self.say("  That is the first question.")
                    continue
                self._revisit_field(a, answered[-1], row)

    # ------------------------------------------------------------ review and save
    def _labels(self, a: dict[str, str]) -> dict[str, str]:
        labels = {c: "" for c in annotate.LABEL_COLUMNS}
        labels.update({k: v for k, v in a.items() if k in labels})
        labels.update(annotator_id=self.initials, annotator_type="human", label_basis="own",
                      labelled_at_utc=self.clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return labels

    def _problems(self, a: dict[str, str], row: dict[str, str]) -> list[str]:
        """Problems the existing validator reports for these answers (the company rule explained first)."""
        errs = annotate.human_only_errors({**row, **self._labels(a)}, self.ids)
        out = []
        if self._company_conflict(a):
            order = applicable(a)
            names = ", ".join(f"{THEME_NAME[r]} (answer {order.index(r) + 1})" for r in self._company_conflict(a))
            out.append(f"company_notice is Y but these themes are R: {names}. {COMPANY_RULE} "
                       f"Change those answers or the company notice (answer {order.index('company_notice') + 1}).")
        return out + [e for e in errs if "never R" not in e]

    def review(self, a: dict[str, str], row: dict[str, str]) -> None:
        """Show all answers and problems; return only when there are no problems and the user types Y."""
        while True:
            order = applicable(a)
            self.say("")
            self.say(f"--- Review {row['item_id']} (nothing is saved until you type Y) ---")
            for i, f in enumerate(order, start=1):
                self.say(f"  {i:>2}. {FIELD_NAME[f]:<32} {safe_text(a.get(f, '')) or '-'}")
            problems = self._problems(a, row)
            if problems:
                self.say("  Cannot be saved yet:")
                for p in problems:
                    self.say(f"   - {p}")
            try:
                raw = self.ask("  Y = save | answer number or field name = change it | < = back | s = skip | "
                               "q = quit: ", upper=False)
            except Back:
                raw = str(len(order))
            low = raw.strip().lower()
            if low == "y":
                if problems:
                    self.say("  Fix the listed problems first: type the number of the answer to change.")
                    continue
                return
            field = order[int(low) - 1] if low.isdigit() and 1 <= int(low) <= len(order) else (
                low if low in order else None)
            if field is None:
                self.say("  Type Y, a number from the list, or a field name such as company_notice.")
                continue
            self._revisit_field(a, field, row)
            self._prune(a)
            self.fill(a, row)

    def label_item(self, row: dict[str, str], index: int, total: int, *, correction: bool = False) -> bool:
        """Label one item. Returns True if saved. Raises Skip or Quit; nothing is saved in either case."""
        self.show(row, index, total)
        a: dict[str, str] = {}
        original: dict[str, str] = {}
        if correction:
            a = {f: row.get(f, "") for f in ORDER if row.get(f, "") or f in ("near_dup_of", "note")}
            self._prune(a)
            original = {f: a.get(f, "") for f in ORDER}
            self.say("  Current labels are loaded. Change what you need; a correction needs a reason.")
        self.fill(a, row)
        reason = ""
        while True:
            self.review(a, row)
            labels = self._labels(a)
            if correction:
                if {f: a.get(f, "") for f in ORDER} == original:
                    self.say("  Nothing changed; nothing saved.")
                    return False
                if not reason:
                    reason = self.ask("  Reason for the correction (required): ", upper=False)
                labels["note"] = " | ".join(x for x in (labels["note"], f"correction: {reason}") if x)
            try:
                annotate.save_item(self.p, row["item_id"], labels)
            except AnnotationError as exc:
                self.say(f"  Not saved: {exc.reason}")
                self.say("  Your answers are kept; change the one that needs it.")
                continue
            self.say(f"  Saved {row['item_id']}.")
            return True

    # ------------------------------------------------------------ sessions
    def _overlap_rows(self) -> list[dict[str, str]]:
        rep = annotate.validate(self.p)
        if rep.integrity_errors:
            raise AnnotationError("working copy failed integrity checks; run `annotate validate`")
        rows = annotate._working_rows(self.p)
        self.ids = {r["item_id"] for r in rows}
        return [r for r in rows if r["overlap_subset"] == "Y"]

    def run(self) -> dict[str, object]:
        """Label the unlabelled overlap items in file order. Resumes automatically."""
        rows = self._overlap_rows()
        pending = [r for r in rows if not annotate.is_labelled(r)]
        done_before = len(rows) - len(pending)
        self.say(f"Overlap items: {len(rows)}; already labelled: {done_before}; to do now: {len(pending)}")
        self.say("No AI suggestions are shown for these items. Type ? for help, < to go back, q to quit.")
        saved, skipped = 0, 0
        try:
            if pending:
                self.ask_initials()
            for i, row in enumerate(pending, start=1):
                try:
                    if self.label_item(row, done_before + i, len(rows)):
                        saved += 1
                except Skip:
                    skipped += 1
                    self.say("  Skipped; it stays unlabelled and comes back next session.")
        except Quit:
            self.say("Stopped. Everything you saved is kept; run the same command to resume.")
            return self._summary(saved, skipped, quit_early=True)
        return self._summary(saved, skipped, quit_early=False)

    def revisit(self, item_id: str) -> dict[str, object]:
        """Re-label one overlap item. An already labelled item needs an explicit correction reason."""
        rows = self._overlap_rows()
        by_id = {r["item_id"]: r for r in rows}
        if item_id not in by_id:
            raise AnnotationError(f"{item_id} is not an overlap item; this command only handles the overlap subset")
        row = by_id[item_id]
        correction = annotate.is_labelled(row)
        try:
            self.ask_initials()
            if correction:
                self.say(f"{item_id} is already labelled. Changing it is a correction and needs a reason.")
                if self.ask("  Change it? [Y/N]: ", {"Y", "N"}) == "N":
                    return self._summary(0, 0, quit_early=False)
            saved = self.label_item(row, list(by_id).index(item_id) + 1, len(rows), correction=correction)
        except (Skip, Quit):
            self.say("Nothing changed.")
            return self._summary(0, 1, quit_early=True)
        return self._summary(int(saved), 0, quit_early=False)

    def _summary(self, saved: int, skipped: int, *, quit_early: bool) -> dict[str, object]:
        s = annotate.status(self.p)
        return {"saved_this_session": saved, "skipped_this_session": skipped, "stopped_early": quit_early,
                "overlap_labelled": s["overlap_labelled"], "overlap_rows": s["overlap_rows"],
                "rows_with_errors": s["rows_with_errors"]}
