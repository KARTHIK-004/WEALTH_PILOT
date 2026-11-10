"""U1 poller-sensitivity control. Question: would the U1 poller have SEEN a DLL that is mapped for only ~21 ms (the lifetime of nvdxgdmal64.dll in R3)?
Method: in a fresh instrumented subprocess (same probe, same scrubbed environment) load a harmless NON-NVIDIA system DLL, hold it mapped for N ms, unload it, and check whether the poller recorded it.
No XGBoost, no model, no NVIDIA DLL is involved; the probe refuses an NVIDIA name.   python u1_control.py [--dll mscms.dll] [--repeats 20] [--hold-ms 21 5]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import u1_run  # noqa: E402  (reuses the scrubbed environment, interpreter and paths)

ap = argparse.ArgumentParser()
ap.add_argument("--dll", default="mscms.dll")
ap.add_argument("--repeats", type=int, default=20)
ap.add_argument("--hold-ms", type=float, nargs="+", default=[21.0, 5.0])
args = ap.parse_args()
out = u1_run.EVID / "u1_control_results.jsonl"
u1_run.RUNS.mkdir(exist_ok=True)
for hold in args.hold_ms:
    seen = 0
    for n in range(1, args.repeats + 1):
        result = u1_run.RUNS / f"CONTROL_{args.dll}_{hold}_{n}_{int(time.time())}.json"
        cmd = [str(u1_run.PY), "-I", "-B", str(u1_run.PROBE), "--repo", str(u1_run.REPO), "--out", str(result), "--mode", "instrumented", "--linger", "0.3", "--control-dll", args.dll, "--control-hold-ms", str(hold)]
        done = subprocess.run(cmd, cwd=u1_run.REPO, env=u1_run.child_env(), capture_output=True, text=True, timeout=60)
        record = json.loads(result.read_text(encoding="utf-8")) if result.exists() else None
        observed = bool(record and record["control_observed_by_poller"])
        seen += observed
        row = {"dll": args.dll, "hold_ms_requested": hold, "run": n, "exit_code": done.returncode, "loaded": record["control"]["loaded"] if record else None, "freed": record["control"]["freed"] if record else None,
               "observed_by_poller": observed, "observation": record["control_observed_by_poller"] if record else None, "still_mapped_at_end": record["control_still_mapped_at_end"] if record else None, "poller_polls": record["poller_polls"] if record else None}
        with open(out, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    print(f"hold {hold} ms: poller observed {args.dll} in {seen}/{args.repeats} runs", flush=True)
