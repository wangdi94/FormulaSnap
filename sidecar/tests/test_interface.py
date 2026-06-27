"""Contract tests for OCR backend interface definitions."""

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


class TestDataClasses:
    """Test data class creation and field access."""

    def test_ocr_result_creation(self):
        """OcrResult can be created with required fields."""
        result = OcrResult(
            latex="$x^2$",
            confidence=0.95,
            backend="pix2text",
            timing_ms=1200,
        )
        assert result.latex == "$x^2$"
        assert result.confidence == 0.95
        assert result.backend == "pix2text"
        assert result.timing_ms == 1200
        assert result.cost_estimate is None

    def test_ocr_result_with_cost(self):
        """OcrResult can include optional CostEstimate."""
        cost = CostEstimate(tokens_used=765, estimated_cost_usd=0.002)
        result = OcrResult(
            latex="$E=mc^2$",
            confidence=0.9,
            backend="mathpix",
            timing_ms=800,
            cost_estimate=cost,
        )
        assert result.cost_estimate is not None
        assert result.cost_estimate.tokens_used == 765
        assert result.cost_estimate.estimated_cost_usd == 0.002

    def test_cost_estimate_creation(self):
        """CostEstimate stores token and cost info."""
        cost = CostEstimate(tokens_used=100, estimated_cost_usd=0.001)
        assert cost.tokens_used == 100
        assert cost.estimated_cost_usd == 0.001

    def test_ocr_options_defaults(self):
        """OcrOptions has sensible defaults."""
        options = OcrOptions()
        assert options.preprocess is True
        assert options.max_dimension == 1024

    def test_ocr_options_custom(self):
        """OcrOptions accepts custom values."""
        options = OcrOptions(preprocess=False, max_dimension=2048)
        assert options.preprocess is False
        assert options.max_dimension == 2048

    def test_rate_limit_status(self):
        """RateLimitStatus stores remaining count and reset time."""
        status = RateLimitStatus(remaining=100, reset_at=1700000000.0)
        assert status.remaining == 100
        assert status.reset_at == 1700000000.0

    def test_validation_result_valid(self):
        """ValidationResult can represent valid state."""
        result = ValidationResult(valid=True, message="OK")
        assert result.valid is True
        assert result.message == "OK"

    def test_validation_result_invalid(self):
        """ValidationResult can represent invalid state."""
        result = ValidationResult(valid=False, message="Missing API key")
        assert result.valid is False
        assert result.message == "Missing API key"


class TestErrorHierarchy:
    """Test error class hierarchy and properties."""

    def test_ocr_error_hierarchy(self):
        """All OCR errors inherit from OcrError."""
        assert issubclass(ApiKeyError, OcrError)
        assert issubclass(RateLimitError, OcrError)
        assert issubclass(NetworkError, OcrError)
        assert issubclass(ParseError, OcrError)

    def test_ocr_error_is_exception(self):
        """OcrError inherits from Exception."""
        assert issubclass(OcrError, Exception)

    def test_api_key_error_message(self):
        """ApiKeyError carries error message."""
        error = ApiKeyError("Invalid API key")
        assert str(error) == "Invalid API key"
        assert isinstance(error, OcrError)

    def test_rate_limit_error_with_retry_after(self):
        """RateLimitError optionally carries retry_after seconds."""
        error = RateLimitError("Rate limited", retry_after=60)
        assert error.retry_after == 60
        assert str(error) == "Rate limited"

    def test_rate_limit_error_without_retry_after(self):
        """RateLimitError works without retry_after."""
        error = RateLimitError("Rate limited")
        assert error.retry_after is None

    def test_network_error_message(self):
        """NetworkError carries error message."""
        error = NetworkError("Connection refused")
        assert str(error) == "Connection refused"

    def test_parse_error_message(self):
        """ParseError carries error message."""
        error = ParseError("Invalid response format")
        assert str(error) == "Invalid response format"


class TestOcrBackendProtocol:
    """Test that OcrBackend Protocol defines the expected interface."""

    def test_protocol_has_recognize(self):
        """OcrBackend defines recognize method."""
        assert hasattr(OcrBackend, "recognize")

    def test_protocol_has_estimate_cost(self):
        """OcrBackend defines estimate_cost method."""
        assert hasattr(OcrBackend, "estimate_cost")

    def test_protocol_has_validate_config(self):
        """OcrBackend defines validate_config method."""
        assert hasattr(OcrBackend, "validate_config")

    def test_protocol_has_get_rate_limit_status(self):
        """OcrBackend defines get_rate_limit_status method."""
        assert hasattr(OcrBackend, "get_rate_limit_status")

    def test_protocol_is_subscriptable(self):
        """OcrBackend can be used as a type hint."""
        # Verify it's a proper Protocol class with expected members
        # get_protocol_members is Python 3.13+; use __protocol_attrs__ (3.11+) or inspect
        import sys
        from typing import get_type_hints

        if sys.version_info >= (3, 12):
            members = OcrBackend.__protocol_attrs__
            assert "recognize" in members
            assert "estimate_cost" in members
            assert "validate_config" in members
            assert "get_rate_limit_status" in members
        else:
            # Python 3.10 fallback: check annotations on the Protocol class
            get_type_hints(OcrBackend)
            for name in ("recognize", "estimate_cost", "validate_config", "get_rate_limit_status"):
                assert name in dir(OcrBackend), f"{name} not found in OcrBackend"
