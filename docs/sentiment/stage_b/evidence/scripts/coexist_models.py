"""B2.1 coexistence test 2: the existing TensorFlow market model and the approved Horizon model in ONE process of the project .venv, loaded and run sequentially.

    python coexist_models.py <tf_first|torch_first> <results.json>

Inputs are synthetic or fictional (a seeded random return window; one invented sentence). No database, no network (every network entry point counts and refuses), no Gemini, no GPU, no download:
Horizon loads from the existing approved directory with local_files_only, safetensors only, trust_remote_code False, and `torch.load` replaced by a function that raises. Nothing is trained.
Thread settings are read, never changed.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import socket
import statistics
import sys
import time

os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"})
ATTEMPTS = []
for _n in ("connect", "connect_ex", "create_connection", "getaddrinfo"):
    def _blocked(*a, _n=_n, **k):
        ATTEMPTS.append(_n)
        raise RuntimeError("network blocked")
    setattr(socket.socket if _n.startswith("connect") and _n != "create_connection" else socket, _n, _blocked)

order, out_path = sys.argv[1], sys.argv[2]
sys.path[:0] = ["backend", "."]
MODEL_DIR = r"C:\Users\Administrator\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small"
MARKET_MODEL, MARKET_SCALER = "models/market/lstm_IXIC_v1.keras", "models/market/lstm_IXIC_scaler_v1.pkl"
SENTENCE = "I am worried because my monthly loan payments are becoming difficult to manage."          # fictional; also the Stage A negative-intent sentence
STAGE_A_RAW = [4.7015862464904785, 0.6210049986839294, -2.895378589630127]                            # Stage A raw logits for this sentence (isolated environment)


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
k32.GetCurrentProcess.restype = wt.HANDLE
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]


def mem():
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return {"peak_mb": round(c.PeakWorkingSetSize / 1048576, 1), "current_mb": round(c.WorkingSetSize / 1048576, 1)}


R = {"order": order, "executable": sys.executable, "errors": [], "stages": {}, "cpu_count": os.cpu_count()}


def mark(name, seconds=None, **extra):
    R["stages"][name] = {**mem(), **({"seconds": round(seconds, 2)} if seconds is not None else {}), **extra}


mark("python_start")
t = time.perf_counter()
from wealthpilot.api.main import app  # noqa: E402,F401  -- the application baseline (import only; nothing is started, no database is touched)
mark("application_imported", time.perf_counter() - t, tensorflow_loaded="tensorflow" in sys.modules, torch_loaded="torch" in sys.modules)

state = {}


def load_tf():
    t0 = time.perf_counter()
    import joblib
    import keras
    import numpy as np
    import tensorflow as tf
    mark("tensorflow_imported", time.perf_counter() - t0)
    t1 = time.perf_counter()
    model = keras.models.load_model(MARKET_MODEL, compile=False)
    scaler = joblib.load(MARKET_SCALER)
    mark("market_model_loaded", time.perf_counter() - t1, input_shape=list(model.input_shape), output_shape=list(model.output_shape), scaler=type(scaler).__name__)
    window = model.input_shape[1]
    returns = np.random.default_rng(42).normal(0.0, 0.01, size=window)             # synthetic returns, not market data
    state.update(tf=tf, np=np, market=model, scaler=scaler, window=window, returns=returns)


def market_forecast():
    np, window = state["np"], state["window"]
    scaled = state["scaler"].transform(state["returns"].reshape(-1, 1)).flatten()   # the existing preprocessing, unchanged
    t0 = time.perf_counter()
    pred = state["market"].predict(scaled.reshape(1, window, 1), verbose=0)[0, 0]
    ms = (time.perf_counter() - t0) * 1000.0
    return float(state["scaler"].inverse_transform(np.array([[pred]]))[0, 0]), float(pred), ms


def load_horizon():
    t0 = time.perf_counter()
    import torch
    torch.load = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("torch.load must not be used"))
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    mark("torch_transformers_imported", time.perf_counter() - t0)
    t1 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR, local_files_only=True, use_safetensors=True, trust_remote_code=False, dtype=torch.float32).eval()
    mark("horizon_loaded", time.perf_counter() - t1, labels=[model.config.id2label[i] for i in range(model.config.num_labels)], parameters=sum(p.numel() for p in model.parameters()))
    state.update(torch=torch, tok=tok, horizon=model)


def horizon_logits():
    torch, tok = state["torch"], state["tok"]
    enc = tok(SENTENCE, truncation=True, max_length=512, return_tensors="pt")
    t0 = time.perf_counter()
    with torch.inference_mode():
        logits = state["horizon"](**enc).logits[0].tolist()
    return logits, (time.perf_counter() - t0) * 1000.0


def run(name, fn):
    try:
        fn()
    except BaseException as e:  # noqa: BLE001
        R["errors"].append(f"{name}: {type(e).__name__}: {str(e)[:200]}")
        R["stages"][name + "_FAILED"] = mem()
        return False
    return True


ok = True
first = {}
if order == "tf_first":
    ok &= run("tensorflow_side", load_tf)
    if ok:
        first["market"] = market_forecast()
    ok &= run("horizon_side", load_horizon) if ok else False
    if ok:
        first["horizon"] = horizon_logits()
else:
    ok &= run("horizon_side", load_horizon)
    if ok:
        first["horizon"] = horizon_logits()
    ok &= run("tensorflow_side", load_tf) if ok else False
    if ok:
        first["market"] = market_forecast()
if not ok:
    json.dump(R, open(out_path, "w"), indent=2); print("FAILED:", R["errors"]); sys.exit(1)

R["versions"] = {"tensorflow": state["tf"].__version__, "torch": state["torch"].__version__}
R["threads_as_found"] = {"torch_intra_op": state["torch"].get_num_threads(), "torch_inter_op": state["torch"].get_num_interop_threads(), "tf_intra_op": state["tf"].config.threading.get_intra_op_parallelism_threads(),
                         "tf_inter_op": state["tf"].config.threading.get_inter_op_parallelism_threads()}
# repeated, interleaved inference with both models resident
m_vals, h_vals, m_ms, h_ms = [first["market"][0]], [first["horizon"][0]], [first["market"][2]], [first["horizon"][1]]
t0 = time.perf_counter()
for _ in range(30):
    f, _, ms = market_forecast(); m_vals.append(f); m_ms.append(ms)
    lg, hm = horizon_logits(); h_vals.append(lg); h_ms.append(hm)
R["sequential_inference"] = {
    "rounds": 31, "wall_seconds": round(time.perf_counter() - t0, 2),
    "market_forecast_first": m_vals[0], "market_all_bitwise_identical": len(set(m_vals)) == 1,
    "horizon_logits_first": h_vals[0], "horizon_all_bitwise_identical": all(v == h_vals[0] for v in h_vals),
    "horizon_matches_stage_a_raw_logits_exactly": h_vals[0] == STAGE_A_RAW,
    "horizon_max_abs_diff_vs_stage_a": max(abs(a - b) for a, b in zip(h_vals[0], STAGE_A_RAW)),
    "market_ms": {"median": round(statistics.median(m_ms), 1), "min": round(min(m_ms), 1), "max": round(max(m_ms), 1)},
    "horizon_ms": {"median": round(statistics.median(h_ms), 2), "min": round(min(h_ms), 2), "max": round(max(h_ms), 2)},
    "first_call_vs_after_both_loaded": {"market_unchanged": m_vals[0] == m_vals[-1], "horizon_unchanged": h_vals[0] == h_vals[-1]}}
import math
R["outputs_finite"] = all(math.isfinite(v) for v in m_vals) and all(math.isfinite(x) for lg in h_vals for x in lg)
R["horizon_one_softmax_probabilities"] = [round(p, 4) for p in state["torch"].softmax(state["torch"].tensor(h_vals[0]), dim=-1).tolist()]
mark("after_sequential_inference")
R["network_attempts"] = len(ATTEMPTS)
R["final_memory"] = mem()
R["status"] = "ERRORS" if R["errors"] else "COMPLETED"
json.dump(R, open(out_path, "w"), indent=2)
print(json.dumps({k: R[k] for k in ("order", "versions", "threads_as_found", "sequential_inference", "outputs_finite", "horizon_one_softmax_probabilities", "network_attempts", "final_memory", "status", "errors")}, indent=2))
for k, v in R["stages"].items():
    print(f"  stage {k:<30} peak {v['peak_mb']:>8} MB  current {v['current_mb']:>8} MB  {v.get('seconds', '')}")
