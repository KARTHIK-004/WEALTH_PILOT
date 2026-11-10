# Annotation rules (rubric v0-draft: labelling rules and flag definitions)

Draft, not frozen. You need only this document for the labelling rules.

## 1. Scope

Labels describe **the wording of one short text a customer chose to write** about their finances. They are not a diagnosis, a risk
tolerance, or advice. The questionnaire and risk assessment remain authoritative.

## 2. Label sets (must match `core/user_text_sentiment.py`)

| Field | Values | Cardinality |
| --- | --- | --- |
| `sentiment` | positive, negative, neutral, mixed, uncertain | exactly one |
| `emotional_tone` | concerned, hopeful, none | at most one **in the current code**; PROPOSED (O6, not in force): zero or more, plus the `ambiguous_tone` flag |
| `topics` | investment_risk, saving, debt, goals, liquidity | zero or more |
| `preferences` | capital_preservation, growth_seeking, liquidity_access, debt_reduction | zero or more |

## 3. Decision rules (apply in order)

1. **Only the text.** Label what is written, not what the person "probably" feels, and not their profile, income or any other record.
2. **sentiment** is the overall attitude expressed *toward the person's finances or financial situation*.
   - `positive` / `negative`: one direction clearly dominates.
   - `mixed`: both a clearly positive and a clearly negative attitude are expressed and neither dominates.
   - `neutral`: the text is about finances but expresses no attitude (a plain statement of fact or intent).
   - `uncertain`: the attitude cannot be determined (off-topic, too short, ambiguous, sarcasm you cannot resolve, text not written entirely in English, see rule 9).
     Use it instead of guessing. `uncertain` is not `neutral`, and a missing text is **not labelled at all** (it is `unavailable` in the product).
3. **emotional_tone** is set only when an emotion is *stated in words* (e.g. "worried", "hopeful"). Never infer it from topic or outcome.
   *PROPOSED (O6, not in force until accepted and implemented): label every stated emotion from the supported list (`concerned`, `hopeful`); if an emotion is present but cannot be
   reliably assigned to one of them, set `flags.ambiguous_tone: true` and no tone. Today's code and the validation of this rubric use one value or none.*
   Emotion is not risk tolerance: "I'm anxious about my loan" says nothing about how much risk the person will accept.
4. **topics**: tag every topic the text is about, even if only in passing.
5. **preferences**: tag a preference only when the person *states what they want* ("I want to invest safely"). A feeling alone ("I'm scared of losses")
   is `emotional_tone`, not a preference. Hedged wants ("maybe", "might") are still tagged but flagged `hedged`.
6. **Negation** flips or removes the cue ("not worried" is not `concerned`). Record `negation: true` when it decided a label.
7. **Never use a label to express a recommendation** about what the person should do.
8. **Contradictory statements**: if a text states opposing wants (for example safety and higher returns), tag *both* preferences, set `sentiment` by rule 2
   (usually `mixed` or `neutral`), and set `flags.contradictory: true`. Do not pick one.
9. **Unsupported language** (PROPOSED policy O5, Option A, used for the dry run): if the text is not written entirely in English, label `sentiment: uncertain`, no tone, topics or preferences, and
   set `flags.language: "unsupported"`, **whether or not you can read it**. This covers other languages, code-mixed text and transliterated text (for example Hindi in Latin script). No automatic translation;
   this group is reported separately in any evaluation. How much non-English makes a text "not entirely English" (a single borrowed word?) is not defined; when unsure, set `rubric_unclear`.
10. **What the annotator sees**: the text and its `id` only. Not the customer, profile, monthly records, risk assessment, other annotators' labels, or the baseline's output.
    The adjudicator sees the two labels per text without annotator identities, still without baseline output (blind adjudication; proposed).
11. **Hypothetical, conditional, wish and counterfactual statements are not the person's current view.** A clause that only says what the person *would*, *might* or *could* feel or want if something
    happened ("if", "suppose", "what if", "in case", "unless", "imagine", "assuming"), that wishes for something that is not so ("I wish I could ..."), or that describes a counterfactual ("had I saved more,
    I would ...") is **not** labelled as the person's current `sentiment`, `emotional_tone` or `preferences`: it counts as no positive or negative attitude, sets no tone and adds no preference.
    Its topics are still tagged (rule 4).
12. **Labelling a text that contains such a clause.** Ask of each clause: does it say what the person feels or wants **now**, or what they **would** feel or want if a condition held?
    - Every attitude in the text is hypothetical: `sentiment` is `uncertain` (the attitude cannot be determined, rule 2), no `emotional_tone`, no `preferences`; tag the topics.
    - The text also states a current view: label that current view only and ignore the hypothetical clause.
    - A condition that only qualifies a statement that is true now does **not** make the statement hypothetical. Keep the current clause and label it; do not discard it because a conditional
      clause is attached.
    - Hypothetical wording that is quoted, or attributed to another person, is not the person's own view in any case. Negating a hypothetical clause does not make it current: rule 6 applies to
      current statements only.
    - A hedged want ("maybe", "I might want to invest more", rule 5) is a current want stated with doubt and stays tagged `hedged`. A want that exists only under a condition is not tagged.
    - A polite form ("I would like ...", "I would prefer ...") states a current want unless a condition is attached to it: before it ("If I had more money, I would like ..."), inside the same clause
      ("... if my income increased"), or after it in the same sentence ("..., if my income increased", "..., but only if ..."). A polite form with such a condition, or a counterfactual one, is not tagged;
      a polite form followed by a separate sentence about a different condition is still current. A polite form that is quoted, said of another person or negated is not the person's current preference.

    | Text | `sentiment` | `emotional_tone` | `preferences` | Why |
    | --- | --- | --- | --- | --- |
    | "If the market crashes, I would be worried." | uncertain | none | none | the worry is hypothetical, not a current view |
    | "If I had more money, I would want higher returns." | uncertain | none | none | the want is conditional and counterfactual, not a current preference |
    | "I feel safe even if prices fall." | positive | none, with `ambiguous_tone` | none | "feel safe" is stated as true now; the condition only qualifies it, so the current clause is kept |
    | "I am worried about my savings, and if the market crashes I would be even more worried." | negative | concerned | none | label the current clause only |
    | "My advisor said: if the market crashes you will be worried." | uncertain | none | none | quoted, hypothetical and not the person's own view |
    | "If the market crashes I would not be worried." | uncertain | none | none | negating a hypothetical does not make it a current calm attitude |

    These examples illustrate the rules; they are not records of any dataset.
13. **Other voices and other times are not the person's current view either.** Quoted text, a statement about what another person thinks, feels or wants, and a feeling or want that the person
    describes as belonging to the past ("I used to ...", "back then ...") give no current `sentiment`, `emotional_tone` or `preferences`. The topics they mention are still tagged (rule 4).
    If the text also states a current view in the person's own words, label that current view only; words that add to it ("and I agree", "and I still am") count only for what they themselves say.
    If nothing current remains there is no current view to label: `sentiment` is `uncertain`, with no tone and no preference (as in rule 12). If you cannot tell whether wording is the person's own
    current view, label only what is clearly current and set `rubric_unclear`; do not guess.

Every annotator also records `difficulty` (easy | moderate | hard) and may add a free-text `note`. Annotators do not see model output.

### Flags

`flags` also allow `contradictory` (bool), `language` (`en` | `unsupported`) and `ambiguous_tone` (bool). **`ambiguous_tone` means one thing: an emotion is expressed but one reliable assignment
from the supported list is not possible.** Under the one-value `emotional_tone` that includes a text stating two emotions.
