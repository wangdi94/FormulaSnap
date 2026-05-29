"""Tests for LLM-based OCR engines (OpenAI Vision)."""

import pytest
from unittest.mock import patch, MagicMock
from sidecar.ocr_engines.openai_engine import OpenAIEngine
from sidecar.ocr_engines.interface import OcrOptions, OcrResult, ApiKeyError


class TestOpenAIEngine:
    def setup_method(self):
        self.engine = OpenAIEngine(api_key="sk-test123456789")

    @patch('sidecar.ocr_engines.openai_engine.openai')
    def test_recognize_success(self, mock_openai):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "$E = mc^2$"
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        mock_openai.chat.completions.create.return_value = mock_response

        result = self.engine.recognize(b"fake_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "E = mc^2" in result.latex
        assert result.backend == "openai"
        assert result.cost_estimate is not None

    @patch('sidecar.ocr_engines.openai_engine.openai')
    def test_recognize_strips_markdown(self, mock_openai):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "```latex\n\\frac{a}{b}\n```"
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        mock_openai.chat.completions.create.return_value = mock_response

        result = self.engine.recognize(b"fake_image", OcrOptions())

        assert "```" not in result.latex
        assert "\\frac{a}{b}" in result.latex

    def test_estimate_cost(self):
        cost = self.engine.estimate_cost(b"fake_image" * 1000)
        assert cost is not None
        assert cost.estimated_cost_usd > 0

    def test_validate_config_no_key(self):
        engine = OpenAIEngine()
        result = engine.validate_config()
        assert result.valid is False

    def test_validate_config_with_key(self):
        result = self.engine.validate_config()
        assert result.valid is True
