"""Composition of the personalised insight (Research Enhancement Track, ADR-043): behaviour facts + optional user-text reading + the existing risk assessment.

Pure and deterministic: no database, clock, ML or LLM; the sentences are templates over values that were already computed. It is DISPLAY ONLY.

- Financial behaviour is the primary evidence. Text sentiment is secondary and optional: with no text, or text that is low-information, the insight is still valid.
- Precedence: the existing risk assessment (and the questionnaire it rests on) is authoritative; a preference inferred from text is `unconfirmed` and never replaces it. If the two disagree
  the disagreement is reported as a `conflict` and the assessment stays in force.
- Nothing here changes a risk profile, a goal, an allocation, a recommendation or a compliance decision, and no sentiment label is an input to any of them. It never says what to buy or sell.
- Every statement names the source fields it rests on.
"""

from __future__ import annotations

from dataclasses import dataclass

from wealthpilot.core.behaviour_findings import BehaviourFindings
from wealthpilot.core.user_text_sentiment import ABSTAIN_MESSAGES, UserTextAnalysis

COMPOSER_VERSION = "personalized_insight_v2"
# Only these pairings are treated as a disagreement, because the existing assessment categories (Conservative / Income / Balanced / Aggressive) make them unambiguous.
_CONFLICTS = {("capital_preservation", "Aggressive"), ("growth_seeking", "Conservative"), ("growth_seeking", "Income")}
PURPOSE = "Informational only. It does not change your risk profile, goals, allocation or any recommendation, and it is not financial advice."


@dataclass(frozen=True)
class RiskProfileView:
    category: str
    source: str                           # e.g. the stored risk assessment of the latest analysis
    assessed_at: str | None


@dataclass(frozen=True)
class Statement:
    text: str
    sources: tuple[str, ...]
    kind: str                             # behaviour_fact | stated_by_user | risk_assessment | caveat


@dataclass(frozen=True)
class Conflict:
    code: str                             # the inferred preference code
    detail: str
    inferred_preference: str = ""
    stored_category: str = ""
    authoritative_source: str = ""        # the source that stays in force (the stored assessment)
    preference_status: str = "unconfirmed"
    action: str = "confirm_or_correct"


@dataclass(frozen=True)
class PersonalizedInsight:
    version: str
    status: str                           # complete | behaviour_only | profile_only | unavailable
    statements: tuple[Statement, ...]
    conflicts: tuple[Conflict, ...]
    caveats: tuple[str, ...]
    purpose: str = PURPOSE


def compose_insight(findings: BehaviourFindings, text: UserTextAnalysis | None, risk: RiskProfileView | None) -> PersonalizedInsight:
    statements: list[Statement] = []
    for f in findings.findings:
        if f.status == "observed" and f.category in ("trend", "activity", "ratio", "data_quality", "coverage"):
            statements.append(Statement(f.statement, f.sources, "behaviour_fact"))
    has_behaviour = any(s.kind == "behaviour_fact" for s in statements) and findings.observation_count > 0
    caveats = [f.statement for f in findings.findings if f.status in ("unavailable", "not_included")]
    conflicts: list[Conflict] = []
    if risk is not None:
        statements.append(Statement(f"Your stored risk assessment is {risk.category} ({risk.source}); it remains the profile in force.", ("risk_assessment",), "risk_assessment"))
    else:
        caveats.append("No stored risk assessment was found for this profile.")
    has_text = text is not None and text.status == "analysed" and not text.abstained
    if text is None or text.status != "analysed":
        caveats.append(text.unavailable_reason if text is not None and text.unavailable_reason else "No text was provided, so no sentiment is shown and none is assumed.")
    elif text.abstained:
        caveats.append(ABSTAIN_MESSAGES.get(text.abstain_reason or "", ABSTAIN_MESSAGES["no_usable_evidence"]) + " No sentiment or preference is inferred.")
    else:
        if text.sentiment is not None:
            tone = f"; the wording suggests {text.emotional_tone}" if text.emotional_tone not in (None, "neutral", "unknown") else ""
            statements.append(Statement(f"From the text you wrote, the overall tone reads as {text.sentiment}{tone}. This is an automatic reading, not a fact about you, and not a risk score.", ("user_text.sentiment",), "stated_by_user"))
        for p in text.preferences:
            label = p.code.replace("_", " ")
            statements.append(Statement(f"You may prefer {label} (from: \"{p.evidence.phrase}\"). This is an unconfirmed interpretation of your text, not an official risk assessment, and it changes nothing until you confirm it.", ("user_text.preferences",), "stated_by_user"))
            if risk is not None and (p.code, risk.category) in _CONFLICTS:
                conflicts.append(Conflict(
                    p.code,
                    f"The text suggests {label} language, but the stored assessment is {risk.category}. The stored assessment remains in force. This interpretation is unconfirmed; confirm or correct it.",
                    p.code, risk.category, risk.source))
        if text.sentiment == "uncertain":
            caveats.append("The text could not be read reliably (for example it only contained a negated expression); no preference was inferred.")
        if text.interpretation_state == "weak":
            caveats.append("This is a weak interpretation: the text gave little explicit evidence.")
        if text.fallback_used:
            caveats.append("The validated sentiment model was unavailable. The result uses the rules baseline.")
        if text.disagreement:
            caveats.append("The sentiment model and the rules baseline read this text differently; both readings are shown and neither is a fact about you.")
        caveats.append("Text readings are informational only." + (" The rules baseline is unvalidated and reports no confidence." if text.confidence is None else ""))
    if has_behaviour:
        status = "complete" if has_text and risk is not None else "behaviour_only"
    else:
        status = "profile_only" if has_text or risk is not None else "unavailable"
    return PersonalizedInsight(COMPOSER_VERSION, status, tuple(statements), tuple(conflicts), tuple(dict.fromkeys(caveats)))


__all__ = ["COMPOSER_VERSION", "Conflict", "PURPOSE", "PersonalizedInsight", "RiskProfileView", "Statement", "compose_insight"]
