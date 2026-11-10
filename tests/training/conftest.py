"""Session set-up for the tests/training suite ONLY.

On Windows machines with an NVIDIA driver the CUDA-enabled XGBoost wheel triggers a driver DLL lifetime fault that kills the pytest process with 0xC0000005 (R3 investigation,
docs/sentiment/R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md). `nvidia_dll_guard` holds one reference to that DLL for the life of the test process. It is a test-only workaround: nothing in the
backend, the scripts, training code or any model imports it, and it is inert on other platforms, on machines without the DLL, and when WEALTHPILOT_NVIDIA_DLL_GUARD=0.

The guard is activated here, at conftest import, which happens before any test module imports XGBoost (the DLL is loaded and unloaded by the driver during XGBoost's first use).
"""
import sys
from pathlib import Path

# the project's pytest runs in importlib mode, which does not put a test directory on sys.path: the guard helper is imported from here (same convention as tests/training/sentiment/conftest.py)
sys.path.insert(0, str(Path(__file__).parent))

import nvidia_dll_guard  # noqa: E402

GUARD_STATE = nvidia_dll_guard.SESSION_GUARD.activate()


def pytest_report_header(config):
    return GUARD_STATE.header()
