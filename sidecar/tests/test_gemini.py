"""Tests for Gemini Vision OCR engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrOptions,
    OcrResult,
    RateLimitError,
)


class TestGeminiEngine:
    """Tests for GeminiEngine OCR backend."""

    def setup_method(self):
        import sidecar.ocr_engines.gemini_engine as mod
        self._orig_avail = mod.GEMINI_AVAILABLE
        self._orig_types = mod.types
        mod.GEMINI_AVAILABLE = True
        mod.types = MagicMock()
        from sidecar.ocr_engines.gemini_engine import GeminiEngine
        self.engine = GeminiEngine(api_key="AIzaSyFAKE_KEY_1234567890")

    def teardown_method(self):
        import sidecar.ocr_engines.gemini_engine as mod
        mod.GEMINI_AVAILABLE = self._orig_avail
        mod.types = self._orig_types

    # ------------------------------------------------------------------
    # Successful recognition
    # ------------------------------------------------------------------

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_success(self, mock_genai):
        """Successful recognition returns OcrResult with LaTeX."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "$E = mc^2$"
        mock_response.usage_metadata.prompt_token_count = 500
        mock_response.usage_metadata.candidates_token_count = 265
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await self.engine.recognize(b"small_image", OcrOptions())

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
    async def test_recognize_large_image_compressed(self, mock_genai):
        """Images >7MB are compressed before sending to Gemini."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "\\int_0^1 x^2 dx"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Build a byte buffer > 7 MB
        large_image = b"\x89PNG\r\n" + b"\x00" * (8 * 1024 * 1024)

        with patch("sidecar.ocr_engines.gemini_engine._compress_image") as mock_compress:
            mock_compress.return_value = b"compressed_png"
            result = await self.engine.recognize(large_image, OcrOptions())

            mock_compress.assert_called_once_with(large_image)
        assert "int" in result.latex

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_small_image_not_compressed(self, mock_genai):
        """Images <=7MB are NOT compressed."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "$x$"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        small_image = b"small" * 100  # 500 bytes

        with patch("sidecar.ocr_engines.gemini_engine._compress_image") as mock_compress:
            await self.engine.recognize(small_image, OcrOptions())
            mock_compress.assert_not_called()

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_exactly_at_limit_not_compressed(self, mock_genai):
        """Image exactly at 7MB limit is NOT compressed (not > limit)."""
        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "$x$"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        exact_limit_image = b"\x00" * GEMINI_IMAGE_LIMIT

        with patch("sidecar.ocr_engines.gemini_engine._compress_image") as mock_compress:
            await self.engine.recognize(exact_limit_image, OcrOptions())
            mock_compress.assert_not_called()

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_one_byte_over_limit_compressed(self, mock_genai):
        """Image 1 byte over 7MB limit IS compressed."""
        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT

        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "\\int_0^1 x^2 dx"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        over_limit_image = b"\x00" * (GEMINI_IMAGE_LIMIT + 1)

        with patch("sidecar.ocr_engines.gemini_engine._compress_image") as mock_compress:
            mock_compress.return_value = b"compressed_png"
            await self.engine.recognize(over_limit_image, OcrOptions())
            mock_compress.assert_called_once_with(over_limit_image)

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_compress_runs_in_executor(self, mock_genai):
        """_compress_image is dispatched via run_in_executor, not blocking event loop."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "\\int_0^1 x^2 dx"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT
        large_image = b"\x00" * (GEMINI_IMAGE_LIMIT + 1)

        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=b"compressed_png")

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            result = await self.engine.recognize(large_image, OcrOptions())

        import sidecar.ocr_engines.gemini_engine as mod
        mock_loop.run_in_executor.assert_called_once_with(
            None, mod._compress_image, large_image
        )
        assert "int" in result.latex

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_small_image_no_executor(self, mock_genai):
        """Small images do NOT call run_in_executor."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "$x$"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock()

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            await self.engine.recognize(b"small", OcrOptions())

        mock_loop.run_in_executor.assert_not_called()

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
        assert result.message == "API key format valid"

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
    async def test_recognize_no_api_key_raises(self, mock_genai):
        """Recognize with empty key raises ApiKeyError."""
        from sidecar.ocr_engines.gemini_engine import GeminiEngine
        engine = GeminiEngine(api_key="")
        with pytest.raises(ApiKeyError):
            await engine.recognize(b"img", OcrOptions())

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_network_error(self, mock_genai):
        """Network failures are wrapped as NetworkError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.aio.models.generate_content = AsyncMock(side_effect=ConnectionError("timeout"))

        with pytest.raises(NetworkError):
            await self.engine.recognize(b"img", OcrOptions())

    # ------------------------------------------------------------------
    # SDK exception mapping
    # ------------------------------------------------------------------

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_auth_error_401(self, mock_genai):
        """Gemini ClientError 401 is mapped to ApiKeyError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        auth_err = type("ClientError", (Exception,), {"code": 401})
        mock_client.aio.models.generate_content = AsyncMock(side_effect=auth_err("unauthorized"))

        import sidecar.ocr_engines.gemini_engine as mod
        original = mod._ClientError
        mod._ClientError = auth_err

        with pytest.raises(ApiKeyError, match="Invalid Gemini API key"):
            await self.engine.recognize(b"img", OcrOptions())

        mod._ClientError = original

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_auth_error_403(self, mock_genai):
        """Gemini ClientError 403 is mapped to ApiKeyError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        auth_err = type("ClientError", (Exception,), {"code": 403})
        mock_client.aio.models.generate_content = AsyncMock(side_effect=auth_err("forbidden"))

        import sidecar.ocr_engines.gemini_engine as mod
        original = mod._ClientError
        mod._ClientError = auth_err

        with pytest.raises(ApiKeyError, match="Invalid Gemini API key"):
            await self.engine.recognize(b"img", OcrOptions())

        mod._ClientError = original

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_rate_limit_error(self, mock_genai):
        """Gemini ClientError 429 is mapped to RateLimitError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        rate_err = type("ClientError", (Exception,), {"code": 429})
        mock_client.aio.models.generate_content = AsyncMock(side_effect=rate_err("rate limited"))

        import sidecar.ocr_engines.gemini_engine as mod
        original = mod._ClientError
        mod._ClientError = rate_err

        with pytest.raises(RateLimitError, match="Gemini rate limit"):
            await self.engine.recognize(b"img", OcrOptions())

        mod._ClientError = original

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_server_error(self, mock_genai):
        """Gemini ServerError is mapped to NetworkError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        server_err = type("ServerError", (Exception,), {})
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=server_err("internal error")
        )

        import sidecar.ocr_engines.gemini_engine as mod
        original = mod._ServerError
        mod._ServerError = server_err

        with pytest.raises(NetworkError, match="Gemini server error"):
            await self.engine.recognize(b"img", OcrOptions())

        mod._ServerError = original

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_unknown_client_error_code(self, mock_genai):
        """Gemini ClientError with unknown code is mapped to NetworkError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        unknown_err = type("ClientError", (Exception,), {"code": 500})
        mock_client.aio.models.generate_content = AsyncMock(side_effect=unknown_err("server error"))

        import sidecar.ocr_engines.gemini_engine as mod
        original = mod._ClientError
        mod._ClientError = unknown_err

        with pytest.raises(NetworkError, match="Gemini API error"):
            await self.engine.recognize(b"img", OcrOptions())

        mod._ClientError = original

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_recognize_timeout_error(self, mock_genai):
        """TimeoutError is mapped to NetworkError."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.aio.models.generate_content = AsyncMock(side_effect=TimeoutError("timed out"))

        with pytest.raises(NetworkError, match="Gemini network error"):
            await self.engine.recognize(b"img", OcrOptions())

    # ------------------------------------------------------------------
    # aclose
    # ------------------------------------------------------------------

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_gemini_aclose(self, mock_genai):
        """aclose awaits client.close() and sets _client to None."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        self.engine._client = mock_client

        await self.engine.aclose()

        mock_client.close.assert_awaited_once()
        assert self.engine._client is None

    @patch("sidecar.ocr_engines.gemini_engine.genai")
    async def test_gemini_aclose_no_client(self, mock_genai):
        """aclose is safe when _client is already None."""
        self.engine._client = None
        await self.engine.aclose()


