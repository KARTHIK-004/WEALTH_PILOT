# Pre-annotation ambiguities (author's own review, BEFORE any annotation)

Author-only. These are suspected gaps found by re-reading the rubric against the fictional pilot texts. They are hypotheses for the dry run to confirm or reject, **not results**: no annotator has labelled
anything, and nothing was run on the baseline. Each is listed with the pilot texts that probe it (by challenge tag, not by label). Do not give this file to annotators or adjudicators.

| Id | Possible ambiguity | Rule | Probe |
| --- | --- | --- | --- |
| A1 | An emotion outside `concerned`/`hopeful` ("relieved", "angry"): is `ambiguous_tone` true, or the tone empty? The flag definition implies the former; rule 3 does not say. | 3, flag note | tag `emotion_not_in_list` |
| A2 | Resolvable sarcasm: label the intended meaning, or `uncertain`? Rule 2 only covers sarcasm that cannot be resolved. | 2 | tag `sarcasm` |
| A3 | A request ("tell me what to buy") states no attitude and no preference: `neutral` or `uncertain`? | 2 | tag `request_for_advice` |
| A4 | Reported speech ("my friend says ..."): whose attitude or preference is labelled? | 2, 5 | tag `reported_speech` |
| A5 | Negation "flips or removes" the cue: when does "not worried" become `positive` vs `neutral`/no tone? | 6 | tag `negation`, `emotion_negated` |
| A6 | Implicit emotion ("lost sleep over my statement"): sentiment `negative` with no tone, or something else? Tone requires an emotion stated in words. | 2, 3 | tag `implicit_emotion` |
| A7 | The topic list has no entry for spending, income, rent or prices; "tag every topic" cannot be followed for such texts. This touches the taxonomy (an owner matter), so only observe it. | 4 | tags `neutral`, `negative` on spending/price texts |
| A8 | Contradictory wants with no attitude: rule 8 says sentiment is "usually mixed or neutral", which does not decide. | 8 | tag `contradictory` |
| A9 | Does `hedged` apply to emotions and sentiment, or only to preferences (rule 5)? | 5 | tag `hedged` |
| A10 | How much non-English makes a text "not entirely English" (one borrowed word)? Rule 9 now says "not written entirely in English" but sets no boundary, and none may be invented here. | 9 | tags `code_mixed`, `unsupported_language` |
| A11 | Number-only or one-word texts: `uncertain` as "too short/off-topic", or `neutral`? | 2 | tags `numbers_only`, `very_short` |

Fixed before annotation (objective wording defect): rule 9 previously depended on whether the annotator could read the text as English, which let a Hindi-fluent annotator skip the `uncertain` rule; it now follows O5 Option A regardless of reading ability.

## Review of the proposals (PROPOSALS ONLY: not applied to the rubric, not in the package, not accepted, no human agreement exists)

Written while the dry run is blocked. Nothing here changes the production taxonomy, API, model or schema, accepts O5 or O6, or has been tested by any annotator. Adopting any proposal edits the rubric, creates a new rubric version (new file hash) and requires
rebuilding the package and manifest.

Classes: **C** = a clarification that can be tested in the dry run without changing the taxonomy; **P** = a policy decision that needs the owner's acceptance; **T** = a taxonomy change that needs explicit approval; **H** = cannot be resolved until independent human annotation
shows whether people apply it consistently. An item can carry one primary class and one or more secondary ones.

| Id | Primary | Also | What it needs |
| --- | --- | --- | --- |
| A1 | C | T (if the tone list is extended) | Test the annotation use of the existing `ambiguous_tone` flag; any extension of the tone list is an O6 / taxonomy decision |
| A2 | C | H | Dry run shows whether annotators recognise sarcasm consistently |
| A3 | C | | Testable as written |
| A4 | C | H | Dry run shows whether annotators can separate speakers in short text |
| A5 | P | H | Owner policy on whether negation removes or reverses; the dry run shows how annotators treat reassurance |
| A6 | P | H | Owner policy on implicitly expressed distress; the dry run shows whether annotators agree on what counts as an adverse effect |
| A7 | T | C (interim `topic_gap` note) | Owner / taxonomy decision whether to add topics; the interim note is testable |
| A8 | C | | Testable as written |
| A9 | C | H | Dry run shows whether one flag per text is enough |
| A10 | P | H | Owner supplies the boundary and any loanword/domain-term ruling; the dry run measures how much annotators differ |
| A11 | C | | Testable as written |

