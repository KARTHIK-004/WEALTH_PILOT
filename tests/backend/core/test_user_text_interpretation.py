"""ADR-050 -- the multi-stage interpretation pipeline of `core/user_text_sentiment.py`: validation -> language / quality -> financial relevance -> clause analysis (negation, third person, quotes,
past feelings) -> sentiment and tone -> topics -> explicit preferences -> abstention. Invented sentences only; no accuracy is measured or claimed (the baseline stays UNVALIDATED_BASELINE)."""

from __future__ import annotations

import pytest

from wealthpilot.core import user_text_sentiment as module
from wealthpilot.core.user_text_sentiment import (
    EVIDENCE_CHARS, MAX_EVIDENCE_ITEMS, MAX_TEXT_CHARS, MIN_LETTER_RATIO, MIN_WORDS, ModelReading, UserTextError, analyse_user_text,
)


def codes(r):
    return [p.code for p in r.preferences]


# ------------------------------------------------------------------ stage 3: financial relevance (the spec's examples)

@pytest.mark.parametrize("text, relevance, abstains", [
    ("I am worried about losing money in the market.", "relevant", False),
    ("I had a good day today.", "ambiguous", True),
    ("The weather is beautiful.", "unrelated", True),
    ("I went to the market to buy vegetables.", "ambiguous", True),                       # a word with two meanings next to everyday talk
    ("I feel really nervous today.", "ambiguous", True),                                   # an emotion with no financial context at all
    ("I want to buy a house next year.", "relevant", False),                               # a goal statement
])
def test_relevance_is_decided_before_any_sentiment_and_a_non_relevant_text_abstains(text, relevance, abstains):
    r = analyse_user_text(text)
    assert r.financial_relevance == relevance and r.abstained is abstains
    if abstains:
        assert (r.sentiment, r.emotional_tone, r.preferences, r.topics, r.evidence, r.requires_confirmation) == ("insufficient_evidence", "unknown", (), (), (), False)
        assert r.abstain_reason in ("unrelated_text", "ambiguous_context") and r.interpretation_state == "abstained"


def test_an_unrelated_text_never_receives_a_forced_label_even_with_strong_emotion_words():
    r = analyse_user_text("The weather is awful and I am so angry and worried about the traffic.")
    assert (r.financial_relevance, r.sentiment, r.emotional_tone, r.abstained) == ("unrelated", "insufficient_evidence", "unknown", True)


# ------------------------------------------------------------------ stage 2: text quality and language

@pytest.mark.parametrize("text, reason", [
    ("Money.", "too_short"), ("savings help", "too_short"),
    ("$$$ 12345 !!! ###", "low_quality_text"), ("\U0001F600" * 40, "low_quality_text"),
    ("मुझे अपनी बचत और निवेश की चिंता है", "unsupported_language"),
    ("我很担心我的储蓄和投资", "unsupported_language"),
    ("Estoy preocupado por mis ahorros y mi dinero en el mercado", "unsupported_language"),
])
def test_unusable_or_unsupported_text_abstains_with_the_right_reason(text, reason):
    r = analyse_user_text(text)
    assert (r.sentiment, r.abstained, r.abstain_reason, r.financial_relevance) == ("insufficient_evidence", True, reason, r.financial_relevance)
    assert r.preferences == () and r.topics == () and r.evidence == ()


def test_the_quality_thresholds_are_configuration_and_their_boundaries_hold():
    assert MIN_WORDS == 3 and MIN_LETTER_RATIO == 0.5
    assert analyse_user_text("worry about savings").abstain_reason != "too_short"
    assert analyse_user_text("worry savings").abstain_reason == "too_short"
    mostly_digits = "savings 123456789012345678901234567890"
    assert analyse_user_text(mostly_digits).abstain_reason == "low_quality_text"


def test_mixed_scripts_below_the_share_limit_are_still_read_and_above_it_are_declined():
    assert analyse_user_text("I am worried about my savings and my loan निवेश").abstained is False         # a stray non-Latin word
    assert analyse_user_text("निवेश बचत बचत I worry").abstain_reason in ("unsupported_language", "too_short")


# ------------------------------------------------------------------ stage 4-5: negation, third person, quotes, past feelings

def test_a_negated_worry_is_not_read_as_calm_or_as_a_risk_preference():
    r = analyse_user_text("I am not worried about losing money.")
    assert (r.sentiment, r.emotional_tone, r.interpretation_state, r.preferences, r.evidence) == ("uncertain", "unknown", "weak", (), ())
    assert r.financial_relevance == "relevant" and "investment_risk" in r.topics
    assert any("not read as its opposite" in item for item in r.limitations)


