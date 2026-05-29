"""OCR engine implementations."""

from sidecar.ocr_engines.interface import (
    ApiKeyError,
    CostEstimate,
    NetworkError,
    OcrBackend,
    OcrError,
    OcrOptions,
    OcrResult,
    ParseError,
    RateLimitError,
    RateLimitStatus,
    ValidationResult,
)
from sidecar.ocr_engines.mathpix_engine import MathpixEngine
from sidecar.ocr_engines.cost_tracker import CostTracker, RateLimitExceeded, cost_tracker
from sidecar.ocr_engines.key_manager import KeyManager, key_manager

__all__ = [
    "ApiKeyError",
    "CostEstimate",
    "CostTracker",
    "cost_tracker",
    "KeyManager",
    "key_manager",
    "MathpixEngine",
    "NetworkError",
    "OcrBackend",
    "OcrError",
    "OcrOptions",
    "OcrResult",
    "ParseError",
    "RateLimitError",
    "RateLimitExceeded",
    "RateLimitStatus",
    "ValidationResult",
]