| Id | Current rule (as written) | Proposed wording | Likely disagreement it addresses | Downstream implications |
| --- | --- | --- | --- | --- |
| A1 | Rule 3: tone only when an emotion is stated in words; supported list `concerned`, `hopeful`. Record format: `ambiguous_tone` = an emotion is expressed but one reliable assignment from the list is not possible. | An emotion outside the list ("relieved", "angry"): leave `emotional_tone` empty, set `ambiguous_tone`, write the word in `note`. | Whether "angry" counts as `concerned`, "relieved" as `hopeful`, or as nothing. | The baseline emits only `concerned`/`hopeful`, so outside-list emotions have no baseline counterpart and must be a separate stratum in any tone comparison. Extending the list would change code, the API literal, generated types, the card and tests (O6). |
| A2 | Rule 2: `uncertain` covers "sarcasm you cannot resolve"; resolvable sarcasm is not mentioned. | Any text whose literal and intended attitude differ: `uncertain`, difficulty `hard`, note `sarcasm`; no "obvious sarcasm" judgement. | Whether a given sarcastic text is "resolvable". | Coverage loss: sarcastic text cannot be scored. The cue-word baseline would read "wonderful" as positive, so such texts show up as false confidence in a later comparison. |
| A3 | Rule 2: `neutral` = about finances, no attitude; requests are not mentioned. | An on-topic request with no attitude and no preference is `neutral`; topics only if the text names one. | `neutral` vs `uncertain` for "tell me what to buy". | Changes class counts only; no code effect. |
| A4 | Rules 2 and 5 do not say whose attitude or want is labelled. | Label only the writer's own stance; an attitude or want attributed to someone else is not labelled. | A friend's advice counted as the writer's preference. | The baseline has no speaker logic and reads cues anywhere in the text, so divergence on reported speech is an expected limitation, not an error. |
| A5 | Rule 6: "Negation flips or removes the cue". | "Removes": a negated cue contributes nothing and never becomes its opposite ("not worried" gives no tone and no `negative`; it is not `positive`). | "I do not feel anxious at all" as `neutral` vs `positive`; when "flips" applies. | Defines what `positive` means for reassurance. The current baseline drops negated cues, so gold and baseline would agree on negation partly by construction; that must be disclosed and not counted as validation. "Flips" would need an antonym lexicon, a new methodology artifact. |
| A6 | Rule 2: attitude expressed toward finances; rule 3: emotion stated in words. Implicit effects are not mentioned. | A described personal effect without evaluation ("lost sleep over my statement") is `neutral`, no tone, note `implicit`. | `negative` vs `neutral` for "lost sleep over my credit card statement". | **Risk of under-labelling implicit distress**: gold would call such texts `neutral`, and the cue-based baseline also misses them, so agreement can look good while both miss the distress. Report an "implicit adverse effect" stratum separately and never read the absence of a negative label as the absence of distress (the card already presents the reading as a suggestion, not a fact). The more natural alternative (allow `negative` for a stated adverse effect) is less reproducible. Needs an owner policy and human evidence. |
| A7 | Rule 4: "tag every topic ... even in passing"; the list is `investment_risk`, `saving`, `debt`, `goals`, `liquidity`. | Interim: texts about spending, income, rent or prices get no topic and a `topic_gap` note; the list is not extended here. | Whether "the rent went up" is `debt`, `saving` or nothing. | **Missing finance-related categories** (spending/expenses, income, prices/inflation, rent, budgeting): "tag every topic" cannot be followed. Adding topics is a taxonomy change touching the code constant, the API literal, generated types, the card, the cue map and tests, plus a new method version and topic-agreement metrics. Without it, topic recall on such texts is undefined. |
| A8 | Rule 8: contradictory wants are both tagged; sentiment "usually `mixed` or `neutral`". | Contradictory wants with no attitude words: `neutral`; `mixed` only when both a positive and a negative attitude are stated; `contradictory` true either way. | `mixed` vs `neutral` for "safe and also double it". | Counts only; the baseline's `mixed` means both polarity cues present, which is a different thing and must be reported as such. |
| A9 | Rule 5: hedged wants are "flagged `hedged`"; the sheet has one `hedged` column per text. | One `hedged` flag per text, set when any label rests on a hedged statement; the note says which. | Whether a hedged emotion or sentiment counts. | Analysis stratum only; no production field. |
| A10 | Rule 9: not written entirely in English → `uncertain`, `language: unsupported`, whether or not the annotator can read it. The boundary ("a single borrowed word?") is undefined. | No boundary is invented. In the dry run annotators set `language` by their own judgement and `rubric_unclear`; the owner then chooses a strict rule (any non-English word) or a proportion rule (a threshold the owner must supply), and rules on loanwords and domain terms. | Whether "My EMI is too high" is English; a Hindi-fluent vs a non-Hindi annotator reading the same mixed text. | **Loanwords:** standard Indian-English finance vocabulary (EMI, SIP, FD) would make the strict rule exclude genuinely English text; any term list is a methodology artifact needing an owner and a version. A proportion rule needs a threshold. The baseline has no language detection (confirmed), so whatever is chosen, its output on the group is reported separately; the same boundary would have to be machine-checkable for O5 Option B. |
| A11 | Rule 2: `uncertain` includes "too short"; `neutral` = about finances, no attitude. | Number-only or single-word texts are `uncertain`; `neutral` is for finance-related text that states no attitude. | `neutral` vs `uncertain` for "ok" and "12000 / 8000 / 4000". | Class counts only; no code effect. |

None of A1-A11 changes a label value or the production taxonomy as proposed; A1 (tone list) and A7 (topic list) would only if the owner later extends the lists, and are noted, not requested. No proposal is accepted and none has human agreement.
O2, O3, O7 and the withdrawal-versus-unlinkability conflict (C3) remain unresolved; O5 and O6 remain PROPOSED. No real text is collected, the package is not distributed and the baseline is not run.
