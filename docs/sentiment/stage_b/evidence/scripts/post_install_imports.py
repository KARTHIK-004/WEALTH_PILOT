"""B2.1 post-install import checks in the project .venv. Imports only: no model, no database, no network, no inference."""
import importlib, json, sys, time, warnings, io
warnings.simplefilter("default")
caught = io.StringIO(); sys.stderr = caught
sys.path[:0] = ["backend", "."]
mods = ["numpy", "scipy", "pandas", "sklearn", "xgboost", "statsmodels", "numba", "shap", "arch", "yaml", "regex", "packaging", "httpx", "anyio",
        "setuptools", "pkg_resources", "tensorboard", "werkzeug", "pytz", "pytest", "tokenizers", "safetensors", "huggingface_hub", "transformers", "torch", "tensorflow", "keras", "wealthpilot.api.main"]
rows = {}
for m in mods:
    t = time.perf_counter()
    try:
        mod = importlib.import_module(m)
        rows[m] = {"ok": True, "version": getattr(mod, "__version__", None), "seconds": round(time.perf_counter() - t, 2)}
    except BaseException as e:  # noqa: BLE001
        rows[m] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}", "seconds": round(time.perf_counter() - t, 2)}
import torch, tensorflow as tf, transformers, safetensors
rows["_torch"] = {"version": torch.__version__, "cuda_available": torch.cuda.is_available(), "cpu_threads": torch.get_num_threads(), "built_with_cuda": torch.version.cuda}
rows["_tensorflow"] = {"version": tf.__version__, "physical_devices": [d.device_type for d in tf.config.list_physical_devices()]}
rows["_transformers"] = {"version": transformers.__version__}; rows["_safetensors"] = {"version": safetensors.__version__}
sys.stderr = sys.__stderr__
rows["_stderr_warnings"] = [l for l in caught.getvalue().splitlines() if l.strip()][:15]
json.dump(rows, open("docs/sentiment/stage_b/evidence/post_install_imports.json", "w"), indent=2)
for k, v in rows.items():
    print(k, "->", v)
