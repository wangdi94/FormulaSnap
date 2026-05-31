"""Google Gemini Vision OCR engine.

Uses Gemini 2.5 Pro to extract LaTeX from images.
"""

from __future__ import annotations

import io
import os
import time
from typing import Optional

try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    GEMINI_AVAILABLE = True
    _ClientError = genai_errors.ClientError
    _ServerError = genai_errors.ServerError
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    genai_errors = None  # type: ignore[assignment]
    GEMINI_AVAILABLE = False
    _ClientError = Exception
    _ServerError = Exception

from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrOptions,
    OcrResult,
    RateLimitError as OcrRateLimitError,
    RateLimitStatus,
    ValidationResult,
)
from sidecar.ocr_engines.llm_base import LlmProvider

# Gemini 2.5 Pro pricing (per million tokens)
GEMINI_INPUT_COST = 1.25 / 1_000_000
GEMINI_OUTPUT_COST = 10.00 / 1_000_000

# Gemini inline image limit: 7 MB
GEMINI_IMAGE_LIMIT = 7 * 1024 * 1024

GEMINI_MODEL = "gemini-2.5-pro"


def _detect_mime_type(image: bytes) -> str:
    """Detect image MIME type from magic bytes.

    Returns 'image/png' for PNG, 'image/gif' for GIF, 'image/webp' for WebP,
    and 'image/jpeg' as default fallback.
    """
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image[:3] == b"GIF":
        return "image/gif"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _compress_image(image: bytes) -> bytes:
    """Compress an image that exceeds Gemini's 7 MB inline limit.

    Uses PIL to downscale and re-encode as JPEG with progressive quality
    reduction until the result fits under the limit.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(image))

    try:
        # Convert to RGB if necessary (e.g. RGBA PNG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Progressive downscale + quality reduction
        quality = 85
        max_side = 2048
        data = b""

        # Use LANCZOS resampling (int constant 1 for broad compatibility)
        lanczos = getattr(Image, "LANCZOS", getattr(Image.Resampling, "LANCZOS", 1))

        for _ in range(10):  # max 10 iterations
            # Resize if largest side exceeds max_side
            w, h = img.size
            if max(w, h) > max_side:
                scale = max_side / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), lanczos)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()

            if len(data) <= GEMINI_IMAGE_LIMIT:
                return data

            # Reduce quality and max_side for next iteration
            quality = max(quality - 15, 30)
            max_side = int(max_side * 0.75)

        raise ValueError(
            f"Unable to compress image below {GEMINI_IMAGE_LIMIT} bytes "
            f"after 10 iterations (best effort: {len(data)} bytes)"
        )
    finally:
        img.close()


class GeminiEngine(LlmProvider):
    """Google Gemini 2.5 Pro Vision OCR backend."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        """Recognize math in image via Gemini 2.5 Pro Vision."""
        if not self._api_key:
            raise ApiKeyError("Gemini API key not configured")

        if not GEMINI_AVAILABLE or genai is None or types is None:
            raise ApiKeyError("google-genai package not installed")

        start_time = time.time()

        # Compress if image exceeds Gemini's 7 MB inline limit
        effective_image = image
        if len(image) > GEMINI_IMAGE_LIMIT:
            effective_image = _compress_image(image)

        # Detect MIME type from original image (before compression)
        mime_type = _detect_mime_type(image)

        try:
            client = genai.Client(api_key=self._api_key)

            image_part = types.Part.from_bytes(
                data=effective_image, mime_type=mime_type
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    image_part,
                    "Extract all mathematical formulas from this image.",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self._build_ocr_prompt(),
                ),
            )
        except _ClientError as exc:
            # 401/403 → authentication error, 429 → rate limit
            code = getattr(exc, "code", 0)
            if code in (401, 403):
                raise ApiKeyError("Invalid Gemini API key") from exc
            if code == 429:
                raise OcrRateLimitError(
                    "Gemini rate limit exceeded", retry_after=60
                ) from exc
            raise NetworkError(f"Gemini API error: {exc}") from exc
        except _ServerError as exc:
            raise NetworkError(f"Gemini server error: {exc}") from exc
        except (ConnectionError, TimeoutError, OSError) as exc:
            raise NetworkError(f"Gemini network error: {exc}") from exc

        raw_text = response.text or ""
        latex = self._parse_response(raw_text)

        # Extract token usage from response
        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 765) or 765
        output_tokens = getattr(usage, "candidates_token_count", 265) or 265
        total_tokens = input_tokens + output_tokens

        cost_usd = (input_tokens * GEMINI_INPUT_COST) + (
            output_tokens * GEMINI_OUTPUT_COST
        )
        timing_ms = int((time.time() - start_time) * 1000)

        return OcrResult(
            latex=latex,
            confidence=None,  # LLM doesn't provide confidence
            backend="gemini",
            timing_ms=timing_ms,
            cost_estimate=CostEstimate(
                tokens_used=total_tokens, estimated_cost_usd=cost_usd
            ),
        )

    def estimate_cost(self, image: bytes) -> Optional[CostEstimate]:
        """Estimate cost based on Gemini 2.5 Pro rates."""
        tokens = self._estimate_tokens(image)
        cost_usd = tokens * GEMINI_INPUT_COST + 265 * GEMINI_OUTPUT_COST
        return CostEstimate(tokens_used=tokens, estimated_cost_usd=cost_usd)

    def validate_config(self) -> ValidationResult:
        """Check that API key is present and well-formed."""
        if not self._api_key:
            return ValidationResult(
                valid=False, message="GEMINI_API_KEY not set"
            )

        return ValidationResult(valid=True, message="API key format valid")

    def get_rate_limit_status(self) -> Optional[RateLimitStatus]:
        """Gemini SDK does not expose rate limit info."""
        return None
