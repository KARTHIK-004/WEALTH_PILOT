# Research Enhancement Track B2 / S2 — Sentiment Completion Report (current)

Date: 2026-10-20 (UTC). Written for: the project owner. This file supersedes the earlier version of itself; owner decisions live in `reports/phaseB2S2_OWNER_APPROVAL_WORKSHEET.md` (the authoritative register) and are not copied here.

## 1. Status in one paragraph

**Engineering of every model-independent stage is complete and tested. Nothing is scientifically validated, no policy gate is cleared, and no real sentiment (title scorer) exists.** Accounting, coverage, near-empty
evidence, candidate conversion, primary/sensitivity counting, the descriptive GDELT document-tone baseline, the scorer interface, validation sampling/export/evidence infrastructure and the blocked-state pipeline are
implemented. Real scoring, daily features and forecast evaluation remain blocked by unapplied policies, a missing model/runtime/weights, missing independent labels and an unapproved protocol.

## 2. Verified state (this run)

| Item | Value |
| --- | --- |
| Git | HEAD `71b363f`, branch `master`, 0 staged, 49 tracked modifications (unchanged), 185 untracked (the sentiment package, its tests and reports are all untracked). Nothing staged, committed or pushed. |
| Development sample | 546 files, tree fingerprint `271939bb1895d1d3` before and after (read-only harness); 192/192 slots, 170/170 day files, 26,854 records valid |
| Policy table | 7 of 8 required policies applied (5 provisional, 2 approved) by the owner's decisions; only `scorer_approval_and_polarity_validation` is unresolved. Provenance: `orchestrator.POLICY_PROVENANCE` |
| Tests (run now) | `tests/backend/data/gdelt/test_sentiment_*.py`: **467 passed**. Full `tests/backend/data/gdelt`: **1492 passed** in 79 s (after the 2026-10-20 policy application).  No skips or failures. |
| Mutation checks (scratchpad scripts, source restored after each) | this run's new evidence/approval guards 8 of 8 caught; earlier runs: tone baseline 10/10, conversion/counting 9/9, validation sampling 6/6, near-empty/coverage 9/9 |
| Not done | no network call, download, install, key/sealed-data access, label creation, inference, scoring, feature generation, evaluation or acquisition in this run |

## 3. Work completed this run (all small, gap-closing)

- `polarity_validation.py`: **target-bound evidence** (`validate_target_evidence`). Two separate targets, `wording_tone` and `market_direction` (`TARGETS`), are never pooled; every label must name its target, be bound to the exact
  annotation export (`annotation_export_sha256`, order-independent, covers id, theme and title hash) and lie inside the frozen validation sample; empty, unfrozen, AI-sourced, overlap-excluded or off-sample labels are refused; a
  predictor of one construct is refused against labels of the other unless a mapping in `APPROVED_CONSTRUCT_MAPPINGS` (empty) is cited; results are per theme, an unlabelled theme is "insufficient", never a score.
- `orchestrator.py`: `POLICY_PROVENANCE` (immutable) names the worksheet record behind each required policy's status. A status is never an approval by itself.
- Tests: `test_sentiment_target_evidence_integrity.py` (7), including that the tone mapping's approval is frozen and has no default.
- Verified, unchanged: stage blockers come from the live table (`pipeline.blocking_gates`, tested against the pipeline); derived tone still requires **all eight** policies; the aggregator's `n_slots_near_empty` already follows the
  owner-confirmed OD-13 alignment (so the "remaining discrepancy" no longer exists); processed-but-unreconciled slots are excluded from the numerator (OD-10 part 2) and the shared block agrees; the denominator is the full grid.

## 4. What is engineering-complete (code + tests)

| Area | Where |
| --- | --- |
| Manifest/day-file adapters, reconciliation, late arrivals (caller-declared lookback), window orchestrator, digest | `manifest_adapter`, `dayfile_adapter`, `slots`, `orchestrator` |
| Shared completeness vs usability vs theme evidence vs result availability; coverage report; near-empty detector (observed and derived kept apart) | `completeness`, `coverage_report`, `near_empty` |
| Candidate → `ArticleRecord` (title-only; text-ok + theme flag; duplicates kept; `UNLINKED:<id>`; hash/outcome checks) | `scored_records` |
| Primary counting (every eligible record) + dedup sensitivity | `features.aggregate_daily_with_sensitivity` |
| Descriptive document-tone baseline (raw strings kept; valid/missing/invalid; mean with `n_valid`, `n_records`, `n_valid_all_zero`, all-zero-excluded sensitivity; gated) | `tone_baseline` |
| Scorer interface (fail-closed, no fallback to neutral) and offline model-metadata review | `scorer_port`, `model_metadata` |
| Validation sampling, title-only annotation export, per-theme and target-bound evidence (descriptive only, verdict `NO_ACCEPTANCE_CRITERIA_APPROVED`) | `polarity_validation` |
| Blocked-state pipeline and per-stage blockers | `pipeline` |
| Human-annotation utilities (assignment, kappa, adjudication, freeze manifest, MIX/UNC handling) and the sample/export builder | `annotation_tools`, `scripts/build_sentiment_validation_sample.py` |

