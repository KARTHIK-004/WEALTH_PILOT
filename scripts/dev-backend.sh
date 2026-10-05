#!/usr/bin/env bash
# Run the FastAPI dev server with reload. Blocks — run this yourself, don't
# ask an agent to run it in the foreground.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .venv/Scripts/activate ]; then source .venv/Scripts/activate; else source .venv/bin/activate; fi
cd backend
uvicorn wealthpilot.api.main:app --reload --app-dir .
