# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for FormulaSnap sidecar.

Build command:
    cd sidecar && pyinstaller pyinstaller.spec

Output: dist/formulasnap-sidecar (single executable)
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Platform-aware extra binaries (Windows: bundle OpenSSL DLLs)
# ---------------------------------------------------------------------------
_extra_binaries = []
if sys.platform == "win32":
    python_dll_dir = Path(sys.base_prefix) / "DLLs"
    for dll_name in [
        "libcrypto-3.dll", "libssl-3.dll",
        "libcrypto-1_1.dll", "libssl-1_1.dll",
        "libcrypto-3-x64.dll", "libssl-3-x64.dll",
    ]:
        dll_path = python_dll_dir / dll_name
        if dll_path.exists():
            _extra_binaries.append((str(dll_path), "."))
    # Collect C extension .pyd files for SSL (ssl.py -> _ssl.pyd)
    for pyd_name in ["_ssl.pyd", "_socket.pyd", "_hashlib.pyd"]:
        pyd_path = python_dll_dir / pyd_name
        if pyd_path.exists():
            _extra_binaries.append((str(pyd_path), "."))

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
    datas=[],
    hiddenimports=[
        # --- Core dependencies ---
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
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
        # --- SSL (Windows DLL bundling + C extension hook) ---
        "ssl",
        "_ssl",
        "_socket",
        "_hashlib",
        # --- OCR engine SDKs ---
        "anthropic",
        "openai",
        "google.genai",
        "google.genai.types",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=True,  # --console: show terminal for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
