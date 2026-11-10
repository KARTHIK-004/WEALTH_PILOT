#!/usr/bin/env bash
# R3 series 3: STRICTLY SEQUENTIAL complete tests/training runs, interleaved envA / envB, no other test activity on the machine, identical command (plain runner, no locator plugin).
cd /c/Users/Administrator/Desktop/Project/TEST
R=docs/sentiment/r_series/evidence
for i in 1 2 3; do
  for e in envA envB; do
    .venv/Scripts/python.exe -I $R/scripts/r3_runner.py --env $e --target tests/training --label "clean_$i" --results $R/r3_results.jsonl
  done
done
echo SERIES3-DONE
