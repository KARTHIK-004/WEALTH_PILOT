# User-Text Validation — Owner Decision Packet (O1–O7)

**The only accepted decisions are the owner's limited approvals of 2026-10-20 recorded in the O1 and O4 rows below (fictional notes only; a fictional dry run).** Everything else, including every "Recommended default", is a recommendation or a proposal. O5 and O6 were *proposed* by the project owner (ADR-044) and are still PROPOSED, not accepted. The "Owner decision" rows of O2, O3, O5, O6 and O7 are blank and stay blank until the owner fills them in. No consent, retention, agreement, sample-size or acceptance threshold is invented here; where a number would be needed, the packet says who must supply it.
Nothing real has been collected, no annotation has started, the baseline `user_text_rules_v0` is unchanged and stays `UNVALIDATED_BASELINE`, and the production taxonomy (one `emotional_tone` value) is unchanged.

**Order of dependence:** O1 → O3 → O2 → O4 → (fictional dry run, rubric revision) → O7. O5 and O6 are independent proposals that must be accepted before any production change, and O6 needs O7's agreement statistic.
O1–O3 gate everything involving real text; O4 gates every human label; O7 gates every number. The fictional dry run needs only the limited O1 and O4 approvals already given.

## O1 — Text source and consent

| | |
| --- | --- |
| Status | RECOMMENDATION (open) |
| Question | Whose text may be used, and on what terms? |
| Recommended default | Fictional notes only until a stated purpose, a plain-language notice, consent before submission, a withdrawal route and an eligibility rule are written down. No sensitive real financial text in this phase. |
| Rationale | Real financial text is sensitive; fictional notes already allow the rubric to be exercised without personal data. |
| Consequences | If accepted: the dry run can start with no personal data; real-text validation waits. If open: same, indefinitely, and the baseline stays unvalidated. |
| Prerequisites | Owner writes the purpose, notice, consent wording and eligibility rule. See "Contradictions" C3 (withdrawal vs no identity link). |
| Owner decision | ACCEPTED, limited (owner, 2026-10-20): fictional notes only. Real participant text collection remains prohibited. |

## O2 — De-identification

| | |
| --- | --- |
| Status | RECOMMENDATION (open) |
| Question | Which identifiers must go, and who removes and verifies them? |
| Recommended default | Contributor self-redacts, then a named checker verifies each record and signs `de_identification_check`; a failed record is dropped, not silently edited; keep no link between a person and their text. Identifiers: direct (name, phone, email, account or card number, address, employer, date of birth) and indirect (unusual amounts, rare job or place, combinations). |
| Rationale | Removing the link removes the main re-identification path; a second person catches misses by the contributor. |
| Consequences | If accepted: real text can be admitted once O1 and O3 are also approved. If open: no real text enters the pipeline. Tool-assisted redaction is a separate approval (and must not send text outside the machine). |
| Prerequisites | O1 (who contributes) and O3 (where it is stored); a named checker. See C2 and C3. |
| Owner decision | |

## O3 — Access, storage, retention, deletion

| | |
| --- | --- |
| Status | RECOMMENDATION (open) |
| Question | Who may read raw text, where it lives, how long it is kept, and how it is deleted? |
| Recommended default | Named access only (annotators and owner, never the rubric author as an annotator); an encrypted folder outside Git and the repository; never sent to an LLM, external model provider or hosted service without a separate explicit approval; deleted after the evaluation report is accepted, keeping only hashes and counts in the frozen manifest; backups follow the same deletion rule; an access log without text. |
| Rationale | Limits exposure to the smallest group and the shortest period the evaluation needs. |
| Consequences | If accepted: storage and deletion are auditable before any collection. If open: no collection. |
| Prerequisites | The owner supplies the actual retention period or trigger, backup policy and the named people; none is invented here. |
| Owner decision | |

## O4 — Annotators, pilot procedure and adjudication

