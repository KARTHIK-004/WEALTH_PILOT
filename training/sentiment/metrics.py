"""Metrics, calibration and abstention-threshold selection for the sentiment model. numpy only: no deep-learning package, no network.

Calibration: a single TEMPERATURE fitted on the VALIDATION split by minimising negative log-likelihood (the standard post-hoc method); the TEST split is never used to fit it. Expected
calibration error (ECE) is reported on the test split before and after. A raw softmax is not calibrated: the application exposes a confidence only for a model whose metadata says it
was calibrated this way and whose evidence is complete.

The abstention threshold (`min_confidence`) and the band cut-offs are NOT invented here: they are derived from the validation split for precision targets the project owner supplies
(`select_min_confidence`), and the artifact records them with the target and the coverage they give.

EVALUATION STATISTICS (second half of this module, below `regression_metrics`): offline, deterministic, standard-library + numpy support for a FUTURE approved, independently labelled
dataset: confidence intervals, annotator agreement, per-class and per-group breakdowns, coverage / abstention reporting, calibration reporting and a paired comparison with the rules
baseline. Nothing here reads a model, a file, the network or user text; it only counts labels it is handed. Its rules:

- No fabricated value and no silent default: an undefined quantity is `None` with a reason (the older `classification_report` above returns 0.0 for an undefined precision; it is unchanged because
  the training pipeline and its tests rely on it, and it must not be used for evidence reports).
- Every statistical choice (interval method, level, resamples, seed, minimum group support) travels in a required `StatisticsPlan`, and every gate in a required `EvaluationPolicy`; both are echoed in the
  output. `StatisticsPlan.owner_approved()` and `EvaluationPolicy.owner_approved()` build the values the owner approved on 2026-10-29; `approved=True` is refused for any other values.
- The approved targets and floors are GATES a report evaluates and prints (`assess_against_policy`: required, observed, met / not met / not evaluable with a reason), never an activation rule: nothing here
  enables, ranks or selects a model, intervals are reported but never gated (NO_LOWER_BOUND_ACTIVATION_RULE), and activation (R14) cannot be recommended from a report.
- Evidence status: a report is `not_validation_evidence` unless the dataset is approved, is not a development fixture or synthetic, the rubric is frozen, the manifest hashes were verified, independence is
  attested, duplicates were excluded and the splits are separate (`EvidenceBasis`). The wording is one of `validated`, `not_validation_evidence`, `descriptive_only`, `insufficient_support`; `validated` only when
  nothing is missing or unmet. A report never validates a confidence score by itself and is never an input to activation.
- Accepted-prediction precision, coverage and abstention are separate numbers. "Strict" counts an abstention as a miss; "selective" looks at the accepted predictions only, with the coverage beside it.
- Undersized groups are reported explicitly (descriptive only, no interval); the output order is deterministic and independent of the order of the input records.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from statistics import NormalDist
from typing import Mapping, Sequence

import numpy as np

from training.sentiment.config import LABELS


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = np.asarray(logits, dtype=float) / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def confusion_matrix(y_true: Sequence[int], y_pred: Sequence[int], n_classes: int = len(LABELS)) -> list[list[int]]:
    """Rows are the true class, columns the predicted class, in `LABELS` order."""
    matrix = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        matrix[int(t), int(p)] += 1
    return matrix.tolist()


def classification_report(y_true: Sequence[int], y_pred: Sequence[int], labels: Sequence[str] = LABELS) -> dict:
    matrix = np.array(confusion_matrix(y_true, y_pred, len(labels)))
    total = int(matrix.sum())
    per_class: dict[str, dict[str, float | int]] = {}
    f1s: list[float] = []
    for i, label in enumerate(labels):
        tp, support = int(matrix[i, i]), int(matrix[i].sum())
        predicted = int(matrix[:, i].sum())
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
        f1s.append(f1)
    return {"samples": total, "accuracy": float(np.trace(matrix) / total) if total else 0.0, "macro_f1": float(np.mean(f1s)) if f1s else 0.0, "per_class": per_class,
            "confusion_matrix": {"labels": list(labels), "rows_are": "true", "matrix": matrix.tolist()}}


def expected_calibration_error(probabilities: np.ndarray, y_true: Sequence[int], bins: int = 10) -> dict:
    """ECE over the top-class confidence with equal-width bins; also returns the reliability table so the error distribution is visible."""
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(y_true)
    confidence, predicted = p.max(axis=1), p.argmax(axis=1)
    correct = (predicted == y).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    table, ece = [], 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (confidence > low) & (confidence <= high) if low > 0 else (confidence >= low) & (confidence <= high)
        if not mask.any():
            continue
        accuracy, mean_confidence, weight = float(correct[mask].mean()), float(confidence[mask].mean()), float(mask.mean())
        ece += weight * abs(accuracy - mean_confidence)
        table.append({"low": float(low), "high": float(high), "count": int(mask.sum()), "accuracy": accuracy, "mean_confidence": mean_confidence})
    return {"ece": float(ece), "bins": bins, "reliability": table}


def _nll(logits: np.ndarray, y: np.ndarray, temperature: float) -> float:
    p = softmax(logits, temperature)
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1.0)).mean())


def fit_temperature(logits: np.ndarray, y_true: Sequence[int]) -> float:
    """The temperature in [0.05, 20] that minimises validation NLL (golden-section search; deterministic, no random start)."""
    z, y = np.asarray(logits, dtype=float), np.asarray(y_true)
    if len(y) == 0:
        raise ValueError("calibration needs validation examples")
    low, high, ratio = math.log(0.05), math.log(20.0), (math.sqrt(5) - 1) / 2
    a, b = high - ratio * (high - low), low + ratio * (high - low)
    fa, fb = _nll(z, y, math.exp(a)), _nll(z, y, math.exp(b))
    for _ in range(80):
        if fa < fb:
            high, b, fb = b, a, fa
            a = high - ratio * (high - low)
            fa = _nll(z, y, math.exp(a))
        else:
            low, a, fa = a, b, fb
            b = low + ratio * (high - low)
            fb = _nll(z, y, math.exp(b))
    return float(math.exp((low + high) / 2))


def select_min_confidence(probabilities: np.ndarray, y_true: Sequence[int], *, target_precision: float, min_coverage: float) -> dict:
    """The LOWEST confidence at which the accepted predictions reach `target_precision` on the validation split while still covering at least `min_coverage` of it.
    Both targets are the owner's decision. Returns `{"found": False}` when no threshold satisfies both, in which case the model must not be called validated."""
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(y_true)
    confidence, correct = p.max(axis=1), (p.argmax(axis=1) == y)
    best = None
    for threshold in sorted({float(c) for c in confidence}):
        accepted = confidence >= threshold
        coverage = float(accepted.mean())
        if coverage < min_coverage or not accepted.any():
            continue
        precision = float(correct[accepted].mean())
        if precision >= target_precision:
            best = {"found": True, "min_confidence": threshold, "precision_at_threshold": precision, "coverage": coverage, "target_precision": target_precision, "min_coverage": min_coverage}
            break
    return best or {"found": False, "target_precision": target_precision, "min_coverage": min_coverage}


def regression_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> dict:
    """MAE, RMSE, R-squared (only when the target varies, otherwise null) and the error distribution of an intensity head, all against the dataset's own intensity labels."""
    t, p = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    if len(t) == 0 or len(t) != len(p):
        raise ValueError("regression metrics need equally long, non-empty inputs")
    error = p - t
    variance = float(((t - t.mean()) ** 2).sum())
    return {"samples": int(len(t)), "mae": float(np.abs(error).mean()), "rmse": float(math.sqrt((error ** 2).mean())),
            "r2": None if variance < 1e-12 else float(1 - (error ** 2).sum() / variance),
            "absolute_error_quantiles": {str(q): float(np.quantile(np.abs(error), q)) for q in (0.5, 0.9, 0.99)}, "bias": float(error.mean())}


