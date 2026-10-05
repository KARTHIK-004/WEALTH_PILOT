#!/usr/bin/env bash
# Create the backend virtualenv, install backend + dev deps, install frontend deps.
set -euo pipefail
cd "$(dirname "$0")/.."

python -m venv .venv
if [ -f .venv/Scripts/activate ]; then source .venv/Scripts/activate; else source .venv/bin/activate; fi
pip install --upgrade pip
pip install -e "backend[dev]"

(cd frontend && npm install)

echo "Install complete. Copy .env.example to .env and fill in real values."
