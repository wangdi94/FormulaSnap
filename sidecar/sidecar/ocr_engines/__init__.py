"""OCR engine implementations."""

from sidecar.ocr_engines.cost_tracker import CostTracker, RateLimitExceededError, cost_tracker
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
from sidecar.ocr_engines.key_manager import KeyManager, key_manager
from sidecar.ocr_engines.manager import EngineManager
from sidecar.ocr_engines.mathpix_engine import MathpixEngine

__all__ = [
    "ApiKeyError",
    "CostEstimate",
    "CostTracker",
    "cost_tracker",
    "EngineManager",
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
    "RateLimitExceededError",
    "RateLimitStatus",
    "ValidationResult",
]