# ======================================================================================================================================================================================
# Evaluation statistics (offline; for a future approved dataset only -- see the module docstring)
# ======================================================================================================================================================================================

REPORT_VERSION = "sentiment_eval_stats_v1"
ABSTAINED = "abstained"          # the extra confusion-matrix column for an example the candidate declined to answer

# The values the OWNER approved on 2026-10-29 (reports/sentiment_model_approval_record.md, "Owner decisions recorded 2026-10-29 (seventeenth brief)"). They live in these two mappings and nowhere else in
# this module; every function still takes its plan / policy as an explicit argument (there is no default), and `approved=True` is accepted only for exactly these values.
OWNER_APPROVED_STATISTICS = {"confidence": 0.95, "resamples": 2000, "seed": 42, "min_group_support": 20, "min_class_support": 75}
OWNER_APPROVED_POLICY = {
    "primary_labels": LABELS, "reported_separately": ("mixed", "uncertain"), "min_heldout": 300, "min_class_support": 75, "min_coverage": 0.70, "max_abstention": 0.30,
    "macro_f1_target": 0.80, "accepted_precision_target": 0.85, "per_class_recall_floor": None, "agreement_floor": None, "ece_ceiling": None, "min_calibration_sample": 20, "bins": 10,
    "primary_agreement": "COHEN_KAPPA", "macro_f1_deciding_view": "strict", "lower_bound_rule": "NO_LOWER_BOUND_ACTIVATION_RULE",
    "multi_label_agreement": "DEFER_MULTI_LABEL_AGREEMENT", "kappa_interval": "NON_STRATIFIED_ITEM_BOOTSTRAP",
}

INTERVAL_METHODS = {"proportion": "wilson", "f1_and_paired_differences": "percentile_bootstrap (stratified by true label; paired for differences)",
                    "kappa": "percentile_bootstrap (non-stratified item bootstrap: kappa has no true class to stratify by, and no alternative was approved)"}
VALIDATION_WORDS = ("validated", "not_validation_evidence", "descriptive_only", "insufficient_support")


