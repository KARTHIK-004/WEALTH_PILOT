"""B2.1 coexistence test 1: TensorFlow and PyTorch imported in ONE process, in a chosen order, in the project .venv.

    python coexist_import_order.py <tf_first|torch_first> <results.json>

Imports, small CPU tensor operations and native-library inspection only: no model, no database, no network, no GPU (CUDA_VISIBLE_DEVICES=-1). Memory is the process peak working set measured with
correctly typed Windows API calls. Thread settings are read, never changed.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import socket
import sys
import time

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"            # never initialise GPU support
os.environ["HF_HUB_OFFLINE"] = "1"
ATTEMPTS = []
for _n in ("connect", "connect_ex"):
    setattr(socket.socket, _n, lambda *a, _n=_n, **k: (ATTEMPTS.append(_n), (_ for _ in ()).throw(RuntimeError("network blocked")))[1])

order, out_path = sys.argv[1], sys.argv[2]


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
k32.GetCurrentProcess.restype = wt.HANDLE
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
psapi.EnumProcessModules.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD)]
psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]


def mem():
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return {"peak_mb": round(c.PeakWorkingSetSize / 1048576, 1), "current_mb": round(c.WorkingSetSize / 1048576, 1)}


def native_modules():
    handle = k32.GetCurrentProcess()
    needed = wt.DWORD()
    arr = (wt.HMODULE * 2048)()
    psapi.EnumProcessModules(handle, arr, ctypes.sizeof(arr), ctypes.byref(needed))
    names = []
    for i in range(min(needed.value // ctypes.sizeof(wt.HMODULE), 2048)):
        buf = ctypes.create_unicode_buffer(520)
        if psapi.GetModuleFileNameExW(handle, arr[i], buf, 520):
            names.append(os.path.basename(buf.value).lower())
    return sorted(set(names))


result = {"order": order, "python": sys.version.split()[0], "executable": sys.executable, "cpu_count": os.cpu_count(), "stages": {}, "errors": []}
result["stages"]["python_start"] = mem()


def stage(name, fn):
    t = time.perf_counter()
    try:
        fn()
        ok, err = True, None
    except BaseException as e:  # noqa: BLE001
        ok, err = False, f"{type(e).__name__}: {str(e)[:200]}"
        result["errors"].append(f"{name}: {err}")
    result["stages"][name] = {**mem(), "seconds": round(time.perf_counter() - t, 2), "ok": ok, "error": err}


def import_tf():
    global tf
    import tensorflow as tf  # noqa: F811


def import_torch():
    global torch
    import torch  # noqa: F811


first, second = (("tensorflow", import_tf), ("torch", import_torch)) if order == "tf_first" else (("torch", import_torch), ("tensorflow", import_tf))
stage(f"import_{first[0]}", first[1])
stage(f"import_{second[0]}", second[1])
if result["errors"]:
    json.dump(result, open(out_path, "w"), indent=2)
    print("IMPORT FAILED:", result["errors"]); sys.exit(1)

result["versions"] = {"tensorflow": tf.__version__, "torch": torch.__version__}
result["devices"] = {"tensorflow": [d.device_type for d in tf.config.list_physical_devices()], "torch_cuda_available": torch.cuda.is_available(), "torch_built_with_cuda": torch.version.cuda}
result["threads_as_found"] = {"torch_intra_op": torch.get_num_threads(), "torch_inter_op": torch.get_num_interop_threads(), "tf_intra_op": tf.config.threading.get_intra_op_parallelism_threads(),
                              "tf_inter_op": tf.config.threading.get_inter_op_parallelism_threads()}


def tf_ops():
    tf.random.set_seed(0)
    a = tf.random.normal((256, 256), seed=0)
    sums = []
    for _ in range(50):
        c = a
        for _ in range(3):
            c = tf.linalg.matmul(c, a) / 256.0
        sums.append(float(tf.reduce_sum(c)))
    return sums


def torch_ops():
    torch.manual_seed(0)
    x = torch.randn(256, 256)
    sums = []
    for _ in range(50):
        y = x
        for _ in range(3):
            y = (y @ x) / 256.0
        sums.append(float(y.sum()))
    return sums


stage("tf_ops_50_repeats", lambda: result.__setitem__("tf_sums", tf_ops()))
stage("torch_ops_50_repeats", lambda: result.__setitem__("torch_sums", torch_ops()))
inter_tf, inter_torch = [], []
for _ in range(30):
    inter_tf.append(float(tf.reduce_sum(tf.linalg.matmul(tf.ones((128, 128)), tf.ones((128, 128))))))
    inter_torch.append(float((torch.ones(128, 128) @ torch.ones(128, 128)).sum()))
result["interleaved"] = {"tf_all_equal": len(set(inter_tf)) == 1, "torch_all_equal": len(set(inter_torch)) == 1, "tf_value": inter_tf[0], "torch_value": inter_torch[0], "expected": 128 * 128 * 128.0}
result["determinism"] = {"tf_50_repeats_identical": len(set(result.get("tf_sums", []))) == 1, "torch_50_repeats_identical": len(set(result.get("torch_sums", []))) == 1}
result["threads_after_ops"] = {"torch_intra_op": torch.get_num_threads(), "tf_intra_op": tf.config.threading.get_intra_op_parallelism_threads()}
mods = native_modules()
keys = ("omp", "mkl", "dnnl", "onednn", "tbb", "iomp", "vcomp", "openblas", "libgomp")
result["native_libraries_of_interest"] = [m for m in mods if any(k in m for k in keys)]
result["openmp_runtimes_loaded"] = [m for m in mods if any(k in m for k in ("libiomp", "vcomp", "libgomp", "libomp"))]
result["native_module_count"] = len(mods)
result["network_attempts"] = len(ATTEMPTS)
result["final_memory"] = mem()
result["status"] = "ERRORS" if result["errors"] else "COMPLETED"
json.dump(result, open(out_path, "w"), indent=2)
print(json.dumps({k: result[k] for k in ("order", "versions", "devices", "threads_as_found", "determinism", "interleaved", "openmp_runtimes_loaded", "native_libraries_of_interest", "final_memory", "status", "errors")}, indent=2))
for k, v in result["stages"].items():
    print(f"  stage {k:<28} peak {v['peak_mb']:>8} MB  current {v['current_mb']:>8} MB  {v.get('seconds', '')}s  ok={v.get('ok', '')}")
