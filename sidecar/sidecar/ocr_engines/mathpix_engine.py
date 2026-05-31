"""Mathpix OCR engine implementation.

Uses the Mathpix Convert API (https://api.mathpix.com/v3/text) for
mathematical expression recognition.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Optional

import httpx

from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrOptions,
    OcrResult,
    RateLimitError,
    RateLimitStatus,
    ValidationResult,
)

MATHPIX_API_URL = "https://api.mathpix.com/v3/text"
MATHPIX_COST_PER_REQUEST = 0.002  # USD


class MathpixEngine:
    """OCR backend powered by the Mathpix API.

    Credentials can be provided via constructor arguments or the
    ``MATHPIX_APP_ID`` / ``MATHPIX_APP_KEY`` environment variables.
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_key: Optional[str] = None,
    ) -> None:
        self._app_id = app_id or os.environ.get("MATHPIX_APP_ID", "")
        self._app_key = app_key or os.environ.get("MATHPIX_APP_KEY", "")

    # ------------------------------------------------------------------
    # OcrBackend protocol methods
    # ------------------------------------------------------------------

    async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        """Recognize mathematical content in an image via Mathpix API.

        Args:
            image: Raw image bytes (PNG, JPEG, etc.).
            options: Recognition options.

        Returns:
            OcrResult with recognized LaTeX and metadata.

        Raises:
            ApiKeyError: If authentication fails (401).
            RateLimitError: If rate limit is exceeded (429).
            NetworkError: If network communication fails.
        """
        if not self._app_id or not self._app_key:
            raise ApiKeyError("Mathpix API credentials not configured")

        start_time = time.time()

        headers = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "Content-Type": "application/json",
        }

        payload = {
            "src": "data:image/png;base64," + base64.b64encode(image).decode(),
            "formats": ["latex_simplified"],
            "data_options": {
                "include_asciimath": False,
                "include_latex": True,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    MATHPIX_API_URL, json=payload, headers=headers, timeout=30
                )
        except httpx.RequestError as exc:
            raise NetworkError(f"Network error: {exc}") from exc

        if response.status_code == 401:
            raise ApiKeyError("Invalid Mathpix API credentials")

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError(
                "Mathpix rate limit exceeded", retry_after=retry_after
            )

        if response.status_code >= 500:
            raise NetworkError(
                f"Mathpix server error: {response.status_code}"
            )

        response.raise_for_status()
        data = response.json()

        latex = data.get("latex_simplified", data.get("latex", ""))
        confidence = data.get("confidence", 0.0)
        timing_ms = int((time.time() - start_time) * 1000)

        return OcrResult(
            latex=latex,
            confidence=confidence,
            backend="mathpix",
            timing_ms=timing_ms,
            cost_estimate=CostEstimate(
                tokens_used=765,
                estimated_cost_usd=MATHPIX_COST_PER_REQUEST,
            ),
        )

    def estimate_cost(self, image: bytes) -> Optional[CostEstimate]:
        """Return a fixed-rate cost estimate for a Mathpix request."""
        return CostEstimate(
            tokens_used=765,
            estimated_cost_usd=MATHPIX_COST_PER_REQUEST,
        )

    def validate_config(self) -> ValidationResult:
        """Validate that API credentials are present and well-formed."""
        if not self._app_id or not self._app_key:
            return ValidationResult(
                valid=False,
                message="Mathpix API ID and key are required",
            )

        if len(self._app_id) < 10 or len(self._app_key) < 10:
            return ValidationResult(
                valid=False,
                message="API credentials appear too short",
            )

        return ValidationResult(valid=True, message="Credentials format valid")

    def get_rate_limit_status(self) -> Optional[RateLimitStatus]:
        """Return rate-limit information (Mathpix does not expose this in advance)."""
        return None
