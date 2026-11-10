"""Guards for rubric rules 11 and 12 (hypothetical, conditional, wish and counterfactual statements) in `docs/USER_TEXT_ANNOTATION_RUBRIC.md` (owner-approved edit, 2026-10-28).

The rubric stays a DRAFT: these tests check that the new rules are present in the part annotators receive, that the existing rules and label sets are untouched, that
(the manifest hashes are checked in `tests/backend/scripts/test_rubric_hash_records.py`) and that the rules baseline agrees with the rubric's examples wherever it can (and that its one
documented, deliberate disagreement is still documented). Invented sentences only; no label here is data and no accuracy is measured."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from wealthpilot.core.user_text_sentiment import analyse_user_text

ROOT = Path(__file__).resolve().parents[3]
RUBRIC = ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md"
SENTIMENTS = {"positive", "negative", "neutral", "mixed", "uncertain"}
TONES = {"concerned", "hopeful", "none"}
PREFERENCES = {"capital_preservation", "growth_seeking", "liquidity_access", "debt_reduction"}
NO_LABEL = {"uncertain", "insufficient_evidence"}          # the baseline abstains (insufficient_evidence) or says uncertain: neither is a sentiment label


def load_builder():
    spec = importlib.util.spec_from_file_location("build_dry_run_package_for_rubric_tests", ROOT / "scripts" / "build_dry_run_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rubric_text() -> str:
    return RUBRIC.read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.fixture(scope="module")
def excerpt() -> str:
    return load_builder().extract_annotator_rubric(RUBRIC.read_text(encoding="utf-8"))


def example_rows(text: str) -> list[tuple[str, str, str, str]]:
    return [(m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip())
            for m in re.finditer(r'^\s*\|\s*"(.+?)"\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', text, re.MULTILINE)]


# ----------------------------------------------------------------------------------------------- the rules are in the part annotators receive
def test_rules_11_and_12_are_in_the_annotator_excerpt_and_say_what_was_approved(excerpt):
    assert "11. **Hypothetical, conditional, wish and counterfactual statements are not the person's current view.**" in excerpt
    assert "12. **Labelling a text that contains such a clause.**" in excerpt
    for phrase in ("is **not** labelled as the person's current `sentiment`, `emotional_tone` or `preferences`", "wishes for something that is not so", "describes a counterfactual",
                   "does **not** make the statement hypothetical", "do not discard it because a conditional", "label that current view only", "Negating a hypothetical clause does not make it current"):
        assert " ".join(phrase.split()) in " ".join(excerpt.split()), phrase


def test_the_examples_named_in_the_approval_are_present_with_the_stated_outcome(excerpt):
    rows = {text: (sentiment, tone, prefs) for text, sentiment, tone, prefs in example_rows(excerpt)}
    assert rows["If the market crashes, I would be worried."][0] == "uncertain"
    assert rows["If I had more money, I would want higher returns."][0] == "uncertain" and rows["If I had more money, I would want higher returns."][2] == "none"
    safe = rows["I feel safe even if prices fall."]
    assert safe[0] == "positive" and safe[2] == "none"           # the current clause is preserved, not discarded for carrying a conditional clause
    assert len(rows) == 6


def test_every_example_uses_only_the_rubric_label_sets(excerpt):
    for text, sentiment, tone, prefs in example_rows(excerpt):
        assert sentiment in SENTIMENTS, text
        assert tone.split(",")[0].strip() in TONES, text
        assert prefs == "none" or set(re.findall(r"[a-z_]+", prefs)) <= PREFERENCES, text


def test_the_existing_rules_and_label_sets_are_unchanged(excerpt):
    leads = ["1. **Only the text.**", "2. **sentiment** is the overall attitude", "3. **emotional_tone** is set only when an emotion", "4. **topics**: tag every topic", "5. **preferences**: tag a preference only",
             "6. **Negation** flips or removes the cue", "7. **Never use a label to express a recommendation**", "8. **Contradictory statements**", "9. **Unsupported language**", "10. **What the annotator sees**"]
    positions = [excerpt.index(lead) for lead in leads]
    assert positions == sorted(positions) and positions[-1] < excerpt.index("11. **Hypothetical")
    assert "| `sentiment` | positive, negative, neutral, mixed, uncertain | exactly one |" in excerpt
    assert "| `emotional_tone` | concerned, hopeful, none |" in excerpt
    assert "Hedged wants (\"maybe\", \"might\") are still tagged but flagged `hedged`." in " ".join(excerpt.split())


def test_the_annotator_excerpt_carries_no_author_only_wording(excerpt):
    assert load_builder().leak_problems("RUBRIC_EXCERPT.md", excerpt) == []


# ----------------------------------------------------------------------------------------------- the draft status
def test_the_rubric_does_not_claim_to_be_frozen_validated_or_measured(rubric_text):
    head = rubric_text[: rubric_text.index("<!-- annotator-excerpt:start -->")]
    assert "not frozen" in head and "no accuracy has been measured" in head and "no annotator has received it" in head
    assert "validated" not in " ".join(re.findall(r"\b(?:is|are|was|now)\s+validated\b", head))


# ----------------------------------------------------------------------------------------------- the baseline against the rubric examples
@pytest.mark.parametrize("text", ["If the market crashes, I would be worried about my savings.", "If I had more money, I would want higher returns on my investments.",
                                  "If the market crashes I would not be worried about my savings.", "I wish I could take more risk with my investments."])
def test_hypothetical_conditional_wish_and_negated_hypothetical_text_gets_no_label_tone_or_preference(text):
    result = analyse_user_text(text)
    assert result.sentiment in NO_LABEL and result.preferences == () and result.emotional_tone in {"unknown", None} and result.evidence == ()


@pytest.mark.parametrize("text", ['My advisor said "if the market crashes you will be worried about your savings".', "My friend says that if the market crashes he would be worried about his savings.",
                                  'He told me "if I had more money I would want higher returns on my investments".'])
def test_quoted_or_third_person_hypothetical_text_is_never_the_users_view(text):
    result = analyse_user_text(text)
    assert result.sentiment in NO_LABEL | {"neutral"} and result.preferences == () and result.evidence == () and result.emotional_tone in {"unknown", "neutral", None}


def test_a_current_clause_beside_a_hypothetical_one_is_labelled_and_the_hypothetical_one_is_not():
    result = analyse_user_text("I am worried about my savings, and if the market crashes I would be even more worried.")
    assert (result.sentiment, result.emotional_tone, result.interpretation_state) == ("negative", "concerned", "valid")
    assert len(result.evidence) == 1 and "market crashes" not in result.evidence[0].phrase


@pytest.mark.parametrize("text,sentiment,tone,preference", [
    ("I am worried about my savings.", "negative", "concerned", None),
    ("I want higher returns on my investments.", "neutral", "neutral", "growth_seeking"),
    ("I want to keep my money safe in savings.", "neutral", "neutral", "capital_preservation"),
    ("I am not worried about my savings.", "uncertain", "unknown", None),
    ("I used to be afraid of the market but I am comfortable with my savings now.", "positive", "calm", None),
])
def test_current_statements_are_handled_exactly_as_before(text, sentiment, tone, preference):
    result = analyse_user_text(text)
    assert (result.sentiment, result.emotional_tone) == (sentiment, tone)
    assert [p.code for p in result.preferences] == ([preference] if preference else [])


def test_the_one_documented_disagreement_between_the_rubric_and_the_baseline_is_still_documented_and_still_real(rubric_text):
    # Rule 12 keeps "I feel safe ... even if ...". The baseline drops a whole clause that carries a conditional marker (ADR-050 addendum), so it does NOT label this positive.
    assert analyse_user_text("I feel safe about my savings even if the market falls.").sentiment != "positive"
    assert "Documented differences from the rules baseline (the baseline is NOT changed to match the rubric)" in " ".join(rubric_text.split())


# ----------------------------------------------------------------------------------------------- rule 13: other voices and other times (added 2026-10-29)
def rule_13(excerpt: str) -> str:
    start = excerpt.index("13. **Other voices and other times")
    return excerpt[start: excerpt.index("Every annotator also records", start)]


def test_rule_13_covers_quotations_other_people_and_past_feelings_and_routes_unsettled_cases_to_rubric_unclear(excerpt):
    text = " ".join(rule_13(excerpt).split())
    for phrase in ("Quoted text", "a statement about what another person thinks, feels or wants", "belonging to the past", "give no current `sentiment`, `emotional_tone` or `preferences`",
                   "The topics they mention are still tagged (rule 4)", "label that current view only", "count only for what they themselves say", "there is no current view to label",
                   "`sentiment` is `uncertain`, with no tone and no preference", "set `rubric_unclear`", "do not guess"):
        assert phrase in text, phrase


def test_rule_13_tags_topics_as_decided_ap9_and_the_baseline_difference_is_documented(rubric_text, excerpt):
    assert "topics they mention are still tagged" in " ".join(rule_13(excerpt).split())                      # AP9 TAG_TOPIC_ONLY (owner decision, 2026-10-29)
    assert "(d) the baseline reports no topic from a quotation or from another person's clause" in " ".join(rubric_text.split())


def test_rule_13_uses_only_the_existing_uncertain_label_and_adds_no_example(excerpt):
    text = rule_13(excerpt)
    assert {"positive", "negative", "neutral", "mixed", "uncertain"} & set(re.findall(r"[a-z]+", text.lower())) == {"uncertain"}       # AP1 to AP3: nothing current gives the existing label, no new one
    assert len(example_rows(excerpt)) == 6 and excerpt.count("| Text |") == 1                                           # still only the six illustrations of rules 11 and 12
    assert "rubric_unclear" in excerpt and excerpt.index("12. **Labelling") < excerpt.index("13. **Other voices")
    assert load_builder().leak_problems("RUBRIC_EXCERPT.md", excerpt) == []


def test_the_rubric_records_the_even_if_and_comma_less_decisions_and_keeps_rule_12_unchanged(rubric_text, excerpt):
    flat = " ".join(rubric_text.split())
    assert "decision: keep the documented difference; direct comparison with this rubric is not claimed for this case, which is reported as a separate group" in flat
    assert "decision: retain the baseline behaviour" in flat and "not covered by an explicit comparability decision and are flagged for the owner to confirm" in flat
    assert "does **not** make the statement hypothetical" in " ".join(excerpt.split()) and "I feel safe even if prices fall." in excerpt        # rule 12 and its example are as approved


@pytest.mark.parametrize("text", ['My advisor said "you should be worried about your savings and your debt".', "My friend is worried about his savings and his debt."])
def test_a_quotation_only_or_other_person_only_text_gives_no_current_view_from_the_baseline(text):
    result = analyse_user_text(text)
    assert result.sentiment == "insufficient_evidence" and result.interpretation_state == "abstained" and result.evidence == () and result.preferences == ()


def test_a_past_feeling_is_not_read_as_a_current_negative_view_and_the_nothing_current_label_is_not_uniform_across_the_baseline():
    past = analyse_user_text("I used to be afraid of losing my savings.")
    assert past.sentiment not in {"negative", "mixed"} and past.emotional_tone != "concerned" and past.evidence == ()
    assert past.sentiment == "neutral" and past.interpretation_state == "weak"                      # documented difference: the rubric (rule 13) says `uncertain` for a text with nothing current; the baseline reads past-only text as neutral and weak
    assert analyse_user_text('My advisor said "you should be worried about your savings and your debt".').sentiment != past.sentiment


def test_the_second_documented_disagreement_a_current_clause_joined_to_a_conditional_one_without_a_comma_is_pinned():
    joined = analyse_user_text("I am worried about my debt and if the market crashes I would be calm about my savings.")
    comma = analyse_user_text("I am worried about my debt, and if the market crashes I would be calm about my savings.")
    assert joined.sentiment == "uncertain" and joined.evidence == ()                                  # the current worry is lost (documented limit)
    assert (comma.sentiment, comma.emotional_tone) == ("negative", "concerned")                       # with a comma the baseline separates the clauses and labels the current one


# ----------------------------------------------------------------------------------------------- baseline behaviours described in the decision sheet (AP1 to AP9), pinned so a change is deliberate
def test_ap1_words_that_adopt_a_quotation_add_no_cue_and_the_quoted_span_is_blanked():
    result = analyse_user_text('My advisor says "keep your savings safe" and I agree with that for my savings.')
    assert result.evidence == () and result.preferences == () and result.sentiment in {"neutral", "uncertain"} and result.interpretation_state in {"weak", "abstained"}


def test_ap2_a_first_person_clause_after_another_persons_clause_is_labelled_and_the_other_persons_is_not():
    result = analyse_user_text("My friend is worried about his savings but I am confident about my investments.")
    assert (result.sentiment, result.emotional_tone) == ("positive", "hopeful") and all("friend" not in e.phrase for e in result.evidence)


def test_ap3_a_past_feeling_that_still_holds_is_not_recovered_without_a_cue_of_its_own():
    result = analyse_user_text("I used to be afraid of losing my savings and I still am.")
    assert result.evidence == () and result.emotional_tone != "concerned" and result.sentiment not in {"negative", "mixed"}


def test_ap8_polite_forms_are_current_wants_while_conditional_mood_forms_are_not():
    assert [p.code for p in analyse_user_text("I would like higher returns on my investments.").preferences] == ["growth_seeking"]
    assert [p.code for p in analyse_user_text("I might want higher returns on my investments.").preferences] == ["growth_seeking"]          # hedged, still tagged
    assert analyse_user_text("If I had more money I would want higher returns on my investments.").preferences == ()                  # conditional, not tagged


def test_ap9_topics_come_from_the_users_own_clauses_including_hypothetical_and_past_ones_but_not_from_quotations_or_other_people():
    assert {"debt", "market"} <= set(analyse_user_text("If the market crashes I would be worried about my debt.").topics)             # hypothetical clause: topics kept
    assert "saving" in analyse_user_text("I used to be afraid of losing my savings.").topics                                            # past clause: topics kept
    assert analyse_user_text('My advisor said "you should be worried about your savings and your debt".').topics == ()                 # quotation: none
    assert analyse_user_text("My friend is worried about his savings and his debt.").topics == ()                                       # another person: none


# ----------------------------------------------------------------------------------------------- AP8 CONTEXT_DEPENDENT: polite forms (owner decision, 2026-10-29)
def test_rule_12_states_the_context_dependent_polite_form_boundary_and_the_baseline_now_agrees_on_the_trailing_condition(excerpt):
    flat = " ".join(excerpt.split())
    for phrase in ('A polite form ("I would like ...", "I would prefer ...") states a current want unless a condition is attached to it', 'or after it in the same sentence ("..., if my income increased", "..., but only if ...")',
                   "A polite form with such a condition, or a counterfactual one, is not tagged", "a polite form followed by a separate sentence about a different condition is still current",
                   "quoted, said of another person or negated is not the person's current preference"):
        assert phrase in flat, phrase
    assert load_builder().leak_problems("RUBRIC_EXCERPT.md", excerpt) == []
    assert analyse_user_text("I would like higher returns on my investments, if my income increased.").preferences == ()
    assert [p.code for p in analyse_user_text("I would like higher returns on my investments.").preferences] == ["growth_seeking"]
