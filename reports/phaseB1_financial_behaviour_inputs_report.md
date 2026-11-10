# Research Enhancement Track — Phase B1 Report
## Optional monthly financial inputs and financial behaviour features

**Track:** Research Enhancement Track (separate from numbered Phases 0–36; never Phase 37).
**Authorised scope:** B1 only. B2 onward is not started.
**Decision record:** `docs/DECISIONS.md` ADR-042.
**Design basis:** `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` (Phase B0).

## 1. Scope completed

- An additive, period-aware store for four optional monthly amounts (income,
  expenses, savings, investment contributions).
- A pure, deterministic feature module over those records.
- API routes to save, correct, list and delete months, and a read-only features
  route.
- One new card on the Customer Profile page to enter and review the months.
- A reversible Alembic migration, applied to both databases.
- Tests, an ADR and this report.

Not done, by design: no recommendation, optimizer, compliance, market-model or
analysis change; no sentiment, no hybrid model, no blockchain; no dependency
added; no dataset or model artifact touched. No demo persona or record changed;
the demo manifest's schema-compatibility pointer was updated (section 11).

## 2. Files inspected

`CLAUDE.md`, `docs/MEMORY.md`, `docs/DECISIONS.md` (ADR-014, 020, 024, 025, 033),
`docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`, `backend/wealthpilot/db/models.py`,
`api/schemas.py`, `api/errors.py`, `api/routers/profiles.py`, `api/main.py`,
`api/dependencies.py`, `api/services/analysis_service.py` (`compute_profile_hash`),
the Alembic history and the latest migration, `frontend/src/components/profile/
financial-inputs-card.tsx`, `lib/api-client.ts`, `lib/format.ts`, the shared test
fixtures, and the existing financial-input tests.

## 3. Data semantics (decided before storage)

What already existed, unchanged:

| Existing field | What it is |
| --- | --- |
| `customers.income` | **Annual** income; net or gross is not documented anywhere |
| `financial_inputs.monthly_essential_expenses` | Recurring monthly **essential** spending, one snapshot |
| `financial_inputs.current_liquid_assets` | A balance (snapshot), not a flow |
| `financial_inputs.contribution_amount` | A **planned** monthly contribution used by goal maths |

None of these was reinterpreted, overwritten or used to build monthly history.

New, in `monthly_financial_records`, all **monthly rupee flows for one calendar month**:

| Field | Meaning |
| --- | --- |
| `income` | Money received in the month, on the stated `income_basis` |
| `expenses` | Total living costs; excludes money moved to savings or investments |
| `savings` | Money newly set aside; a transfer out of savings is not new savings |
| `investment_contribution` | Money newly invested; moving existing savings into an investment is neither new savings nor new income |
| `income_basis` | `net` or `gross`, optional, never assumed; allowed only with an income |

Savings and investment contributions are disjoint flows, which is how
double-counting is prevented. Expenses are deliberately **not** split into
essential and discretionary, and the existing essential-spending snapshot keeps
its own meaning. Currency: none is stored (consistent with the whole application,
which presents rupees); the feature module refuses mixed currencies.

## 4. Reporting-period strategy

- `period_month` is the first day of the month; the API uses `YYYY-MM`.
- One row per customer per month (unique). A second save of the same month is a
  correction.
- Omitted field keeps its value; explicit `null` clears it; a month can be
  deleted.
- Future months and years before 2000 are rejected.
- A missing month is simply absent. It is never filled in or treated as zero.

## 5. Input validation rules

| Rule | Where enforced |
| --- | --- |
| Amount is a JSON number; strings (including "1,000", "12e3"), booleans and containers rejected | Pydantic validator |
| Finite (NaN and infinity rejected) | Pydantic and DB |
| Non-negative | Pydantic and DB CHECK |
| At most two decimal places; at most 999,999,999,999.99 | Pydantic |
| Unknown fields rejected | `extra="forbid"` |
| At least one amount per record | Service and DB CHECK |
| `income_basis` only with an income | Service and DB CHECK |
| Period is first of month | Service and DB CHECK |
| Unique per customer and month | DB UNIQUE |
| Two saves racing for one new month | `409`, with the driver error (which contains amounts) not logged or returned |

