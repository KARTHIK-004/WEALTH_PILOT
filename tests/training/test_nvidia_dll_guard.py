"""Focused tests of the TEST-ONLY NVIDIA DLL lifetime guard (tests/training/nvidia_dll_guard.py, R3 mitigation).

Everything except the last two groups runs against a FAKE driver store in tmp_path with a fake loader, so no real driver DLL is touched. The two real-machine tests skip unless this is Windows
and the real driver DLL exists. Nothing here uses XGBoost, the network, a database or any application code.
"""
from __future__ import annotations

import ast
import gc
import os
import sys
import threading
from pathlib import Path

import pytest

import nvidia_dll_guard as guard
from nvidia_dll_guard import ACTIVE, INACTIVE, DllLifetimeGuard

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "nvam.inf_amd64_0123456789abcdef"
WINDOWS = pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")


class FakeKernel:
    """Counts references the way LoadLibrary/FreeLibrary do, and remembers what was loaded."""

    def __init__(self, fail: bool = False) -> None:
        self.refs, self.loads, self.frees, self.paths, self.fail = 0, 0, 0, [], fail

    def load(self, path: str) -> int:
        if self.fail:
            raise OSError("simulated load failure")
        self.refs += 1
        self.loads += 1
        self.paths.append(path)
        return 0x7FF000010000

    def free(self, handle: int) -> bool:
        self.frees += 1
        self.refs -= 1
        return True

    def probe(self, handle: int) -> bool:
        return self.refs > 0


def make_store(tmp_path: Path, packages: tuple[str, ...] = (PACKAGE,), payload: bytes = b"MZ" + b"\0" * 4096) -> Path:
    store = tmp_path / "FileRepository"
    for name in packages:
        (store / name).mkdir(parents=True)
        (store / name / guard.DLL_NAME).write_bytes(payload)
    store.mkdir(exist_ok=True)
    return store


def make_guard(store: Path, kernel: FakeKernel, *, platform: str = "win32", environ: dict | None = None) -> DllLifetimeGuard:
    return DllLifetimeGuard(driver_store=store, platform=platform, environ=environ if environ is not None else {}, loader=kernel.load, freer=kernel.free, probe=kernel.probe)


# ------------------------------------------------------------------------------------------------------------------------------------------------------------ activation
def test_activation_loads_the_one_validated_dll_exactly_once_and_reports_its_identity(tmp_path):
    store, kernel = make_store(tmp_path), FakeKernel()
    state = make_guard(store, kernel).activate()
    assert (state.status, state.reason) == (ACTIVE, "pinned") and state.handle == 0x7FF000010000
    assert kernel.loads == 1 and kernel.paths == [str(store / PACKAGE / guard.DLL_NAME)]                      # an absolute path, never the bare name
    assert state.sha256 == guard.sha256_of(store / PACKAGE / guard.DLL_NAME) and "pinned" in state.header()


def test_repeated_initialisation_never_loads_a_second_reference(tmp_path):
    kernel = FakeKernel()
    g = make_guard(make_store(tmp_path), kernel)
    first = g.activate()
    again = [g.activate() for _ in range(5)]
    assert kernel.loads == 1 and kernel.refs == 1
    assert [s.reason for s in again] == ["already_pinned"] * 5 and {s.handle for s in again} == {first.handle}


