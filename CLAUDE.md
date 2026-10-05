# WealthPilot AI — Claude Code Instructions

Agentic AI-Based Autonomous Financial Advisor for Personalized Wealth
Management. M.Tech educational/research prototype — not licensed
financial advice. Does not execute trades, transfer funds, or connect to
a brokerage for execution, ever.

## 1. Project

WealthPilot AI combines ML risk classification, behaviour-drift
detection, goal-funding math, market-regime analysis, portfolio
construction (MVO/HRP/1-N), a binding compliance gate, and an LLM
explanation layer into one analysis pipeline. Deterministic backend
calculation is the sole numerical authority; the frontend and Gemini only
display/restate what the backend already computed. Full product
description: `docs/PRD.md`.

## 2. Documentation Hierarchy

```
CLAUDE.md  (this file — concise entry point)
  -> docs/DECISIONS.md   permanent architectural decisions (ADRs)
  -> docs/RULES.md        detailed development rulebook
  -> docs/ARCHITECTURE.md current system wiring, as verified
  -> docs/PRD.md          product requirements
  -> docs/DESIGN.md       frontend visual/interaction system
  -> docs/SECURITY.md     security posture and disclosed limitations
  -> docs/TEST_PLAN.md    testing strategy and actual commands
  -> docs/MEMORY.md       CURRENT project state (not historical)
  -> TASKS.md             phase/task tracker
  -> reports/             historical, phase-by-phase completion reports
```

Additionally, `docs/PROJECT_PLAN.md` (methodology/spec) and
`docs/MASTER_PROMPT.md` (feature/page checklist) are this project's own
original specification documents, reconciled into
`docs/BUILD_PLAN.md` (the authoritative phase-by-phase plan). On
architecture (package layout, dependency choices, API route style, phase
numbering), **this file and `docs/PROJECT_PLAN.md` win** over
`docs/MASTER_PROMPT.md` — an explicit decision made 2026-09-13, recorded
in `docs/DECISIONS.md`. If current source code and a document disagree,
do not silently pick one — see `docs/RULES.md` Rule 29.

## 3. Before Coding

For every non-trivial task: (1) read the relevant documentation above and
the most relevant `reports/*.md`; (2) inspect the existing implementation
— do not assume, verify; (3) identify reusable code and affected files;
(4) make a short implementation plan for anything touching more than
three files; (5) implement only the requested scope; (6) run the relevant
tests, then the full regression suite; (7) update `docs/MEMORY.md` if
state changed materially; (8) report exact changes in whatever format
was requested; (9) STOP. Do not start coding from only the final sentence
of a long prompt — read the whole thing first.

## 4. Scope Control

Do not refactor unrelated code, replace an approved library, redesign
unrelated UI, change the database schema unnecessarily, retrain a model
unnecessarily, or modify a completed phase's behavior unless the current
task explicitly requires it. If you find an unrelated issue, document it
— do not silently fix it. Never start the next phase without explicit
instruction; a bare "continue" resumes in-progress work, it is not
approval for new scope.

## 5. Approved Technology Stack

**Backend** — Python 3.11 · FastAPI · uvicorn · SQLAlchemy · Alembic ·
PostgreSQL · LangGraph · AutoGen · google-genai · scikit-learn · XGBoost ·
TensorFlow · statsmodels · arch · yfinance · SHAP · pandas · numpy ·
scipy · Pydantic v2 · pydantic-settings. `scipy` is approved specifically
for constrained numerical optimization in the portfolio optimizer
(box-constrained MVO); Ledoit-Wolf shrinkage itself comes from
`scikit-learn.covariance`.

**Frontend** — React 19 · Vite · TypeScript · Tailwind CSS · shadcn/ui ·
TanStack Query · React Router · Recharts · lucide-react.

No Docker, no Next.js — both halves run natively. Do not add a library
outside this list without asking first.

## 6. Frontend Rules

The frontend never computes a financial number (risk, financial health,
goal feasibility, Monte Carlo probability, required contribution,
emergency-fund status, portfolio weight, compliance decision,
recommendation strategy) — only formatting, form-shape validation, and UI
state. TypeScript types are generated from the live OpenAPI schema
(`npm run generate-types`), never hand-written. shadcn/ui is the only
primitive component system. Full detail: `.claude/rules/frontend.md`,
`docs/DESIGN.md`.

## 7. Backend Rules

Layering: API route → `api/services/` orchestration → `core/`/`agents/`
domain logic → `db/models.py`. Public API schemas (`api/schemas.py`) are
deliberately separate from internal `agents/state.py`/`core/*.py`
models. RFC 7807 for every error. Any schema change is an Alembic
migration applied to both `DATABASE_URL` and `TEST_DATABASE_URL`. Full
detail: `.claude/rules/backend.md`, `docs/ARCHITECTURE.md` §5-9.