| | |
| --- | --- |
| Status | RECOMMENDATION (open) |
| Question | Who labels, how are they trained, and how are disagreements settled? |
| Recommended default | Independent annotators working alone and blind (text and id only; no customer, profile, risk assessment or baseline output); a different person adjudicates, blind to annotator identity and to baseline output; none of them the rubric author. Train on the synthetic rubric examples, then calibrate on a separate small set. The 30-text fictional pack supports a rubric-clarity dry run only. |
| Rationale | Independence and blinding are what make later agreement and accuracy figures meaningful; the author adjudicating their own rules would bias them. |
| Consequences | If accepted: agreement can be measured honestly. If open: the dry run has no participants, no human labels exist and none can be reported. |
| Prerequisites | The owner chooses how many annotators and adjudicators and who they are (no number is set here); O3 (access terms). |
| Owner decision | ACCEPTED, limited (owner, 2026-10-20): for the fictional dry run only, two independent annotators and one adjudicator, all independent of the rubric author. If suitable reviewers are unavailable, self-annotation must not be substituted or called independent. Reviewers are not yet identified (see Dry-run status). |

## O5 — Language policy (PROPOSED by the owner; not accepted)

| | |
| --- | --- |
| Status | PROPOSED (ADR-044), not accepted, not implemented. Owner, 2026-10-20: Option A is the proposed annotation policy for the dry run (code-mixed or unsupported-language examples annotated `uncertain`); `user_text_rules_v0` and its taxonomy are unchanged. |
| Question | How are code-mixed and unsupported-language texts handled? |
| Owner proposal | For the initial validation, code-mixed or unsupported-language text is labelled `uncertain`, flagged `language`, not translated automatically, and reported separately. |
| Confirmed limitation | The baseline has no language detection. A non-English sentence containing **one recognised English cue word** is labelled from that word alone (invented examples, not pilot texts, not an evaluation: a Hindi-in-Latin sentence ending "... excited hoon" gives `positive`/`hopeful`; a Spanish sentence containing "worried" gives `negative`/`concerned`; the same Hindi sentence without a cue gives `uncertain`). A characterisation test pins this. So the proposal holds for annotators but not for the baseline's own output. |
| Recommended default | A for the validation protocol now: annotators label such text `uncertain`, the baseline is unchanged, and its output on the flagged group is reported separately so the false-confidence rate is visible. B later, as a separately scoped change: fail closed, returning `uncertain` with a reason unless the text is confirmed to be English. |
| Options | A annotation-only (no code change; the UI could still show a label for code-mixed text). B fail closed on unconfirmed English (needs a deterministic confirmation rule; no language-ID package is approved; any word-coverage threshold would be an invented threshold, so the owner must approve a specific rule and its tests first; withholds labels from some genuine English text). C fail closed on detected non-English (misses unlisted languages and mixed text). |
| Consequences | Nothing is implemented. If B is later approved: an English-confirmation rule, a new `METHOD_VERSION`, an API field, tests (including updating the characterisation test), and a report of the withheld share. If open: the limitation stays, documented. |
| Prerequisites | For B: an owner-approved deterministic policy. For any evaluation: O7. |
| Owner decision | |

## O6 — Emotional-tone labels (PROPOSED by the owner; not accepted)

