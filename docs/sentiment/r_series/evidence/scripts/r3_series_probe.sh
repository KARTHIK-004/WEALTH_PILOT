#!/usr/bin/env bash
# R3 series 2: the same complete tests/training suite with the access-violation locator plugin, envB (pre-install reconstruction) and envA (current), interleaved.
cd /c/Users/Administrator/Desktop/Project/TEST
R=docs/sentiment/r_series/evidence
for i in 1 2; do
  for e in envB envA; do
    .venv/Scripts/python.exe -I $R/scripts/r3_runner.py --env $e --target tests/training --label "probe_$i" --av-probe --results $R/r3_results.jsonl
  done
done
echo SERIES2-DONE
