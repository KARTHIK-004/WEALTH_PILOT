"""Robustness of the rules baseline on arbitrary input (Phase 1 hardening). Seeded random strings (no real text, no data file): whatever is thrown at `analyse_user_text`, it either raises
`UserTextError` for the two documented refusals (control characters, over-length) or returns a well-formed analysis that stays inside the documented contract: bounded evidence, masked links /
addresses / digit runs, no label on an abstention, no confidence, no preference without text, deterministic."""
from __future__ import annotations

import random
import string

import pytest

from wealthpilot.core.user_text_sentiment import (
    ABSTAIN_REASONS,
    CONFIDENCE_BANDS,
    EMOTIONS,
    EVIDENCE_CHARS,
    INTERPRETATION_STATES,
    MAX_EVIDENCE_ITEMS,
    MAX_TEXT_CHARS,
    PREFERENCES,
    SENTIMENTS,
    TOPICS,
    UserTextAnalysis,
    UserTextError,
    analyse_user_text,
)

WORDS = ("worried", "savings", "invest", "my", "I", "the", "not", "if", "would", "like", "prefer", "growth", "loan", "debt", "market", "but", "and", "friend", "used", "to", "want", "safe", "returns",
         "afraid", "comfortable", "even", "only", "suppose", "He", "said", "\"quoted\"", "money", "http://example.test/a", "someone@example.test", "1234567890123", "👍", "₹", "—", "...", "ok")
ALPHABETS = (string.ascii_letters + string.digits + " " * 6, string.punctuation + " ", "अआइईउऊकखगघ ", "日本語のテキスト ", "😀😃😄👍💰 ", "éèêëçñü ")


def random_text(rng: random.Random) -> str:
    kind = rng.randrange(4)
    if kind == 0:
        return " ".join(rng.choice(WORDS) for _ in range(rng.randrange(0, 40)))
    if kind == 1:
        alphabet = rng.choice(ALPHABETS)
        return "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 300)))
    if kind == 2:
        return ", ".join(" ".join(rng.choice(WORDS) for _ in range(rng.randrange(1, 8))) for _ in range(rng.randrange(1, 8))) + rng.choice([".", "?", "!", ""])
    return "".join(rng.choice(string.printable[:-5] + " ​ ") for _ in range(rng.randrange(0, 1200)))


def check(analysis: UserTextAnalysis) -> None:
    assert analysis.status in ("analysed", "unavailable")
    assert analysis.method in ("rules_baseline", "unavailable") and analysis.model_version == "user_text_rules_v1" and analysis.privacy_status == "in_memory_only"
    assert analysis.confidence is None and analysis.confidence_band == "unavailable" and analysis.sentiment_intensity is None and analysis.class_probabilities is None
    assert analysis.interpretation_state in INTERPRETATION_STATES and analysis.confidence_band in CONFIDENCE_BANDS
    if analysis.status == "unavailable":
        assert analysis.sentiment is None and analysis.preferences == () and analysis.evidence == () and analysis.topics == ()
        return
    assert analysis.sentiment in SENTIMENTS and analysis.emotional_tone in EMOTIONS
    assert all(t in TOPICS for t in analysis.topics)
    assert len(analysis.evidence) <= MAX_EVIDENCE_ITEMS
    for item in [*analysis.evidence, *(p.evidence for p in analysis.preferences)]:
        assert len(item.phrase) <= EVIDENCE_CHARS
        assert "http" not in item.phrase.lower().replace("[link]", "") and "@" not in item.phrase                      # links and e-mail addresses are masked
        assert not any(run in item.phrase for run in ("1234567", "12345678"))                                          # long digit runs are masked
    assert all(p.code in PREFERENCES and p.status == "unconfirmed" and p.requires_confirmation for p in analysis.preferences)
    if analysis.abstained:
        assert analysis.sentiment == "insufficient_evidence" and analysis.abstain_reason in ABSTAIN_REASONS and analysis.interpretation_state == "abstained"
        assert analysis.preferences == () and analysis.evidence == () and analysis.emotional_tone == "unknown"
    else:
        assert analysis.abstain_reason is None and analysis.interpretation_state in ("valid", "weak")
    assert analysis.requires_confirmation == bool(analysis.preferences)


@pytest.mark.parametrize("seed", range(8))
def test_arbitrary_input_never_breaks_the_contract(seed):
    rng = random.Random(1000 + seed)
    refused = answered = 0
    for _ in range(150):
        text = random_text(rng)
        try:
            first = analyse_user_text(text)
        except UserTextError as exc:
            refused += 1
            assert text not in str(exc) and (len(" ".join(text.split())) > MAX_TEXT_CHARS or any(ord(c) < 32 or ord(c) == 127 for c in text))        # only the two documented refusals; the text is never echoed
            continue
        answered += 1
        check(first)
        assert analyse_user_text(text) == first                                                                       # deterministic
    assert answered > 0


def test_the_documented_refusals_are_the_only_exceptions_and_never_echo_the_text():
    with pytest.raises(UserTextError) as control:
        analyse_user_text("I am worried\x00 about my savings SECRETMARKER")
    assert "SECRETMARKER" not in str(control.value)
    with pytest.raises(UserTextError) as too_long:
        analyse_user_text("savings " * 200)
    assert "savings savings" not in str(too_long.value)
    assert analyse_user_text("x" * MAX_TEXT_CHARS).status == "analysed"
    with pytest.raises(UserTextError):
        analyse_user_text("x" * (MAX_TEXT_CHARS + 1))


def test_non_string_input_is_refused_not_coerced():
    for bad in (5, 5.5, ["savings"], {"a": 1}, b"savings"):
        with pytest.raises(UserTextError):
            analyse_user_text(bad)                          # type: ignore[arg-type]
    assert analyse_user_text(None).status == "unavailable" and analyse_user_text("   ").status == "unavailable"


def test_evidence_is_bounded_and_masked_for_a_deliberately_hostile_but_valid_text():
    text = ("I am worried about my savings see https://example.test/" + "a" * 90 + " or write to someone@example.test or call 9876543210123 " + "and I am worried about my debt " * 8)[:MAX_TEXT_CHARS]
    result = analyse_user_text(text)
    check(result)
    assert result.evidence and all(len(e.phrase) <= EVIDENCE_CHARS for e in result.evidence)
    joined = " ".join(e.phrase for e in result.evidence)
    assert "https" not in joined and "someone@" not in joined and "9876543210123" not in joined


def test_unicode_oddities_do_not_break_the_language_and_quality_gates():
    for text in ("​" * 30, " " * 40, "😀" * 40, "💰 💰 💰 savings", "सेविंग्स की चिंता है मुझे अपने निवेश के बारे में", "ｓａｖｉｎｇｓ ｉｎｖｅｓｔ ｗｏｒｒｉｅｄ ａｂｏｕｔ", "Í am worried about my savings"):
        result = analyse_user_text(text)
        check(result)
