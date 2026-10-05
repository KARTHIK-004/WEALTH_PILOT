# WealthPilot AI — Task Tracker

## Current Task

None in progress. Phase 36 (Household Goals & Emergency-Fund Planning) is
the most recent completed task.

## Current Phase

Phase 36 is the most recently completed phase. No phase is currently in
progress, and no further phase is authorized.

## Completed Phases

Status determined from `reports/*.md` and verified source state, not
assumed — see `docs/MEMORY.md` for the current, authoritative state
summary.

- [x] Phase 0 — Foundation
- [x] Phase 1 — Initial schema
- [x] Phase 2 — Data quality (`reports/phase2_data_quality_report.md`)
- [x] Phase 3 — Leakage audit (`reports/phase3_leakage_audit.md`)
- [x] Phase 4 — Risk classification (`reports/phase4_risk_classification_report.md`)
- [x] Phase 5 — Expense segmentation + behaviour detection
      (`reports/phase5_expense_segmentation_report.md`,
      `reports/phase5_behaviour_detection_report.md`)
- [x] Phase 6 — Market analysis (`reports/phase6_market_analysis_report.md`)
- [x] Phase 7 — Goal engine (`reports/phase7_goal_engine_report.md`)
- [x] Phase 8 — Portfolio optimization
      (`reports/phase8_portfolio_optimization_report.md`)
- [x] Phase 9 — Compliance (`reports/phase9_compliance_report.md`)
- [x] Phase 10 — Agent state/nodes
      (`reports/phase10_agent_state_nodes_report.md`)
- [x] Phase 11 — LangGraph (`reports/phase11_langgraph_report.md`)
- [x] Phase 12 — AutoGen debate (`reports/phase12_autogen_debate_report.md`)
- [x] Phase 13 — Gemini explanation
      (`reports/phase13_gemini_explanation_report.md`)
- [x] Phase 14 — Recommendation engine
      (`reports/phase14_recommendation_engine_report.md`)
- [x] Phase 15 — FastAPI (`reports/phase15_fastapi_report.md`)
- [x] Phase 16 — React shell (`reports/phase16_react_shell_report.md`)
- [x] Phase 17 — React pages 1-5
      (`reports/phase17_react_pages_1_5_report.md`)
- [x] Phase 18 — React pages 6-9
      (`reports/phase18_react_pages_6_9_report.md`)
- [x] Phase 19 — Final evaluation
      (`reports/phase19_final_evaluation_report.md`)
- [x] Phase 20 — Login (`reports/phase20_login_report.md`)
- [x] Phase 21 — Create user (`reports/phase21_create_user_report.md`)
- [x] Phase 22 — Onboarding (`reports/phase22_onboarding_report.md`)
- [x] Phase 23 — Persistence (`reports/phase23_persistence_report.md`)
- [x] Phase 24 — Demo account (`reports/phase24_demo_account_report.md`)
- [x] Phase 25 — Final UX polish (`reports/phase25_final_ux_report.md`)
- [x] Demo Data phase (`reports/demo_data_completion_report.md`,
      `reports/demo_dataset_catalog.md`) — not numbered in its own
      filename; completed after Phase 25.
- [x] Live Analysis Flow phase
      (`reports/live_analysis_flow_fix_report.md`) — not numbered in its
      own filename; completed after the Demo Data phase.
- [x] Post-Login Profile Flow fix
      (`reports/post_login_profile_flow_report.md`) — not numbered in its
      own filename; completed alongside/after the Live Analysis Flow
      phase.
- [x] Phase 28 — Financial Input & Savings-First Integration
      (`reports/phase28_financial_input_savings_first_report.md`)
- [x] Documentation system setup (this tracker, `docs/PRD.md`,
      `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/TEST_PLAN.md`,
      `docs/SECURITY.md`, `docs/DECISIONS.md`, `docs/MEMORY.md`,
      `docs/RULES.md`, `.claude/rules/*.md`)
- [x] Phase 29 — Final Integration & Validation — COMPLETE
      (`reports/phase29_final_integration_report.md`). Verified the whole
      chain end to end against the real pipeline (all four demo personas,
      SSE, isolation, RFC 7807, API contract, database head, security
      scan, model/dataset integrity); final isolated backend run 763
      passed, 3 skipped, 0 failed; frontend tsc/oxlint/build clean
      (frontend journeys verified at source level only — no browser tool
      exists). Found and fixed four defects in the Phase 28 baseline: goal
      Monte Carlo fed daily returns for monthly periods (every goal showed
      a spurious 0.0%); no page rendered compliance rule reasons (a
      rejected analysis showed only a generic sentence); the
      `savings_first` SSE summary claimed "insufficient" even when
      sufficiency was unknown; `GET /api/profiles/lookup` was
      nondeterministic when a customer name repeats. Also added a pipeline
      version to the analysis cache key so a computation fix invalidates
      stale cached results.

