"""Pix2Text OCR engine — local free backend.

Uses the pix2text library (ONNX Runtime-based) to recognize mathematical
formulas and text from images.  No API key required, no cost.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from typing import Optional

from sidecar.ocr_engines.interface import (
    CostEstimate,
    OcrOptions,
    OcrResult,
    RateLimitStatus,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# Optional dependency — gracefully degrade when pix2text is not installed.
# Names are always available in module scope so that tests can @patch them.
# ---------------------------------------------------------------------------

PIX2TEXT_AVAILABLE: bool = False
Pix2Text: type | None = None  # noqa: N816 — matches pix2text public API
ort: object | None = None  # onnxruntime module reference

try:
    from pix2text import Pix2Text as _Pix2Text

    Pix2Text = _Pix2Text
    PIX2TEXT_AVAILABLE = True
except ImportError:
    pass

try:
    import onnxruntime as _ort

    ort = _ort
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class Pix2TextEngine:
    """Local OCR backend powered by Pix2Text (free, no API key).

    Implements the OcrBackend Protocol (structural subtyping).
    """

    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._p2t = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_initialized(self) -> None:
        """Lazily create the Pix2Text client on first use."""
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:  # double-check
                return
            if Pix2Text is not None:
                loop = asyncio.get_event_loop()
                self._p2t = await loop.run_in_executor(
                    None, Pix2Text.from_config
                )
                self._initialized = True

    def _run_recognition(self, image: bytes) -> list[dict]:
        """Run Pix2Text recognition synchronously (for executor)."""
        from PIL import Image

        with Image.open(io.BytesIO(image)) as img:
            return self._p2t.recognize_page(img)

    # ------------------------------------------------------------------
    # OcrBackend Protocol methods
    # ------------------------------------------------------------------

    async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        """Recognize mathematical content in *image* bytes.

        Returns the highest-confidence formula block, or the concatenated
        text content when no formula is detected.
        """
        await self._ensure_initialized()

        if self._p2t is None:
            return OcrResult(
                latex="",
                confidence=0.0,
                backend="pix2text",
                timing_ms=0,
            )

        start_time = time.time()

        # Run recognition in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, self._run_recognition, image
        )

        # Prefer formulas; fall back to plain text
        formulas = [r for r in results if r.get("type") == "formula"]
        if formulas:
            best = max(formulas, key=lambda x: x.get("confidence", 0))
            latex = best.get("text", "")
            confidence = best.get("confidence", 0.0)
        else:
            texts = [r for r in results if r.get("type") == "text"]
            latex = " ".join(t.get("text", "") for t in texts)
            confidence = max(
                (t.get("confidence", 0) for t in texts), default=0.0
            )

        timing_ms = int((time.time() - start_time) * 1000)

        return OcrResult(
            latex=latex,
            confidence=confidence,
            backend="pix2text",
            timing_ms=timing_ms,
        )

    def estimate_cost(self, image: bytes) -> Optional[CostEstimate]:
        """Local engine is free — always returns ``None``."""
        return None

    def validate_config(self) -> ValidationResult:
        """Check that pix2text and ONNX Runtime are importable."""
        if Pix2Text is None:
            return ValidationResult(
                valid=False,
                message="pix2text or onnxruntime not installed",
            )

        if ort is None:
            return ValidationResult(
                valid=False,
                message="onnxruntime not installed",
            )

        try:
            providers = ort.get_available_providers()
            if (
                "CPUExecutionProvider" in providers
                or "CUDAExecutionProvider" in providers
            ):
                return ValidationResult(
                    valid=True,
                    message="ONNX Runtime available",
                )
            return ValidationResult(
                valid=False,
                message="No execution provider available",
            )
        except Exception as exc:
            return ValidationResult(valid=False, message=str(exc))

    def get_rate_limit_status(self) -> Optional[RateLimitStatus]:
        """Local engine has no rate limits — always returns ``None``."""
        return None