The service validates the merged result **before** touching any stored row, so a
rejected request cannot leave a partial change behind.

## 6. Missing-value behaviour

- Every amount is nullable; `NULL` means not reported.
- A blank form field is never sent as 0; on a month that already has a value, a
  blank field clears it.
- No ratio is computed from a missing value. Each unavailable feature carries a
  plain reason.
- Zero income never divides.
- Existing customers have no rows; their profile, financial inputs and analysis
  behave exactly as before.

## 7. Features implemented (`core/behaviour_features.py`, `behaviour_features_v1`)

| Feature | Definition | Unavailable when |
| --- | --- | --- |
| Expense, savings, investment-to-income | amount ÷ income for the **same** month | income missing or zero; numerator missing |
| Change in expenses, savings, investments | latest minus the immediately previous calendar month (absolute and relative) | previous month absent; either value unknown; relative change if previous is zero |
| Savings / investment consistency | share of known months with an amount above zero, over the 12 months ending at the latest report | fewer than 3 known months |
| Data-quality notes | outflows exceed income in the latest month; mixed or unstated income basis | (flags only, nothing is corrected) |

They are ratios and changes of reported amounts. They are not sentiment, say
nothing about emotion or psychology, and imply no holding. The window (12) and
minimum (3) are feature-construction parameters, not financial thresholds.

## 8. Schema change and rationale

