"""Tests for Gemini Vision OCR engine."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrOptions,
    OcrResult,
    RateLimitError,
    ValidationResult,
)


class TestGeminiEngine:
    """Tests for GeminiEngine OCR backend."""

    def setup_method(self):
        from sidecar.ocr_engines.gemini_engine import GeminiEngine
        self.engine = GeminiEngine(api_key="AIzaSyFAKE_KEY_1234567890")

    # ------------------------------------------------------------------
    # Successful recognition
    # ------------------------------------------------------------------

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    def test_recognize_success(self, mock_genai):
        """Successful recognition returns OcrResult with LaTeX."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "$E = mc^2$"
        mock_response.usage_metadata.prompt_token_count = 500
        mock_response.usage_metadata.candidates_token_count = 265
        mock_client.models.generate_content.return_value = mock_response

        result = self.engine.recognize(b"small_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "E = mc^2" in result.latex
        assert result.backend == "gemini"
        assert result.cost_estimate is not None
        assert result.cost_estimate.tokens_used == 765
        assert result.timing_ms >= 0

    # ------------------------------------------------------------------
    # Large image compression
    # ------------------------------------------------------------------

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    def test_recognize_large_image_compressed(self, mock_genai):
        """Images >7MB are compressed before sending to Gemini."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "\\int_0^1 x^2 dx"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.models.generate_content.return_value = mock_response

        # Build a byte buffer > 7 MB
        large_image = b"\x89PNG\r\n" + b"\x00" * (8 * 1024 * 1024)

        with patch("sidecar.ocr_engines.gemini_engine._compress_image") as mock_compress:
            mock_compress.return_value = b"compressed_png"
            result = self.engine.recognize(large_image, OcrOptions())

            mock_compress.assert_called_once_with(large_image)
        assert "int" in result.latex

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    def test_recognize_small_image_not_compressed(self, mock_genai):
        """Images <=7MB are NOT compressed."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "$x$"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.models.generate_content.return_value = mock_response

        small_image = b"small" * 100  # 500 bytes

        with patch("sidecar.ocr_engines.gemini_engine._compress_image") as mock_compress:
            self.engine.recognize(small_image, OcrOptions())
            mock_compress.assert_not_called()

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def test_estimate_cost(self):
        """estimate_cost returns a valid CostEstimate."""
        cost = self.engine.estimate_cost(b"fake_image" * 1000)

        assert cost is not None
        assert isinstance(cost, CostEstimate)
        assert cost.estimated_cost_usd > 0
        # 765 input tokens * $1.25/MTok + 265 output tokens * $10/MTok
        expected = 765 * (1.25 / 1_000_000) + 265 * (10.0 / 1_000_000)
        assert abs(cost.estimated_cost_usd - expected) < 1e-9

    # ------------------------------------------------------------------
    # Config validation
    # ------------------------------------------------------------------

    def test_validate_config_with_key(self):
        """Valid key returns ValidationResult with valid=True."""
        result = self.engine.validate_config()
        assert result.valid is True
        assert result.message

    def test_validate_config_no_key(self):
        """Missing key returns ValidationResult with valid=False."""
        from sidecar.ocr_engines.gemini_engine import GeminiEngine
        engine = GeminiEngine(api_key="")
        result = engine.validate_config()
        assert result.valid is False
        assert "GEMINI_API_KEY" in result.message

    def test_validate_config_env_fallback(self):
        """API key falls back to GEMINI_API_KEY env var."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "AIzaSyEnvKey"}):
            from sidecar.ocr_engines.gemini_engine import GeminiEngine
            engine = GeminiEngine()
            assert engine._api_key == "AIzaSyEnvKey"

    # ------------------------------------------------------------------
    # Rate limit / error handling
    # ------------------------------------------------------------------

    def test_get_rate_limit_status_returns_none(self):
        """Gemini SDK does not expose rate limit info."""
        assert self.engine.get_rate_limit_status() is None

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    def test_recognize_no_api_key_raises(self, mock_genai):
        """Recognize with empty key raises ApiKeyError."""
        from sidecar.ocr_engines.gemini_engine import GeminiEngine
        engine = GeminiEngine(api_key="")
        with pytest.raises(ApiKeyError):
            engine.recognize(b"img", OcrOptions())

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    def test_recognize_network_error(self, mock_genai):
        """Network failures are wrapped as NetworkError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.side_effect = ConnectionError("timeout")

        with pytest.raises(NetworkError):
            self.engine.recognize(b"img", OcrOptions())