def test_concurrent_initialisation_loads_once(tmp_path):
    kernel = FakeKernel()
    g = make_guard(make_store(tmp_path), kernel)
    threads = [threading.Thread(target=g.activate) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert kernel.loads == 1 and g.state.status == ACTIVE


# ----------------------------------------------------------------------------------------------------------------------------------------------- expected path validation
@pytest.mark.parametrize("build", ["wrong_package_name", "too_deep", "empty_file", "not_pe", "too_large", "directory_instead_of_file"])
def test_a_dll_that_fails_the_path_or_file_checks_is_never_loaded(tmp_path, build):
    store = tmp_path / "FileRepository"
    if build == "wrong_package_name":
        package = store / "evil_package"
        package.mkdir(parents=True)
        (package / guard.DLL_NAME).write_bytes(b"MZ" + b"\0" * 64)
    elif build == "too_deep":
        package = store / "extra" / PACKAGE
        package.mkdir(parents=True)
        (package / guard.DLL_NAME).write_bytes(b"MZ" + b"\0" * 64)
    else:
        package = store / PACKAGE
        package.mkdir(parents=True)
        target = package / guard.DLL_NAME
        if build == "empty_file":
            target.write_bytes(b"")
        elif build == "not_pe":
            target.write_bytes(b"ELF" + b"\0" * 64)
        elif build == "too_large":
            with open(target, "wb") as handle:
                handle.write(b"MZ")
                handle.seek(guard.MAX_BYTES)
                handle.write(b"\0")
        else:
            target.mkdir()
    kernel = FakeKernel()
    state = make_guard(store, kernel, environ={guard.ENV_PATH: str(next(store.rglob(guard.DLL_NAME)))}).activate()      # via the explicit path so every shape reaches validation
    assert (state.status, state.reason) == (INACTIVE, "path_not_trusted") and kernel.loads == 0


def test_an_explicit_path_outside_the_driver_store_is_refused_and_a_bare_name_is_never_used(tmp_path):
    store, kernel = make_store(tmp_path), FakeKernel()
    outside = tmp_path / "elsewhere" / guard.DLL_NAME
    outside.parent.mkdir()
    outside.write_bytes(b"MZ" + b"\0" * 64)
    for bad in (str(outside), guard.DLL_NAME, str(store / PACKAGE / "other.dll")):
        state = make_guard(store, kernel, environ={guard.ENV_PATH: bad}).activate()
        assert state.status == INACTIVE and state.reason in ("path_not_trusted", "dll_not_found"), bad
    assert kernel.loads == 0


def test_a_symbolic_link_is_refused(tmp_path):
    store = make_store(tmp_path, packages=())
    real = tmp_path / "real.dll"
    real.write_bytes(b"MZ" + b"\0" * 64)
    (store / PACKAGE).mkdir()
    link = store / PACKAGE / guard.DLL_NAME
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("this account cannot create symbolic links")
    kernel = FakeKernel()
    assert make_guard(store, kernel, environ={guard.ENV_PATH: str(link)}).activate().reason == "path_not_trusted" and kernel.loads == 0


def test_the_optional_sha256_pin_is_enforced(tmp_path):
    store = make_store(tmp_path)
    digest = guard.sha256_of(store / PACKAGE / guard.DLL_NAME)
    bad, good = FakeKernel(), FakeKernel()
    assert make_guard(store, bad, environ={guard.ENV_SHA256: "0" * 64}).activate().reason == "hash_mismatch" and bad.loads == 0
    assert make_guard(store, good, environ={guard.ENV_SHA256: digest.upper()}).activate().reason == "pinned" and good.loads == 1


def test_several_installed_driver_packages_are_ambiguous_unless_the_exact_file_is_named(tmp_path):
    store, kernel = make_store(tmp_path, packages=(PACKAGE, "nv_dispi.inf_amd64_fedcba9876543210")), FakeKernel()
    assert make_guard(store, kernel).activate().reason == "ambiguous_candidates" and kernel.loads == 0
    chosen = store / "nv_dispi.inf_amd64_fedcba9876543210" / guard.DLL_NAME
    state = make_guard(store, kernel, environ={guard.ENV_PATH: str(chosen)}).activate()
    assert (state.reason, kernel.paths) == ("pinned", [str(chosen)])


# ---------------------------------------------------------------------------------------------------------------------------------------------------------- missing DLL / failures
def test_a_missing_dll_or_store_is_reported_transparently_and_nothing_raises(tmp_path):
    kernel = FakeKernel()
    empty = tmp_path / "FileRepository"
    empty.mkdir()
    assert make_guard(empty, kernel).activate().reason == "dll_not_found"
    assert make_guard(tmp_path / "does-not-exist", kernel).activate().reason == "dll_not_found"
    assert make_guard(empty, kernel, environ={guard.ENV_PATH: str(empty / PACKAGE / guard.DLL_NAME)}).activate().reason == "dll_not_found"
    assert kernel.loads == 0


def test_a_failing_load_is_reported_and_can_be_retried(tmp_path):
    store, kernel = make_store(tmp_path), FakeKernel(fail=True)
    g = make_guard(store, kernel)
    assert (g.activate().status, g.state.reason) == (INACTIVE, "load_failed")
    kernel.fail = False
    assert g.activate().reason == "pinned" and kernel.refs == 1


# ----------------------------------------------------------------------------------------------------------------------------------------- lifetime retention and cleanup
def test_the_reference_is_retained_until_released_whatever_happens_in_between(tmp_path):
    kernel = FakeKernel()
    g = make_guard(make_store(tmp_path), kernel)
    g.activate()
    for _ in range(3):                                                                                       # the driver's own FreeLibrary lowers the count by one load it made itself
        kernel.refs += 1
        kernel.refs -= 1
        gc.collect()
    assert kernel.frees == 0 and kernel.refs == 1 and g.is_retained()
    kernel.refs += 1                                                                                         # driver loads ...
    kernel.free(0)                                                                                           # ... and unloads: the module is still mapped because of our reference
    assert g.is_retained() and kernel.refs == 1


def test_release_gives_back_exactly_the_one_reference_once(tmp_path):
    kernel = FakeKernel()
    g = make_guard(make_store(tmp_path), kernel)
    assert g.release() is False                                                                              # nothing to release before activation
    g.activate()
    assert g.release() is True and kernel.frees == 1 and kernel.refs == 0
    assert g.release() is False and kernel.frees == 1 and g.state.reason == "released" and not g.is_retained()
    assert g.activate().reason == "pinned" and kernel.loads == 2                                              # a fresh activation after release loads again


# ------------------------------------------------------------------------------------------------------------------------------------------------- scope: platform and switch
def test_it_does_nothing_on_other_platforms_even_when_a_matching_file_exists(tmp_path):
    kernel = FakeKernel()
    for platform in ("linux", "darwin"):
        g = make_guard(make_store(tmp_path / platform), kernel, platform=platform)
        assert (g.activate().status, g.state.reason) == (INACTIVE, "not_windows") and not g.is_retained() and g.release() is False
    assert kernel.loads == 0


def test_the_environment_switch_turns_it_off(tmp_path):
    kernel = FakeKernel()
    state = make_guard(make_store(tmp_path), kernel, environ={guard.ENV_DISABLE: "0"}).activate()
    assert (state.status, state.reason) == (INACTIVE, "disabled_by_env") and kernel.loads == 0


# ------------------------------------------------------------------------------------------------------------------------------------ production isolation (static)
def test_no_production_code_script_or_training_code_imports_the_guard():
    offenders = []
    for folder in ("backend", "scripts", "training", "config", "models"):
        for path in (ROOT / folder).rglob("*.py"):
            if "nvidia_dll_guard" in path.read_text(encoding="utf-8", errors="ignore") and ".venv" not in path.parts:
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
    importers = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").rglob("*.py") if p.name not in ("nvidia_dll_guard.py", "test_nvidia_dll_guard.py")
                       and "import nvidia_dll_guard" in p.read_text(encoding="utf-8", errors="ignore"))
    assert importers == [str(Path("tests") / "training" / "conftest.py")]


