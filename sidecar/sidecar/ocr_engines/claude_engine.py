"""Claude Vision OCR engine.

Uses Anthropic Claude Sonnet to extract LaTeX from images.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Optional

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
    _AuthenticationError = anthropic.AuthenticationError
    _RateLimitError = anthropic.RateLimitError
    _APIConnectionError = anthropic.APIConnectionError
except ImportError:
    anthropic = None  # type: ignore[assignment]
    ANTHROPIC_AVAILABLE = False
    _AuthenticationError = Exception
    _RateLimitError = Exception
    _APIConnectionError = Exception

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

# Claude Sonnet pricing (per million tokens)
CLAUDE_INPUT_COST = 3.0 / 1_000_000
CLAUDE_OUTPUT_COST = 15.0 / 1_000_000


class ClaudeEngine(LlmProvider):
    """Anthropic Claude Sonnet Vision OCR backend."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        """Recognize math in image via Claude Sonnet Vision."""
        if not self._api_key:
            raise ApiKeyError("Anthropic API key not configured")

        if not ANTHROPIC_AVAILABLE or anthropic is None:
            raise ApiKeyError("Anthropic package not installed")

        start_time = time.time()
        image_base64 = base64.b64encode(image).decode()

        client = anthropic.Anthropic(api_key=self._api_key)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self._build_ocr_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": "Extract all mathematical formulas from this image.",
                            },
                        ],
                    }
                ],
            )
        except _AuthenticationError:
            raise ApiKeyError("Invalid Anthropic API key")
        except _RateLimitError:
            raise OcrRateLimitError("Claude rate limit exceeded", retry_after=60)
        except _APIConnectionError:
            raise NetworkError("Failed to connect to Claude API")

        text_block = response.content[0]
        raw_text = getattr(text_block, "text", "") or ""
        latex = self._parse_response(raw_text)

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens

        cost_usd = (input_tokens * CLAUDE_INPUT_COST) + (
            output_tokens * CLAUDE_OUTPUT_COST
        )
        timing_ms = int((time.time() - start_time) * 1000)

        return OcrResult(
            latex=latex,
            confidence=None,  # LLM doesn't provide confidence
            backend="claude",
            timing_ms=timing_ms,
            cost_estimate=CostEstimate(
                tokens_used=total_tokens, estimated_cost_usd=cost_usd
            ),
        )

    def estimate_cost(self, image: bytes) -> Optional[CostEstimate]:
        """Estimate cost based on Claude Sonnet rates."""
        input_tokens = self._estimate_tokens(image)
        output_tokens = 265  # estimated output
        cost_usd = input_tokens * CLAUDE_INPUT_COST + output_tokens * CLAUDE_OUTPUT_COST
        return CostEstimate(
            tokens_used=input_tokens + output_tokens, estimated_cost_usd=cost_usd
        )

    def validate_config(self) -> ValidationResult:
        """Check that API key is present."""
        if not self._api_key:
            return ValidationResult(valid=False, message="ANTHROPIC_API_KEY not set")

        return ValidationResult(valid=True, message="API key format valid")

    def get_rate_limit_status(self) -> Optional[RateLimitStatus]:
        """Anthropic doesn't expose rate limit info via SDK."""
        return None
