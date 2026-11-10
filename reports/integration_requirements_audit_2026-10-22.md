# Integration and Requirements-Verification Pass — 2026-10-22

Scope: verify the Financial Behaviour & Sentiment page and the Data Protection page against the current backend contracts, run the relevant
regression, audit the implementation against `docs/PROJECT_PLAN.md`, and fix verified in-scope integration defects. Nothing was committed or
pushed. `neondb` was never connected to; the only database used was the isolated test database `neondb_test` through the guarded runner.

Evidence labels: **[run]** = executed in this pass with the result recorded in section 4; **[read]** = read from code, metrics or a report in this
pass but not re-executed; **[carried]** = stated by an earlier report and not re-verified here.

## 1. Contract verification

### Financial Behaviour & Sentiment (`/financial-behaviour`)
| Check | Result | Evidence |
| --- | --- | --- |
| Generated TypeScript types equal a fresh generation from the live OpenAPI schema | identical | [run] regenerated and compared byte-for-byte (CR ignored) |
| Frontend fixtures equal what the real route returns today | yes | [run] `test_the_frontend_test_fixtures_are_exactly_what_the_backend_returns_today` |
| Length limit and control-character class never looser than the backend | yes | [run] `test_the_length_boundary_matches_the_documented_limit_and_the_frontend_is_never_looser`, frontend cross-check tests |
| Text never stored, logged, echoed (200, 400, 422, 500) | yes | [run] backend hardening tests; [run] real-browser check: not in localStorage, sessionStorage or URL before or after submit |
| `uncertain` / unrecognised readings never shown as neutral | yes | [run] component cases and a mutation (V29-V31) that fails if it changes |
| Sentiment cannot override the stored assessment | yes | [run] `test_the_stored_assessment_is_reported_and_never_overridden_by_the_text`; the page states the stored assessment stays the authority; [read] the insight modules are not imported by analysis, recommendation or compliance (tested) |
| Profile switching clears typed text and results | yes | [run] card keyed by profile (tested + mutation V43); [run] browser: profile 2 showed an empty box, 0 months, no stale reading |
| Validation, loading, error, empty, one-month states | yes | [run] component cases |

### Data Protection (`/security`)
| Check | Result | Evidence |
| --- | --- | --- |
| Encryption status is a real result | yes | the route runs a real encrypt/decrypt round trip with a random probe; [run] a test makes the round trip fail and the status becomes `failed`; a real captured response exists for each state |
| Ledger status is a real result | yes | the route walks the whole chain; [run] a tampered event produces `invalid` with the failing sequence, in a test and in the real browser |
| No key, hash, event or note text in the status response | yes | [run] `test_security_status_exposes_no_hashes_keys_or_record_contents` |
| Page shows the exact label "Academic prototype — not a real blockchain." | yes | [run] backend `PROTOTYPE_NOTICE` test and rendered case |
| `X-Customer-Id` limitation documented accurately | yes | stated in `THREAT_MODEL.md` §7, `SECURITY.md`, ADR-047, `RULES.md` Rule 36 and in the page's own limitations list: a caller who sets the path profile and the header to someone else's id is not stopped |
| No wording calls the ledger a real blockchain, decentralized, immutable or tamper-proof | yes | [run] scan of docs, frontend and backend; remaining hits are negations, rules, or "immutable" raw datasets. One stale sentence in `MEMORY.md` ("blockchain work comes after the AI track") was corrected |

## 2. Defects found and fixed in this pass
1. **Protected-note and security-status routes returned an anonymous 500 on a database without migration `f7a2d4b6c810`** (this is the state of the
   development database today), with an unhandled-exception traceback in the log. Now a plain 503 that names the missing migration; nothing is
   created, saved or logged as unhandled; identity is still checked first; the same routes work as soon as the tables exist. The 503 is a status
   these routes already documented, so no contract changed. Tests: 4 new SQLite tests, a mutation check (removing the fix fails 3 of them), and the 4
   PostgreSQL tests on the isolated database.
