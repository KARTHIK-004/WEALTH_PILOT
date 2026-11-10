# B2 pause and research handoff

Date: 2026-10-19. Status: **B2 is paused (deferred), not complete. No new phase number is created. Nothing was run.**

Written for: you, the project owner, who decides whether and how the research track continues.

**What this task did:** read the authoritative plan and the latest B2 reports, identified the next defined phase, separated the work by state, specified a minimal experiment on existing market data, and recorded the unresolved dependencies. It changed documentation only.

**What it did not do:** no AI annotation, no provider call, no external data transmission, no sealed-key access, no GDELT download, no deletion or overwrite of any data, label, backup, report, approval artifact or code, no model training or experiment, no hosted-database access, no commit. Nothing here claims sentiment is validated or that any model improves on any baseline.

**Labels:** [VERIFIED] read from a file or a check; [PLAN] stated by `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`; [PROPOSED] not yet approved; [UNVERIFIED] not confirmed; [ESTIMATED] computed with stated assumptions.

---

## 1. The next phase, from the authoritative plan

**Where the plan lives** [VERIFIED]. The research track (B0 to B10) is defined only in `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` (section 20, phased plan; section 21, acceptance criteria). `docs/PROJECT_PLAN.md`, `docs/BUILD_PLAN.md`, `TASKS.md` and `CLAUDE.md` contain no B-track phases. The architecture document says the track is not a numbered phase and "no Phase 37 exists". No new number is created here.

**The plan's order, and what blocks it:**

| Phase | Plan deliverable (section 20) | Plan dependency | State now |
| --- | --- | --- | --- |
| B0 | Architecture and feasibility | none | done |
| B1 | Behaviour features on existing fields | your decision on inputs | done and accepted |
| B2 | Approved news source, ingestion, alignment tests | source approval | **paused** (section 3) |
| **B3** | Sentiment classifier, validation against labelled text, aggregation | B2, **dependency approval** | **next in order, blocked** |
| B4 | Market-only, sentiment-only and hybrid models, walk-forward | **B3** | not started |
| B5 | Personalisation layer and nudge integration | B4, ADRs | not started |
| B6 | Ablation, leakage audit, robustness, report | B4 | not started |
| B7 / B8 | Audit design; ledger implementation | independent of B2 to B6 (the plan says they "can proceed in parallel if you prefer") | not started |
| B9, B10 | Frontend display; integration and viva | B5 and B8; all | not started |

**Result.** The next phase in dependency order is **B3**. It cannot start: it needs the B2 labelled data and filter decision, which do not exist, and a dependency approval (`transformers` and a deep-learning backend are not installed and not in the approved stack). It would also produce sentiment features, which you have excluded from model inputs until validated.

**Where the requested experiment sits.** You asked to prioritise experiments on existing market data and quantitative behaviour features. In the plan:

- **Market data without sentiment** is B4's **model A (market-only)** and **model D (existing baselines)** (section 11). The plan makes B4 depend on B3. **The plan does not say B4's market-only arm may run before B3**, so running it is a re-sequencing that needs your explicit approval and a note in the plan. I did not start it.
- **Behaviour features** are not market-model inputs: section 10.4 keeps them out of the market model, and they enter only the personalisation layer (B5, which depends on B4). RQ3 (do they improve relevance?) is "not testable" without relevance labels (sections 4 and 13.5). Section 5 below shows they also have no historical coverage.
- **B7/B8** are the only phases the plan itself marks as independent. They need no market or news data.

**So no phase can proceed without a decision from you.** The options, which you choose between:

1. **Approve re-sequencing B4's market-only stage** (models A and D) ahead of B3, specified in section 4. It is the only option that uses existing market data. It stays "B4"; no new number.
2. **Proceed with B7** (audit architecture and threat model decision record). It needs no data or model.
3. **Resume B2** by deciding the items in section 6.

I recommend option 1, with its approvals in section 6, because it is the only path that tests something with data already on hand. That is a recommendation, not a decision.

**Acceptance criteria that apply** (section 21, verbatim in substance):

- **B3:** classifier agreement with labelled text reported with its limits; model version stored; no live-request training.
- **B4:** all models trained on identical folds; leakage tests pass; baselines reproduced; results saved with seeds and dataset hashes.
- **B2:** every stored article has source, licence, `published_at` and `ingested_at`; duplicates and unmapped share reported; a test proves no article can be used before its publication cutoff.

---

## 2. Work by state

### Complete

