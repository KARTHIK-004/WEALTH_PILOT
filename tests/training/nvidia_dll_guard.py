"""TEST-ONLY guard for the Windows NVIDIA-driver DLL lifetime fault found by the R3 investigation (docs/sentiment/R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md).

THE FAULT. The CUDA-enabled XGBoost wheel probes the CUDA driver the first time it runs, even with CUDA_VISIBLE_DEVICES=-1 and device="cpu". On a Windows machine with an NVIDIA driver that loads
`nvcuda.dll` -> `nvapi64.dll` -> `nvdxgdmal64.dll`; the driver then unloads `nvdxgdmal64.dll` about 21 ms later, yet leaves a native callback whose entry point is inside it. When that callback later
fires, the CPU executes unmapped memory (an EXECUTE access violation at `nvdxgdmal64.dll + 0x8080`, on a non-Python thread) and the whole test process dies with exit code 0xC0000005, either in the middle
of a long run or at interpreter exit.

THE GUARD. It holds ONE extra reference to that DLL (one `LoadLibraryExW`) for the life of the test process, so the driver's own `FreeLibrary` only lowers the count and the module stays mapped. It changes
nothing else: not XGBoost, not GPU selection, not the driver, not any dependency, and it never calls into the DLL.

SCOPE. Imported only by `tests/training/conftest.py` (so only a pytest run that collects tests/training on Windows), never by the backend, `scripts/`, the API, FastAPI start-up, training code or any
model. A static test (`test_nvidia_dll_guard.py`) enforces that nothing outside tests/ imports it. It is a workaround for a driver defect, NOT a fix: the guard is inert on non-Windows systems and on machines
without the DLL, and `WEALTHPILOT_NVIDIA_DLL_GUARD=0` turns it off.

TRUST. The DLL is never loaded by bare name (no search path). It is accepted only if it lives at `<SystemRoot>\\System32\\DriverStore\\FileRepository\\nv*.inf_amd64_<hex>\\nvdxgdmal64.dll` (a directory only
administrators/TrustedInstaller can write), is a regular file (no symbolic link or other reparse point, not a directory), is a plausible PE image (non-empty, under 16 MB, starts with "MZ"), and is the ONLY
candidate (several installed driver packages are ambiguous, so the guard stays inactive instead of guessing; `WEALTHPILOT_NVIDIA_DLL_PATH` may name the exact file, and is validated by the same rules).
`WEALTHPILOT_NVIDIA_DLL_SHA256`, when set, must equal the file's SHA-256. LIMITATION: the guard does not itself verify the Authenticode/catalog signature; on the investigated machine the file was checked
by hand (signature Valid, publisher "Microsoft Windows Hardware Compatibility Publisher", SHA-256 recorded in the R3 report).
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

DLL_NAME = "nvdxgdmal64.dll"
ENV_DISABLE = "WEALTHPILOT_NVIDIA_DLL_GUARD"            # "0" turns the guard off
ENV_PATH = "WEALTHPILOT_NVIDIA_DLL_PATH"                # optional exact path (validated by the same rules)
ENV_SHA256 = "WEALTHPILOT_NVIDIA_DLL_SHA256"            # optional exact SHA-256 (hex)
PACKAGE_DIRECTORY = re.compile(r"^nv[a-z0-9_]*\.inf_amd64_[0-9a-f]{16}$", re.IGNORECASE)
MAX_BYTES = 16 * 1024 * 1024
REPARSE_POINT = 0x400
LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR, LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x100, 0x1000

ACTIVE, INACTIVE = "active", "inactive"
REASONS = ("pinned", "already_pinned", "not_windows", "disabled_by_env", "dll_not_found", "ambiguous_candidates", "path_not_trusted", "hash_mismatch", "load_failed", "released")


@dataclass(frozen=True)
class GuardState:
    status: str                       # active | inactive
    reason: str                       # one of REASONS
    path: str | None = None
    sha256: str | None = None
    handle: int | None = None

    def header(self) -> str:
        return f"nvidia_dll_guard: {self.status} ({self.reason})" + (f" {self.path} sha256={self.sha256}" if self.path else "")


# ---------------------------------------------------------------------------------------------------------------------------------------- Win32 primitives (only called on Windows)
def default_driver_store() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "DriverStore" / "FileRepository"


def load_library(path: str) -> int:
    """One LoadLibraryExW of an ABSOLUTE path. Returns the module handle; raises OSError on failure."""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    handle = kernel32.LoadLibraryExW(path, None, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def free_library(handle: int) -> bool:
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.FreeLibrary.argtypes = [ctypes.c_void_p]
    kernel32.FreeLibrary.restype = ctypes.c_int
    return bool(kernel32.FreeLibrary(handle))


def module_is_mapped(handle: int) -> bool:
    """True when `handle` is a module currently mapped in this process (GetModuleHandleExW from the address, no reference change)."""
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleExW.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HMODULE)]
    found = wintypes.HMODULE()
    ok = kernel32.GetModuleHandleExW(0x4 | 0x2, ctypes.c_void_p(handle), ctypes.byref(found))          # FROM_ADDRESS | UNCHANGED_REFCOUNT
    return bool(ok) and (found.value or 0) == handle


# -------------------------------------------------------------------------------------------------------------------------------------------------------------- validation
def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & REPARSE_POINT)
    except OSError:
        return True


def rejection(path: Path, driver_store: Path) -> str | None:
    """None when `path` is an acceptable copy of the DLL; otherwise a short reason. Pure file-system checks, nothing is loaded."""
    try:
        if path.name.lower() != DLL_NAME:
            return "wrong file name"
        if not os.path.isabs(path):
            return "path is not absolute"
        package, store = path.parent, driver_store
        if os.path.normcase(str(package.parent)) != os.path.normcase(str(store)):
            return "not directly inside a package folder of the driver store"
        if not PACKAGE_DIRECTORY.match(package.name):
            return "package folder name is not an NVIDIA inf_amd64 package"
        if _is_reparse_point(path) or _is_reparse_point(package) or _is_reparse_point(store):
            return "symbolic link or reparse point"
        if not path.is_file():
            return "not a regular file"
        size = path.stat().st_size
        if not 0 < size <= MAX_BYTES:
            return "implausible size"
        with open(path, "rb") as handle:
            if handle.read(2) != b"MZ":
                return "not a PE image"
    except OSError:
        return "unreadable"
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------- the guard
class DllLifetimeGuard:
    """Holds one reference to the driver DLL. `activate()` is idempotent and thread-safe; `release()` gives the reference back (tests only; the session guard is never released before exit)."""

    def __init__(self, *, driver_store: Path | None = None, platform: str | None = None, environ: Mapping[str, str] | None = None,
                 loader: Callable[[str], int] | None = None, freer: Callable[[int], bool] | None = None, probe: Callable[[int], bool] | None = None) -> None:
        self._store = driver_store if driver_store is not None else default_driver_store()
        self._platform = platform if platform is not None else sys.platform
        self._env = environ if environ is not None else os.environ
        self._load, self._free, self._probe = loader or load_library, freer or free_library, probe or module_is_mapped
        self._lock = threading.Lock()
        self._state: GuardState | None = None

    @property
    def state(self) -> GuardState | None:
        return self._state

    def _decide(self) -> GuardState:
        if not self._platform.startswith("win"):
            return GuardState(INACTIVE, "not_windows")
        if self._env.get(ENV_DISABLE) == "0":
            return GuardState(INACTIVE, "disabled_by_env")
        explicit = self._env.get(ENV_PATH)
        if explicit:
            candidates = [Path(explicit)]
        else:
            try:
                candidates = [p for p in sorted(self._store.glob(f"nv*.inf_amd64_*/{DLL_NAME}"))]
            except OSError:
                candidates = []
            if not candidates:
                return GuardState(INACTIVE, "dll_not_found")
            if len(candidates) > 1:
                return GuardState(INACTIVE, "ambiguous_candidates")
        path = candidates[0]
        if explicit and not path.exists():
            return GuardState(INACTIVE, "dll_not_found", str(path))
        if rejection(path, self._store) is not None:
            return GuardState(INACTIVE, "path_not_trusted", str(path))
        digest = sha256_of(path)
        expected = self._env.get(ENV_SHA256)
        if expected and expected.strip().lower() != digest:
            return GuardState(INACTIVE, "hash_mismatch", str(path), digest)
        try:
            handle = self._load(str(path))
        except OSError:
            return GuardState(INACTIVE, "load_failed", str(path), digest)
        return GuardState(ACTIVE, "pinned", str(path), digest, handle)

    def activate(self) -> GuardState:
        with self._lock:
            if self._state is not None and self._state.status == ACTIVE:
                return GuardState(ACTIVE, "already_pinned", self._state.path, self._state.sha256, self._state.handle)          # no second load
            self._state = self._decide()
            return self._state

    def is_retained(self) -> bool:
        """True while this guard holds a reference AND the module is really mapped in the process."""
        state = self._state
        return bool(state and state.status == ACTIVE and state.handle is not None and self._probe(state.handle))

    def release(self) -> bool:
        """Give the one reference back. Returns True if a reference was released. Idempotent."""
        with self._lock:
            state = self._state
            if state is None or state.status != ACTIVE or state.handle is None:
                return False
            released = bool(self._free(state.handle))
            self._state = GuardState(INACTIVE, "released" if released else "load_failed", state.path, state.sha256)
            return released


SESSION_GUARD = DllLifetimeGuard()
