"""OCR backend abstract interface definitions.

This module defines the Protocol and data classes for OCR backend implementations.
Uses Python Protocol for structural subtyping (duck typing).

Usage:
    from sidecar.ocr_engines.interface import (
        OcrBackend, OcrResult, CostEstimate, OcrOptions,
        RateLimitStatus, ValidationResult,
        OcrError, ApiKeyError, RateLimitError, NetworkError, ParseError
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class OcrOptions:
    """Options for OCR recognition.

    Attributes:
        preprocess: Whether to preprocess the image before recognition.
        max_dimension: Maximum image dimension (width or height) in pixels.
    """

    preprocess: bool = True
    max_dimension: int = 1024


@dataclass
class CostEstimate:
    """Cost estimate for an OCR operation.

    Attributes:
        tokens_used: Number of tokens consumed (for LLM-based backends).
        estimated_cost_usd: Estimated cost in US dollars.
    """

    tokens_used: int
    estimated_cost_usd: float


@dataclass
class OcrResult:
    """Result of an OCR recognition operation.

    Attributes:
        latex: Recognized LaTeX string.
        confidence: Confidence score between 0.0 and 1.0, or None if
            the backend does not provide confidence (e.g. LLM engines).
        backend: Name of the backend that produced this result.
        timing_ms: Time taken for recognition in milliseconds.
        cost_estimate: Optional cost estimate for this operation.
    """

    latex: str
    backend: str
    timing_ms: int
    confidence: float | None = None
    cost_estimate: CostEstimate | None = None


@dataclass
class RateLimitStatus:
    """Current rate limit status for a backend.

    Attributes:
        remaining: Number of requests remaining before rate limit.
        reset_at: Unix timestamp when the rate limit resets.
    """

    remaining: int
    reset_at: float  # Unix timestamp


@dataclass
class ValidationResult:
    """Result of a backend configuration validation.

    Attributes:
        valid: Whether the configuration is valid.
        message: Human-readable message describing the validation result.
    """

    valid: bool
    message: str


# ---------------------------------------------------------------------------
# Error Types
# ---------------------------------------------------------------------------


class OcrError(Exception):
    """Base exception for all OCR-related errors.

    All custom OCR exceptions inherit from this class,
    allowing callers to catch any OCR error with a single except clause.
    """

    pass


class ApiKeyError(OcrError):
    """Raised when the API key is missing, invalid, or expired."""

    pass


class RateLimitError(OcrError):
    """Raised when the API rate limit has been exceeded.

    Attributes:
        retry_after: Optional number of seconds to wait before retrying.
    """

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class NetworkError(OcrError):
    """Raised when a network error occurs during API communication."""

    pass


class ParseError(OcrError):
    """Raised when the API response cannot be parsed."""

    pass


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class OcrBackend(Protocol):
    """Protocol defining the interface for OCR backend implementations.

    Any class implementing these methods with compatible signatures
    will satisfy this protocol (structural subtyping).

    Example:
        class MyOcrBackend:
            async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
                ...

            def estimate_cost(self, image: bytes) -> Optional[CostEstimate]:
                ...

            def validate_config(self) -> ValidationResult:
                ...

            def get_rate_limit_status(self) -> Optional[RateLimitStatus]:
                ...
    """

    async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        """Recognize mathematical content in an image.

        Args:
            image: Raw image bytes (PNG, JPEG, etc.).
            options: Recognition options.

        Returns:
            OcrResult with recognized LaTeX and metadata.

        Raises:
            ApiKeyError: If authentication fails.
            RateLimitError: If rate limit is exceeded.
            NetworkError: If network communication fails.
            ParseError: If response parsing fails.
        """
        ...

    def estimate_cost(self, image: bytes) -> CostEstimate | None:
        """Estimate the cost of recognizing an image.

        Args:
            image: Raw image bytes.

        Returns:
            CostEstimate if the backend supports cost estimation, None otherwise.
        """
        ...

    def validate_config(self) -> ValidationResult:
        """Validate the backend configuration.

        Returns:
            ValidationResult indicating whether the config is valid.
        """
        ...

    def get_rate_limit_status(self) -> RateLimitStatus | None:
        """Get the current rate limit status.

        Returns:
            RateLimitStatus if available, None if the backend doesn't track limits.
        """
        ...
