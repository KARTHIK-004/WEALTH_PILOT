"""ADR-052 -- how a trained model's reading is combined with the deterministic pipeline in `analyse_user_text`: the model runs only after every earlier stage, reads only the user's own current
clauses, never overrides a rules safeguard, and every way it can fail ends in a visible rules-baseline fallback (or, if fallback is off, an abstention). Fake models only; no weights."""

from __future__ import annotations

import pytest

from wealthpilot.core.user_text_sentiment import FALLBACK_REASONS, ModelReading, analyse_user_text

PRIVATE = "PRIVATE-TEXT-LEAK-4417"
_UNSET = object()
NERVOUS = "I am nervous about the market."
POSITIVE = "I feel confident about my savings."


class Model:
    def __init__(self, label="negative", probability=0.9, *, calibrated=True, abstain_below=0.6, band_cutoffs=(0.6, 0.85), probabilities=None, intensity=None, error=None, reading=_UNSET):
        self.error, self.reading, self.calls = error, reading, []
        self.value = ModelReading(label, probability, calibrated, "sentiment-v1", "validated" if calibrated else "unvalidated", abstain_below if calibrated else None,
                                  band_cutoffs if calibrated else None, probabilities or {"positive": 0.05, "negative": 0.9, "neutral": 0.05}, intensity, "test-model")

    def interpret(self, text):
        self.calls.append(text)
        if self.error:
            raise self.error
        return self.value if self.reading is _UNSET else self.reading


class WithReason(Exception):
    def __init__(self, reason):
        super().__init__("fixed")
        self.reason = reason


# ------------------------------------------------------------------------------------------------ a model that answers


def test_a_valid_model_reading_supplies_the_label_probabilities_confidence_and_keeps_the_rules_tone_topics_and_preferences():
    plain = analyse_user_text("I am worried about losing my savings, and I want to invest more safely.")
    r = analyse_user_text("I am worried about losing my savings, and I want to invest more safely.", Model("negative", 0.9, intensity=-0.72))
    assert (r.method, r.model_name, r.model_version, r.validation_status, r.sentiment, r.fallback_used, r.fallback_reason) == ("hybrid", "test-model", "sentiment-v1", "validated", "negative", False, None)
    assert (r.confidence, r.confidence_band, r.confidence_calibration_status) == (0.9, "high", "calibrated")
    assert r.class_probabilities == {"positive": 0.05, "negative": 0.9, "neutral": 0.05} and r.sentiment_intensity == -0.72
    assert (r.emotional_tone, r.topics, r.preferences, r.evidence, r.financial_relevance) == (plain.emotional_tone, plain.topics, plain.preferences, plain.evidence, plain.financial_relevance)
    assert (r.rules_label, r.disagreement) == ("negative", False)
    assert any("comes from the model" in item for item in r.limitations)


def test_an_uncalibrated_reading_shows_its_probabilities_but_never_a_confidence():
    r = analyse_user_text(NERVOUS, Model("negative", 0.97, calibrated=False))
    assert (r.confidence, r.confidence_band, r.confidence_calibration_status, r.validation_status) == (None, "unavailable", "uncalibrated", "unvalidated")
    assert r.class_probabilities is not None and r.sentiment == "negative"


def test_the_confidence_band_follows_the_models_own_cutoffs():
    bands = {p: analyse_user_text(NERVOUS, Model("negative", p)).confidence_band for p in (0.9, 0.7, 0.6)}
    assert bands == {0.9: "high", 0.7: "medium", 0.6: "medium"}


def test_without_a_validated_regression_head_the_intensity_is_null_even_if_a_reading_names_none():
    assert analyse_user_text(NERVOUS, Model("negative", 0.9)).sentiment_intensity is None
    assert analyse_user_text(NERVOUS, Model("negative", 0.9, intensity=0.3)).sentiment_intensity == 0.3


# ------------------------------------------------------------------------------------------------ the model reads only what the safeguards left


def test_the_model_never_runs_when_an_earlier_stage_abstained():
    for text in ("The weather is beautiful.", "Money.", "I had a good day today.", "मुझे निवेश करना है और बचत भी", None, "   ", "!!! ???"):
        m = Model()
        r = analyse_user_text(text, m)
        assert m.calls == [], text
        assert r.fallback_used is False and r.method in ("unavailable", "rules_baseline")        # an abstention is not a model failure


def test_the_model_reads_only_the_users_own_current_words():
    m = Model()
    analyse_user_text('My friend is terrified of the market. He said "you will lose everything". I used to be afraid of risk, but now I feel confident about my savings.', m)
    seen = m.calls[0].lower()
    assert "friend" not in seen and "lose everything" not in seen and "afraid" not in seen and "terrified" not in seen
    assert "confident about my savings" in seen


# ------------------------------------------------------------------------------------------------ disagreement with the rules baseline


def test_the_model_and_the_rules_agree_with_no_caveat():
    r = analyse_user_text(NERVOUS, Model("negative"))
    assert r.disagreement is False and not any("model and the rules baseline" in n for n in r.limitations)


def test_opposite_polarities_are_unresolved_not_silently_chosen():
    r = analyse_user_text(NERVOUS, Model("positive", 0.95, probabilities={"positive": 0.95, "negative": 0.03, "neutral": 0.02}))
    assert (r.sentiment, r.interpretation_state, r.disagreement, r.rules_label) == ("uncertain", "weak", True, "negative")
    assert (r.confidence, r.confidence_band, r.sentiment_intensity) == (None, "unavailable", None)         # the model's confidence is not attached to a label it did not give
    assert r.class_probabilities is not None                                                              # the model's own reading stays visible
    assert any("opposite sentiments" in n for n in r.limitations)


