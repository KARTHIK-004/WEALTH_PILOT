# Research Enhancement Track — Phase B2-S2.8H: Owner Decision Intake

**Outcome: intake and audit only. 0 owner responses to the S2.8G worksheet were found, so every OD and E item is still unresolved.** This is a valid outcome.
Nothing below authorises anything. No policy status, code, test, threshold, parameter or lookback changed. Date: 2026-10-20 (UTC). Written for: the project owner.

## 1. Verified state (checked this phase)

| Check | Before | After |
| --- | --- | --- |
| Git | HEAD `71b363f`, branch `master`, 0 staged, 49 tracked modifications, 163 untracked | identical except this report (164 untracked) |
| S2.8G worksheet | present: `reports/phaseB2S2_8G_owner_decision_worksheet.md` (the +1 untracked file versus the S2.8G baseline of 162 is that worksheet itself, created after that count) | — |
| Policy table (`orchestrator.POLICY_STATUS`, executed) | unchanged from S2.8G; 8 of 8 required policies block, none `APPLIED_*` | unchanged |
| Sentiment tests | `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/backend/data/gdelt/test_sentiment_*.py` → 299 passed | not re-run (no change) |
| Full GDELT suite | **not run** this phase (last known: 1324 passed in S2.8E; no code changed since) | — |
| Sample tree | read-only harness `s25_verify.py`: 546 files, `271939bb1895d1d3` | unchanged |

**Search for an owner response.** I looked for any owner response or approval record for the S2.8G template (file names in `reports/` and `docs/`, and text search for
"owner response / owner answers"). Matches were only my own S2.8F/S2.8G documents and `docs/MEMORY.md` entries describing them. The S2.8H prompt contains no answers.
Other approval files (`phaseB2J_development_sample_approval_checklist.md`, `phaseB2U4_ai_annotation_approval_package.md`) concern earlier, different decisions and
were not read as answers to these items. Therefore: **owner answers verified = 0.**

**Provenance note.** Earlier reports (S2.8B–S2.8D) attribute some selections to the owner's phase-instruction text (not visible to me as a standalone record). I carry
those as `SELECTED_PROVISIONAL` or `IMPLEMENTED_NOT_APPROVED` with that source stated; they are not a response to the S2.8G worksheet and approve nothing new.

## 2. Intake register

"Owner answer" is `—` (blank = unresolved) unless a recorded earlier selection exists; any such selection is cited, not extended. No status here is `OWNER_CONFIRMED`,
`OWNER_CHANGED`, `AUTHORIZED_FOR_IMPLEMENTATION` or `AUTHORIZED_FOR_EXECUTION`.

