"""Human-annotation utilities for the sentiment validation set. Pure and offline: they read no file, key, label store or model output, and they create no label.

Workflow (owner decisions of 2026-10-20): fresh human labels for two separate targets (``wording_tone`` and ``market_direction``); annotators see only item id, theme and title; a deterministic 20% subset per theme is
labelled by two annotators; every disagreement is adjudicated blind to model output; the labels are frozen and hashed before any scorer runs.

**Label codes.** ``POS`` / ``NEG`` / ``NEU`` are the comparable classes (they map to ``positive`` / ``negative`` / ``neutral``). ``MIX`` (mixed) and ``UNC`` (uncertain) are valid human answers that are kept DISTINCT from each other and
from ``NEU``, and are **not comparable** with a three-class scorer: they never enter the confusion matrix or an accuracy denominator, and are reported as counts (``NOT_COMPARABLE_TREATMENT``, fixed here before any result exists).
Inter-annotator agreement uses all five codes (primary) and the comparable three (secondary).

Everything refuses rather than repairs: a missing, malformed, unbound, AI-based or off-sample label, an undecided disagreement, or an unattested adjudication stops the freeze. Test fixtures are synthetic and are never
human annotations.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.polarity_validation import (
    HUMAN_INDEPENDENT, TARGETS, Prediction, ReferenceLabel, ValidationSample,
)
from wealthpilot.data.gdelt.sentiment.schema import THEMES
from wealthpilot.data.gdelt.timeutil import require_utc

CODES = ("POS", "NEG", "NEU", "MIX", "UNC")
COMPARABLE = {"POS": "positive", "NEG": "negative", "NEU": "neutral"}
NOT_COMPARABLE = ("MIX", "UNC")
UNRESOLVED = "UNRESOLVED"                 # an adjudication outcome: the item is excluded and counted, never guessed
NOT_COMPARABLE_TREATMENT = ("MIX and UNC are kept distinct from each other and from NEU. They are excluded from the 3-class confusion matrix, accuracy and F1 denominators and reported as counts per theme "
                            "and target; a scorer's predictions on such items are reported as a breakdown, never scored right or wrong. Agreement uses all five codes (primary) and the three comparable codes (secondary).")
PROTOCOL_STATUS = "PROPOSAL_NOT_APPROVED"      # the metrics and acceptance criteria stay proposals until the owner approves them


class AnnotationError(GdeltToolError):
    code = "sentiment_annotation_error"


class FreezeRefused(AnnotationError):
    code = "sentiment_annotation_freeze_refused"


def _sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _rank(seed: int, tag: str, theme: str, item: str) -> tuple[str, str]:
    return hashlib.sha256(f"{seed}:{tag}:{theme}:{item}".encode()).hexdigest(), item


# ================================================================ assignment

@dataclass(frozen=True)
class DoubleAssignment:
    fraction: float
    seed: int
    double: Mapping[str, tuple[str, ...]]        # theme -> items that BOTH annotators label
    n_double: Mapping[str, int]
    not_feasible: tuple[str, ...]                # themes whose pool is too small for a double-labelled subset (fewer than 5 items)
    sha256: str


def assign_double_annotation(sample: ValidationSample, *, fraction: float, seed: int) -> DoubleAssignment:
    """Deterministically choose ``ceil(fraction * n)`` items per theme for double labelling (themes with fewer than 5 items are reported as not feasible, never padded)."""
    if not (isinstance(fraction, float) and 0.0 < fraction <= 1.0):
        raise AnnotationError("fraction must be a float in (0, 1]")
    if not (isinstance(seed, int) and not isinstance(seed, bool)):
        raise AnnotationError("seed must be an explicit integer")
    double: dict[str, tuple[str, ...]] = {}
    nf: list[str] = []
    for t in THEMES:
        ids = sample.by_theme.get(t, ())
        if len(ids) < 5:
            double[t] = ()
            if ids:
                nf.append(t)
            continue
        k = math.ceil(fraction * len(ids))
        double[t] = tuple(sorted(ids, key=lambda a: _rank(seed, "double", t, a))[:k])
    return DoubleAssignment(fraction, seed, double, {t: len(v) for t, v in double.items()}, tuple(nf), _sha([fraction, seed, sample.manifest_sha256, sorted(double.items())]))


# ================================================================ annotations, agreement, adjudication

@dataclass(frozen=True)
class AnnotationRecord:
    item_id: str
    theme: str
    target: str
    annotator_id: str                # initials; never an email
    annotator_type: str              # must be "human"
    label_basis: str                 # must be "own": no AI suggestion was seen
    code: str                        # one of CODES
    instruction_sha256: str
    export_sha256: str
    labelled_at_utc: datetime


@dataclass(frozen=True)
class AdjudicationRecord:
    item_id: str
    theme: str
    target: str
    adjudicator_id: str
    final_code: str                  # one of CODES, or UNRESOLVED
    blind_to_model_output: bool      # the adjudicator's attestation that no model output was seen
    adjudicated_at_utc: datetime


@dataclass(frozen=True)
class Agreement:
    n: int
    observed: float | None
    kappa: float | None              # None when undefined (no items, or chance agreement is 1)
    categories: tuple[str, ...]


def cohen_kappa(pairs: Sequence[tuple[str, str]], categories: Sequence[str]) -> Agreement:
    n = len(pairs)
    if n == 0:
        return Agreement(0, None, None, tuple(categories))
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in categories)
    return Agreement(n, po, None if pe >= 1.0 else (po - pe) / (1.0 - pe), tuple(categories))


def _check_annotation(r: AnnotationRecord, sample: ValidationSample, target: str, export_sha256: str, instruction_sha256: str) -> None:
    where = f"{r.item_id}/{r.theme}/{r.annotator_id}"
    if r.target != target:
        raise AnnotationError(f"{where}: target {r.target!r} differs from {target!r}")
    if r.item_id not in sample.by_theme.get(r.theme, ()):
        raise AnnotationError(f"{where}: not in the frozen validation sample")
    if r.code not in CODES:
        raise AnnotationError(f"{where}: code {r.code!r} is not one of {CODES}")
    if r.annotator_type != "human" or r.label_basis != "own":
        raise AnnotationError(f"{where}: only human labels made on the annotator's own judgement count (AI suggestions are not independent)")
    if not r.annotator_id.strip() or "@" in r.annotator_id:
        raise AnnotationError(f"{where}: annotator_id must be non-empty initials, never an email")
    if r.export_sha256 != export_sha256 or r.instruction_sha256 != instruction_sha256:
        raise AnnotationError(f"{where}: the label is not bound to this export and instruction sheet")
    require_utc(r.labelled_at_utc, "labelled_at_utc")


def disagreements(first: Mapping[tuple[str, str], str], second: Mapping[tuple[str, str], str]) -> tuple[tuple[str, str], ...]:
    """Items both annotators labelled with different codes (MIX versus POS counts as a disagreement)."""
    return tuple(sorted(k for k in first if k in second and first[k] != second[k]))


# ================================================================ freeze

@dataclass(frozen=True)
class FreezeManifest:
    target: str
    sample_sha256: str
    export_sha256: str
    instruction_sha256: str
    assignment_sha256: str
    protocol_sha256: str
    protocol_status: str
    final_codes: Mapping[tuple[str, str], str]               # (item, theme) -> code, adjudicated where needed; unresolved items absent
    counts: Mapping[str, Mapping[str, int]]                  # theme -> code (or UNRESOLVED) -> n
    agreement: Mapping[str, Mapping[str, Agreement]]         # theme -> {"all_codes": ..., "comparable": ...} on the double-labelled items
    n_unresolved: Mapping[str, int]
    sha256: str                                              # binds everything above plus the raw annotations and adjudications (not the timestamp)
    frozen_at_utc: datetime                                  # recorded, never relied on
    treatment: str = NOT_COMPARABLE_TREATMENT


def build_freeze_manifest(*, target: str, sample: ValidationSample, export_sha256: str, instruction_sha256: str, assignment: DoubleAssignment,
                          annotations: Sequence[AnnotationRecord], adjudications: Sequence[AdjudicationRecord], primary_annotator: str,
                          secondary_annotator: str | None, protocol_sha256: str, frozen_at_utc: datetime) -> FreezeManifest:
    """Validate every label and decision and return the freeze record, or raise ``FreezeRefused``. Nothing is repaired, defaulted or guessed."""
    try:
        return _build(target, sample, export_sha256, instruction_sha256, assignment, annotations, adjudications, primary_annotator, secondary_annotator, protocol_sha256, frozen_at_utc)
    except FreezeRefused:
        raise
    except GdeltToolError as exc:                  # any validation error, including a malformed timestamp, is a refusal
        raise FreezeRefused(str(exc)) from exc


def _build(target, sample, export_sha256, instruction_sha256, assignment, annotations, adjudications, primary, secondary, protocol_sha256, frozen_at):   # noqa: ANN001
    if target not in TARGETS:
        raise FreezeRefused(f"target must be one of {TARGETS}")
    if assignment != assign_double_annotation(sample, fraction=assignment.fraction, seed=assignment.seed):          # the whole object, not only its hash
        raise FreezeRefused("the double-annotation assignment does not belong to this sample")
    require_utc(frozen_at, "frozen_at_utc")
    if not annotations:
        raise FreezeRefused("no annotations: there is nothing to freeze")
    ids = {r.annotator_id for r in annotations}
    if primary not in ids or ids - {primary, secondary}:
        raise FreezeRefused(f"annotators found {sorted(ids)} differ from the declared primary {primary!r} and secondary {secondary!r}")
    by: dict[str, dict[tuple[str, str], str]] = {primary: {}}
    if secondary:
        by[secondary] = {}
    for r in annotations:
        _check_annotation(r, sample, target, export_sha256, instruction_sha256)
        key = (r.item_id, r.theme)
        if key in by[r.annotator_id]:
            raise FreezeRefused(f"{r.item_id}/{r.theme}: labelled twice by {r.annotator_id}")
        by[r.annotator_id][key] = r.code
    sampled = {(i, t) for t in THEMES for i in sample.by_theme.get(t, ())}
    missing = sorted(sampled - set(by[primary]))
    if missing:
        raise FreezeRefused(f"{len(missing)} sampled item(s) have no label from the primary annotator, e.g. {missing[0]}")
    wanted_double = {(i, t) for t in THEMES for i in assignment.double.get(t, ())}
    got_double = set(by[secondary]) if secondary else set()
    if got_double != wanted_double:
        raise FreezeRefused(f"the secondary annotator must label exactly the assigned double-annotation items (missing {len(wanted_double - got_double)}, unexpected {len(got_double - wanted_double)})")
    queue = disagreements(by[primary], by[secondary] if secondary else {})
    adj: dict[tuple[str, str], AdjudicationRecord] = {}
    for a in adjudications:
        key = (a.item_id, a.theme)
        if a.target != target or key in adj:
            raise FreezeRefused(f"{a.item_id}/{a.theme}: adjudication has the wrong target or is repeated")
        if a.final_code not in CODES + (UNRESOLVED,):
            raise FreezeRefused(f"{a.item_id}/{a.theme}: adjudicated code {a.final_code!r} is not valid")
        if a.blind_to_model_output is not True or not a.adjudicator_id.strip() or "@" in a.adjudicator_id:
            raise FreezeRefused(f"{a.item_id}/{a.theme}: an adjudication needs an adjudicator id and the attestation that no model output was seen")
        require_utc(a.adjudicated_at_utc, "adjudicated_at_utc")
        adj[key] = a
    if set(adj) != set(queue):
        raise FreezeRefused(f"adjudications must cover exactly the disagreements (missing {len(set(queue) - set(adj))}, unexpected {len(set(adj) - set(queue))})")
    final = {k: (adj[k].final_code if k in adj else c) for k, c in by[primary].items()}
    counts = {t: {c: 0 for c in CODES + (UNRESOLVED,)} for t in THEMES}
    for (i, t), c in final.items():
        counts[t][c] += 1
    agreement = {}
    for t in THEMES:
        pairs = [(by[primary][k], by[secondary][k]) for k in sorted(wanted_double) if k[1] == t] if secondary else []
        comp = [(a, b) for a, b in pairs if a in COMPARABLE and b in COMPARABLE]
        agreement[t] = {"all_codes": cohen_kappa(pairs, CODES), "comparable": cohen_kappa(comp, tuple(COMPARABLE))}
    kept = {k: c for k, c in final.items() if c != UNRESOLVED}
    digest = _sha({"target": target, "sample": sample.manifest_sha256, "export": export_sha256, "instructions": instruction_sha256, "assignment": assignment.sha256,
                   "protocol": protocol_sha256, "protocol_status": PROTOCOL_STATUS, "treatment": NOT_COMPARABLE_TREATMENT,
                   "final": sorted([i, t, c] for (i, t), c in final.items()),
                   "annotations": sorted([r.item_id, r.theme, r.annotator_id, r.code] for r in annotations),
                   "adjudications": sorted([a.item_id, a.theme, a.adjudicator_id, a.final_code] for a in adjudications)})
    return FreezeManifest(target, sample.manifest_sha256, export_sha256, instruction_sha256, assignment.sha256, protocol_sha256, PROTOCOL_STATUS, kept, counts, agreement,
                          {t: counts[t][UNRESOLVED] for t in THEMES}, digest, frozen_at)


def comparable_reference_labels(m: FreezeManifest) -> list[ReferenceLabel]:
    """The frozen labels a three-class scorer can be compared with: POS / NEG / NEU only, as ``human_independent`` labels bound to the export."""
    return [ReferenceLabel(i, COMPARABLE[c], HUMAN_INDEPENDENT, m.frozen_at_utc, t, m.target, m.export_sha256)
            for (i, t), c in sorted(m.final_codes.items()) if c in COMPARABLE]


def not_comparable_counts(m: FreezeManifest) -> dict[str, dict[str, int]]:
    """MIX, UNC and UNRESOLVED counts per theme, reported beside (never inside) the classification metrics."""
    return {t: {c: m.counts[t][c] for c in NOT_COMPARABLE + (UNRESOLVED,)} for t in THEMES}


def not_comparable_prediction_breakdown(m: FreezeManifest, predictions: Sequence[Prediction]) -> dict[str, dict[str, Counter]]:
    """What a scorer predicted on MIX / UNC items: a descriptive breakdown, never scored as right or wrong."""
    pred = {p.article_id: p.label for p in predictions}
    out: dict[str, dict[str, Counter]] = {t: {c: Counter() for c in NOT_COMPARABLE} for t in THEMES}
    for (i, t), c in m.final_codes.items():
        if c in NOT_COMPARABLE:
            out[t][c][pred.get(i, "no_prediction")] += 1
    return out


def target_export_sha256(target: str, rows: Sequence[Mapping[str, str]]) -> str:
    """The export hash for ONE target pass: the order-independent content hash bound to the target name, so a label made for one pass can never validate against the other."""
    from wealthpilot.data.gdelt.sentiment.polarity_validation import annotation_export_sha256
    if target not in TARGETS:
        raise AnnotationError(f"target must be one of {TARGETS}")
    return _sha([target, annotation_export_sha256(rows)])
