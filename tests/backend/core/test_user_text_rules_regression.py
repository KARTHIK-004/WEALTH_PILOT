"""Regression and boundary tests for the production rules baseline `user_text_rules_v1` (`core/user_text_sentiment.py`).

CHARACTERIZATION, NOT VALIDATION. The table below pins what the baseline returned for 30 FICTIONAL sentences on 2026-11-05, so that an unintended change is noticed. It does NOT say the
classifications are correct: several show known limitations (a "growing, but worried" sentence is read as negative, not mixed; sarcasm abstains; the rules are English-only). The sentences are
not a dataset, not ground truth and not an accuracy evaluation. An intentional change to the rules means updating this table in the same commit, with a decision record.
"""
from __future__ import annotations

import pytest

from wealthpilot.core.user_text_sentiment import MAX_TEXT_CHARS, METHOD_RULES, METHOD_VERSION, UserTextError, analyse_user_text

GOLDEN = {'positive_savings': {'text': 'I feel happy because my savings have increased this month.',
                      'status': 'analysed',
                      'sentiment': 'positive',
                      'state': 'valid',
                      'tone': 'calm',
                      'relevance': 'relevant',
                      'abstain': None,
                      'topics': ['saving'],
                      'preferences': [],
                      'method': 'rules_baseline',
                      'confidence': None},
 'negative_emi': {'text': 'I am worried because my monthly loan EMI keeps increasing and I cannot save.',
                  'status': 'analysed',
                  'sentiment': 'negative',
                  'state': 'valid',
                  'tone': 'concerned',
                  'relevance': 'relevant',
                  'abstain': None,
                  'topics': ['debt', 'saving'],
                  'preferences': [],
                  'method': 'rules_baseline',
                  'confidence': None},
 'neutral_deposit': {'text': 'I deposited five thousand rupees into my savings account this month.',
                     'status': 'analysed',
                     'sentiment': 'neutral',
                     'state': 'weak',
                     'tone': 'neutral',
                     'relevance': 'relevant',
                     'abstain': None,
                     'topics': ['saving'],
                     'preferences': [],
                     'method': 'rules_baseline',
                     'confidence': None},
 'mixed': {'text': 'My investments are growing, but I am worried about future expenses.',
           'status': 'analysed',
           'sentiment': 'negative',
           'state': 'valid',
           'tone': 'concerned',
           'relevance': 'relevant',
           'abstain': None,
           'topics': ['investment_risk'],
           'preferences': [],
           'method': 'rules_baseline',
           'confidence': None},
 'ambiguous_statement': {'text': 'I reviewed my account statement yesterday.',
                         'status': 'analysed',
                         'sentiment': 'insufficient_evidence',
                         'state': 'abstained',
                         'tone': 'unknown',
                         'relevance': 'ambiguous',
                         'abstain': 'ambiguous_context',
                         'topics': [],
                         'preferences': [],
                         'method': 'rules_baseline',
                         'confidence': None},
 'negation': {'text': 'I am not worried about my savings at all.',
              'status': 'analysed',
              'sentiment': 'uncertain',
              'state': 'weak',
              'tone': 'unknown',
              'relevance': 'relevant',
              'abstain': None,
              'topics': ['saving'],
              'preferences': [],
              'method': 'rules_baseline',
              'confidence': None},
 'hypothetical': {'text': 'If I lost my job I would panic about my savings.',
                  'status': 'analysed',
                  'sentiment': 'uncertain',
                  'state': 'weak',
                  'tone': 'unknown',
                  'relevance': 'relevant',
                  'abstain': None,
                  'topics': ['saving'],
                  'preferences': [],
                  'method': 'rules_baseline',
                  'confidence': None},
 'past_feeling': {'text': 'Last year I was very stressed about my loan.',
                  'status': 'analysed',
                  'sentiment': 'neutral',
                  'state': 'weak',
                  'tone': 'neutral',
                  'relevance': 'relevant',
                  'abstain': None,
                  'topics': ['debt'],
                  'preferences': [],
                  'method': 'rules_baseline',
                  'confidence': None},
 'third_person': {'text': 'My brother is terrified about his mortgage.',
                  'status': 'analysed',
                  'sentiment': 'insufficient_evidence',
                  'state': 'abstained',
                  'tone': 'unknown',
                  'relevance': 'ambiguous',
                  'abstain': 'ambiguous_context',
                  'topics': [],
                  'preferences': [],
                  'method': 'rules_baseline',
                  'confidence': None},
 'quoted_speech': {'text': 'My friend said "I hate my debt" yesterday.',
                   'status': 'analysed',
                   'sentiment': 'insufficient_evidence',
                   'state': 'abstained',
                   'tone': 'unknown',
                   'relevance': 'ambiguous',
                   'abstain': 'ambiguous_context',
                   'topics': [],
                   'preferences': [],
                   'method': 'rules_baseline',
                   'confidence': None},
 'preference_safe': {'text': 'I prefer safer investments because I worry about losing my savings.',
                     'status': 'analysed',
                     'sentiment': 'negative',
                     'state': 'valid',
                     'tone': 'concerned',
                     'relevance': 'relevant',
                     'abstain': None,
                     'topics': ['investment_risk', 'saving'],
                     'preferences': ['capital_preservation'],
                     'method': 'rules_baseline',
                     'confidence': None},
 'preference_growth': {'text': 'I want to invest more aggressively for higher returns even if it is risky.',
                       'status': 'analysed',
                       'sentiment': 'uncertain',
                       'state': 'weak',
                       'tone': 'unknown',
                       'relevance': 'relevant',
                       'abstain': None,
                       'topics': ['investment_risk'],
                       'preferences': [],
                       'method': 'rules_baseline',
                       'confidence': None},
 'hopeful_retirement': {'text': 'I feel hopeful about my retirement plan and I am saving every month.',
                        'status': 'analysed',
                        'sentiment': 'positive',
                        'state': 'valid',
                        'tone': 'hopeful',
                        'relevance': 'relevant',
                        'abstain': None,
                        'topics': ['retirement', 'saving'],
                        'preferences': [],
                        'method': 'rules_baseline',
                        'confidence': None},
 'no_emergency_fund': {'text': 'I am anxious because I have no emergency fund.',
                       'status': 'analysed',
                       'sentiment': 'negative',
                       'state': 'valid',
                       'tone': 'concerned',
                       'relevance': 'relevant',
                       'abstain': None,
                       'topics': ['emergency_fund'],
                       'preferences': [],
                       'method': 'rules_baseline',
                       'confidence': None},
 'debt_stress': {'text': 'My credit card debt makes me feel stressed and frustrated.',
                 'status': 'analysed',
                 'sentiment': 'negative',
                 'state': 'valid',
                 'tone': 'concerned',
                 'relevance': 'relevant',
                 'abstain': None,
                 'topics': ['debt'],
                 'preferences': [],
                 'method': 'rules_baseline',
                 'confidence': None},
 'market_nervous': {'text': 'The market crash makes me nervous about my investments.',
                    'status': 'analysed',
                    'sentiment': 'negative',
                    'state': 'valid',
                    'tone': 'concerned',
                    'relevance': 'relevant',
                    'abstain': None,
                    'topics': ['investment_risk', 'market'],
                    'preferences': [],
                    'method': 'rules_baseline',
                    'confidence': None},
 'sarcasm_like': {'text': 'Great, another fee, just what my budget needed.',
                  'status': 'analysed',
                  'sentiment': 'insufficient_evidence',
                  'state': 'abstained',
                  'tone': 'unknown',
                  'relevance': 'relevant',
                  'abstain': 'no_usable_evidence',
                  'topics': [],
                  'preferences': [],
                  'method': 'rules_baseline',
                  'confidence': None},
 'unrelated': {'text': 'The weather is lovely and the football was great.',
               'status': 'analysed',
               'sentiment': 'insufficient_evidence',
               'state': 'abstained',
               'tone': 'unknown',
               'relevance': 'unrelated',
               'abstain': 'unrelated_text',
               'topics': [],
               'preferences': [],
               'method': 'rules_baseline',
               'confidence': None},
 'two_words': {'text': 'Money worries.',
               'status': 'analysed',
               'sentiment': 'insufficient_evidence',
               'state': 'abstained',
               'tone': 'unknown',
               'relevance': 'ambiguous',
               'abstain': 'too_short',
               'topics': [],
               'preferences': [],
               'method': 'rules_baseline',
               'confidence': None},
 'three_words': {'text': 'worried about loan',
                 'status': 'analysed',
                 'sentiment': 'insufficient_evidence',
                 'state': 'abstained',
                 'tone': 'unknown',
                 'relevance': 'ambiguous',
                 'abstain': 'ambiguous_context',
                 'topics': [],
                 'preferences': [],
                 'method': 'rules_baseline',
                 'confidence': None},
 'tamil': {'text': 'என் கடன் தவணை அதிகரித்து வருவதால் எனக்கு கவலையாக இருக்கிறது',
           'status': 'analysed',
           'sentiment': 'insufficient_evidence',
           'state': 'abstained',
           'tone': 'unknown',
           'relevance': 'ambiguous',
           'abstain': 'unsupported_language',
           'topics': [],
           'preferences': [],
           'method': 'rules_baseline',
           'confidence': None},
 'spanish': {'text': 'Estoy muy contento porque por fin pude ahorrar para mis vacaciones.',
             'status': 'analysed',
             'sentiment': 'insufficient_evidence',
             'state': 'abstained',
             'tone': 'unknown',
             'relevance': 'ambiguous',
             'abstain': 'unsupported_language',
             'topics': [],
             'preferences': [],
             'method': 'rules_baseline',
             'confidence': None},
 'code_mixed_tamil_english': {'text': 'எனக்கு savings பற்றி ரொம்ப worry ஆக இருக்கு and my EMI is high',
                              'status': 'analysed',
                              'sentiment': 'insufficient_evidence',
                              'state': 'abstained',
                              'tone': 'unknown',
                              'relevance': 'ambiguous',
                              'abstain': 'unsupported_language',
                              'topics': [],
                              'preferences': [],
                              'method': 'rules_baseline',
                              'confidence': None},
 'french': {'text': 'Je suis inquiet pour mon épargne et mes dettes ce mois.',
            'status': 'analysed',
            'sentiment': 'insufficient_evidence',
            'state': 'abstained',
            'tone': 'unknown',
            'relevance': 'ambiguous',
            'abstain': 'unsupported_language',
            'topics': [],
            'preferences': [],
            'method': 'rules_baseline',
            'confidence': None},
 'emoji_only': {'text': '😀😀😀😀😀😀',
                'status': 'analysed',
                'sentiment': 'insufficient_evidence',
                'state': 'abstained',
                'tone': 'unknown',
                'relevance': 'ambiguous',
                'abstain': 'low_quality_text',
                'topics': [],
                'preferences': [],
                'method': 'rules_baseline',
                'confidence': None},
 'digits_only': {'text': '123 456 789 012',
                 'status': 'analysed',
                 'sentiment': 'insufficient_evidence',
                 'state': 'abstained',
                 'tone': 'unknown',
                 'relevance': 'ambiguous',
                 'abstain': 'low_quality_text',
                 'topics': [],
                 'preferences': [],
                 'method': 'rules_baseline',
                 'confidence': None},
 'contact_details': {'text': 'Please call 07700 900123 about my savings worries and my loan.',
                     'status': 'analysed',
                     'sentiment': 'negative',
                     'state': 'valid',
                     'tone': 'concerned',
                     'relevance': 'relevant',
                     'abstain': None,
                     'topics': ['debt', 'saving'],
                     'preferences': [],
                     'method': 'rules_baseline',
                     'confidence': None},
 'contradictory_preference': {'text': 'I want safe investments but also very high returns quickly.',
                              'status': 'analysed',
                              'sentiment': 'neutral',
                              'state': 'valid',
                              'tone': 'neutral',
                              'relevance': 'relevant',
                              'abstain': None,
                              'topics': ['investment_risk'],
                              'preferences': ['capital_preservation'],
                              'method': 'rules_baseline',
                              'confidence': None},
 'neutral_schedule': {'text': 'My rent is due on the fifth and my salary arrives on the last working day.',
                      'status': 'analysed',
                      'sentiment': 'insufficient_evidence',
                      'state': 'abstained',
                      'tone': 'unknown',
                      'relevance': 'relevant',
                      'abstain': 'no_usable_evidence',
                      'topics': [],
                      'preferences': [],
                      'method': 'rules_baseline',
                      'confidence': None},
 'confident_goal': {'text': 'I am confident that I can reach my savings goal this year.',
                    'status': 'analysed',
                    'sentiment': 'positive',
                    'state': 'valid',
                    'tone': 'hopeful',
                    'relevance': 'relevant',
                    'abstain': None,
                    'topics': ['goals', 'saving'],
                    'preferences': [],
                    'method': 'rules_baseline',
                    'confidence': None}}


