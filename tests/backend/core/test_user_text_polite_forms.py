"""AP8 `CONTEXT_DEPENDENT` (owner decision, 2026-10-29): a polite form ("I would like ...", "I would prefer ...") states a CURRENT want unless a condition is attached; a conditional or counterfactual polite
form is withheld. The one production-baseline change this authorised is a condition that FOLLOWS the polite clause in the same sentence (", if my income increased", ", but only if ..."); it is limited to
those two phrases. Invented sentences only; nothing here is a label, a dataset record or a measurement."""
from __future__ import annotations

import pytest

from wealthpilot.core.user_text_sentiment import NOTE_HYPOTHETICAL, ModelReading, analyse_user_text


def prefs(text: str) -> list[str]:
    return [p.code for p in analyse_user_text(text).preferences]


# ------------------------------------------------------------------------------------------------------------------------------- current polite forms are accepted
@pytest.mark.parametrize("text,expected", [
    ("I would like higher returns.", ["growth_seeking"]),
    ("I would like higher returns on my investments.", ["growth_seeking"]),
    ("I would prefer more growth in my investments.", ["growth_seeking"]),
    ("I would prefer to keep my money safe in savings.", ["capital_preservation"]),
])
def test_a_current_polite_form_is_accepted_as_a_current_preference(text, expected):
    result = analyse_user_text(text)
    assert [p.code for p in result.preferences] == expected and NOTE_HYPOTHETICAL not in result.limitations and result.sentiment == "neutral"
    assert all(p.status == "unconfirmed" and p.requires_confirmation for p in result.preferences)


def test_a_short_polite_form_without_finance_context_is_declined_by_the_relevance_gate_not_by_polite_form_handling():
    result = analyse_user_text("I would prefer more growth.")
    assert result.abstained and result.abstain_reason == "ambiguous_context" and result.preferences == ()          # "growth" is not a finance word; this is ADR-050's relevance gate, unchanged


# ------------------------------------------------------------------------------------------------------------------------------- conditional and counterfactual polite forms are withheld
@pytest.mark.parametrize("text", [
    "If I had more money, I would want higher returns.",
    "If I had more money, I would like higher returns on my investments.",
    "Had I more money I would prefer more growth in my investments.",
    "Suppose I got a bonus, I would prefer more growth in my investments.",
    "I would like higher returns on my investments if my income increased.",
    "I would like higher returns on my investments, if my income increased.",
    "I would like higher returns on my investments, but only if my income increased.",
    "I would like higher returns on my investments, unless my income fell.",
    "I would prefer more growth in my investments, provided that my income increased.",
    "I would prefer more growth in my investments, as long as my income increased.",
    "I would prefer more growth in my investments, assuming my income increased.",
    "I would like higher returns on my investments, and only if my income increased.",
])
def test_a_conditional_or_counterfactual_polite_form_is_withheld(text):
    result = analyse_user_text(text)
    assert result.preferences == () and result.sentiment == "uncertain" and result.interpretation_state == "weak" and NOTE_HYPOTHETICAL in result.limitations


def test_a_condition_in_a_later_sentence_does_not_withhold_an_earlier_current_polite_form():
    result = analyse_user_text("I would like higher returns on my investments. If my income fell I would worry about my savings.")
    assert [p.code for p in result.preferences] == ["growth_seeking"]


# ------------------------------------------------------------------------------------------------------------------------------- mixed current and conditional preferences
def test_a_current_polite_form_beside_a_conditional_one_keeps_only_the_current_preference():
    separated = analyse_user_text("I would like higher returns on my investments, but if my income fell I would like to protect my savings.")
    assert [p.code for p in separated.preferences] == ["growth_seeking"]                       # the second clause has a want of its own: it is the consequent, not a bare condition of the first
    sentences = analyse_user_text("I would like higher returns on my investments. If my income fell I would like to protect my savings.")
    assert [p.code for p in sentences.preferences] == ["growth_seeking"]


def test_the_comma_less_mixed_form_keeps_the_documented_baseline_behaviour_and_loses_the_current_part():
    joined = analyse_user_text("I would like higher returns on my investments and if my income fell I would like to protect my savings.")
    assert joined.preferences == () and joined.sentiment == "uncertain"                         # RETAIN_DOCUMENTED_BASELINE_BEHAVIOR (owner decision): the whole sentence is one conditional clause


# ------------------------------------------------------------------------------------------------------------------------------- quoted, third-person and negated polite forms
@pytest.mark.parametrize("text", [
    'My advisor said "I would like higher returns on your investments" but I am not sure.',
    'My advisor said "I would prefer more growth in your investments".',
    "My friend would like higher returns on his investments.",
    "My wife would prefer more growth in our investments but I am not sure.",
])
def test_a_quoted_or_third_person_polite_form_is_never_the_users_preference(text):
    assert prefs(text) == []


@pytest.mark.parametrize("text", ["I would not like higher returns on my investments.", "I wouldn't prefer more growth in my investments.", "I would never like higher returns on my investments."])
def test_a_negated_polite_form_is_not_a_preference_and_its_opposite_is_not_inferred(text):
    result = analyse_user_text(text)
    assert result.preferences == ()


# ------------------------------------------------------------------------------------------------------------------------------- the change is limited to the polite forms
def test_a_non_polite_want_followed_by_a_condition_is_unchanged_by_this_decision():
    assert prefs("I want higher returns on my investments, if my income increased.") == ["growth_seeking"]          # not authorised to change; a documented asymmetry
    assert prefs("I would love more growth in my investments.") == []                                                  # "would love" was never a stance phrase and is untouched
    assert prefs("I would rather keep my money safe in savings.") == ["capital_preservation"]                          # nor is "would rather"


def test_a_polite_form_with_a_trailing_condition_is_not_shown_to_a_model():
    class Capturing:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def interpret(self, text: str) -> ModelReading:
            self.seen.append(text)
            return ModelReading("positive", 0.9, True, "stand-in-v0", "UNVALIDATED_STAND_IN", class_probabilities={"positive": 0.9, "negative": 0.05, "neutral": 0.05})

    model = Capturing()
    analyse_user_text("I am worried about my savings. I would like higher returns on my investments, if my income increased.", model)
    assert len(model.seen) == 1 and "worried" in model.seen[0] and "higher returns" not in model.seen[0]


def test_the_result_is_deterministic():
    text = "I would like higher returns on my investments, if my income increased."
    assert analyse_user_text(text) == analyse_user_text(text)
