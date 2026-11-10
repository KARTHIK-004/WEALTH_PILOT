"""Run the registered research model(s) on one text and compare (ADR-053, role slots from ADR-055). Never raises, never logs, never stores or returns the text.

The text has ALREADY passed `analyse_user_text` (length and control-character rules, privacy, language and relevance checks). Only text that analysis found eligible reaches a model; anything else
yields `input_not_eligible` and the rules baseline stands. That includes every non-English text, because the rules front end abstains on it: the research model's multilingual ability is therefore
unreachable BY DESIGN (ADR-055), not by oversight. The outcome is display-only research output.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from wealthpilot.core.sentiment import registry
from wealthpilot.core.sentiment.adapter import PRETRAINED_ROOT, BackendFactory, ResearchConfig, classify_with
from wealthpilot.core.sentiment.comparison import Comparison, ModelVsRules, Overall, compare_slots, decide_overall, model_vs_rules
from wealthpilot.core.sentiment.normalization import ModelResult, unavailable

NOT_ELIGIBLE_STATES = ("abstained", "unavailable")
Slots = Mapping[str, "tuple[registry.Candidate | None, str | None]"]


@dataclass(frozen=True)
class ResearchOutcome:
    results: tuple[ModelResult, ...]                 # one per role, in `registry.ROLES` order
    comparison: Comparison
    overall: Overall
    model_vs_rules: tuple[ModelVsRules, ...]         # one per model that answered
    eligible: bool
    ran: bool                                        # True only when at least one model was actually asked
    total_ms: float


def current_slots() -> dict[str, tuple[registry.Candidate | None, str | None]]:
    return {role: registry.slot_state(role) for role in registry.ROLES}


def run_research(text: str | None, *, rules_label: str | None, interpretation_state: str | None, config: ResearchConfig, root: Path = PRETRAINED_ROOT,
                 backend_factory: BackendFactory | None = None, slots: Slots | None = None) -> ResearchOutcome:
    started = time.perf_counter()
    slots = slots if slots is not None else current_slots()
    eligible = bool(text) and interpretation_state is not None and interpretation_state not in NOT_ELIGIBLE_STATES
    results: list[ModelResult] = []
    ran = False
    for role in registry.ROLES:
        candidate, reason = slots.get(role, (None, "no_candidate_approved"))
        if candidate is None:
            results.append(unavailable("", "", "", reason or "no_candidate_approved", role=role))        # no registered candidate: a fact about the slot, whatever the settings
        elif not config.enabled:
            results.append(unavailable(candidate.key, candidate.repository, candidate.revision, "disabled", role=role))
        elif not eligible:
            results.append(unavailable(candidate.key, candidate.repository, candidate.revision, "input_not_eligible", role=role))
        else:
            results.append(classify_with(candidate, config, text or "", role=role, root=root, backend_factory=backend_factory))
            ran = True
    comparison = compare_slots(results)
    overall = decide_overall(comparison, rules_label, interpretation_state, eligible=eligible or not config.enabled)
    per_model = tuple(model_vs_rules(r, rules_label) for r in results if r.available)
    return ResearchOutcome(tuple(results), comparison, overall, per_model, eligible, ran, round((time.perf_counter() - started) * 1000.0, 2))
