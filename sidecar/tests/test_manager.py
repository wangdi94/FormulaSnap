"""Tests for EngineManager fallback chain and CircuitBreaker integration."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from sidecar.ocr_engines.interface import OcrError, OcrOptions, OcrResult
from sidecar.ocr_engines.manager import EngineManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(backend: str = "test") -> OcrResult:
    return OcrResult(latex="x^2", backend=backend, timing_ms=50, confidence=0.9)


class _StubEngine:
    """Minimal engine stub for testing."""

    def __init__(
        self,
        result: OcrResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.call_count = 0

    async def recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        self.call_count += 1
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result

    def estimate_cost(self, image: bytes):
        return None

    def validate_config(self):
        from sidecar.ocr_engines.interface import ValidationResult
        return ValidationResult(valid=True, message="ok")

    def get_rate_limit_status(self):
        return None


# ---------------------------------------------------------------------------
# Tests — EngineManager
# ---------------------------------------------------------------------------


class TestEngineManagerFallback:
    def setup_method(self) -> None:
        self.opts = OcrOptions()
        self.image = b"\x89PNG"

    def test_primary_success_returns_primary_result(self) -> None:
        primary_result = _make_result("gemini")
        primary = _StubEngine(result=primary_result)
        secondary = _StubEngine(result=_make_result("openai"))

        mgr = EngineManager([("gemini", primary), ("openai", secondary)])
        result = asyncio.run(mgr.recognize(self.image, self.opts))

        assert result.backend == "gemini"
        assert result.latex == "x^2"
        assert primary.call_count == 1
        assert secondary.call_count == 0

    def test_primary_fails_falls_back_to_secondary(self) -> None:
        primary = _StubEngine(error=OcrError("engine down"))
        secondary_result = _make_result("openai")
        secondary = _StubEngine(result=secondary_result)

        mgr = EngineManager([("gemini", primary), ("openai", secondary)])
        result = asyncio.run(mgr.recognize(self.image, self.opts))

        assert result.backend == "openai"
        assert primary.call_count == 1
        assert secondary.call_count == 1

    def test_all_engines_fail_raises_error(self) -> None:
        primary = _StubEngine(error=OcrError("fail 1"))
        secondary = _StubEngine(error=OcrError("fail 2"))

        mgr = EngineManager([("gemini", primary), ("openai", secondary)])
        try:
            asyncio.run(mgr.recognize(self.image, self.opts))
            assert False, "Expected OcrError"
        except OcrError as e:
            assert "All OCR engines failed" in str(e)
            assert "gemini: fail 1" in str(e)
            assert "openai: fail 2" in str(e)


# ---------------------------------------------------------------------------
# Tests — Circuit Breaker integration
# ---------------------------------------------------------------------------


class TestEngineManagerCircuitBreaker:
    def setup_method(self) -> None:
        self.opts = OcrOptions()
        self.image = b"\x89PNG"

    def test_circuit_breaker_closed_initially(self) -> None:
        primary = _StubEngine(result=_make_result("gemini"))
        secondary = _StubEngine(result=_make_result("openai"))

        mgr = EngineManager([("gemini", primary), ("openai", secondary)])

        for name in ("gemini", "openai"):
            breaker = mgr.get_breaker(name)
            assert breaker is not None
            assert breaker.allow_request()
            assert breaker.consecutive_failures == 0

    def test_circuit_breaker_resets_on_success(self) -> None:
        failing_engine = _StubEngine(error=OcrError("boom"))
        working_engine = _StubEngine(result=_make_result("openai"))

        mgr = EngineManager([("gemini", failing_engine), ("openai", working_engine)])

        breaker = mgr.get_breaker("gemini")
        assert breaker is not None

        for _ in range(2):
            asyncio.run(mgr.recognize(self.image, self.opts))
        assert breaker.consecutive_failures == 2
        assert breaker.allow_request()

        mgr._chain[0] = ("gemini", _StubEngine(result=_make_result("gemini")), breaker)
        asyncio.run(mgr.recognize(self.image, self.opts))

        assert breaker.consecutive_failures == 0
        assert breaker.allow_request()

    def test_circuit_breaker_opens_after_3_failures(self) -> None:
        primary = _StubEngine(error=OcrError("boom"))
        secondary_result = _make_result("openai")
        secondary = _StubEngine(result=secondary_result)

        mgr = EngineManager([("gemini", primary), ("openai", secondary)])

        # Fail primary 3 times to trip the breaker
        for _ in range(3):
            result = asyncio.run(mgr.recognize(self.image, self.opts))
            assert result.backend == "openai"

        breaker = mgr.get_breaker("gemini")
        assert breaker is not None
        assert breaker.consecutive_failures >= 3
        assert not breaker.allow_request()

        # 4th call: primary should be skipped entirely (circuit OPEN)
        primary.call_count = 0
        secondary.call_count = 0
        result = asyncio.run(mgr.recognize(self.image, self.opts))
        assert result.backend == "openai"
        assert primary.call_count == 0  # skipped
        assert secondary.call_count == 1

    def test_circuit_breaker_recovers_after_timeout(self) -> None:
        t = 1000.0

        def fake_time() -> float:
            return t

        with patch("sidecar.ocr_engines.manager.time") as mock_time:
            mock_time.time.side_effect = fake_time

            primary_result = _make_result("gemini")
            primary = _StubEngine(result=primary_result)
            secondary = _StubEngine(result=_make_result("openai"))

            mgr = EngineManager([("gemini", primary), ("openai", secondary)])

            # Fail primary 3 times to open the breaker
            fail_engine = _StubEngine(error=OcrError("down"))
            mgr._chain[0] = ("gemini", fail_engine, mgr._chain[0][2])
            for _ in range(3):
                asyncio.run(mgr.recognize(self.image, self.opts))

            breaker = mgr.get_breaker("gemini")
            assert breaker is not None
            assert not breaker.allow_request()

            # Advance time past recovery timeout
            t = 1061.0

            # Replace failing engine with working one
            mgr._chain[0] = ("gemini", primary, breaker)
            assert breaker.allow_request()  # HALF_OPEN → allows probe

            result = asyncio.run(mgr.recognize(self.image, self.opts))
            assert result.backend == "gemini"
            assert breaker.allow_request()  # CLOSED after success

    def test_circuit_breaker_skips_open_engine(self) -> None:
        """When an engine's breaker is OPEN, it should be skipped without calling recognize()."""
        primary = _StubEngine(error=OcrError("down"))
        secondary = _StubEngine(result=_make_result("openai"))

        mgr = EngineManager([("gemini", primary), ("openai", secondary)])

        # Trip the breaker
        for _ in range(3):
            asyncio.run(mgr.recognize(self.image, self.opts))

        # Reset call counts
        primary.call_count = 0
        secondary.call_count = 0

        result = asyncio.run(mgr.recognize(self.image, self.opts))
        assert result.backend == "openai"
        assert primary.call_count == 0
        assert secondary.call_count == 1

    def test_register_and_engine_names(self) -> None:
        mgr = EngineManager()
        assert mgr.engine_names == []

        mgr.register("gemini", _StubEngine(result=_make_result("gemini")))
        mgr.register("pix2text", _StubEngine(result=_make_result("pix2text")))
        assert mgr.engine_names == ["gemini", "pix2text"]

        # Duplicate registration is a no-op
        mgr.register("gemini", _StubEngine(result=_make_result("other")))
        assert mgr.engine_names == ["gemini", "pix2text"]

    def test_no_engines_raises(self) -> None:
        mgr = EngineManager()
        try:
            asyncio.run(mgr.recognize(self.image, self.opts))
            assert False, "Expected OcrError"
        except OcrError as e:
            assert "No OCR engines registered" in str(e)
