"""R3 minimal reproducer. One mode per process; prints the mode, then waits so that a dangling native thread has time to fire. Exit code 3221225477 (0xC0000005) = the crash.

    python r3_repro.py MODE [WAIT_SECONDS]       MODE: xgboost | tensorflow | sklearn | numpy | none | xgboost_cpu_param
Set R3_AV_LOG=<file> to have the access-violation locator (r3_avprobe) log DLL loads/unloads and any fault. No database, no network, no project code is used.
"""
import os
import sys
import time

mode = sys.argv[1]
wait = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
if os.environ.get("R3_AV_LOG"):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import r3_avprobe
    r3_avprobe.pytest_sessionstart(None)
import numpy as np

rng = np.random.default_rng(42)
x, y = rng.normal(size=(200, 5)), rng.integers(0, 2, 200)
if mode in ("xgboost", "xgboost_cpu_param"):
    import xgboost as xgb
    model = xgb.XGBClassifier(n_estimators=5, random_state=42, **({"device": "cpu", "tree_method": "hist"} if mode == "xgboost_cpu_param" else {}))
    model.fit(x, y)
    model.predict(x)
elif mode == "tensorflow":
    import tensorflow as tf
    m = tf.keras.Sequential([tf.keras.layers.Input((5,)), tf.keras.layers.Dense(4), tf.keras.layers.Dense(1)])
    m.compile("adam", "mse")
    m.fit(x, y.astype("float32"), epochs=1, verbose=0)
elif mode == "sklearn":
    from sklearn.ensemble import RandomForestClassifier
    RandomForestClassifier(n_estimators=10, random_state=42).fit(x, y)
elif mode == "numpy":
    np.linalg.svd(rng.normal(size=(200, 200)))
print("MODE", mode, "work done; waiting", wait, "s", flush=True)
time.sleep(wait)
print("MODE", mode, "survived", flush=True)
