#!/usr/bin/env bash
# R3 series 1: the complete tests/training suite, interleaved A,B,A,B... so memory pressure and machine state are shared evenly. Identical command in every environment.
cd /c/Users/Administrator/Desktop/Project/TEST
R=docs/sentiment/r_series/evidence
for i in 1 2 3 4 5; do
  for e in envA envB; do
    .venv/Scripts/python.exe -I $R/scripts/r3_runner.py --env $e --target tests/training --label "full_$i" --results $R/r3_results.jsonl
  done
done
echo SERIES1-DONE
