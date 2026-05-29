import pytest
from unittest.mock import patch, MagicMock
from sidecar.ocr_engines.mathpix_engine import MathpixEngine
from sidecar.ocr_engines.interface import (
    OcrOptions, OcrResult, ValidationResult, CostEstimate,
    ApiKeyError, RateLimitError, NetworkError
)


class TestMathpixEngine:
    def setup_method(self):
        self.engine = MathpixEngine()

    def test_estimate_cost_returns_fixed_rate(self):
        cost = self.engine.estimate_cost(b"fake_image")
        assert cost is not None
        assert cost.estimated_cost_usd > 0

    @patch('sidecar.ocr_engines.mathpix_engine.httpx')
    def test_recognize_success(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "latex": "$x^2 + 5x + 6 = 0$",
            "confidence": 0.95
        }
        mock_httpx.post.return_value = mock_response

        engine = MathpixEngine(app_id="test_id", app_key="test_key")
        result = engine.recognize(b"fake_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "x^2" in result.latex
        assert result.backend == "mathpix"

    @patch('sidecar.ocr_engines.mathpix_engine.httpx')
    def test_recognize_invalid_key(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid credentials"}
        mock_httpx.post.return_value = mock_response

        engine = MathpixEngine(app_id="bad_id", app_key="bad_key")

        with pytest.raises(ApiKeyError):
            engine.recognize(b"fake_image", OcrOptions())

    @patch('sidecar.ocr_engines.mathpix_engine.httpx')
    def test_recognize_rate_limit(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limited"}
        mock_response.headers = {"Retry-After": "60"}
        mock_httpx.post.return_value = mock_response

        engine = MathpixEngine(app_id="test_id", app_key="test_key")

        with pytest.raises(RateLimitError) as exc_info:
            engine.recognize(b"fake_image", OcrOptions())
        assert exc_info.value.retry_after == 60

    def test_validate_config_no_key(self):
        engine = MathpixEngine()
        result = engine.validate_config()
        assert result.valid is False
        assert "key" in result.message.lower() or "id" in result.message.lower()

    def test_validate_config_with_key(self):
        engine = MathpixEngine(app_id="test_id", app_key="test_key")
        result = engine.validate_config()
        # Should be valid format (actual connectivity test would need real API)
        assert isinstance(result, ValidationResult)