- **B0:** design and feasibility document.
- **B1** (`reports/phaseB1_financial_behaviour_inputs_report.md`, `phaseB1V_verification_report.md`, ADR-042): optional monthly financial records and a pure behaviour-feature module. Accepted. Nothing reads them in analysis, recommendation, optimizer or compliance.
- **B2, research and tooling:**
  - The news-source evaluation and the Route A feasibility, pilot and readiness studies.
  - The isolated GDELT acquisition tool (offline-tested), with full acquisition always refused.
  - The authorised 192-batch development sample, acquired and verified (384 requests, 1,000,147,201 bytes).
  - The review dataset: 1,493 items, 312 overlap, 1,181 non-overlap.
  - The human annotation workflow, validator, labeller, label freeze and evaluation code (synthetic-tested).
  - The AI-assisted annotation pipeline, **built but disabled** (B2-U3), with its approval package (B2-U4) and offline repairs (B2-U5). 577 tests pass in `tests/backend/data/gdelt/` as of B2-U5.

### Paused (B2), with acceptance criteria not met

| B2 criterion or deliverable | State |
| --- | --- |
| Stored-article metadata (source, licence, `published_at`, `ingested_at`) | partly met, **for the development sample only** |
| Duplicates and unmapped share reported | partly met, sample only |
| Pre-cutoff test | met at the rule level |
| Labelled review of the 1,493 items | **not met: 0 labelled, 0 AI suggestions** |
| Label freeze, evaluation against the sealed key, filter decision | **not met** (the key has not been opened) |
| Window-wide acquisition driver; full-window ingestion | **not met** (driver not built; full acquisition not approved) |
| The B2 architecture decision record | **not written** |

### Blocked by a decision of yours

- **Labelling path:** human-only labelling of the 312 overlap items, or the AI-assisted protocol (B2-T options A to D).
- **The four AI gates:** methodology (including the blind subset, proposed 150), provider and model, data handling, execution; plus the polarity option and whether raw provider responses must be expirable (B2-U4, B2-U5).
- **Evaluation methodology** for AI-assisted labels (treatment of ambiguous labels, kappa and AC1, clustered intervals, use for the B2-I section 4.7 filter decision).
- **Locking the GDELT switches** (section 7 below).
- **Re-sequencing** (section 1) and the experiment approvals (section 6).

### Not started

B3 to B10; the B2 ADR; the window-wide acquisition driver.

---

## 3. Preserving B2 while it is paused

Live state, checked 2026-10-19 (read-only; the sealed key by size and time only) [VERIFIED]:

| Item | Value |
| --- | --- |
| Items / overlap / non-overlap; labelled | 1,493 / 312 / 1,181; 0 |
| `annotation_A.csv`, backup, working copy | `11db13e668bd3da8…` (identical) |
| `annotation_B.csv` | `211729002893c1e4…` |
| Sealed key | 142,900 bytes, modified 2026-10-13 22:28 +0530; not opened |
| GDELT data on disk | about 963 MB under `datasets/raw/gdelt/` (raw batches about 955 MB) |
| AI build lock; adapter registry | `False`; empty |
| GDELT `NETWORK` and `DEV_SAMPLE` switches | **still `True`**, and the development-sample approval record is still in `run_config.yaml` |

**Do not delete** the sample, labels, backups, reports or approval artifacts while B2 is paused. Your 2026-10-13 retention rule ("keep until annotation and review are complete, then delete") has not been triggered, because review is incomplete.

**One risk while paused:** the network and development-sample switches remain on, so a repeated `fetch-sample` would pass its gate. I did not change them (reversible, but it breaks one test that asserts the post-acquisition state). Locking them is your decision.

---

## 4. Minimal experiment: market-only baselines and one feature-addition comparison

**This is a specification, not a plan to run.** It needs the approvals in section 6. It follows the plan's section 10 to 12 and the existing harness in `training/market/`.

### 4.1 Question

Does a model using price-derived features predict the next 5-trading-day realised-volatility category better than a naive baseline and the existing GARCH baseline, on identical walk-forward windows? A second, optional comparison asks whether adding **cross-asset price features** helps. **No result exists; no improvement is claimed or expected.** The plan notes that a null result is a likely and legitimate outcome.

### 4.2 Explicitly excluded inputs

- **GDELT sentiment, and any news-derived feature:** unvalidated, and the labelled review is 0 of 1,493. It is not an input to any arm.
- **Financial-behaviour features (B1 and FAR-Trans):** the plan keeps them out of the market model (section 10.4), and they have no usable history (section 5).
- User or customer data of any kind.

### 4.3 Data

- **Source of record:** the `market_data` table, 5 instruments (`^IXIC`, `^NDX`, `QQQ`, `AGG`, `GLD`), 1,177 daily rows each, 2022-01-03 to 2026-09-11, 1,176 returns. Fingerprint `563afd212589d22002696a56580998f7b61f8135547dc41933773aa92273ce40` (per-ticker hashes in `reports/phaseB2H_pre_acquisition_readiness.md` section 5.1) [VERIFIED in B2-H].
- **Access:** the table is in the hosted database, and there are no market-data files [VERIFIED in B2-H]. The existing training did **not** read the table: it fetched from yfinance directly [VERIFIED from code]. See section 7, item 1.