def test_a_past_feeling_is_not_the_current_one():
    r = analyse_user_text("I used to be afraid of risk, but now I am comfortable.")
    assert (r.sentiment, r.emotional_tone) == ("positive", "calm") and [e.phrase for e in r.evidence] == ["now I am comfortable"]
    assert any("past" in item for item in r.limitations)
    only_past = analyse_user_text("I used to be afraid of losing my savings.")
    assert only_past.sentiment != "negative" and only_past.evidence == ()


def test_another_persons_feeling_is_not_the_users_own():
    r = analyse_user_text("My friend is nervous about the market, not me.")
    assert (r.abstained, r.sentiment, r.evidence) == (True, "insufficient_evidence", ())
    both = analyse_user_text("My brother is terrified of the market. I am confident about my savings.")
    assert (both.sentiment, both.emotional_tone) == ("positive", "hopeful") and "terrified" not in " ".join(e.phrase for e in both.evidence)
    assert any("other people" in item for item in both.limitations)
    he = analyse_user_text("He is worried about his loan and I feel calm about my savings.")
    assert he.sentiment == "positive"


def test_a_quoted_phrase_is_not_the_users_own_view():
    r = analyse_user_text('People say "you will lose everything" but I feel confident about my investments.')
    assert (r.sentiment, r.emotional_tone) == ("positive", "hopeful")
    assert "lose everything" not in " ".join(e.phrase for e in r.evidence)
    assert any("Quoted" in item for item in r.limitations)


def test_conflicting_cues_are_mixed_not_averaged_and_the_concerned_tone_wins_the_single_tone_field():
    r = analyse_user_text("I am excited about my retirement plans but anxious about my debt.")
    assert (r.sentiment, r.emotional_tone) == ("mixed", "concerned") and len(r.evidence) == 2
    assert {"retirement", "debt"} <= set(r.topics)


def test_frustration_and_calm_are_distinct_tones():
    assert analyse_user_text("I am frustrated with my loan payments.").emotional_tone == "frustrated"
    assert analyse_user_text("I am relaxed about my savings.").emotional_tone == "calm"
    assert analyse_user_text("I am frustrated and worried about my loan.").emotional_tone == "concerned"


def test_a_relevant_text_with_no_affect_cue_has_a_neutral_tone_and_is_weak():
    r = analyse_user_text("I track my loan every month.")
    assert (r.sentiment, r.emotional_tone, r.interpretation_state) == ("neutral", "neutral", "weak")


# ------------------------------------------------------------------ stage 6-7: topics and explicit preferences

def test_the_extended_topics_are_found():
    assert {"market", "investment_risk"} <= set(analyse_user_text("The market crash makes investing feel risky to me.").topics)
    assert "retirement" in analyse_user_text("I think about my retirement savings.").topics
    assert {"emergency_fund", "liquidity"} <= set(analyse_user_text("I need cash for emergencies.").topics)


@pytest.mark.parametrize("text, expected", [
    ("I want to protect my savings and avoid losing money.", "capital_preservation"),
    ("I do not want to lose my savings.", "capital_preservation"),
    ("I want my investments to be low risk.", "capital_preservation"),
    ("I want higher returns on my savings.", "growth_seeking"),
    ("I want to grow my investments.", "growth_seeking"),
    ("I am nervous about the market, but I am comfortable taking long-term risk.", "growth_seeking"),
    ("I want easy access to my money for emergencies.", "liquidity_access"),
    ("I need to keep cash in my savings account.", "liquidity_access"),
    ("I want to pay off my loan faster.", "debt_reduction"),
    ("I want to get out of debt.", "debt_reduction"),
    ("I want a balanced portfolio for my savings.", "balanced_growth"),
])
def test_an_explicit_preference_is_extracted_unconfirmed_with_bounded_evidence(text, expected):
    r = analyse_user_text(text)
    assert expected in codes(r)
    p = next(p for p in r.preferences if p.code == expected)
    assert (p.status, p.requires_confirmation) == ("unconfirmed", True) and 0 < len(p.evidence.phrase) <= EVIDENCE_CHARS and r.requires_confirmation is True