@pytest.mark.parametrize("name", list(GOLDEN))
def test_the_rules_baseline_still_returns_exactly_what_it_returned_for_each_fictional_sentence(name):
    expected = GOLDEN[name]
    a = analyse_user_text(expected["text"])
    got = {"status": a.status, "sentiment": a.sentiment, "state": a.interpretation_state, "tone": a.emotional_tone, "relevance": a.financial_relevance, "abstain": a.abstain_reason,
           "topics": sorted(a.topics), "preferences": sorted(p.code for p in a.preferences), "method": a.method, "confidence": a.confidence}
    assert got == {k: v for k, v in expected.items() if k != "text"}, name


def test_every_baseline_reading_is_the_production_method_with_no_confidence_intensity_or_model():
    for name, row in GOLDEN.items():
        a = analyse_user_text(row["text"])
        assert a.method == METHOD_RULES == "rules_baseline" and a.model_version == METHOD_VERSION == "user_text_rules_v1", name
        assert a.confidence is None and a.sentiment_intensity is None and a.fallback_used is False and a.model_name is None and a.class_probabilities is None, name


def test_missing_empty_and_whitespace_only_text_is_unavailable_never_neutral():
    for value in (None, "", "   ", chr(10) + chr(9) + "  "):
        a = analyse_user_text(value)
        assert (a.status, a.sentiment, a.interpretation_state) == ("unavailable", None, "unavailable") and "No sentiment is inferred" in a.unavailable_reason, repr(value)


