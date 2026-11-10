# Research Enhancement Track — Phase B1-V Verification Report

**Type:** verification only. No feature, schema, calculation, model, dataset or
demo-data change was made. Phase B2 has not started.
**Subject:** Phase B1 (`reports/phaseB1_financial_behaviour_inputs_report.md`,
`docs/DECISIONS.md` ADR-042).
**Date:** 2026-10-12.

## 1. Repository state inspected

- `git status` at the start of verification was **identical** to the end of B1
  (same modified and untracked files), so nothing had changed since the B1 report.
- B1 code present as reported: `MonthlyFinancialRecord` model, router registered in
  `api/main.py`, `MonthlyRecordUpdate` schema, `MonthlyRecordNotFoundError` and
  `UnprocessableRecordError`, the race handler (`IntegrityError` → `409`) in
  `monthly_records_service.py`, the manifest head pointer `e5b1c7d93a20`.
- **Additive-only check against git HEAD** (these files were unmodified before B1,
  so the diff is exactly B1's change): `errors.py` +11/−0, `main.py` +2/−0,
  `schemas.py` +91/−0, `models.py` +40/−0, `api-client.ts` +11/−0, `types/api.ts`
  +337/−0, `test_migration_history.py` +15/−1 (the one removed line is the old head
  pin).
- **Protected modules byte-identical to git HEAD:** `core/recommendation.py`,
  `core/optimizer.py`, `core/compliance.py`, `core/goals.py`, all of `agents/`,
  `api/services/analysis_service.py` (including `compute_profile_hash`),
  `config/compliance_rules.yaml`, `training/`, `models/`.

## 2. Implementation behaviour verified

| Requirement | Evidence |
| --- | --- |
| Keyed by customer and calendar month | `UNIQUE(customer_id, period_month)` and the first-of-month CHECK exist on both live databases; duplicate-period tests pass |
| Missing distinct from zero | API tests (explicit `0` stored as 0, omitted stays `null`); browser: blank savings shows "Not provided", entered 0 shows ₹0 |
| Optional fields and income-basis rules | API tests; browser validation messages for empty month, negative amount, basis without income; DB CHECK `basis_needs_income` |
| Duplicate-period updates | API tests (second PUT corrects, one row); browser edit kept one row |
| Concurrent creation | `test_a_duplicate_period_race_is_a_409_and_never_echoes_the_amounts` passes |
| Deterministic features | `test_result_is_independent_of_input_order`; module has no clock, I/O or randomness |
| Missing months not zero | change needs the consecutive month; consistency counts only known months (tests pass) |
| Zero or missing income | no division; reason returned (tests pass) |
| Annual income and snapshots unchanged | `test_features_never_use_the_annual_profile_income`, `test_existing_financial_inputs_are_unaffected`; dev-DB fingerprints of `customers.income` and `financial_inputs` identical before and after verification |
| Analysis cache unchanged | `test_saving_monthly_records_does_not_change_the_analysis_cache_key`; `analysis_service.py` unchanged vs HEAD |
| Individual and household workflows | household goal, summary, member and finance suites pass (sections 3–4) |

## 3. Database and migration checks (read-only)

| Check | Development DB | Test DB |
| --- | --- | --- |
| `alembic heads` (files) | `e5b1c7d93a20` — single head | — |
| `alembic current` | `e5b1c7d93a20 (head)` | `e5b1c7d93a20 (head)` |
| `alembic check` (model vs schema) | No new upgrade operations | No new upgrade operations |
| Table columns, 8 CHECK constraints, unique key, FK `ON DELETE CASCADE` | present | present |
| `monthly_financial_records` rows | 0 | 0 |

Snapshots of both databases taken before and after verification (row counts of
nine tables plus fingerprints of `customers.income` and `financial_inputs`) are
**identical**. Nothing was reset, truncated or deleted.

## 4. Tests executed in B1-V

One run, `-v`, output to a file, against the hosted databases, with no other
process touching them:

| Group | Passed |
| --- | ---: |
| `tests/backend/core/test_behaviour_features.py` (B1) | 30 |
| `tests/backend/db/test_migration_history.py` (B1 migration) | 13 |
| `tests/backend/api/test_monthly_records.py` (B1) | 53 |
| `tests/backend/api/test_household_goals.py` | 84 |
| `tests/backend/api/test_qa.py` | 5 |
| `tests/backend/api/test_scenarios.py` | 2 |
| `tests/backend/api/test_seed_demo_data.py` | 34 |
| `tests/backend/api/test_sse.py` | 4 |
| `tests/backend/data` | 21 |
| `tests/training` (behaviour 13, expense 10, market 51, portfolio 12, risk 13) | 99 |
| **Total** | **345** |

**Result: 345 passed, 0 failed, 0 errors, 0 skipped**, with 146 warnings
reported by pytest (warnings, not failures; not individually classified here).
Duration 46 min 41 s. Exit code 0.

Frontend: `npx tsc -b` pass; `npx oxlint` the existing 8 warnings, none in B1
files; `npm run build` pass.

## 5. Combined regression coverage of B1

Together with the runs recorded in the B1 report, **every test file under
`tests/` has now been executed against the B1 code, with a passing final result**:

- B1-V (above): the groups B1 had not run, plus the focused B1 tests.
- B1 targeted run: `test_monthly_records.py`, `tests/backend/core`,
  `tests/backend/db`, `tests/backend/scripts`, `test_profiles.py`,
  `test_rfc7807.py`, `test_lifespan.py`, `test_households.py`,
  `test_household_summary.py`. Its 29 failures and 2 errors were classified (2
  hosted-DB disconnects, 1 head pin, 28 manifest-head) and all passed in isolation
  after the B1 fixes.
- B1 interrupted full run (to 30%): all of `tests/backend/agents`,
  `test_analysis.py`, `test_goal_period_frequency.py`, `test_health.py`,
  `test_household_finance_metadata.py`, `test_household_finances.py`. 436 passed,
  1 skipped (a live-Gemini test, as documented), 1 failure that passed in isolation.

Caveat stated precisely: those agent and analysis groups ran while the monthly-records
service's race handler was being added. They import but do not exercise that
service, and no other code has changed since they ran.

## 6. Browser verification

**Repository rule:** `CLAUDE.md` ("Do not run training jobs or long-lived servers
yourself") and both `scripts/dev-backend.sh` and `scripts/dev-frontend.sh` ("Blocks
— run this yourself") rule out starting the documented dev servers myself. They
were **not** started, and no process-management convention was changed.

**What was done instead (no server process):** a headless-browser check with
Playwright (Chromium):

- The **built** frontend (`frontend/dist`, from `npm run build`) was served to the
  browser from disk through Playwright request interception.
- Every API call was handed to the **real FastAPI app running in-process** in a
  short-lived Python helper (FastAPI TestClient; no port is opened).
- That helper ran on the **development database inside one transaction that was
  always rolled back**, the same pattern as the test suite's `real_client` fixture.
  The before/after snapshots in section 3 confirm no change.

Not exercised by this method: the uvicorn and Vite processes themselves, real
network latency, and the browser's handling of a real cross-origin server.

**Scenario** (Individual Demo login → Customer Profile), 43 checks:

| Area | Checks (all passed in the final runs) |
| --- | --- |
| Existing profile intact | summary shows the persona; snapshot shows ₹14,40,000; financial-inputs card loads 45000; questionnaire shows 25 answers |
| Validation | empty month; negative amount; basis without income; 3-decimal value rejected by the API and shown as a friendly error (raw detail collapsed); nothing saved after rejected attempts |
| Create (partial) | income ₹1,00,000, spending ₹40,000, savings blank → "Not provided", investments 0 → ₹0, basis Net; form recognises the existing month |
| Edit | spending → ₹45,000, savings → ₹20,000, income kept, still one row |
| Clear | blank spending → "Not provided", other fields kept |
| Second month | form resets when switching month; partial month (spending only, basis Not stated); newest first; switching back reloads stored values |
| Delete | Aug removed, Jul kept |
| Accessibility | basis buttons expose `aria-pressed`; delete buttons have accessible names |
| Layout | no page-level horizontal overflow at 1440, 1024, 768 and 390 px; saving a month works at 390 px |
| Health | no uncaught page errors; no 5xx; transaction rolled back |

**Runs:** run 1 — 12 of 14 checks then stopped: one `PUT` returned **HTTP 500**,
and the harness halted. Runs 2 and 3 (identical scenario, with server exceptions
captured) — **43/43 passed**, no server exception. An in-process replay of the
exact request sequence also succeeded.

**Classification of the run-1 500: not reproduced; cause not captured.** That run
did not save the server log, so the exception is unknown. The code path is
deterministic and identical between runs, and the hosted database has dropped
connections repeatedly during this project, so a transient database error is the
most likely explanation. This is an inference, not a verified finding. It is
recorded as an open observation, not a confirmed regression.

**Usability observation (not a defect):** at 390 px the records table scrolls
sideways inside its own container; Savings, Investments, Basis and the delete
button need a sideways scroll to reach. The page itself does not overflow.
Smallest possible correction, if wanted: a stacked list layout below the `sm`
breakpoint. Not made, because it is outside verification scope.

**Manual verification on the real stack (for you):**

1. `scripts/dev-backend.sh` (terminal 1), `scripts/dev-frontend.sh` (terminal 2).
2. Open `http://localhost:5173/login` → **Use Individual Demo** → **Customer
   Profile** → scroll to **Monthly record (optional)**.
3. Choose a past month; enter Income 100000, Spending 40000, leave Savings blank,
   Investments 0, choose **Net** → **Save month**. Expect the row: ₹1,00,000 /
   ₹40,000 / Not provided / ₹0 / Net.
4. Change Spending to 45000 and Savings to 20000 → **Update month**; then blank
   Spending → **Update month** (expect "Not provided").
5. Try: no amounts (expect "Enter at least one amount…"); −5 (expect "…0 or
   greater"); Gross with no income (expect "Choose net or gross only…").
6. Delete the month with the bin icon.
7. Repeat once at phone width.
8. Note: records saved this way persist in the development database; delete them
   afterwards if you want the demo data unchanged.

## 7. Confirmed regressions

**None.**

## 8. Remaining untested or open areas

- The uvicorn/Vite live stack was not run by me (section 6); the manual steps
  above cover it.
- The run-1 HTTP 500 in the browser harness is unexplained (section 6).
- Concurrency is verified by a simulated race (forced duplicate insert), not by two
  genuinely simultaneous clients.
- The behaviour-features endpoint has no UI yet (by design); it is covered by API
  tests only.

## 9. No unrelated changes

- `git status` at the end of verification is identical to the start, apart from
  this report.
- The `pip freeze` fingerprint is unchanged and no npm dependency was added.
- No implementation file, test, migration, dataset, model artifact or demo record
  was modified.
- The harness, replay and snapshot scripts live only in the session's scratch
  directory, outside the repository.

## 10. Is B1 ready for acceptance?

**Yes, with the observations above.** Every test file has a passing result
against the B1 code; the migration is at head on both databases with no drift;
the features behave as documented; protected modules are unchanged; and the UI
works end to end in a headless browser against the real API. Your manual check
on the real dev servers and a decision on the mobile table layout remain open.
B2 needs your explicit approval and a licensed historical news source.
