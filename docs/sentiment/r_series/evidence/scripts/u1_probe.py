"""U1 child probe: import named modules in a FRESH interpreter and report what got loaded. Read-only; never loads a model, fits, predicts, starts a server or opens a database/network connection.

    python -I -B u1_probe.py --out result.json [--import MODULE ...] [--mode instrumented|minimal] [--linger SECONDS]

instrumented: installs a Python audit hook BEFORE any import that (a) records and BLOCKS socket connect / DNS lookups / subprocess starts / any open() of a file named `.env*` (so an import-time side effect becomes a
visible BLOCKED result, never a connection or a secret read), (b) records every ctypes.dlopen and every open() of a model-artifact-looking file, (c) records the Python call chain at the first `import xgboost`;
and starts a poller thread that enumerates the process's loaded Windows modules (psapi.EnumProcessModulesEx) continuously, so a driver DLL that is mapped and unmapped within tens of milliseconds is still seen.
minimal: no hook and no poller thread - only the imports, a linger, and one final module snapshot (a control for the instrumentation itself).
The probe never calls into any NVIDIA DLL and never touches XGBoost beyond importing it when asked.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib
import json
import os
import re
import sys
import threading
import time
from ctypes import wintypes as wt

T0 = time.perf_counter()
ARTIFACT_EXT = (".pkl", ".joblib", ".keras", ".h5", ".safetensors", ".onnx", ".pt", ".pth", ".bin", ".ubj", ".csv", ".parquet")
BLOCK_EVENTS = {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.sendto", "socket.bind",
                "subprocess.Popen", "os.system", "os.exec", "os.spawn", "os.posix_spawn", "os.startfile"}
NVIDIA_RE = re.compile(r"^(nv|cuda|cudnn|cublas|cufft|curand|cusolver|cusparse|nvrtc|nvcuda|nvapi|nvml|nvdxgdmal|nvidia)", re.I)
SECRET_NAME_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DATABASE|_URL|DSN|API)", re.I)
HEAVY = ("xgboost", "shap", "numba", "sklearn", "joblib", "scipy", "pandas", "numpy", "tensorflow", "keras", "torch", "transformers", "safetensors", "langgraph", "langchain_core", "google.genai",
         "autogen", "sqlalchemy", "psycopg", "fastapi", "pydantic", "uvicorn", "yfinance", "statsmodels", "arch", "training", "wealthpilot")

EVENTS: dict = {"blocked": [], "dlopen": [], "artifact_open": [], "xgboost_import_chain": None, "audit_event_counts": {}}
_IN_HOOK = threading.local()


def now_ms() -> float:
    return round((time.perf_counter() - T0) * 1000, 1)


def frames_from(frame, limit: int = 40) -> list[str]:
    out = []
    while frame is not None and len(out) < limit:
        out.append(f"{frame.f_code.co_filename}:{frame.f_lineno} {frame.f_code.co_name}")
        frame = frame.f_back
    return out


def audit_hook(event: str, args: tuple) -> None:
    if getattr(_IN_HOOK, "busy", False):
        return
    _IN_HOOK.busy = True
    try:
        if event in BLOCK_EVENTS:
            origin = frames_from(sys._getframe(2), 8)
            # The one benign pattern: the standard library's `platform` asking cmd.exe for the Windows version (`cmd /c ver`), reached from sklearn's import. It is still blocked (platform falls back); it is only
            # labelled so it is not mistaken for an import-time side effect of project code. Anything else stays an unlabelled, reportable block.
            text = repr(args).lower()
            ver_probe = event == "subprocess.Popen" and "cmd.exe" in text and "ver" in text.split("cmd.exe", 1)[1] and any("platform.py" in f and "_syscmd_ver" in f for f in origin)
            # Second benign pattern: urllib3 binds a throw-away IPv6 loopback socket (::1, port 0) at import to learn whether IPv6 exists (`HAS_IPV6`). Local only, no traffic; reached via langchain/langgraph -> urllib3.
            ipv6_probe = event == "socket.bind" and "('::1', 0)" in repr(args) and any("urllib3" in f and "connection.py" in f for f in origin[:2])
            EVENTS["blocked"].append({"t_ms": now_ms(), "event": event, "args": repr(args)[:200], "from": origin, "benign_platform_ver_probe": ver_probe, "benign_urllib3_ipv6_probe": ipv6_probe, "benign": ver_probe or ipv6_probe})
            raise PermissionError(f"U1 probe blocked {event}")
        if event == "open":
            raw = args[0]
            if isinstance(raw, int):
                return
            try:
                name = os.path.basename(os.fsdecode(raw)).lower()
            except Exception:
                return
            if name.startswith(".env"):
                EVENTS["blocked"].append({"t_ms": now_ms(), "event": "open(.env)", "args": name, "from": frames_from(sys._getframe(2), 8)})
                raise PermissionError("U1 probe blocked a read of an environment file")
            if name.endswith(ARTIFACT_EXT) and len(EVENTS["artifact_open"]) < 50:
                EVENTS["artifact_open"].append({"t_ms": now_ms(), "path": os.fsdecode(raw)[-160:], "mode": str(args[1])})
        elif event == "ctypes.dlopen":
            EVENTS["dlopen"].append({"t_ms": now_ms(), "name": str(args[0])[-200:]})
        elif event == "import" and EVENTS["xgboost_import_chain"] is None and str(args[0]).split(".")[0] == "xgboost":
            EVENTS["xgboost_import_chain"] = {"t_ms": now_ms(), "module": str(args[0]), "frames": frames_from(sys._getframe(2))}
    except PermissionError:
        raise
    except Exception:                                      # an audit-hook exception would abort the audited operation; only the deliberate block may do that
        pass
    finally:
        _IN_HOOK.busy = False


# ---- loaded-module enumeration (Windows) ---------------------------------------------------------------------------------------------------------------------------------------------------------
psapi = ctypes.WinDLL("psapi", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetCurrentProcess.restype = wt.HANDLE
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
PROC = k32.GetCurrentProcess()


def loaded_modules(cache: dict | None = None) -> dict[int, str]:
    array = (wt.HMODULE * 4096)()
    needed = wt.DWORD()
    if not psapi.EnumProcessModulesEx(PROC, array, ctypes.sizeof(array), ctypes.byref(needed), 3):
        return {}
    count = min(needed.value // ctypes.sizeof(wt.HMODULE), 4096)
    handles = [array[i] or 0 for i in range(count)]
    names: dict[int, str] = {}
    buffer = ctypes.create_unicode_buffer(1040)
    for handle in handles:
        if cache is not None and handle in cache:
            names[handle] = cache[handle]
            continue
        if psapi.GetModuleFileNameExW(PROC, handle, buffer, 1040):
            names[handle] = buffer.value
    if cache is not None:
        cache.clear()
        cache.update(names)
    return names


class Poller(threading.Thread):
    daemon = True

    def __init__(self) -> None:
        super().__init__(name="u1-poller")
        self.stop_flag = threading.Event()
        self.cache: dict[int, str] = {}
        self.baseline: set[str] = {os.path.basename(p).lower() for p in loaded_modules(self.cache).values()}
        self.seen: dict[str, dict] = {}                  # basename -> {first_ms, last_ms, path}
        self.polls = 0

    def run(self) -> None:
        while not self.stop_flag.is_set():
            self.poll()
            time.sleep(0.0005)

    def poll(self) -> None:
        current = loaded_modules(self.cache)
        t = now_ms()
        self.polls += 1
        for path in current.values():
            base = os.path.basename(path).lower()
            if base in self.baseline:
                continue
            entry = self.seen.get(base)
            if entry is None:
                self.seen[base] = {"first_ms": t, "last_ms": t, "path": path}
            else:
                entry["last_ms"] = t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--import", dest="imports", action="append", default=[])
    ap.add_argument("--mode", choices=("instrumented", "minimal"), default="instrumented")
    ap.add_argument("--linger", type=float, default=2.0)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--control-dll", default="", help="poller sensitivity control only: load this harmless system DLL, keep it mapped --control-hold-ms, then unload it (never an NVIDIA DLL)")
    ap.add_argument("--control-hold-ms", type=float, default=21.0)
    args = ap.parse_args()
    if args.control_dll and NVIDIA_RE.match(os.path.basename(args.control_dll)):
        raise SystemExit("refusing to use an NVIDIA DLL as the control")
    if args.mode == "instrumented":
        sys.addaudithook(audit_hook)                       # first thing, before any project/library import
    repo = args.repo
    for extra in (os.path.join(repo, "backend"), repo):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    poller = Poller() if args.mode == "instrumented" else None
    baseline_all = {os.path.basename(p).lower() for p in loaded_modules().values()}
    modules_before = set(sys.modules)
    if poller is not None:
        poller.start()
    control = None
    if args.control_dll:
        k32.LoadLibraryW.restype = ctypes.c_void_p
        k32.LoadLibraryW.argtypes = [wt.LPCWSTR]
        k32.FreeLibrary.argtypes = [ctypes.c_void_p]
        time.sleep(0.05)
        handle = k32.LoadLibraryW(args.control_dll)
        loaded_at = now_ms()
        time.sleep(args.control_hold_ms / 1000)
        freed = bool(k32.FreeLibrary(handle)) if handle else False
        control = {"dll": args.control_dll, "loaded": bool(handle), "loaded_at_ms": loaded_at, "hold_ms_requested": args.control_hold_ms, "freed": freed, "freed_at_ms": now_ms()}
    results = []
    for name in args.imports:
        started = now_ms()
        entry = {"module": name, "ok": False}
        try:
            module = importlib.import_module(name)
            entry["ok"] = True
            entry["file"] = str(getattr(module, "__file__", ""))[-160:]
        except BaseException as exc:                          # record, do not hide
            entry["exception"] = {"type": type(exc).__name__, "message": str(exc)[:300]}
            tb, trail = exc.__traceback__, []
            while tb is not None:
                trail.append(f"{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno} {tb.tb_frame.f_code.co_name}")
                tb = tb.tb_next
            entry["exception"]["where"] = trail[-6:]
        entry["elapsed_ms"] = round(now_ms() - started, 1)
        results.append(entry)
    imports_done_ms = now_ms()
    time.sleep(args.linger)                                   # lets a late unload / late event happen while the process is alive and observed
    if poller is not None:
        poller.stop_flag.set()
        poller.join(timeout=2)
        poller.poll()
    final = loaded_modules()
    final_bases = sorted({os.path.basename(p).lower() for p in final.values()})
    sys_modules = sorted(sys.modules)
    heavy = {name: any(m == name or m.startswith(name + ".") for m in sys_modules) for name in HEAVY}
    nvidia_final = [b for b in final_bases if NVIDIA_RE.match(b) and b not in baseline_all]
    nvidia_seen = {b: v for b, v in (poller.seen.items() if poller else []) if NVIDIA_RE.match(b)}
    secret_like = sorted(k for k in os.environ if SECRET_NAME_RE.search(k))
    record = {
        "mode": args.mode, "python": sys.version.split()[0], "executable": sys.executable, "cwd": os.getcwd(), "argv_imports": args.imports, "flags": {"isolated": sys.flags.isolated, "dont_write_bytecode": sys.flags.dont_write_bytecode},
        "env_var_names": sorted(os.environ), "env_secret_like_names_present": secret_like, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "imports": results, "imports_done_ms": imports_done_ms, "linger_s": args.linger,
        "xgboost_in_sys_modules": "xgboost" in sys.modules, "xgboost_submodules": [m for m in sys_modules if m == "xgboost" or m.startswith("xgboost.")][:8], "heavy_modules_in_sys_modules": heavy,
        "sys_modules_total": len(sys_modules), "sys_modules_new": len(set(sys_modules) - modules_before),
        "nvidia_modules_in_baseline_before_imports": sorted(b for b in baseline_all if NVIDIA_RE.match(b)),
        "nvidia_dll_final_snapshot": nvidia_final, "nvdxgdmal64_in_final_snapshot": "nvdxgdmal64.dll" in final_bases,
        "nvidia_dll_timeline_ms": nvidia_seen, "nvdxgdmal64_ever_observed": "nvdxgdmal64.dll" in nvidia_seen or "nvdxgdmal64.dll" in nvidia_final,
        "poller_polls": poller.polls if poller else 0, "native_modules_new_seen_by_poller": ({b: v["first_ms"] for b, v in poller.seen.items()} if poller else {}),
        "native_modules_final_count": len(final_bases), "xgboost_native_in_final": [b for b in final_bases if "xgboost" in b],
        "audit": {"blocked": EVENTS["blocked"], "dlopen": EVENTS["dlopen"][:40], "artifact_open": EVENTS["artifact_open"], "xgboost_import_chain": EVENTS["xgboost_import_chain"]} if args.mode == "instrumented" else "not installed (minimal mode)",
        "control": control, "control_observed_by_poller": (poller.seen.get(os.path.basename(args.control_dll).lower()) if (poller and args.control_dll) else None),
        "control_still_mapped_at_end": (os.path.basename(args.control_dll).lower() in final_bases) if args.control_dll else None,
        "wealthpilot_file": str(getattr(sys.modules.get("wealthpilot"), "__file__", ""))[-120:], "total_ms": now_ms(),
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
