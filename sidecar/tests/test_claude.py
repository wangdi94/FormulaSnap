"""Tests for Claude Vision OCR engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sidecar.ocr_engines.claude_engine import ClaudeEngine
from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrOptions,
    OcrResult,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_anthropic_response(
    text: str = "$E = mc^2$", input_tokens: int = 500, output_tokens: int = 265
):
    """Build a fake Anthropic messages.create response."""
    content_block = MagicMock()
    content_block.text = text

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClaudeEngine:
    def setup_method(self):
        import sidecar.ocr_engines.claude_engine as mod
        self._orig_avail = mod.ANTHROPIC_AVAILABLE
        mod.ANTHROPIC_AVAILABLE = True
        self.engine = ClaudeEngine(api_key="sk-ant-test123456789")

    def teardown_method(self):
        import sidecar.ocr_engines.claude_engine as mod
        mod.ANTHROPIC_AVAILABLE = self._orig_avail

    # -- recognize success --------------------------------------------------

    @patch("sidecar.ocr_engines.claude_engine.anthropic")
    async def test_recognize_success(self, mock_anthropic):
        """Successful OCR returns OcrResult with correct fields."""
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("$E = mc^2$")
        )

        result = await self.engine.recognize(b"fake_image", OcrOptions())

        assert isinstance(result, OcrResult)
        assert "E = mc^2" in result.latex
        assert result.backend == "claude"
        assert result.timing_ms >= 0
        assert result.cost_estimate is not None
        assert result.cost_estimate.tokens_used == 765  # 500 + 265
        assert result.cost_estimate.estimated_cost_usd > 0

    # -- markdown stripping -------------------------------------------------

    @patch("sidecar.ocr_engines.claude_engine.anthropic")
    async def test_recognize_strips_markdown(self, mock_anthropic):
        """Response wrapped in markdown fences is cleaned."""
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("```latex\n\\frac{a}{b}\n```")
        )

        result = await self.engine.recognize(b"fake_image", OcrOptions())

        assert "```" not in result.latex
        assert "\\frac{a}{b}" in result.latex

    # -- invalid API key ----------------------------------------------------

    @patch("sidecar.ocr_engines.claude_engine.anthropic")
    async def test_recognize_authentication_error(self, mock_anthropic):
        """AnthropicAuthenticationError is mapped to ApiKeyError."""
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        auth_err = type("AuthenticationError", (Exception,), {})
        mock_anthropic.AuthenticationError = auth_err
        mock_client.messages.create = AsyncMock(side_effect=auth_err("bad key"))

        # Re-patch the module-level alias
        import sidecar.ocr_engines.claude_engine as mod
        original = mod._AuthenticationError
        mod._AuthenticationError = auth_err

        with pytest.raises(ApiKeyError, match="Invalid Anthropic API key"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._AuthenticationError = original

    @patch("sidecar.ocr_engines.claude_engine.anthropic")
    async def test_recognize_rate_limit_error(self, mock_anthropic):
        """Anthropic RateLimitError is mapped to ocr RateLimitError."""
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        rate_err = type("RateLimitError", (Exception,), {})
        mock_anthropic.RateLimitError = rate_err
        mock_client.messages.create = AsyncMock(side_effect=rate_err("rate limited"))

        import sidecar.ocr_engines.claude_engine as mod
        original = mod._RateLimitError
        mod._RateLimitError = rate_err

        with pytest.raises(RateLimitError, match="Claude rate limit"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._RateLimitError = original

    @patch("sidecar.ocr_engines.claude_engine.anthropic")
    async def test_recognize_connection_error(self, mock_anthropic):
        """Anthropic APIConnectionError is mapped to NetworkError."""
        mock_client = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        conn_err = type("APIConnectionError", (Exception,), {})
        mock_anthropic.APIConnectionError = conn_err
        mock_client.messages.create = AsyncMock(side_effect=conn_err("connection failed"))

        import sidecar.ocr_engines.claude_engine as mod
        original = mod._APIConnectionError
        mod._APIConnectionError = conn_err

        with pytest.raises(NetworkError, match="Failed to connect to Claude"):
            await self.engine.recognize(b"fake_image", OcrOptions())

        mod._APIConnectionError = original

    # -- missing API key at call time ---------------------------------------

    async def test_recognize_no_key_raises(self):
        """Recognize with empty key raises ApiKeyError immediately."""
        engine = ClaudeEngine(api_key="")
        with pytest.raises(ApiKeyError, match="not configured"):
            await engine.recognize(b"img", OcrOptions())

    # -- cost estimation ----------------------------------------------------

    def test_estimate_cost(self):
        """estimate_cost returns positive cost based on Claude rates."""
        cost = self.engine.estimate_cost(b"fake_image" * 1000)
        assert cost is not None
        assert isinstance(cost, CostEstimate)
        assert cost.estimated_cost_usd > 0
        # 765 * $3/1M + 265 * $15/1M = 0.002295 + 0.003975 = 0.00627
        expected = 765 * (3.0 / 1_000_000) + 265 * (15.0 / 1_000_000)
        assert abs(cost.estimated_cost_usd - expected) < 1e-8

    # -- config validation --------------------------------------------------

    def test_validate_config_no_key(self):
        engine = ClaudeEngine(api_key="")
        result = engine.validate_config()
        assert result.valid is False
        assert "ANTHROPIC_API_KEY" in result.message

    def test_validate_config_with_key(self):
        result = self.engine.validate_config()
        assert result.valid is True

    # -- rate limit status --------------------------------------------------

    def test_get_rate_limit_status_returns_none(self):
        assert self.engine.get_rate_limit_status() is None

    # -- provider not installed ---------------------------------------------

    async def test_recognize_package_not_installed(self):
        """When anthropic is missing, recognize raises ApiKeyError."""
        import sidecar.ocr_engines.claude_engine as mod
        orig_avail = mod.ANTHROPIC_AVAILABLE
        orig_mod = mod.anthropic
        mod.ANTHROPIC_AVAILABLE = False
        mod.anthropic = None  # type: ignore[assignment]

        with pytest.raises(ApiKeyError, match="not installed"):
            await self.engine.recognize(b"img", OcrOptions())

        mod.ANTHROPIC_AVAILABLE = orig_avail
        mod.anthropic = orig_mod

    # -- aclose -------------------------------------------------------------

    async def test_aclose_calls_client_close(self):
        """aclose() calls client.close() and sets _client to None."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        self.engine._client = mock_client

        await self.engine.aclose()

        mock_client.close.assert_awaited_once()
        assert self.engine._client is None

    async def test_aclose_no_client(self):
        """aclose() is safe when _client is already None."""
        self.engine._client = None
        await self.engine.aclose()  # Should not raise

    async def test_aclose_idempotent(self):
        """Calling aclose() twice does not error; close() called only once."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        self.engine._client = mock_client

        await self.engine.aclose()
        await self.engine.aclose()  # Second call — no error

        mock_client.close.assert_awaited_once()
        assert self.engine._client is None
