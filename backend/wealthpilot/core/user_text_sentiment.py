"""Interpretation of text the user chose to write (Research Enhancement Track, ADR-043; multi-stage pipeline, ADR-050). A deterministic RULES BASELINE with an optional,
validated-model hook. It is INFORMATIONAL ONLY: nothing here is an input to a risk profile, goal, portfolio, recommendation or compliance decision.

This is NOT a trained model and has NOT been validated: `VALIDATION_STATUS = "UNVALIDATED_BASELINE"`. No model, weight, package or network is used, so there is nothing to
download, license or transmit, and the user's text never leaves the process. No trained, validated model exists in this repository; `SentimentModel` is the seam through which an
approved one could be added later, and until then every reading comes from the rules below and says so (`method = "rules_baseline"`). Its output is a suggestion for the user to
confirm, never a fact about the user.

PIPELINE (each stage can stop the reading; a stopped reading is an ABSTENTION, never a guessed label):

1. input validation / privacy   `validate_text`: control characters and over-length text are refused (the text is never echoed); whitespace is normalised.
2. text and language quality    too short, mostly non-letters, a non-Latin script, or text that cannot be confirmed as English -> abstain.
3. financial relevance          `relevant | unrelated | ambiguous` from a fixed personal-finance lexicon, counted over the user's OWN clauses only.
4. clause analysis              the text is split into clauses; quoted spans, other people's views ("my friend is nervous") and past feelings ("I used to be afraid") are not the
                                user's current view; a negated cue ("not worried") is dropped and its opposite is NEVER concluded.
5. sentiment and emotional tone sentiment from explicit affect cues; emotional tone is a separate field and is NOT a risk tolerance.
6. topics                       the subjects mentioned (a mention, not a position).
7. explicit preferences         only from an explicit phrase (or a generic word after a first-person stance verb such as "want"); always `unconfirmed`. A hypothetical or conditional
                                clause ("if the market falls I would be worried", "if I had more money I would want growth") is, like a past feeling, never a current view.
8. confidence / abstention      `confidence` stays None unless a calibrated model supplies one; weak evidence is labelled `weak`, not `valid`.

TAXONOMY (controlled vocabularies; none of them is a risk tolerance):

- `sentiment`:       positive | negative | neutral | mixed | uncertain | insufficient_evidence. `insufficient_evidence` = the pipeline abstained. `uncertain` = something was
                     said but cannot be read reliably (for example only a negated cue). No text at all is NOT a label: the status is `unavailable`.
- `emotional_tone`:  concerned | hopeful | frustrated | calm | neutral | unknown. `unknown` when abstained or unreadable. Not a diagnosis and not how much risk the person
                     can or wants to take: a worried user is not thereby a conservative investor.
- `preferences`:     capital_preservation | growth_seeking | liquidity_access | debt_reduction | balanced_growth, each `unconfirmed` and `requires_confirmation`.
- `confidence`:      None for the rules baseline (they are not calibrated, so no probability is claimed). `confidence_band` is then `unavailable`.

KNOWN LIMITS (stated, not hidden; also returned in `limitations`): English only and the language check is conservative (it can abstain on very terse English); keyword
relevance can misjudge a word with two meanings; no sarcasm, irony or deep context; negation, quotation and third-person handling is basic (pronoun and relationship words, not names);
misspellings are missed. These limits are why the method is unvalidated and why confidence is never reported.

Privacy: pure function of its input; nothing is stored or logged here (this module imports no logger), and the text is not returned except as short, sanitised evidence phrases.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Mapping, Protocol

METHOD_VERSION = "user_text_rules_v1"
VALIDATION_STATUS = "UNVALIDATED_BASELINE"
METHOD_RULES = "rules_baseline"
METHOD_HYBRID = "hybrid"
METHOD_TRAINED = "trained_model"
METHOD_UNAVAILABLE = "unavailable"
PRIVACY_STATUS = "in_memory_only"

MAX_TEXT_CHARS = 1000
EVIDENCE_CHARS = 100
MAX_EVIDENCE_ITEMS = 6

# Configuration values for the quality and evidence stages. They are rule-of-thumb gates of this UNVALIDATED baseline (not tuned on data, not calibrated probabilities); each is
# exercised by a test. Changing one is a classifier change and needs its own review.
MIN_WORDS = 3                       # fewer words than this cannot carry a financial statement
MIN_LETTER_RATIO = 0.5              # letters / non-space characters; below it the text is mostly numbers, symbols or emoji
MAX_NON_LATIN_SHARE = 0.2           # share of letters outside the Latin script above which the text is treated as an unsupported language
MIN_TOKENS_FOR_LANGUAGE_CHECK = 6   # below this there are too few words to judge the language from common English words
MIN_ENGLISH_FUNCTION_SHARE = 0.15   # share of tokens that are common English function words, below which the text is not confirmed as English
MIN_SIGNALS_ALONE = 2               # explicit signals (affect cues + stated preferences) that make a reading `valid` with no topic
MIN_SIGNALS_WITH_TOPIC = 1          # ... or one explicit signal together with at least one topic

SENTIMENTS = ("positive", "negative", "neutral", "mixed", "uncertain", "insufficient_evidence")
EMOTIONS = ("concerned", "hopeful", "frustrated", "calm", "neutral", "unknown")
RELEVANCE = ("relevant", "unrelated", "ambiguous")
TOPICS = ("investment_risk", "saving", "debt", "goals", "liquidity", "market", "retirement", "emergency_fund")
PREFERENCES = ("capital_preservation", "growth_seeking", "liquidity_access", "debt_reduction", "balanced_growth")
PREFERENCE_STATUSES = ("unconfirmed", "confirmed", "rejected", "not_inferred")   # only `unconfirmed` is ever produced: confirmations are not stored
CONFIDENCE_BANDS = ("high", "medium", "low", "unavailable")
METHODS = (METHOD_RULES, METHOD_TRAINED, METHOD_HYBRID, METHOD_UNAVAILABLE)
INTERPRETATION_STATES = ("valid", "weak", "abstained", "unavailable")
ABSTAIN_REASONS = ("too_short", "low_quality_text", "unsupported_language", "unrelated_text", "ambiguous_context", "no_usable_evidence", "model_confidence_below_threshold", "model_unavailable")
# Why the rules baseline answered although a trained model was configured (ADR-052). Fixed codes only: they never carry text, a path or an exception message.
FALLBACK_REASONS = ("dependencies_missing", "artifact_missing", "artifact_corrupt", "artifact_incompatible", "path_not_allowed", "not_validated", "version_mismatch", "load_failed",
                    "inference_failed", "timeout", "invalid_output", "invalid_configuration", "below_threshold")
CALIBRATION_STATUSES = ("calibrated", "uncalibrated", "not_applicable")
_MODEL_CLASSES = ("positive", "negative", "neutral")
_OPPOSITE = {frozenset(("positive", "negative"))}
_MODEL_SENTIMENTS = ("positive", "negative", "neutral", "mixed", "uncertain")

LIMITATIONS = (
    "rules baseline, not validated",
    "English only: the language check is conservative (script and common English words), so other languages are not interpreted and very terse English can be declined",
    "relevance is judged from a fixed list of personal-finance words, which can misjudge a word with two meanings",
    "no sarcasm, irony or deep context; negation, quotation and third-person handling is basic",
    "negated cues are not read as their opposite",
    "confidence is not claimed",
)
NOTE_NEGATION = "A negated expression (for example 'not worried') was not read as its opposite."
NOTE_OTHERS = "Wording about other people was not treated as your own view."
NOTE_QUOTED = "Quoted text was not treated as your own view."
NOTE_PAST = "Feelings described as past were not treated as how you feel now."
NOTE_HYPOTHETICAL = "Hypothetical or conditional statements ('if ...', 'suppose ...', 'I would be ...') were not treated as how you feel or what you prefer now."
NOTE_OPPOSING = "The text states opposing preferences, so none was inferred."
NOTE_MODEL_TONE = "With a model reading, the sentiment label comes from the model; tone, topics and preferences still come from the rules baseline."
NOTE_FALLBACK = "The trained sentiment model could not be used for this text, so the rules baseline answered."
NOTE_DISAGREE_UNRESOLVED = "The model and the rules baseline read opposite sentiments, so no sentiment is claimed."
NOTE_DISAGREE_MODEL = "The model and the rules baseline disagree; the model's label is shown and the rules baseline's reading is kept for comparison."
NOTE_SAFEGUARD_KEPT = "A rules safeguard (only a negated expression was found) was kept: the model's label is shown for comparison only."
ABSTAIN_MESSAGES = {
    "too_short": "There is not enough reliable financial context to interpret this text.",
    "low_quality_text": "There is not enough reliable financial context to interpret this text.",
    "unsupported_language": "The text does not appear to be in English, the only language this analysis supports, so it was not interpreted.",
    "unrelated_text": "This text does not contain enough personal-finance context for a financial insight.",
    "ambiguous_context": "There is not enough reliable financial context to interpret this text.",
    "no_usable_evidence": "There is not enough reliable financial context to interpret this text.",
    "model_confidence_below_threshold": "The sentiment model was not confident enough to interpret this text.",
    "model_unavailable": "The sentiment model was unavailable and fallback to the rules baseline is switched off, so this text was not interpreted.",
}


def _phrase(term: str) -> str:
    return r"\s+".join(re.escape(part) for part in term.split())


def _terms(terms: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z'])(?:" + "|".join(_phrase(t) for t in sorted(terms, key=len, reverse=True)) + r")(?![a-z'])")


_AFFECT_TERMS = {
    "concerned": ("worried", "worry", "worries", "worrying", "afraid", "scared", "nervous", "anxious", "anxiety", "concerned", "fear", "fearful", "uneasy", "frightened", "terrified",
                  "panic", "panicking", "stressed", "stress", "struggling", "cannot afford", "can't afford", "can not afford", "lose sleep", "losing sleep"),
    "frustrated": ("frustrated", "frustrating", "annoyed", "angry", "upset", "disappointed", "irritated", "fed up", "sick of", "tired of"),
    "hopeful": ("confident", "optimistic", "excited", "hopeful", "looking forward", "encouraged"),
    "calm": ("comfortable", "calm", "relaxed", "secure", "at ease", "content", "satisfied", "peaceful", "reassured", "happy", "glad", "pleased"),
}
_NEGATIVE_FAMILIES = ("concerned", "frustrated")
_POSITIVE_FAMILIES = ("hopeful", "calm")
_TONE_PRIORITY = ("concerned", "frustrated", "hopeful", "calm")
_AFFECT = {family: _terms(terms) for family, terms in _AFFECT_TERMS.items()}

_TOPIC_TERMS = {
    "investment_risk": ("invest", "investing", "investment", "investments", "investor", "risk", "risks", "risky", "losing", "lose", "loss", "losses"),
    "saving": ("save", "saving", "savings", "saved"),
    "debt": ("debt", "debts", "loan", "loans", "emi", "emis", "owe", "borrow", "borrowing", "mortgage", "credit card"),
    "goals": ("goal", "goals", "house", "home", "education", "wedding", "down payment", "college", "tuition"),
    "liquidity": ("cash", "withdraw", "withdrawal", "access my money", "liquid", "liquidity"),
    "market": ("market", "markets", "stock market", "stock", "stocks", "volatile", "volatility", "crash", "share price"),
    "retirement": ("retire", "retirement", "retired", "pension"),
    "emergency_fund": ("emergency fund", "emergency", "emergencies", "rainy day"),
}
_TOPICS = {topic: _terms(terms) for topic, terms in _TOPIC_TERMS.items()}
_WEAK_CONTEXT = ("goal", "goals", "house", "home", "education", "wedding", "college", "tuition", "car", "vacation")
_STRONG_CONTEXT = tuple(sorted({t for terms in _TOPIC_TERMS.values() for t in terms} - set(_WEAK_CONTEXT) - {"losing", "lose", "loss", "losses"} | {
    "money", "income", "salary", "expense", "expenses", "budget", "interest", "returns", "wealth", "financial", "finance", "finances", "insurance", "tax", "taxes", "inflation",
    "asset", "assets", "equity", "equities", "etf", "sip", "dividend", "bond", "bonds", "fund", "funds", "portfolio", "rent", "spend", "spending", "afford", "bank", "credit",
    "paycheck", "net worth"}))
_STRONG = _terms(_STRONG_CONTEXT)
_WEAK = _terms(_WEAK_CONTEXT)
_OFFTOPIC = _terms(("weather", "rain", "raining", "sunny", "snow", "football", "cricket", "movie", "film", "pizza", "lunch", "dinner", "breakfast", "traffic", "train", "bus",
                    "music", "song", "birthday", "vegetables", "groceries", "grocery", "coffee", "gym", "recipe"))

# Explicit preference phrases (regular expressions over the lower-cased clause). `explicit` stand alone; `generic` are single words that are only a preference after a stance verb.
_PREFERENCE_PATTERNS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "capital_preservation": (
        (r"protect(?:ing)? my", r"preserv(?:e|ing) (?:my|the|our)", r"avoid(?:ing)? (?:losing|loss(?:es)?)", r"(?:do not|don't|dont) want to lose", r"(?:cannot|can't|can not) afford to lose",
         r"low[- ]risk", r"keep my money safe", r"capital preservation", r"play(?:ing)? it safe", r"(?:minimi[sz]e|reduce|limit) (?:my )?risk",
         r"conservative (?:approach|investor|portfolio|strategy)"),
        (r"safe(?:ly|r|ty)?", r"conservative(?:ly)?")),
    "growth_seeking": (
        (r"grow(?:ing)? my", r"higher returns?", r"maxim[iz]e(?:ing)? (?:my )?returns?", r"take (?:on )?more risk", r"more aggressive", r"aggressive (?:growth|approach|portfolio|investing|investor)",
         r"long[- ]term growth", r"build(?:ing)? (?:my )?wealth", r"comfortable (?:with|taking|in taking) (?:\w+[ -]){0,2}risks?",
         r"(?:willing|ready|happy|prepared|able) to (?:take|accept|bear) (?:\w+[ -]){0,2}risks?"),
        (r"growth", r"aggressive(?:ly)?")),
    "liquidity_access": (
        (r"access (?:to )?my (?:money|cash|funds)", r"keep(?:ing)? (?:some |enough )?cash", r"(?:easy|quick|ready|immediate) access", r"cash (?:available|on hand|ready)", r"stay(?:ing)? liquid",
         r"need(?:ing)? (?:some |more )?cash"),
        (r"withdraw(?:als?)?", r"liquid", r"emergency fund")),
    "debt_reduction": (
        (r"reduc(?:e|ing) my (?:debt|loan|emi)s?", r"clear(?:ing)? my (?:debt|loan|emi)s?", r"get(?:ting)? out of debt", r"debt[- ]free", r"pay(?:ing)? down (?:my )?(?:debt|loan)s?"),
        (r"pay(?:ing)? off", r"repay(?:ing|ment)?")),
    "balanced_growth": (
        (r"balanced (?:approach|portfolio|growth|mix|strategy)", r"balance (?:between )?(?:growth|risk) and (?:safety|security|stability|growth|risk)", r"(?:steady|moderate) (?:growth|risk|returns?)",
         r"mix of (?:growth|safety)"),
        (r"balanced",)),
}
_PREFERENCE_RX = {
    code: (re.compile(r"(?<![a-z'])(?:" + "|".join(explicit) + r")(?![a-z'])"), re.compile(r"(?<![a-z'])(?:" + "|".join(generic) + r")(?![a-z'])"))
    for code, (explicit, generic) in _PREFERENCE_PATTERNS.items()
}
_OPPOSING = {frozenset(("capital_preservation", "growth_seeking"))}

_STANCE = re.compile(r"\b(?:want|wants|wish|prefer|need|would like|aim|aiming|looking to|plan to|planning to|hope to|prioriti[sz]e|care about|like to|trying to|try to|intend to)\b")
_FIRST_PERSON = re.compile(r"\b(?:i|me|my|mine|myself|we|our|us)\b")
_PAST = re.compile(r"\b(?:used to|back then|in the past|previously|formerly|years ago|once was)\b|\b(?:was|were) (?:\w+ )?(?:afraid|scared|nervous|worried|anxious|concerned|stressed)\b")
# A clause is HYPOTHETICAL (not the user's current view, like a past feeling) when it carries a conditional marker or a conditional-mood phrase, or is the consequent of a conditional clause in
# the same sentence ("If the market falls, I would be worried"). Indirect questions ("tell me if I should worry") and idioms ("if possible") are not conditions and are removed first.
# Conservative on purpose: a clause with a marker is not read as a current feeling or preference even when part of it is ("I feel safe even if prices fall").
_HYPOTHETICAL = re.compile(
    r"\b(?:if|unless|suppose|supposing|imagine|imagining|assuming|in case|provided that|as long as|were i|had i)\b|\bshould (?:the|my|our|it|there|prices?|markets?|interest|inflation)\b"
    r"|\bwish(?:ed)? (?:i|we) (?:could|would|had|were|didn't|hadn't)\b|\b(?:would|might|could) (?:be|feel|get|become|panic|worry|lose|start)\b")
_NOT_A_CONDITION = re.compile(r"\b(?:tell|ask|asking|wonder|wondering|know|check|see|sure|unsure)\s+(?:me\s+|you\s+)?if\b|\bif (?:possible|needed|necessary|any|ever)\b")
_CONSEQUENT_BREAK = re.compile(r"^(?:[.!?;\n:]|but|however|although|though|yet|whereas|while)", re.IGNORECASE)
# POLITE FORMS (decision AP8 `CONTEXT_DEPENDENT`, owner, 2026-10-29): "I would like ..." and "I would prefer ..." state a current want unless a condition is attached. A condition BEFORE the clause or inside
# it is handled above; this covers the one remaining form, a condition that FOLLOWS the polite clause in the same sentence ("..., if my income increased", "..., but only if ..."). Limited to these two phrases.
_POLITE = re.compile(r"\bwould (?:like|prefer)\b")
_TRAILING_CONDITION = re.compile(r"^\W*(?:and\s+)?(?:only\s+)?(?:if|unless|provided(?: that)?|assuming|as long as|in case)\b")
_SENTENCE_END = re.compile(r"^\s*[.!?;\n:]")
_OTHER = re.compile(
    r"^\W*(?:(?:and|so|because|also|then)\s+)?(?:he|she|they|he's|she's|they're|people|everyone|everybody|others|someone|somebody|(?:some )?(?:friends?|colleagues?|coworkers?|neighbou?rs?)|"
    r"(?:my|our|his|her|their) (?:friends?|wife|husband|partner|brother|sister|father|mother|dad|mom|mum|parents?|son|daughter|uncle|aunt|cousin|colleagues?|coworkers?|boss|neighbou?rs?|family|relatives?))\b")
_NEGATORS = ("not", "no", "never", "hardly", "barely", "rarely", "without", "neither", "nor", "none", "nobody")
_NEGATION_WINDOW = 4
_SPLIT = re.compile(r"[.!?]+(?=\s|$)|[;\n]|:(?=\s|$)|,(?!\d)|\b(?:but|however|although|though|yet|whereas|while)\b|\b(?:and|so|because)\b(?=\s+(?:i|i'm|i've|i'd|we|he|she|they)\b)", re.IGNORECASE)
_QUOTED = re.compile(r'"[^"]+"|“[^”]+”')
_TOKEN = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
_WORD = re.compile(r"[a-z']+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EMAIL = re.compile(r"\S+@\S+\.\S+")
_URL = re.compile(r"(?:https?://|www\.)\S+")
_LONG_DIGITS = re.compile(r"(?:\d[ -]?){6,}")
_LEADING_CONJUNCTION = re.compile(r"^(?:and|so|because|also|then|or)\s+", re.IGNORECASE)
_ENGLISH_FUNCTION_WORDS = frozenset((
    "i", "me", "my", "mine", "we", "our", "us", "you", "your", "he", "she", "it", "they", "them", "the", "a", "an", "and", "or", "but", "is", "am", "are", "was", "were", "be", "been", "to", "of",
    "in", "on", "at", "for", "with", "about", "that", "this", "these", "those", "not", "no", "do", "does", "did", "have", "has", "had", "will", "would", "can", "could", "should", "want", "need",
    "so", "if", "than", "then", "more", "much", "too", "very", "off", "up", "down", "out", "from", "by", "as", "what", "how", "when", "why", "please", "just", "now", "also", "all", "some",
    "any", "i'm", "i've", "i'd", "i'll", "don't", "can't", "isn't", "won't", "doesn't", "didn't", "it's", "that's", "there", "here", "who", "which", "because", "even", "still", "only"))


class UserTextError(ValueError):
    """The text cannot be analysed at all (too long, or contains control characters). The message never contains the text."""


@dataclass(frozen=True)
class Evidence:
    label: str            # the cue family or the preference / topic code
    phrase: str           # a short, sanitised excerpt of the user's own words


@dataclass(frozen=True)
class StatedPreference:
    code: str
    evidence: Evidence
    status: str = "unconfirmed"
    requires_confirmation: bool = True


@dataclass(frozen=True)
class UserTextAnalysis:
    status: str                                   # analysed | unavailable
    unavailable_reason: str | None
    sentiment: str | None
    emotional_tone: str | None
    topics: tuple[str, ...]
    preferences: tuple[StatedPreference, ...]
    evidence: tuple[Evidence, ...]
    confidence: float | None                      # None unless a CALIBRATED model supplied it; always None for the rules baseline
    requires_confirmation: bool
    method: str = METHOD_RULES                    # rules_baseline | trained_model | hybrid | unavailable
    validation_status: str = VALIDATION_STATUS
    limitations: tuple[str, ...] = LIMITATIONS
    model_version: str = METHOD_VERSION
    financial_relevance: str | None = None        # relevant | unrelated | ambiguous (None when no text)
    confidence_band: str = "unavailable"
    abstained: bool = False
    abstain_reason: str | None = None
    interpretation_state: str = "valid"           # valid | weak | abstained | unavailable
    fallback_used: bool = False                   # a trained model was configured but could not answer; the rules baseline answered
    privacy_status: str = PRIVACY_STATUS
    model_name: str | None = None                 # the trained model's name, when one answered
    class_probabilities: Mapping[str, float] | None = None   # the model's own probabilities per class (RAW unless `confidence_calibration_status` says calibrated)
    confidence_calibration_status: str = "not_applicable"    # calibrated | uncalibrated | not_applicable (no model answered)
    sentiment_intensity: float | None = None      # -1.0 .. +1.0 from a VALIDATED regression head only; None otherwise
    rules_label: str | None = None                # what the rules baseline alone concluded, kept for comparison
    disagreement: bool = False                    # the model and the rules baseline read different sentiments
    fallback_reason: str | None = None            # one of FALLBACK_REASONS when `fallback_used`


@dataclass(frozen=True)
class ModelReading:
    """What an approved, validated sentiment model returns. The model supplies its own abstention threshold and band cut-offs from ITS validation: this module defines none."""

    sentiment: str                                # positive | negative | neutral | mixed | uncertain
    probability: float | None                     # probability of that label in [0, 1], or None
    calibrated: bool                              # True only when the probability is calibrated and documented
    model_version: str
    validation_status: str
    abstain_below: float | None = None
    band_cutoffs: tuple[float, float] | None = None   # (medium_minimum, high_minimum)
    class_probabilities: Mapping[str, float] | None = None   # the probability of every class the model has (positive / negative / neutral), summing to 1
    intensity: float | None = None                    # -1.0 .. +1.0, only from a validated regression head
    model_name: str | None = None


class SentimentModel(Protocol):
    """The seam for a trained model (`core/sentiment_model.py` implements it). It must run locally on the text in memory; it must not log, persist or transmit the text.
    A model that raises (an exception may carry `.reason`, one of FALLBACK_REASONS) or returns anything outside the `ModelReading` contract is a failure, never a result."""

    def interpret(self, text: str) -> ModelReading: ...


def validate_text(text: str | None) -> str | None:
    """The cleaned text, or None when nothing was provided. Raises `UserTextError` without echoing the text."""
    if text is None:
        return None
    if not isinstance(text, str):
        raise UserTextError("text must be a string")
    if _CONTROL.search(text):
        raise UserTextError("text contains control characters")
    cleaned = " ".join(text.split())
    if len(cleaned) > MAX_TEXT_CHARS:
        raise UserTextError(f"text is longer than {MAX_TEXT_CHARS} characters")
    return cleaned or None


def _evidence_phrase(raw: str) -> str:
    """A short excerpt that is safe to return: whitespace-collapsed, links / e-mail addresses / long digit runs masked, a leading conjunction removed, bounded."""
    phrase = " ".join(raw.split())
    phrase = _URL.sub("[link]", phrase)
    phrase = _EMAIL.sub("[email]", phrase)
    phrase = _LONG_DIGITS.sub("[number]", phrase)
    phrase = _LEADING_CONJUNCTION.sub("", phrase).strip(" ,;:-")
    return phrase if len(phrase) <= EVIDENCE_CHARS else phrase[: EVIDENCE_CHARS - 1].rstrip() + "…"


@dataclass(frozen=True)
class _Clause:
    text: str           # original case, quoted spans blanked
    low: str            # lower case, curly apostrophes straightened
    speaker: str        # self | other
    past: bool
    hypothetical: bool = False


def _clauses(work: str) -> list[_Clause]:
    cuts: list[tuple[int, int, str]] = []
    previous = 0
    for m in _SPLIT.finditer(work):
        cuts.append((previous, m.start(), m.group()))
        previous = m.end()
    cuts.append((previous, len(work), ""))
    out: list[_Clause] = []
    speaker = "self"
    carry = False       # the previous clause was hypothetical and this one continues its sentence (a consequent)
    open_link = False   # the last clause and the next one are in the same sentence (no sentence end between them)
    for a, b, delimiter in cuts:
        segment = work[a:b]
        if _TOKEN.search(segment):
            low = segment.lower().replace("’", "'")
            if _OTHER.match(low):
                speaker = "other"
            elif _FIRST_PERSON.search(low):
                speaker = "self"
            hypothetical = carry or bool(_HYPOTHETICAL.search(_NOT_A_CONDITION.sub(" ", low)))
            if open_link and out and _POLITE.search(out[-1].low) and not out[-1].hypothetical and _TRAILING_CONDITION.match(low) and not _STANCE.search(low):
                out[-1] = replace(out[-1], hypothetical=True)           # a polite form followed by its BARE condition (no want of its own) is conditional, not a current want
            out.append(_Clause(segment, low, speaker, bool(_PAST.search(low)), hypothetical))
            carry = hypothetical
            open_link = True
        if _SENTENCE_END.match(delimiter):
            open_link = False
        if _CONSEQUENT_BREAK.match(delimiter.strip()):
            carry = False
    return out


def _negated(low: str, index: int) -> bool:
    words = _WORD.findall(low[max(0, index - 40):index])[-_NEGATION_WINDOW:]
    return any(w in _NEGATORS or w.endswith("n't") for w in words)


def _script_and_quality(cleaned: str) -> str | None:
    """An abstain reason when the text is unusable before any interpretation, else None."""
    letters = [c for c in cleaned if c.isalpha()]
    visible = [c for c in cleaned if not c.isspace()]
    if not letters or len(letters) / max(1, len(visible)) < MIN_LETTER_RATIO:
        return "low_quality_text"
    non_latin = sum(1 for c in letters if not (ord(c) < 0x250 or 0x1E00 <= ord(c) <= 0x1EFF))
    if non_latin / len(letters) > MAX_NON_LATIN_SHARE:
        return "unsupported_language"
    tokens = _TOKEN.findall(cleaned.lower().replace("’", "'"))
    if len(tokens) < MIN_WORDS:
        return "too_short"
    if len(tokens) >= MIN_TOKENS_FOR_LANGUAGE_CHECK and sum(1 for t in tokens if t in _ENGLISH_FUNCTION_WORDS) / len(tokens) < MIN_ENGLISH_FUNCTION_SHARE:
        return "unsupported_language"
    return None


def _abstain(reason: str, relevance: str | None, notes: tuple[str, ...] = (), fallback: bool = False) -> UserTextAnalysis:
    return UserTextAnalysis(
        "analysed", None, "insufficient_evidence", "unknown", (), (), (), None, False, METHOD_RULES, VALIDATION_STATUS, LIMITATIONS + notes, METHOD_VERSION,
        relevance or "ambiguous", "unavailable", True, reason, "abstained", fallback)


def _band(probability: float, cutoffs: tuple[float, float] | None) -> str:
    if cutoffs is None:
        return "unavailable"
    medium, high = cutoffs
    return "high" if probability >= high else "medium" if probability >= medium else "low"


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _valid_reading(reading: object) -> bool:
    if not (isinstance(reading, ModelReading) and reading.sentiment in _MODEL_SENTIMENTS and isinstance(reading.model_version, str) and bool(reading.model_version)
            and isinstance(reading.validation_status, str) and bool(reading.validation_status)):
        return False
    if reading.probability is not None and not (_is_number(reading.probability) and 0.0 <= float(reading.probability) <= 1.0):
        return False
    if reading.abstain_below is not None and not (_is_number(reading.abstain_below) and 0.0 <= float(reading.abstain_below) <= 1.0):
        return False
    if reading.band_cutoffs is not None and not (len(reading.band_cutoffs) == 2 and all(_is_number(c) for c in reading.band_cutoffs) and reading.band_cutoffs[0] <= reading.band_cutoffs[1]):
        return False
    if reading.intensity is not None and not (_is_number(reading.intensity) and -1.0 <= float(reading.intensity) <= 1.0):
        return False
    if reading.class_probabilities is not None:
        probabilities = reading.class_probabilities
        if not (isinstance(probabilities, Mapping) and probabilities and set(probabilities) <= set(_MODEL_CLASSES) and all(_is_number(v) and 0.0 <= float(v) <= 1.0 for v in probabilities.values())
                and abs(sum(float(v) for v in probabilities.values()) - 1.0) <= 1e-3):
            return False
    return True


def _model_reading(model: SentimentModel, text: str) -> tuple[ModelReading | None, str | None]:
    """A VALID model reading, or (None, a fixed reason code) if the model failed or returned something outside the contract. The exception (which could carry text) is never kept:
    only its `reason`, and only when it is one of the fixed `FALLBACK_REASONS`."""
    try:
        reading = model.interpret(text)
    except Exception as exc:  # noqa: BLE001 -- any model failure falls back to the rules; the exception object is dropped on purpose
        reason = getattr(exc, "reason", None)
        return None, reason if isinstance(reason, str) and reason in FALLBACK_REASONS else "inference_failed"
    return (reading, None) if _valid_reading(reading) else (None, "invalid_output")


def _fallback_or_abstain(analysis: UserTextAnalysis, reason: str, allow_fallback: bool, abstain_reason: str = "model_unavailable") -> UserTextAnalysis:
    """The model did not answer. With fallback allowed the rules baseline answers and says why; otherwise the text is not interpreted. Never silent."""
    if allow_fallback:
        return replace(analysis, fallback_used=True, fallback_reason=reason, limitations=analysis.limitations + (NOTE_FALLBACK,))
    return replace(_abstain(abstain_reason, analysis.financial_relevance, tuple(n for n in analysis.limitations[len(LIMITATIONS):])), fallback_used=True, fallback_reason=reason)


def _model_input(own: list[_Clause]) -> str:
    """What the model reads: only the user's OWN, CURRENT clauses (quoted spans blanked, other people's clauses and past feelings left out), so the model cannot resurface what the
    rules safeguards excluded. Clause boundaries become full stops."""
    current = [c.text.strip(" ,;:-") for c in own if not c.past and not c.hypothetical]
    chosen = [t for t in current if t] or [c.text.strip(" ,;:-") for c in own if c.text.strip(" ,;:-")]
    return ". ".join(chosen)


def analyse_user_text(text: str | None, model: SentimentModel | None = None, *, model_unavailable_reason: str | None = None, allow_fallback: bool = True) -> UserTextAnalysis:
    """`model` is a trained model (or None). `model_unavailable_reason` says a model IS configured but cannot be used (one of FALLBACK_REASONS): the rules baseline then answers and
    the result says so (`fallback_used`), unless `allow_fallback` is false, in which case the text is not interpreted. With neither, the rules baseline is simply the method."""
    cleaned = validate_text(text)
    if cleaned is None:
        return UserTextAnalysis("unavailable", "No text was provided. No sentiment is inferred and none is assumed.", None, None, (), (), (), None, False,
                                METHOD_UNAVAILABLE, VALIDATION_STATUS, LIMITATIONS, METHOD_VERSION, None, "unavailable", False, None, "unavailable")

    quality = _script_and_quality(cleaned)
    if quality in ("low_quality_text", "unsupported_language"):
        return _abstain(quality, "ambiguous")

    blanked = _QUOTED.sub(lambda m: " " * len(m.group()), cleaned)
    quoted = blanked != cleaned
    clauses = _clauses(blanked)
    own = [c for c in clauses if c.speaker == "self"]
    others_seen = any(c.speaker == "other" for c in clauses)
    notes: list[str] = []

    # --- cues, read clause by clause: only the user's own, current, non-negated words count
    affect: dict[str, list[tuple[_Clause, int]]] = {family: [] for family in _AFFECT}
    negation_seen = past_seen = hypothetical_seen = False
    for clause in own:
        for family, rx in _AFFECT.items():
            for m in rx.finditer(clause.low):
                if _negated(clause.low, m.start()):
                    negation_seen = True
                elif clause.past:
                    past_seen = True
                elif clause.hypothetical:
                    hypothetical_seen = True
                else:
                    affect[family].append((clause, m.start()))
    negative = [hit for family in _NEGATIVE_FAMILIES for hit in affect[family]]
    positive = [hit for family in _POSITIVE_FAMILIES for hit in affect[family]]

    topics = tuple(topic for topic, rx in _TOPICS.items() if any(rx.search(c.low) for c in own))

    prefs: list[StatedPreference] = []
    for code, (explicit, generic) in _PREFERENCE_RX.items():
        for clause in own:
            if clause.past:
                continue
            if clause.hypothetical:     # a preference stated only under a condition is not a current preference
                hypothetical_seen = hypothetical_seen or bool(explicit.search(clause.low) or (generic.search(clause.low) and _STANCE.search(clause.low)))
                continue
            hit = next((m for m in explicit.finditer(clause.low) if not _negated(clause.low, m.start())), None)
            if hit is None:
                hit = next((m for m in generic.finditer(clause.low) if not _negated(clause.low, m.start()) and _STANCE.search(clause.low[: m.start()])), None)
            if hit is not None:
                prefs.append(StatedPreference(code, Evidence(code, _evidence_phrase(clause.text))))
                break
    found_codes = {p.code for p in prefs}
    opposed = set().union(*(pair for pair in _OPPOSING if pair <= found_codes))
    if opposed:
        prefs = [p for p in prefs if p.code not in opposed]
        notes.append(NOTE_OPPOSING)

    # --- stage 3: financial relevance, over the user's own clauses
    own_low = " ".join(c.low for c in own)
    strong = set(_STRONG.findall(own_low))
    weak = set(_WEAK.findall(own_low))
    first_person = any(_FIRST_PERSON.search(c.low) for c in own)
    stance = bool(_STANCE.search(own_low))
    off_topic = bool(_OFFTOPIC.search(own_low))
    has_signal = bool(negative or positive or prefs)
    if len(strong) >= 2 or (strong and first_person) or (weak and stance and first_person):
        relevance = "relevant"
        if off_topic and len(strong) < 2 and not stance and not has_signal:
            relevance = "ambiguous"     # a word with two meanings next to everyday talk ("I went to the market for vegetables")
    elif not strong and not weak and off_topic:
        relevance = "unrelated"
    else:
        relevance = "ambiguous"
    if quoted:
        notes.append(NOTE_QUOTED)
    if others_seen:
        notes.append(NOTE_OTHERS)
    if negation_seen:
        notes.append(NOTE_NEGATION)
    if past_seen:
        notes.append(NOTE_PAST)
    if hypothetical_seen:
        notes.append(NOTE_HYPOTHETICAL)

    if quality == "too_short":
        return _abstain("too_short", relevance, tuple(notes))
    if relevance == "unrelated":
        return _abstain("unrelated_text", relevance, tuple(notes))
    if relevance == "ambiguous":
        return _abstain("ambiguous_context", relevance, tuple(notes))

    # --- stage 5: sentiment and tone (a negated cue is dropped; only a negated cue leaves the reading `uncertain`)
    if negative and positive:
        sentiment = "mixed"
    elif negative:
        sentiment = "negative"
    elif positive:
        sentiment = "positive"
    elif negation_seen or hypothetical_seen:     # something was said that cannot be read as a current view: never a label
        sentiment = "uncertain"
    elif topics or prefs:
        sentiment = "neutral"
    else:
        return _abstain("no_usable_evidence", relevance, tuple(notes))
    tone = next((family for family in _TONE_PRIORITY if affect[family]), "unknown" if sentiment == "uncertain" else "neutral")

    evidence: list[Evidence] = []
    for label, hits in (("negative_cue", negative), ("positive_cue", positive)):
        if hits:
            clause, _ = min(hits, key=lambda h: h[1] + 10_000 * own.index(h[0]))
            evidence.append(Evidence(label, _evidence_phrase(clause.text)))
    evidence = evidence[:MAX_EVIDENCE_ITEMS]

    signals = len(negative) + len(positive) + len(prefs)
    state = "valid" if (signals >= MIN_SIGNALS_ALONE or (signals >= MIN_SIGNALS_WITH_TOPIC and topics)) and sentiment != "uncertain" else "weak"
    if len(notes) and NOTE_OPPOSING in notes:
        state = "weak"

    analysis = UserTextAnalysis("analysed", None, sentiment, tone, topics, tuple(prefs), tuple(evidence), None, bool(prefs), METHOD_RULES, VALIDATION_STATUS,
                                LIMITATIONS + tuple(notes), METHOD_VERSION, relevance, "unavailable", False, None, state, rules_label=sentiment)
    if model is None:
        if model_unavailable_reason is not None:        # a model is configured but unusable (missing dependency, artifact, validation ...): never hidden
            return _fallback_or_abstain(analysis, model_unavailable_reason if model_unavailable_reason in FALLBACK_REASONS else "load_failed", allow_fallback)
        return analysis

    # --- the trained model (ADR-052): it reads only the user's own current clauses; every earlier stage and every rules safeguard has already run
    reading, failure = _model_reading(model, _model_input(own))
    if reading is None:
        return _fallback_or_abstain(analysis, failure or "inference_failed", allow_fallback)
    probability = None if reading.probability is None else float(reading.probability)
    if probability is not None and reading.abstain_below is not None and probability < float(reading.abstain_below):
        return _fallback_or_abstain(analysis, "below_threshold", allow_fallback, "model_confidence_below_threshold")
    calibrated = bool(reading.calibrated) and probability is not None
    rules_label = analysis.sentiment
    disagreement = reading.sentiment != rules_label and reading.sentiment != "uncertain" and rules_label != "uncertain"
    final, final_state, extra = reading.sentiment, analysis.interpretation_state, [NOTE_MODEL_TONE]
    if rules_label == "uncertain":                       # only a negated expression: the rules safeguard is never overridden by a model
        final, final_state = "uncertain", "weak"
        extra.append(NOTE_SAFEGUARD_KEPT)
    elif disagreement and frozenset((reading.sentiment, rules_label)) in _OPPOSITE:
        final, final_state = "uncertain", "weak"          # opposite polarities, unresolved: no sentiment is claimed
        extra.append(NOTE_DISAGREE_UNRESOLVED)
    elif disagreement:
        extra.append(NOTE_DISAGREE_MODEL)                 # the model's label is used and the rules' reading is kept beside it
    overridden = final != reading.sentiment
    return replace(
        analysis, sentiment=final, interpretation_state=final_state, method=METHOD_HYBRID, model_version=reading.model_version, model_name=reading.model_name,
        validation_status=reading.validation_status, confidence=probability if calibrated and not overridden else None,
        confidence_band=_band(probability, reading.band_cutoffs) if calibrated and not overridden and probability is not None else "unavailable",
        confidence_calibration_status="calibrated" if calibrated else "uncalibrated",
        class_probabilities=None if reading.class_probabilities is None else {k: float(v) for k, v in reading.class_probabilities.items()},
        sentiment_intensity=None if reading.intensity is None or overridden else float(reading.intensity), rules_label=rules_label, disagreement=disagreement,
        limitations=analysis.limitations + tuple(extra))


__all__ = ["ABSTAIN_MESSAGES", "ABSTAIN_REASONS", "CONFIDENCE_BANDS", "EMOTIONS", "EVIDENCE_CHARS", "Evidence", "INTERPRETATION_STATES", "LIMITATIONS", "MAX_TEXT_CHARS", "METHODS",
           "CALIBRATION_STATUSES", "FALLBACK_REASONS", "METHOD_HYBRID", "METHOD_RULES", "METHOD_TRAINED", "METHOD_UNAVAILABLE", "METHOD_VERSION", "ModelReading", "PREFERENCES", "PREFERENCE_STATUSES", "PRIVACY_STATUS", "RELEVANCE",
           "SENTIMENTS", "SentimentModel", "StatedPreference", "TOPICS", "UserTextAnalysis", "UserTextError", "VALIDATION_STATUS", "analyse_user_text", "validate_text"]
