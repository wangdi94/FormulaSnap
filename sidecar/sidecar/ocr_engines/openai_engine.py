"""OpenAI Vision OCR engine.

Uses GPT-4o to extract LaTeX from images.
"""

from __future__ import annotations

import base64
import os
import time

try:
    import openai
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
    _AuthenticationError = openai.AuthenticationError
    _RateLimitError = openai.RateLimitError
    _APIConnectionError = openai.APIConnectionError
except ImportError:
    openai = None  # type: ignore[assignment]
    AsyncOpenAI = None  # type: ignore[assignment,misc]
    OPENAI_AVAILABLE = False
    _AuthenticationError = Exception
    _RateLimitError = Exception
    _APIConnectionError = Exception

from sidecar.ocr_engines.image_utils import detect_mime_type
from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrError,
    OcrOptions,
    OcrResult,
    RateLimitStatus,
    ValidationResult,
)
from sidecar.ocr_engines.interface import (
    RateLimitError as OcrRateLimitError,
)
from sidecar.ocr_engines.llm_base import LlmProvider

# gpt-4o pricing (per million tokens)
OPENAI_INPUT_COST = 2.50 / 1_000_000
OPENAI_OUTPUT_COST = 10.00 / 1_000_000


class OpenAIEngine(LlmProvider):
    """OpenAI GPT-4o Vision OCR backend."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None  # AsyncOpenAI, 延迟初始化

    async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        """Recognize math in image via GPT-4o Vision."""
        if not self._api_key:
            raise ApiKeyError("OpenAI API key not configured")

        if not OPENAI_AVAILABLE or openai is None:
            raise ApiKeyError("OpenAI package not installed")

        start_time = time.time()
        image_base64 = base64.b64encode(image).decode()

        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, timeout=60.0)

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self._build_ocr_prompt()},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{detect_mime_type(image)};base64,{image_base64}"
                                },
                            },
                            {
                                "type": "text",
                                "text": "Extract all mathematical formulas from this image.",
                            },
                        ],
                    },
                ],
                max_tokens=1024,
            )
        except _AuthenticationError:
            raise ApiKeyError("Invalid OpenAI API key")
        except _RateLimitError:
            raise OcrRateLimitError("OpenAI rate limit exceeded", retry_after=60)
        except _APIConnectionError:
            raise NetworkError("Failed to connect to OpenAI API")

        if not response.choices:
            raise OcrError("OpenAI 返回空结果")
        raw_text = response.choices[0].message.content or ""
        latex = self._parse_response(raw_text)

        total_tokens = response.usage.total_tokens if response.usage else 765
        input_tokens = response.usage.prompt_tokens if response.usage else 500
        output_tokens = response.usage.completion_tokens if response.usage else 265

        cost_usd = (input_tokens * OPENAI_INPUT_COST) + (
            output_tokens * OPENAI_OUTPUT_COST
        )
        timing_ms = int((time.time() - start_time) * 1000)

        return OcrResult(
            latex=latex,
            confidence=None,  # LLM doesn't provide confidence
            backend="openai",
            timing_ms=timing_ms,
            cost_estimate=CostEstimate(
                tokens_used=total_tokens, estimated_cost_usd=cost_usd
            ),
        )

    def estimate_cost(self, image: bytes) -> CostEstimate | None:
        """Estimate cost based on gpt-4o rates."""
        tokens = self._estimate_tokens(image)
        cost_usd = tokens * OPENAI_INPUT_COST + 265 * OPENAI_OUTPUT_COST
        return CostEstimate(tokens_used=tokens, estimated_cost_usd=cost_usd)

    def validate_config(self) -> ValidationResult:
        """Check that API key is present and well-formed."""
        if not self._api_key:
            return ValidationResult(valid=False, message="OPENAI_API_KEY not set")

        if not self._api_key.startswith("sk-"):
            return ValidationResult(
                valid=False, message="OPENAI_API_KEY should start with 'sk-'"
            )

        return ValidationResult(valid=True, message="API key format valid")

    def get_rate_limit_status(self) -> RateLimitStatus | None:
        """OpenAI doesn't expose rate limit info via SDK."""
        return None

    async def aclose(self) -> None:
        """Close the async client and release resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
