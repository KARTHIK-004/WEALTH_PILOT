"""R3 controlled runner. Runs ONE pytest invocation under a named comparison environment and appends one JSON line to a results file.

    python r3_runner.py --env envA --target tests/training --label full --results results.jsonl [--extra "<more pytest args>"] [--env-var NAME=VALUE ...]

The interpreter is `<root>/<env>/Scripts/python.exe` (a byte-for-byte copy of the project .venv for envA; the same copy minus the 15 Transformer packages and with setuptools 65.5.0 for envB). The
project `.venv` is never modified. Test selection and options are identical for every environment. Records: exit code (a native crash shows as 3221225477 = 0xC0000005 or a negative/139 code), the
pytest summary line, whether the output contains `Windows fatal exception`, which heavy libraries were in `sys.modules` at the end (via a tiny conftest-free plugin), free physical memory before the run.
Nothing is read from or written to any database; the network guard plugin refuses external connections exactly as in the earlier runs.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\.copilot\wealthpilot-r3")
REPO = Path(r"C:\Users\Administrator\Desktop\Project\TEST")
NETGUARD_DIR = Path(r"C:\Users\Administrator\AppData\Local\Temp\claude\c--Users-Administrator-Desktop-Project-TEST\22ee5a9f-eeda-468f-9ef7-3ad8f42c8fd3\scratchpad\iso20")


class MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_memory_mb() -> dict:
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return {"avail_phys_mb": round(status.ullAvailPhys / 1048576), "avail_commit_mb": round(status.ullAvailPageFile / 1048576), "load_pct": status.dwMemoryLoad}


PLUGIN = '''
import sys
import threading
def pytest_sessionfinish(session, exitstatus):
    mods = ("torch", "tensorflow", "xgboost", "sklearn", "joblib", "transformers", "shap", "numba", "scipy", "statsmodels", "arch", "keras")
    sys.stderr.write("R3_IMPORTED " + ",".join(m for m in mods if m in sys.modules) + "\\n")
    g = sys.modules.get("nvidia_dll_guard")
    sys.stderr.write("R3_GUARD " + (g.SESSION_GUARD.state.header() if g is not None and g.SESSION_GUARD.state else "not loaded") + "\\n")
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--target", required=True, nargs="+")
    ap.add_argument("--label", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--extra", default="")
    ap.add_argument("--env-var", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--plugin-file", action="append", default=[], help="copy this pytest plugin module into the plugin dir and load it (diagnostic interventions only)")
    ap.add_argument("--av-probe", action="store_true", help="load the access-violation locator plugin (r3_avprobe.py) and log to <results>_av/<env>_<label>.log")
    args = ap.parse_args()
    plugin_dir = ROOT / "plugin"
    plugin_dir.mkdir(exist_ok=True)
    (plugin_dir / "r3_probe.py").write_text(PLUGIN, encoding="utf-8")
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONPATH=f".;{NETGUARD_DIR};{plugin_dir}", PYTHONFAULTHANDLER="1")
    for pair in args.env_var:
        k, v = pair.split("=", 1)
        env[k] = v
    probe_args: list[str] = []
    if args.av_probe:
        import shutil
        shutil.copy(Path(__file__).with_name("r3_avprobe.py"), plugin_dir / "r3_avprobe.py")
        av_dir = Path(str(args.results) + "_av")
        av_dir.mkdir(exist_ok=True)
        env["R3_AV_LOG"] = str(av_dir / f"{args.env}_{args.label}_{int(time.time())}.log")
        probe_args = ["-p", "r3_avprobe"]
    for plugin_file in args.plugin_file:
        import shutil
        shutil.copy(plugin_file, plugin_dir / Path(plugin_file).name)
        probe_args += ["-p", Path(plugin_file).stem]
    python = ROOT / args.env / "Scripts" / "python.exe" if args.env != "project" else REPO / ".venv" / "Scripts" / "python.exe"
    cmd = [str(python), "-m", "pytest", "-p", "netguard", "-p", "r3_probe", *probe_args, "-p", "no:cacheprovider", "-q", "--no-header", *args.target, *args.extra.split()]
    before = free_memory_mb()
    t0 = time.time()
    low = {"min_avail_phys_mb": before["avail_phys_mb"], "min_avail_commit_mb": before["avail_commit_mb"]}
    stop = threading.Event()

    def sample() -> None:                                                                                        # whole-machine free memory every 2 s while the test process runs
        while not stop.wait(2.0):
            m = free_memory_mb()
            low["min_avail_phys_mb"] = min(low["min_avail_phys_mb"], m["avail_phys_mb"])
            low["min_avail_commit_mb"] = min(low["min_avail_commit_mb"], m["avail_commit_mb"])
    threading.Thread(target=sample, daemon=True).start()
    try:
        done = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=args.timeout, encoding="utf-8", errors="replace")
        code, out = done.returncode, done.stdout + "\n" + done.stderr
    except subprocess.TimeoutExpired as exc:
        code, out = "timeout", (exc.stdout or "") + "\n" + (exc.stderr or "") if isinstance(exc.stdout, str) else "timeout"
    stop.set()
    elapsed = round(time.time() - t0, 1)
    summary = next((line for line in reversed(out.splitlines()) if re.search(r"\d+ (passed|failed|error)", line)), "")
    guard_state = next((line.split(" ", 1)[1] for line in out.splitlines() if line.startswith("R3_GUARD")), "")
    imported = next((line.split(" ", 1)[1] for line in out.splitlines() if line.startswith("R3_IMPORTED")), "")
    fatal_lines = [line.strip() for line in out.splitlines() if "fatal exception" in line.lower()]
    last_test = ""
    m = re.findall(r"^(tests[\\/][^\s:]+::\S+)", out, re.M)
    if m:
        last_test = m[-1]
    row = {"env": args.env, "label": args.label, "target": " ".join(args.target), "extra": args.extra, "env_vars": args.env_var, "exit_code": code, "exit_hex": (hex(code & 0xFFFFFFFF) if isinstance(code, int) else None),
           "crashed": bool(fatal_lines) or (isinstance(code, int) and (code < 0 or code > 5)), "fatal": fatal_lines[:1], "summary": summary.strip(), "elapsed_s": elapsed, "imported_at_end": imported, "guard_state": guard_state,
           "memory_before": before, "memory_during_low": low, "memory_after": free_memory_mb(), "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)), "python": str(python)}
    with open(args.results, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    log_dir = Path(args.results).with_suffix("")
    log_dir.mkdir(exist_ok=True)
    (log_dir / f"{args.env}_{args.label}_{int(t0)}.log").write_text(out[-20000:], encoding="utf-8")
    print(json.dumps({k: row[k] for k in ("env", "label", "exit_code", "crashed", "summary", "elapsed_s", "imported_at_end")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