## 8. ML Rules

Train offline only, in `training/<family>/`, writing to
`models/<family>/`; nothing trains inside a request, a LangGraph node, or
an agent. No shuffled splits on time series — expanding-window
walk-forward with an embargo gap; market models target returns/
volatility, never price levels. `random_state=42` everywhere. Full
detail: `.claude/rules/ml.md`.

## 9. Data Leakage Rules

Never use future information — no future transactions, no future market
data, no preprocessor fit on data including the held-out fold, no target
information leaking into a feature. Filter FAR-Trans's `Predicted_*`/
`Not_Available` rows before training. This applies even to a "static"
per-entity classification framing — point-in-time correctness still
applies. Full detail: `docs/DECISIONS.md` ADR-008, `docs/RULES.md`
Rule 8-9.

## 10. Financial Logic Rules

Never invent a financial formula, threshold, or methodology decision not
already specified in `docs/PROJECT_PLAN.md`/`docs/MASTER_PROMPT.md` or
already implemented in `core/`. Gemini never computes a number — it
receives an already-computed dict and writes validated prose. The
frontend never computes a number either — if one is needed, add an API
field. Full detail: `docs/DECISIONS.md` ADR-014.

## 11. Compliance Rules

Compliance is binding and fail-closed. Precedence: Compliance >
Savings-first > Risk > Goal > Market. A REJECT verdict cannot reach the
explanation node or the API response — `enforce_gate` raises and nothing
catches it. Rules live in `config/compliance_rules.yaml`; each has a unit
test. Do not weaken a rule, remove one, or change precedence without an
explicit, scoped instruction — see `docs/DECISIONS.md` ADR-018 for the
one precedent and how narrowly it was scoped.

## 12. Missing Data Rules

Distinguish zero, unknown/not-yet-provided, structurally unavailable, and
not-yet-evaluated. Represent unknown/unavailable as `null` plus an
`*_unavailable_reason` string, in the database, the API, and the
frontend — never as `0`, never guessed, never silently defaulted.

## 13. Demo Rules

Demo personas are synthetic identity + real pipeline output — never a
hand-inserted result. New demo data goes through the real public API
(`backend/scripts/seed_demo_data.py`), with exactly one documented
exception (`risk_inputs.external_customer_id`, which has no public API).
Never hard-code a demo customer's numeric id into a frontend page
component.

## 14. Customer Isolation

Authenticated users resolve to their associated customer automatically —
no manual customer-id entry, no customer-switching UI, ever, unless
explicitly requested. Every per-customer query is scoped by
`customer_id`/`profile_id` at the ORM level. Household membership
(Phase 32, `docs/RULES.md` Rule 31) is contextual identity only — never an
input to individual analysis, and never account switching; household routes
require the caller's `X-Customer-Id` and authorize against membership. A
household's own financial records (Phase 33, Rule 32, ADR-032) are stored
source data: any member reads, only the primary writes. Phase 34 (Rule 33,
ADR-033) adds one read-only summary over them — all arithmetic in
`core/household_finance.py`, nothing persisted, NULL never zero — and **no
household figure reaches `POST /api/analysis` or any advice path**: no
household savings rate, debt ratio, score, goal feasibility, risk profile,
portfolio or recommendation exists. Phase 35 (Rule 34, ADR-034) added only
optional metadata (`notes`, `description`, `interest_rate`) that no
calculation reads; `is_active` remains the activity rule. Phase 36 (Rule 35,
ADR-035) added `household_goals` — stored facts only, separate from individual
`financial_goals`, with no goal math (the assumptions `core/goals.py` needs do
not exist for a household) and the emergency-fund requirement still computed
only by the Phase 34 summary.

## 15. API Rules

Pydantic v2 schemas; frontend TypeScript types generated from OpenAPI,
never hand-duplicated; RFC 7807 problem-details errors; every
analysis-adjacent response carries `model_version` and `data_source`.
Long graph runs stream over SSE at `/api/analysis/stream`, one progress
event per node (name/status/duration/summary) — never chain-of-thought.

## 16. Database Rules

PostgreSQL via SQLAlchemy; Alembic migrations, always applied to both
the dev and test databases. Prefer reusing existing schema; when a new
table is genuinely needed, one table per persistence concern (not new
columns bolted onto `customers`).

## 17. UI Rules

shadcn/ui as the primary — and only — component system; reuse existing
components. Follow `docs/DESIGN.md`. Every API-dependent page handles
loading/empty/unavailable/error/success. Never hide missing information.

## 18. Security Rules

