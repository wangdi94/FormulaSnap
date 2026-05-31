"""Tests for OpenAI Vision OCR engine."""

import pytest
from unittest.mock import patch, MagicMock

from sidecar.ocr_engines.openai_engine import OpenAIEngine
from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrError,
    OcrOptions,
    OcrResult,
    RateLimitError,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_openai_response(text: str = "$E = mc^2$", total_tokens: int = 765,
                          prompt_tokens: int = 500, completion_tokens: int = 265):
    """Build a fake OpenAI chat.completions.create response."""
    message = MagicMock()
    message.content = text

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.total_tokens = total_tokens
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOpenAIEngine:
    def setup_method(self):
        import sidecar.ocr_engines.openai_engine as mod
        self._orig_avail = mod.OPENAI_AVAILABLE
        mod.OPENAI_AVAILABLE = True
        self.engine = OpenAIEngine(api_key="sk-test1234567890abcdef")

    def teardown_method(self):
        import sidecar.ocr_engines.openai_engine as mod
        mod.OPENAI_AVAILABLE = self._orig_avail

    # -- recognize success --------------------------------------------------

    @patch("sidecar.ocr_engines.openai_engine.openai")
    async def test_recognize_success(self, mock_openai):
        """Successful OCR returns OcrResult with correct fields."""
        mock_openai.chat.completions.create.return_value = _mock_openai_response("$E = mc^2$")

        result = await self.engine.recognize(b"fake_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "E = mc^2" in result.latex
        assert result.backend == "openai"
        assert result.timing_ms >= 0
        assert result.cost_estimate is not None
        assert result.cost_estimate.tokens_used == 765
        assert result.cost_estimate.estimated_cost_usd > 0

    # -- empty choices → OcrError ------------------------------------------

    @patch("sidecar.ocr_engines.openai_engine.openai")
    async def test_recognize_empty_choices_raises(self, mock_openai):
        """Empty choices list raises OcrError."""
        response = MagicMock()
        response.choices = []
        mock_openai.chat.completions.create.return_value = response

        with pytest.raises(OcrError, match="OpenAI 返回空结果"):
            await self.engine.recognize(b"fake_image", OcrOptions())

    # -- markdown stripping -------------------------------------------------

    @patch("sidecar.ocr_engines.openai_engine.openai")
    async def test_recognize_strips_markdown(self, mock_openai):
        """Response wrapped in markdown fences is cleaned."""
        mock_openai.chat.completions.create.return_value = _mock_openai_response(
            "```latex\n\\frac{a}{b}\n```"
        )

        result = await self.engine.recognize(b"fake_image", OcrOptions())

        assert "```" not in result.latex
        assert "\\frac{a}{b}" in result.latex

    # -- invalid API key ----------------------------------------------------

    @patch("sidecar.ocr_engines.openai_engine.openai")
    async def test_recognize_authentication_error(self, mock_openai):
        """OpenAI AuthenticationError is mapped to ApiKeyError."""
        auth_err = type("AuthenticationError", (Exception,), {})
        mock_openai.AuthenticationError = auth_err
        mock_openai.chat.completions.create.side_effect = auth_err("bad key")

        import sidecar.ocr_engines.openai_engine as mod
        original = mod._AuthenticationError
        mod._AuthenticationError = auth_err

        with pytest.raises(ApiKeyError, match="Invalid OpenAI API key"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._AuthenticationError = original

    @patch("sidecar.ocr_engines.openai_engine.openai")
    async def test_recognize_rate_limit_error(self, mock_openai):
        """OpenAI RateLimitError is mapped to ocr RateLimitError."""
        rate_err = type("RateLimitError", (Exception,), {})
        mock_openai.RateLimitError = rate_err
        mock_openai.chat.completions.create.side_effect = rate_err("rate limited")

        import sidecar.ocr_engines.openai_engine as mod
        original = mod._RateLimitError
        mod._RateLimitError = rate_err

        with pytest.raises(RateLimitError, match="OpenAI rate limit"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._RateLimitError = original

    @patch("sidecar.ocr_engines.openai_engine.openai")
    async def test_recognize_connection_error(self, mock_openai):
        """OpenAI APIConnectionError is mapped to NetworkError."""
        conn_err = type("APIConnectionError", (Exception,), {})
        mock_openai.APIConnectionError = conn_err
        mock_openai.chat.completions.create.side_effect = conn_err("connection failed")

        import sidecar.ocr_engines.openai_engine as mod
        original = mod._APIConnectionError
        mod._APIConnectionError = conn_err

        with pytest.raises(NetworkError, match="Failed to connect to OpenAI"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._APIConnectionError = original

    # -- missing API key at call time ---------------------------------------

    async def test_recognize_no_key_raises(self):
        """Recognize with empty key raises ApiKeyError immediately."""
        engine = OpenAIEngine(api_key="")
        with pytest.raises(ApiKeyError, match="not configured"):
            await engine.recognize(b"img", OcrOptions())

    # -- cost estimation ----------------------------------------------------

    def test_estimate_cost(self):
        """estimate_cost returns positive cost based on OpenAI rates."""
        cost = self.engine.estimate_cost(b"fake_image" * 1000)
        assert cost is not None
        assert isinstance(cost, CostEstimate)
        assert cost.estimated_cost_usd > 0

    # -- config validation --------------------------------------------------

    def test_validate_config_no_key(self):
        engine = OpenAIEngine(api_key="")
        result = engine.validate_config()
        assert result.valid is False
        assert "OPENAI_API_KEY" in result.message

    def test_validate_config_bad_prefix(self):
        engine = OpenAIEngine(api_key="bad-prefix")
        result = engine.validate_config()
        assert result.valid is False
        assert "sk-" in result.message

    def test_validate_config_with_key(self):
        result = self.engine.validate_config()
        assert result.valid is True

    # -- rate limit status --------------------------------------------------

    def test_get_rate_limit_status_returns_none(self):
        assert self.engine.get_rate_limit_status() is None

    # -- provider not installed ---------------------------------------------

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
