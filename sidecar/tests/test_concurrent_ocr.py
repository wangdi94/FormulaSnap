"""Tests for concurrent OCR request handling.

Verifies rate limiting, circuit breaker behavior, and cache correctness
under concurrent access patterns.
"""

from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from sidecar.api.server import _engines, app, register_engine
from sidecar.cache import ocr_cache
from sidecar.ocr_engines.cost_tracker import RateLimitExceededError, cost_tracker
from sidecar.ocr_engines.interface import OcrError, OcrOptions, OcrResult
from sidecar.ocr_engines.manager import CircuitBreaker, EngineManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_image_base64(data: bytes = b"test-image") -> str:
    """Encode raw bytes to base64 string for /api/ocr requests."""
    return base64.b64encode(data).decode()


def _make_result(
    latex: str = "x^2",
    backend: str = "pix2text",
    timing_ms: int = 100,
) -> OcrResult:
    return OcrResult(latex=latex, backend=backend, timing_ms=timing_ms, confidence=0.9)


def _make_engine_mock(
    latex: str = "x^2",
    backend: str = "pix2text",
    call_delay: float = 0.0,
) -> MagicMock:
    """Build a MagicMock engine whose recognize() returns a plausible result.

    Args:
        latex: LaTeX string in the mock result.
        backend: Backend name in the mock result.
        call_delay: Seconds to sleep inside recognize() to simulate latency.
    """
    result = MagicMock()
    result.latex = latex
    result.confidence = 0.95
    result.backend = backend
    result.timing_ms = 100
    result.cost_estimate = None

    async def _recognize(image: bytes, options: OcrOptions) -> MagicMock:
        if call_delay > 0:
            import time
            time.sleep(call_delay)
        return result

    engine = MagicMock()
    engine.recognize = AsyncMock(side_effect=_recognize)
    return engine


def _make_failing_engine_mock(error: Exception) -> MagicMock:
    """Build a MagicMock engine whose recognize() always raises."""
    engine = MagicMock()
    engine.recognize = AsyncMock(side_effect=error)
    return engine


# ---------------------------------------------------------------------------
# Tests — Concurrent OCR requests
# ---------------------------------------------------------------------------


class TestConcurrentOcrRequests:
    """Verify concurrent request handling through the /api/ocr endpoint."""

    def setup_method(self) -> None:
        _engines.clear()
        ocr_cache.clear()
        cost_tracker.reset()

    def test_concurrent_requests_processed(self) -> None:
        """Fire 3 concurrent requests with different images — all succeed."""
        engine = _make_engine_mock()
        register_engine("pix2text", engine)

        client = TestClient(app)
        payloads = [
            {"image_base64": _make_image_base64(f"image-{i}".encode()), "backend": "pix2text"}
            for i in range(3)
        ]

        with patch("sidecar.api.server.cost_tracker"):
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(client.post, "/api/ocr", json=p)
                    for p in payloads
                ]
                results = [f.result() for f in as_completed(futures)]

        assert all(r.status_code == 200 for r in results)
        assert all(r.json()["latex"] == "x^2" for r in results)
        assert engine.recognize.call_count == 3

    def test_rate_limit_rejects_rapid_calls(self) -> None:
        """Rapid calls trigger rate limit (via mocked cost_tracker).

        Note: cache is bypassed (ocr_cache.get patched to return None) so that
        repeated requests with the same image actually reach the rate limiter.
        """
        engine = _make_engine_mock()
        register_engine("pix2text", engine)

        client = TestClient(app)
        payload = {"image_base64": _make_image_base64(b"rate-limit-img"), "backend": "pix2text"}

        call_count = 0

        def _mock_check_limit() -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RateLimitExceededError(
                    "Minimum interval not elapsed. Retry after 2.0s",
                    retry_after=2.0,
                )

        with patch("sidecar.api.server.cost_tracker") as mock_ct, \
             patch("sidecar.api.server.ocr_cache") as mock_cache:
            mock_ct.check_limit_only = MagicMock(side_effect=_mock_check_limit)
            mock_ct.record_call = MagicMock()
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            results = [client.post("/api/ocr", json=payload) for _ in range(3)]

        statuses = sorted(r.status_code for r in results)
        assert statuses.count(200) == 1
        assert statuses.count(429) == 2
        rate_limited = [r for r in results if r.status_code == 429]
        for r in rate_limited:
            body = r.json()
            assert body["detail"]["error"] == "RATE_LIMIT_EXCEEDED"

    def test_circuit_breaker_under_concurrency(self) -> None:
        """Concurrent failures trigger circuit breaker (3 failures → OPEN)."""
        breaker = CircuitBreaker(failure_threshold=3)

        def _record_failure() -> None:
            breaker.record_failure()

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_record_failure) for _ in range(3)]
            for f in as_completed(futures):
                f.result()

        assert breaker.consecutive_failures >= 3
        assert not breaker.allow_request()

    def test_circuit_breaker_skips_open_engine_in_manager(self) -> None:
        """EngineManager skips engines whose breaker is OPEN after failures."""
        failing = _StubEngine(error=OcrError("boom"))
        working = _StubEngine(result=_make_result(backend="openai"))

        mgr = EngineManager([("gemini", failing), ("openai", working)])

        def _run_recognize() -> OcrResult:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(mgr.recognize(b"\x89PNG"))
            finally:
                loop.close()

        results = [_run_recognize() for _ in range(3)]

        assert all(r.backend == "openai" for r in results)
        breaker = mgr.get_breaker("gemini")
        assert breaker is not None
        assert breaker.consecutive_failures >= 3

    def test_cache_serves_concurrent_hits(self) -> None:
        """Same image from concurrent requests uses cache — engine called once."""
        engine = _make_engine_mock()
        register_engine("pix2text", engine)

        client = TestClient(app)
        payload = {"image_base64": _make_image_base64(b"same-image"), "backend": "pix2text"}

        with patch("sidecar.api.server.cost_tracker"):
            # Pre-warm the cache with a sequential request.
            warmup = client.post("/api/ocr", json=payload)
            assert warmup.status_code == 200

            # Concurrent requests should all hit cache.
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(client.post, "/api/ocr", json=payload)
                    for _ in range(3)
                ]
                results = [f.result() for f in as_completed(futures)]

        assert all(r.status_code == 200 for r in results)
        assert engine.recognize.call_count == 1


# ---------------------------------------------------------------------------
# Stub engine for EngineManager tests
# ---------------------------------------------------------------------------


class _StubEngine:
    """Minimal engine stub for testing EngineManager."""

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
