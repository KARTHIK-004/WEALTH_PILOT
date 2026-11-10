"""R3 diagnostic pytest plugin: record WHERE a native access violation happens (module + offset + thread), without any registry change, dump or debugger.

Installs a first-chance vectored exception handler (ctypes). For every STATUS_ACCESS_VIOLATION it appends one line to the file named by R3_AV_LOG: time, thread id, whether the thread is a Python thread,
faulting address, read/write/execute and target address, the module that contains the faulting address (with offset) and the module that contains the target address. It never changes program flow
(returns EXCEPTION_CONTINUE_SEARCH), so an exception that was going to be handled is still handled and a fatal one is still fatal. Diagnostic only; used by the R3 investigation.
"""
import ctypes
import os
import threading
import time
from ctypes import wintypes as wt

LOG = os.environ.get("R3_AV_LOG", "r3_av.log")
EXCEPTION_ACCESS_VIOLATION = 0xC0000005
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetModuleHandleExW.argtypes = [wt.DWORD, ctypes.c_void_p, ctypes.POINTER(wt.HMODULE)]
k32.GetModuleFileNameW.argtypes = [wt.HMODULE, wt.LPWSTR, wt.DWORD]


class ExceptionRecord(ctypes.Structure):
    pass


ExceptionRecord._fields_ = [("ExceptionCode", wt.DWORD), ("ExceptionFlags", wt.DWORD), ("ExceptionRecord", ctypes.POINTER(ExceptionRecord)), ("ExceptionAddress", ctypes.c_void_p),
                            ("NumberParameters", wt.DWORD), ("ExceptionInformation", ctypes.c_size_t * 15)]


class ExceptionPointers(ctypes.Structure):
    _fields_ = [("ExceptionRecord", ctypes.POINTER(ExceptionRecord)), ("ContextRecord", ctypes.c_void_p)]


def module_of(address):
    if not address:
        return "none"
    handle = wt.HMODULE()
    if not k32.GetModuleHandleExW(0x4 | 0x2, address, ctypes.byref(handle)):                 # FROM_ADDRESS | UNCHANGED_REFCOUNT
        return "unmapped-or-heap"
    buffer = ctypes.create_unicode_buffer(520)
    k32.GetModuleFileNameW(handle, buffer, 520)
    return f"{os.path.basename(buffer.value)}+0x{address - (handle.value or 0):x}"


# ---- module load/unload tracking: which DLL occupied an address that is later executed after it vanished ---------------------------------------------------------------------------------------
psapi = ctypes.WinDLL("psapi", use_last_error=True)
k32.GetCurrentProcess.restype = wt.HANDLE
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]


class ModuleInfo(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wt.DWORD), ("EntryPoint", ctypes.c_void_p)]


psapi.GetModuleInformation.argtypes = [wt.HANDLE, wt.HMODULE, ctypes.POINTER(ModuleInfo), wt.DWORD]
HISTORY = []                   # every module ever observed: dict(base, size, name, loaded_at, unloaded_at)
CURRENT = {}                   # base -> index in HISTORY of the module currently loaded there
LOCK = threading.Lock()


def now_ms():
    return time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"


def log(line):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(now_ms() + " " + line + chr(10))


def snapshot(label):
    with LOCK:
        process = k32.GetCurrentProcess()
        needed = wt.DWORD()
        array = (wt.HMODULE * 2048)()
        if not psapi.EnumProcessModulesEx(process, array, ctypes.sizeof(array), ctypes.byref(needed), 3):
            return
        bases = {}
        for i in range(min(needed.value // ctypes.sizeof(wt.HMODULE), 2048)):
            bases[array[i] if isinstance(array[i], int) else ctypes.cast(array[i], ctypes.c_void_p).value] = array[i]
        for base, handle in bases.items():
            if base not in CURRENT:
                info, name = ModuleInfo(), ctypes.create_unicode_buffer(520)
                if not psapi.GetModuleInformation(process, handle, ctypes.byref(info), ctypes.sizeof(info)):
                    continue
                psapi.GetModuleFileNameExW(process, handle, name, 520)
                HISTORY.append({"base": base, "size": info.SizeOfImage, "name": os.path.basename(name.value), "loaded_at": now_ms(), "unloaded_at": None})
                CURRENT[base] = len(HISTORY) - 1
                if len(HISTORY) > len(bases) + 5 or STARTED[0]:
                    log(f"{label} LOADED   {HISTORY[-1]['name']} base=0x{base:x} size=0x{info.SizeOfImage:x}")
        for base in [b for b in CURRENT if b not in bases]:
            entry = HISTORY[CURRENT.pop(base)]
            entry["unloaded_at"] = now_ms()
            log(f"{label} UNLOADED {entry['name']} base=0x{base:x} size=0x{entry['size']:x}")


STARTED = [False]


def owner_of(address):
    for entry in reversed(HISTORY):
        if entry["base"] <= address < entry["base"] + entry["size"]:
            return f"{entry['name']}+0x{address - entry['base']:x} (loaded {entry['loaded_at']}, unloaded {entry['unloaded_at']})"
    return "no module ever seen at this address"


def poll():
    while True:
        try:
            snapshot("poll")
        except Exception:                                                                    # noqa: BLE001
            pass
        time.sleep(0.02)


HANDLER = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(ExceptionPointers))


@HANDLER
def handler(pointers):
    try:
        record = pointers.contents.ExceptionRecord.contents
        if record.ExceptionCode == EXCEPTION_ACCESS_VIOLATION:
            kind = {0: "read", 1: "write", 8: "execute"}.get(record.ExceptionInformation[0], "?")
            tid = k32.GetCurrentThreadId()
            python_thread = tid in {t.native_id for t in threading.enumerate()}
            line = (f"{time.strftime('%H:%M:%S')} tid={tid} python_thread={python_thread} fault_at={module_of(record.ExceptionAddress)} {kind} target=0x{record.ExceptionInformation[1]:x}"
                    f" target_in={module_of(record.ExceptionInformation[1])} history_fault={owner_of(record.ExceptionAddress or 0)} history_target={owner_of(record.ExceptionInformation[1])}\n")
            with open(LOG, "a", encoding="utf-8") as handle:
                handle.write(line)
    except Exception:                                                                        # noqa: BLE001 - a diagnostic must never raise inside an exception handler
        pass
    return 0                                                                                   # EXCEPTION_CONTINUE_SEARCH


_registered = ctypes.windll.kernel32 and ctypes.WinDLL("kernel32").AddVectoredExceptionHandler
_registered.restype = ctypes.c_void_p
_registered.argtypes = [wt.ULONG, HANDLER]
_token = _registered(1, handler)


def pytest_runtest_logstart(nodeid, location):
    log(f"TEST {nodeid}")
    snapshot("before " + nodeid.split("::")[-1][:60])


def pytest_sessionstart(session):
    snapshot("sessionstart")
    STARTED[0] = True
    threading.Thread(target=poll, daemon=True).start()