| ID | Item | Status | Owner answer (source) | Depends on | What an answer would authorise | Still blocked | Evidence before changing the implementation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OD-01 | Earlier-batch lookback duration; who supplies the range | duration **UNCONFIRMED**; C-min mechanism **IMPLEMENTED_NOT_APPROVED** | — (mechanism selected per S2.8C report; no duration anywhere) | — | a duration or a measure-first rule | completeness claims beyond the declared range; E7 | measured lateness on contiguous data (none in repo) |
| OD-02 | Source-coverage thresholds: primary 0.75; sensitivity 0.50 and 0.90 (each separate); may the policy be applied | **SELECTED_PROVISIONAL** | — (values recorded as provisional, S2.8B record) | OD-03..06 for final behaviour | adopt/change/drop each value; applying the policy is a separate answer | any validity or no-news claim; scoring and features | behaviour on contiguous data with delayed and near-empty slots |
| OD-03 | Near-empty detector: 14 days, ≥ 7 observations, < 10% of median; partial lookback may decide | **SELECTED_PROVISIONAL** | — (provisional, S2.8B record) | contiguous history | adopt/change values; partial-lookback yes/no | replacing the observed flag; applying the policy | observed-versus-derived agreement on contiguous data |
| OD-04 | NULL near-empty: undecided, unusable, or usable only under an applied rule | **UNCONFIRMED** (principle "NULL is neither complete nor verified no-news" is recorded as selected; mechanism is not) | — | OD-02, OD-03 | one of the three mappings | treating NULL as false (never) | share of NULL slots on contiguous data |
| OD-05 | Explicit near-empty: primary handling; sensitivity variant wanted | primary **SELECTED_PROVISIONAL** (uncovered); variant **UNCONFIRMED**, not implemented | — | OD-02, OD-03 | confirm primary; authorise the variant | implementing the variant | OD-02/03 answered |
| OD-06 | Consecutive-missing-slot cap (none / number with unit / flag-only) | **UNCONFIRMED** | — | OD-02 | a cap rule | any cap | run-length distribution |
| OD-07 | Scoring-coverage threshold or report-only | **UNCONFIRMED**, **BLOCKED** | — | E1 | a threshold or report-only | scoring coverage use | scorer failure rates |
| OD-08 | Delayed batch with zero rows | **IMPLEMENTED_NOT_APPROVED** (rule applied in S2.8D, attributed there to the owner's instruction) | — (no reversal requested) | — | nothing new | — | — |
| OD-09 | Shared completeness vocabulary: confirm or exact renames | **UNCONFIRMED** (provisional assistant design) | — | — | freeze names and digest semantics | freezing before an answer | owner review of the enumerations |
| OD-10 | Aggregator: (1) report-only `CoverageBlock`; (2) processed-but-unreconciled slot treatment | **UNCONFIRMED** (both parts, separately) | — | OD-09 for (1)'s names | (1) a report-only field; (2) numerator semantics | numerator change without (2) | cross-check tests, written before any change |
| OD-11 | Linking rule or none; cross-interval counting; counting unit | retention/"similarity is not identity" **SELECTED_PROVISIONAL**; unit "every eligible record + repetition sensitivity" **SELECTED_PROVISIONAL**; linking and cross-interval **UNCONFIRMED** | — (S2.8B record) | E3 | linking/cross-interval rules | story IDs from similarity alone (never inferred) | repeat statistics are descriptive only |
| OD-12 | Calendar source (or caller-supplied); theme cutoffs yes/no | **UNCONFIRMED** (calendars caller-supplied, unapproved; theme cutoffs not implemented) | — | — | a source; theme cutoffs | production-like boundary claims | named calendar and a window check |
| E1 | Scorer/model identity and version; licence review; dependency list; separate authorisations: installation, external provider, data transmission, network | **BLOCKED** | — | — | selection only; each execution authorisation is separate | integration, install, provider calls | licence and dependency review |
| E2 | Polarity label source, protocol, acceptance criteria; labelling authorisation | **BLOCKED** | — | E1 | a validation plan | validated-polarity claims | completed independent labels |
| E3 | Eligibility, counting unit, story-ID policy | **BLOCKED** | — | E1, OD-11 | a conversion contract | conversion code | written contract and tests |
| E4 | Feature generation | **BLOCKED** | — | E1–E3, all 8 policies applied | permission only after those | features | policies `APPLIED_*` |
| E5 | Target, horizon, split/embargo, metrics; separate authorisation to run | **BLOCKED** | — | E4 | an evaluation design (approved criteria not reopened) | running any evaluation | written protocol |
| E6 | Independent reference-label plan; separate authorisation for any sealed-key access | **BLOCKED** | — | — | a validation plan | filter-validation claim; unsealing | independent labels |
| E7 | Window, lookback, storage, network authorisation, download authorisation (separate fields) | **BLOCKED** | — | OD-01, OD-03 | acquisition planning | any download | OD-01/03 answered |

Counts: owner answers verified **0**; unresolved decisions **19 of 19** (OD-08 counted as unresolved-by-answer only in the sense that no new answer exists; it is an implemented rule awaiting no input).
Ambiguities needing the owner: (a) whether the earlier-selected provisional values in OD-02, OD-03, OD-05 and OD-11 should now be marked confirmed, changed or left provisional;
(b) the original owner-decision message is not visible, so S2.8B–D attributions cannot be re-verified here; (c) OD-04's mechanism and OD-10's two parts need separate answers.

## 3. Next-action matrix

| ID | Class | Smallest next action supported by the evidence |
| --- | --- | --- |
| OD-01 | NEEDS_OWNER_CLARIFICATION | owner states a duration, "measure first", or "caller-supplied" |
| OD-02 | NEEDS_OWNER_CLARIFICATION | per-value answer plus a separate answer on applying the policy |
| OD-03 | NEEDS_OWNER_CLARIFICATION | confirm/change each value; partial lookback yes/no |
| OD-04 | NEEDS_OWNER_CLARIFICATION | pick one mapping |
| OD-05 | NEEDS_OWNER_CLARIFICATION | confirm primary; yes/no on the variant (no implementation without it) |
| OD-06 | NEEDS_OWNER_CLARIFICATION | none / number with unit / flag-only |
| OD-07 | BLOCKED_BY_DEPENDENCY (E1) | none until a scorer is approved |
| OD-08 | DOCUMENT_ONLY | none |
| OD-09 | NEEDS_OWNER_CLARIFICATION | confirm or list renames |
| OD-10 | READY_FOR_IMPLEMENTATION_AFTER_AUTHORIZATION (part 1: report-only block, plan in S2.8G section 3); part 2 NEEDS_OWNER_CLARIFICATION | owner answers part 1 yes/no and part 2 before any numerator change |
| OD-11 | NEEDS_OWNER_CLARIFICATION | linking rule, cross-interval rule, unit |
| OD-12 | NEEDS_OWNER_CLARIFICATION | name a calendar source; theme cutoffs yes/no |
| E1 | EXECUTION_NOT_AUTHORIZED | owner names model, licence, dependencies; separate authorisations later |
| E2 | BLOCKED_BY_DEPENDENCY (E1) | none |
| E3 | BLOCKED_BY_DEPENDENCY (E1, OD-11) | none |
| E4 | BLOCKED_BY_DEPENDENCY (E1–E3, 8 policies) | none |
| E5 | BLOCKED_BY_DEPENDENCY (E4) | none |
| E6 | EXECUTION_NOT_AUTHORIZED | owner supplies an independent labelling plan; no unsealing |
| E7 | BLOCKED_BY_DEPENDENCY (OD-01, OD-03) | none; no download |

Nothing in this matrix recommends starting S2.9 or S4 while required policies are unapplied or E1–E7 are unresolved.

## 4. Blank response template (unchanged from S2.8G; blank = unresolved; one line never approves another)

```text
OD-01 lookback:            [ ] fixed: ____   [ ] measure first, decided by: ____   [ ] caller-supplied indefinitely
OD-02 primary:             [ ] adopt 0.75   [ ] change to ____   [ ] drop
OD-02 0.50:                [ ] adopt   [ ] change to ____   [ ] drop
OD-02 0.90:                [ ] adopt   [ ] change to ____   [ ] drop
OD-02 apply the policy:    [ ] yes   [ ] no
OD-03 values:              [ ] adopt 14 / 7 / 10%   [ ] change to ____   [ ] drop      partial lookback may decide: [ ] yes [ ] no
OD-04 NULL flag:           [ ] undecided   [ ] unusable   [ ] usable only under an applied rule
OD-05 primary:             [ ] confirm uncovered   [ ] change to ____      sensitivity variant: [ ] yes [ ] no
OD-06 missing-slot cap:    [ ] none   [ ] ____ slots/hours   [ ] blocks   [ ] flags only
OD-07 scoring coverage:    [ ] ____   [ ] report only
OD-08:                     [ ] keep   [ ] reverse (explicit request)
OD-09 vocabulary:          [ ] confirmed   [ ] renames: ____
OD-10 (1) report-only block: [ ] yes [ ] no     (2) unreconciled slot: [ ] excluded [ ] covered
OD-11 linking: ____   cross-interval: [ ] allowed [ ] forbidden   unit: ____
OD-12 calendar source: ____   theme cutoffs: [ ] yes [ ] no
E1 model/version: ____  licence reviewed: [ ] yes [ ] no  dependencies: ____
E1 authorise separately: install [ ] y [ ] n   external provider [ ] y [ ] n   data transmission [ ] y [ ] n   network [ ] y [ ] n
E2 source/protocol/criteria: ____   authorise labelling: [ ] y [ ] n
E3 eligibility / unit / story-ID rule: ____
E4 feature generation: [ ] authorised (only after E1-E3 and all policies applied) [ ] not authorised
E5 target/horizon/split/metrics: ____   authorise running: [ ] y [ ] n
E6 reference-label plan: ____   authorise sealed-key access/unsealing: [ ] y [ ] n
E7 window: ____ lookback: ____ storage: ____   network: [ ] y [ ] n   download: [ ] y [ ] n
```

## 5. Validation of this document

All 19 items appear; every answer field is blank unless an earlier recorded selection is cited with its source; recommendations are not in the answer column; no policy status changed
(table in section 1 read from the code before and after); no execution permission is inferred; no existing file was overwritten (only this report was created); the report matches the
state checked above. `docs/MEMORY.md` was **not** changed: no project state changed.

## 6. Not done

No network, download, install, key access, unsealing, scoring, features, evaluation, acquisition, S2.9 or S4; no code, test, threshold, parameter, lookback or policy-status change; no staging or commit.
