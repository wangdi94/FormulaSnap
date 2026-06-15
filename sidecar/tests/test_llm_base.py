"""Tests for LLM-based OCR engines (OpenAI Vision)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sidecar.ocr_engines.interface import (
    ApiKeyError,
    NetworkError,
    OcrOptions,
    OcrResult,
    RateLimitError,
)
from sidecar.ocr_engines.openai_engine import OpenAIEngine


class TestOpenAIEngine:
    def setup_method(self):
        import sidecar.ocr_engines.openai_engine as mod
        self._orig_avail = mod.OPENAI_AVAILABLE
        mod.OPENAI_AVAILABLE = True
        self.engine = OpenAIEngine(api_key="sk-test123456789")

    def teardown_method(self):
        import sidecar.ocr_engines.openai_engine as mod
        mod.OPENAI_AVAILABLE = self._orig_avail

    @patch('sidecar.ocr_engines.openai_engine.AsyncOpenAI')
    async def test_recognize_success(self, mock_async_openai):
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "$E = mc^2$"
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await self.engine.recognize(b"fake_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "E = mc^2" in result.latex
        assert result.backend == "openai"
        assert result.cost_estimate is not None

    @patch('sidecar.ocr_engines.openai_engine.AsyncOpenAI')
    async def test_recognize_strips_markdown(self, mock_async_openai):
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "```latex\n\\frac{a}{b}\n```"
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await self.engine.recognize(b"fake_image", OcrOptions())

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

    def test_get_rate_limit_status_returns_none(self):
        """OpenAI SDK does not expose rate limit info."""
        assert self.engine.get_rate_limit_status() is None

    # -- error mapping -------------------------------------------------------

    @patch('sidecar.ocr_engines.openai_engine.AsyncOpenAI')
    async def test_recognize_authentication_error(self, mock_async_openai):
        """OpenAI AuthenticationError is mapped to ApiKeyError."""
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        auth_err = type("AuthenticationError", (Exception,), {})
        mock_client.chat.completions.create = AsyncMock(side_effect=auth_err("bad key"))

        import sidecar.ocr_engines.openai_engine as mod
        original = mod._AuthenticationError
        mod._AuthenticationError = auth_err

        with pytest.raises(ApiKeyError, match="Invalid OpenAI API key"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._AuthenticationError = original

    @patch('sidecar.ocr_engines.openai_engine.AsyncOpenAI')
    async def test_recognize_rate_limit_error(self, mock_async_openai):
        """OpenAI RateLimitError is mapped to ocr RateLimitError."""
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        rate_err = type("RateLimitError", (Exception,), {})
        mock_client.chat.completions.create = AsyncMock(side_effect=rate_err("rate limited"))

        import sidecar.ocr_engines.openai_engine as mod
        original = mod._RateLimitError
        mod._RateLimitError = rate_err

        with pytest.raises(RateLimitError, match="OpenAI rate limit"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._RateLimitError = original

    @patch('sidecar.ocr_engines.openai_engine.AsyncOpenAI')
    async def test_recognize_connection_error(self, mock_async_openai):
        """OpenAI APIConnectionError is mapped to NetworkError."""
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        conn_err = type("APIConnectionError", (Exception,), {})
        mock_client.chat.completions.create = AsyncMock(side_effect=conn_err("connection failed"))

        import sidecar.ocr_engines.openai_engine as mod
        original = mod._APIConnectionError
        mod._APIConnectionError = conn_err

        with pytest.raises(NetworkError, match="Failed to connect to OpenAI"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._APIConnectionError = original

    async def test_recognize_no_key_raises(self):
        """Recognize with empty key raises ApiKeyError immediately."""
        engine = OpenAIEngine(api_key="")
        with pytest.raises(ApiKeyError, match="not configured"):
            await engine.recognize(b"img", OcrOptions())

    async def test_recognize_package_not_installed(self):
        """When openai is missing, recognize raises ApiKeyError."""
        import sidecar.ocr_engines.openai_engine as mod
        orig_avail = mod.OPENAI_AVAILABLE
        orig_mod = mod.openai
        mod.OPENAI_AVAILABLE = False
        mod.openai = None  # type: ignore[assignment]

        with pytest.raises(ApiKeyError, match="not installed"):
            await self.engine.recognize(b"img", OcrOptions())

        mod.OPENAI_AVAILABLE = orig_avail
        mod.openai = orig_mod
