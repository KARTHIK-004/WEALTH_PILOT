#!/usr/bin/env bash
# R4: test-only DLL guard, before/after in ONE project .venv, strictly sequential and interleaved. baseline = guard switched off (WEALTHPILOT_NVIDIA_DLL_GUARD=0); guarded = default.
cd /c/Users/Administrator/Desktop/Project/TEST
R=docs/sentiment/r_series/evidence
run() { .venv/Scripts/python.exe -I $R/scripts/r3_runner.py --env project --target tests/training --results $R/r4_results.jsonl "$@"; }
run --label base_1 --env-var WEALTHPILOT_NVIDIA_DLL_GUARD=0
run --label guard_1
run --label base_2 --env-var WEALTHPILOT_NVIDIA_DLL_GUARD=0
run --label guard_2
run --label guard_3
run --label base_3 --env-var WEALTHPILOT_NVIDIA_DLL_GUARD=0
run --label guard_4
run --label guard_5
echo R4-SERIES-DONE
