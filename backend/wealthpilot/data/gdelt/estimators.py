"""Pure estimators for the labelled filter review (B2-I section 4.6) and agreement measures.

No file, network or key access here: callers pass in-memory records. Nothing in this module decides
which labels are valid or independent; that is the evaluation gate's job (``evaluate.py``).

**Estimators follow the pre-registered B2-I §4.6 definitions.** Each sampled item carries the weight
``N_c / n_c`` of its cell. Ambiguous (``A``) items are excluded from point estimates and bracket the bounds.

Departure from B2-I, disclosed: the bootstrap uses ``random.Random(42)``, not numpy's ``default_rng(42)``,
because the isolated GDELT package may import only the standard library. Results are deterministic but
not numerically identical to numpy's stream.

The thresholds in ``proposed_thresholds`` are the B2-I §4.7 values. They are PROPOSED, not approved.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import sqrt

THEMES = ("equity", "rates", "gold")
REL = {"equity": "rel_equity", "rates": "rel_rates", "gold": "rel_gold"}
CAPTURED_CELLS = ("C1", "C2", "C3", "C4", "C5")
CUE_CELLS = ("C1", "C2", "C3", "C4", "C5", "C6")
RULE_OF_THREE = 3.0
# The bootstrap is the standard-library Mersenne Twister, random.Random(seed). B2-I section 4.6 names numpy
# default_rng(42). A matching seed does NOT give the same resamples across generators. Switching generator is a
# methodology decision and changes the evaluation fingerprint.
BOOTSTRAP_GENERATOR = "random.Random"
BOOTSTRAP_SEED = 42
BOOTSTRAP_RESAMPLES = 2000
PROPOSED_THRESHOLDS = {"precision_min": 0.70, "precision_lower_bound_min": 0.60, "pooled_capture_recall_min": 0.90}


@dataclass(frozen=True)
class Scored:
    """One labelled item joined to its sampling-cell facts."""

    item_id: str
    batch_ts: str
    cell: str                      # C1..C7
    cell_rows: int                 # N_c: rows in the cell
    cell_items: int                # n_c: items sampled from it
    rel: dict[str, str]            # theme -> R / RL / I / A (the human final label)
    company: str                   # Y / N / U
    member: dict[str, bool]        # theme -> member of the candidate series (from the key)
    label_basis: str = "own"
    mech_dup: str | None = None    # the pipeline duplicate mark; None = not supplied (missing, never assumed ORIGINAL)
    near_dup_of: str | None = None  # the annotator's duplicate reference ("" = none); None = not supplied

    @property
    def weight(self) -> float:
        return self.cell_rows / self.cell_items


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def reporting_floor(n_non_ambiguous: int) -> str:
    """B2-I §4.6: 100 or more -> estimate; 30-99 -> indicative; under 30 -> counts only."""
    return "estimate" if n_non_ambiguous >= 100 else "indicative" if n_non_ambiguous >= 30 else "counts_only"


def _w(items: Sequence[Scored], pred: Callable[[Scored], bool]) -> float:
    return sum(i.weight for i in items if pred(i))


def precision(items: Sequence[Scored], theme: str) -> dict[str, object]:
    """Weighted share of the theme's series members labelled R (ambiguous excluded)."""
    members = [i for i in items if i.member[theme]]
    c = Counter(i.rel[theme] for i in members)
    w = {k: _w(members, lambda i, k=k: i.rel[theme] == k) for k in ("R", "RL", "I", "A")}
    non_amb = w["R"] + w["RL"] + w["I"]
    n_non_amb = c["R"] + c["RL"] + c["I"]
    point = w["R"] / non_amb if non_amb > 0 else None
    total = non_amb + w["A"]
    return {
        "members_labelled": len(members), "counts": {k: c[k] for k in ("R", "RL", "I", "A")},
        "non_ambiguous": n_non_amb, "reporting": reporting_floor(n_non_amb),
        "precision": point,
        "bounds_ambiguous_as_not_R_to_R": (w["R"] / total, (w["R"] + w["A"]) / total) if total > 0 else None,
        "lenient_R_or_RL": (w["R"] + w["RL"]) / non_amb if non_amb > 0 else None,
        "unweighted_wilson_95": wilson(c["R"], n_non_amb),
    }