def test_text_that_is_not_a_string_is_refused_without_echoing_it():
    for value in (123, 1.5, True, ["a"], {"t": 1}, b"loan worry", object()):
        with pytest.raises(UserTextError) as raised:
            analyse_user_text(value)  # type: ignore[arg-type]
        assert "must be a string" in str(raised.value) and repr(value) not in str(raised.value)


def test_the_length_limit_is_exactly_one_thousand_characters_and_the_refusal_never_echoes_the_text():
    base = "I am worried about my loan and my savings every month "
    assert MAX_TEXT_CHARS == 1000
    assert analyse_user_text((base * 30)[:1000]).status == "analysed"
    secret = "blue-harbour-47"
    with pytest.raises(UserTextError) as raised:
        analyse_user_text((base * 30)[:990] + secret + "x" * 20)
    assert "longer than 1000" in str(raised.value) and secret not in str(raised.value)


@pytest.mark.parametrize("char", [chr(0), chr(7), chr(27), chr(127)])
def test_control_characters_are_refused_without_echoing_the_text(char):
    with pytest.raises(UserTextError) as raised:
        analyse_user_text(f"I am worried{char} about my loan and savings")
    assert "control characters" in str(raised.value) and "worried" not in str(raised.value)


def test_newlines_tabs_and_invisible_formatting_characters_are_accepted_and_do_not_change_the_reading():
    plain = analyse_user_text("I am worried about my loan and savings")
    for text in ("I am worried about" + chr(10) + "my loan" + chr(9) + "and savings", "I am worried about my l" + chr(0x200B) + "oan and savings", "I am worried " + chr(0x200F) + " about my loan and savings"):
        a = analyse_user_text(text)
        assert (a.status, a.sentiment) == (plain.status, plain.sentiment), repr(text)


