"""Tests for Pix2Text OCR engine (local free backend)."""

import asyncio
import time

import pytest
from unittest.mock import patch, MagicMock

from sidecar.ocr_engines.pix2text_engine import Pix2TextEngine
from sidecar.ocr_engines.interface import OcrOptions, OcrResult, ValidationResult


class TestPix2TextEngine:
    """Unit tests for Pix2TextEngine with mocked dependencies."""

    def setup_method(self):
        self.engine = Pix2TextEngine()

    def test_estimate_cost_returns_none(self):
        """Pix2Text is local, so cost should be None."""
        cost = self.engine.estimate_cost(b"fake_image")
        assert cost is None

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    async def test_recognize_calls_pix2text(self, mock_image_open, mock_p2t_class):
        """Test that recognize() calls Pix2Text API and extracts best formula."""
        mock_p2t = MagicMock()
        mock_p2t.recognize_page.return_value = [
            {"type": "formula", "text": "$x^2 + 5x + 6 = 0$", "confidence": 0.95},
        ]
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()
        result = await engine.recognize(b"fake_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "x^2" in result.latex
        assert result.confidence > 0
        assert result.backend == "pix2text"
        assert result.timing_ms >= 0

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    async def test_recognize_returns_highest_confidence_formula(self, mock_image_open, mock_p2t_class):
        """When multiple formulas are found, return the one with highest confidence."""
        mock_p2t = MagicMock()
        mock_p2t.recognize_page.return_value = [
            {"type": "formula", "text": "$a=1$", "confidence": 0.7},
            {"type": "formula", "text": "$b=2$", "confidence": 0.95},
            {"type": "formula", "text": "$c=3$", "confidence": 0.5},
        ]
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()
        result = await engine.recognize(b"fake_image", OcrOptions())

        assert result.latex == "$b=2$"
        assert result.confidence == 0.95

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    async def test_recognize_handles_no_formula(self, mock_image_open, mock_p2t_class):
        """Test handling when no formula is found — fall back to text content."""
        mock_p2t = MagicMock()
        mock_p2t.recognize_page.return_value = [
            {"type": "text", "text": "Hello world", "confidence": 0.8},
        ]
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()
        result = await engine.recognize(b"fake_image", OcrOptions())

        assert result.latex is not None
        assert "Hello world" in result.latex
        assert result.confidence == 0.8

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    async def test_recognize_handles_empty_result(self, mock_image_open, mock_p2t_class):
        """Test handling when Pix2Text returns empty result list."""
        mock_p2t = MagicMock()
        mock_p2t.recognize_page.return_value = []
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()
        result = await engine.recognize(b"fake_image", OcrOptions())

        assert result.latex == ""
        assert result.confidence == 0.0

    # ------------------------------------------------------------------
    # Edge cases: empty / corrupt image
    # ------------------------------------------------------------------

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    async def test_recognize_empty_image_raises(self, mock_image_open, mock_p2t_class):
        """Empty image should raise OSError during processing."""
        mock_image_open.side_effect = OSError("empty image")
        mock_p2t = MagicMock()
        mock_p2t_class.from_config.return_value = mock_p2t

        engine = Pix2TextEngine()
        with pytest.raises(OSError, match="empty image"):
            await engine.recognize(b"", OcrOptions())

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    async def test_recognize_corrupt_image_raises(self, mock_image_open, mock_p2t_class):
        """Corrupt image should raise UnidentifiedImageError."""
        from PIL import UnidentifiedImageError

        mock_image_open.side_effect = UnidentifiedImageError("cannot identify image")
        mock_p2t = MagicMock()
        mock_p2t_class.from_config.return_value = mock_p2t

        engine = Pix2TextEngine()
        with pytest.raises(UnidentifiedImageError, match="cannot identify image"):
            await engine.recognize(b"corrupt_data", OcrOptions())

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text", MagicMock)
    @patch("sidecar.ocr_engines.pix2text_engine.ort")
    def test_validate_config_checks_onnxruntime(self, mock_ort):
        """Test that validate_config checks ONNX Runtime availability."""
        mock_ort.get_available_providers.return_value = [
            "CPUExecutionProvider",
        ]

        engine = Pix2TextEngine()
        result = engine.validate_config()

        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert "ONNX Runtime" in result.message

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text", MagicMock)
    @patch("sidecar.ocr_engines.pix2text_engine.ort")
    def test_validate_config_no_providers(self, mock_ort):
        """Test that validate_config fails when no providers available."""
        mock_ort.get_available_providers.return_value = []

        engine = Pix2TextEngine()
        result = engine.validate_config()

        assert isinstance(result, ValidationResult)
        assert result.valid is False

    def test_validate_config_when_pix2text_not_installed(self):
        """Test that validate_config fails when pix2text is not installed."""
        import sidecar.ocr_engines.pix2text_engine as mod
        orig_avail = mod.PIX2TEXT_AVAILABLE
        orig_p2t = mod.Pix2Text
        mod.PIX2TEXT_AVAILABLE = False
        mod.Pix2Text = None

        try:
            engine = Pix2TextEngine()
            result = engine.validate_config()

            assert isinstance(result, ValidationResult)
            assert result.valid is False
            assert "not installed" in result.message.lower()
        finally:
            mod.PIX2TEXT_AVAILABLE = orig_avail
            mod.Pix2Text = orig_p2t

    def test_get_rate_limit_status_returns_none(self):
        """Local engine has no rate limits."""
        status = self.engine.get_rate_limit_status()
        assert status is None

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    async def test_pix2text_non_blocking(self, mock_image_open, mock_p2t_class):
        """Concurrent recognize() calls should not block the event loop.

        If recognize_page() ran on the event loop thread, 3 calls with
        0.2s sleep each would take ~0.6s.  With run_in_executor they
        execute in parallel threads and finish in ~0.2s.
        """
        mock_p2t = MagicMock()

        def slow_recognize(img):
            time.sleep(0.2)
            return [{"type": "formula", "text": "$x$", "confidence": 0.9}]

        mock_p2t.recognize_page.side_effect = slow_recognize
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()

        # Pre-initialize so init lock doesn't affect the concurrency test
        await engine._ensure_initialized()

        start = time.time()
        results = await asyncio.gather(
            engine.recognize(b"img1", OcrOptions()),
            engine.recognize(b"img2", OcrOptions()),
            engine.recognize(b"img3", OcrOptions()),
        )
        elapsed = time.time() - start

        # Sequential would be ~0.6s; parallel via executor should be ~0.2s
        assert elapsed < 0.5, (
            f"Concurrent calls took {elapsed:.2f}s, expected < 0.5s — "
            "event loop likely blocked by synchronous recognize_page()"
        )
        assert len(results) == 3
        for r in results:
            assert isinstance(r, OcrResult)
            assert r.confidence == 0.9
