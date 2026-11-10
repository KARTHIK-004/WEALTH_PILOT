"""Edge cases of the `user_text_rules_v1` baseline (ADR-043, ADR-050), pinned as CHARACTERISATION of its current behaviour -- not as evidence that it is accurate. The sentences are invented;
there are no gold labels, no human agreement and no accuracy claim here. Each case documents what the rules do today, with an emphasis on the conservative outcomes the product relies on:
missing or blank text is unavailable, text that cannot be interpreted reliably is an ABSTENTION (`insufficient_evidence`), a negated cue is dropped and never reversed, and nothing is inferred
beyond an explicit cue.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from wealthpilot.core.user_text_sentiment import (
    EMOTIONS,
    EVIDENCE_CHARS,
    LIMITATIONS,
    MAX_TEXT_CHARS,
    METHOD_VERSION,
    PREFERENCES,
    SENTIMENTS,
    TOPICS,
    VALIDATION_STATUS,
    UserTextError,
    analyse_user_text,
    validate_text,
)


def shape(text):
    r = analyse_user_text(text)
    return r.status, r.sentiment, r.emotional_tone, list(r.topics), [p.code for p in r.preferences]


# ------------------------------------------------------------------ missing and blank text

@pytest.mark.parametrize("text", [None, "", " ", "   ", "\n", "\t", "\r\n \t \n", "   "])
def test_missing_or_blank_text_is_unavailable_not_neutral(text):
    r = analyse_user_text(text)
    assert (r.status, r.sentiment, r.emotional_tone, r.confidence) == ("unavailable", None, None, None)
    assert r.topics == () and r.preferences == () and r.evidence == () and r.requires_confirmation is False
    assert r.unavailable_reason and "No sentiment is inferred and none is assumed" in r.unavailable_reason


# ------------------------------------------------------------------ text with no usable content abstains, with a stated reason

@pytest.mark.parametrize("text, reason", [
    ("मुझे निवेश करना है और बचत भी", "unsupported_language"),                                   # Devanagari script
    ("Quiero ahorrar mas", "ambiguous_context"),                                              # three words, no financial lexicon match
    ("Mujhe naye plan ke baare mein kuch pata nahi.", "unsupported_language"),                  # transliterated Hindi: no common English words
    ("\U0001F600\U0001F600\U0001F600", "low_quality_text"), ("!!! ???", "low_quality_text"), ("12000 / 8000 / 4000", "low_quality_text"),
    ("ok", "too_short"), ("Money.", "too_short"),
    ("The train was late today and the weather is nice.", "unrelated_text"),
    ("I had a good day today.", "ambiguous_context"),
])
def test_text_that_cannot_be_interpreted_abstains_with_nothing_inferred(text, reason):
    r = analyse_user_text(text)
    assert (r.status, r.sentiment, r.emotional_tone, list(r.topics), list(r.preferences)) == ("analysed", "insufficient_evidence", "unknown", [], [])
    assert (r.abstained, r.abstain_reason, r.interpretation_state) == (True, reason, "abstained")
    assert r.evidence == () and r.confidence is None and r.requires_confirmation is False


def test_mostly_symbols_or_digits_is_low_quality_and_a_short_phrase_is_too_short():
    assert analyse_user_text("$$$ 12345 !!! ###").abstain_reason == "low_quality_text"
    assert analyse_user_text("savings help").abstain_reason == "too_short"                      # two words
    assert analyse_user_text("worry about savings").abstain_reason != "too_short"               # three words is the minimum


def test_the_language_check_uses_script_and_common_english_words_and_never_the_cue_words():
    assert shape("Mujhe naye plan ke baare mein bahut excited hoon.")[1] == "insufficient_evidence"
    assert analyse_user_text("Quiero ahorrar mas pero estoy worried.").abstain_reason == "unsupported_language"
    assert shape("I am worried about my savings")[1] == "negative"                              # ordinary English passes
    assert any("English only" in item for item in LIMITATIONS) and analyse_user_text("x").limitations[: len(LIMITATIONS)] == LIMITATIONS


# ------------------------------------------------------------------ negation: dropped, never reversed

@pytest.mark.parametrize("text, expected_sentiment, expected_tone", [
    ("I am not worried about my loan.", "uncertain", "unknown"),            # the negated cue is dropped and the opposite is not concluded
    ("I am never confident about my savings.", "uncertain", "unknown"),
    ("I'm not not worried about my savings", "uncertain", "unknown"),       # a double negation is not resolved to a positive reading
    ("Without worry, I want to invest safely with my savings.", "uncertain", "unknown"),
    ("I can't say I'm happy with my savings.", "uncertain", "unknown"),
])
def test_a_negated_cue_is_dropped_and_the_opposite_is_never_concluded(text, expected_sentiment, expected_tone):
    r = analyse_user_text(text)
    assert (r.sentiment, r.emotional_tone) == (expected_sentiment, expected_tone)
    assert r.sentiment not in ("positive", "negative") and r.evidence == ()


def test_a_negator_no_longer_hides_a_topic_word_because_a_topic_is_a_mention_not_a_position():
    """ADR-050 corrects the earlier known limitation: 'never confident about saving' now reports the `saving` topic."""
    assert shape("I am never confident about saving.")[3] == ["saving"]
    assert shape("I am confident about saving.")[3] == ["saving"]


def test_a_cue_inside_a_question_is_still_a_cue_but_a_quoted_cue_is_not_the_users_own():
    assert shape("Could you tell me if I should worry about my savings?")[:3] == ("analysed", "negative", "concerned")
    quoted = analyse_user_text('The article said "everyone should be terrified of the market" but I want to save more.')
    assert quoted.sentiment != "negative" and "terrified" not in " ".join(e.phrase for e in quoted.evidence)
    assert any("Quoted" in note for note in quoted.limitations)


# ------------------------------------------------------------------ mixed and ambiguous wording

def test_both_polarities_are_mixed_and_a_concerned_word_wins_the_tone_label():
    status, sentiment, tone, topics, prefs = shape("I'm worried but also confident about my savings.")
    assert (sentiment, tone, topics, prefs) == ("mixed", "concerned", ["saving"], [])
    assert shape("I feel hopeful about retirement.")[:4] == ("analysed", "positive", "hopeful", ["retirement"])


def test_case_and_surrounding_markup_do_not_change_the_reading_and_markup_is_returned_raw_for_the_renderer_to_escape():
    assert shape("WORRIED ABOUT MY SAVINGS")[:3] == ("analysed", "negative", "concerned")
    r = analyse_user_text("<script>alert(1)</script> I am worried about my loan")
    assert (r.sentiment, r.emotional_tone, list(r.topics)) == ("negative", "concerned", ["debt"])
    assert all(len(e.phrase) <= EVIDENCE_CHARS for e in r.evidence)
    assert any("<script>" in e.phrase for e in r.evidence)      # not interpreted, not stripped: the frontend escapes it when rendering (tests/component cases)


# ------------------------------------------------------------------ topics and preferences only when explicit; a preference is never a risk tolerance

def test_a_preference_does_not_create_a_topic_and_a_topic_does_not_create_a_preference():
    assert shape("I want to keep my savings safe.")[3:] == (["saving"], ["capital_preservation"])
    assert shape("I want a safe place for my money.")[3:] == ([], ["capital_preservation"])
    assert shape("I track my loan every month.")[3:] == (["debt"], [])


def test_a_stated_preference_and_an_emotion_stay_separate_fields_and_nothing_is_a_risk_tolerance():
    r = analyse_user_text("I'm worried about my EMI and want to pay off my loan.")
    assert (r.emotional_tone, [p.code for p in r.preferences]) == ("concerned", ["debt_reduction"])
    assert all(p.status == "unconfirmed" and p.requires_confirmation for p in r.preferences) and r.requires_confirmation is True
    names = {f.name for f in dataclasses.fields(r)}
    assert not any("risk" in n or "tolerance" in n for n in names)


def test_the_controlled_vocabularies_are_exactly_the_documented_ones():
    assert SENTIMENTS == ("positive", "negative", "neutral", "mixed", "uncertain", "insufficient_evidence")
    assert EMOTIONS == ("concerned", "hopeful", "frustrated", "calm", "neutral", "unknown")
    assert TOPICS == ("investment_risk", "saving", "debt", "goals", "liquidity", "market", "retirement", "emergency_fund")
    assert PREFERENCES == ("capital_preservation", "growth_seeking", "liquidity_access", "debt_reduction", "balanced_growth")
    assert (METHOD_VERSION, VALIDATION_STATUS) == ("user_text_rules_v1", "UNVALIDATED_BASELINE")


def test_nothing_is_returned_outside_the_vocabularies_for_a_sweep_of_inputs():
    words = ["worried", "confident", "not", "never", "invest", "safe", "savings", "loan", "emergency", "retire", "growth", "pay off", "xyzzy", "बचत", "\U0001F600"]
    for i in range(len(words)):
        for j in range(len(words)):
            r = analyse_user_text(f"I {words[i]} and {words[j]} today.")
            assert r.sentiment in SENTIMENTS and r.emotional_tone in (*EMOTIONS, None) and set(r.topics) <= set(TOPICS)
            assert {p.code for p in r.preferences} <= set(PREFERENCES) and r.confidence is None
            assert all(p.status == "unconfirmed" and p.requires_confirmation for p in r.preferences)


# ------------------------------------------------------------------ limits and control characters

def test_the_limit_is_counted_in_characters_after_collapsing_whitespace():
    assert MAX_TEXT_CHARS == 1000
    assert validate_text("a" * 1000) == "a" * 1000
    with pytest.raises(UserTextError):
        validate_text("a" * 1001)
    assert validate_text("\U0001F600" * 1000) is not None
    with pytest.raises(UserTextError):
        validate_text("\U0001F600" * 1001)
    assert validate_text("a" + " " * 3000 + "b") == "a b"            # collapsed first, so the raw length is not what is limited
    assert validate_text("   x   ") == "x" and validate_text(" \t\n ") is None


@pytest.mark.parametrize("code", [*range(0, 9), 11, 12, *range(14, 32), 127])
def test_every_control_character_is_refused_without_echoing_the_text(code):
    marker = "PRIVATE-MARKER-7731"
    with pytest.raises(UserTextError) as info:
        analyse_user_text(f"{marker} fine{chr(code)}text")
    assert marker not in str(info.value) and str(info.value) == "text contains control characters"


def test_tab_newline_carriage_return_and_ordinary_unicode_are_accepted():
    assert analyse_user_text("I want to save\tmore\r\nand ₹ matters").status == "analysed"


def test_an_over_long_text_is_refused_without_echoing_it_and_a_non_string_is_refused():
    marker = "PRIVATE-MARKER-9912"
    with pytest.raises(UserTextError) as info:
        analyse_user_text(marker * 300)
    assert marker not in str(info.value) and "1000" in str(info.value)
    for bad in (123, ["x"], {"a": 1}, b"bytes"):
        with pytest.raises(UserTextError) as info:
            analyse_user_text(bad)  # type: ignore[arg-type]
        assert str(info.value) == "text must be a string"


# ------------------------------------------------------------------ purity

def test_the_reading_is_a_pure_function_of_the_text_with_short_evidence_only():
    text = "I'm worried about losing my savings, and I want to invest more safely. " + "filler " * 40
    assert analyse_user_text(text) == analyse_user_text(text)
    r = analyse_user_text(text)
    assert all(len(e.phrase) <= EVIDENCE_CHARS for e in (*r.evidence, *(p.evidence for p in r.preferences)))
    assert not re.search(r"filler filler filler filler filler", " ".join(e.phrase for e in r.evidence))      # the text is not returned wholesale
