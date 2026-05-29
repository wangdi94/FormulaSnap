"""Tests for Pix2Text OCR engine (local free backend)."""

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
    def test_recognize_calls_pix2text(self, mock_image_open, mock_p2t_class):
        """Test that recognize() calls Pix2Text API and extracts best formula."""
        mock_p2t = MagicMock()
        mock_p2t.recognize_page.return_value = [
            {"type": "formula", "text": "$x^2 + 5x + 6 = 0$", "confidence": 0.95},
        ]
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()
        result = engine.recognize(b"fake_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "x^2" in result.latex
        assert result.confidence > 0
        assert result.backend == "pix2text"
        assert result.timing_ms >= 0

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    def test_recognize_returns_highest_confidence_formula(self, mock_image_open, mock_p2t_class):
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
        result = engine.recognize(b"fake_image", OcrOptions())

        assert result.latex == "$b=2$"
        assert result.confidence == 0.95

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    def test_recognize_handles_no_formula(self, mock_image_open, mock_p2t_class):
        """Test handling when no formula is found — fall back to text content."""
        mock_p2t = MagicMock()
        mock_p2t.recognize_page.return_value = [
            {"type": "text", "text": "Hello world", "confidence": 0.8},
        ]
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()
        result = engine.recognize(b"fake_image", OcrOptions())

        assert result.latex is not None
        assert "Hello world" in result.latex
        assert result.confidence == 0.8

    @patch("sidecar.ocr_engines.pix2text_engine.Pix2Text")
    @patch("PIL.Image.open")
    def test_recognize_handles_empty_result(self, mock_image_open, mock_p2t_class):
        """Test handling when Pix2Text returns empty result list."""
        mock_p2t = MagicMock()
        mock_p2t.recognize_page.return_value = []
        mock_p2t_class.from_config.return_value = mock_p2t
        mock_image_open.return_value = MagicMock()

        engine = Pix2TextEngine()
        result = engine.recognize(b"fake_image", OcrOptions())

        assert result.latex == ""
        assert result.confidence == 0.0

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

    @patch("sidecar.ocr_engines.pix2text_engine.PIX2TEXT_AVAILABLE", False)
    def test_validate_config_when_pix2text_not_installed(self):
        """Test that validate_config fails when pix2text is not installed."""
        engine = Pix2TextEngine()
        result = engine.validate_config()

        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert "not installed" in result.message.lower()

    def test_get_rate_limit_status_returns_none(self):
        """Local engine has no rate limits."""
        status = self.engine.get_rate_limit_status()
        assert status is None