### 4.4 Target [PROPOSED; not approved]

The plan's primary target (section 10.2): the category Low, Normal or High of realised volatility over the next 5 trading days (labels span t+1 to t+5), with category boundaries from the **training window's terciles only**. It is not approved. **Fallback:** the already-approved 1-day return and 20-day realised-volatility targets of the existing harness, scored by RMSE and MAE.

### 4.5 Arms

All arms are trained and scored on the same windows and the same test observations.

| Arm | Model | Features |
| --- | --- | --- |
| N1 (naive) | Training-window majority class | none |
| N2 (naive) | Persistence: the category of the most recent already-realised 5-day window | trailing volatility only |
| G | GARCH forecast converted to a category with the training-window terciles | returns |
| M2 | Regularised logistic regression, then gradient-boosted trees (XGBoost 2.1.2, installed) | own-instrument price features: lagged returns, trailing volatility at several windows, momentum, drawdown, volume change |
| M3 (optional) | the better of the M2 models | M2 features plus other instruments' same-day price features |

M3 is run only if the coverage and leakage tests in 4.7 pass. No other feature addition is proposed. Behaviour and sentiment features are not candidates.

### 4.6 Validation, preserved from the existing design

- **Chronological expanding-window walk-forward**, no shuffling: 504 initial training days, 63-day test windows, 10 windows, 630 test observations per instrument, `random_state=42`.
- **Embargo:** the existing 5 trading days. For a 5-day label the embargo must be **at least the label length**, so 5 is the minimum and must not be shortened. A unit test must show no training label window overlaps a test origin.
- **Training-only preprocessing:** scaling, category terciles, class weights and any selected hyperparameter are fit on the training fold only. Tuning happens inside the training fold (a nested expanding split). The test window is never used to choose anything.
- **Point-in-time features:** each feature at day t uses only data available at the close of t, with tests that fail if a feature uses a later timestamp.
- **Consistent windows:** one fold definition, written once, used by every arm and every instrument. A comparison is valid only between arms scored on identical origins.
- **Records:** seeds, library versions, the dataset fingerprint, the fold boundaries, and every arm's results saved to a new location (not `models/market/`, which is not overwritten).

### 4.7 Tests required before any model is trained

1. Label-window versus embargo overlap test.
2. Point-in-time test for every feature.
3. A fold test that proves terciles and scalers see only training rows.
4. A coverage check: every feature is defined for every origin in every fold (no silent drops), with the count of any missing.
5. A reproduction check: the existing naive, ARIMA and GARCH results (`models/metrics.json`) are reproduced on the frozen data within a stated tolerance. If they are not, stop and report; the data differs from the data behind the existing results.

### 4.8 Metrics and what counts as evidence

- **Category target:** macro-F1, balanced accuracy and per-class recall, per instrument and per fold, against N1, N2 and G.
- **Intervals:** fold-level and block-bootstrap intervals, which respect overlapping labels.
- **Planned comparisons, fixed in advance:** each of M2 and M3 against the best naive arm and G, and M3 against M2, for 5 instruments. Holm correction across them. Negative results are reported.
- **Sample size, stated up front** [ESTIMATED]: 630 test origins per instrument, but 5-day labels overlap, so the effective number of independent labels is about 126 (630 ÷ 5). A rough standard error for an accuracy near one half is about 4.5 points, so a 95% interval of about ±8.7 points. **Differences smaller than roughly nine points are not distinguishable from chance for one instrument.** The plan's figure of "about 1,140 usable observations" (section 12) does not match the harness: after the 504-day initial window there are 630 test origins per instrument (`models/metrics.json`).
- **No improvement is claimed before results exist.** A better forecast metric would not show better portfolio outcomes; portfolio claims need the separate cost-aware backtest (B6).

### 4.9 Holdout [decision needed]

No final holdout is defined [VERIFIED, B2-H]. The existing 630 test observations have already been scored by the existing models, so they are not untouched. The 37-return unused tail (2026-07-22 to 2026-09-11) is far too short for a 5-day-category test (about seven non-overlapping labels). Options for you: designate nothing and label every result exploratory; use the tail only as a descriptive check; or treat data after 2026-09-11, collected later, as the true holdout. Pre-registering the comparisons in 4.8 before any run is the main guard against tuning to the test windows.

---

## 5. Behaviour features: coverage assessment [VERIFIED]