Never commit or log a secret. Never expose Gemini/AutoGen chain-of
-thought or a raw exception to the frontend. Prototype authentication is
intentionally minimal and disclosed as such — do not silently build out
production-grade auth. Full detail: `docs/SECURITY.md`.

## 19. Testing

Backend: `pytest tests/ -v`, run in isolation (no concurrent process
touching either database); for a long run, avoid piping through `tail` —
it hides real progress. Frontend: `npx tsc -b`, `npm run build`,
`npx oxlint`. Up to 3 live-Gemini tests skip when Gemini is unavailable
or out of quota. The databases are hosted, so a network drop mid-run can
produce a burst of DB failures — classify each failure from its own
traceback (network vs assertion) and re-run in isolation before
concluding anything; see `docs/TEST_PLAN.md` §"Transient Failures." Never
claim completion with a failing required test, and never claim a clean
run that did not happen.

## 20. Documentation Rules

Update `docs/MEMORY.md` when current state changes materially. Add a new
ADR to `docs/DECISIONS.md` when an architectural decision is made or
superseded — never silently edit an accepted ADR's substance. Leave
historical `reports/*.md` intact; add a superseded-by note inside an old
report rather than rewriting it.

## 21. Phase Discipline

Work proceeds phase-by-phase. Implement only the requested phase; test;
verify; document; report in the requested format; STOP. Wait for explicit
instruction before starting another phase.

## 22. Completion Standard

Not complete until: the change is implemented within its stated scope;
tests pass (or a failure is diagnosed as a known transient artifact via
isolated re-run); `docs/MEMORY.md` is updated if state changed; and the
report is honest about what was and was not verified — never claim
browser-based visual testing occurred without an actual headless-browser
tool having been used for it.

## 23. Current Project State

See `docs/MEMORY.md` for the authoritative, current-state summary — do
not restate or duplicate it here; this section is a pointer, not a copy,
so it can never drift out of sync with the real record.

## 24. Final Response

State exactly what was done, in the format the task requested. If a task
specified an exact final-message format (a literal opening line, a
numbered summary), use it verbatim — do not paraphrase or reorder it.

## Repository Layout

```text
backend/
  pyproject.toml
  wealthpilot/
    config/      settings, logging
    db/          models, session, migrations
    data/        acquisition, quality, preprocessing — code only, no data files
    core/        goal math, optimizer, compliance — deterministic
    agents/      state, nodes, graph, debate, explanation, recommendation
    api/         routers, schemas, dependencies, sse, services
training/        one script per model family
  risk/  expense/  behaviour/  market/  portfolio/
models/          serialized artifacts + metrics.json
  risk/  expense/  behaviour/  market/
datasets/raw/    downloaded data, gitignored — .gitkeep tracked
  FAR-Trans/     customer_information.csv, asset_information.csv, markets.csv,
                 close_prices.csv, limit_prices.csv, transactions.csv,
                 questionnaires.csv
  kaggle/        personal-finance-ml-dataset (or the chosen alternative),
                 original downloaded filename kept as-is
  generated/     synthetic ML training dataset (CSVs git-ignored; regenerate with
                 scripts/generate_wealthpilot_synthetic_dataset.py, seed 42) --
                 not read by any training script; see ADR-039
demo_data/       synthetic demo dataset (seed input only, NEVER ML training
                 data) -- README.md, manifest.json; see ADR-038
config/
  compliance_rules.yaml
tests/
frontend/
  src/
    components/ui/   shadcn primitives — added via CLI, not hand-written
    components/      app components (charts/, portfolio/, profile/, shell/)
    pages/           one file per route
    lib/             api-client.ts (typed fetch), format.ts, demo-customer.ts
    types/api.ts     GENERATED — never edit by hand
    hooks/
    providers/
docs/
reports/
scripts/
```

`training/`, `models/`, `datasets/`, `config/`, and `tests/` are
top-level, siblings of `backend/` and `frontend/` — **not** nested inside
`backend/`. `datasets/raw/` is the single canonical location for
original/downloaded data; nothing downloaded or acquired is ever placed
inside `backend/wealthpilot/`, and no trained model artifact is ever
placed inside `datasets/`. `backend/wealthpilot/data/` holds acquisition,
quality and preprocessing *code* that reads from `datasets/raw/` and
writes to PostgreSQL — never data files themselves.

## Working Style

Plan before coding on any stage touching more than three files. Tests
alongside code, not after. Type hints everywhere in Python; no `any` in
TypeScript. Add shadcn components with `npx shadcn@latest add <name>` —
do not hand-write primitives the CLI provides. Do not run training jobs
or long-lived servers yourself — write it, then tell the user the
command (for a one-off need like OpenAPI-schema generation, call
`app.openapi()` directly in a short Python process instead of starting a
server). Small commits, conventional messages, only when explicitly
asked to commit.
