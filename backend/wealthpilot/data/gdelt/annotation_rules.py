"""Rule-based validation of annotation records (B2-U18). Pure and offline: it reads nothing, writes nothing and decides nothing
about accuracy. It only says whether a set of label rows is structurally and logically consistent.

It reuses the existing rubric enumerations and ``annotate.content_errors`` (the validator the human workflow already uses), and adds
the checks that look across rows: missing, duplicated and unknown IDs; duplicate references that are malformed, unknown,
self-referencing or circular; source fields that differ from the original; overlap membership that disagrees with the verified
manifest; and annotator or basis values that would let a non-human label pass as a human one.

Two modes:

- ``human_reference``: rows of the human working copy. ``annotator_type`` must be ``human`` and ``label_basis`` one of the
  recognised human bases; ``ai_only`` labels or an ``ai`` annotator are contamination and are named as such.
- ``content_only``: label content only (used for model suggestions, which carry no annotator or basis columns).

Nothing here changes the rubric, a threshold or an approval.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from wealthpilot.data.gdelt import annotate
from wealthpilot.data.gdelt.annotate import AMB_CODES, BASIS_VALUES, COMPANY_VALUES, LABEL_COLUMNS, POL_VALUES, REL_VALUES, SOURCE_COLUMNS

_ID_RE = re.compile(r"^D\d{4}$")
REL_FIELDS = ("rel_equity", "rel_rates", "rel_gold")
POL_FIELDS = ("pol_equity", "pol_rates", "pol_gold")
HUMAN_REFERENCE, CONTENT_ONLY = "human_reference", "content_only"
AI_ONLY_BASIS = "ai_only"


@dataclass
class RuleReport:
    problems: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, kind: str, item_id: str | None, detail: str) -> None:
        self.problems.append({"kind": kind, "item_id": item_id, "detail": detail})

    @property
    def kinds(self) -> set[str]:
        return {p["kind"] for p in self.problems}


def _v(row: Mapping[str, Any]) -> dict[str, str]:
    return {c: str(row.get(c) or "").strip() for c in LABEL_COLUMNS}


def check_row(rep: RuleReport, row: Mapping[str, Any], *, all_ids: set[str] | None = None, mode: str = CONTENT_ONLY) -> None:
    """Row-level checks. ``all_ids`` (when given) is the set of valid item IDs for duplicate-reference validation."""
    iid = str(row.get("item_id") or "").strip()
    v = _v(row)
    before = len(rep.problems)
    for f in REL_FIELDS:
        if v[f] not in REL_VALUES:
            rep.add("enum_invalid", iid, f"{f} must be R, RL, I or A (got {v[f]!r})")
    if v["company_notice"] not in COMPANY_VALUES:
        rep.add("enum_invalid", iid, f"company_notice must be Y, N or U (got {v['company_notice']!r})")
    if v["amb_code"] and v["amb_code"] not in AMB_CODES:
        rep.add("enum_invalid", iid, f"amb_code {v['amb_code']!r} is not a rubric code")
    for rel, pol in zip(REL_FIELDS, POL_FIELDS):
        if v[pol] and v[pol] not in POL_VALUES:
            rep.add("enum_invalid", iid, f"{pol} must be POS, NEG, NEU, MIX or UNC (got {v[pol]!r})")
        elif v[rel] == "R" and not v[pol]:
            rep.add("polarity_missing", iid, f"{pol} is required when {rel} is R")
        elif v[rel] in REL_VALUES and v[rel] != "R" and v[pol]:
            rep.add("polarity_unexpected", iid, f"{pol} must be blank unless {rel} is R")
    has_a = "A" in {v[f] for f in REL_FIELDS}
    if has_a and v["amb_code"] not in AMB_CODES:
        rep.add("amb_missing", iid, "a theme is A but amb_code is missing or invalid")
    if v["amb_code"] and not has_a:
        rep.add("amb_unexpected", iid, "amb_code is set but no theme is A")
    if v["company_notice"] == "Y" and "R" in {v[f] for f in REL_FIELDS}:
        rep.add("company_conflict", iid, "a company or fund notice (company_notice Y) is never R")
    ref = v["near_dup_of"]
    if ref:
        if not _ID_RE.match(ref):
            rep.add("near_dup_malformed", iid, f"near_dup_of must be an item ID such as D0001 (got {ref!r})")
        elif ref == iid:
            rep.add("near_dup_self", iid, "near_dup_of names the item itself")
        elif all_ids is not None and ref not in all_ids:
            rep.add("near_dup_unknown", iid, f"near_dup_of {ref!r} is not an item of this dataset")
    if mode == HUMAN_REFERENCE:
        a_type, basis = v["annotator_type"], v["label_basis"]
        if a_type == "ai" or basis == AI_ONLY_BASIS:
            rep.add("ai_only_contamination", iid, "an AI-only label cannot be a human-reference label")
        elif a_type != "human":
            rep.add("non_human_annotator", iid, f"annotator_type must be 'human' (got {a_type!r})")
        if basis != AI_ONLY_BASIS and basis not in BASIS_VALUES:
            rep.add("basis_invalid", iid, f"label_basis {basis!r} is not a recognised human basis")
        if not v["annotator_id"]:
            rep.add("annotator_missing", iid, "annotator_id (initials) is required")
    if len(rep.problems) == before:                                 # a safety net: anything the shared rubric validator still finds
        for msg in annotate.content_errors(v, item_id=iid or None, all_ids=all_ids if all_ids is not None else set()):
            if "near_dup_of must be another existing item_id" in msg and all_ids is None:
                continue                                           # existence cannot be judged without the ID set
            rep.add("rubric", iid, msg)


def check_rows(rows: Sequence[Mapping[str, Any]], *, expected_ids: Iterable[str] | None = None,
               originals: Mapping[str, Mapping[str, str]] | None = None, overlap_ids: Iterable[str] | None = None,
               mode: str = HUMAN_REFERENCE, only_labelled: bool = False) -> RuleReport:
    """Set-level and row-level checks over ``rows``.

    ``expected_ids`` enables missing/unknown-ID detection; ``originals`` (item_id -> the original annotation row) enables the
    source-field check; ``overlap_ids`` is the VERIFIED overlap membership, compared with each row's ``overlap_subset``.
    ``only_labelled`` skips rows with no label value at all (a working copy is partly empty by design).
    """
    rep = RuleReport()
    ids = [str(r.get("item_id") or "").strip() for r in rows]
    for i in ids:
        if not _ID_RE.match(i):
            rep.add("malformed_item_id", i or None, "item ID is empty or malformed")
    for i, n in sorted(Counter(i for i in ids if i).items()):
        if n > 1:
            rep.add("duplicate_item", i, f"the item appears {n} times")
    expected = set(expected_ids) if expected_ids is not None else None
    if expected is not None:
        for i in sorted(set(ids) - expected - {""}):
            rep.add("unknown_item", i, "the item is not in the expected set")
        for i in sorted(expected - set(ids)):
            rep.add("missing_item", i, "an expected item has no row")
    valid_ids = expected if expected is not None else {i for i in ids if _ID_RE.match(i)}
    refs: dict[str, str] = {}
    for r in rows:
        iid = str(r.get("item_id") or "").strip()
        if only_labelled and not any(str(r.get(c) or "").strip() for c in LABEL_COLUMNS):
            continue
        check_row(rep, r, all_ids=valid_ids, mode=mode)
        ref = str(r.get("near_dup_of") or "").strip()
        if ref:
            refs[iid] = ref
        if originals is not None and iid in originals:
            changed = [c for c in SOURCE_COLUMNS if str(r.get(c) or "") != str(originals[iid].get(c) or "")]
            if changed:
                rep.add("source_changed", iid, f"source fields differ from the original: {changed}")
        elif originals is not None and iid and iid not in originals:
            rep.add("unknown_item", iid, "the item is not in the original")
    if overlap_ids is not None:
        ov = set(overlap_ids)
        for r in rows:
            iid = str(r.get("item_id") or "").strip()
            flag = str(r.get("overlap_subset") or "").strip()
            if flag in ("Y", "N") and (flag == "Y") != (iid in ov):
                rep.add("membership_conflict", iid, "overlap_subset disagrees with the verified overlap membership")
    for a, b in sorted(refs.items()):
        if refs.get(b) == a and a < b:
            rep.add("near_dup_cycle", a, f"{a} and {b} name each other as the duplicate source")
    return rep
