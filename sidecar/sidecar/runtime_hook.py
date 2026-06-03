"""
PyInstaller runtime hook — Windows DLL search path fix.

Runs between bootloader init and main script execution.
Ensures that the PyInstaller temp extraction directory (sys._MEIPASS)
is in the Windows DLL search path before any C extension modules
(e.g., _ssl.pyd) are loaded.

This is the standard fix for:
    "DLL load failed while importing _ssl"
in PyInstaller one-file bundles on Windows.

Refs:
    - https://pyinstaller.org/en/stable/runtime-information.html
    - https://docs.python.org/3/library/os.html#os.add_dll_directory
    - pyinstaller#9381, #8956, #7510
"""

import os
import sys

if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    meipass = sys._MEIPASS  # type: ignore[attr-defined]

    # 1) Modern approach (Python 3.8+): register with AddDllDirectory
    #    Affects LoadLibraryEx(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS).
    os.add_dll_directory(meipass)

    # 2) Legacy fallback: prepend to %PATH%
    #    Works on ALL Python/Windows versions. Also covers edge cases
    #    where subprocesses spawned by uvicorn need the same DLL resolution.
    meipass = os.path.normpath(meipass)
    old_path = os.environ.get("PATH", "")
    if meipass not in old_path.split(os.pathsep):
        os.environ["PATH"] = meipass + os.pathsep + old_path