One new table, `monthly_financial_records`; nothing else changed. A separate table
(ADR-025's pattern) was chosen over new columns on `customers` or
`financial_inputs`, because those hold a snapshot and a month is a different
persistence concern. Migration `e5b1c7d93a20` revises `c3e8f2a9d154`.

- Verified on the test database: upgrade, downgrade, upgrade.
- Applied to the development database.
- `alembic check` reports no drift.

## 9. API and frontend

| Route | Purpose |
| --- | --- |
| `GET /api/profiles/{id}/monthly-financial-records` | List months, newest first |
| `GET/PUT/DELETE /api/profiles/{id}/monthly-financial-records/{YYYY-MM}` | Read, save or correct, delete |
| `GET /api/profiles/{id}/behaviour-features` | Read-only features (carries `model_version`, `data_source`) |

Frontend: a "Monthly record (optional)" card on Customer Profile (month picker,
four optional amounts with plain-language help, a net/gross choice, and a table
of recorded months with delete). It calculates nothing. The OpenAPI types were
regenerated in-process; the diff is purely additive.

## 10. Privacy

- The service never logs an amount, payload or feature value, and the API layer
  has no request-body logging.
- Nothing is sent to a ledger, an external provider, or an LLM; no new service or
  tracking was added.
- The records are not encrypted at rest by this repository, and none is claimed.
- Like every `profile_id` route, they are scoped by customer id, not authorised
  (ADR-020/024); the prototype still has no per-account authorisation.
- Validation errors (`422`) echo the offending value back to the same caller, as
  the rest of the API does.

## 11. Tests

New tests (all passing):

| File | Tests | Covers |
| --- | ---: | --- |
| `tests/backend/core/test_behaviour_features.py` | 30 | empty and partial input, explicit zero vs missing, zero and missing income, same-month income, mixed currency, negative/NaN/infinity/float rejected, duplicate period, first-of-month, unknown basis, consecutive-month change, single observation, zero-previous relative change, consistency minimum and window, unreported months not counted as zero, outflow flag, mixed and unstated basis, order independence |
| `tests/backend/api/test_monthly_records.py` | 53 | all fields omitted, partial record, explicit zero, empty and null-only payloads, negative, strings ("1000", "1,000", "12e3"), booleans, lists, three decimals, out-of-range, unknown field, NaN/infinity literals, malformed/future/too-old/current periods, duplicate-month correction, explicit null clears, last amount cannot be cleared, delete, ordering, income basis rules, customer isolation, unknown customer 404 on every route, features endpoint (empty, populated, never uses annual income), analysis cache key unchanged, existing financial inputs unchanged, table CHECK/UNIQUE constraints, duplicate-period race returns 409 without echoing amounts |
| `tests/backend/db/test_migration_history.py` (2 added) | 13 total | single head is now B1; B1 revises the Phase 36 head; B1 creates one table and one index and touches no existing table |

Migration checks run by hand: `upgrade` → `downgrade -1` → `upgrade` on the test
database; `upgrade` on the development database; `alembic check` reported no
drift.

Regression runs (hosted databases, `-v` output to a file):

1. **Full suite, interrupted.** Started, but it progressed at about 2% per 10
   minutes against the hosted database and would have needed about six more
   hours, so I stopped it at 30%. Up to that point: **436 passed, 1 failed, 1
   skipped**. It covered every `tests/backend/agents/` file and the first API
   files. The one failure
   (`test_analysis.py::test_second_call_after_financial_inputs_change_runs_a_fresh_analysis`)
   **passed when re-run in isolation**.
2. **Targeted run** (the isolated re-run above, `test_monthly_records.py`,
   `tests/backend/core`, `tests/backend/db`, `tests/backend/scripts`,
   `test_profiles.py`, `test_rfc7807.py`, `test_lifespan.py`,
   `test_households.py`, `test_household_summary.py`): **733 passed, 29 failed,
   2 errors** in 1 h 49 min. Every failure was classified from its traceback:
   - 2 errors: `server closed the connection unexpectedly` (hosted-database
     drop). Both **passed in isolation**.
   - 1 failure: `test_there_is_exactly_one_head` still expected the Phase 36 head.
     Updated to the B1 head.
   - 28 failures: `test_validate_demo_data.py`, all from one cause. The demo
     manifest's `compatible_with.alembic_head` still named the Phase 36 head, and
     the validator requires it to equal the current head.
3. **Isolated re-run after the fixes:** `test_migration_history.py`,
   `test_validate_demo_data.py` and the two errored tests: all pass (69 + 13).

Not run in this phase, with the reason: the rest of the full suite after 30%,
which is `test_household_goals.py` (partly run), `test_qa.py`,
`test_scenarios.py`, `test_seed_demo_data.py`, `test_sse.py`,
`tests/backend/data` and `tests/training`. None of them imports the new module
or table, but they were not executed, so no claim of a full clean run is made.

Frontend: `npx tsc -b` pass; `npx oxlint` no warnings in changed files (the
existing 8 remain); `npm run build` pass. Not exercised in a browser (see
section 12).

**One demo-data metadata change.** To keep the demo validator passing, the
manifest's hand-maintained `compatible_with.alembic_head` was changed from
`c3e8f2a9d154` to `e5b1c7d93a20` (in `demo_data/manifest.json` and in the
validator's default header), and the manifest was regenerated. No persona,
household record, expected result or data file changed. The manifest's
`deterministic_identifier`, which hashes every data file, is identical before
and after (`741ad85f…`).

## 12. Remaining limitations

- Nothing consumes the records yet; they exist to enable later research phases.
- The Customer Profile card was verified by type-check, lint and production build
  only. It has **not** been exercised in a browser, because no backend or frontend
  dev server was running and this project's rule is not to start long-lived
  servers myself. To try it: `scripts/dev-backend.sh`, `scripts/dev-frontend.sh`,
  sign in, open Customer Profile.
- The demo personas have no monthly records (demo data was deliberately untouched).
- `expenses` is a single total; essential versus discretionary is not captured here.
- A customer's amounts are self-reported and unverified.
- Income basis is optional, so ratios on different bases are flagged but not
  converted.
- No per-account authorisation, and no encryption at rest.
- Consistency over fewer than three known months is reported as unavailable, so a
  new user will see few trend features for a while.

## 13. Recommended next phase

Phase B2 only (the market-sentiment data pipeline), and only after a historical
news source is identified and approved; B0 found no such data in the repository.
Blockchain work stays after the AI research track, as decided.