@dataclass(frozen=True)
class StatisticsPlan:
    """Every statistical choice, passed explicitly (there is no default plan). `StatisticsPlan.owner_approved()` builds the owner-approved one; `approved=True` is refused for any other values.
    `min_class_support` may be None only for a hand-built, unapproved plan (no class-support flag is then raised)."""

    confidence: float
    resamples: int
    seed: int
    min_group_support: int
    min_class_support: int | None
    approved: bool

    def __post_init__(self) -> None:
        if not (isinstance(self.confidence, float) and 0.0 < self.confidence < 1.0):
            raise ValueError("confidence must be a float strictly between 0 and 1")
        for name in ("resamples", "seed", "min_group_support"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
        if self.resamples < 100 or self.min_group_support < 1:
            raise ValueError("resamples must be at least 100 and min_group_support at least 1")
        if self.min_class_support is not None and (not isinstance(self.min_class_support, int) or isinstance(self.min_class_support, bool) or self.min_class_support < 1):
            raise ValueError("min_class_support must be None or a positive integer")
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a bool")
        if self.approved and {name: getattr(self, name) for name in OWNER_APPROVED_STATISTICS} != OWNER_APPROVED_STATISTICS:
            raise ValueError("approved=True is valid only for the values the owner approved")

    @classmethod
    def owner_approved(cls) -> "StatisticsPlan":
        return cls(**OWNER_APPROVED_STATISTICS, approved=True)

    def describe(self) -> dict:
        return {"status": "approved by the owner (2026-10-29)" if self.approved else "NOT the owner-approved plan (hand-built; its values carry no approval)", "confidence": self.confidence,
                "resamples": self.resamples, "seed": self.seed, "min_group_support": self.min_group_support,
                "min_class_support": self.min_class_support if self.min_class_support is not None else "not set (no class-support flag is raised)", "interval_methods": dict(INTERVAL_METHODS)}


@dataclass(frozen=True)
class EvaluationPolicy:
    """The evaluation GATES the owner approved. They are gates a report evaluates and prints, never an activation rule: nothing here enables, ranks or selects a model (activation is the separate R14
    decision, and the owner chose NO_LOWER_BOUND_ACTIVATION_RULE: intervals are reported, never gated, and a report alone never recommends activation). `None` for a floor or ceiling is an explicit owner
    choice (NO_FLOOR, REPORT_ONLY), not a missing value; every field is required. `approved=True` is refused for any values other than the owner-approved ones."""

    primary_labels: tuple[str, ...]
    reported_separately: tuple[str, ...]
    min_heldout: int
    min_class_support: int
    min_coverage: float
    max_abstention: float
    macro_f1_target: float
    accepted_precision_target: float
    per_class_recall_floor: float | None
    agreement_floor: float | None
    ece_ceiling: float | None
    min_calibration_sample: int
    bins: int
    primary_agreement: str
    macro_f1_deciding_view: str
    lower_bound_rule: str
    multi_label_agreement: str
    kappa_interval: str
    approved: bool

    def __post_init__(self) -> None:
        _check_labels(self.primary_labels)
        for name in ("min_heldout", "min_class_support", "min_calibration_sample", "bins"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("min_coverage", "max_abstention", "macro_f1_target", "accepted_precision_target"):
            value = getattr(self, name)
            if not isinstance(value, float) or not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be a float in (0, 1]")
        for name in ("per_class_recall_floor", "agreement_floor", "ece_ceiling"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, float) or not 0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be None (an explicit NO_FLOOR / REPORT_ONLY) or a float in [0, 1]")
        if abs(self.max_abstention - (1.0 - self.min_coverage)) > 1e-9:
            raise ValueError("max_abstention must equal 1 - min_coverage (the owner derived it)")
        if self.primary_agreement != "COHEN_KAPPA":
            raise ValueError("the approved primary agreement statistic is COHEN_KAPPA")
        for name, only in (("macro_f1_deciding_view", "strict"), ("lower_bound_rule", "NO_LOWER_BOUND_ACTIVATION_RULE"), ("multi_label_agreement", "DEFER_MULTI_LABEL_AGREEMENT"),
                           ("kappa_interval", "NON_STRATIFIED_ITEM_BOOTSTRAP")):
            if getattr(self, name) != only:
                raise ValueError(f"{name} must be '{only}': no other value is approved or implemented")
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a bool")
        if self.approved and {name: getattr(self, name) for name in OWNER_APPROVED_POLICY} != OWNER_APPROVED_POLICY:
            raise ValueError("approved=True is valid only for the values the owner approved")

    @classmethod
    def owner_approved(cls) -> "EvaluationPolicy":
        return cls(**OWNER_APPROVED_POLICY, approved=True)

    def describe(self) -> dict:
        return {"status": "approved by the owner (2026-10-29)" if self.approved else "NOT the owner-approved policy (hand-built; its values carry no approval)",
                "primary_labels": list(self.primary_labels), "reported_separately": list(self.reported_separately), "min_heldout": self.min_heldout, "min_class_support": self.min_class_support,
                "min_coverage": self.min_coverage, "max_abstention": self.max_abstention, "macro_f1_target": self.macro_f1_target, "accepted_precision_target": self.accepted_precision_target,
                "per_class_recall_floor": self.per_class_recall_floor if self.per_class_recall_floor is not None else "NO_FLOOR",
                "agreement_floor": self.agreement_floor if self.agreement_floor is not None else "NO_FLOOR",
                "ece_ceiling": self.ece_ceiling if self.ece_ceiling is not None else "REPORT_ONLY", "min_calibration_sample": self.min_calibration_sample, "bins": self.bins,
                "primary_agreement": self.primary_agreement, "macro_f1_deciding_view": self.macro_f1_deciding_view, "lower_bound_rule": self.lower_bound_rule,
                "multi_label_agreement": self.multi_label_agreement, "kappa_interval": self.kappa_interval,
                "meaning": "evaluation gates only: no code reads them to enable, rank or select a model; intervals are reported but never used as a gate, and activation cannot be recommended from a report: it is the separate R14 decision"}


@dataclass(frozen=True)
class EvidenceBasis:
    """What the labelled data is and how it was prepared. Every field is required: there is no default that could make a report look like evidence. A report is `eligible_for_owner_review`
    only when ALL of them hold: the dataset is approved and is neither a development fixture nor synthetic, the rubric is frozen, the manifest hashes were verified, the annotators' independence
    is attested, exact and near-duplicate exclusion was verified, and the training, calibration and held-out splits are separate."""

    dataset_approved: bool
    development_fixture: bool
    synthetic: bool
    rubric_frozen: bool
    manifest_hashes_verified: bool
    independence_attested: bool
    duplicates_excluded: bool
    splits_separate: bool

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a bool")

    def describe(self) -> dict:
        checks = ((self.dataset_approved, "the dataset is not approved"), (not self.development_fixture, "the data is a development fixture"),
                  (not self.synthetic, "the data is synthetic (a stand-in, not independent human labels)"), (self.rubric_frozen, "the rubric is not frozen"),
                  (self.manifest_hashes_verified, "the manifest hashes were not verified"), (self.independence_attested, "annotator independence is not attested"),
                  (self.duplicates_excluded, "exact and near-duplicate exclusion was not verified"),
                  (self.splits_separate, "separate training, calibration and held-out splits were not verified"))
        reasons = [message for ok, message in checks if not ok]
        status = "not_validation_evidence" if reasons else "eligible_for_owner_review"
        return {"status": status, "reasons": reasons, "validation_claimed": False, "confidence_scores_validated": False,
                "activation": "not decided here: activation is the separate R14 decision, and a report is never an input to it"}


@dataclass(frozen=True)
class EvalRecord:
    """One labelled example and one candidate's answer for it. `prediction` is None when the candidate abstained. `groups` maps a dimension (for example "topic") to a TUPLE of values."""

    item_id: str
    truth: str
    prediction: str | None
    probabilities: Mapping[str, float] | None = None
    groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


# ------------------------------------------------------------------ intervals

def wilson_interval(successes: int, n: int, confidence: float) -> dict | None:
    """The Wilson score interval for a proportion; None when there are no examples (nothing is invented)."""
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("successes must lie between 0 and n")
    if n == 0:
        return None
    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    low = 0.0 if successes == 0 else max(0.0, centre - half)
    high = 1.0 if successes == n else min(1.0, centre + half)
    return {"low": float(low), "high": float(high), "method": "wilson", "confidence": confidence}


def _percentile_interval(values: np.ndarray, plan: StatisticsPlan) -> dict | None:
    defined = values[~np.isnan(values)]
    if defined.size == 0:
        return None
    alpha = (1 - plan.confidence) / 2
    return {"low": float(np.quantile(defined, alpha)), "high": float(np.quantile(defined, 1 - alpha)), "method": "percentile_bootstrap", "confidence": plan.confidence, "resamples": plan.resamples,
            "seed": plan.seed, "undefined_replicates": int(values.size - defined.size)}


def _proportion(successes: int, n: int, plan: StatisticsPlan, withheld: str | None) -> dict:
    out: dict = {"value": None if n == 0 else successes / n, "numerator": int(successes), "denominator": int(n), "interval": None, "interval_withheld_reason": None, "unavailable_reason": None}
    if n == 0:
        out["unavailable_reason"] = "no examples in the denominator"
    elif withheld is not None:
        out["interval_withheld_reason"] = withheld
    else:
        out["interval"] = wilson_interval(successes, n, plan.confidence)
    return out


def _estimate(value: float, interval: dict | None, withheld: str | None, unavailable: str | None = None) -> dict:
    defined = value is not None and not (isinstance(value, float) and math.isnan(value))
    return {"value": float(value) if defined else None, "interval": interval if defined else None, "interval_withheld_reason": withheld if defined and interval is None else None,
            "unavailable_reason": None if defined else (unavailable or "undefined for these examples")}


# ------------------------------------------------------------------ encoding and the shared counting core

def _check_labels(labels: Sequence[str]) -> tuple[str, ...]:
    labels = tuple(labels)
    if len(labels) < 2 or len(set(labels)) != len(labels) or not all(isinstance(label, str) and label and label != ABSTAINED for label in labels):
        raise ValueError(f"labels must be at least two distinct non-empty strings, none of them '{ABSTAINED}'")
    return labels


def _encode(truth: Sequence[str], prediction: Sequence[str | None], labels: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Integer codes: the true class 0..k-1 and the answer 0..k-1, or -1 for an abstention. An unknown label is an error, never a silent class."""
    if len(truth) != len(prediction):
        raise ValueError("truth and prediction must have the same length")
    index = {label: i for i, label in enumerate(labels)}
    try:
        t = np.array([index[x] for x in truth], dtype=int)
    except KeyError as exc:
        raise ValueError(f"a true label is not one of the evaluated labels: {exc.args[0]!r}") from None
    try:
        p = np.array([-1 if x is None else index[x] for x in prediction], dtype=int)
    except KeyError as exc:
        raise ValueError(f"a predicted label is neither None (abstained) nor one of the evaluated labels: {exc.args[0]!r}") from None
    return t, p


def _canonical(records: Sequence[EvalRecord]) -> list[EvalRecord]:
    """Records in a fixed order (by item id), so no result depends on the order the caller supplied them in. Duplicate ids are an error."""
    ids = [r.item_id for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("item ids must be unique")
    for r in records:
        for dimension, values in r.groups.items():
            if not isinstance(values, (tuple, list)) or not all(isinstance(v, str) for v in values):
                raise ValueError(f"group values of '{dimension}' must be a tuple of strings (a bare string would be split into characters)")
    return sorted(records, key=lambda r: r.item_id)


def _matrices(t: np.ndarray, p: np.ndarray, k: int, rows: np.ndarray) -> np.ndarray:
    """(replicates, k, k + 1) counts: row = true class, column 0 = abstained, column c + 1 = answered as class c."""
    replicates = rows.shape[0]
    code = t[rows] * (k + 1) + (p[rows] + 1) + np.arange(replicates)[:, None] * (k * (k + 1))
    return np.bincount(code.ravel(), minlength=replicates * k * (k + 1)).reshape(replicates, k, k + 1)


def _resample_rows(t: np.ndarray, plan: StatisticsPlan) -> np.ndarray:
    """Bootstrap row indices, stratified by true label (each class keeps its size), from a fresh generator seeded by the plan: the same input always gives the same rows."""
    rng = np.random.default_rng(plan.seed)
    parts = []
    for cls in np.unique(t):
        members = np.flatnonzero(t == cls)
        parts.append(members[rng.integers(0, members.size, (plan.resamples, members.size))])
    return np.concatenate(parts, axis=1)


def _summaries(m: np.ndarray) -> dict[str, np.ndarray]:
    """Everything is derived from the counts exactly once (the point estimate and every bootstrap replicate use this one function). NaN marks an undefined value."""
    k = m.shape[1]
    tp = np.stack([m[:, c, c + 1] for c in range(k)], axis=1).astype(float)
    support = m.sum(axis=2).astype(float)
    predicted = m[:, :, 1:].sum(axis=1).astype(float)
    answered_support = support - m[:, :, 0]
    n, answered, correct = support.sum(axis=1), predicted.sum(axis=1), tp.sum(axis=1)

    def f1(true_positive: np.ndarray, truth_total: np.ndarray) -> np.ndarray:    # 2TP / (2TP + FP + FN) = 2TP / (predicted + support); undefined only when both are zero
        denominator = predicted + truth_total
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(denominator > 0, 2 * true_positive / denominator, np.nan)

    def macro(f: np.ndarray) -> np.ndarray:
        defined = ~np.isnan(f)
        count = defined.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(count > 0, np.nansum(f, axis=1) / count, np.nan)

    f1_strict, f1_selective = f1(tp, support), f1(tp, answered_support)
    with np.errstate(divide="ignore", invalid="ignore"):
        return {"tp": tp, "support": support, "predicted": predicted, "n": n, "answered": answered, "correct": correct, "f1_strict": f1_strict,
                "macro_strict": macro(f1_strict), "macro_selective": macro(f1_selective),
                "accuracy_strict": np.where(n > 0, correct / n, np.nan), "coverage": np.where(n > 0, answered / n, np.nan)}


def _summary(t: np.ndarray, p: np.ndarray, labels: tuple[str, ...], plan: StatisticsPlan, *, detail: bool) -> dict:
    k, n = len(labels), int(t.size)
    if n == 0:
        return {"status": "no_data", "samples": 0, "reason": "no examples: nothing is computed and nothing is defaulted"}
    supported = n >= plan.min_group_support
    withheld = None if supported else f"fewer than {plan.min_group_support} examples: descriptive only, no interval"
    point = _summaries(_matrices(t, p, k, np.arange(n)[None, :]))
    boot = _summaries(_matrices(t, p, k, _resample_rows(t, plan))) if supported else None
    support = point["support"][0]
    true_classes = int((support > 0).sum())
    answered = int(point["answered"][0])
    correct = int(point["correct"][0])
    macro_reason_strict = None if true_classes >= 2 else "fewer than two true classes are present, so macro-F1 is not informative"
    macro_reason_selective = macro_reason_strict or (None if answered > 0 else "the candidate answered nothing")

    def boot_interval(name: str) -> dict | None:
        return None if boot is None else _percentile_interval(boot[name], plan)

    overall = {
        "strict": {"accuracy": _proportion(correct, n, plan, withheld),
                   "macro_f1": _estimate(point["macro_strict"][0] if macro_reason_strict is None else None, boot_interval("macro_strict") if macro_reason_strict is None else None, withheld,
                                         macro_reason_strict),
                   "meaning": "an abstention counts as a miss (it lowers recall and accuracy; it does not change precision)"},
        "selective": {"accepted_precision": _proportion(correct, answered, plan, withheld),
                      "macro_f1": _estimate(point["macro_selective"][0] if macro_reason_selective is None else None, boot_interval("macro_selective") if macro_reason_selective is None else None, withheld,
                                            macro_reason_selective),
                      "meaning": "only the accepted predictions are looked at; the coverage beside it says how many that is"},
        "coverage": {"answered": answered, "abstained": n - answered, "coverage": _proportion(answered, n, plan, withheld), "abstention_rate": _proportion(n - answered, n, plan, withheld)},
    }
    out: dict = {"status": "supported" if supported else "descriptive_only", "samples": n, "interval_withheld_reason": withheld,
                 "true_class_counts": {label: int(support[i]) for i, label in enumerate(labels)}, "overall": overall}
    if detail:
        per_class = {}
        for i, label in enumerate(labels):
            s, predicted, tp = int(support[i]), int(point["predicted"][0][i]), int(point["tp"][0][i])
            f1_point = point["f1_strict"][0][i]
            per_class[label] = {
                "support": s, "predicted": predicted, "true_positive": tp,
                "undersized": None if plan.min_class_support is None else s < plan.min_class_support,
                "precision": _proportion(tp, predicted, plan, withheld), "recall": _proportion(tp, s, plan, withheld),
                "f1": _estimate(f1_point, None if boot is None else _percentile_interval(boot["f1_strict"][:, i], plan), withheld, "the class has no examples and was never predicted"),
            }
        out["per_class"] = per_class
        counts = _matrices(t, p, k, np.arange(n)[None, :])[0]      # column 0 holds the abstentions; the report lists them last, after the labels
        out["confusion_matrix"] = {"rows_are": "true", "rows": list(labels), "columns": [*labels, ABSTAINED], "matrix": np.concatenate([counts[:, 1:], counts[:, :1]], axis=1).tolist()}
    return out


# ------------------------------------------------------------------ public reports

def evaluate_predictions(records: Sequence[EvalRecord], *, labels: Sequence[str], plan: StatisticsPlan, evidence: EvidenceBasis) -> dict:
    """The full report for ONE candidate: strict and selective accuracy / macro-F1, accepted-prediction precision, coverage and abstention, per-class precision / recall / F1 with intervals, and
    the confusion matrix with its abstained column. `evidence` and `plan` are required: nothing is assumed about where the labels came from or how to interval them."""
    labels = _check_labels(labels)
    recs = _canonical(records)
    t, p = _encode([r.truth for r in recs], [r.prediction for r in recs], labels)
    body = _summary(t, p, labels, plan, detail=True)
    return {"report_version": REPORT_VERSION, "evidence": evidence.describe(), "plan": plan.describe(), "labels": list(labels), **body}


def grouped_report(records: Sequence[EvalRecord], *, labels: Sequence[str], plan: StatisticsPlan, evidence: EvidenceBasis, required_groups: Mapping[str, Sequence[str]] | None = None) -> dict:
    """The same measures per group (dimension -> value, both sorted). A record may belong to several values of a dimension. A group with no records, or fewer than `plan.min_group_support`,
    is listed explicitly and is never silently dropped or interval-estimated; `required_groups` makes an expected group appear even when no record has it."""
    labels = _check_labels(labels)
    recs = _canonical(records)
    dimensions: dict[str, set[str]] = {}
    for r in recs:
        for dimension, values in r.groups.items():
            dimensions.setdefault(dimension, set()).update(values)
    for dimension, values in (required_groups or {}).items():
        dimensions.setdefault(dimension, set()).update(values)
    groups: dict[str, dict] = {}
    not_supported: list[str] = []
    for dimension in sorted(dimensions):
        groups[dimension] = {}
        for value in sorted(dimensions[dimension]):
            subset = [r for r in recs if value in r.groups.get(dimension, ())]
            t, p = _encode([r.truth for r in subset], [r.prediction for r in subset], labels)
            entry = _summary(t, p, labels, plan, detail=False)
            groups[dimension][value] = entry
            if entry["status"] != "supported":
                not_supported.append(f"{dimension}={value} ({entry['status']}, n={entry['samples']})")
    return {"report_version": REPORT_VERSION, "evidence": evidence.describe(), "plan": plan.describe(), "labels": list(labels), "groups": groups, "groups_not_supported": not_supported}


def compare_predictions(truth: Sequence[str], first: Sequence[str | None], second: Sequence[str | None], *, labels: Sequence[str], plan: StatisticsPlan, evidence: EvidenceBasis,
                        first_name: str, second_name: str) -> dict:
    """Candidate `first` against candidate `second` (for example a model against the rules baseline) on the SAME examples: each one's own summary, the discordance counts, and the paired,
    stratified-bootstrap difference (first minus second) in strict accuracy, strict macro-F1 and coverage. No significance test and no winner is declared: the interval either contains
    zero or it does not, and choosing a model is the owner's decision."""
    labels = _check_labels(labels)
    if first_name == second_name:
        raise ValueError("the two candidates need different names")
    t, a = _encode(truth, first, labels)
    _, b = _encode(truth, second, labels)
    k, n = len(labels), int(t.size)
    out: dict = {"report_version": REPORT_VERSION, "evidence": evidence.describe(), "plan": plan.describe(), "labels": list(labels), "samples": n, "first": first_name, "second": second_name}
    if n == 0:
        return {**out, "status": "no_data", "reason": "no examples: nothing is compared"}
    supported = n >= plan.min_group_support
    withheld = None if supported else f"fewer than {plan.min_group_support} examples: descriptive only, no interval"
    first_correct, second_correct = a == t, b == t
    out["status"] = "supported" if supported else "descriptive_only"
    out["candidates"] = {first_name: _summary(t, a, labels, plan, detail=False), second_name: _summary(t, b, labels, plan, detail=False)}
    out["discordance"] = {"both_correct": int((first_correct & second_correct).sum()), f"only_{first_name}_correct": int((first_correct & ~second_correct).sum()),
                          f"only_{second_name}_correct": int((~first_correct & second_correct).sum()), "both_wrong_or_abstained": int((~first_correct & ~second_correct).sum()),
                          "meaning": "an abstention is wrong"}
    point_a, point_b = _summaries(_matrices(t, a, k, np.arange(n)[None, :])), _summaries(_matrices(t, b, k, np.arange(n)[None, :]))
    rows = _resample_rows(t, plan) if supported else None
    boot_a, boot_b = (_summaries(_matrices(t, a, k, rows)), _summaries(_matrices(t, b, k, rows))) if supported else (None, None)
    differences = {}
    for name, key in (("strict_accuracy", "accuracy_strict"), ("strict_macro_f1", "macro_strict"), ("coverage", "coverage")):
        value = point_a[key][0] - point_b[key][0]
        interval = None if boot_a is None else _percentile_interval(boot_a[key] - boot_b[key], plan)
        entry = _estimate(value, interval, withheld, "a macro-F1 is undefined for these examples")
        entry["interval_excludes_zero"] = None if entry["interval"] is None else bool(entry["interval"]["low"] > 0 or entry["interval"]["high"] < 0)
        differences[name] = entry
    out["difference_first_minus_second"] = differences
    out["significance_testing"] = "NOT_REQUIRED (owner decision, 2026-10-29): no p-value and no test statistic is produced"
    out["selection"] = "none: no candidate is ranked or selected, and nothing here enables a model"
    out["note"] = "descriptive: the paired difference and the discordance counts only; the choice is the owner's"
    return out


def calibration_report(records: Sequence[EvalRecord], *, labels: Sequence[str], plan: StatisticsPlan, evidence: EvidenceBasis, bins: int) -> dict:
    """Reliability of the model's top-class confidence against the labels. A confidence is never treated as validated here: this reports how it behaved on THESE labels, and `validated` is
    always False because validating it needs an approved dataset and an owner decision. Records without probabilities are counted and excluded, never filled in."""
    labels = _check_labels(labels)
    if not isinstance(bins, int) or bins < 1:
        raise ValueError("bins must be a positive integer")
    recs = _canonical(records)
    scored = [r for r in recs if r.probabilities is not None]
    out: dict = {"report_version": REPORT_VERSION, "evidence": evidence.describe(), "plan": plan.describe(), "labels": list(labels), "records": len(recs), "scored": len(scored),
                 "without_probabilities": len(recs) - len(scored),
                 "confidence_status": {"validated": False, "reason": "a confidence score is validated only by an approved labelled dataset AND an owner decision; this report is evidence for that decision, not the decision"}}
    if not scored:
        return {**out, "status": "no_predictions", "reason": "no record carries probabilities: nothing is computed and nothing is defaulted"}
    matrix = np.zeros((len(scored), len(labels)))
    for row, r in enumerate(scored):
        if set(r.probabilities) != set(labels) or any(not (isinstance(v, (int, float)) and math.isfinite(v) and 0.0 <= v <= 1.0) for v in r.probabilities.values()):
            raise ValueError("probabilities must have exactly one finite value in [0, 1] per evaluated label")
        matrix[row] = [float(r.probabilities[label]) for label in labels]
        if abs(matrix[row].sum() - 1.0) > 1e-3:
            raise ValueError("probabilities must sum to 1")
    index = {label: i for i, label in enumerate(labels)}
    try:
        y = np.array([index[r.truth] for r in scored], dtype=int)
    except KeyError as exc:
        raise ValueError(f"a true label is not one of the evaluated labels: {exc.args[0]!r}") from None
    accepted = np.array([r.prediction is not None for r in scored])

    def block(mask: np.ndarray) -> dict | None:
        if not mask.any():
            return None
        sub, truth = matrix[mask], y[mask]
        ece = expected_calibration_error(sub, truth, bins)
        confidence, correct = sub.max(axis=1), (sub.argmax(axis=1) == truth)
        edges = np.linspace(0.0, 1.0, bins + 1)
        table = []
        for low, high in zip(edges[:-1], edges[1:]):
            in_bin = (confidence > low) & (confidence <= high) if low > 0 else (confidence >= low) & (confidence <= high)
            count = int(in_bin.sum())
            hits = int(correct[in_bin].sum())
            supported = count >= plan.min_group_support
            table.append({"low": float(low), "high": float(high), "count": count, "accuracy": None if count == 0 else hits / count, "mean_confidence": None if count == 0 else float(confidence[in_bin].mean()),
                          "accuracy_interval": wilson_interval(hits, count, plan.confidence) if supported else None, "sparse": not supported})
        return {"samples": int(mask.sum()), "ece": ece["ece"], "bins": table}

    return {**out, "status": "supported" if len(scored) >= plan.min_group_support else "descriptive_only", "strict": block(np.ones(len(scored), dtype=bool)),
            "accepted_only": block(accepted), "views": {"strict": "every scored example, whatever its abstention (an abstention has no correctness, so this is the only strict calibration)",
                                                       "accepted_only": "only the examples the candidate answered"}, "method": "equal-width bins over the top-class confidence",
            "note": "bins below the minimum group support carry no interval and are marked sparse"}


# ------------------------------------------------------------------ D13: temperature scaling fitted on the calibration split only

TEMPERATURE_POLICY_VERSION = "d13-temperature-v1"
TEMPERATURE_METHOD = "temperature_scaling_nll_on_log_probabilities"
TEMPERATURE_FIT_SPLIT = "calibration"
TEMPERATURE_BOUNDS = (0.05, 20.0)                      # the search interval of `fit_temperature`
PROBABILITY_SUM_TOLERANCE = 1e-3                       # the tolerance of `calibration_report` and of the predictions-file gate
TEMPERATURE_REPRESENTATION = ("log-probabilities: softmax(log p) equals p, so dividing log p by T is exactly temperature scaling of the logits whenever the probabilities are a softmax output and a "
                              "one-parameter power calibration otherwise; no logit is invented, and a zero probability stays zero")


def _checked_probability_matrix(records: Sequence[EvalRecord], labels: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """The probability matrix and the true-label indices of records that ALL carry probabilities, after the D13 checks: exactly the evaluated labels, finite values in [0, 1], a sum of 1 within
    the tolerance, and a non-null predicted label that is a most-probable class. A problem is a fixed message: no id, label or probability is echoed."""
    index = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(records), len(labels)))
    truth = np.zeros(len(records), dtype=int)
    for row, r in enumerate(records):
        p = r.probabilities
        if not isinstance(p, Mapping) or set(p) != set(labels) or any(not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0) for v in p.values()):
            raise ValueError("probabilities must have exactly one finite value in [0, 1] per evaluated label")
        matrix[row] = [float(p[label]) for label in labels]
        if abs(matrix[row].sum() - 1.0) > PROBABILITY_SUM_TOLERANCE:
            raise ValueError("probabilities must sum to 1")
        if r.prediction is not None and (r.prediction not in index or matrix[row][index[r.prediction]] < matrix[row].max()):
            raise ValueError("a predicted label must be the most probable class of its probabilities")
        if r.truth not in index:
            raise ValueError("a true label is not one of the evaluated labels")
        truth[row] = index[r.truth]
    return matrix, truth


def _log_scores(matrix: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return np.log(matrix)


def fit_calibration_temperature(records: Sequence[EvalRecord], *, labels: Sequence[str], policy: EvaluationPolicy) -> dict:
    """The temperature fitted on the CALIBRATION split's probability-bearing records (pass the calibration split and nothing else; the caller never passes training or held-out records). The fit
    minimises the negative log-likelihood of the true labels over `log p / T` (deterministic golden-section search). Below `policy.min_calibration_sample` scored examples nothing is fitted: the
    status is `descriptive_only` and the temperature is None with the reason; with no probabilities at all the status is `unavailable`. A fitted temperature is a number about THESE records only."""
    labels = _check_labels(labels)
    recs = _canonical(records)
    scored = [r for r in recs if r.probabilities is not None]
    base = {"policy_version": TEMPERATURE_POLICY_VERSION, "method": TEMPERATURE_METHOD, "fit_split": TEMPERATURE_FIT_SPLIT, "representation": TEMPERATURE_REPRESENTATION,
            "bounds": list(TEMPERATURE_BOUNDS), "min_scored": policy.min_calibration_sample, "records": len(recs), "scored": len(scored)}
    if not scored:
        return {**base, "status": "unavailable", "temperature": None, "reason": "no calibration-split record carries probabilities: no temperature is fitted and none is invented"}
    matrix, truth = _checked_probability_matrix(scored, labels)
    if len(scored) < policy.min_calibration_sample:
        return {**base, "status": "descriptive_only", "temperature": None,
                "reason": f"fewer than {policy.min_calibration_sample} scored calibration examples: no temperature is fitted and calibration is descriptive-only"}
    scores = _log_scores(matrix)
    temperature = fit_temperature(scores, truth)
    low, high = TEMPERATURE_BOUNDS
    return {**base, "status": "fitted", "temperature": temperature, "reason": None, "at_search_bound": bool(temperature <= low * (1 + 1e-6) or temperature >= high * (1 - 1e-6)),
            "nll_before": _nll(scores, truth, 1.0), "nll_after": _nll(scores, truth, temperature)}


def apply_temperature(probabilities: Mapping[str, float], *, labels: Sequence[str], temperature: float) -> dict[str, float]:
    """One probability mapping rescaled by a fitted temperature (the argmax, hence any predicted label, is unchanged). Used for held-out predictions only."""
    labels = _check_labels(labels)
    if not (isinstance(temperature, float) and math.isfinite(temperature) and temperature > 0.0):
        raise ValueError("temperature must be a positive finite float")
    scaled = softmax(_log_scores(np.array([[float(probabilities[label]) for label in labels]])), temperature)[0]
    return {label: float(value) for label, value in zip(labels, scaled)}


def temperature_calibration_report(calibration_records: Sequence[EvalRecord], heldout_records: Sequence[EvalRecord], *, labels: Sequence[str], plan: StatisticsPlan, evidence: EvidenceBasis,
                                   policy: EvaluationPolicy) -> dict:
    """D13 for ONE candidate: fit the temperature on the calibration split only, apply it to the held-out probabilities only, and report the held-out calibration before and after (10 equal-width
    ECE bins, strict and accepted-only, ECE report-only). Labels, abstentions and the rules baseline are untouched (a labels-only candidate has nothing to calibrate and is reported as such).
    Calibration validates nothing and recommends nothing: `validated` stays False and activation is the separate R14 decision."""
    labels = _check_labels(labels)
    held = _canonical(heldout_records)
    if {r.item_id for r in calibration_records} & {r.item_id for r in held}:
        raise ValueError("the calibration and held-out records must be disjoint")
    fit = fit_calibration_temperature(calibration_records, labels=labels, policy=policy)
    scored = [r for r in held if r.probabilities is not None]
    if scored:
        _checked_probability_matrix(scored, labels)
    before = calibration_report(held, labels=labels, plan=plan, evidence=evidence, bins=policy.bins)
    after = None
    if scored and fit["status"] == "fitted":
        rescaled = [replace(r, probabilities=apply_temperature(r.probabilities, labels=labels, temperature=fit["temperature"])) if r.probabilities is not None else r for r in held]
        if [r.prediction for r in rescaled] != [r.prediction for r in held]:
            raise ValueError("calibration must not change a predicted label")
        after = calibration_report(rescaled, labels=labels, plan=plan, evidence=evidence, bins=policy.bins)
    if not scored:
        status, reason = "labels_only", "the candidate carries no probabilities (labels-only, like the rules baseline): there is nothing to calibrate and it stays descriptive-only"
    elif fit["status"] != "fitted":
        status, reason = fit["status"], fit["reason"]
    else:
        status, reason = "fitted_and_applied", None
    return {"policy_version": TEMPERATURE_POLICY_VERSION, "status": status, "reason": reason, "fit": fit, "applied": after is not None, "labels_changed": False, "bins": policy.bins,
            "ece_gate": "REPORT_ONLY (owner decision): ECE is reported, never gated", "heldout_uncalibrated": before, "heldout_calibrated": after,
            "validated": False, "activation_recommendation": "none: calibration is evidence for the owner, never a recommendation (NO_LOWER_BOUND_ACTIVATION_RULE; activation is the separate R14 decision)"}


# ------------------------------------------------------------------ annotator agreement

def cohen_kappa(first: Sequence[str | None], second: Sequence[str | None], labels: Sequence[str]) -> dict:
    """Cohen's kappa for two annotators over the same items. An item either one left unlabelled (None) is excluded and counted. Kappa is None, with a reason, when it is undefined (no items,
    or both annotators used a single identical label so chance agreement is 1)."""
    labels = _check_labels(labels)
    if len(first) != len(second):
        raise ValueError("the two annotators must rate the same items")
    pairs = [(a, b) for a, b in zip(first, second) if a is not None and b is not None]
    index = {label: i for i, label in enumerate(labels)}
    try:
        a = np.array([index[x] for x, _ in pairs], dtype=int)
        b = np.array([index[y] for _, y in pairs], dtype=int)
    except KeyError as exc:
        raise ValueError(f"a rating is not one of the labels: {exc.args[0]!r}") from None
    out: dict = {"items": len(first), "compared": len(pairs), "excluded_unlabelled": len(first) - len(pairs), "observed_agreement": None, "expected_agreement": None, "kappa": None, "unavailable_reason": None}
    if not pairs:
        out["unavailable_reason"] = "no item was labelled by both annotators"
        return out
    k = len(labels)
    counts = np.bincount(a * k + b, minlength=k * k).reshape(k, k).astype(float)
    n = counts.sum()
    observed = float(np.trace(counts) / n)
    expected = float((counts.sum(axis=1) * counts.sum(axis=0)).sum() / (n * n))
    out["observed_agreement"], out["expected_agreement"] = observed, expected
    if expected >= 1.0:
        out["unavailable_reason"] = "chance agreement is 1 (both annotators used one identical label throughout), so kappa is undefined"
    else:
        out["kappa"] = float((observed - expected) / (1 - expected))
    return out


def specific_agreement(first: Sequence[str | None], second: Sequence[str | None], labels: Sequence[str]) -> dict:
    """Per-label specific agreement 2 * both / (first + second); None for a label neither annotator used. Items either annotator left unlabelled are excluded."""
    labels = _check_labels(labels)
    if len(first) != len(second):
        raise ValueError("the two annotators must rate the same items")
    pairs = [(a, b) for a, b in zip(first, second) if a is not None and b is not None]
    out = {}
    for label in labels:
        both = sum(1 for a, b in pairs if a == label and b == label)
        total = sum(1 for a, _ in pairs if a == label) + sum(1 for _, b in pairs if b == label)
        out[label] = {"agreement": None if total == 0 else 2 * both / total, "both": both, "uses": total, "unavailable_reason": "neither annotator used this label" if total == 0 else None}
    return out


def krippendorff_alpha_nominal(units: Sequence[Sequence[str | None]], labels: Sequence[str]) -> dict:
    """Krippendorff's alpha for nominal labels, any number of annotators, missing ratings allowed (None). A unit with fewer than two ratings carries no agreement information and is excluded
    and counted. Alpha is None, with a reason, when it is undefined (fewer than two usable ratings overall, or all ratings identical so there is no expected disagreement)."""
    labels = _check_labels(labels)
    index = {label: i for i, label in enumerate(labels)}
    k = len(labels)
    coincidence = np.zeros((k, k))
    used = 0
    for unit in units:
        ratings = [x for x in unit if x is not None]
        try:
            codes = [index[x] for x in ratings]
        except KeyError as exc:
            raise ValueError(f"a rating is not one of the labels: {exc.args[0]!r}") from None
        if len(codes) < 2:
            continue
        used += 1
        for i, c in enumerate(codes):
            for j, d in enumerate(codes):
                if i != j:
                    coincidence[c, d] += 1 / (len(codes) - 1)
    out: dict = {"units": len(units), "units_used": used, "units_excluded": len(units) - used, "alpha": None, "unavailable_reason": None}
    total = coincidence.sum()
    marginals = coincidence.sum(axis=1)
    expected_total = float(marginals.sum() ** 2 - (marginals ** 2).sum())
    if total <= 1 or expected_total <= 0:
        out["unavailable_reason"] = "fewer than two usable ratings, or every rating is identical, so alpha is undefined"
        return out
    observed_disagreement = float(total - np.trace(coincidence))
    out["alpha"] = float(1 - (total - 1) * observed_disagreement / expected_total)
    return out


def agreement_report(ratings: Mapping[str, Sequence[str | None]], *, labels: Sequence[str], plan: StatisticsPlan, policy: EvaluationPolicy) -> dict:
    """Agreement between named annotators who rated the same items in the same order: every pair (sorted by name) with kappa, a paired bootstrap interval, observed agreement and
    per-label specific agreement, plus Krippendorff's alpha across all annotators. Interval withheld below `plan.min_group_support` items."""
    labels = _check_labels(labels)
    names = sorted(ratings)
    if len(names) < 2:
        raise ValueError("agreement needs at least two annotators")
    n_items = {len(ratings[name]) for name in names}
    if len(n_items) != 1:
        raise ValueError("every annotator must rate the same items in the same order")
    items = n_items.pop()
    supported = items >= plan.min_group_support
    withheld = None if supported else f"fewer than {plan.min_group_support} items: descriptive only, no interval"
    pairs = {}
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            entry = cohen_kappa(ratings[first], ratings[second], labels)
            interval = None
            if supported and entry["kappa"] is not None:
                keep = [x for x, (a, b) in enumerate(zip(ratings[first], ratings[second])) if a is not None and b is not None]
                a = np.array([labels.index(ratings[first][x]) for x in keep])
                b = np.array([labels.index(ratings[second][x]) for x in keep])
                rng = np.random.default_rng(plan.seed)
                rows = rng.integers(0, len(keep), (plan.resamples, len(keep)))
                k = len(labels)
                code = a[rows] * k + b[rows] + np.arange(plan.resamples)[:, None] * (k * k)
                counts = np.bincount(code.ravel(), minlength=plan.resamples * k * k).reshape(plan.resamples, k, k).astype(float)
                n = counts.sum(axis=(1, 2))
                observed = np.trace(counts, axis1=1, axis2=2) / n
                expected = (counts.sum(axis=2) * counts.sum(axis=1)).sum(axis=1) / (n * n)
                with np.errstate(divide="ignore", invalid="ignore"):
                    kappas = np.where(expected < 1.0, (observed - expected) / (1 - expected), np.nan)
                interval = _percentile_interval(kappas, plan)
            pairs[f"{first} | {second}"] = {**entry, "kappa_interval": interval, "interval_withheld_reason": withheld if entry["kappa"] is not None and interval is None else None,
                                            "specific_agreement": specific_agreement(ratings[first], ratings[second], labels)}
    units = [[ratings[name][x] for name in names] for x in range(items)]
    return {"report_version": REPORT_VERSION, "plan": plan.describe(), "labels": list(labels), "annotators": names, "items": items, "pairs": pairs,
            "primary_statistic": policy.primary_agreement, "agreement_floor": policy.agreement_floor if policy.agreement_floor is not None else "NO_FLOOR (reported, not gated)",
            "secondary_statistics": ["specific_agreement (per pair, per label)", "krippendorff_alpha"], "krippendorff_alpha": krippendorff_alpha_nominal(units, labels), "kappa_interval_method": policy.kappa_interval,
            "multi_label": {"status": "deferred", "decision": policy.multi_label_agreement, "reason": "topics and preferences stay descriptive and no multi-label agreement claim is made (owner decision, 2026-10-29); nothing is computed for them"},
            "basis": "the ratings must be the independent PRE-adjudication labels of the annotators; the adjudicated labels are the final reference and are not an input here",
            "note": "agreement is measured on the supplied labels only; the independence of the annotators is the owner's attestation, not something this code can check"}


_COMPLETE = ("met", "reported", "not_applicable")


def _gate(name: str, required: object, observed: object, status: str, reason: str | None = None, *, informational: bool = False) -> dict:
    return {"gate": name, "required": required, "observed": observed, "status": status, "reason": reason, "informational": informational}


def _at_least(name: str, required: float, observed: float | int | None, why_undefined: str) -> dict:
    if observed is None:
        return _gate(name, required, None, "not_evaluable", why_undefined)
    return _gate(name, required, observed, "met" if observed >= required else "not_met")


def _at_most(name: str, required: float, observed: float | None, why_undefined: str) -> dict:
    if observed is None:
        return _gate(name, required, None, "not_evaluable", why_undefined)
    return _gate(name, required, observed, "met" if observed <= required else "not_met")


def assess_against_policy(summary: dict, *, policy: EvaluationPolicy, calibration: dict | None, agreement: dict | None, calibration_fit: dict | None = None) -> dict:
    """Evaluates ONE candidate's `evaluate_predictions` report against the owner-approved gates and returns the validation wording. It prints, for every gate, the required value, the observed value
    and `met`, `not_met` or `not_evaluable` with the reason; it never ranks or selects a candidate and never enables anything. The wording is one of `validated`, `not_validation_evidence`,
    `descriptive_only`, `insufficient_support` (`validated` only when nothing is missing or unmet). The macro-F1 gate is decided by the STRICT view (the selective view is reported beside it)."""
    if summary.get("report_version") != REPORT_VERSION or "labels" not in summary or "evidence" not in summary:
        raise ValueError("the summary must be the output of evaluate_predictions")
    if summary["labels"] != list(policy.primary_labels):
        raise ValueError("the report is not on the approved primary label set, so it cannot be assessed against the policy")
    evidence, overall, classes = summary["evidence"], summary.get("overall"), summary.get("per_class") or {}
    gates = [_gate("evidence_basis", "eligible_for_owner_review", evidence["status"], "met" if evidence["status"] == "eligible_for_owner_review" else "not_met", "; ".join(evidence["reasons"]) or None)]
    approved = policy.approved and summary["plan"]["status"].startswith("approved")
    gates.append(_gate("approved_policy_and_plan", True, approved, "met" if approved else "not_met", None if approved else "the policy or the statistics plan is not the owner-approved one"))
    gates.append(_at_least("support:heldout_size", policy.min_heldout, summary["samples"], "no examples"))
    for label in policy.primary_labels:
        gates.append(_at_least(f"support:class:{label}", policy.min_class_support, classes[label]["support"] if classes else 0, "no examples"))

    def value(*path: str) -> float | None:
        node = overall
        for part in path:
            node = None if node is None else node.get(part)
        return None if node is None else node.get("value")

    none = "the value is undefined for these examples"
    gates.append(_at_least("target:macro_f1:strict", policy.macro_f1_target, value("strict", "macro_f1"), none))
    selective_f1 = value("selective", "macro_f1")
    gates.append(_gate("report:macro_f1:selective", policy.macro_f1_target, selective_f1, "reported" if selective_f1 is not None else "not_evaluable",
                       "reported beside the deciding strict view; it does not decide the gate (owner decision, 2026-10-29)" if selective_f1 is not None else none, informational=True))
    gates.append(_at_least("target:accepted_prediction_precision", policy.accepted_precision_target, value("selective", "accepted_precision"), none))
    gates.append(_at_least("coverage:minimum", policy.min_coverage, value("coverage", "coverage"), none))
    gates.append(_at_most("coverage:maximum_abstention", policy.max_abstention, value("coverage", "abstention_rate"), none))
    for label in policy.primary_labels:
        if policy.per_class_recall_floor is None:
            gates.append(_gate(f"floor:recall:{label}", "NO_FLOOR", classes[label]["recall"]["value"] if classes else None, "not_applicable", "NO_FLOOR (owner decision)"))
        else:
            gates.append(_at_least(f"floor:recall:{label}", policy.per_class_recall_floor, classes[label]["recall"]["value"] if classes else None, none))
    strict = None if calibration is None else calibration.get("strict")
    if strict is None:
        gates.append(_gate("calibration", "reported with enough examples", None, "not_evaluable", "no calibration report with scored examples was supplied"))
    elif strict["samples"] < policy.min_calibration_sample:
        gates.append(_gate("calibration", f"at least {policy.min_calibration_sample} scored examples", strict["samples"], "descriptive_only", "calibration is descriptive-only below the minimum sample"))
    elif policy.ece_ceiling is None:
        gates.append(_gate("calibration", "REPORT_ONLY", strict["ece"], "reported", "ECE is reported, not gated (owner decision)"))
    else:
        gates.append(_at_most("calibration", policy.ece_ceiling, strict["ece"], none))
    if calibration_fit is not None:                      # D13: supplied only by the frozen-evaluation path; the temperature is fitted on the calibration split alone
        if calibration_fit["status"] == "fitted":
            gates.append(_gate("temperature_calibration", f"temperature fitted on the {calibration_fit['fit_split']} split only", calibration_fit["temperature"], "reported", "reported, not gated (owner decision)"))
        elif calibration_fit["status"] == "descriptive_only":
            gates.append(_gate("temperature_calibration", f"at least {calibration_fit['min_scored']} scored calibration examples", calibration_fit["scored"], "descriptive_only", calibration_fit["reason"]))
        else:
            gates.append(_gate("temperature_calibration", f"temperature fitted on the {calibration_fit['fit_split']} split only", None, "not_evaluable", calibration_fit["reason"]))
    if agreement is None:
        gates.append(_gate("agreement", policy.primary_agreement, None, "not_evaluable", "no agreement report was supplied"))
    else:
        if agreement.get("primary_statistic") != policy.primary_agreement:
            raise ValueError("the agreement report does not use the approved primary statistic")
        kappas = {pair: entry["kappa"] for pair, entry in agreement["pairs"].items()}
        defined = [k for k in kappas.values() if k is not None]
        if not defined:
            gates.append(_gate("agreement", policy.primary_agreement, kappas, "not_evaluable", "kappa is undefined for every annotator pair"))
        elif policy.agreement_floor is None:
            gates.append(_gate("agreement", "NO_FLOOR", kappas, "reported", "agreement is reported, not gated (owner decision)"))
        else:
            gates.append(_at_least("agreement", policy.agreement_floor, min(defined), none))
    gates += [_gate("interval_lower_bound_rule", policy.lower_bound_rule, "intervals reported beside every estimate", "not_applicable",
                    "intervals are reported only and are never a gate; a point estimate passing is not validation and no report recommends activation (owner decision, 2026-10-29)", informational=True),
              _gate("rules_baseline_comparison", "paired differences and discordance", "reported by compare_predictions", "reported", "no winner is declared automatically", informational=True),
              _gate("significance_testing", "NOT_REQUIRED", "none", "not_applicable", "no p-value and no new dependency (owner decision)", informational=True)]
    required = [g for g in gates if not g["informational"]]
    incomplete = [g for g in required if g["status"] not in _COMPLETE]
    if evidence["status"] != "eligible_for_owner_review":
        word = "not_validation_evidence"
    elif any(g["gate"].startswith("support:") and g["status"] != "met" for g in required):
        word = "insufficient_support"
    elif incomplete:
        word = "descriptive_only"
    else:
        word = "validated"
    return {"report_version": REPORT_VERSION, "policy": policy.describe(), "validation": {"status": word, "unmet_or_missing": [f"{g['gate']}: {g['status']}" for g in incomplete], "words": list(VALIDATION_WORDS)},
            "gates": gates, "activation": "not decided here: activation is the separate R14 decision", "activation_recommendation": "none: a metric report alone never recommends activation (NO_LOWER_BOUND_ACTIVATION_RULE)",
            "selection": "none: no candidate is ranked or selected"}


def evaluation_report(records: Sequence[EvalRecord], *, labels: Sequence[str], plan: StatisticsPlan, evidence: EvidenceBasis, policy: EvaluationPolicy,
                      agreement: dict | None = None, required_groups: Mapping[str, Sequence[str]] | None = None, calibration_fit: dict | None = None) -> dict:
    """The overall report, the per-group breakdown, the calibration report (strict and accepted-only) and, on the approved primary label set, the assessment against the gates, for ONE candidate.
    `agreement` is an `agreement_report` (or None, which the assessment reports as not evaluable). It states what was measured and on what evidence; it decides nothing."""
    summary = evaluate_predictions(records, labels=labels, plan=plan, evidence=evidence)
    calibration = calibration_report(records, labels=labels, plan=plan, evidence=evidence, bins=policy.bins)
    assessment = (assess_against_policy(summary, policy=policy, calibration=calibration, agreement=agreement, calibration_fit=calibration_fit) if list(labels) == list(policy.primary_labels)
                  else {"validation": {"status": "not_validation_evidence", "reason": "the labels are not the approved primary label set; this report is secondary and is not assessed against the gates"}})
    return {"report_version": REPORT_VERSION, "summary": summary, "groups": grouped_report(records, labels=labels, plan=plan, evidence=evidence, required_groups=required_groups),
            "calibration": calibration, "assessment": assessment}
