# WealthPilot AI - Final Readiness Checklist

Date: 2026-11-10. Companion to `docs/FINAL_PROJECT_READINESS_AUDIT.md` (section numbers below refer to it). Raw evidence: `docs/audit_evidence/`.

Status vocabulary: **PASS** / **FAIL** / **SKIPPED** / **BLOCKED** / **NOT RUN** / **ENVIRONMENT FAILURE** / **NATIVE PROCESS CRASH**, plus **DOCUMENTED** (taken from a project document, not re-verified by this audit). A skipped or unrun item is never a pass.

Overall: **CONDITIONALLY READY for the M.Tech demonstration (offline/demo mode); not production.** Open items needing an owner decision are marked **DECISION**.

## A. Repository and Git integrity (audit section 3)

| # | Check | Status | Evidence |
|---|---|---|---|
| A1 | Git object integrity (`git fsck --no-dangling`) | PASS | clean output |
| A2 | No secrets, `.env`, raw datasets or model weights tracked | PASS | `git ls-files` review; 441 tracked, none over 5 MB |
| A3 | `.env`, `datasets/raw/*`, `models/sentiment_pretrained/`, `frontend/dist` ignored | PASS | `git check-ignore -v` |
| A4 | Pre-existing modified/untracked work preserved | PASS | `manifest_before.tsv` vs `manifest_after.tsv` (audit section 22) |
| A5 | Work committed to version control | FAIL (by instruction) | 78 modified + 221 untracked paths vs 1 commit; no commit allowed. **DECISION** (F-06) |
| A6 | Trained artifacts reproducible from a clean clone | FAIL | `.pkl`/`.keras` ignored; needs the local `models/` folder or retraining. **DECISION** (F-06) |

## B. Phase completion Phases 0-36 (audit section 4)

| # | Check | Status | Evidence |
|---|---|---|---|
| B1 | Every phase has implementation anchors on disk | PASS | 38 deliverables checked (script output in the audit) |
| B2 | Every phase has a completion report | PASS for 36 of 38 | Phases 0 and 1: none (F-15) |
| B3 | `TASKS.md` complete and current | FAIL (stale) | lacks post-36 sentiment work; ADR-037 backend unchecked (F-04, F-07) |
| B4 | No unauthorised next phase started | PASS | tracker: "no further phase authorised"; none created |

## C. Backend architecture and APIs (sections 5, 10)

| # | Check | Status | Evidence |
|---|---|---|---|
| C1 | OpenAPI schema builds without a server | PASS | 39 paths / 58 operations / 112 schemas |
| C2 | Layering (route -> service -> core/agents -> db) | PASS | static review; no numeric libraries in routers |
| C3 | Generated frontend types equal live OpenAPI | PASS | 0 differing lines |
| C4 | Backend core engines (goals, optimizer, compliance, recommendation, household finance, emergency fund, Monte Carlo) | PASS | `tests/backend/core` 1,198 passed, 12 skipped |
| C5 | Compliance rules each tested | PASS | 5 rules, each referenced in tests |
| C6 | RFC 7807 errors, SSE, validation, scoping behaviour (API tests) | NOT RUN (partial: 119 passed, 1 failed of ~639) | stopped by auditor (audit 2.3). **DECISION** |
| C7 | App startup / lifespan / `warm_model_caches` | NOT RUN | U1 restriction; code-read only |
| C8 | Known 500-instead-of-422 defects (Phase 33 schemas) | NOT RUN / DOCUMENTED | F-09 |
| C9 | Live Gemini explanation validated | SKIPPED | key blanked; 4 live tests skipped; quota history DOCUMENTED |

## D. Frontend (section 6)

| # | Check | Status | Evidence |
|---|---|---|---|
| D1 | `npx tsc -b` | PASS | exit 0, 0 errors (`fe_tsc.txt`) |
| D2 | `npx oxlint` | PASS | 0 errors, 8 warnings (documented baseline) |
| D3 | `npm run build` | PASS | JS 1,353.30 kB, gzip 392.03 kB |
| D4 | `npm test` | PASS | 279 / 279 |
| D5 | `npm run typecheck:tests` | PASS | exit 0 |
| D6 | `npm run test:mutations` | PASS | 200 of 200 detected |
| D7 | No financial arithmetic in React | PASS | heuristic scan; display scaling only |
| D8 | No hard-coded customer id / no switching UI / no `any` | PASS | grep scans |
| D9 | Canonical disclaimer displayed in the app | FAIL | never rendered; partial wording only (F-02). **DECISION** |
| D10 | Browser end-to-end / visual / accessibility testing | NOT RUN | DOCUMENTED earlier only |

