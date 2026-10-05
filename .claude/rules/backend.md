# Backend Rules

Quick-reference for `backend/wealthpilot/`. Full detail: `docs/RULES.md`,
`docs/ARCHITECTURE.md` §5-9.

- FastAPI + Pydantic v2 + SQLAlchemy + Alembic + PostgreSQL. Python 3.11,
  type hints everywhere.
- Layer discipline: API route → `api/services/` orchestration →
  `core/`/`agents/` domain logic → `db/models.py`. Do not put a large
  financial calculation directly inside a route handler.
- `api/schemas.py` models are deliberately separate from internal
  `agents/state.py`/`core/*.py` models — never leak a DB session, model
  object, or agent-internal concept through the public API contract.
- Errors: RFC 7807 problem+json (`api/errors.py`) — never a bare 500 or
  an unstructured error string.
- Any schema change ships as an Alembic migration
  (`alembic revision --autogenerate`), applied to BOTH `DATABASE_URL` and
  (`ALEMBIC_TARGET=test alembic upgrade head`) `TEST_DATABASE_URL`.
  Prefer reusing an existing table/column; when a new table is genuinely
  needed, follow the one-table-per-persistence-concern pattern
  (`financial_goals`, `questionnaire_answers`, `financial_inputs`), not
  new columns bolted onto `customers`.
- No request-time training. Training lives only in `training/`, writes
  only to `models/`, runs only when a human explicitly invokes it.
- Backend is the sole numerical authority — every financial number is
  computed exactly once in `core/` or a trained model. Never duplicate a
  calculation in a second code path.
- Missing data is `null` + an `*_unavailable_reason` string — never `0`,
  never guessed, never silently defaulted.
- Household routes (Phase 32) require the caller's associated customer in
  `X-Customer-Id` (`api/dependencies.py::get_acting_customer_id`) and
  authorize against membership in `api/services/household_service.py`;
  `households`/`household_members` are identity/membership only — no financial
  fields, no effect on `POST /api/analysis` (`docs/RULES.md` Rule 31, ADR-031).
- Household financial records (Phase 33: `household_incomes`,
  `household_expenses`, `household_assets`, `household_liabilities`,
  `api/services/household_finance_service.py`) are **stored source data only** —
  never add a derived figure to those models, services, routes or schemas
  (`docs/RULES.md` Rule 32, ADR-032). Any member may read; only the primary may
  write; `household_id` comes from the path only; a record id from another
  household is a 404, never a 403.
- Household aggregation (Phase 34) lives ONLY in `core/household_finance.py` —
  pure, DB-free, `Decimal`, no clock, no ML, no LLM — orchestrated by
  `api/services/household_summary_service.py` and exposed by the single
  read-only route `GET /api/households/{id}/financial-summary`. Nothing is
  persisted and nothing is recomputed elsewhere. Never add a savings rate, debt
  ratio, score, contribution capacity, goal feasibility, household risk or
  household recommendation, and never feed a household figure into
  `POST /api/analysis` (`docs/RULES.md` Rule 33, ADR-033).
- Phase 35 metadata (`notes`, asset/liability `description`, liability
  `interest_rate`) is optional, factual and never computed with — the engine's
  input records have no field for it. Do not add date-window activity rules or
  relax `amount > 0` / nullable `monthly_payment` without a new ADR
  (`docs/RULES.md` Rule 34, ADR-034).
- Household goals (Phase 36, `household_goals`,
  `api/services/household_goal_service.py`) are stored facts, separate from the
  individual `financial_goals`. Never compute goal math for them, never touch
  `financial_goals` or `core/goals.py` on their behalf, and never compute a
  second emergency-fund requirement (`docs/RULES.md` Rule 35, ADR-035).
- Every per-customer route/query is scoped by `customer_id`/`profile_id`
  at the ORM level — never an unscoped query narrowed client-side.
- Do not run a long-lived server (`uvicorn`) yourself for a one-off task
  like OpenAPI-schema generation — call `app.openapi()` directly in a
  short Python process instead. `PYTHONPATH` must include the repo root
  (not just `backend/`) for any one-off script that imports from
  `agents/nodes.py` (which imports `training.*`).