All modules are under `backend/wealthpilot/data/gdelt/sentiment/`; tests under `tests/backend/data/gdelt/test_sentiment_*.py`.

## 5. Stages and what blocks them (live table, after the owner's 2026-10-20 decisions)

| Stage | Blocked by |
| --- | --- |
| Derived tone (`tone_derived`) | `scorer_approval_and_polarity_validation=UNRESOLVED_NOT_APPLIED` only (the all-eight gate is kept) |
| Real scoring | the same policy; no approved model, runtime, weights |
| Daily features | the same policy; E1 (no scorer); E4 (not authorised) |
| Forecast evaluation | everything above; E5 (no approved target, instruments, split, baselines, acceptance criteria) |

| Required policy (`orchestrator.POLICY_STATUS` key) | Status | Note |
| --- | --- | --- |
| `deduplication_and_story_updates` | APPLIED_PROVISIONAL | primary = every eligible record; current dedup = sensitivity |
| `cross_interval_story_uniqueness` | APPLIED_APPROVED | each record in its verified availability interval; no unique-story claim |
| `source_coverage_threshold` | APPLIED_PROVISIONAL | 0.75 / 0.50 / 0.90, informational: never decides usability |
| `scoring_coverage_threshold` | APPLIED_APPROVED | report only, no cutoff |
| `scorer_approval_and_polarity_validation` | **UNRESOLVED_NOT_APPLIED** | blocked: model, licence, runtime, weights, labels, criteria |
| `near_empty_slot_handling` | APPLIED_PROVISIONAL | 14 / 7 / 10%; unknown stays unknown |
| `holiday_and_early_close_calendars` | APPLIED_PROVISIONAL | caller-supplied, unverified |
| `late_batch_strictness` | APPLIED_PROVISIONAL | caller-declared lookback per run; residual limit reported in every result |

Decisions and their provenance: worksheet section "Policy application decisions (2026-10-20)" and `orchestrator.POLICY_PROVENANCE`. **The aggregator's configured coverage threshold is now informational too** (`features._assess_day`): each row reports `coverage`, `coverage_threshold` and `coverage_threshold_met`, and the shared
`coverage_report` lists the configured value as its primary threshold. The status `insufficient_coverage` is no longer produced; a low ratio alone neither suppresses features nor changes usability. Integrity rules are
unchanged and independent of the ratio: no available batch (`missing_source_batches`), non-final or unresolved earlier batches, unreconciled slots or a processed slot with no reconciliation result
(`slot_article_mismatch`), and grid problems all still fail closed; gaps leave the interval `undecided_policy`, an empty theme `unverified_empty`, `no_news` `None`.
**Consequence to be aware of:** the ratio no longer promotes an interval with gaps to `usable_under_coverage_rule`, so such results are `unavailable (undecided_policy)` at any coverage. That matches the orchestrator. If you want
intervals that meet 0.75 to count as usable, the threshold would have to be `APPLIED_APPROVED` (a decisive rule), which contradicts "informational"; your call.

## 6. Model, licence and runtime inventory (metadata-only read already done; not repeated)

