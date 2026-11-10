# User-Text Sentiment — Annotation Rubric and Validation Dataset Specification

Status: **PROPOSED (draft v0)**. Nothing here is approved, no real user text has been collected, and no accuracy has been measured.
The baseline `user_text_rules_v0` (ADR-043) stays **UNVALIDATED_BASELINE** until the independent human-labelled evaluation in section 6 is
run under an approved protocol.

Revision note (2026-10-28, owner-approved, recorded in `reports/sentiment_model_approval_record.md`): rules 11 and 12 (hypothetical, conditional, wish and counterfactual statements) were added to section 3 and a note to section 7. No existing rule, label set or example changed. Rule 13 (quotations, other people's statements, past feelings) was added on 2026-10-29 under the owner's later instruction, with no example; later the same day the owner decided the open annotation-policy items (AP1 to AP9, recorded in the validation decision sheet) and rule 13 was made consistent with them (topics tagged; a text with nothing current in it is `uncertain`). The rubric is still a draft: it is not frozen, not validated, and no annotator has received it.

Rubric version: **v0-draft, not frozen**. A frozen version is identified by the SHA-256 of this file recorded in the freeze manifest (section 5a); annotators are given only the parts of this file
enclosed by `annotator-excerpt` comments (sections 1-3 and the flag definitions of section 4), never the owner-decision, protocol, provenance or baseline-evaluation sections.

<!-- annotator-excerpt:start -->

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

<!-- annotator-excerpt:end -->

## 4. Record format (JSON Lines, one object per text)

`id`, `text`, `source` (`synthetic_rubric` | `real_user_text`), `split` (`rubric_walkthrough` | `calibration` | `validation`),
`labels` {`sentiment`, `emotional_tone`, `topics`, `preferences`}, `flags` {`hedged`, `negation`, `difficulty`}, `annotator_id`.
Real records carry no name, account number, amount that identifies a person, or any other identifier (remove before annotation).

<!-- annotator-excerpt:start -->

### Flags

`flags` also allow `contradictory` (bool), `language` (`en` | `unsupported`) and `ambiguous_tone` (bool). **`ambiguous_tone` means one thing: an emotion is expressed but one reliable assignment
from the supported list is not possible.** Under the one-value `emotional_tone` that includes a text stating two emotions.

<!-- annotator-excerpt:end -->

Author note (not for annotators): if O6 is accepted, two stated emotions are simply both listed in `emotional_tone_proposed` and the flag is kept for emotions that cannot be assigned at all, so the one pilot example
flagged for two emotions would then change; a documented consequence of O6, not a defect.

Real records additionally carry `provenance` (`source_batch`, `collected_on`, `de_identified_by`, `de_identification_check`) and are never edited after the freeze in section 5a. `source_batch` names a
de-identified collection batch, never a person or a consent record: a field linking a text to a person would contradict the recommended O2 default (no person-to-text link).

## 5. Separation of data

| Set | Source | Allowed use |
| --- | --- | --- |
| Rubric examples (`datasets/rubric_examples/user_text_rubric_examples_v0.jsonl`) | **Synthetic, written by the rubric author.** Labels are *illustrative*, not independent. | Train annotators, test the rubric wording. **Never** accuracy evaluation, never tuning the rules. |
| Calibration set | Future, annotators only | Resolve disagreements, refine the rubric |
| Validation set | Future, **real or realistic user text, independently labelled** | The only basis for any accuracy statement |

Rubric examples must never be moved into the validation set, and no text used to tune cue lists may appear in it.

### 5a. Freeze before evaluation (proposed)

Before the baseline is run on a validation set, write a freeze manifest (the same idea as the existing `sentiment_validation_v1` manifest) recording: SHA-256 of the rubric and of the texts file and every
annotator and adjudicated labels file, record count, per-class counts, the O5/O6 decisions in force, the baseline's `METHOD_VERSION`, the annotator and adjudicator codes, the adjudication log hash, and the date. The baseline is
run only on a frozen set; any later edit to the texts, labels or rubric creates a new version and invalidates the earlier result. No tool builds this manifest yet (NOT STARTED).

## 6. Proposed validation protocol (needs owner approval before any step)

1. **Approvals first**: text source and consent (who writes it, under what notice), storage location and retention, who may read it. Until approved, collect nothing.
2. **Annotators**: at least two independent people per text, unaware of baseline output; a third adjudicates disagreements. Record `annotator_id`; no annotator may be the rubric author.
3. **Size and balance**: to be set by the owner. Report per-class counts; do not claim a result on a class with too few examples. No number is proposed here because none is derived.
4. **Agreement before accuracy**: report inter-annotator agreement (for example Cohen's kappa per field) first. If agreement is poor, fix the rubric, not the baseline.
5. **Evaluation (only after 1-4)**: run the baseline once, report per-field precision/recall and the confusion matrix, with `uncertain` and `mixed` reported separately (not forced into three classes).
   Acceptance criteria are chosen by the owner *before* the run.
6. **Compare** to a trained model only if a model is approved (licensing, no external transmission of text).
7. Until then the product keeps `confidence: null` and the label **UNVALIDATED_BASELINE**.

## 7. Known rubric risks

- **`emotional_tone` allows one value.** A text can state two emotions ("hopeful but nervous"); the rubric forces a choice that is arbitrary. See PROPOSED decision O6 (section 8); the code is unchanged until it is accepted.

- English only; code-mixed or transliterated text (common for Indian users) is `uncertain` until a language policy is approved.
- Sarcasm and negated idioms are hard; use `uncertain` and `difficulty: hard`.
- Very short texts rarely contain an attitude; do not over-label.
- **Hypothetical and conditional statements (rules 11 and 12, added 2026-10-28; decisions confirmed 2026-10-29).** Rule 12 keeps a current clause that a condition only qualifies, and gives a text with nothing but
  hypothetical wording, or a negated hypothetical, the label `uncertain` (weak). A hedged want is current and tagged `hedged`; a want that exists only under a condition is not current.
- **Quotations, other people's statements and past feelings (rule 13, added 2026-10-29; decided the same day).** They give no current view, and a text with nothing current in it is `uncertain`, as for rule 12. Topics are
  still tagged. The decisions are recorded in `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md` (items AP1 to AP3 and AP9) and in `reports/sentiment_model_approval_record.md`.
- **Documented differences from the rules baseline (the baseline is NOT changed to match the rubric).** The baseline (`user_text_rules_v1`) differs from this rubric in these cases, each pinned by a test:
  (a) it drops a whole clause that carries a conditional marker, so it does not read "I feel safe about my savings even if the market falls" as a current feeling, whereas rule 12 keeps it (decision: keep the documented
  difference; direct comparison with this rubric is not claimed for this case, which is reported as a separate group); (b) the same happens when a current clause and a conditional clause are joined by "and" with no comma:
  the baseline treats the sentence as one conditional clause and loses the current part, whereas rule 12 labels it (with a comma the baseline separates them; decision: retain the baseline behaviour);
  (c) a text that is only a past feeling is read by the baseline as neutral and weak, whereas rule 13 labels it `uncertain`; a text that is only a quotation or only about another person is declined by the baseline,
  which is also "no label" and so agrees in effect; (d) the baseline reports no topic from a quotation or from another person's clause, whereas rule 4 with rule 13 tags it; (e) the baseline has no `hedged` flag.
  Differences (c) to (e) were not covered by an explicit comparability decision and are flagged for the owner to confirm.

## 8. Open owner decisions (O5 and O6 proposed)

O1 and O4 are accepted in limited form (owner, 2026-10-20): O1 for fictional notes only (real participant text collection remains prohibited); O4 for the fictional dry run with two independent annotators and one adjudicator,
all independent of the rubric author. O5 and O6 are PROPOSED: recorded, not accepted, not implemented in the production taxonomy or `user_text_rules_v0`. O2, O3 and O7 are open. Details and the next decisions:
see `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md`.

| Id | Decision needed | Until decided |
| --- | --- | --- |
| O1 | Source of validation text, consent wording and notice | Fictional notes only; no real text is collected |
| O2 | De-identification method and who verifies it | Collect nothing |
| O3 | Who may access raw text; where it is stored; retention period; deletion on request | Collect nothing |
| O4 | Annotators (number, who, training) and adjudication process | Dry run only; the independent human reviewers are not yet identified, so no labels exist |
| O5 | Language policy. **PROPOSED:** for the initial validation, code-mixed or unsupported-language text is labelled `uncertain` and flagged `language`; no automatic translation; this group is reported separately | Annotators label such text `uncertain`. The baseline does **not**: it labels from any English cue word it contains (confirmed limitation; no change made) |
| O6 | Tone cardinality. **PROPOSED:** allow multiple `emotional_tone` labels; keep `concerned` and `hopeful` as the initial supported list; use `ambiguous_tone` when an emotion cannot be reliably assigned; never infer risk tolerance from emotion | Code and taxonomy unchanged: one value; the two-emotion example is flagged `ambiguous_tone` |
| O7 | Sample size, class balance, agreement threshold and acceptance criteria | No accuracy claim |