| | |
| --- | --- |
| Status | PROPOSED (ADR-044), not accepted, not implemented. Owner, 2026-10-20: stays proposed; the dry run only identifies rubric ambiguity; no production schema or API change. |
| Question | May `emotional_tone` hold several labels, and which? |
| Owner proposal | Allow multiple `emotional_tone` labels; keep `concerned` and `hopeful` as the initial list; use `ambiguous_tone` when an emotion cannot be reliably assigned; never infer risk tolerance from emotion. |
| Recommended default | Keep the production schema (one value or none) until O6 is accepted; in the dry run, collect the proposed reading separately (`emotional_tone_proposed`) so both can be compared. |
| Rationale | The pilot already contains texts with two stated emotions and emotions outside the list ("relieved", "angry"); the dry run shows whether annotators can apply the proposal. |
| Consequences | If accepted: a schema change (list, `ambiguous_tone`, regenerated types, the card, tests, ADR-043's one-value field superseded), a set-based agreement statistic, and a rule for emotions outside the list (ADR-044 suggests recording them as `other_emotion`, not forcing them into the list). If open: nothing changes. |
| Prerequisites | O7 (agreement statistic). See C1: `ambiguous_tone` had two meanings, now unified in the rubric. |
| Owner decision | |

## O7 — Validation design and acceptance

| | |
| --- | --- |
| Status | RECOMMENDATION (open) |
| Question | What is being tested, on how much data, and what counts as good enough? |
| Recommended default | Decide in this order: the objective and the smallest class of interest; the agreement statistic (for example Cohen's kappa per field, or a set-based measure if O6 is accepted) and its minimum; the acceptance criteria per field; only then derive the sample size from those assumptions. Fix all of it before the baseline runs, then freeze (rubric 5a). |
| Rationale | Criteria chosen after seeing results can be tuned to pass; a sample size without stated assumptions has no justification. |
| Consequences | If accepted: an evaluation can be pre-registered and frozen. If open: no evaluation, so no accuracy, precision, recall or generalisation claim. |
| Prerequisites | O1–O4 for real text; O5/O6 outcomes for the label set; the owner supplies every threshold and the sample-size assumptions (none is given here). `uncertain`, `mixed` and the unsupported-language group are reported separately. |
| Owner decision | |

## Dry-run status (fictional notes only; 2026-10-20)

| Item | State |
| --- | --- |
| Limited approvals (O1 fictional only, O4 for the dry run) | RECORDED above, in the owner's words |
| Rubric | `v0-draft`, **not frozen**; rule 9 aligned with O5 Option A (not entirely English → `uncertain`, whether or not the annotator can read it) |
| Annotator package `pilot_pack_v0/package/` | BUILT and verified by `scripts/build_dry_run_package.py --verify`: texts, blank template, instructions, and only the rubric parts between its `annotator-excerpt` markers (sections 1-3 and the flag definitions); no challenge map, manifest, owner decisions, provenance or protocol. `verify` also flags an excerpt or package copy that is stale against the rubric or its sources |
| Manifest `author_only/DRAFT_MANIFEST.json` | DRAFT, `frozen: false`, `freeze_process_completed: false`, lists the steps still to do |
| Participant register (independence attestation) | NOT SUPPLIED; template in `author_only/`; the builder keeps `distribution_ready: false` until two annotators and one adjudicator are attested independent of the rubric author |
| Annotation by two independent annotators | **NOT STARTED, BLOCKED**: no suitable human reviewers have been identified. The rubric author (an AI assistant) did not annotate and AI-generated labels are not accepted as independent labels |
| Blind adjudication | NOT STARTED; the adjudicator package (`pilot_pack_v0/adjudicator/`) and `pilot_disagreements.py --blind` are ready |
| Baseline on the pilot texts / any accuracy | NOT RUN, not claimed |
| Pre-annotation ambiguities A1-A11 | `author_only/pre_annotation_ambiguities.md`: hypotheses with PROPOSED clarifications, each classified C (testable, no taxonomy change), P (owner policy), T (taxonomy) or H (needs human annotation); none applied, none has human agreement |
| Freeze | NOT DONE; required steps listed in the manifest |

## Contradictions and gaps found in the materials

| Id | Finding | Handling |
| --- | --- | --- |
| C1 | `ambiguous_tone` was defined two ways (an emotion that cannot be reliably assigned, vs "two emotions stated"). | Fixed in the rubric: one meaning, with the O6 consequence stated. The dry-run sheet uses it under today's one-value reading. |
| C2 | The rubric's provenance field `consented_source_id` implied a text-to-person/consent link, against the recommended O2 default of no link. | Fixed in the rubric: `source_batch`, a de-identified batch, never a person. Still subject to the owner's O2 choice. |
| C3 | O1 needs a withdrawal route, but O2's default keeps no person-to-text link, so a text cannot be found to withdraw it. | **Open, owner decision. Recorded (owner, 2026-10-20) as a blocker for any future real-text collection.** Options: keep a link until the freeze (weakens O2); or give each contributor a random token held only by them, so they can ask to withdraw by token without any stored identity. |
| C4 | Annotators were pointed at the whole rubric, which also holds owner decisions, the protocol and baseline wording; there was no rubric version; the freeze manifest listed too little. | Fixed: annotators get only the rubric parts between its `annotator-excerpt` markers (sections 1-3 and the flag definitions; an audit on 2026-10-20 found the first excerpt had still leaked the provenance, consent and O2 wording and a remark about the pilot, now removed and checked); version `v0-draft` (frozen = file SHA-256); manifest fields extended. A tool that builds the manifest is NOT STARTED. |
| C5 | Annotators were not told they get no identity, profile, risk or baseline information. | Fixed in the dry-run instructions. |
| C6 | The baseline's single-tone, English-only design conflicts with the O5/O6 proposals (see O5, O6). | Documented only; no production change until the owner accepts. |
| C7 | The rubric's owner-decision table still said O1-O4 were open and that unsupported-language text "is `uncertain` (already the behaviour)" for the baseline, which the confirmed O5 limitation contradicts. | Fixed in the rubric: O1/O4 shown as limited approvals; the baseline is stated NOT to behave that way. |
| C8 | Rubric rule 2 defined `uncertain` for "language you cannot read", contradicting rule 9 (not entirely English → `uncertain` whether or not you can read it). | Fixed: rule 2 now points to rule 9. The package and DRAFT manifest were rebuilt (still unfrozen). |

## Addendum 2026-10-27 — Held-out personal-finance set and Transformer evaluation (PROPOSALS ONLY)

Added for the sentiment-model research phase (ADR-052). **Nothing here is accepted.** The accepted decisions remain the limited O1 and O4 approvals recorded above (fictional notes only; a fictional dry run). No statement has been written, no real text collected, no annotator named, no label made, no package installed, no weight or dataset downloaded, and the rules baseline `user_text_rules_v1` (`UNVALIDATED_BASELINE`, model switched off) stays the only active method. **This packet still sets no number:** the owner's proposed targets and quotas for a new held-out set are written in `reports/sentiment_transformer_dependency_request.md` (sections E and G), where each is labelled a proposal; the approval checklist with one state per decision is its section F, and every item there is UNRESOLVED except the owner's instruction to keep intensity regression deferred.

The rubric `docs/USER_TEXT_ANNOTATION_RUBRIC.md` is deliberately **not edited**: its SHA-256 is recorded in the pilot pack's DRAFT manifest, and the dry-run rubric is `v0-draft`. A new held-out set would need its own frozen rubric version, written after the dry run (step 2 below). *(Superseded in part on 2026-10-28 by the owner's approval recorded in `reports/sentiment_model_approval_record.md`: rules 11 and 12 on hypothetical and conditional statements were added to the draft, which no annotator had received, and the manifest hashes were rebuilt with `scripts/build_dry_run_package.py`: rubric `c77179950111c4ffaedf1564e5ee6466f6f38c753d012e1930672c1b77808fd3`, excerpt `a7bc2d328c55e9bddece4023ebd609c2713b6a1e3df679ba0ddd83f6bac9cd9b`. The rubric is still `v0-draft`, not frozen.)*

### What the proposal covers (details and numbers in the report)

- **A new, independent held-out set of personal-finance statements**, never seen by the baseline or any model, spanning investment concerns, savings, debt, liquidity, emergency funds, retirement, financial goals and market concerns, in positive, negative, neutral, mixed and uncertain wording, including negation, contradictory preferences, low-information text and unsupported or code-mixed text. The proposed size is a **minimum, not proof of validity**: every class and subgroup is small, so intervals are reported and no validation is claimed where a class has inadequate support.
- **Authoring**: only if the owner approves fictional-data generation (D8), by people who are neither the rubric author nor the author of the baseline's cue lists and who do not see those lists; no copying from any benchmark; no identifying detail. Consented participant text instead would first need O1, O2, O3 and C3 decided.
- **Annotation**: two independent annotators label alone; a third person adjudicates disagreements; all are independent of the rubric author and of the model or rules work. Everyone sees only a statement id and its text: no profile, risk, customer or monthly-record data, and no rules or model output. The adjudicator also does not see which annotator gave which label.
- **Real text stays out of scope** until consent, retention and de-identification are approved (O1, O2, O3 and the withdrawal-versus-unlinkability conflict C3). Any future real text needs de-identification verified by a named checker, named access only, encrypted storage outside the repository, never an LLM or external service, and a stated retention and deletion route that the owner supplies.
- **Freeze before any model runs**: the rubric version, the text manifest and the adjudicated labels are frozen and hashed with SHA-256 in a manifest that records the date; a change creates a new version. Exact and near-duplicates are removed within the set and against every training, calibration and development text. Training data, calibration data and the held-out set are three disjoint sets, and the held-out set is never used to tune anything.
- **Reporting**: exact class counts, annotator agreement, class-specific uncertainty and every limitation accompany any result. Nothing is called validation unless the owner has recorded that its criteria are met.
- **Evaluation**: the rules baseline, FinBERT and one approved general RoBERTa-family candidate, scored once each on the frozen set with the metrics listed in the report; a model that reaches high precision only by abstaining on nearly all inputs is not activated; intensity regression stays deferred and disabled.

## Next decisions: the smallest useful sequence

Only these need the owner next. Everything below step 2 can wait for dry-run evidence, and nothing in steps 3-5 is needed to start the dry run. All options are proposals; no number is proposed.

| Step | Decision | Recommendation (not a decision) | Unblocks |
| --- | --- | --- | --- |
| 1 | Name two annotators and one adjudicator independent of the rubric author (anonymous codes, independence attested in the participant register) | Do this first; it is the only blocker to starting | Distribution of the verified package and the dry run |
| 2 | Run the dry run on rubric `v0-draft` exactly as it stands, or first apply the testable clarifications (class C in the ambiguity review: A1 annotation use, A2, A3, A4, A8, A9, A11) as a new draft version | Run `v0-draft` unchanged first, so real disagreement is observed and not pre-empted; apply the C-class clarifications afterwards | Evidence for steps 3-4 |
| 3 | After the dry run, decide the policy items: A5 (negation removes or reverses), A6 (implicit distress; the under-labelling risk), A10 (language boundary and loanword/domain-term ruling), plus O5 (accept or reject Option A / consider B) | Decide each with the disagreement evidence in hand; do not decide A10's boundary before seeing how annotators differ | A frozen next rubric version |
| 4 | After the dry run, decide taxonomy items together with O6: whether to extend the topic list (A7) and the tone list (A1), and whether tone may hold several labels | One taxonomy review, not item by item | Any production change (separately scoped) |
| 5 | Only before any real text: O2, O3, O7 and the withdrawal-versus-unlinkability conflict (C3) | Not now | Real-text collection and any baseline evaluation |

Still open and unchanged: O2, O3, O7, C3. Still PROPOSED: O5, O6. The baseline stays `UNVALIDATED_BASELINE`; no real text has been collected, the package has not been distributed, and the baseline has not been run on the pilot.

## Addendum 2026-10-29 — Annotation-policy gaps (UNRESOLVED; no statement is created or labelled)

Added on the owner's instruction. Nine annotation-policy questions were open; the owner decided all of them on 2026-10-29 (the decision is in each item's Owner entry and in the approval record). For each: what the draft rubric says today, what the rules baseline `user_text_rules_v1` does today (every behaviour below is pinned by a test, in `tests/backend/core/test_user_text_rubric_hypothetical.py` and `test_user_text_hypothetical.py`), the options, and a recommendation that is **not a decision**. The `Owner entry` row of each item records the decision. **No statement was created or labelled for this addendum.** The fictional sentences in rule 12 of the rubric remain illustrations of the wording, not dataset records and not validation data. No consent, retention, agreement, sample-size or acceptance threshold is invented here; none is given here, and no number is set here.