- [x] Phase 30 — Analytics Graphs & Visualization — COMPLETE
      (`reports/phase30_analytics_visualization_report.md`). Display-only
      Recharts components in `frontend/src/components/charts/`: risk
      probabilities, emergency fund (required vs current, backend
      shortfall as text), goal target vs inflation-adjusted target,
      portfolio allocation donut (approved only), scenario comparison, and
      an Agent Activity pipeline view drawn only from received SSE events.
      Savings-first shows no allocation, rejected shows the compliance
      breakdown and no chart, pending shows nothing. Goals page shows
      corrected Monte Carlo values to one decimal and a note when the
      backend's `contribution_gap` is negative. No backend, model, dataset
      or schema change; `types/api.ts` regenerated (comment-only diff).
      No risk/return or frontier chart (the API has no frontier data).
      Final isolated backend run 763 passed, 3 skipped, 0 failed; tsc 0
      errors, oxlint 0 errors / 8 baseline warnings, build succeeds.
      Verified at source level plus a server-side render of the real
      components against real API data — no browser tool exists.

- [x] Phase 31 — Final Demo Readiness — COMPLETE
      (`reports/phase31_final_demo_readiness_report.md`). End-to-end audit
      of the whole application for the live demo and viva: routes and
      navigation, identity, profile / financial inputs / questionnaire,
      goals, every page's approved / savings-first / rejected / pending
      rendering, loading / error / empty / no-profile states, accessibility
      and responsive source audit, bundle analysis, secret scan (NOT
      FOUND), and a rollback-safe live regression of every API route (56
      checks) plus a 71-check server-side render of the real app against the
      four demo personas — no browser tool exists. Fixed: "Use Demo
      Account" could stay on the blank fallback customer in a browser that
      had remembered it (ADR-030); the Why page's fallback alert misstated
      the cause and did not label AI wording vs template; the Dashboard said
      "No goals recorded" for a profile with unevaluated goals; empty
      financial-input fields were not visibly "not provided"; the
      questionnaire was unreachable after account creation. Added
      `docs/final_demo_script.md` and `docs/final_viva_talking_points.md`.
      No backend, model, dataset or schema change; backend suite 763
      passed, 3 skipped, 0 failed.

- [x] Phase 32 — Household Foundation & Family Member Association —
      COMPLETE (`reports/phase32_household_foundation_report.md`).
      Introduced a first-class Household linked to customers through a
      membership table (`Customer -> Household Membership -> Household`,
      ADR-031): new `households`/`household_members` tables and migration
      `f59ab6395383` (applied to dev and test), six API routes (create,
      get, profile-household, list/add/remove members — no deletion
      route), controlled relationship/role vocabularies, and the
      membership rules enforced in the database AND the service (one
      household per customer, one primary per household, primary =
      `self`, `self` never a dependent, no duplicates, primary cannot be
      removed). Household routes authorize against membership using the
      caller's `X-Customer-Id`; a Household card was added to the Customer
      Profile page. **Identity and membership only — no household
      financial data, no household calculations, and `POST /api/analysis`
      is provably unchanged.** The existing `customers` table and the four
      demo personas were untouched.
- [x] Phase 33 — Household Financial Data Foundation —
      COMPLETE (`reports/phase33_household_financial_data_report.md`).
      Gave a household somewhere to store its OWN financial information:
      four independent tables (`household_incomes`, `household_expenses`,
      `household_assets`, `household_liabilities`) and migration
      `d2be70d8b07f` (applied to dev and test), each owned by a household
      through `household_id` alone with no `customer_id`; 16 API routes
      (list/create/update/delete per resource) reusing the Phase 32
      `X-Customer-Id` authorization — any member reads, only the primary
      writes, a record id from another household is a 404; controlled
      vocabularies for frequency/category/asset type/liability type with
      free-text income source; NULL kept distinct from zero (nullable
      `monthly_payment`, defaultless `is_essential`); and four new tabs on
      the Customer Profile page's Household card. **Data foundation only:
      no total, net worth, savings rate, debt ratio or any other derived
      figure is computed anywhere — no summary endpoint, no summary screen,
      no arithmetic in React — and `POST /api/analysis`, the individual
      financial-input system, the ML models, compliance and the agent
      pipeline are provably unchanged (ADR-032, `docs/RULES.md` Rule 32).**