def test_a_non_opposite_disagreement_uses_the_model_and_keeps_the_rules_reading_beside_it():
    r = analyse_user_text("I want to save for a house.", Model("negative", 0.9))                           # rules: neutral
    assert (r.sentiment, r.rules_label, r.disagreement) == ("negative", "neutral", True)
    assert r.confidence == 0.9 and any("keeps" in n or "kept for comparison" in n for n in r.limitations)


def test_a_rules_safeguard_for_a_negated_expression_is_never_overridden():
    r = analyse_user_text("I am not worried about losing money.", Model("negative", 0.95))                  # rules: uncertain (only a negated cue)
    assert (r.sentiment, r.rules_label, r.interpretation_state) == ("uncertain", "uncertain", "weak") and r.confidence is None
    assert any("rules safeguard" in n and "was kept" in n for n in r.limitations)


# ------------------------------------------------------------------------------------------------ every failure is visible


@pytest.mark.parametrize("reason", [r for r in FALLBACK_REASONS if r != "below_threshold"])
def test_a_configured_but_unusable_model_falls_back_to_the_rules_and_says_why(reason):
    r = analyse_user_text(NERVOUS, None, model_unavailable_reason=reason)
    assert (r.fallback_used, r.fallback_reason, r.method, r.sentiment, r.abstained) == (True, reason, "rules_baseline", "negative", False)
    assert r.confidence is None and r.class_probabilities is None and any("rules baseline answered" in n for n in r.limitations)


def test_an_unknown_reason_code_is_coerced_never_passed_through():
    assert analyse_user_text(NERVOUS, None, model_unavailable_reason="C:/secret/path").fallback_reason == "load_failed"


def test_with_no_model_configured_the_rules_baseline_is_simply_the_method_not_a_fallback():
    r = analyse_user_text(NERVOUS)
    assert (r.method, r.fallback_used, r.fallback_reason, r.model_name, r.class_probabilities, r.confidence_calibration_status, r.sentiment_intensity) == (
        "rules_baseline", False, None, None, None, "not_applicable", None)


def test_fallback_switched_off_means_the_text_is_not_interpreted():
    r = analyse_user_text(NERVOUS, None, model_unavailable_reason="dependencies_missing", allow_fallback=False)
    assert (r.abstained, r.abstain_reason, r.sentiment, r.fallback_reason, r.preferences) == (True, "model_unavailable", "insufficient_evidence", "dependencies_missing", ())


def test_a_model_exception_never_carries_the_text_and_keeps_only_a_fixed_reason():
    r = analyse_user_text(f"I am worried about my savings {PRIVATE}", Model(error=RuntimeError(f"failed on {PRIVATE}")))
    assert (r.fallback_used, r.fallback_reason, r.method) == (True, "inference_failed", "rules_baseline")
    assert "failed on" not in repr(r) and PRIVATE not in repr(r.fallback_reason) and PRIVATE not in " ".join(r.limitations)       # the exception's message (which held the text) is gone
    assert analyse_user_text(NERVOUS, Model(error=WithReason("timeout"))).fallback_reason == "timeout"
    assert analyse_user_text(NERVOUS, Model(error=WithReason("not-a-code"))).fallback_reason == "inference_failed"


def test_a_confidence_below_the_models_own_threshold_falls_back_or_abstains():
    low = Model("negative", 0.4, probabilities={"positive": 0.3, "negative": 0.4, "neutral": 0.3})
    r = analyse_user_text(NERVOUS, low)
    assert (r.fallback_used, r.fallback_reason, r.method, r.sentiment, r.abstained) == (True, "below_threshold", "rules_baseline", "negative", False)
    off = analyse_user_text(NERVOUS, low, allow_fallback=False)
    assert (off.abstained, off.abstain_reason, off.sentiment, off.fallback_reason) == (True, "model_confidence_below_threshold", "insufficient_evidence", "below_threshold")


@pytest.mark.parametrize("bad", [
    None, "negative", ModelReading("excellent", 0.9, True, "v", "validated"), ModelReading("negative", 1.4, True, "v", "validated"), ModelReading("negative", float("nan"), True, "v", "validated"),
    ModelReading("negative", 0.9, True, "v", "validated", class_probabilities={"negative": 0.9}),                           # does not sum to 1
    ModelReading("negative", 0.9, True, "v", "validated", class_probabilities={"angry": 1.0}),
    ModelReading("negative", 0.9, True, "v", "validated", class_probabilities={"negative": float("inf"), "neutral": 0.0}),
    ModelReading("negative", 0.9, True, "v", "validated", intensity=2.0), ModelReading("negative", 0.9, True, "v", "validated", abstain_below=1.5),
    ModelReading("negative", 0.9, True, "", "validated"), ModelReading("negative", 0.9, True, "v", "validated", band_cutoffs=(0.9, 0.5)),
])
def test_an_invalid_model_output_is_a_failure_with_the_rules_answering(bad):
    r = analyse_user_text(NERVOUS, Model(reading=bad))
    assert (r.fallback_used, r.fallback_reason, r.method, r.sentiment) == (True, "invalid_output", "rules_baseline", "negative")


def test_the_result_never_holds_the_text_or_a_path():
    r = analyse_user_text(f"I am worried about my savings {PRIVATE} and my loan, which is why I am nervous.", Model(error=RuntimeError(f"C:/models/secret/{PRIVATE}")))
    assert "C:/models" not in repr(r) and "secret" not in repr(r)
