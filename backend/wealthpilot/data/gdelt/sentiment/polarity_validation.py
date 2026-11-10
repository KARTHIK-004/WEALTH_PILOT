"""Polarity-validation infrastructure. Pure and offline: it works on in-memory objects, opens no file, and touches no key, label store or AI suggestion.

It computes **descriptive** agreement statistics between independent human reference labels and a scorer's predictions, and it **rejects** evidence that is not valid. It never
declares a scorer validated: no acceptance criterion is approved (E2d), so the result carries ``verdict = NO_ACCEPTANCE_CRITERIA_APPROVED`` and the caller must not read it as one.

Evidence is rejected (``PolarityEvidenceError``) when: a label is not human-independent (an AI suggestion is never ground truth); a label id is in the caller's overlap-exclusion set;
the labels were not frozen strictly before every prediction was made; predictions come from more than one model identity; an id is duplicated; a label or prediction is malformed.
Evidence is *insufficient* (no metrics are computed) when fewer than ``min_labelled`` labelled articles were actually scored. ``min_labelled`` has no default: the sample size is the owner's decision.
An ``unavailable`` prediction is counted apart; it is never scored as wrong, as neutral or as correct. Intervals are Wilson 95% intervals on counts.

**Sampling and annotation export (no labels are created here).** ``draw_validation_sample`` selects, per theme, which text-ok theme-flagged candidates should be labelled: deterministic (a SHA-256 ranking of
``seed:theme:article_id``, not a random generator), seeded explicitly, never from the caller's overlap-exclusion set, and reported with the pool sizes and any shortfall. ``annotation_rows`` exports only the id,
the theme and the title for the human annotators: never a tone value, a prediction or any scorer output, so the labels stay independent of the system they will judge. ``validate_polarity_by_theme`` runs
the evidence check once per theme, because one article can carry a different polarity for each theme.

**Unresolved (owner decision, not settled here):** what "polarity" means. The B2 annotation rubric labels polarity per theme "from the asset holder's view" (POS / NEG / NEU / MIX / UNC; rising yields are NEG for
bonds), which is market direction. A text-tone scorer, and GDELT's document tone, measure wording. Comparing them without a stated mapping would conflate the two.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.dayfile_adapter import CandidateRecord
from wealthpilot.data.gdelt.sentiment.schema import LABELS, THEMES, UNAVAILABLE
from wealthpilot.data.gdelt.sentiment.scored_records import scoring_inputs
from wealthpilot.data.gdelt.timeutil import require_utc

HUMAN_INDEPENDENT = "human_independent"
TARGETS = ("wording_tone", "market_direction")      # two different constructs; never pooled
# Construct mappings the owner has approved for comparing a predictor of one construct with labels of the other. None is approved, so a mismatch is always refused.
APPROVED_CONSTRUCT_MAPPINGS: frozenset[str] = frozenset()
VERDICT = "NO_ACCEPTANCE_CRITERIA_APPROVED"
_Z95 = 1.959963984540054


class PolarityEvidenceError(GdeltToolError):
    code = "sentiment_polarity_evidence_invalid"


@dataclass(frozen=True)
class ReferenceLabel:
    article_id: str
    label: str                       # positive | negative | neutral
    labeller_kind: str               # must be HUMAN_INDEPENDENT
    frozen_at_utc: datetime          # when the labels were frozen
    theme: str | None = None         # the theme the polarity is for (None: not theme-specific)
    target: str | None = None        # the construct that was labelled: one of TARGETS (required by ``validate_target_evidence``)
    export_sha256: str | None = None # the annotation export these labels were made against (required by ``validate_target_evidence``)


@dataclass(frozen=True)
class Prediction:
    article_id: str
    label: str                       # positive | negative | neutral | unavailable
    scored_at_utc: datetime | None   # None only for an unavailable prediction
    model_id: str
    model_revision: str
    construct: str = "wording_tone"  # what the predictor measures: one of TARGETS


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float
    n: int


@dataclass(frozen=True)
class ClassStats:
    label: str
    support: int                     # reference labels of this class that were scored
    precision: Interval | None       # None when nothing was predicted as this class
    recall: Interval | None          # None when the class has no support


@dataclass(frozen=True)
class PolarityEvidence:
    status: str                      # INSUFFICIENT_EVIDENCE | COMPUTED_DESCRIPTIVE
    verdict: str                     # always NO_ACCEPTANCE_CRITERIA_APPROVED
    model: tuple[str, str] | None    # (model_id, model_revision)
    n_labelled: int
    n_scored: int
    n_unavailable: int               # labelled, but the prediction is unavailable: counted, never scored
    n_unpredicted: int               # labelled, with no prediction at all
    min_labelled: int
    confusion: tuple[tuple[int, ...], ...] | None    # rows = reference, columns = prediction, order = LABELS
    accuracy: Interval | None
    classes: tuple[ClassStats, ...]
    macro_f1: float | None           # over classes with support and at least one prediction; descriptive only


def wilson(successes: int, n: int) -> Interval | None:
    """Wilson 95% score interval; ``None`` when ``n`` is 0 (no interval is invented)."""
    if n <= 0:
        return None
    p = successes / n
    z2 = _Z95 ** 2
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = _Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half), n)


def validate_polarity(labels: Sequence[ReferenceLabel], predictions: Sequence[Prediction], *, excluded_ids: frozenset[str],
                      min_labelled: int) -> PolarityEvidence:
    if not (isinstance(min_labelled, int) and not isinstance(min_labelled, bool) and min_labelled >= 1):
        raise PolarityEvidenceError("min_labelled must be an integer >= 1 (no default: the sample size is an owner decision)")
    if not isinstance(excluded_ids, frozenset):
        raise PolarityEvidenceError("excluded_ids must be a frozenset of the overlap-excluded article ids")
    ref: dict[str, ReferenceLabel] = {}
    for lab in labels:
        if lab.labeller_kind != HUMAN_INDEPENDENT:
            raise PolarityEvidenceError(f"{lab.article_id}: labeller kind {lab.labeller_kind!r} is not human-independent; AI suggestions are never ground truth")
        if lab.label not in LABELS:
            raise PolarityEvidenceError(f"{lab.article_id}: reference label {lab.label!r} is not one of {LABELS}")
        if lab.article_id in ref:
            raise PolarityEvidenceError(f"{lab.article_id}: duplicate reference label")
        if lab.article_id in excluded_ids:
            raise PolarityEvidenceError(f"{lab.article_id}: is in the overlap-exclusion set")
        require_utc(lab.frozen_at_utc, "frozen_at_utc")
        ref[lab.article_id] = lab
    pred: dict[str, Prediction] = {}
    for p in predictions:
        if p.label not in LABELS + (UNAVAILABLE,):
            raise PolarityEvidenceError(f"{p.article_id}: prediction label {p.label!r} is malformed")
        if p.article_id in pred:
            raise PolarityEvidenceError(f"{p.article_id}: duplicate prediction")
        if (p.label == UNAVAILABLE) != (p.scored_at_utc is None):
            raise PolarityEvidenceError(f"{p.article_id}: a scored prediction needs a scoring time and an unavailable one must have none")
        pred[p.article_id] = p
    models = {(p.model_id, p.model_revision) for p in pred.values()}
    if len(models) > 1:
        raise PolarityEvidenceError(f"predictions come from {len(models)} model identities; one evidence set is for one model")
    for aid, lab in ref.items():
        p = pred.get(aid)
        if p is not None and p.scored_at_utc is not None and not lab.frozen_at_utc < require_utc(p.scored_at_utc, "scored_at_utc"):
            raise PolarityEvidenceError(f"{aid}: the labels were not frozen strictly before scoring")
    scored = [(ref[a].label, pred[a].label) for a in sorted(ref) if a in pred and pred[a].label != UNAVAILABLE]
    n_unavail = sum(1 for a in ref if a in pred and pred[a].label == UNAVAILABLE)
    n_unpred = sum(1 for a in ref if a not in pred)
    base = dict(verdict=VERDICT, model=next(iter(models), None), n_labelled=len(ref), n_scored=len(scored), n_unavailable=n_unavail,
                n_unpredicted=n_unpred, min_labelled=min_labelled)
    if len(scored) < min_labelled:
        return PolarityEvidence(status="INSUFFICIENT_EVIDENCE", confusion=None, accuracy=None, classes=(), macro_f1=None, **base)   # type: ignore[arg-type]
    idx = {label: i for i, label in enumerate(LABELS)}
    cm = [[0] * 3 for _ in range(3)]
    for r, q in scored:
        cm[idx[r]][idx[q]] += 1
    stats: list[ClassStats] = []
    f1s: list[float] = []
    for label in LABELS:
        i = idx[label]
        support, predicted, hit = sum(cm[i]), sum(cm[j][i] for j in range(3)), cm[i][i]
        prec, rec = wilson(hit, predicted), wilson(hit, support)
        stats.append(ClassStats(label, support, prec, rec))
        if support and predicted:
            p_, r_ = hit / predicted, hit / support
            f1s.append(0.0 if p_ + r_ == 0 else 2 * p_ * r_ / (p_ + r_))
    return PolarityEvidence(status="COMPUTED_DESCRIPTIVE", confusion=tuple(tuple(r) for r in cm),
                            accuracy=wilson(sum(cm[i][i] for i in range(3)), len(scored)), classes=tuple(stats),
                            macro_f1=sum(f1s) / len(f1s) if f1s else None, **base)       # type: ignore[arg-type]


def validate_polarity_by_theme(labels: Sequence[ReferenceLabel], predictions: Sequence[Prediction], *, excluded_ids: frozenset[str],
                               min_labelled: int) -> Mapping[str, PolarityEvidence]:
    """One evidence check per theme. A label with ``theme=None`` is rejected here: a per-theme claim needs a per-theme label."""
    if any(lab.theme not in THEMES for lab in labels):
        raise PolarityEvidenceError(f"every label needs a theme in {THEMES}")
    return {t: validate_polarity([lab for lab in labels if lab.theme == t], predictions, excluded_ids=excluded_ids, min_labelled=min_labelled)
            for t in THEMES if any(lab.theme == t for lab in labels)}


@dataclass(frozen=True)
class ValidationSample:
    seed: int
    per_theme: int
    by_theme: Mapping[str, tuple[str, ...]]      # article ids to label, per theme, in draw order
    pool_sizes: Mapping[str, int]                # eligible candidates per theme after exclusions
    shortfall: Mapping[str, int]                 # requested minus drawn, per theme
    n_excluded_in_pool: int                      # eligible candidates removed because they are in the exclusion set
    manifest_sha256: str                         # binds seed, size, exclusions and the drawn ids


def draw_validation_sample(candidates: Sequence[CandidateRecord], *, excluded_ids: frozenset[str], per_theme: int, seed: int, min_chars: int) -> ValidationSample:
    """Which candidates should be labelled by humans. Pure and deterministic; no labels, predictions or scores are read or produced."""
    if not isinstance(excluded_ids, frozenset):
        raise PolarityEvidenceError("excluded_ids must be a frozenset of the overlap-excluded article ids")
    for name, v in (("per_theme", per_theme), ("seed", seed)):
        if not (isinstance(v, int) and not isinstance(v, bool)) or (name == "per_theme" and v < 1):
            raise PolarityEvidenceError(f"{name} must be an explicit integer" + (" >= 1" if name == "per_theme" else ""))
    eligible = scoring_inputs(candidates, min_chars=min_chars)
    kept = [c for c in eligible if c.article_id not in excluded_ids]
    by_theme: dict[str, tuple[str, ...]] = {}
    pools: dict[str, int] = {}
    short: dict[str, int] = {}
    for t in THEMES:
        pool = sorted((c.article_id for c in kept if c.theme_flags[t]),
                      key=lambda a: (hashlib.sha256(f"{seed}:{t}:{a}".encode()).hexdigest(), a))
        by_theme[t], pools[t] = tuple(pool[:per_theme]), len(pool)
        short[t] = per_theme - len(by_theme[t])
    digest = hashlib.sha256(json.dumps([seed, per_theme, len(excluded_ids), sorted(by_theme.items())], sort_keys=True).encode()).hexdigest()
    return ValidationSample(seed, per_theme, by_theme, pools, short, len(eligible) - len(kept), digest)


def annotation_rows(sample: ValidationSample, candidates: Sequence[CandidateRecord]) -> list[dict[str, str]]:
    """What the human annotators receive: article id, theme and title only. Never a tone value, a prediction or a score."""
    title = {c.article_id: c.title for c in candidates}
    return [{"article_id": a, "theme": t, "title": title[a]} for t in THEMES for a in sample.by_theme[t]]


def annotation_export_sha256(rows: Sequence[Mapping[str, str]]) -> str:
    """A hash of the exact annotation content (id, theme, and the hash of the title), independent of row order. Labels made against an export carry this value."""
    items = sorted([r["article_id"], r["theme"], hashlib.sha256(r["title"].encode("utf-8")).hexdigest()] for r in rows)
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


@dataclass(frozen=True)
class TargetEvidence:
    target: str
    sample_sha256: str
    export_sha256: str
    by_theme: Mapping[str, PolarityEvidence]     # one entry per theme that has a sample, including themes with no labels (insufficient)
    verdict: str = VERDICT


def validate_target_evidence(labels: Sequence[ReferenceLabel], predictions: Sequence[Prediction], *, target: str, sample: ValidationSample,
                             export_sha256: str, excluded_ids: frozenset[str], min_labelled: int,
                             construct_mapping: str | None = None) -> TargetEvidence:
    """Per-theme evidence for ONE named target, bound to the exact sample and annotation export. Refuses absent, off-sample, wrong-target or unbound labels, and refuses to compare a predictor of one
    construct with labels of the other unless the owner has approved that mapping (``APPROVED_CONSTRUCT_MAPPINGS``, empty today)."""
    if target not in TARGETS:
        raise PolarityEvidenceError(f"target must be one of {TARGETS}")
    if not labels:
        raise PolarityEvidenceError("no reference labels: there is nothing to validate against (no result is produced)")
    in_sample = {(a, t) for t, ids in sample.by_theme.items() for a in ids}
    for lab in labels:
        if lab.target != target:
            raise PolarityEvidenceError(f"{lab.article_id}: label target {lab.target!r} differs from {target!r}; constructs are never pooled")
        if lab.export_sha256 != export_sha256:
            raise PolarityEvidenceError(f"{lab.article_id}: the label is not bound to this annotation export")
        if (lab.article_id, lab.theme) not in in_sample:
            raise PolarityEvidenceError(f"{lab.article_id}: ({lab.theme}) is not in the frozen validation sample")
    wrong = {p.construct for p in predictions if p.construct != target}
    if wrong and construct_mapping not in APPROVED_CONSTRUCT_MAPPINGS:
        raise PolarityEvidenceError(f"predictions measure {sorted(wrong)} but the labels are {target!r}: no approved mapping between the constructs")
    by_theme = {t: validate_polarity([lab for lab in labels if lab.theme == t], predictions, excluded_ids=excluded_ids, min_labelled=min_labelled)
                for t in THEMES if sample.by_theme.get(t)}
    return TargetEvidence(target, sample.manifest_sha256, export_sha256, by_theme)