class TestDetectMimeType:
    """Tests for detect_mime_type helper."""

    def test_detect_png(self):
        from sidecar.ocr_engines.image_utils import detect_mime_type
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert detect_mime_type(png_header) == "image/png"

    def test_detect_gif(self):
        from sidecar.ocr_engines.image_utils import detect_mime_type
        gif_header = b"GIF89a" + b"\x00" * 100
        assert detect_mime_type(gif_header) == "image/gif"

    def test_detect_webp(self):
        from sidecar.ocr_engines.image_utils import detect_mime_type
        webp_header = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert detect_mime_type(webp_header) == "image/webp"

    def test_detect_jpeg_fallback(self):
        from sidecar.ocr_engines.image_utils import detect_mime_type
        jpeg_header = b"\xff\xd8\xff" + b"\x00" * 100
        assert detect_mime_type(jpeg_header) == "image/jpeg"

    def test_detect_unknown_defaults_to_png(self):
        from sidecar.ocr_engines.image_utils import detect_mime_type
        assert detect_mime_type(b"\x00" * 100) == "image/png"


class TestCompressImage:
    """Tests for _compress_image helper."""

    def test_raises_value_error_after_max_iterations(self):
        from unittest.mock import MagicMock, patch

        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT, _compress_image

        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.size = (100, 100)
        mock_img.convert.return_value = mock_img

        def fake_save(buf, **kwargs):
            buf.write(b"\x00" * (GEMINI_IMAGE_LIMIT + 1))

        mock_img.save.side_effect = fake_save

        with patch("PIL.Image.open", return_value=mock_img):
            with pytest.raises(ValueError, match="Unable to compress image"):
                _compress_image(b"fake_large_image")

    def test_returns_compressed_data_when_within_limit(self):
        import io

        from PIL import Image

        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT, _compress_image

        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        small_image = buf.getvalue()

        assert len(small_image) <= GEMINI_IMAGE_LIMIT
        result = _compress_image(small_image)
        assert len(result) <= GEMINI_IMAGE_LIMIT

    def test_compress_image_mime_type(self):
        """PNG input yields JPEG output after _compress_image."""
        import io

        from PIL import Image

        from sidecar.ocr_engines.gemini_engine import _compress_image
        from sidecar.ocr_engines.image_utils import detect_mime_type

        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_image = buf.getvalue()

        compressed = _compress_image(png_image)
        mime_type = detect_mime_type(compressed)

        assert mime_type == "image/jpeg", f"Expected image/jpeg, got {mime_type}"

    def test_compress_image_empty_raises(self):
        """Empty image raises an exception."""
        from sidecar.ocr_engines.gemini_engine import _compress_image

        with pytest.raises(Exception):
            _compress_image(b"")

    def test_compress_image_just_over_limit(self):
        """A real image just over the limit compresses successfully."""
        import io

        from PIL import Image

        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT, _compress_image

        # Create a large enough image to exceed the limit
        img = Image.new("RGB", (2000, 2000), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        large_image = buf.getvalue()

        # Ensure it's actually over the limit
        if len(large_image) <= GEMINI_IMAGE_LIMIT:
            # Need a bigger image — duplicate it
            large_image = large_image * ((GEMINI_IMAGE_LIMIT // len(large_image)) + 1)

        result = _compress_image(large_image)
        assert len(result) <= GEMINI_IMAGE_LIMIT
        assert len(result) > 0
