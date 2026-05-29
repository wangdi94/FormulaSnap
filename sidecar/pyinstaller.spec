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
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(SPECPATH)  # noqa: F821 — PyInstaller injects SPECPATH

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "sidecar" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
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
        # --- OCR engine SDKs ---
        "anthropic",
        "openai",
        "google.genai",
        "google.genai.types",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    strip=False,
    upx=True,
    console=False,  # --console: show terminal for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