Status of the draft: the rubric is still `v0-draft`, not frozen and not validated, and no annotator has received it. Rules 11, 12 and 13 were added to it under the owner's instructions of 2026-10-28 and 2026-10-29; this supersedes in part the recommendation of step 2 below to run the draft "unchanged": whichever version is used must be identified by the hash the official builder records in the pilot-pack manifest.

### AP1 — Plain quotations

| | |
| --- | --- |
| Question | What does a text receive when it is, or contains, quoted words? |
| Rubric today | Rule 13: quoted text gives no current sentiment, tone or preference; a current view elsewhere in the text is labelled alone; with nothing current left the text is labelled by rule 2 from what remains and marked `rubric_unclear`. No label is prescribed. |
| Baseline today | The quoted span is blanked. A text that is only a quotation is declined (abstention, ambiguous context). Words after a quotation that adopt it ("and I agree") add no cue. |
| Open | The label for a quotation-only text (`uncertain` or `neutral`); a quotation the person adopts; the person quoting their own earlier words; whether topics inside a quotation are tagged (see AP9). |
| Options | A. nothing-current texts are `uncertain`. B. they are `neutral`. C. keep `rubric_unclear` and report them as a separate group. |
| Recommendation (not a decision) | A for a quotation-only text (it matches the baseline's abstention); C for an adopted quotation until a dry run shows how annotators read it. |
| Owner entry | **DECIDED 2026-10-29: `NO_CURRENT_VIEW`.** Quoted wording gives no current sentiment, tone or preference; a text with nothing current in it is `uncertain` (as for AP5); topics are tagged (AP9). Rule 13 of the draft rubric is consistent. The baseline is not changed. |

### AP2 — Statements about other people

| | |
| --- | --- |
| Question | What does a text receive when it states what another person thinks, feels or wants? |
| Rubric today | Rule 13, as for AP1. |
| Baseline today | A clause about another person is not the user's view; a text that is only about another person is declined (abstention, ambiguous context); a current first-person clause beside it is labelled. A first-person pronoun after the other person's clause returns the speaker to the user. |
| Open | The label for an other-person-only text; a family or household member whose finances the person shares (household figures never enter individual analysis, but the wording may); whether the person's agreement with the other person counts. |
| Options | As AP1. |
| Recommendation (not a decision) | A (consistent with the baseline and with AP1). |
| Owner entry | **DECIDED 2026-10-29: `NO_CURRENT_VIEW`.** Another person's wording gives no current sentiment, tone or preference; a text with nothing current in it is `uncertain`; topics are tagged (AP9). Rule 13 is consistent. The baseline is not changed. |

### AP3 — Past feelings

| | |
| --- | --- |
| Question | What does a feeling or want described as past receive, including one the person says still holds? |
| Rubric today | Rule 13, as for AP1. |
| Baseline today | A past clause gives no cue; a text that is only a past feeling is **not** declined but read as neutral and weak, with its topics reported; a past feeling that "still" holds is not recovered unless the same clause carries its own cue. This is **not uniform** with AP1 and AP2, which is why rule 13 prescribes no label. |
| Open | The label for a past-only text (`uncertain` or `neutral`); a past feeling that persists; the baseline's different treatment of past-only text. |
| Options | A. `uncertain`, which would also change the baseline (a production change needing its own approval). B. `neutral`, matching the baseline. C. `rubric_unclear` and a separate group. |
| Recommendation (not a decision) | C until the dry run shows how annotators read persistence; then decide between A and B once, together with AP1 and AP2. |
| Owner entry | **DECIDED 2026-10-29: `NO_CURRENT_VIEW`.** A feeling or want described as past gives no current sentiment, tone or preference; a text with nothing current in it is `uncertain`; topics are tagged (AP9). Rule 13 is consistent. The baseline is not changed, so it still reads a past-only text as neutral and weak: a documented difference, flagged for the owner to confirm. |

### AP4 — A current clause qualified by "even if" (rubric and baseline disagree)

| | |
| --- | --- |
| Question | Is a statement true now that carries a trailing condition ("even if ...") a current view? |
| Rubric today | Rule 12: yes, the current clause is kept and labelled; its condition only qualifies it. |
| Baseline today | No: a clause carrying a conditional marker is dropped as a whole, so the text is `uncertain` and weak. The same loss occurs for a current clause joined to a conditional clause by "and" with no comma (see AP6). |
| Outcomes | `ALIGN_BASELINE_TO_RUBRIC`: preserve the current clause when "even if" qualifies a present statement. `ALIGN_RUBRIC_TO_BASELINE`: label the whole conditional construction as non-current. `KEEP_DOCUMENTED_DIFFERENCE`: keep both as they are and do not claim comparability for this case. |
| Consequence of each | The first changes production code in `core/user_text_sentiment.py` (clause splitting at "even if" and similar), flips two pinned tests, risks mis-splitting, and needs its own approval. The second rewrites the third bullet and one example row of rule 12, discards a statement an annotator can read plainly, and rebuilds the pilot-pack hashes through the builder. The third changes nothing, but needs a way to identify these items in any held-out set (an annotator note or a pre-agreed list) so they can be reported as a separate group and left out of any direct comparison tally. |
| Recommendation (not a decision) | `KEEP_DOCUMENTED_DIFFERENCE` for the dry run, then decide from how often the case occurs in real annotation. |
| **Status** | **DECIDED** (`KEEP_DOCUMENTED_DIFFERENCE`). Neither the rubric nor the baseline was changed. |
| Owner entry | **DECIDED 2026-10-29: `KEEP_DOCUMENTED_DIFFERENCE`.** Rule 12 and the baseline both stay as they are; direct comparison with this rubric is not claimed for this case, which is reported as a separate group. No production change. |

### AP5 — Hypothetical-only text

| | |
| --- | --- |
| Rubric today | Rule 12: `uncertain`, no tone, no preference; topics tagged. |
| Baseline today | The same: `uncertain` and weak, no cue, tone or preference; topics reported. The two agree. |
| Open | Confirm the agreement; whether wish and counterfactual wording is treated like conditional wording. |
| Options | A. confirm. B. treat wishes differently. |
| Recommendation (not a decision) | A. |
| Owner entry | **DECIDED 2026-10-29: `UNCERTAIN_WEAK`.** A hypothetical-only text is `uncertain` (weak) with no tone and no preference. Rule 12 and the baseline already agree. |

### AP6 — Mixed current and hypothetical text

| | |
| --- | --- |
| Rubric today | Rule 12: label the current view only. |
| Baseline today | With a comma or a sentence break between them, the current clause is labelled and the hypothetical one ignored. Joined by "and" with no comma, the whole sentence is one conditional clause and the current part is lost (`uncertain`). |
| Open | Whether that loss is acceptable; whether the baseline should split before a conditional marker (a production change). |
| Options | Keep the difference and report it (as AP4). Align the baseline (production change). Align the rubric (label no-comma sentences as non-current, which makes the label depend on punctuation). |
| Recommendation (not a decision) | Decide together with AP4; aligning the rubric to punctuation is the weakest option. |
| Owner entry | **DECIDED 2026-10-29: `LABEL_CURRENT_ONLY`.** Only the current clause is labelled. The comma-less "and" question was decided the same day as `RETAIN_DOCUMENTED_BASELINE_BEHAVIOR`: the baseline is not changed and the loss is reported as a documented difference. |

### AP7 — Negated hypothetical text

| | |
| --- | --- |
| Rubric today | Rule 12: still not a current view; negation does not make it a current calm attitude. |
| Baseline today | The same (`uncertain`, weak). Rule 6 (negation flips or removes a cue) applies to current statements only. |
| Open | Confirm; relation to the open question of whether negation removes or reverses a cue. |
| Options | A. confirm. B. decide negation together with the existing negation ambiguity first. |
| Recommendation (not a decision) | A. |
| Owner entry | **DECIDED 2026-10-29: `NO_CURRENT_VIEW`.** A negated hypothetical is not a current view and is not a current calm attitude. Rule 12 and the baseline already agree. |

### AP8 — Hedged versus conditional preferences

| | |
| --- | --- |
| Rubric today | Rule 5: a hedged want is tagged and flagged `hedged`; rule 12: a want that exists only under a condition is not tagged. |
| Baseline today | A hedged want ("might want ...") is tagged as a preference; a conditional want is not. The baseline has **no** hedge flag, so `hedged` cannot be compared. Polite forms ("would like", "would prefer") are stance verbs and are read as current wants; conditional-mood phrases ("would be", "would feel") are hypothetical. |
| Open | The boundary: is a polite "would like" a current want or a conditional one; whether `hedged` is evaluated at all. |
| Options | A. polite forms are current wants. B. polite forms are conditional unless a condition is stated. C. leave to `rubric_unclear`. |
| Recommendation (not a decision) | A. |
| Owner entry | **DECIDED 2026-10-29: `HEDGED_CURRENT_CONDITIONAL_NOT_CURRENT`.** A hedged want is current and tagged `hedged`; a want that exists only under a condition is not current. The polite-form boundary was decided later the same day: `CONTEXT_DEPENDENT`. "I would like ..." and "I would prefer ..." state a current want unless a condition is attached before them, inside the clause or after them in the same sentence ("..., if my income increased", "..., but only if ..."); a conditional or counterfactual polite form is withheld; a polite form that is quoted, said of another person or negated is never the person's preference. This is the one production-baseline change the owner authorised, limited to polite forms: the baseline previously accepted a polite form followed by a trailing condition and now withholds it. |

### AP9 — Topic tagging when the sentiment is not current

| | |
| --- | --- |
| Rubric today | Rule 4: tag every topic the text is about, even in passing. Rules 11 and 12 add that topics of a hypothetical clause are still tagged. Rule 13 deliberately says nothing about topics. |
| Baseline today | Topics are reported from the user's own clauses, including hypothetical and past ones. Topics inside a quotation and inside another person's clause are **not** reported. |
| Open | Whether topics mentioned only in quoted, other-person or past wording are tagged. |
| Options | A. tag them (follow rule 4 literally; the baseline then under-reports). B. tag only the user's own clauses (matches the baseline). |
| Recommendation (not a decision) | B for comparability, stated in the rubric. |
| Owner entry | **DECIDED 2026-10-29: `TAG_TOPIC_ONLY`.** Topics mentioned in non-current wording are tagged; no sentiment, tone or preference is taken from that wording. The baseline is not changed, so it still reports no topic from a quotation or another person's clause: a documented difference, flagged for the owner to confirm. |

### Agreement between the rubric and the baseline today, in one place

| Case | State |
| --- | --- |
| Hypothetical-only, negated hypothetical, hedged versus conditional preference (the stated forms) | agree |
| Quotation-only and other-person-only (both are declined by the baseline) | no label prescribed by the rubric; AP1 and AP2 |
| Past-only | baseline reads neutral; no label prescribed by the rubric; AP3 |
| Current clause with "even if" | **differ** (AP4) |
| Current clause joined to a conditional clause with no comma | **differ** (AP6) |
| Topics in quoted or other-person wording | **differ** if rule 4 is read literally (AP9) |

The three outcomes of AP4 were the only options the owner named for the "even if" difference; the owner chose `KEEP_DOCUMENTED_DIFFERENCE` on 2026-10-29.

*Note (2026-10-29): the hashes quoted in the earlier superseded-by note above were those of 2026-10-28. After rule 13 was added the official builder recorded rubric `5a5be11cbe06f0685c91d17670c814c42b1373202d852a70e8d905ed1fbc48a2` and excerpt `cc465ffdaad2f4452987df62955146c5664bd929817878d6c5018ba999f93f22`; the pilot-pack manifest is always the authority.*

*Update (2026-10-29, later the same day): items AP1 to AP9 and the comma-less "and" rule are decided; none of the decisions changes production behaviour. The differences between the draft rubric and the rules baseline that remain are documented in section 7 of the rubric and pinned by tests. Those under AP3 (past-only text) and AP9 (topics in quotations and other people's clauses) were not covered by an explicit comparability decision and are flagged for the owner to confirm.*

*Note (2026-10-29, after the annotation-policy decisions): the official builder recorded rubric `bcd6b56da929e984faabba825b3377a78a610862d7b0b19e5a6b43e19738b7c0` and excerpt `a7032ef0b3c6bd747d312a74ab433826bb0025468fba4eb1d717877933e38c6e`. The pilot-pack manifest is the authority for the current values.*

*Note (2026-10-29, eighteenth brief): AP8 is now fully decided (`CONTEXT_DEPENDENT`, including the polite-form boundary). The official builder recorded rubric `346c5dce27bd37f493decc4d55876adc6dbdf6008e48f10c318f74e217896e8e` and excerpt `d98ece044dde43c36b1337d8e4df7cc7015f2b84d1c36402447f2601f180e778`; the pilot-pack manifest is the authority.*

*Note (2026-10-30): the participant register that D4, D6, D17 and D18 require now has an offline schema and validator (`training/sentiment/participant_register.py`, tested on invented registers only): anonymous codes, two annotators, one adjudicator, one evaluator and a de-identification verifier, independence attestations, role-checked access authorizations with scope and dates, a deletion authorization, and consent metadata for consented data. It does not decide anything: independence stays the owner's attestation, the storage location (D16) is not approved, no register exists, and C3 (withdrawal versus unlinkability) is still unresolved. The D13 calibration policy (temperature fitted on the calibration split only, 10 equal-width bins, report-only ECE, descriptive-only below 20 scored examples) is implemented for synthetic fixtures; no annotation, collection or freeze has happened and the rubric stays `v0-draft`.*

*Note (2026-10-30): the owner's retention-and-deletion and adjudication-and-agreement decisions are specified in the consolidated form (rows D17 and D8) and the register validator enforces the deletion policy; no register, path (D16), source (D1, D2), rubric freeze (D5) or permission to create data (D20) exists yet, and C3 (withdrawal versus unlinkability) remains unresolved for any consented text.*

*Note (2026-10-30, phase closure): The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved. No annotation, collection or rubric freeze happens in this phase; the rubric stays `v0-draft`.*
