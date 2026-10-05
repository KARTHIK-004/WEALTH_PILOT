#!/usr/bin/env bash
# Validate WealthPilot AI's synthetic demo dataset (demo_data/, ADR-038).
# Static: no database, no server. Exits non-zero on any failure. Usage:
#   scripts/validate_demo_data.sh                    # validate
#   scripts/validate_demo_data.sh --write-manifest   # regenerate the manifest, then validate
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .venv/Scripts/activate ]; then source .venv/Scripts/activate; else source .venv/bin/activate; fi
python backend/scripts/validate_demo_data.py "$@"