def test_contact_details_and_links_never_appear_in_the_evidence_or_topics():
    a = analyse_user_text("Please call 07700 900123 or write jane.doe@example.com about my savings worries and my loan, see https://example.org/x")
    shown = " ".join(e.phrase for e in a.evidence) + " ".join(p.evidence.phrase for p in a.preferences)
    assert not any(token in shown for token in ("07700", "900123", "jane.doe", "example.org", "https://"))
    assert all(len(e.phrase) <= 120 for e in a.evidence)


def test_a_preference_is_always_unconfirmed_and_never_a_risk_tolerance():
    for name, row in GOLDEN.items():
        a = analyse_user_text(row["text"])
        for p in a.preferences:
            assert p.status == "unconfirmed" and p.requires_confirmation is True and p.evidence.phrase, name
        assert not any("risk_tolerance" in str(getattr(a, f, "")) for f in ("topics", "emotional_tone")), name


def test_the_baseline_is_english_only_and_says_so_for_tamil_spanish_french_and_code_mixed_text():
    for name in ("tamil", "spanish", "french", "code_mixed_tamil_english"):
        a = analyse_user_text(GOLDEN[name]["text"])
        assert (a.interpretation_state, a.abstain_reason, a.sentiment) == ("abstained", "unsupported_language", "insufficient_evidence"), name