def test_a_generic_word_is_a_preference_only_after_a_first_person_stance_verb():
    assert codes(analyse_user_text("I want to invest safely.")) == ["capital_preservation"]
    assert codes(analyse_user_text("The safe option in my savings account is boring.")) == []
    assert codes(analyse_user_text("I am repaying my loan every month.")) == []                       # a fact about repayment is not a wish to pay off
    assert codes(analyse_user_text("My friend wants to invest safely and I track my savings.")) == []


def test_no_preference_comes_from_weak_evidence_or_unrelated_text():
    for text in ("I think about my savings a lot.", "I had a good day and want to be safe.", "The weather is nice and I want growth.", "I feel nervous about the market."):
        assert analyse_user_text(text).preferences == (), text


def test_a_negated_statement_does_not_create_the_opposite_preference():
    r = analyse_user_text("I am not worried about risk.")
    assert r.preferences == () and r.sentiment == "uncertain"
    assert codes(analyse_user_text("I do not want to protect my savings at all.")) == []             # the negated preference is dropped, and growth is not concluded


def test_opposing_explicit_preferences_are_both_withheld_and_the_reading_is_weak():
    r = analyse_user_text("I want higher returns but I also want to protect my savings.")
    assert r.preferences == () and r.interpretation_state == "weak" and any("opposing" in item for item in r.limitations)


def test_emotional_tone_is_never_converted_into_a_risk_preference():
    for text in ("I am nervous about the market.", "I am scared of losing my savings.", "I am anxious about my investments.", "I am comfortable with my investments."):
        r = analyse_user_text(text)
        assert r.preferences == (), text
    nervous = analyse_user_text("I am nervous about the market.")
    assert nervous.emotional_tone == "concerned" and all(p.code != "capital_preservation" for p in nervous.preferences)


def test_comfortable_taking_risk_is_growth_seeking_only_with_that_explicit_evidence():
    assert codes(analyse_user_text("I am comfortable taking long-term risk with my investments.")) == ["growth_seeking"]
    assert codes(analyse_user_text("I am comfortable with my investments.")) == []


# ------------------------------------------------------------------ stage 8: confidence, state and the evidence limits

def test_the_baseline_never_reports_a_confidence_and_labels_weak_and_valid_readings():
    valid = analyse_user_text("I am worried about losing my savings.")
    weak = analyse_user_text("I want to save for a house.")
    for r in (valid, weak, analyse_user_text("The weather is beautiful.")):
        assert r.confidence is None and r.confidence_band == "unavailable" and r.method == "rules_baseline" and r.validation_status == "UNVALIDATED_BASELINE"
    assert (valid.interpretation_state, weak.interpretation_state) == ("valid", "weak")


def test_evidence_is_short_sanitised_and_limited_even_for_a_maximum_length_text():
    long_clause = "I am worried about " + "my savings and " * 30 + "my loan"
    r = analyse_user_text(long_clause)
    assert r.evidence and all(len(e.phrase) <= EVIDENCE_CHARS for e in r.evidence) and r.evidence[0].phrase.endswith("…")
    assert len(r.evidence) <= MAX_EVIDENCE_ITEMS
    masked = analyse_user_text("I am worried about my savings at me@example.com and https://example.org/x and account 123456789012")
    joined = " ".join(e.phrase for e in masked.evidence)
    assert joined and "@" not in joined and "https" not in joined and "123456789012" not in joined
    assert "[email]" in joined and "[link]" in joined and "[number]" in joined
    assert analyse_user_text("My account 123456789012 worries me, I am worried about my loan.").evidence[0].phrase.count("123456789012") == 0


def test_the_result_never_holds_the_full_text():
    text = "I am worried about my savings. " + "Unique-marker-4471 " * 40
    r = analyse_user_text(text[:MAX_TEXT_CHARS])
    blob = repr(r)
    assert blob.count("Unique-marker-4471") <= 6 and text[:200] not in blob


def test_validation_refusals_never_echo_the_text():
    for bad in ("bad\x00text Unique-marker-5521", "Unique-marker-5521" * 100):
        with pytest.raises(UserTextError) as info:
            analyse_user_text(bad)
        assert "Unique-marker-5521" not in str(info.value) and "Unique-marker-5521" not in repr(info.value)


# ------------------------------------------------------------------ the optional validated-model seam and its rules-baseline fallback

class Model:
    def __init__(self, reading=None, error=None):
        self.reading, self.error, self.calls = reading, error, []

    def interpret(self, text):
        self.calls.append(len(text))
        if self.error:
            raise self.error
        return self.reading