def pooled_recall(items: Sequence[Scored], theme: str) -> float | None:
    """Weighted R among series members divided by weighted R over cells C1-C6."""
    num = _w(items, lambda i: i.member[theme] and i.rel[theme] == "R")
    den = _w(items, lambda i: i.cell in CUE_CELLS and i.rel[theme] == "R")
    return num / den if den > 0 else None


def capture_recall(items: Sequence[Scored], theme: str) -> dict[str, object]:
    """Weighted R in captured cells (C1-C5) over weighted R in all cells.

    If no sampled C7 item is R, the C7 contribution is bounded by the rule of three and the result is a
    lower bound, as B2-I §4.6 requires.
    """
    num = _w(items, lambda i: i.cell in CAPTURED_CELLS and i.rel[theme] == "R")
    r6 = _w(items, lambda i: i.cell == "C6" and i.rel[theme] == "R")
    c7 = [i for i in items if i.cell == "C7" and i.rel[theme] != "A"]
    r7_items = [i for i in c7 if i.rel[theme] == "R"]
    if not c7:
        return {"recall": None, "lower_bound": False, "note": "no non-ambiguous C7 items"}
    if r7_items:
        r7 = _w(c7, lambda i: i.rel[theme] == "R")
        den = num + r6 + r7
        return {"recall": num / den if den > 0 else None, "lower_bound": False}
    bound = c7[0].cell_rows * RULE_OF_THREE / len(c7)
    den = num + r6 + bound
    return {"recall": num / den if den > 0 else None, "lower_bound": True,
            "note": "no R in C7: rule-of-three upper bound used for C7, so this is a lower bound"}


def company_stats(items: Sequence[Scored]) -> dict[str, object]:
    c4 = [i for i in items if i.cell == "C4"]
    out: dict[str, object] = {
        "flagged_company_items_labelled": len(c4),
        "share_labelled_Y": (sum(i.company == "Y" for i in c4) / len(c4)) if c4 else None,
        "leakage_weighted_share_of_series_members_labelled_Y": {},
    }
    leak = out["leakage_weighted_share_of_series_members_labelled_Y"]
    assert isinstance(leak, dict)
    for t in THEMES:
        members = [i for i in items if i.member[t]]
        tot = _w(members, lambda i: True)
        leak[t] = _w(members, lambda i: i.company == "Y") / tot if tot > 0 else None
    return out


def quantile(sorted_values: Sequence[float], q: float) -> float:
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def unique_story_precision(items: Sequence[Scored], theme: str) -> dict[str, object]:
    """Precision over unique stories only (B2-I 3.6): members the pipeline marks ORIGINAL and the annotator did not mark
    as a near-duplicate. Reported as unavailable, never guessed, if any member lacks the duplicate information."""
    members = [i for i in items if i.member[theme]]
    if any(i.mech_dup is None or i.near_dup_of is None for i in members):
        return {"available": False, "reason": "duplicate information was not supplied for every series member"}
    unique = [i for i in members if i.mech_dup == "ORIGINAL" and not i.near_dup_of]
    out = precision(unique, theme)
    return {"available": True, "members_total": len(members), "members_unique_story": len(unique), **out}


def cell_wilson(items: Sequence[Scored], theme: str) -> dict[str, object]:
    """Unweighted Wilson 95% interval per sampling cell: share of the cell's non-ambiguous items labelled R (B2-I 4.6
    cross-check). A cell with no non-ambiguous item is reported as None, not zero."""
    out: dict[str, object] = {}
    for cell in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
        rows = [i for i in items if i.cell == cell and i.rel[theme] != "A"]
        k = sum(i.rel[theme] == "R" for i in rows)
        out[cell] = {"non_ambiguous": len(rows), "R": k, "wilson_95": wilson(k, len(rows)) if rows else None}
    return out


def near_dup_count(items: Sequence[Scored]) -> int | None:
    """Annotator NEAR_DUP references; None if the information was not supplied for every item."""
    if any(i.near_dup_of is None for i in items):
        return None
    return sum(bool(i.near_dup_of) for i in items)


