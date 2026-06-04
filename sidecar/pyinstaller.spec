# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for FormulaSnap sidecar.

Build command:
    cd sidecar && pyinstaller pyinstaller.spec

Output: dist/formulasnap-sidecar (single executable)
"""

import glob
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# ---------------------------------------------------------------------------
# Extra data files (platform-independent)
# ---------------------------------------------------------------------------
_extra_datas = []
try:
    import certifi
    _extra_datas.append((certifi.where(), "certifi"))
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Platform-aware extra binaries (Windows: bundle OpenSSL DLLs + SSL .pyd)
# ---------------------------------------------------------------------------
_extra_binaries = []
_ssl_hidden = []  # default for non-Windows; populated below on win32
if sys.platform == "win32":
    python_dll_dir = Path(sys.base_prefix) / "DLLs"
    # Use glob to catch ALL OpenSSL DLL naming variants:
    #   libcrypto-1_1-x64.dll, libcrypto-1_1.dll, libcrypto-3-x64.dll, ...
    # Hard-coded names risk missing the -x64 suffix variant (Python 3.10/3.11).
    for pattern in ("libcrypto-*.dll", "libssl-*.dll"):
        for dll_path in glob.glob(str(python_dll_dir / pattern)):
            _extra_binaries.append((dll_path, "."))
    # Collect C extension .pyd files for SSL (ssl.py -> _ssl.pyd)
    for pyd_name in ("_ssl.pyd", "_socket.pyd", "_hashlib.pyd"):
        pyd_path = python_dll_dir / pyd_name
        if pyd_path.exists():
            _extra_binaries.append((str(pyd_path), "."))
    # Nuclear option: ensure PyInstaller collects ALL ssl binary deps
    _ssl_datas, _ssl_binaries, _ssl_hidden = collect_all("ssl")
    _extra_binaries.extend(_ssl_binaries)
    # Bundle VC++ 2015-2022 runtime DLLs (needed by _ssl.pyd and most .pyd files)
    # PyInstaller's automatic analysis may skip these if found in C:\Windows\System32,
    # assuming they're present on the target system — but not all users have the
    # VC++ Redistributable installed. Bundling from the Python root is safer.
    for vc_dll in ("VCRUNTIME140.dll", "VCRUNTIME140_1.dll", "MSVCP140.dll"):
        vc_path = Path(sys.base_prefix) / vc_dll
        if vc_path.exists():
            _extra_binaries.append((str(vc_path), "."))
    # Diagnostic: print what DLLs were found for SSL
    print(f"[DIAG] Python base prefix: {sys.base_prefix}")
    print(f"[DIAG] OpenSSL DLLs found ({len(_extra_binaries)} binaries):")
    for src, dst in _extra_binaries:
        print(f"  {Path(src).name} -> {dst}")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(SPECPATH)  # noqa: F821 — PyInstaller injects SPECPATH

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "sidecar" / "main.py")],
    pathex=[str(ROOT)],
    binaries=_extra_binaries,
    datas=_extra_datas,
    hiddenimports=[
        # --- uvicorn (all submodules — auto-discovered to avoid missing imports) ---
        *collect_submodules("uvicorn"),
        # --- SSL: frozen importer MUST know about ssl/_ssl. ---
        # collect_all('ssl') returns EMPTY (ssl is a module, not a package),
        # so _ssl_hidden is just [] — we add explicit entries here.
        *_ssl_hidden,
        "ssl",
        "_ssl",
        "_socket",
        "_hashlib",
        "fastapi",
        "pydantic",
        "httpx",
        "httpx._transports",
        "httpx._transports.default",
        # --- pix2text & ONNX ---
        "pix2text",
        "pix2text.utils",
        "pix2text.text_recognizer",
        "pix2text.form_recognizer",
        "onnxruntime",
        # --- PIL / Pillow (used by pix2text) ---
        "PIL",
        "PIL.Image",
        # --- OCR engine SDKs ---
        "anthropic",
        "openai",
        "google.genai",
        "google.genai.types",
        # --- setuptools/pkg_resources transitive deps ---
        "appdirs",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "sidecar" / "runtime_hook.py")],
    excludes=[
        # Heavy ML frameworks not needed
        "torch",
        "torchvision",
        "torchaudio",
        "wandb",
        "ultralytics",
        "pytorch-lightning",
        "transformers",
        "opencv-python",
        "seaborn",
        "matplotlib",
    ],
    noarchive=False,
)

# ---------------------------------------------------------------------------
# PYZ — compressed Python archive
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure)  # noqa: F821

# ---------------------------------------------------------------------------
# EXE — single-file executable
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="formulasnap-sidecar",
    debug=False,
    bootloader_ignore_signals=True,
    strip=True,
    upx=True,
    console=True,  # --console: show terminal for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