| | ProsusAI/finbert | mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis |
| --- | --- | --- |
| Revision read | `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` | `ae0eab9ad336d7d548e0efe394b07c04bcaf6e91` |
| Labels (declared index order) | 0 positive, 1 negative, 2 neutral | 0 negative, 1 neutral, 2 positive (differs: a scorer must follow each model's own order) |
| Licence **claim** (model card, unverified) | CC BY-NC-SA 4.0 weights; training data PhraseBank (CC BY-NC-SA 3.0) + Reuters TRC2 (NIST terms) | Apache-2.0, yet trained on PhraseBank (NC-SA per the other card); card auto-generated |
| Self-reported quality | none | 0.982 accuracy on the PhraseBank `sentences_allagree` split: not evidence about GDELT headlines |
| Runtime | needs `transformers` + torch/TF/Flax; none installed; outside the approved stack | needs `transformers` + torch (no TF weights) |
| Status | deferred | deferred |

A model-card licence statement is not verified permission; code, weights and training-data licences are separate questions. Domain mismatch (company-specific training sentences vs macro headlines) and the tone-versus-direction gap are open for both.

## 7. Scientifically unvalidated

No independent polarity labels exist, none were created or read, and no sealed data was opened. Tone baseline values (when permitted) are descriptive document tone, not title sentiment or market direction. No metric, threshold,
forecast result or "validated" claim exists, and the synthetic tests prove only code behaviour.

## 8. Proposal only: minimal evaluation protocol (NOT approved; nothing is run)

Question: does a lagged, availability-safe sentiment/tone feature add predictive information beyond market-only features? Candidate target (proposal): next-5-trading-day realised-volatility category from training-only tercile cuts
(the existing 20-day realised-volatility definition is the alternative). Instruments: the market model's `^IXIC`, `^NDX`, QQQ, AGG, GLD with their stored market-data provenance. Calendar/cutoff: the existing 16:00 New York interval
rule with caller-supplied calendars. Splits: expanding-window walk-forward with embargo, reusing `training/market/common.py::walk_forward_windows`. Arms: market-only, sentiment/tone-only, hybrid, time-shuffled-sentiment control. Missing-news and
low-coverage days stay missing (never neutral) and are reported, not imputed. Per-theme evidence required; metrics and uncertainty (block bootstrap) and the "inconclusive" rule (e.g. interval covering no difference) must be fixed before any run. Every item here awaits your decision.

## 9. Owner decisions still open (recommendations are NOT approval)

Applied or decided on 2026-10-20: policies 1-7 above; scorer policy kept blocked; all-eight derived-tone gate kept; separate polarity targets; fresh human labels frozen and hashed before scoring; both models deferred; protocol required
before evaluation; OD-09 deferred. Still open:

| # | Decision | Recommendation |
| --- | --- | --- |
| 1 | Licence reading for a model (E1b), then model choice, weights download, install, local CPU run, transmission denied | decide the licence reading first |
| 2 | Polarity acceptance criteria and minimum labelled sample per theme and target; who labels and how disagreements are handled | state before labelling starts |
| 3 | Evaluation protocol (section 8) and the E4 feature go-ahead | approve before any run |
| 4 | Authoritative calendar source (currently caller-supplied, unverified) | name one when convenient |

## 11. Decision package: model licensing and independent validation (prepared 2026-10-20; proposals only, nothing approved)

### 11.1 Model candidates: claims versus verified permissions

Re-read from the saved local metadata files only (no network): the model cards' own wording was re-checked line by line against section 6. **Verified** below means "the card says so"; **no licence permission is verified for either model.**

| | ProsusAI/finbert | mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis |
| --- | --- | --- |
| Weights licence (card claim) | CC BY-NC-SA 4.0 (front matter, API tag and a "License and Usage Terms" section: "restricts commercial use ... any adaptations must be shared under the same license") | Apache-2.0 (front matter and API tag) |
| Who decides if use is "non-commercial" | the user: the card says Prosus cannot answer commercial or legal questions and disclaims all warranty | not addressed |
| Training-data restriction (card claim) | Financial PhraseBank is CC BY-NC-SA 3.0; the base language model was further trained on Reuters TRC2 "distributed by NIST under its own access terms" | trained on `financial_phrasebank` (4,840 sentences); the card does not mention that dataset's licence, which the other card states is CC BY-NC-SA 3.0 |
| Internal consistency | consistent (non-commercial throughout) | **inconsistent on its face**: a permissive weights label on a model trained on a non-commercial, share-alike corpus; the card is auto-generated ("proofread and complete it") |
| LICENSE file in the repo | none listed | none listed |
| Runtime | `transformers` + a tensor backend; weights for PyTorch, TF (`tf_model.h5`), Flax, safetensors; 109.5M parameters | `transformers` + PyTorch (no TF weights); 82.1M parameters; built with Transformers 4.10.2 / PyTorch 1.9; the repo also lists `training_args.bin`, a pickle that must never be loaded |
| In this environment | none of torch, transformers, tokenizers, safetensors installed; outside the approved stack (`CLAUDE.md` section 5); 8 CPUs, 15.7 GB RAM, 2 GB GPU of unverified use; CPU inference is plausible (assumption) | same |
| Task fit for GDELT titles | three-class tone on company-specific sentences; the titles are macro, market-level and short (median 62-64 characters); no validation on this text exists | same; the self-reported 0.982 accuracy is on the PhraseBank `sentences_allagree` split, the easiest subset, with the best epoch picked on it: no evidence about GDELT |
| Output labels | index order 0 positive, 1 negative, 2 neutral | index order 0 negative, 1 neutral, 2 positive (different: follow each model's own order) |
| Open legal questions (not for the assistant) | does a research prototype whose outputs feed an advisory demo count as non-commercial? does ShareAlike reach outputs or features, or only redistributed or fine-tuned weights? | is the Apache-2.0 label valid for weights derived from a non-commercial corpus? only the model author or the data owner can say |

Not established by anything local: what Financial PhraseBank's annotators were asked (investor view of price impact versus wording). If it was the investor view, both models lean toward market direction, not wording tone; this affects which target each can be validated against.

**Owner decisions needed before a model can be selected, downloaded or run (each separate; none implied by another):**

| ID | Decision | Options | Recommendation (NOT APPROVAL) |
| --- | --- | --- | --- |
| M1 | Licence reading | (a) accept CC BY-NC-SA 4.0 as a research-only, non-commercial use and keep any derived weights or fine-tunes out of redistribution; (b) accept the Apache-2.0 claim for the DistilRoBERTa model despite its training data; (c) require written confirmation from the model author or a legal opinion first; (d) neither model | (a) or (d); do not rely on (b) without (c) |
| M2 | Model | FinBERT / DistilRoBERTa / neither | decide after M1 |
| M3 | Weights download | allow one download from the model host, pinned to the revision read (`0bc2ac10...` or `ae0eab9a...`), SHA-256 recorded before first use, safetensors only | allow only after M1 and M2 |
| M4 | Package installation | `torch`, `transformers`, `tokenizers`, `safetensors` (exact versions; compatibility with numpy 1.26.4 and TensorFlow 2.17 is unverified), preferably in a separate environment; this is the "ask first" `CLAUDE.md` requires for libraries outside the approved stack | separate environment; CPU build |
| M5 | Execution | local CPU only (already decided: external transmission denied) | confirm |
| M6 | Scope of first use | score only the validation sample first (about 1-2 thousand titles at most), never the full window | confirm |

### 11.2 Human annotation protocol (proposal; uses `draw_validation_sample`, `annotation_rows`, `annotation_export_sha256`, `validate_target_evidence`)

1. **Pool and sample.** Pool = text-ok, theme-flagged candidates from the existing 192-batch development sample (no new acquisition needed: 2,701 equity_us, 2,888 rates_us, 192 gold before exclusions; gold is thin). `excluded_ids` = the overlap-excluded items from the approved overlap-first control (D13): read from its record, not from labels. Fixed seed 42 (project rule). Proposed `per_theme` = 200 for equity_us and rates_us; gold takes what the pool allows and reports the shortfall.
2. **Two separate passes, two instruction sheets, never shown together.** Pass A, `wording_tone`: "Judge only the words of this headline: positive, negative or neutral tone. Ignore what you think it means for markets." Pass B, `market_direction`, per theme: the existing rubric wording, "from the asset holder's view; rising yields are NEG for bonds", with POS / NEG / NEU / MIX / UNC. Instruction sheets are versioned and hashed. MIX and UNC have no scorer counterpart, so they are counted and reported as "not comparable" and excluded from agreement metrics (this handling needs your approval; the validation code currently accepts only the three labels).
3. **Blinding.** Annotators receive only `annotation_rows` (id, theme, title), in a deterministic shuffled order. No tone value, prediction, score, source domain or AI suggestion is shown. No model runs before the labels are frozen. If any annotator saw such a value, those labels are void.
4. **Annotators and adjudication.** At least two independent humans label a proposed 20% overlap subset to measure agreement; the project owner may label the rest alone (precedent: the B2 plan). Disagreements go to a third pass or an adjudicator who sees both labels but no model output; the original labels and the adjudicated label are both kept. Unresolvable items are excluded and counted.
5. **Provenance per label.** annotator initials (never an email), `human`, basis `own`, date, instruction-sheet hash, export hash, target, theme.
6. **Freeze.** When complete: compute a SHA-256 over the canonical label file bound to the export hash and the sample manifest hash; record it (and the pre-registered metrics and criteria below) in the worksheet **before** any scorer runs. Timestamps are recorded but the control rests on the hashes, as in D13. No re-sampling or re-labelling after the freeze.
7. **Option, not default:** the 312 existing human-only overlap labels (D13) include per-theme asset-holder polarity. You decided on fresh labels; reusing those would save effort for `market_direction` but they were drawn for filter validation, only exist where a theme was labelled relevant, and I have not read them. Your call.

### 11.3 Metrics, evidence floor and acceptance criteria (ALL PROPOSALS; none approved; nothing computed)

Reporting (per target and per theme, never pooled): confusion matrix; accuracy with Wilson 95% interval; per-class precision and recall with Wilson intervals; macro-F1 (descriptive); labelled, scored, unavailable and not-comparable counts; inter-annotator agreement (Cohen's kappa on the overlap subset); the majority-class baseline accuracy; and, for the tone baseline, the same table so the two are comparable only where a mapping is approved.

Wilson 95% half-widths show what sample sizes buy (computed arithmetic, not data): at true accuracy 0.8, n=100 gives [0.71, 0.87], n=200 [0.74, 0.85], n=400 [0.76, 0.84]; at 0.7, n=200 gives [0.63, 0.76].

| Item | Proposed value | Why |
| --- | --- | --- |
| Minimum scored labels per theme and target | 200 (below it: "insufficient", no verdict) | interval width about 0.11 at 0.8 |
| Minimum support per present class | 30 (a class below it is reported but excluded from the criterion) | per-class intervals are otherwise uninformative |
| Agreement floor | kappa >= 0.6 on the overlap subset; below it the target definition or instructions are revised before scoring | labels this noisy cannot validate a scorer |
| Acceptance (a scorer is "supported" for a theme and target) | accuracy Wilson lower bound exceeds the majority-class baseline accuracy by at least 0.05, and every class above the support floor has recall lower bound >= 0.40 | beats a trivial baseline with margin and does not ignore a class |
| Rejection | accuracy Wilson upper bound at or below the baseline | clearly no better than guessing the majority |
| Otherwise | inconclusive | intervals overlap |
| Cross-construct comparison | forbidden unless an approved mapping is cited (`APPROVED_CONSTRUCT_MAPPINGS` is empty) | wording is not direction |

What this cannot show: acceptance on these labels is evidence about this sample and annotators, not about forecasting; a supported tone scorer is still not a validated predictor of anything.

### 11.4 Annotation milestone: sample drawn, exports written, nothing labelled (2026-10-20)

Decisions applied (owner): `wording_tone` and `market_direction` as separate targets; fresh human labels (the D13 overlap labels were not used or read); seed 42; up to 200 equity_us and 200 rates_us titles and all
eligible gold up to the pool; annotators see only item id, theme and title; 20% double-labelled per theme; blind adjudication; labels frozen and hashed before any scoring; `MIX` and `UNC` kept distinct.

Built by `scripts/build_sentiment_validation_sample.py` (local, offline, read-only on the dataset; the ONE file under `scripts/` the scaffold isolation test now explicitly allows to import the sentiment package, with its own
test that it touches no network, model, scoring, key or label). Outputs (new, `datasets/derived/sentiment_validation_v1/`, 8 files; the script refuses to overwrite and a fresh run is byte-identical):

| Theme | Eligible pool (text ok, theme-flagged) | After D13 exclusion | Requested | Sampled | Shortfall | Double-labelled |
| --- | --- | --- | --- | --- | --- | --- |
| equity_us | 2,701 | 2,631 | 200 | 200 | 0 | 40 |
| rates_us | 2,888 | 2,844 | 200 | 200 | 0 | 40 |
| gold | 192 | 147 | 200 | 147 | **53** (pool exhausted; no data was acquired to fill it) | 30 |

The D13 overlap control removed 129 distinct candidates (membership read from the `gkg_record_id` column of the original overlap manifest only; its id-list hash is recorded; the overlap lock record does not exist in this repository, so none was used).
Some articles are sampled for more than one theme (flagged in the manifest); each pass has one row per (item, theme).

Hashes (SHA-256): sample manifest `22593a372596e21a4cca8a0bdd5ae49ea5e9e8625e391fc5c7527f49e06f0764`; manifest file `81a5566c6df63e725533cfd6d32daded9ed16a5ecc13d98c5afc064d5b4c680a`; double-annotation assignment
`d4140d6c01287786bcf93918d7695784c53a37183642f1a75920b5a36bb48273`; export content (target-bound) wording_tone `83a1633d7a80f2a1b302eef32ef9a228b2c662e1bd1cdae4cd5ba4f6a4b6cac1`, market_direction
`da354113d1c1a7eca6d86391c7a710988b21ed2b124ca16cbeb6fb0804259173`; instruction sheets wording_tone `94d6e9a7a20e9802e82aeb08020d7cd4b81099c29e7d0681cf28336f13fb0293`, market_direction
`ff9d2f502a680a82a82ec6a8036a489251da7c65334e1ac30be039f03005c366`; overlap-id list `7e769356182a2c460c5d82b358504dcecec274f8d04fdd88945c7ef673c86736`; source fingerprints (manifest database
`ea734b8a...e9dd3`, day files `3f3237da...6bd4`, candidates `a2fd2af6...a483`, 170 day files, 26,854 candidates, min_chars 20) and per-file hashes are in `sample_manifest.json`.

Privacy: the annotation sheets contain exactly `item_id, theme, title, code, note` (code and note blank). No tone value, score, prediction, source domain or label is exported.

Utilities added (`sentiment/annotation_tools.py`, 24 tests, mutation check 9/9): deterministic double-annotation assignment; Cohen's kappa (all five codes primary, three comparable codes secondary; undefined rather than 1.0
when chance agreement is 1); annotation records that must be human, `own` basis, initials not an email, bound to the target-specific export hash and instruction hash; disagreement queue and blind adjudication records (the
adjudicator attests no model output was seen; `UNRESOLVED` items are excluded and counted); `build_freeze_manifest`, which REFUSES missing, extra, malformed, AI-based, off-sample, unbound or duplicate labels, undecided disagreements,
a foreign or tampered assignment and naive timestamps; the freeze hash binds sample, export, instructions, assignment, protocol, every raw label and every adjudication (the timestamp is recorded, not hashed).

**MIX / UNC treatment (fixed now, before any result):** distinct from each other and from NEU; excluded from the 3-class confusion matrix, accuracy and F1 denominators; reported as counts per theme and target; a scorer's
predictions on such items are a descriptive breakdown, never right or wrong; agreement uses all five codes (primary) and the three comparable codes (secondary).
**Still proposals, not approved:** the metrics, evidence floors, kappa floor and acceptance criteria of 11.3 (the freeze manifest carries `PROPOSAL_NOT_APPROVED`).

No human annotation exists. Labels will exist only when real annotators return the sheets; they must then be frozen and hashed before any scorer runs.

### 11.5 Smallest executable next step

Hand `annotation_<target>_primary.csv` (and the `_secondary.csv` for the second annotator) to the human annotators with the matching instruction sheet; each returns initials and the filled `code` column. Then adjudicate disagreements blind,
build the freeze manifest (`build_freeze_manifest`), and record its hash in the worksheet. Approve or edit the proposed metrics and criteria (11.3) before that freeze. Scoring waits for M1-M6.

### 11.6 Decision request and recommended order

1. **Licence reading M1** (and then M2 model): your reading of CC BY-NC-SA 4.0 for a research prototype, or request written confirmation.
2. **Approve or edit the annotation protocol 11.2:** `per_theme` (200?), two passes, overlap subset (20%?), who labels and adjudicates, MIX/UNC handling, option to reuse D13 labels or not.
3. **Approve or edit the metrics, floors and criteria in 11.3** (they must be fixed before the freeze).
4. After 1-3: M3-M6 (download, install in a separate environment, local CPU, first-use scope).

Recommended execution order: (a) your decisions on 2 and 3, (b) sampler run and export (no model needed), (c) human labelling in two passes with adjudication, (d) freeze and record the hash, (e) M1-M6 decisions, (f) download, install and score the validation sample only, (g) evidence report against the pre-registered criteria, (h) only then reconsider the scorer policy and feature authorisation.

## 12. Next executable step

Follow the order in section 11.6: resolve the licence reading (M1) and approve the annotation protocol and criteria (11.2, 11.3); then a local scorer can be written behind `ScorerPort`, the sampler can produce the annotation export for human labelling, and the scorer policy can be reconsidered.
Until then every downstream stage correctly stays blocked.