2. **The Data Protection page described that 503 as "We couldn't complete this analysis"** (the shared error component's wording). The page now shows
   the backend's own fixed sentence for a 503 and keeps the shared message for everything else. 2 new rendered cases, 2 new mutations.
3. **Mutation runner counted stale mutations as kills** (found in the previous pass; fixed there; re-verified here: 112 of 112 with a pre-flight).
4. A stale `MEMORY.md` sentence about blockchain work.

Not changed, deliberately: the sentiment classifier, financial formulas, API contracts, security policy, risk logic.

## 3. Requirements audit against `docs/PROJECT_PLAN.md`

### Completed (code, artifact, test or report exists)
| Plan item | Evidence |
| --- | --- |
| Stage 0: config, logging, PostgreSQL schema with Alembic, `data_source` / `model_version` columns | [read] models and migrations; single Alembic head `f7a2d4b6c810` (DB-free test) |
| 2.1 Risk classification: 4 models (logistic regression, random forest, XGBoost, MLP), macro-F1, per-class recall, confusion matrix, calibration, SHAP, genuine labels only | [read] `models/metrics.json`, `models/risk/*`; best model random forest; [run] `tests/training` 99 passed |
| 2.2 Expense segmentation (income-normalised, K-Means and GMM and Ward compared) | [read] metrics: selected K-Means, k = 2 (data-driven, as the plan allows) |
| 2.3 Behaviour detection (rolling z-score / CUSUM + Isolation Forest, thresholds calibrated) | [read] `models/behaviour/*`, metrics |
| 2.4 Market models: naive, ARIMA, GARCH, LSTM, GRU on 5 instruments, walk-forward, Diebold-Mariano, regime label only | [read] `models/market/*`, metrics; ARIMA/GARCH are refit per window and only a methodology summary is saved (documented in the Phase 6 report) |
| 2.5 Portfolio: MVO + Ledoit-Wolf + box constraints, HRP, 1/N, backtest, frontier | [read] `models/portfolio/*` |
| 2.6 Goals: closed form + Monte Carlo (10,000 paths) | [read] `core/goals.py`; [run] `tests/backend/core` in the DB-free group |
| Compliance as a binding, YAML-driven rule engine; REJECT cannot reach the explanation | [run] `tests/backend/core` compliance tests pass; the agent-level gate-safety tests need the development database and were NOT run (section 3, Untested) |
| LangGraph with typed state and conditional routes (information request, re-profile, savings-first); AutoGen scoped to the debate; Gemini with schema validation | [read] `agents/graph.py`; agent tests (section 4) |
| FastAPI with RFC 7807 errors, SSE progress stream, profile-hash result cache, generated TypeScript types | [run] API tests (section 4), types identical to a fresh generation |
| React/Vite/shadcn UI: the nine views plus Goals, Household, Behaviour & Sentiment, Data Protection; Agent Activity from the stream; Scenario Simulator | [run] frontend gates (section 4); two pages verified in a real browser |
| Demo personas through the real API with a validated manifest | [run] `validate_demo_data.py` DEMO DATA VALID |
| Sensitive-data protection prototype (extension, ADR-047) | [run] 147 security tests + 4 PostgreSQL + 112 frontend mutations |

### Completed with a documented deviation from the plan
| Deviation | Status |
| --- | --- |
| Compliance REJECT does not loop back to recommendation with a retry cap (plan Part 3) | approved 2026-09-14, recorded in `agents/graph.py` and the decision log |
| FAR-Trans and Kaggle are never paired into synthetic profiles (plan Stage 1 step 6) | recorded decision: the populations stay unlinked |
| ARIMA/GARCH are not serialized per fit (plan 6.6) | documented in the Phase 6 report |
| **GMM and Ward are not serialized; only the selected K-Means and scaler are (plan 6.2 says all are "fitted and serialized")** | **not documented as a decision; low risk because only the selected model is used when serving; should be recorded** |

### Incomplete
| Item | Why |
| --- | --- |
| Word-format project report (plan Stage 6, item 26) | no such file in the repository; cannot be verified here |
| Real server-side authentication and authorization | out of scope by ADR-020; the protected notes' confidentiality is therefore limited to database or backup readers without the key |
| UI to create, read, update or delete a protected note | only the API and a count on the Data Protection page exist; no page lets a user use the feature |
| Key rotation and re-encryption tooling, key escrow, managed KMS, external ledger anchor, ledger rate limiting | listed hardening items in `THREAT_MODEL.md` §14 |
| Encryption of existing sensitive tables | not done by design; the page lists them as unprotected |

### Blocked (needs the owner or independent people)
| Item | Blocker |
| --- | --- |
| Apply migration `f7a2d4b6c810` to the development database | owner action (`alembic upgrade head` for `DATABASE_URL`); routes answer 503 until then |
| Independent human annotation of the sentiment rules | needs at least two independent reviewers and the owner's decisions O1-O4 and O7, plus formal acceptance of O5/O6; the rules baseline stays `UNVALIDATED_BASELINE`; the fictional pilot pack is not evidence |
| Real GDELT acquisition and any trained sentiment model | not approved |
| Real blockchain integration | not approved; only the local hash-chain prototype exists |

### Untested or not re-run in this pass
| Item | Why |
| --- | --- |
| 42 agent tests that use development-database fixtures (`real_*`) | they would connect to `neondb`, which this pass must not do; deselected by the guarded runner (the other 187 agent tests passed) |
| End-to-end analysis with real FAR-Trans and market data in a database, and the populated Risk / Portfolio / Recommendation pages in a browser | no such database is available without `neondb`; the offline backend returns `pending_information` |
| 3 live-Gemini tests | skipped when Gemini is unreachable or out of quota |
| Penetration test, load test, independent security review | never performed |
| 10 buttons rendered as links that assistive technology announces as buttons | [carried] from an earlier pass, not re-checked |

## 4. Commands run and results
See the final report of this pass for the exact commands and numbers; they are repeated in `docs/TEST_PLAN.md` section 25.

### Results of this pass (all [run])
| Command | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest tests/backend/core tests/backend/security tests/backend/scripts tests/backend/db/test_migration_history.py tests/backend/api/test_personalized_insights.py tests/backend/api/test_personalized_insights_hardening.py tests/backend/api/test_health.py tests/backend/api/test_lifespan.py -q` | **930 passed, 1 skipped** |
| `.venv\Scripts\python.exe -m pytest tests/backend/data/gdelt -q` (run on 2026-10-21, NOT re-run in this pass) | 1492 passed |
| `.venv\Scripts\python.exe -m pytest tests/training -q` | **99 passed** (no database) |
| `python scripts/run_isolated_db_tests.py ...` once per file over `tests/backend/agents` (guarded runner, `neondb_test` only; its own deselection of development-database tests) | **187 passed, 0 failed, 3 skipped (live Gemini)**; **42 tests deselected** because they use development-database fixtures; two files (`test_compliance_gate_safety.py`, `test_financial_inputs_integration.py`) are entirely such tests and collected nothing (exit 5) |
| `python scripts/run_isolated_db_tests.py --suite api -- tests/backend/api/test_protected_records_postgres.py -v` | 4 passed |
| `python backend/scripts/validate_demo_data.py` | DEMO DATA VALID |
| `python scripts/export_security_fixtures.py --check` | fixtures current |
| `npx tsc -b`, `npm run typecheck:tests` (in `frontend/`) | exit 0, exit 0 |
| `npx oxlint` | 0 errors, 8 existing warnings |
| `npm run build` | built |
| `npm test` | **135 passed** |
| `npm run test:mutations` | **112 of 112 detected**, with the pre-flight against stale mutations |

The isolated api/db/ingestion suites (665 passed, one transient connection drop that passed on re-run, 22 files clean plus the re-run file) were run in the previous pass; no backend code that they cover changed since except `protected_record_service.py` (re-verified by the 4 PostgreSQL tests above).

**Runner caveat found in this pass**: `scripts/run_isolated_db_tests.py --suite X -- <path>` always collects the suite's own directory as well, so a per-file run of a path outside that suite also runs the suite. A first attempt at the agent files therefore ran unrelated API tests and was stopped and discarded (one of those hit a transient connection drop). The accepted run drives the runner's own `main()` with a one-file suite registered, so the guard is unchanged. Per-file results for the earlier api/db/ingestion run were unaffected because their totals match the suite counts. The runner itself was not modified; a `--only` option would be a worthwhile small improvement.

Core workflows that remain unverified without `neondb`: see "Untested" above. A real-pipeline run needs a database holding FAR-Trans and market data.

## 5. Findings from the owner's screenshots (Risk and Goals pages)
Both pages showed "not available yet" / "analysis has not reviewed them yet" for the owner's profile. This is the designed pending-information path, not a defect:
`risk_analyst --(confidence is None)--> information_request --> END` (`agents/graph.py`). The risk model reads FAR-Trans trading history through
`risk_inputs.external_customer_id`, which only the demo personas A-C have (persona D deliberately has none) and which no public API or form can set.
With no risk result the graph ends before the goal analyst, so recorded goals are not reviewed either. This follows plan Part 3 ("risk confidence
below threshold: route to an information-request node instead of proceeding"). Decision for the owner, deliberately not made here: (a) keep as is and
improve the empty-state wording to say why and point to the demo accounts, or (b) change the graph so goal feasibility, which needs no risk category,
still runs. (b) changes a completed phase and needs explicit approval.