def test_the_guard_module_uses_only_the_standard_library_and_never_touches_xgboost_settings_or_the_environment():
    tree = ast.parse((Path(guard.__file__)).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "hashlib", "os", "re", "sys", "threading", "dataclasses", "pathlib", "typing", "ctypes"}
    for node in ast.walk(tree):                                                                              # it only ever READS os.environ (a mapping passed in), never assigns or calls putenv
        if isinstance(node, ast.Assign):
            for target in node.targets:
                assert not (isinstance(target, ast.Subscript) and "environ" in ast.dump(target.value))
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("putenv", "unsetenv", "setdefault")


# ----------------------------------------------------------------------------------------------------------------------------------------------- the real machine (skips elsewhere)
def real_dll_present() -> bool:
    return sys.platform.startswith("win") and any(guard.default_driver_store().glob(f"nv*.inf_amd64_*/{guard.DLL_NAME}"))


@WINDOWS
@pytest.mark.skipif(not real_dll_present(), reason="no NVIDIA driver DLL on this machine")
def test_on_this_machine_the_real_dll_is_pinned_once_mapped_and_a_second_guard_shares_the_same_module():
    session = guard.SESSION_GUARD.state
    assert session is not None and (session.status, session.reason) in ((ACTIVE, "pinned"), (INACTIVE, "disabled_by_env"), (INACTIVE, "ambiguous_candidates"))
    if session.status == INACTIVE:
        pytest.skip(f"session guard inactive: {session.reason}")
    assert guard.SESSION_GUARD.is_retained() and guard.SESSION_GUARD.activate().reason == "already_pinned"
    other = DllLifetimeGuard()
    state = other.activate()
    assert (state.status, state.reason, state.handle, state.path) == (ACTIVE, "pinned", session.handle, session.path)           # same module base: no duplicate DLL
    assert other.release() is True and guard.SESSION_GUARD.is_retained()                                     # giving back the second reference leaves the session's reference in place
    assert os.path.normcase(session.path).startswith(os.path.normcase(str(guard.default_driver_store())))


@WINDOWS
@pytest.mark.skipif(not real_dll_present(), reason="no NVIDIA driver DLL on this machine")
def test_the_conftest_activated_the_guard_before_any_test_ran():
    training_conftest = next(m for m in list(sys.modules.values()) if os.path.normcase(str(getattr(m, "__file__", "") or "")) == os.path.normcase(str(Path(__file__).with_name("conftest.py"))))
    assert training_conftest.GUARD_STATE.reason in ("pinned", "disabled_by_env", "ambiguous_candidates") and training_conftest.GUARD_STATE.header().startswith("nvidia_dll_guard:")
