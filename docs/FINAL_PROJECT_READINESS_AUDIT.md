# WealthPilot AI - Final Repository-Wide Readiness Audit

Date: 2026-11-10. Branch `master`, single commit `71b363f` ("Initial project upload"). Written for: the project owner (M.Tech supervisor/viva preparation and the owner's own go/no-go decision).

Companion file: `docs/FINAL_PROJECT_READINESS_CHECKLIST.md` (one line per check). Raw evidence: `docs/audit_evidence/`. U1 (backend XGBoost exposure) is a separate investigation, summarised in section 17 and reported in full in `docs/sentiment/r_series/U1_BACKEND_XGBOOST_RUNTIME_EXPOSURE_REPORT.md`.

Status vocabulary used throughout: **PASS**, **FAIL**, **SKIPPED**, **BLOCKED**, **NOT RUN**, **ENVIRONMENT FAILURE**, **NATIVE PROCESS CRASH**. Skipped and unrun tests are never counted as passed. "OBSERVED" means seen in this audit's own output; "DOCUMENTED" means taken from a project document and not re-verified here; "INFERENCE" is labelled as such.

---

## 1. Executive summary

**Overall readiness: CONDITIONALLY READY for the M.Tech demonstration and viva (offline / demo mode, with the disclosed limitations); NOT production-ready, and not claimed to be.**

What is established by this audit's own evidence (OBSERVED):

- All 38 phase-level deliverables (Phases 0-25 and 28-36, plus the three un-numbered phases; there is no Phase 26/27 by design) have implementation anchors present in the repository; 36 of 38 also have a completion report (Phases 0 and 1 have none; their evidence is code and the initial migration).
- Frontend: `tsc -b` 0 errors; `oxlint` 0 errors / 8 warnings; production build succeeds; 279 unit tests pass; 200 of 200 mutation checks detected; the committed `frontend/src/types/api.ts` is byte-identical to a fresh `app.openapi()` dump (0 differing lines).
- Backend, database-free and sealed: **4,010 passed, 1 failed, 19 skipped**, plus **136 passed** in the isolated `db`+`ingestion` suites (`neondb_test` only), across `core`, `security`, `data`, `pipeline`, `scripts`, 7 database-free agent test files, the sentiment API test file and the guarded `tests/training` suite (796 passed, 2 skipped, exit 0, no native crash, R4 guard active).
- Migrations: one root, one head (`f7a2d4b6c810`); ORM and migrations define the same 22 tables; the isolated test database is at head.
- Security scan: no real credential in any tracked or untracked non-ignored file; `.env` and raw data are git-ignored; no PII in demo data.
- Sentiment: production remains `user_text_rules_v1`; both Transformer flags default and ship `false`; Horizon is a registered **research-only** candidate.
- U1 classification stays exactly: **No exposure observed in tested imports.** It is not upgraded to "safe".

What is NOT established (read before relying on this audit):

1. **The database-backed API suite (about 639 tests: the stopped invocation selected 775, which included the 136 `db`/`ingestion` tests that did complete) was NOT completed.** I stopped it after 120 tests (119 passed, 1 failed) because its fixture runs the application lifespan, which calls `warm_model_caches` - something the U1 restrictions in the audit brief say not to execute (section 2.3). The remaining ~519 API tests are **NOT RUN** in this audit. This is the single largest gap; it needs an explicit owner decision (section 20).
2. 169 database-signal agent tests (8 files) are **NOT RUN** (the "never run the `agents` directory" rule).
3. The one backend failure (`test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold`) is a pre-existing, previously reported false positive and was not touched.
4. No browser-based end-to-end test was run; `npm audit` / OSV were not run (no network use).

Top findings (full register in section 19): the AutoGen debate is built and tested but **not wired into the live pipeline** (disclosed in the project's own documents); the **full canonical disclaimer is never rendered by the frontend**; the risk model has modest skill (macro-F1 0.41, chance 0.25) and the market models do not beat a naive forecast; **all work since the initial commit is uncommitted**; several living documents are stale.

---

## 2. Method, authority and safeguards

### 2.1 Document authority

`CLAUDE.md` and `docs/PROJECT_PLAN.md` win over `docs/MASTER_PROMPT.md` on architecture (decision of 2026-09-13, recorded in `docs/DECISIONS.md`); `docs/BUILD_PLAN.md` is the reconciled phase plan; `docs/MEMORY.md` is the declared current-state record, `reports/` the history. Where code and a document disagreed I recorded the disagreement instead of picking silently (`docs/RULES.md` Rule 29).

### 2.2 Safeguards applied (all OBSERVED)

| Safeguard | How it was kept |
|---|---|
| Never touch development `neondb` | Not accessed. The only database contact was `neondb_test`, through `scripts/run_isolated_db_tests.py` (it refuses anything but `neondb_test` on the expected host, forces both URLs to the test URL, deselects the `real_*` development-database tests). |
| No plain DB-backed pytest | Every other run used a **sealed environment**: `DATABASE_URL`, `TEST_DATABASE_URL`, `GEMINI_API_KEY`, `PROTECTED_DATA_KEYS` set to empty strings (they override `.env` in the application's Settings) plus the Python network guard (0 external connection/lookup attempts in every run). The network guard alone would not stop `libpq`; the empty URLs are the stronger control. |
| No commit/push, no cleanup/reset | None performed. |
| No `.venv` / dependency / model / driver / GPU change | None. `pip freeze` unchanged; artifact hashes recorded read-only (`audit_evidence/artifact_hashes.tsv`). |
| Horizon stays research-only, flags false | Verified (section 12). |
| Guard preserved, not expanded | `tests/training/{nvidia_dll_guard,conftest,test_nvidia_dll_guard}.py` untouched (hashes in the before/after manifest). |
| Gemini not called | The key was blanked in every run; the live-Gemini tests skip. |

### 2.3 A restriction conflict I found, and what I did about it

The brief tells me to run the isolated database runner "only if essential", and the U1 restrictions say not to execute `warm_model_caches`, XGBoost fit/predict or served requests. The API suite's fixture (`tests/backend/api/conftest.py:114`, `with TestClient(app)`) starts the application lifespan, so running it executes `warm_model_caches` and in-process requests. I started that suite before checking the fixture; once I saw it I **stopped it** (about 19 minutes in, 120 of ~639 API tests executed, `neondb_test` only, no development database, Gemini blanked). So the deferred item "`warm_model_caches`" was in fact executed, inside tests, for those 19 minutes. This does not change U1's classification (U1 is a separate import-level investigation and its evidence is untouched), but I am disclosing it plainly. After that I ran only the two DB suites that never import the app (`db`, `ingestion`).

Two further notes on the same restriction: (a) the guarded `tests/training` suite necessarily fits and predicts with XGBoost - the brief asked for that suite explicitly, so I read the XGBoost restriction as applying to U1's own deferred experiments, not to the existing suites; (b) several sealed suites (`security`, `scripts`) make in-process requests through a test client without starting any server.

### 2.4 Change control

Baseline recorded before any audit edit: `docs/audit_evidence/git_status_before.txt` (299 entries) and a SHA-256 manifest of every modified/untracked file (`manifest_before.tsv`, 785 files). Section 22 compares them with the end state.

---

## 3. Repository inventory and Git integrity

| Item | Result |
|---|---|
| Branch / commits | `master`; 1 commit (`71b363f Initial project upload`); no stash |
| `git fsck --no-dangling` | clean (no errors) |
| Tracked files | 441; none over 5 MB; no `.env`, no raw dataset, no model weights (`.pkl`/`.keras`/`.safetensors` are ignored) |
| Working tree at start of audit | 299 entries: 78 modified, 221 untracked (+ the `docs/audit_evidence/` folder created by this audit) |
| `.gitignore` | ignores `.env`, `datasets/raw/*`, `models/sentiment_pretrained/`, `frontend/dist`, `frontend/node_modules`; the older note in `docs/MEMORY.md` that `datasets/raw` is not ignored is **stale** |
| Version-control hygiene | **All work after the initial upload is uncommitted** (sentiment phase, household phases' later edits, demo data, R1-R4, U1). A disk failure would lose it; nothing is committed because the brief forbids it. |

Test and source inventory: 182 test files, 4,983 collected tests (OBSERVED, collection only): `backend/data` 1,513, `backend/core` 1,210, `training` 798, `backend/api` 656, `backend/scripts` 264, `backend/agents` 232, `backend/security` 147, `backend/db` 132, `backend/pipeline` 31. Frontend: 154 TypeScript/TSX files, 19 pages.

---

## 4. Phases 0-36 - implementation evidence

Method: for each phase, the completion report in `reports/` exists and the main implementation anchors (files named below) exist on disk. This establishes **presence and traceability**, not behavioural correctness (that is the tests' job, sections 15 and 19). `TASKS.md` marks every phase complete; there is no Phase 26/27 report by design (documented).

| Phase | Report | Anchors present |
|---|---|---|
| 0 Foundation | none | `pyproject.toml`, `config/settings.py`, `api/main.py` (3/3) |
| 1 Initial schema | none | `db/models.py`, `alembic/versions` root `14ad3e0629d1` (2/2) |
| 2 Data quality | yes | `data/quality.py`, `data/ingestion.py` |
| 3 Leakage audit | yes | `data/preprocessing.py` |
| 4 Risk classification | yes | `training/risk/train.py`, `models/risk/rf_v1.pkl` |
| 5 Expense + behaviour | yes | `training/expense`, `training/behaviour`, both model files |
| 6 Market analysis | yes | `training/market`, `models/market/*.keras` |
| 7 Goal engine | yes | `core/goals.py` |
| 8 Portfolio optimisation | yes | `core/optimizer.py`, `training/portfolio`, `models/portfolio/*.json` |
| 9 Compliance | yes | `core/compliance.py`, `config/compliance_rules.yaml` |
| 10 Agent state / nodes | yes | `agents/state.py`, `agents/nodes.py` |
| 11 LangGraph | yes | `agents/graph.py` |
| 12 AutoGen debate | yes | `agents/debate.py` (built; **not wired live**, section 11) |
| 13 Gemini explanation | yes | `agents/explanation.py` |
| 14 Recommendation | yes | `core/recommendation.py`, `agents/recommendation.py` |
| 15 FastAPI | yes | `api/main.py`, routers, `sse.py`, `lifespan.py` |
| 16-18 React shell and pages | yes | shell, providers, 9 analysis pages |
| 19 Final evaluation | yes | (evaluation report) |
| 20-25 Login, create user, onboarding, persistence, demo account, final UX | yes | pages and `demo-customer.ts` |
| Demo-data, Live-analysis-flow, Post-login-flow (un-numbered) | yes | `demo_data/`, `analysis_service.py` |
| 28 Financial input / savings-first | yes | |
| 29 Final integration | yes | |
| 30 Analytics graphs | yes | `components/charts` |
| 31 Demo readiness | yes | `final_demo_script.md`, `final_viva_talking_points.md` |
| 32-36 Household (identity, records, aggregation, metadata, goals) | yes | household routers/services, `core/household_finance.py`, migrations |

Extensions after Phase 36 (not numbered phases; documented in `TASKS.md`/ADRs): individual+family demo (ADR-036), synthetic ML dataset (ADR-039), demo dataset package (ADR-038), the sentiment programme (ADR-043 to ADR-056) and R1-R4/U1. One tracked item is **explicitly unfinished**: the backend part of the plain-language explanation enhancement (ADR-037) - `TASKS.md` leaves it unchecked.

---

## 5. Backend architecture and APIs

- **Surface (OBSERVED, `app.openapi()` in a sealed short process, no server, lifespan not started):** 39 paths, 58 operations, 112 schemas. By prefix: `/api/households` 27, `/api/profiles` 21, `/api/analysis` 3, `/api/demo` 2, `/api/health`, `/api/qa`, `/api/questionnaire`, `/api/scenarios`, `/api/sentiment-model` 1 each.
- **Identity:** 34 operations take the caller in `X-Customer-Id`; 13 carry a customer/profile/household id in the path or query; 11 take none (health, questionnaire, demo, and similar). This is **data-scoping, not authorization** - disclosed (`docs/SECURITY.md` section 6, ADR-020).
- **Layering (static):** routers import services and schemas; no router imports numpy/pandas/sklearn; the only financial arithmetic sits in `core/`. `agents/graph.py` documents that it holds no financial logic.
- **Entry point:** `api/main.py:38` calls `get_settings()` at import (reads `.env`). That is normal for the app, but it is why U1 could not import it.
- **Startup:** `lifespan.warm_model_caches` loads the risk preprocessor + random forest, the behaviour isolation forest and the FAR-Trans tables, and fails closed if an artifact is missing (code-read; **not executed here**, section 2.3).
- **Contract drift:** none (section 6).
- **Errors:** RFC 7807 handlers in `api/errors.py` (code-read; behaviour covered by API tests that were not completed - section 15).

---

## 6. Frontend architecture and workflows

| Check | Result |
|---|---|
| `npx tsc -b` | **PASS**, exit 0, 0 errors |
| `npx oxlint` | **PASS**, 0 errors, 8 warnings (the documented baseline: fast-refresh/export and one set-state-in-effect warnings in shadcn primitives) |
| `npm run build` | **PASS**; JS 1,353.30 kB (gzip 392.03 kB), CSS 107.22 kB; single chunk (accepted; `docs/MEMORY.md` still quotes the older 1,094.83 kB) |
| `npm test` | **PASS** 279 / 279 |
| `npm run typecheck:tests` | **PASS** |
| `npm run test:mutations` | **PASS** 200 of 200 mutations detected |
| Generated types current | **PASS** - fresh `app.openapi()` -> `openapi-typescript` equals committed `src/types/api.ts` (0 diff lines) |
| No financial arithmetic in React (heuristic scan of pages/components/lib/hooks) | **PASS** - only display scaling (`probability * 100` for progress bars, percent formatting in `lib/format.ts`) |
| No hard-coded customer id; no customer switching UI | **PASS** - `setProfileId` is called only on login/create-user/logout |
| No `any` in non-generated TypeScript | **PASS** (the only match is a comment) |
| Browser end-to-end / visual testing | **NOT RUN** in this audit (no browser tool used). Earlier browser verification for the sentiment pages is DOCUMENTED (ADR-046); chart drawing and dark-mode contrast are documented as unverified. |

Workflows by source evidence (not re-executed): login -> create user -> onboarding (goals, questionnaire) -> profile -> financial inputs -> analysis (approved / savings-first / rejected / pending) -> dashboard, risk, goals, portfolio, scenarios, why-this-recommendation, agent activity, behaviour & sentiment, household (profile card, tabs), security status.

---

## 7. Database models, migrations and isolation

| Check | Result |
|---|---|
| Migration chain (static parse) | 11 migrations, 1 root, **1 head `f7a2d4b6c810`**, no dangling parent |
| Test database revision (read-only `alembic current` via the runner) | `f7a2d4b6c810 (head)` - matches |
| ORM vs migrations | 22 tables in both; **no drift** |
| Owner keys | every table has `customer_id`/`household_id`/`profile_id` except `customers`, `households` (the entities), `market_data` (global) and `audit_ledger_events` (ledger) |
| Runner preflight / identity | target `neondb_test`; application settings resolve to the same host and database; read-only connection check returned `neondb_test` |
| `tests/backend/db` + `tests/backend/data/test_ingestion.py` via the isolated runner | **PASS - 136 passed in 13 min 9 s, exit 0** (`db_isolated_run_db_ingestion.txt`); 0 blocked-engine attempts |
| API-layer isolation tests (customer scoping, household membership, 404-not-403) | **NOT RUN to completion** (they are in the stopped API suite) - DOCUMENTED as passing in earlier phases |
| Past incident | DOCUMENTED (`docs/MEMORY.md`, 2026-11-04): plain `pytest` on `agents` opened sessions on development `neondb`; modification UNKNOWN. This audit did not repeat it. |

---

## 8. Dataset ingestion and data-quality pipelines

- Raw data: FAR-Trans (7 CSVs) and 2 Kaggle CSVs under `datasets/raw/`, git-ignored, last modified 2026-09-13. SHA-256 baseline recorded in `audit_evidence/artifact_hashes.tsv`. (A recorded Phase 5 baseline is referred to in `docs/MEMORY.md` but I could not find the hash list in the documents searched, so **this audit establishes the baseline; it cannot confirm "unchanged since Phase 5" by hash**.)
- Data-quality / ingestion code: `data/quality.py`, `data/ingestion.py`, `data/preprocessing.py`; `tests/backend/data` (1,513 tests) - sealed run **1,508 passed, 1 failed** (the pre-existing GDELT scaffold false positive, F-05); ingestion into the test database is in the `db`+`ingestion` run (section 15).
- Leakage controls: Phase 3 audit report present; `random_state=42` throughout the recorded metrics; ML rules (`.claude/rules/ml.md`) require walk-forward with embargo (recorded: 504-day initial train, 5-day embargo, 63-day test windows for market models).
- GDELT research acquisition is out of the served path and excluded from the training-data guard by design (ADR-045).

---

## 9. ML training, artifacts, evaluation and inference

| Family | Artifact(s) | Recorded result (`models/metrics.json`, DOCUMENTED; not retrained) |
|---|---|---|
| Risk (4-class) | `rf_v1.pkl` (served), `xgb_v1.pkl`, `logreg_v1.pkl`, `mlp_v1.keras`, `preprocessor_v1.pkl` | 5-fold macro-F1: RF 0.4075 +- 0.0048 (best), XGBoost 0.3969, MLP 0.3545, LogReg 0.3527; population 21,528; chance for 4 balanced classes is 0.25 |
| Behaviour | `iforest_v1.pkl`, thresholds | Isolation Forest, contamination 0.05; 6,397 anomalies flagged (5.0% of the panel, i.e. the contamination setting, not an accuracy figure) |
| Expense segmentation | k-means + scaler | silhouette 0.458 at k=2 (0.29 at k=3/4); FAR-Trans customers can never get an expense persona (structural, documented) |
| Market | ARIMA/LSTM/GRU/GARCH per instrument | ARIMA order (0,0,0) in every window for ^IXIC, ^NDX, QQQ (no structure found); naive baseline reported; Diebold-Mariano comparisons in the Phase 6 report |
| Portfolio | MVO / HRP / 1-N configs, Ledoit-Wolf, backtest | deterministic, config files only |

Findings: artifacts exist for every family, load paths are cached and read-only (code-read), nothing trains in a request (`training/` only; rule enforced by tests in `tests/backend`). **Skill is modest and honestly reported** (F-03). Inference at runtime is deterministic Python plus the cached sklearn artifacts; the serving path does not import XGBoost (section 17). The live-inference path (`warm_model_caches`, `/api/analysis`) was **NOT RUN** by me.

---

## 10. Risk modelling and financial safety

- Backend is the sole numerical authority (`CLAUDE.md` section 10): confirmed structurally - frontend arithmetic scan (section 6), Gemini receives a computed dict and its output is validated (`agents/explanation.py`), AutoGen is not in the pipeline.
- Compliance is binding and fail-closed: `config/compliance_rules.yaml` has 5 rules (`weights_sum_to_one`, `no_negative_weights`, `qqq_within_risk_band`, `single_asset_cap`, `emergency_fund_savings_first`), each referenced by tests (16 / 8 / 13 / 14 / 10 occurrences). Core suite **1,198 passed** (includes the compliance, goals, optimizer and household-finance engines).
- Precedence Compliance > Savings-first > Risk > Goal > Market is documented and implemented in `core/recommendation.py`; routing has no REJECT retry loop by design.
- Missing data: null + `*_unavailable_reason`, never zero (tests in `core`); NULL-vs-zero behaviour pinned for the household summary.
- Household figures never reach `POST /api/analysis` (Phase 34-36 rules; `core` tests).
- Residual: the risk classifier is weak (F-03); the app mitigates by confidence routing (threshold 0.50) to an information-request state rather than guessing.

---

## 11. LangGraph and AutoGen

- **LangGraph (OBSERVED, code and tests):** 14 nodes, deterministic routing; `_safe_call` turns exceptions into structured failures; graph construction/routing/state tests (7 sealed agent files) **59 passed, 4 skipped** (the 4 are live-Gemini tests, skipped because the key was blanked).
- **AutoGen: implemented and unit-tested standalone, NOT part of the live analysis pipeline.** `analysis_service` runs the graph, then `recommendation_engine_node`, then `explanation_node`; nothing in `backend/wealthpilot` calls `run_strategy_debate` (only its docstring mentions it, and three test files call it). This is disclosed in `docs/ARCHITECTURE.md` section 11, `reports/phase19` ("NOT WIRED (live)"), `reports/phase31`, `docs/final_demo_script.md` and `docs/final_viva_talking_points.md`. Consequence for the viva: do **not** describe a live multi-agent debate; describe it as a built, tested, deliberately unwired component. (F-01)
- Gemini: structured-output validation, one regeneration, templated fallback; the account's quota has been exhausted at times, so the templated explanation is the common demo path (DOCUMENTED).
- Agent test files with database signals (8 files, 169 tests): **NOT RUN**.

---

## 12. Sentiment production baseline and Horizon isolation

| Check | Result |
|---|---|
| Production method | `user_text_rules_v1` (`api/schemas.py:1368`, literal type) - **PASS** |
| Flags default | `sentiment_model_enabled=False`, `sentiment_transformers_enabled=False`, `demo_mode_enabled=False` in `Settings`; same in `.env.example` - **PASS** |
| Actual `.env` flags | checked by `test_sentiment_final_state.py` (it reads the real `.env`; I did not) - core suite passed - **PASS** |
| Horizon | registered as the `general` **research** candidate (`core/sentiment/registry.py`); `production_activation: not_activated`; financial slot empty - **PASS** (core tests: slots, API, candidate reviews, final state) |
| Weights | local, git-ignored (`models/sentiment_pretrained/`), SHA-256 manifest; opt-in real-weights smoke test **SKIPPED** (9 skips, env switch off) - not run in this audit |
| Sentiment never affects risk/goals/portfolio/compliance | pinned by tests (core + `test_personalized_insights.py` 8 passed) |
| Unresolved governance items | D20 rejected; A3.3/A3.5 as recorded; E3 and F1 unresolved; B2.2 not started (DOCUMENTED) |

---

## 13. Security, privacy and credential handling

| Check | Result |
|---|---|
| Secret scan over 1,147 tracked + untracked non-ignored files (Google, OpenAI/Anthropic, GitHub, AWS, Slack tokens, PEM keys, URL-embedded passwords, key assignments) | **PASS** - 3 pattern hits, all verified placeholders/test fakes (`sk-ant-...` made-up test key, `fakeuser` test URLs, `.env.example` placeholder) |
| `.env` | git-ignored, untracked, **not read by me**; `.env.example` and `frontend/.env.example` only |
| PII in demo data | **PASS** - no email addresses; the one 10-digit match is part of a SHA-256 value |
| `neondb` / `neondb_test` access | only `neondb_test` via the runner |
| Security suite | **147 passed** (sealed): encryption envelope, audit ledger, protected notes, key handling |
| Customer isolation | data-scoping only, **no per-account authorization** (disclosed); prototype auth is client-side (`localStorage`), by design (ADR-020) |
| Chain-of-thought / raw exception exposure | prevented by design (RFC 7807, no reasoning field in SSE `NodeEvent`); behaviour covered by API tests that were not completed |
| Prompt-injection tests | present in `tests/backend/agents/test_explanation.py` - part of the 8 agent files **NOT RUN** (the Gemini-free validation paths are partly covered by `test_explanation_node.py`, which passed) |
| Dependency vulnerability audit (OSV, `npm audit`) | **NOT RUN** (network); the transformers/torch advisory history is DOCUMENTED with owner decisions |

---

## 14. Dependency integrity

- `pip check`: **No broken requirements found.**
- `wealthpilot` declares 21 exact pins; **all 21 match the installed versions**; `xgboost==2.1.2`, `shap==0.46.0`.
- `pip freeze` is identical to the R3/R4 reference; no dependency was changed by this audit.
- `npm ls --depth=0`: no missing/invalid packages.
- Approved-stack rule (`CLAUDE.md` section 5): the project also has `torch`, `transformers`, `safetensors` and `tensorflow` installed - the Transformer set was approved by the owner as research-only (ADR-053/055/056); the backend serving path imports none of them (U1).
- `pyautogen` pulls `flaml`, which imports `xgboost` at import (U1 latent path).

---

## 15. Test coverage and actual execution

All sealed runs: environment `DATABASE_URL`, `TEST_DATABASE_URL`, `GEMINI_API_KEY`, `PROTECTED_DATA_KEYS` empty; network guard on (0 external attempts). Commands and logs: `docs/audit_evidence/run_sealed_suites.sh`, `sealed_*.txt`.

| Run | Command (abridged) | Class | Result |
|---|---|---|---|
| `tests/backend/core` | `pytest -p netguard tests/backend/core` | **PASS** | 1,198 passed, 12 skipped |
| `tests/backend/security` | | **PASS** | 147 passed |
| `tests/backend/data` (excl. `test_ingestion.py`) | | **FAIL** (1) | 1,508 passed, 1 failed (F-05) |
| `tests/backend/pipeline` | | **PASS** | 31 passed |
| `tests/backend/scripts` | | **PASS** | 263 passed, 1 skipped |
| 7 database-free agent files | `test_graph_construction/_routing`, `test_state`, `test_debate_node`, `test_explanation_node`, both `*_gemini_client` | **PASS** | 59 passed, 4 skipped (live Gemini, key blanked) |
| `tests/backend/api/test_personalized_insights.py` | | **PASS** | 8 passed |
| `tests/training` (guarded) | `pytest -p netguard tests/training` | **PASS** | 796 passed, 2 skipped (symlink privilege), exit 0, no fatal exception; header `nvidia_dll_guard: active (pinned)` |
| Isolated `api` suite (~639 tests; the stopped invocation selected 775 with db + ingestion) | `run_isolated_db_tests.py` (stopped by me, section 2.3) | **NOT RUN** beyond 120 tests | 119 passed, 1 failed (below), ~519 not executed |
| Isolated `db` + `ingestion` (136 collected) | `run_isolated_db_tests.py --suite db --suite ingestion` | **PASS** | **136 passed in 13 min 9 s, exit 0**; `neondb_test` only; "blocked engine attempts = 0"; development-database tests deselected |
| 8 DB-signal agent files | | **NOT RUN** | 169 tests |
| `test_health.py`, `test_lifespan.py` | | **NOT RUN** | both run the app lifespan (`warm_model_caches`) |
| Frontend | see section 6 | **PASS** | tsc / oxlint / build / 279 unit / 200 mutations |
| Browser E2E | | **NOT RUN** | |

Totals of the sealed backend/training runs: **4,010 passed, 1 failed, 19 skipped**, plus the 120 partial API tests (119 passed, 1 failed). With the 136 passing isolated `db`/`ingestion` tests the audit executed about 4,290 of the 4,983 collected tests; **about 697 are NOT RUN** (~519 API tests, 169 database-signal agent tests, and the ~9 `test_health`/`test_lifespan` tests that start the lifespan).

**The one API failure** (`test_analysis.py::test_approved_analysis_returns_recommendation_and_explanation`, `assert body["explanation"]["disclaimer"]` -> `None`): classified **FAIL, explained by the auditor's own environment change**. With `GEMINI_API_KEY` blank, `run_explanation` returns `status="failed", output=None` ("no Gemini API key supplied") and the API maps `output.get("disclaimer")` -> `None`; with a configured key (even a quota-exhausted one) the templated fallback path sets the canonical disclaimer. I did not re-run it with a key (that would call an external service). Two lessons: the test is not hermetic with respect to the key, and in a no-key deployment the explanation block carries no disclaimer (F-02, F-11). I did not change the test or the code.

Documented history for comparison (DOCUMENTED, not re-verified): a full isolated run of 1,326 passed / 1 skipped (2 h 9 min, September); Stage A of the sentiment work recorded 4,294 passed / 1 failed / 9 skipped across nine directory runs. Those figures are the evidence that the API suite passed at those dates; this audit cannot re-confirm it.

---

## 16. Documentation completeness and drift

Required documents all exist: `CLAUDE.md`, `.claude/rules/*.md` (6), `docs/{PRD,ARCHITECTURE,DESIGN,SECURITY,TEST_PLAN,MEMORY,DECISIONS (56 ADRs),RULES,PROJECT_PLAN,MASTER_PROMPT,BUILD_PLAN}.md`, `TASKS.md`, `reports/` (108 files), demo/viva set (`demo_runbook.md`, `final_demo_script.md`, `final_viva_talking_points.md`, `reports/final_viva_facts.md`), and the sentiment set (13 reports plus R1-R4, U1).

Drift found (F-04, none silently fixed):

| Document | Stale statement |
|---|---|
| `README.md` "Status" | "All planned phases through Phase 31" - the project is at Phase 36 plus extensions |
| `docs/MEMORY.md` "Last Verified State" | "verified ... at the completion of Phase 32" |
| `docs/MEMORY.md` "Current Test Status" | 1,326 passed / 1,260 passed; the suite now collects 4,983 |
| `docs/MEMORY.md` "Current Build Status" | bundle 1,094.83 kB; now 1,353.30 kB |
| `docs/MEMORY.md` "Current Blockers: None" | the known GDELT scaffold failure and the machine-specific native crash are tracked elsewhere only |
| `docs/MEMORY.md` `.gitignore` finding | `datasets/raw` is now ignored |
| `TASKS.md` | "Current task: None; Phase 36 most recent" - it does not list the sentiment programme, R1-R4 or U1; one box (ADR-037 backend) is intentionally unchecked |
| `reports/final_viva_facts.md` | quotes 697/763 tests; superseded by a note inside the file |
| `CLAUDE.md` section 19 | "up to 3 live-Gemini tests skip" - 4 skip when no key is set (2 debate + 2 explanation) |

Added by this audit: this file, the checklist, `docs/audit_evidence/`, and the U1 and R4 reports earlier in the session.

---

## 17. U1 - backend XGBoost / NVIDIA DLL exposure (separate investigation)

Source of truth: `docs/sentiment/r_series/U1_BACKEND_XGBOOST_RUNTIME_EXPOSURE_REPORT.md` (authoritative; not re-run here).

**Exact classification: No exposure observed in tested imports.** Not "safe"; not "confirmed exposure"; the driver defect is not fixed.

- 37 fresh-subprocess import runs, all PASS, exit 0, no crash; the backend's served import closure does not import `xgboost`; no run mapped `nvdxgdmal64.dll` or any NVIDIA module (including nine where `xgboost.dll` was loaded); poller sensitivity control 40 of 40.
- Latent path: `import autogen` / `import flaml` imports `xgboost` (`autogen/oai/client.py:9` -> `flaml/__init__.py:5` -> `flaml/automl/ml.py:12`), reachable only through `run_strategy_debate`, which nothing calls.
- **Deferred - NOT RUN, unverified runtime investigations:** `sys.modules` after a served request; DLL state after a served request; live backend behaviour; `warm_model_caches` as an investigation; any use of XGBoost (fit/predict/DMatrix/Booster) in a backend process; the AutoGen debate execution path; `wealthpilot.api.main` import (BLOCKED - reads `.env` at import).
- **This audit's relation to U1:** I did not run any U1 deferred experiment. Two things happened inside ordinary test suites and are disclosed in section 2.3: the guarded `tests/training` suite fits/predicts with XGBoost (by design, as the brief required), and the stopped API suite started the app lifespan for about 19 minutes. Neither involved instrumentation of the backend's DLL state, so **neither upgrades or downgrades the U1 classification**.

---

## 18. R4 mitigation status

- `tests/training/nvidia_dll_guard.py`, `conftest.py`, `test_nvidia_dll_guard.py` are present, untouched (hashes unchanged in the before/after manifest), test-only; no import from `backend/`, `scripts/`, `training/`, `config/` or `models/` (enforced by a test in the guard's own suite).
- This audit's guarded whole-suite run: **796 passed, 2 skipped, exit 0, no fatal exception**, header `nvidia_dll_guard: active (pinned)` for the single NVIDIA driver package on this machine. R4 recorded guard-off 4 of 5 whole-suite runs crashing with `0xC0000005` and guard-on 0 of 5; with this run, **6 consecutive guarded whole-suite runs have completed without a native crash** (5 R4 + 1 audit). No unguarded run was repeated here.
- Limits (unchanged): a workaround for a driver defect, not a fix; protects only runs that collect `tests/training/`; inactive if several NVIDIA driver packages are installed unless the path is named; no in-code signature check; machine-specific.
- Not touched: XGBoost, the driver, GPU preference, the guard's scope.

---

## 19. Findings register

| ID | Severity | Finding | Evidence | Status / recommendation |
|---|---|---|---|---|
| F-00 | **High (process)** | The audit executed ~19 min of the isolated API suite before noticing its fixture runs `warm_model_caches` (U1 restriction); stopped at 120 of ~639 API tests | section 2.3; `db_isolated_run_api_partial_STOPPED.txt` | Disclosed. API suite needs a decision (section 20) |
| F-01 | Medium | AutoGen debate is not wired into the live pipeline | `analysis_service.py`; no caller of `run_strategy_debate`; docs disclose | Disclosed in project docs; keep viva wording accurate, or wire it under a new ADR |
| F-02 | Medium | The full canonical disclaimer ("Disclaimer to Carry Through the System", `PROJECT_PLAN.md`) is never rendered by the frontend (no `disclaimer` use in `src/`); only partial wording on landing/About/Financial Health; with no Gemini key `explanation.disclaimer` is null | grep of `frontend/src`; `analysis_service.py:630`; failing API test | Owner decision: add a static footer/notice (small UI change, not made here) |
| F-03 | Medium | Risk model skill is modest (macro-F1 0.41 vs chance 0.25); market models do not beat naive (ARIMA (0,0,0)); expense persona unavailable for FAR-Trans customers | `models/metrics.json`; reports 4 and 6 | Honestly documented; present as a methodology/pipeline project, not a predictive-accuracy claim |
| F-04 | Low-Medium | Living documents are stale (README phase, MEMORY test counts/bundle/last-verified/blockers, TASKS post-36 work) | section 16 | Refresh `docs/MEMORY.md`, `TASKS.md`, README (documentation only) |
| F-05 | Low | `test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold` fails: its text search treats `from wealthpilot.core.sentiment import adapter` in `personalized_insight_service.py` as `import sentiment` | `sealed_data.txt` | Pre-existing, previously designated report-only; not modified. Fix = tighten the test's pattern (owner approval) |
| F-06 | Medium | All work since the initial commit is uncommitted; trained `.pkl`/`.keras` artifacts are git-ignored, so a clean clone cannot run analysis without the local `models/` folder | git status; `.gitignore` | Owner decision on commit strategy and artifact delivery before submission |
| F-07 | Low | Plain-language explanation backend (ADR-037) not done | `TASKS.md` | Intentional; leave or schedule |
| F-08 | Info | Prototype authentication / no server-side authorization | `docs/SECURITY.md` sections 6-7 | Disclosed; state in viva |
| F-09 | Low | Phase 33 record endpoints return 500 (not 422) for explicit `null` and non-finite amounts on PUT | `docs/MEMORY.md` (documented in Phase 36) | **Not re-verified** here (API suite not run) |
| F-10 | Medium | Machine-specific NVIDIA/XGBoost native crash; test-only guard in place; backend exposure not observed in imports, runtime unverified | sections 17-18 | Owner decisions in section 20 |
| F-11 | Low | `test_analysis` explanation test is not hermetic with respect to `GEMINI_API_KEY` | section 15 | Make the test set its own key stub or skip when none (owner approval) |
| F-12 | Low | Frontend bundle is a single 1.35 MB chunk | build output | Accepted characteristic |
| F-13 | Info | Gemini quota intermittently exhausted: demos show the templated explanation | `docs/MEMORY.md` | Prepare to say so; consider a demo key with quota |
| F-14 | Low | OSV / `npm audit` / browser E2E not run | - | Run when network use and a browser tool are authorized |
| F-15 | Info | Phases 0 and 1 have no completion report | section 4 | Evidence is code + root migration |

No code, test, dependency, model or documentation file other than the new audit files was modified to fix any finding (the small-fix allowance was not used: every candidate needed an owner decision or touched a designated report-only item).

---

## 20. Remaining approval-dependent decisions

1. **Authorize (or not) a full isolated run of the ~639-test API suite**, knowing it starts the app lifespan (`warm_model_caches`) and makes in-process requests. Without it, API behaviour is verified only by the September/Stage A history, not by this audit. Estimated 1.5-2 hours; blank the Gemini key or accept templated explanations.
2. Authorize the 8 database-signal agent test files (or confirm they stay excluded).
3. U1 follow-up: a separately approved, isolated runtime investigation (XGBoost use in a server-like process; `sys.modules`/DLL state after warming and a served request).
4. Native crash options (none applied): driver update/rollback; force the Intel GPU for `python.exe`; CPU-only XGBoost wheel (dependency change, `CLAUDE.md` section 5).
5. Whether to wire the AutoGen debate into the live flow (new ADR) or keep it standalone.
6. Whether to render the canonical disclaimer in the frontend (F-02).
7. Commit strategy and delivery of `models/` for the submission copy (F-06).
8. Documentation refresh (F-04) and the GDELT scaffold test pattern (F-05).
9. Sentiment governance items still open: E3, F1, B2.2; Horizon remains research-only unless the owner decides otherwise (no activation was or will be done by this audit).
10. Network-dependent checks: OSV/`npm audit`, live Gemini validation, browser E2E.

---

## 21. M.Tech demonstration readiness

**Verdict: ready to demonstrate, provided the presenter works inside the disclosed boundaries; two things should be done before the viva (re-run the API suite with authorization; refresh the stale documents).**

What demonstrates well (evidence-backed): the deterministic pipeline and its four terminal states (approved, savings-first, rejected, pending); compliance as a hard veto; household identity -> records -> read-only summary -> goals as stored facts; the per-page "never hide missing data" behaviour; the sentiment programme as a governed, research-only extension; the security prototype (encrypted notes, audit ledger); a clean frontend build with 279 unit tests and 200/200 mutations.

What to say plainly in the viva: risk-model skill is modest and why; the market models do not beat a naive baseline; AutoGen is built but not in the live flow; authentication is a prototype with data-scoping only; Gemini quota may force the templated explanation; the first-run dataset (FAR-Trans) is European research data; nothing here is licensed financial advice (and the full disclaimer should be visible - F-02).

Operational readiness: the demo needs the local `models/` folder, a reachable Neon database (the app uses the hosted dev database at demo time; I did not touch it), `npm run dev`/`uvicorn` started by the presenter (not by this audit), and a decision on the Gemini key. `docs/demo_runbook.md` and `docs/final_demo_script.md` exist; their AutoGen statements are accurate.

---

## 22. Change record - audit-created changes vs pre-existing work

Baseline: `docs/audit_evidence/git_status_before.txt` and `manifest_before.tsv` (taken before any audit edit). End state compared in `docs/audit_evidence/manifest_after.tsv` and `git_status_after.txt`.

### 22.1 What existed before the audit (pre-existing work - preserved, not modified)

The baseline (299 git-status entries + the empty `docs/audit_evidence/` folder created at the start; 785 individually fingerprinted modified/untracked files) already contained: the 78 modified and 221 untracked paths of the project's own earlier work (sentiment programme, household phases' later edits, demo data, documentation) **and** the deliverables of the earlier tasks in this same working session - R1-R3 edits, the R4 test-only guard (`tests/training/{nvidia_dll_guard,conftest,test_nvidia_dll_guard}.py`), the R3/R4/U1 evidence and reports. Those are pre-existing from this audit's point of view.

### 22.2 Comparison (content-level, SHA-256)

| Measure | Result |
|---|---|
| Git status entries | 300 before -> 302 after; the only difference is the two new files below (`diff git_status_before.txt git_status_after.txt`) |
| Pre-existing files whose content changed | **0** |
| Pre-existing files removed from the modified/untracked set | **0** |
| New files | 27, **all under `docs/`**: the 2 deliverables + 25 files in `docs/audit_evidence/` (logs, hashes, manifests, the sealed-run script). Created after the "after" fingerprint: `manifest_after.tsv`, `manifest_comparison.txt` |
| Changes under `backend/`, `frontend/src/`, `training/`, `models/`, `config/`, `scripts/` | **0 in each** |
| R4 guard files, U1 report, R3 report | byte-identical (hashes equal) |
| `.venv`, `package.json`/lockfiles, model artifacts, raw datasets | untouched (hash baseline recorded, not altered) |
| Commits / pushes / stashes / resets / cleans | none |

### 22.3 Audit-created changes (separate from pre-existing work)

1. `docs/FINAL_PROJECT_READINESS_AUDIT.md` (this file) and `docs/FINAL_PROJECT_READINESS_CHECKLIST.md`.
2. `docs/audit_evidence/`: `git_status_before/after.txt`, `manifest_before/after.tsv`, `manifest_comparison.txt`, `artifact_hashes.tsv`, `run_sealed_suites.sh`, `sealed_*.txt`, `fe_*.txt`, `collect_only.txt`, `db_isolated_run*.txt`.
3. Outside the repository (scratch only, not part of the project): the OpenAPI dump, the regenerated types file, the manifest scripts, in the session scratchpad.
4. Side effects outside the working tree: `frontend/dist` rewritten by `npm run build` (git-ignored); `tsc -b` build-info (ignored); rows written to **`neondb_test`** by the 136 passing DB tests and the 120 API tests I stopped (the suites use rolled-back transactions and cleanup; the stop killed one connection mid-test, and the server discards an unfinished transaction - I did not re-inspect the test database afterwards beyond the `alembic current` and runner checks); no write to the development database.

### 22.4 Operational note

I terminated the isolated API run with `Stop-Process`. The matching command-line filter also matched the three `bash` wrappers that had launched it, so those shells were ended too; no other process was touched.


---

## 23. Reproduction

```
# sealed DB-free suites (writes docs/audit_evidence/sealed_*.txt)
bash docs/audit_evidence/run_sealed_suites.sh <netguard_dir> <out_dir>
# isolated DB suites that never start the app (no lifespan)
GEMINI_API_KEY= python scripts/run_isolated_db_tests.py --suite db --suite ingestion -- -rfEs
# frontend
cd frontend && npx tsc -b && npx oxlint && npm run build && npm test && npm run typecheck:tests && npm run test:mutations
# API contract / types freshness (no server): app.openapi() -> openapi-typescript -> diff against src/types/api.ts
```
