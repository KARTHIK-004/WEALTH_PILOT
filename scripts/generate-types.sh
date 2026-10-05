#!/usr/bin/env bash
# Regenerate frontend/src/types/api.ts from the live backend OpenAPI schema.
# The backend must already be running (see scripts/dev-backend.sh).
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm run generate-types
