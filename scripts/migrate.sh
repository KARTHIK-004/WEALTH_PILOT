#!/usr/bin/env bash
# Apply Alembic migrations. No-op until Phase 1 adds the Alembic environment.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .venv/Scripts/activate ]; then source .venv/Scripts/activate; else source .venv/bin/activate; fi
cd backend
alembic upgrade head
