"""Hypothetical and conditional statements are not a user's current view (ADR-050 addendum, 2026-10-28), exactly like a past feeling: no sentiment label, no tone, no preference and no
evidence comes from them, and a trained model is never shown them. The rules baseline is exercised directly; no model, package, database or network is involved."""
from __future__ import annotations

import pytest

from wealthpilot.core.user_text_sentiment import NOTE_HYPOTHETICAL, ModelReading, analyse_user_text

HYPOTHETICAL_FEELINGS = [
    "If the market crashes I would be very worried about my investments",
    "If the market crashes, I would be very worried about my investments",
    "Suppose I lost my job, I would be scared about my savings and loan",
    "What if my investments fall, I might panic about my savings",
    "I will be worried about my savings only if my salary is delayed",
    "Should the stock market drop, I would feel anxious about my portfolio",
    "In case I lose my job I will be stressed about my loan",
    "Imagine my savings were gone, I would be terrified about my retirement",
    "Unless my income improves I will be anxious about my debt",
    "I wish I could stop being afraid of the stock market and my investments",
]
HYPOTHETICAL_PREFERENCES = [
    "If I had more money I would want higher returns on my investments",
    "I would prefer to protect my savings if the market gets volatile",
    "Suppose I got a bonus, I would want to pay off my loan and my debt",
    "If the market falls I would like to keep my money safe in savings",
]


@pytest.mark.parametrize("text", HYPOTHETICAL_FEELINGS)
def test_a_hypothetical_feeling_is_never_read_as_a_current_feeling(text):
    result = analyse_user_text(text)
    assert result.status == "analysed"
    assert result.sentiment == "uncertain" and result.interpretation_state == "weak"
    assert result.emotional_tone == "unknown"
    assert result.evidence == () and result.preferences == ()
    assert result.confidence is None and result.confidence_band == "unavailable"
    assert NOTE_HYPOTHETICAL in result.limitations


@pytest.mark.parametrize("text", HYPOTHETICAL_PREFERENCES)
def test_a_hypothetical_preference_is_never_read_as_a_current_preference(text):
    result = analyse_user_text(text)
    assert result.preferences == ()
    assert result.sentiment == "uncertain" and result.evidence == ()
    assert NOTE_HYPOTHETICAL in result.limitations


def test_a_current_feeling_beside_a_hypothetical_one_is_read_and_the_hypothetical_one_is_not():
    result = analyse_user_text("I am worried about my savings. If the market crashes I would be calm about my loan.")
    assert (result.sentiment, result.emotional_tone) == ("negative", "concerned")
    assert [e.label for e in result.evidence] == ["negative_cue"]
    assert all("market crashes" not in e.phrase for e in result.evidence)
    assert NOTE_HYPOTHETICAL in result.limitations          # the hypothetical "calm" was dropped, and the response says so


def test_a_consequent_is_hypothetical_across_a_comma_but_not_across_a_sentence_or_a_contrast():
    sentence = analyse_user_text("If prices fall, I would be worried about my savings. I am excited about my investments.")
    assert (sentence.sentiment, sentence.emotional_tone) == ("positive", "hopeful")
    contrast = analyse_user_text("If prices fall I would worry about my savings but I am confident about my investments")
    assert (contrast.sentiment, contrast.emotional_tone) == ("positive", "hopeful")
    consequent = analyse_user_text("If prices fall, I am worried about my savings")
    assert consequent.sentiment == "uncertain" and consequent.evidence == ()


def test_indirect_questions_and_idioms_are_not_conditions():
    assert analyse_user_text("Could you tell me if I should worry about my savings?").sentiment == "negative"
    result = analyse_user_text("I want to protect my savings if possible")
    assert [p.code for p in result.preferences] == ["capital_preservation"] and NOTE_HYPOTHETICAL not in result.limitations


def test_a_hypothetical_clause_still_counts_as_a_topic_mention_but_never_as_a_position():
    result = analyse_user_text("If the stock market falls I would be worried about my debt")
    assert set(result.topics) >= {"market", "debt"} and result.preferences == () and result.sentiment == "uncertain"


class Capturing:
    """A stand-in for a trained model: records the exact text it was shown and answers with a fixed reading. No weights, no package."""

    def __init__(self, label: str = "positive") -> None:
        self.seen: list[str] = []
        self.label = label

    def interpret(self, text: str) -> ModelReading:
        self.seen.append(text)
        return ModelReading(self.label, 0.9, True, "stand-in-v0", "UNVALIDATED_STAND_IN", class_probabilities={"positive": 0.9, "negative": 0.05, "neutral": 0.05})


def test_a_model_is_never_shown_a_hypothetical_clause_when_a_current_clause_exists():
    model = Capturing()
    analyse_user_text("I am worried about my savings. If the market crashes I would be calm about my loan.", model)
    assert len(model.seen) == 1 and "calm" not in model.seen[0] and "market crashes" not in model.seen[0] and "worried" in model.seen[0]


def test_a_model_cannot_turn_a_hypothetical_only_text_into_a_label():
    model = Capturing("positive")
    result = analyse_user_text("If the market crashes I would be very worried about my investments", model)
    assert result.sentiment == "uncertain" and result.interpretation_state == "weak"       # the rules safeguard is never overridden by a model
    assert result.confidence is None and result.sentiment_intensity is None