- [x] Phase 34 — Household Financial Aggregation, Emergency Fund & Goal
      Foundation — COMPLETE
      (`reports/phase34_household_financial_aggregation_report.md`).
      Added the first household-level interpretation of the Phase 33
      records: a deterministic, read-only summary computed entirely in the
      new pure module `core/household_finance.py` (monthly normalization —
      yearly counted as amount/12, one-time never made recurring; active
      records only; aggregated income, expenses, assets and liabilities;
      monthly cash flow; net position; and an emergency-fund position
      reusing `core/goals.py`'s 6-month constant and `current >= required`
      comparison), orchestrated by
      `api/services/household_summary_service.py` and served by ONE
      read-only route, `GET /api/households/{id}/financial-summary`
      (ADR-033, `docs/RULES.md` Rule 33). **No database change at all** —
      no table, column or migration — because nothing derived is
      persisted. NULL stays distinct from zero everywhere, including a
      recorded zero being a known fact while an absent record is unknown.
      **Reports only: no savings rate, debt ratio, score, ranking, goal
      feasibility, Monte Carlo, household risk, portfolio or
      recommendation, and no household figure reaches
      `POST /api/analysis`.** Also corrected a Phase 32 route-inventory
      test that Phase 33 had left failing.

- [x] Phase 35 — Household Financial Data Persistence & Management —
      COMPLETE (`reports/phase35_household_financial_persistence_report.md`).
      Found the specified tables, CRUD routes and summary integration already
      built by Phases 33/34; with the owner's agreement added only optional
      factual metadata (migration `a7c41e9b6f30`: `notes` on all four tables,
      `description` on assets/liabilities, `interest_rate` on liabilities),
      kept `is_active` and ADR-032's constraints (ADR-034). Added a
      database-free migration-history test.
- [x] Phase 36 — Household Goals & Emergency-Fund Planning — COMPLETE
      (`reports/phase36_household_goals_report.md`). New `household_goals`
      table (migration `c3e8f2a9d154`) and five routes: household goals as
      stored facts, separate from individual `financial_goals`, with no goal
      math and the emergency-fund requirement still computed only by the
      Phase 34 summary (ADR-035). Goals tab on the household card. Found and
      documented (not fixed) two pre-existing 500-instead-of-422 defects in
      the Phase 33 record schemas.

- [x] Demo experience update — Individual + Family demo (not a numbered
      phase; no Phase 37). `reports/family_demo_report.md`. The login page
      offers "Use Individual Demo" (unchanged resolution) and "Use Family
      Demo" (the canonical "WealthPilot Demo Family" household, seeded
      idempotently through the public household API from two existing
      personas). No schema, model, pipeline or individual-analysis change
      (ADR-036).

- [ ] Plain-language explanation enhancement (not a numbered phase; ADR-037):
      DONE: the Simple / Detailed views on Why This Recommendation. The Simple
      view is built from deterministic fields. NOT DONE: the backend part —
      the plain-language prompt, the stricter validation (ticker attribution,
      derived counts, grouped amounts) and the plainer fallback. It is
      prepared, but not applied or validated; its pre-patch full-suite run was
      interrupted.

- [x] Synthetic ML training dataset (not a numbered phase; ADR-039):
      `datasets/generated/` holds 100,000 customers, 2,642,361 transactions
      and 325,290 goals, plus copies in the FAR-Trans and Kaggle formats.
      There is a seeded generator and a validator. No production or training
      code changed, and the dataset is not wired into any training script.

- [x] Complete demo dataset package (not a numbered phase; ADR-038):
      `demo_data/` holds personas A–D, the family household, scenarios,
      expected outcomes and a manifest. `seed_demo_data.py` reads it, and
      `validate_demo_data.py` validates it. Individual analyses and the family
      household are unchanged.

Note: there is no report numbered "Phase 26" or "Phase 27" — the three
non-numbered-filename phases above occupy that position in the project's
actual chronological history, ahead of Phase 28. Do not assume a
"Phase 26"/"Phase 27" report exists; it does not.

## Active Work

None.

## Blocked Work

None.

## Pending Work

None scheduled. See `docs/PRD.md` §40 (Future Scope) and
`docs/MEMORY.md`'s "Pending Work" for the current, authoritative
statement — this section should always agree with that one.

## Future Phases

None scheduled. Any future phase requires explicit instruction before
starting, per `docs/RULES.md` Rule 28 (Phase Discipline).
