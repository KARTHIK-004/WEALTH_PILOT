"""Comparison of the research model(s) with each other and with the rules baseline (ADR-053, generalised to role slots by ADR-055). Pure functions: no I/O, no model, no text.

A SLOT is `configured` when a registered candidate fills its role; a slot with no registered candidate (reason `no_candidate_approved` / `registration_pending`) is simply absent from the comparison,
it is neither a failure nor a disagreement. With one configured model the comparison is that model against the rules reading (`single_model`); with two it is the two models against each other.
Nothing is averaged and no probability of one model is compared with another's (uncalibrated, possibly different architectures). A shared label exists only when every available model produced the
same label. Disagreement or any rules safeguard yields `uncertain`; no third classifier and no language model breaks a tie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from wealthpilot.core.sentiment.normalization import ModelResult

STATUSES = ("agreement", "disagreement", "single_model", "model_unavailable", "one_model_unavailable", "both_models_unavailable", "no_model_configured", "uncertain")
UNCERTAINTY_REASONS = ("models_disagree", "rules_disagree", "context_safeguard", "transformers_unavailable", "one_model_unavailable", "input_not_eligible", "model_label_uncertain", "no_model_registered")
RULES_ABSTAIN = (None, "uncertain", "insufficient_evidence")
NOT_CONFIGURED = ("no_candidate_approved", "registration_pending")          # slot reasons that mean "no registered candidate", as opposed to a candidate that failed


@dataclass(frozen=True)
class Comparison:
    status: str
    shared_label: str | None
    explanation: str


@dataclass(frozen=True)
class Overall:
    sentiment: str | None            # the experimental combined reading, or the rules baseline when no model answered
    source: str                      # transformer_comparison | rules_baseline_fallback
    rules_relation: str              # agrees | disagrees | rules_abstained | not_compared
    uncertainty_reason: str | None


@dataclass(frozen=True)
class ModelVsRules:
    role: str
    rules_label: str | None
    model_label: str | None
    relation: str                    # agrees | disagrees | rules_abstained | not_compared
    explanation: str


def configured(results: Sequence[ModelResult]) -> list[ModelResult]:
    return [r for r in results if r.available or r.unavailable_reason not in NOT_CONFIGURED]


def compare_models(first: ModelResult, second: ModelResult) -> Comparison:
    """The two-model case (both slots configured)."""
    a, b = first.available, second.available
    if not a and not b:
        return Comparison("both_models_unavailable", None, "Neither pretrained model produced a result, so no comparison is possible.")
    if a != b:
        return Comparison("one_model_unavailable", None, "Only one pretrained model produced a result, so the two cannot be compared; its result is shown on its own.")
    if first.normalized_label in (None, "uncertain") or second.normalized_label in (None, "uncertain"):
        return Comparison("uncertain", None, "At least one model did not give a usable label, so the comparison is uncertain.")
    if first.normalized_label == second.normalized_label:
        return Comparison("agreement", first.normalized_label, "Both pretrained models produced the same label. This is model output, not a human-validated finding.")
    return Comparison("disagreement", None, "The two pretrained models produced different labels, so no single sentiment is reported. Each model's own result is shown.")


def compare_slots(results: Sequence[ModelResult]) -> Comparison:
    """The comparison over every slot's result (the slot order is irrelevant). Handles zero, one or two configured models."""
    live = configured(results)
    if not live:
        return Comparison("no_model_configured", None, "No pretrained model is registered for research use, so only the rules-based reading is available.")
    if len(live) == 1:
        only = live[0]
        if not only.available:
            return Comparison("model_unavailable", None, "The pretrained model produced no result, so the rules-based reading is used on its own.")
        if only.normalized_label in (None, "uncertain"):
            return Comparison("uncertain", None, "The pretrained model did not give a usable label, so the result is uncertain.")
        return Comparison("single_model", only.normalized_label,
                          "One pretrained model answered, and its label is compared with the rules-based reading. Its label is model output, not a human-validated finding.")
    return compare_models(live[0], live[1])


def model_vs_rules(result: ModelResult, rules_label: str | None) -> ModelVsRules:
    label = result.normalized_label if result.available else None
    relation = "not_compared" if label is None else _relation(label, rules_label)
    text = {"agrees": "The model's label and the rules-based reading agree.", "disagrees": "The model's label differs from the rules-based reading.",
            "rules_abstained": "The rules-based reading did not commit to a label, so there is nothing to compare with.", "not_compared": "No model label was available to compare."}[relation]
    return ModelVsRules(result.role, rules_label, label, relation, text)


def decide_overall(comparison: Comparison, rules_label: str | None, rules_state: str | None, *, eligible: bool = True) -> Overall:
    """The combined experimental reading. It never feeds anything: the production sentiment, the stored risk assessment and every financial decision are unchanged."""
    if not eligible:
        return Overall(rules_label, "rules_baseline_fallback", "not_compared", "input_not_eligible")
    if comparison.status == "no_model_configured":
        return Overall(rules_label, "rules_baseline_fallback", "not_compared", "no_model_registered")
    if comparison.status in ("model_unavailable", "one_model_unavailable", "both_models_unavailable"):
        return Overall(rules_label, "rules_baseline_fallback", "not_compared", "one_model_unavailable" if comparison.status == "one_model_unavailable" else "transformers_unavailable")
    if comparison.status == "disagreement":
        return Overall("uncertain", "transformer_comparison", "not_compared", "models_disagree")
    if comparison.status == "uncertain" or comparison.shared_label is None:
        return Overall("uncertain", "transformer_comparison", "not_compared", "model_label_uncertain")
    relation = _relation(comparison.shared_label, rules_label)
    if rules_state == "weak":
        return Overall("uncertain", "transformer_comparison", relation, "context_safeguard")          # negation, hypothetical, past or quoted wording: the rules safeguards found no clear present feeling
    if relation == "disagrees":
        return Overall("uncertain", "transformer_comparison", relation, "rules_disagree")
    return Overall(comparison.shared_label, "transformer_comparison", relation, None)


def _relation(model_label: str | None, rules_label: str | None) -> str:
    if rules_label in RULES_ABSTAIN:
        return "rules_abstained"
    if model_label is None:
        return "not_compared"
    return "agrees" if model_label == rules_label else "disagrees"
