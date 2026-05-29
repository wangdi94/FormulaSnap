"""Tests for OCR Engine Manager — routing, circuit breaker, and fallback."""

import pytest
import time
from unittest.mock import MagicMock

from sidecar.ocr_engines.manager import CircuitBreaker, EngineManager, _CircuitState
from sidecar.ocr_engines.interface import (
    OcrOptions,
    OcrResult,
    CostEstimate,
    OcrError,
    ApiKeyError,
    NetworkError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(backend: str, latex: str = "x^2", cost: float = 0.0) -> OcrResult:
    """Create a minimal OcrResult for testing."""
    return OcrResult(
        latex=latex,
        confidence=0.9,
        backend=backend,
        timing_ms=10,
        cost_estimate=CostEstimate(tokens_used=100, estimated_cost_usd=cost) if cost > 0 else None,
    )


def _make_engine(
    backend: str,
    cost: float = 0.0,
    fail: bool = False,
) -> MagicMock:
    """Create a mock engine with configurable behavior."""
    engine = MagicMock()
    engine.estimate_cost.return_value = (
        CostEstimate(tokens_used=100, estimated_cost_usd=cost) if cost > 0 else None
    )
    if fail:
        engine.recognize.side_effect = NetworkError(f"{backend} unavailable")
    else:
        engine.recognize.return_value = _make_result(backend, cost=cost)
    return engine


# ---------------------------------------------------------------------------
# CircuitBreaker Tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def setup_method(self):
        self.breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

    def test_initial_state_is_closed(self):
        assert self.breaker.state == _CircuitState.CLOSED
        assert self.breaker.allow_request() is True

    def test_single_failure_stays_closed(self):
        self.breaker.record_failure()
        assert self.breaker.state == _CircuitState.CLOSED
        assert self.breaker.allow_request() is True
        assert self.breaker.consecutive_failures == 1

    def test_two_failures_stays_closed(self):
        self.breaker.record_failure()
        self.breaker.record_failure()
        assert self.breaker.state == _CircuitState.CLOSED
        assert self.breaker.allow_request() is True

    def test_three_failures_opens_breaker(self):
        for _ in range(3):
            self.breaker.record_failure()
        assert self.breaker.state == _CircuitState.OPEN
        assert self.breaker.allow_request() is False

    def test_success_resets_failure_counter(self):
        self.breaker.record_failure()
        self.breaker.record_failure()
        self.breaker.record_success()
        assert self.breaker.consecutive_failures == 0
        assert self.breaker.state == _CircuitState.CLOSED

    def test_open_to_half_open_after_timeout(self):
        # Trip the breaker
        for _ in range(3):
            self.breaker.record_failure()
        assert self.breaker.state == _CircuitState.OPEN

        # Simulate time passing by manipulating internal state
        with self.breaker._lock:
            self.breaker._opened_at = time.time() - 61.0

        assert self.breaker.state == _CircuitState.HALF_OPEN
        assert self.breaker.allow_request() is True

    def test_half_open_success_closes(self):
        # Trip and fast-forward to half-open
        for _ in range(3):
            self.breaker.record_failure()
        with self.breaker._lock:
            self.breaker._opened_at = time.time() - 61.0

        assert self.breaker.state == _CircuitState.HALF_OPEN
        self.breaker.record_success()
        assert self.breaker.state == _CircuitState.CLOSED
        assert self.breaker.consecutive_failures == 0

    def test_half_open_failure_reopens(self):
        # Trip and fast-forward to half-open
        for _ in range(3):
            self.breaker.record_failure()
        with self.breaker._lock:
            self.breaker._opened_at = time.time() - 61.0

        assert self.breaker.state == _CircuitState.HALF_OPEN
        self.breaker.record_failure()
        assert self.breaker.state == _CircuitState.OPEN

    def test_manual_reset(self):
        for _ in range(3):
            self.breaker.record_failure()
        assert self.breaker.state == _CircuitState.OPEN

        self.breaker.reset()
        assert self.breaker.state == _CircuitState.CLOSED
        assert self.breaker.consecutive_failures == 0

    def test_custom_threshold(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        breaker.record_failure()
        assert breaker.state == _CircuitState.OPEN
        assert breaker.allow_request() is False


# ---------------------------------------------------------------------------
# EngineManager — explicit backend routing
# ---------------------------------------------------------------------------


class TestManagerExplicitRouting:
    def setup_method(self):
        self.pix2text = _make_engine("pix2text", cost=0.0)
        self.mathpix = _make_engine("mathpix", cost=0.002)
        self.openai = _make_engine("openai", cost=0.003)
        self.engines = {
            "pix2text": self.pix2text,
            "mathpix": self.mathpix,
            "openai": self.openai,
        }
        self.manager = EngineManager(engines=self.engines)

    def test_explicit_backend_calls_correct_engine(self):
        result = self.manager.recognize(b"img", backend="mathpix")
        assert result.backend == "mathpix"
        self.mathpix.recognize.assert_called_once()

    def test_explicit_backend_does_not_call_other_engines(self):
        self.manager.recognize(b"img", backend="pix2text")
        self.pix2text.recognize.assert_called_once()
        self.mathpix.recognize.assert_not_called()
        self.openai.recognize.assert_not_called()

    def test_unknown_backend_raises(self):
        with pytest.raises(OcrError, match="Unknown OCR backend"):
            self.manager.recognize(b"img", backend="nonexistent")

    def test_explicit_backend_respects_circuit_breaker(self):
        # Trip pix2text's breaker
        breaker = self.manager.get_breaker("pix2text")
        for _ in range(3):
            breaker.record_failure()

        with pytest.raises(OcrError, match="temporarily disabled"):
            self.manager.recognize(b"img", backend="pix2text")

    def test_options_passed_through(self):
        opts = OcrOptions(preprocess=False, max_dimension=512)
        self.manager.recognize(b"img", backend="pix2text", options=opts)
        self.pix2text.recognize.assert_called_once_with(b"img", opts)


# ---------------------------------------------------------------------------
# EngineManager — cost-aware auto routing
# ---------------------------------------------------------------------------


class TestManagerCostRouting:
    def test_auto_picks_cheapest_engine(self):
        """Auto mode should pick the engine with lowest estimated cost."""
        cheap = _make_engine("pix2text", cost=0.0)
        expensive = _make_engine("openai", cost=0.005)
        manager = EngineManager(engines={"pix2text": cheap, "openai": expensive})

        result = manager.recognize(b"img")
        assert result.backend == "pix2text"
        cheap.recognize.assert_called_once()
        expensive.recognize.assert_not_called()

    def test_auto_picks_cheapest_among_many(self):
        """Among multiple paid engines, auto picks the cheapest."""
        gemini = _make_engine("gemini", cost=0.001)
        openai = _make_engine("openai", cost=0.003)
        claude = _make_engine("claude", cost=0.005)
        pix2text = _make_engine("pix2text", cost=0.0)
        manager = EngineManager(engines={
            "gemini": gemini,
            "openai": openai,
            "claude": claude,
            "pix2text": pix2text,
        })

        result = manager.recognize(b"img")
        assert result.backend == "pix2text"

    def test_estimate_all_returns_all_costs(self):
        engines = {
            "pix2text": _make_engine("pix2text", cost=0.0),
            "mathpix": _make_engine("mathpix", cost=0.002),
            "openai": _make_engine("openai", cost=0.003),
        }
        manager = EngineManager(engines=engines)
        estimates = manager.estimate_all(b"img")

        assert "pix2text" in estimates
        assert "mathpix" in estimates
        assert "openai" in estimates
        # Pix2Text returns None (free)
        assert estimates["pix2text"] is None
        assert estimates["mathpix"] is not None
        assert estimates["mathpix"].estimated_cost_usd == 0.002

    def test_estimate_all_handles_engine_error(self):
        """If an engine's estimate_cost raises, return None for that engine."""
        broken = _make_engine("broken", cost=0.0)
        broken.estimate_cost.side_effect = Exception("boom")
        manager = EngineManager(engines={"broken": broken})
        estimates = manager.estimate_all(b"img")
        assert estimates["broken"] is None


# ---------------------------------------------------------------------------
# EngineManager — circuit breaker integration
# ---------------------------------------------------------------------------


class TestManagerCircuitBreaker:
    def test_consecutive_failures_trip_breaker(self):
        engine = _make_engine("openai", fail=True)
        manager = EngineManager(engines={"openai": engine, "pix2text": _make_engine("pix2text")})

        # First 2 failures: breaker stays closed
        for _ in range(2):
            with pytest.raises(NetworkError):
                manager.recognize(b"img", backend="openai")
        assert manager.get_breaker("openai").state == _CircuitState.CLOSED

        # 3rd failure: breaker opens
        with pytest.raises(NetworkError):
            manager.recognize(b"img", backend="openai")
        assert manager.get_breaker("openai").state == _CircuitState.OPEN

    def test_breaker_blocks_after_open(self):
        engine = _make_engine("openai", fail=True)
        manager = EngineManager(engines={"openai": engine})

        # Trip the breaker
        for _ in range(3):
            with pytest.raises(NetworkError):
                manager.recognize(b"img", backend="openai")

        # Now it should be blocked
        with pytest.raises(OcrError, match="temporarily disabled"):
            manager.recognize(b"img", backend="openai")

    def test_success_resets_breaker_counter(self):
        fail_engine = _make_engine("openai", fail=True)
        manager = EngineManager(engines={"openai": fail_engine})

        # 2 failures
        for _ in range(2):
            with pytest.raises(NetworkError):
                manager.recognize(b"img", backend="openai")
        assert manager.get_breaker("openai").consecutive_failures == 2

        # 1 success resets
        fail_engine.recognize.side_effect = None
        fail_engine.recognize.return_value = _make_result("openai")
        manager.recognize(b"img", backend="openai")
        assert manager.get_breaker("openai").consecutive_failures == 0

    def test_available_engines_excludes_open(self):
        broken = _make_engine("openai", fail=True)
        healthy = _make_engine("pix2text")
        manager = EngineManager(engines={"openai": broken, "pix2text": healthy})

        for _ in range(3):
            with pytest.raises(NetworkError):
                manager.recognize(b"img", backend="openai")

        available = manager.available_engines()
        assert "openai" not in available
        assert "pix2text" in available


# ---------------------------------------------------------------------------
# EngineManager — fallback chain
# ---------------------------------------------------------------------------


class TestManagerFallback:
    def test_fallback_when_primary_fails(self):
        """If the cheapest engine fails, auto falls through to the next."""
        failing = _make_engine("pix2text", cost=0.0, fail=True)
        fallback = _make_engine("mathpix", cost=0.002)
        manager = EngineManager(engines={"pix2text": failing, "mathpix": fallback})

        result = manager.recognize(b"img")
        assert result.backend == "mathpix"
        fallback.recognize.assert_called_once()

    def test_fallback_chain_llm_to_mathpix_to_pix2text(self):
        """Full fallback: LLM → Mathpix → Pix2Text."""
        gemini = _make_engine("gemini", cost=0.001, fail=True)
        openai = _make_engine("openai", cost=0.003, fail=True)
        claude = _make_engine("claude", cost=0.005, fail=True)
        mathpix = _make_engine("mathpix", cost=0.002, fail=True)
        pix2text = _make_engine("pix2text", cost=0.0)

        manager = EngineManager(engines={
            "gemini": gemini,
            "openai": openai,
            "claude": claude,
            "mathpix": mathpix,
            "pix2text": pix2text,
        })

        result = manager.recognize(b"img")
        # Should have fallen through to pix2text
        assert result.backend == "pix2text"
        pix2text.recognize.assert_called_once()

    def test_fallback_skips_circuit_broken_engines(self):
        """Circuit-broken engines are skipped in the fallback chain."""
        broken = _make_engine("pix2text", cost=0.0, fail=True)
        healthy = _make_engine("mathpix", cost=0.002)
        manager = EngineManager(engines={"pix2text": broken, "mathpix": healthy})

        # Trip pix2text's breaker
        for _ in range(3):
            with pytest.raises(NetworkError):
                manager.recognize(b"img", backend="pix2text")

        # Auto mode should skip broken pix2text and use mathpix
        result = manager.recognize(b"img")
        assert result.backend == "mathpix"

    def test_all_engines_fail_raises_last_error(self):
        """If every engine fails (including pix2text), raise the last error."""
        engines = {
            "pix2text": _make_engine("pix2text", cost=0.0, fail=True),
            "mathpix": _make_engine("mathpix", cost=0.002, fail=True),
        }
        manager = EngineManager(engines=engines)

        with pytest.raises(NetworkError):
            manager.recognize(b"img")

    def test_auto_mode_does_not_raise_for_normal_operation(self):
        """In normal operation, auto mode always returns a result."""
        engines = {
            "pix2text": _make_engine("pix2text", cost=0.0),
            "mathpix": _make_engine("mathpix", cost=0.002),
        }
        manager = EngineManager(engines=engines)
        result = manager.recognize(b"img")
        assert isinstance(result, OcrResult)

    def test_fallback_preserves_result_from_successful_engine(self):
        """The result comes from whichever engine actually succeeded."""
        failing = _make_engine("gemini", cost=0.001, fail=True)
        succeeding = _make_engine("openai", cost=0.003)
        manager = EngineManager(engines={"gemini": failing, "openai": succeeding})

        result = manager.recognize(b"img")
        assert result.backend == "openai"
        assert result.latex == "x^2"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestManagerEdgeCases:
    def test_single_engine_manager(self):
        """Manager with only one engine works fine."""
        engine = _make_engine("pix2text")
        manager = EngineManager(engines={"pix2text": engine})
        result = manager.recognize(b"img")
        assert result.backend == "pix2text"

    def test_default_options_used_when_none(self):
        """When options=None, default OcrOptions is used."""
        engine = _make_engine("pix2text")
        manager = EngineManager(engines={"pix2text": engine})
        manager.recognize(b"img")
        call_args = engine.recognize.call_args
        assert isinstance(call_args[0][1], OcrOptions)

    def test_breaker_state_thread_safety(self):
        """Circuit breaker state transitions are thread-safe."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        import threading

        errors = []

        def fail():
            try:
                for _ in range(100):
                    breaker.record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert breaker.state == _CircuitState.OPEN
