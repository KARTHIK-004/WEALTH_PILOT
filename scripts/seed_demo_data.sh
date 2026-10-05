#!/usr/bin/env bash
# Set up / verify / reset WealthPilot AI's synthetic demo customer
# population from demo_data/ (ADR-038). Requires a running backend
# (see `scripts/dev-backend.sh`) unless --in-process is given. Usage:
#   scripts/seed_demo_data.sh setup|verify|reset [--base-url URL | --in-process]
#   scripts/seed_demo_data.sh setup-family|verify-family|reset-family [--in-process]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .venv/Scripts/activate ]; then source .venv/Scripts/activate; else source .venv/bin/activate; fi
cd backend
python scripts/seed_demo_data.py "$@"