## E. Database, migrations, isolation (section 7)

| # | Check | Status | Evidence |
|---|---|---|---|
| E1 | Single Alembic head, no dangling parent | PASS | head `f7a2d4b6c810` |
| E2 | Test database at head | PASS | `alembic current` via the runner |
| E3 | ORM equals migrations | PASS | 22 = 22 tables |
| E4 | Isolated runner target is `neondb_test` only | PASS | preflight + read-only identity check |
| E5 | Development `neondb` not accessed | PASS | by construction; no dev URL given to any run |
| E6 | `tests/backend/db` + `test_ingestion.py` through the runner | PASS | 136 passed (db + ingestion) | `db_isolated_run_db_ingestion.txt` |
| E7 | API-level customer/household isolation tests | NOT RUN (partial) | see C6 |

## F. Data and ML (sections 8, 9)

| # | Check | Status | Evidence |
|---|---|---|---|
| F1 | Data tests (quality, preprocessing, GDELT tooling) | FAIL (1 of 1,509) | 1,508 passed; F-05 false positive, pre-existing |
| F2 | Raw dataset integrity baseline | PASS (baseline recorded) / cannot confirm "unchanged since Phase 5" | `artifact_hashes.tsv` |
| F3 | Model artifacts present for all families, not modified | PASS | hashes recorded; mtimes at training dates |
| F4 | Training suite (guarded) | PASS | 796 passed, 2 skipped, exit 0 |
| F5 | Retraining | NOT RUN (forbidden) | |
| F6 | Model skill adequate | PARTIAL | risk macro-F1 0.41 (chance 0.25); market ~ naive (F-03) |
| F7 | Leakage controls (walk-forward + embargo, `random_state=42`) | PASS (DOCUMENTED + metrics) | `metrics.json` |
| F8 | Backend serving path free of XGBoost imports | PASS (imports tested) | U1 |

## G. Agents and AI (section 11)

| # | Check | Status | Evidence |
|---|---|---|---|
| G1 | LangGraph construction / routing / state | PASS | 59 passed in 7 files |
| G2 | AutoGen debate unit-tested | PASS (DOCUMENTED + node test) | `test_debate_node` passed; full `test_debate.py` NOT RUN (DB signal) |
| G3 | AutoGen wired into the live pipeline | FAIL (by design, disclosed) | F-01 |
| G4 | 8 DB-signal agent files | NOT RUN | 169 tests |
| G5 | Gemini never computes a number; structured-output validation | PASS (code-read + `test_explanation_node`) ; prompt-injection tests NOT RUN | |

## H. Sentiment production baseline and Horizon isolation (section 12)

| # | Check | Status | Evidence |
|---|---|---|---|
| H1 | Production method is `user_text_rules_v1` | PASS | schema literal + core tests |
| H2 | `SENTIMENT_MODEL_ENABLED` and `SENTIMENT_TRANSFORMERS_ENABLED` false | PASS | Settings defaults, `.env.example`, `test_sentiment_final_state` |
| H3 | Horizon registered, research-only, not activated | PASS | registry + slot tests |
| H4 | Real-weights smoke test | SKIPPED | opt-in switch off (9 skips) |
| H5 | Sentiment never changes risk/goals/portfolio/compliance | PASS | core tests; `test_personalized_insights` 8 passed |
| H6 | Open governance items (E3, F1, B2.2, D20) | DOCUMENTED / unresolved | **DECISION** |

## I. Security and privacy (section 13)

| # | Check | Status | Evidence |
|---|---|---|---|
| I1 | Secret scan | PASS | 3 hits, all verified fakes/placeholders |
| I2 | No PII in demo data | PASS | |
| I3 | Security test suite | PASS | 147 passed |
| I4 | No raw exception / chain-of-thought to the client | PASS (DOCUMENTED design) / API tests NOT RUN | |
| I5 | Per-account authorization | FAIL (by design, disclosed) | F-08 |
| I6 | Dependency vulnerability scans (OSV, `npm audit`) | NOT RUN | no network |

