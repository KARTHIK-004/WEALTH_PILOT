"""Native label -> WealthPilot label, and the result record each adapter returns (ADR-053).

The mapping is by NAME, read from the model's own `config.json` `id2label` at load time; an index order is never assumed (candidates differ in class order). The accepted native names are
positive / negative / neutral and the financial-tweet vocabulary bullish (-> positive) / bearish (-> negative), case-insensitive; the native label is always returned unchanged beside the
normalised one. Any other label is unsupported and makes the model's answer UNAVAILABLE: nothing is guessed, and an unknown label is never silently turned into neutral. Raw scores are the model's own logits; the softmax is that one model's distribution and is labelled uncalibrated, never a confidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

UNAVAILABLE_REASONS = (
    "disabled", "licence_not_verified", "format_not_allowed", "dependencies_missing", "weights_missing", "manifest_invalid", "revision_mismatch", "artifact_corrupt", "label_unsupported",
    "load_failed", "timeout", "inference_failed", "invalid_output", "invalid_configuration", "input_not_eligible",
    "loading", "internal_error", "no_candidate_approved", "registration_pending",
)
PROBABILITY_KIND = "raw_softmax_uncalibrated"
NATIVE_TO_NORMALIZED = {"positive": "positive", "bullish": "positive", "negative": "negative", "bearish": "negative", "neutral": "neutral"}


def normalise_native_label(raw: object) -> str | None:
    """The WealthPilot label for one native label, or None when it is not exactly one of the three supported names."""
    if not isinstance(raw, str):
        return None
    return NATIVE_TO_NORMALIZED.get(raw.strip().lower())


def label_order_from_id2label(id2label: object) -> tuple[str, ...] | None:
    """The native labels in logit order from a `config.json` `id2label` mapping, or None when it is not a complete, unambiguous 0..n-1 mapping of supported names."""
    if not isinstance(id2label, dict) or not id2label:
        return None
    try:
        indexed = {int(k): v for k, v in id2label.items()}
    except (TypeError, ValueError):
        return None
    if sorted(indexed) != list(range(len(indexed))):
        return None
    ordered = tuple(indexed[i] for i in range(len(indexed)))
    normalised = [normalise_native_label(v) for v in ordered]
    if None in normalised or len(set(normalised)) != len(normalised):
        return None
    return tuple(str(v).strip() for v in ordered)                      # the model's own spelling is preserved


def softmax(values: list[float]) -> list[float]:
    peak = max(values)
    exps = [math.exp(v - peak) for v in values]
    total = sum(exps)
    return [e / total for e in exps]


@dataclass(frozen=True)
class ModelResult:
    """One model's independent answer. Holds no text. `normalized_label` is None whenever the model is unavailable; it is never defaulted."""

    model_key: str
    repository: str
    revision: str
    available: bool
    unavailable_reason: str | None = None
    native_label: str | None = None
    normalized_label: str | None = None
    raw_scores: tuple[tuple[str, float], ...] | None = None          # (native label, logit)
    probabilities: tuple[tuple[str, float], ...] | None = None       # (native label, raw softmax); uncalibrated
    processing_ms: float | None = None
    role: str = "general"                                            # the slot this result fills: financial | general


def unavailable(model_key: str, repository: str, revision: str, reason: str, *, role: str = "general") -> ModelResult:
    assert reason in UNAVAILABLE_REASONS, reason
    return ModelResult(model_key, repository, revision, False, unavailable_reason=reason, role=role)


def result_from_logits(model_key: str, repository: str, revision: str, labels: tuple[str, ...], logits: object, processing_ms: float, *, role: str = "general") -> ModelResult:
    """Validate the logits (right length, finite numbers) and build the result; any defect is `invalid_output`, never a guessed label."""
    if (not isinstance(logits, (list, tuple)) or len(logits) != len(labels)
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) for v in logits)):
        return unavailable(model_key, repository, revision, "invalid_output", role=role)
    values = [float(v) for v in logits]
    probabilities = softmax(values)
    best = max(range(len(values)), key=probabilities.__getitem__)
    return ModelResult(
        model_key, repository, revision, True, native_label=labels[best], normalized_label=normalise_native_label(labels[best]),
        raw_scores=tuple(zip(labels, values)), probabilities=tuple(zip(labels, probabilities)), processing_ms=round(processing_ms, 2), role=role)
