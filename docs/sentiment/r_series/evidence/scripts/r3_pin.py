"""R3 DIAGNOSTIC INTERVENTION (not a fix): keep nvdxgdmal64.dll mapped for the whole process.

The R3 investigation found that the crash is an EXECUTE access violation inside nvdxgdmal64.dll after that NVIDIA driver component was unloaded ~21 ms after XGBoost's CUDA probe loaded it. Holding one
extra reference to the DLL makes the driver's own FreeLibrary a no-op, so a late callback would find the code still mapped. If the crash disappears with this plugin and not without it, the
unload is the cause. It is loaded only by the R3 runner (`--plugin-file`), never by the project, a test or the application.
"""
import ctypes

PATH = r"C:\Windows\System32\DriverStore\FileRepository\nvam.inf_amd64_900a074fe80431cd\nvdxgdmal64.dll"
try:
    _PIN = ctypes.WinDLL(PATH)
    PINNED = True
except OSError:
    PINNED = False