## J. Dependencies (section 14)

| # | Check | Status | Evidence |
|---|---|---|---|
| J1 | `pip check` | PASS | no broken requirements |
| J2 | 21 exact pins equal installed | PASS | |
| J3 | `.venv` / lockfiles unchanged | PASS | `pip freeze` identical to R3/R4 reference |
| J4 | `npm ls --depth=0` clean | PASS | |

## K. Test execution summary (section 15)

| # | Run | Status | Result |
|---|---|---|---|
| K1 | core | PASS | 1,198 passed / 12 skipped |
| K2 | security | PASS | 147 passed |
| K3 | data | FAIL | 1,508 passed / 1 failed |
| K4 | pipeline | PASS | 31 passed |
| K5 | scripts | PASS | 263 passed / 1 skipped |
| K6 | 7 agent files | PASS | 59 passed / 4 skipped |
| K7 | personalized-insights API | PASS | 8 passed |
| K8 | training (guarded) | PASS | 796 passed / 2 skipped |
| K9 | isolated API suite (~639) | NOT RUN beyond 120 | 119 passed / 1 failed (key-dependent test) |
| K10 | isolated db + ingestion | PASS | 136 passed in 13 min 9 s |
| K11 | native process crashes in this audit | none | 0 |
| K12 | environment failures | none classified | (network was reachable) |

## L. U1 - backend NVIDIA DLL exposure (section 17)

| # | Check | Status | Evidence |
|---|---|---|---|
| L1 | Final classification | **No exposure observed in tested imports** (unchanged; not "safe") | U1 report |
| L2 | Standalone `xgboost` import maps an NVIDIA DLL | PASS (not observed) | 9 runs |
| L3 | Backend served import closure imports `xgboost` | PASS (not observed) | 18 runs |
| L4 | Latent path `autogen` -> `flaml` -> `xgboost` | FINDING | not wired |
| L5 | `sys.modules`/DLL state after a served request | NOT RUN (deferred) | |
| L6 | `warm_model_caches` as an investigation | NOT RUN (deferred) | note: ~19 min of API tests started the lifespan; audit 2.3 |
| L7 | XGBoost fit/predict/DMatrix/Booster as an investigation | NOT RUN (deferred) | the guarded training suite uses XGBoost by design |
| L8 | AutoGen debate execution path | NOT RUN (deferred) | |
| L9 | `wealthpilot.api.main` import | BLOCKED | reads `.env` at import |

## M. R4 mitigation (section 18)

| # | Check | Status | Evidence |
|---|---|---|---|
| M1 | Guard files present, unmodified, test-only | PASS | manifest hashes |
| M2 | Guard active in the guarded suite | PASS | header `active (pinned)` |
| M3 | Whole-suite guarded runs without native crash | PASS | 6 consecutive (5 R4 + 1 audit) |
| M4 | Guard expanded, or applied to production/other suites | NOT DONE (correct) | |
| M5 | Underlying driver defect fixed | NO | workaround only. **DECISION** (F-10) |

## N. Documentation (section 16)

| # | Check | Status | Evidence |
|---|---|---|---|
| N1 | Required documents exist | PASS | |
| N2 | `docs/MEMORY.md` current | FAIL (stale in places) | F-04 |
| N3 | README current | FAIL | says "through Phase 31" |
| N4 | ADRs for architectural decisions | PASS | 56 ADRs, latest ADR-056 |
| N5 | Demo / viva documents accurate about AutoGen | PASS | |
| N6 | This audit and checklist | PASS | created |

## O. M.Tech demonstration readiness (section 21)

| # | Check | Status |
|---|---|---|
| O1 | Four analysis outcomes demonstrable (approved, savings-first, rejected, pending) | PASS (DOCUMENTED: Phase 29/31 live verification; not re-run) |
| O2 | Demo data and personas present, synthetic, no PII | PASS |
| O3 | Frontend builds and passes its unit tests | PASS |
| O4 | Honest limitations documented for the viva | PASS, with the gaps listed in F-01/F-02/F-03/F-08 |
| O5 | API suite re-confirmed on the current code | **NOT RUN - DECISION before the viva** |
| O6 | Stale documents refreshed | **TODO - DECISION** |