def cluster_bootstrap(items: Sequence[Scored], statistic: Callable[[Sequence[Scored]], float | None], *,
                      n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict[str, object]:
    """Resample whole batches with replacement (items within a batch are correlated).

    Item weights stay those of the original sample. A resample whose statistic is undefined is skipped and
    counted.
    """
    groups: dict[str, list[Scored]] = {}
    for i in items:
        groups.setdefault(i.batch_ts, []).append(i)
    keys = sorted(groups)
    rng = random.Random(seed)
    values: list[float] = []
    undefined = 0
    for _ in range(n_resamples):
        sample: list[Scored] = []
        for _k in keys:
            sample.extend(groups[rng.choice(keys)])
        v = statistic(sample)
        if v is None:
            undefined += 1
        else:
            values.append(v)
    if not values:
        return {"ci_95": None, "resamples_used": 0, "resamples_undefined": undefined, "batches": len(keys)}
    values.sort()
    return {"ci_95": (quantile(values, 0.025), quantile(values, 0.975)), "resamples_used": len(values),
            "resamples_undefined": undefined, "batches": len(keys), "seed": seed}


def proposed_thresholds(precision_point: float | None, precision_lower: float | None,
                        pooled_capture_recall: float | None) -> dict[str, object]:
    """B2-I §4.7 checks, reported as facts. The approved criteria live in ``decision.CRITERIA``; this older helper and its
    ``PROPOSED_*`` names are kept unchanged for the evaluation fingerprint and do not decide anything."""
    t = PROPOSED_THRESHOLDS
    checks = {
        "precision_at_least_0.70": None if precision_point is None else precision_point >= t["precision_min"],
        "bootstrap_lower_bound_at_least_0.60": None if precision_lower is None else precision_lower >= t["precision_lower_bound_min"],
        "pooled_capture_recall_at_least_0.90": None if pooled_capture_recall is None else pooled_capture_recall >= t["pooled_capture_recall_min"],
    }
    return {"status": "PROPOSED thresholds (B2-I section 4.7); not approved", "checks": checks,
            "all_met": all(v is True for v in checks.values())}


# ---------------------------------------------------------------- agreement (pure; not wired to any dataset)

def confusion(a: Sequence[str], b: Sequence[str]) -> dict[str, dict[str, int]]:
    if len(a) != len(b):
        raise ValueError("rater label lists must have equal length")
    table: dict[str, dict[str, int]] = {}
    for x, y in zip(a, b):
        table.setdefault(x, {}).setdefault(y, 0)
        table[x][y] += 1
    return table


def agreement(a: Sequence[str], b: Sequence[str], *, exclude: frozenset[str] = frozenset()) -> dict[str, object]:
    """Raw agreement, Cohen's kappa and Gwet's AC1 for two raters over paired labels.

    Pairs where either label is in ``exclude`` (for example ``{"A"}``) are dropped and counted. These are
    the arithmetic only: whether two label sets are *independent* is decided elsewhere and must be stated
    wherever a result is reported.
    """
    if len(a) != len(b):
        raise ValueError("rater label lists must have equal length")
    pairs = [(x, y) for x, y in zip(a, b) if x not in exclude and y not in exclude]
    n = len(pairs)
    out: dict[str, object] = {"pairs": n, "excluded_pairs": len(a) - n}
    if n == 0:
        return {**out, "raw_agreement": None, "cohen_kappa": None, "gwet_ac1": None}
    cats = sorted({x for p in pairs for x in p})
    po = sum(x == y for x, y in pairs) / n
    pa = Counter(x for x, _ in pairs)
    pb = Counter(y for _, y in pairs)
    pe_kappa = sum((pa[c] / n) * (pb[c] / n) for c in cats)
    kappa = None if pe_kappa == 1 else (po - pe_kappa) / (1 - pe_kappa)
    q = len(cats)
    pi = {c: (pa[c] + pb[c]) / (2 * n) for c in cats}
    pe_ac1 = sum(pi[c] * (1 - pi[c]) for c in cats) / (q - 1) if q > 1 else 1.0
    ac1 = None if pe_ac1 == 1 else (po - pe_ac1) / (1 - pe_ac1)
    return {**out, "raw_agreement": po, "cohen_kappa": kappa, "gwet_ac1": ac1, "categories": cats}
