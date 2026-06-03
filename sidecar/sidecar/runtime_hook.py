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
    # Add the PyInstaller temp directory to the DLL search path so that
    # C extensions (e.g. _ssl.pyd) can find their shared library
    # dependencies (e.g. libcrypto-3-x64.dll, libssl-3-x64.dll).
    meipass = sys._MEIPASS  # type: ignore[attr-defined]
    os.add_dll_directory(meipass)