GOOD = ModelReading("negative", 0.81, True, "test_model_1", "VALIDATED_FOR_TEST", abstain_below=0.5, band_cutoffs=(0.6, 0.8))


def test_a_failing_model_falls_back_to_the_rules_baseline_and_the_exception_is_not_kept():
    m = Model(error=RuntimeError("PRIVATE-TEXT-LEAK I am worried about my savings"))
    r = analyse_user_text("I am worried about my savings.", m)
    assert r.fallback_used is True and r.method == "rules_baseline" and r.sentiment == "negative" and r.confidence is None and m.calls
    assert "PRIVATE-TEXT-LEAK" not in repr(r)


@pytest.mark.parametrize("bad", [
    None, "negative", ModelReading("excellent", 0.9, True, "m", "v"), ModelReading("negative", 1.5, True, "m", "v"), ModelReading("negative", True, True, "m", "v"),
    ModelReading("negative", 0.9, True, "", "v"), ModelReading("negative", 0.9, True, "m", ""), ModelReading("negative", 0.9, True, "m", "v", band_cutoffs=(0.9, 0.1)),
])
def test_an_invalid_model_reading_is_a_failure_not_a_result(bad):
    r = analyse_user_text("I am worried about my savings.", Model(bad))
    assert r.fallback_used is True and r.method == "rules_baseline" and r.model_version == module.METHOD_VERSION and r.confidence is None


def test_a_valid_calibrated_model_reading_is_a_hybrid_with_a_band_and_the_rules_still_supply_tone_topics_and_preferences():
    r = analyse_user_text("I am worried about losing my savings, and I want to invest more safely.", Model(GOOD))
    assert (r.method, r.model_version, r.validation_status, r.fallback_used) == ("hybrid", "test_model_1", "VALIDATED_FOR_TEST", False)
    assert (r.sentiment, r.confidence, r.confidence_band) == ("negative", 0.81, "high")
    assert r.emotional_tone == "concerned" and codes(r) == ["capital_preservation"] and r.preferences[0].requires_confirmation
    medium = analyse_user_text("I am worried about my savings.", Model(ModelReading("negative", 0.65, True, "m", "v", band_cutoffs=(0.6, 0.8))))
    low = analyse_user_text("I am worried about my savings.", Model(ModelReading("negative", 0.55, True, "m", "v", band_cutoffs=(0.6, 0.8))))
    assert (medium.confidence_band, low.confidence_band) == ("medium", "low")


def test_confidence_is_not_exposed_unless_the_model_marks_it_calibrated():
    r = analyse_user_text("I am worried about my savings.", Model(ModelReading("negative", 0.9, False, "m", "v", band_cutoffs=(0.6, 0.8))))
    assert (r.method, r.confidence, r.confidence_band) == ("hybrid", None, "unavailable")
    none = analyse_user_text("I am worried about my savings.", Model(ModelReading("negative", None, True, "m", "v")))
    assert (none.confidence, none.confidence_band) == (None, "unavailable")


def test_a_model_below_its_own_documented_threshold_falls_back_visibly_or_abstains_when_fallback_is_off():
    low = Model(ModelReading("negative", 0.3, True, "m", "v", abstain_below=0.5))
    r = analyse_user_text("I am worried about my savings.", low)
    assert (r.fallback_used, r.fallback_reason, r.method, r.sentiment, r.abstained) == (True, "below_threshold", "rules_baseline", "negative", False)    # ADR-052: the rules baseline answers, visibly
    off = analyse_user_text("I am worried about my savings.", low, allow_fallback=False)
    assert (off.abstained, off.abstain_reason, off.sentiment, off.emotional_tone, off.preferences, off.interpretation_state) == (
        True, "model_confidence_below_threshold", "insufficient_evidence", "unknown", (), "abstained")


def test_the_model_is_not_asked_when_an_earlier_stage_already_abstained():
    for text in ("The weather is beautiful.", "Money.", "मुझे निवेश की चिंता है और बचत भी", "I had a good day today.", None, "   "):
        m = Model(GOOD)
        analyse_user_text(text, m)
        assert m.calls == [], text


def test_the_module_defines_no_confidence_threshold_of_its_own():
    """A calibrated model brings its own documented cut-offs (`ModelReading`); the baseline invents none."""
    names = {n.lower() for n in dir(module)}
    assert not any("confidence_threshold" in n or "calibrat" in n and n.isupper() for n in names)
    assert module.analyse_user_text("I am worried about my savings.").confidence is None