| Source | What it has | Historical coverage | Usable for a market or feature-addition experiment? |
| --- | --- | --- | --- |
| B1 monthly records and `behaviour_features_v1` | income, expenses, savings, investment contribution ratios and changes, per customer per month | **None in the repository.** B1 added no dataset and no demo or seed records (B1 report); the hosted database was not queried | **No** |
| FAR-Trans transactions (Phase 5 panel) | trade count, buy value, asset mix per customer-month; 127,924 rows, 29,090 customers, 2018-01 to 2022-11 | real, but investment activity only (no savings or expense data), and it overlaps the market data **only in 2022** (about 84,000 transactions) | **No** as a market predictor (plan 10.4). It supports only the existing risk and drift models |
| Kaggle expense data | spending categories | separate population; ADR-010 forbids linking it to FAR-Trans | **No** |
| Synthetic ML dataset (`datasets/generated`) | generated | ADR-039: not read by any training script; synthetic data cannot validate a behaviour effect | **No** |

So no behaviour-feature comparison can be run now. The only behaviour deliverable that could proceed is a **non-modelling coverage and leakage audit** (a feature-availability matrix), which needs no training and no new data. RQ3 stays "not testable" unless relevance labels are created.

---

## 6. Decisions and approvals needed before implementation

For the market-only stage (option 1):

1. **Re-sequence B4's market-only stage ahead of B3.** The plan lists B4 as dependent on B3.
2. **Approve the primary target** (5-day volatility category), or choose the fallback.
3. **Approve the arms and the planned comparisons** in 4.5 and 4.8, and the minimum effect that would count (the plan's RQ1 refers to a pre-registered minimum effect that is not yet defined).
4. **Choose the data route** (section 7, item 1).
5. **Decide the holdout** (4.9).
6. **Authorise a human-run training script** in `training/` and an output location outside `models/market/`. Nothing trains in a request or a test, and I do not run it.

For resuming B2: the items in section 2, "Blocked by a decision of yours".

---

## 7. Missing data, insufficient history and unresolved dependencies

1. **Data access (blocking).** The market data exists only in the hosted `market_data` table, and the existing results came from a direct yfinance fetch on 2026-09-14, not from that table [VERIFIED]. Running anything needs either an authorised read-only export of the table, checked against the fingerprint `563afd21…`, or a fresh fetch whose values may differ from the table (revisions, adjustments). The reproduction check in 4.7 decides whether the two agree. I did not access the database or the network.
2. **Short history.** 1,176 returns per instrument; only 10 walk-forward windows and 630 test origins; about 126 effective labels for a 5-day target (4.8). Only moderate or large effects are detectable.
3. **No untouched holdout** (4.9).
4. **The primary target and the minimum effect are not approved** (section 6).
5. **No behaviour or sentiment history** (section 5, and B2 paused). Neither enters the experiment.
6. **Instrument scope.** The universe is five US-listed instruments in USD (QQQ, AGG, GLD plus two indices). Results say nothing about Indian instruments (plan section 5).
7. **No experiment code exists.** The training script, the feature builders and the leakage tests (4.7) would be new; the plan treats the existing market models as not to be replaced or retrained.
8. **Dependencies:** `xgboost 2.1.2`, `scikit-learn 1.5.2`, `arch 7.1.0`, `statsmodels 0.14.4`, `pandas 2.2.3`, `numpy 1.26.4` are installed [VERIFIED]. The market-only stage needs no new dependency. B3 would need `transformers` and a deep-learning backend (not installed, not approved).
9. **Compute.** CPU only; the market-only models are small and fit this machine.

---

## 8. Documentation changes and verification

**Changed** (documentation only):

- `reports/phaseB2_pause_and_research_handoff.md`: this report (new).
- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`: a short section 7.12 recording the pause, and a status note under section 20 pointing here. No existing text was rewritten, and no method or criterion was changed.
- `docs/MEMORY.md`: one short entry marking B2 paused and naming the next phase and the blocker.

**Not changed:** `TASKS.md` (it tracks numbered phases and contains no research-track entries), the rubric, validators and code, any earlier report, and every data file.

**Verification performed:**

- Re-read the plan sections (7.11, 8 to 13, 20 to 22), `docs/MEMORY.md`, the B1 and B2 reports, `models/metrics.json` (market, risk, behaviour) and the training modules, and confirmed by search that no other document defines the research phases.
- Confirmed the live B2 state read-only (counts, hashes, key size and time, gate state, disk size), the same values as before.
- Checked that every file path cited in the three edited documents exists.
- **No tests were run** for this task, because only documentation changed; I do not claim any test result here. The last recorded result (B2-U5, 2026-10-19) was 577 passed in `tests/backend/data/gdelt/`. The full project suite and the hosted-database tests were not run.
- No model was trained or run, no provider or network was used, and nothing was committed.
