#!/usr/bin/env bash
# Sealed, database-free backend/training suites for the readiness audit. Sequential (never overlapping).
# Safeguards: DATABASE_URL, TEST_DATABASE_URL, GEMINI_API_KEY and PROTECTED_DATA_KEYS are set to EMPTY strings (they override .env in the application's Settings), so no test can obtain a
# database URL or call Gemini; the Python network guard additionally refuses non-local connections and lookups. Nothing here touches neondb or neondb_test.
# Usage: run_sealed_suites.sh <netguard_dir> <out_dir>
set -u
NETGUARD_DIR="$1"; OUT="$2"
cd /c/Users/Administrator/Desktop/Project/TEST || exit 2
PY=.venv/Scripts/python.exe
export DATABASE_URL= TEST_DATABASE_URL= GEMINI_API_KEY= PROTECTED_DATA_KEYS= PYTHONFAULTHANDLER=1
export PYTHONPATH=".;$NETGUARD_DIR"
run() {  # label, pytest args...
  label="$1"; shift
  start=$(date +%s)
  $PY -m pytest -p netguard -p no:cacheprovider -q -rfEs "$@" > "$OUT/sealed_$label.txt" 2>&1
  code=$?
  echo "$label exit=$code elapsed=$(( $(date +%s) - start ))s :: $(grep -E '[0-9]+ (passed|failed|error)' "$OUT/sealed_$label.txt" | tail -1)" | tee -a "$OUT/sealed_summary.txt"
}
: > "$OUT/sealed_summary.txt"
run core      tests/backend/core
run security  tests/backend/security
run data      tests/backend/data --ignore=tests/backend/data/test_ingestion.py
run pipeline  tests/backend/pipeline
run scripts   tests/backend/scripts
run agents7   tests/backend/agents/test_debate_gemini_client.py tests/backend/agents/test_debate_node.py tests/backend/agents/test_explanation_gemini_client.py tests/backend/agents/test_explanation_node.py tests/backend/agents/test_graph_construction.py tests/backend/agents/test_graph_routing.py tests/backend/agents/test_state.py
run training  tests/training
echo "ALL SEALED SUITES DONE" >> "$OUT/sealed_summary.txt"
