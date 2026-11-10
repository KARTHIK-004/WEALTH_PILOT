# WealthPilot AI

Agentic AI-based autonomous financial advisor — an M.Tech case-study
prototype. Educational decision-support only, not licensed financial advice;
does not execute trades, transfer funds, or perform any autonomous financial
transaction.

## Documentation

Start with [`CLAUDE.md`](CLAUDE.md) (the Claude Code entry point) or, for
a human/reviewer overview, [`docs/PRD.md`](docs/PRD.md). Full hierarchy:

1. [`CLAUDE.md`](CLAUDE.md) — stack, non-negotiable rules, repository layout
2. [`docs/PRD.md`](docs/PRD.md) — product requirements and current
   implementation status
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design, as
   verified against source
4. [`docs/DECISIONS.md`](docs/DECISIONS.md) — permanent architectural
   decisions (ADRs)
5. [`docs/MEMORY.md`](docs/MEMORY.md) — current project state
6. [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — data sources, model
   selection and comparison, training inventory, risks
7. [`docs/MASTER_PROMPT.md`](docs/MASTER_PROMPT.md) — feature/requirements
   checklist, page-by-page UI spec (architecture notes at the top explain how
   this relates to the two documents above)
8. [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) — the authoritative,
   phase-by-phase implementation plan

See also [`docs/DESIGN.md`](docs/DESIGN.md), [`docs/SECURITY.md`](docs/SECURITY.md),
[`docs/TEST_PLAN.md`](docs/TEST_PLAN.md), [`docs/RULES.md`](docs/RULES.md),
and [`TASKS.md`](TASKS.md).

## Status

All planned phases through Phase 31 (Final Demo Readiness)
are implemented, tested, and documented — see
[`docs/MEMORY.md`](docs/MEMORY.md) for the current, authoritative state
and [`TASKS.md`](TASKS.md) for the full phase checklist.

## Stack

Backend: Python 3.11, FastAPI, LangGraph, AutoGen, Gemini, SQLAlchemy +
Alembic, PostgreSQL, scikit-learn, XGBoost, TensorFlow, statsmodels, arch,
yfinance, SHAP.

Frontend: React 19, Vite, TypeScript, Tailwind CSS, shadcn/ui, TanStack
Query, React Router, Recharts.

No Docker, no Next.js — services run natively.

## Repository layout

```
backend/wealthpilot/   FastAPI app, agents, core financial engines, data code
training/               one script per model family
models/                 serialized artifacts + metrics.json
datasets/raw/           downloaded FAR-Trans / Kaggle data (gitignored)
config/                 compliance_rules.yaml
tests/
frontend/               React + Vite + shadcn/ui
docs/
reports/                evaluation and case-study output (Phase 19)
```

## Development setup

See `scripts/` for the commands each of the steps below wraps.

### Backend

```
cd backend
python -m venv ../.venv
../.venv/Scripts/activate        # Windows; use `source ../.venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
cp ../.env.example ../.env       # then fill in real values
# the repo root must be on PYTHONPATH (startup imports the top-level training/ package):
set PYTHONPATH=..                  # Windows cmd.exe
$env:PYTHONPATH = ".."             # Windows PowerShell
export PYTHONPATH=..               # macOS/Linux
uvicorn wealthpilot.api.main:app --reload --app-dir .
```

Without `PYTHONPATH`, startup fails with `ModuleNotFoundError: No module named 'training'`.

Health check: `http://localhost:8000/api/health`

### Frontend

```
cd frontend
npm install
npm run dev
```

Dev server: `http://localhost:5173`

### Tests

```
pytest
```

### Running the demo

With the backend and frontend running and the demo personas seeded
(`scripts/seed_demo_data.sh verify` lists them; `setup` seeds a fresh
environment), open `http://localhost:5173/login` and click **Use Demo
Account** — it resolves to the seeded "WealthPilot Demo — Complete"
customer (approved MVO recommendation). The savings-first and compliance-
rejected personas are shown through the API explorer at
`http://localhost:8000/docs`, since the app deliberately has no customer
switcher. The click-by-click script is [`docs/final_demo_script.md`](docs/final_demo_script.md),
viva answers are in [`docs/final_viva_talking_points.md`](docs/final_viva_talking_points.md),
and the longer narrative is [`docs/demo_runbook.md`](docs/demo_runbook.md).

### Regenerate frontend API types

With the backend running:

```
cd frontend
npm run generate-types
```

This writes `frontend/src/types/api.ts` from the live OpenAPI schema. Never
hand-edit that file.

## Windows note on `make`

A `Makefile` is provided for reference and for contributors with GNU Make
available (e.g. via WSL). On a plain Windows/PowerShell machine without
`make`, use the equivalent commands in `scripts/` or above directly.
