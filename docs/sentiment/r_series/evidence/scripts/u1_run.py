"""U1 runner: one fresh subprocess per experiment, project .venv python, scrubbed environment, timeout, classification. Appends one JSON line per run to u1_results.jsonl and keeps each child's full
JSON under u1_runs/. Read-only investigation: nothing in the repository other than this evidence folder is written; no database, no network (the child blocks both at the Python level), no server.

    python u1_run.py --suite all|smoke [--only ID ...]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Administrator\Desktop\Project\TEST")
PY = REPO / ".venv" / "Scripts" / "python.exe"
EVID = REPO / "docs" / "sentiment" / "r_series" / "evidence"
PROBE = EVID / "scripts" / "u1_probe.py"
RESULTS = EVID / "u1_results.jsonl"
RUNS = EVID / "u1_runs"

# Environment allow-list: only what Windows and the interpreter need. No GEMINI_*/DATABASE_*/PROTECTED_* etc. is passed; credential names are set to EMPTY strings so that even a stray settings
# object could only ever see "not configured" (and the child additionally blocks any read of a `.env` file). CUDA_VISIBLE_DEVICES is deliberately NOT set (the backend would not set it either).
ALLOW = ("SystemRoot", "SYSTEMDRIVE", "windir", "TEMP", "TMP", "PATH", "PATHEXT", "COMSPEC", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "OS", "ProgramData",
         "ProgramFiles", "ProgramFiles(x86)", "CommonProgramFiles", "COMPUTERNAME", "USERNAME", "HOMEDRIVE", "HOMEPATH")
EMPTY_CREDENTIALS = ("DATABASE_URL", "TEST_DATABASE_URL", "GEMINI_API_KEY", "PROTECTED_DATA_KEYS")

ROUTERS = ["analysis", "demo", "health", "household_finances", "household_goals", "household_summary", "households", "monthly_records", "personalized_insights", "profiles", "protected_records", "qa", "scenarios"]
# (id, mode, [imports], linger_s, repeats, stage)
SUITE = [
    ("C0_baseline_no_import", "instrumented", [], 1.0, 1, "control"),
    ("S2A_xgboost_instrumented", "instrumented", ["xgboost"], 2.0, 3, "stage2"),
    ("S2B_xgboost_minimal", "minimal", ["xgboost"], 2.0, 3, "stage2"),
    ("S3_shap", "instrumented", ["shap"], 2.0, 3, "stage3"),
    # Added after the first full pass (same script otherwise): the confirmed third-party path autogen -> flaml -> xgboost found by the Stage 3 static scan of site-packages.
    ("S3b_flaml", "instrumented", ["flaml"], 2.0, 3, "stage3"),
    ("S3c_autogen", "instrumented", ["autogen"], 2.0, 3, "stage3"),
    ("S3d_agents_debate_module", "instrumented", ["wealthpilot.agents.debate"], 2.0, 3, "stage3"),
    ("S4a_agents_nodes", "instrumented", ["wealthpilot.agents.nodes"], 2.0, 3, "stage4"),
    ("S4b_agents_graph", "instrumented", ["wealthpilot.agents.graph"], 2.0, 3, "stage4"),
    ("S4c_analysis_service", "instrumented", ["wealthpilot.api.services.analysis_service"], 2.0, 3, "stage4"),
    ("S4d_lifespan_dependencies", "instrumented", ["wealthpilot.api.lifespan", "wealthpilot.api.dependencies"], 2.0, 3, "stage4"),
    ("S4e_all_routers_no_main", "instrumented", ["wealthpilot.api.errors", "wealthpilot.api.sse", "wealthpilot.api.lifespan"] + [f"wealthpilot.api.routers.{r}" for r in ROUTERS], 2.0, 3, "stage4"),
    ("S4f_training_behaviour", "instrumented", ["training.behaviour.common", "training.behaviour.detection"], 2.0, 3, "stage4"),
]


def child_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in ALLOW if k in os.environ}
    for name in EMPTY_CREDENTIALS:
        env[name] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def classify(code, record: dict | None, out: str) -> str:
    if code == "timeout":
        return "ENVIRONMENT FAILURE (timeout)"
    if isinstance(code, int) and (code < 0 or code > 5):
        return "NATIVE PROCESS CRASH" + (" (after result written)" if record else " (before result written)")
    if record is None:
        return "ENVIRONMENT FAILURE (no result file)"
    audit = record.get("audit")
    if isinstance(audit, dict) and any(not b.get("benign") for b in audit.get("blocked", [])):
        return "BLOCKED (import-time side effect refused)"
    failed = [i for i in record["imports"] if not i["ok"]]
    if failed:
        message = failed[0].get("exception", {}).get("type", "")
        return "FAIL" if message not in ("ModuleNotFoundError", "ImportError") else "ENVIRONMENT FAILURE (import error)"
    return "PASS" if code == 0 else f"FAIL (exit {code})"


def run_one(exp_id: str, mode: str, imports: list[str], linger: float, n: int, stage: str) -> dict:
    RUNS.mkdir(exist_ok=True)
    out_json = RUNS / f"{exp_id}_{n}_{int(time.time())}.json"
    cmd = [str(PY), "-I", "-B", str(PROBE), "--repo", str(REPO), "--out", str(out_json), "--mode", mode, "--linger", str(linger)]
    for name in imports:
        cmd += ["--import", name]
    started = time.time()
    try:
        done = subprocess.run(cmd, cwd=REPO, env=child_env(), capture_output=True, text=True, timeout=240, encoding="utf-8", errors="replace")
        code, text = done.returncode, (done.stdout + "\n" + done.stderr)
    except subprocess.TimeoutExpired:
        code, text = "timeout", ""
    record = json.loads(out_json.read_text(encoding="utf-8")) if out_json.exists() else None
    status = classify(code, record, text)
    row = {
        "id": exp_id, "run": n, "stage": stage, "mode": mode, "command": " ".join(f'"{c}"' if " " in c else c for c in cmd), "python": str(PY), "cwd": str(REPO), "exit_code": code,
        "exit_hex": hex(code & 0xFFFFFFFF) if isinstance(code, int) else None, "status": status, "elapsed_s": round(time.time() - started, 1), "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started)),
        "stderr_tail": text.strip()[-600:], "result_file": out_json.name if record else None,
    }
    if record:
        row.update({
            "python_version": record["python"], "xgboost_in_sys_modules": record["xgboost_in_sys_modules"], "nvdxgdmal64_ever_observed": record["nvdxgdmal64_ever_observed"],
            "nvidia_in_baseline": record["nvidia_modules_in_baseline_before_imports"], "nvidia_dlls_observed": sorted(set(record["nvidia_dll_final_snapshot"]) | set(record["nvidia_dll_timeline_ms"])), "nvidia_timeline_ms": record["nvidia_dll_timeline_ms"],
            "heavy_loaded": sorted(k for k, v in record["heavy_modules_in_sys_modules"].items() if v), "sys_modules_new": record["sys_modules_new"], "imports": [(i["module"], i["ok"], i.get("exception", {}).get("type")) for i in record["imports"]],
            "blocked_events": record["audit"]["blocked"] if isinstance(record["audit"], dict) else None, "artifact_opens": record["audit"]["artifact_open"] if isinstance(record["audit"], dict) else None,
            "env_secret_like_names_present": record["env_secret_like_names_present"], "imports_done_ms": record["imports_done_ms"], "xgboost_import_chain": (record["audit"].get("xgboost_import_chain") if isinstance(record["audit"], dict) else None),
        })
    with open(RESULTS, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    print(f"{exp_id} #{n}: exit={code} {status} xgboost_in_sys_modules={row.get('xgboost_in_sys_modules')} nvdxgdmal64={row.get('nvdxgdmal64_ever_observed')} nvidia={row.get('nvidia_dlls_observed')} ({row['elapsed_s']}s)", flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=[])
    args = ap.parse_args()
    for exp_id, mode, imports, linger, repeats, stage in SUITE:
        if args.only and exp_id not in args.only:
            continue
        for n in range(1, repeats + 1):
            run_one(exp_id, mode, imports, linger, n, stage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
