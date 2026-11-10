#!/usr/bin/env bash
# R3 series 4: causal test. Strictly sequential, interleaved: envB without the intervention, envB with nvdxgdmal64.dll pinned (x3 pairs), then envA with the pin (x2). Same command otherwise.
cd /c/Users/Administrator/Desktop/Project/TEST
R=docs/sentiment/r_series/evidence
for i in 1 2; do
  .venv/Scripts/python.exe -I $R/scripts/r3_runner.py --env envB --target tests/training --label "ctl_unpinned_$i" --results $R/r3_results.jsonl
  .venv/Scripts/python.exe -I $R/scripts/r3_runner.py --env envB --target tests/training --label "ctl_pinned_$i" --plugin-file $R/scripts/r3_pin.py --results $R/r3_results.jsonl
done
for i in 1 2; do
  .venv/Scripts/python.exe -I $R/scripts/r3_runner.py --env envA --target tests/training --label "ctl_envA_pinned_$i" --plugin-file $R/scripts/r3_pin.py --results $R/r3_results.jsonl
done
echo SERIES4-DONE
