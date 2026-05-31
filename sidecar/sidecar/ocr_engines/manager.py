"""OCR Engine Manager — cost-aware routing with circuit breaker and fallback.

Provides a unified entry point for all OCR backends with:
- Cost-aware routing: pick the cheapest available engine.
- Circuit breaker: disable engines after consecutive failures, auto-recover.
- Fallback chain: LLM → Mathpix → Pix2Text (never fails).
"""

from __future__ import annotations

import logging
import time
import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from sidecar.ocr_engines.interface import (
    CostEstimate,
    OcrError,
    OcrOptions,
    OcrResult,
)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class _CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Disabled after failures
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """Per-backend circuit breaker.

    After ``failure_threshold`` consecutive failures the backend is disabled
    for ``recovery_timeout`` seconds, then automatically re-enabled.

    Args:
        failure_threshold: Consecutive failures before opening (default 3).
        recovery_timeout: Seconds to wait before half-open (default 60).
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._consecutive_failures: int = 0
        self._state: _CircuitState = _CircuitState.CLOSED
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> _CircuitState:
        """Current state, auto-transitioning OPEN → HALF_OPEN after timeout."""
        with self._lock:
            if (
                self._state == _CircuitState.OPEN
                and (time.time() - self._opened_at) >= self._recovery_timeout
            ):
                self._state = _CircuitState.HALF_OPEN
            return self._state

    @property
    def consecutive_failures(self) -> int:
        """Number of consecutive failures (resets on success)."""
        with self._lock:
            return self._consecutive_failures

    def allow_request(self) -> bool:
        """Check whether a request is allowed through the breaker."""
        state = self.state  # triggers auto-transition
        if state == _CircuitState.CLOSED:
            return True
        if state == _CircuitState.HALF_OPEN:
            return True  # allow one probe request
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call — resets failure counter."""
        with self._lock:
            self._consecutive_failures = 0
            self._state = _CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call — may trip the breaker."""
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._state = _CircuitState.OPEN
                self._opened_at = time.time()

    def reset(self) -> None:
        """Manually reset the breaker to closed state."""
        with self._lock:
            self._consecutive_failures = 0
            self._state = _CircuitState.CLOSED
            self._opened_at = 0.0


# ---------------------------------------------------------------------------
# Engine Manager
# ---------------------------------------------------------------------------

# Fallback chain order: LLM engines → Mathpix → Pix2Text (ultimate fallback).
# LLM engines are ordered by estimated cost (cheapest first).
_FALLBACK_CHAIN: Tuple[str, ...] = ("gemini", "openai", "claude", "mathpix", "pix2text")


class EngineManager:
    """Unified manager for all OCR backends.

    Features:
    - ``recognize(image, backend="auto")`` — route to a specific or best engine.
    - ``estimate_all(image)`` — compare costs across all engines.
    - Circuit breaker per engine (3 failures → 60 s cooldown → auto-recover).
    - Fallback chain: LLM → Mathpix → Pix2Text (never raises for ``auto``).

    Args:
        engines: Mapping of backend name → engine instance.
        failure_threshold: Circuit breaker failure threshold (default 3).
        recovery_timeout: Circuit breaker recovery timeout in seconds (default 60).
    """

    def __init__(
        self,
        engines: Optional[Dict[str, Any]] = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ) -> None:
        if engines is not None:
            self._engines: Dict[str, Any] = dict(engines)
        else:
            self._engines = self._build_default_engines()

        self._breakers: Dict[str, CircuitBreaker] = {
            name: CircuitBreaker(failure_threshold, recovery_timeout)
            for name in self._engines
        }

    # ------------------------------------------------------------------
    # Default engine construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_default_engines() -> Dict[str, Any]:
        """Lazily import and instantiate all known engines."""
        from sidecar.ocr_engines.pix2text_engine import Pix2TextEngine
        from sidecar.ocr_engines.mathpix_engine import MathpixEngine
        from sidecar.ocr_engines.openai_engine import OpenAIEngine
        from sidecar.ocr_engines.claude_engine import ClaudeEngine
        from sidecar.ocr_engines.gemini_engine import GeminiEngine

        return {
            "pix2text": Pix2TextEngine(),
            "mathpix": MathpixEngine(),
            "openai": OpenAIEngine(),
            "claude": ClaudeEngine(),
            "gemini": GeminiEngine(),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recognize(
        self,
        image: bytes,
        backend: str = "auto",
        options: Optional[OcrOptions] = None,
    ) -> OcrResult:
        """Recognize mathematical content in *image*.

        Args:
            image: Raw image bytes.
            backend: Engine name (``"openai"``, ``"mathpix"``, …) or
                ``"auto"`` for cost-aware routing with fallback.
            options: Optional recognition options.

        Returns:
            OcrResult from the selected (or fallback) engine.

        Raises:
            OcrError: If *backend* is explicitly specified and fails, or
                if all engines in the fallback chain are exhausted (should
                not happen because Pix2Text is the ultimate fallback).
        """
        if options is None:
            options = OcrOptions()

        if backend != "auto":
            return self._call_engine(backend, image, options)

        # Auto mode: cost-aware routing + fallback chain
        return self._auto_recognize(image, options)

    def estimate_all(self, image: bytes) -> Dict[str, Optional[CostEstimate]]:
        """Estimate cost for every registered engine.

        Returns:
            Mapping of engine name → CostEstimate (``None`` for free engines
            like Pix2Text).
        """
        estimates: Dict[str, Optional[CostEstimate]] = {}
        for name, engine in self._engines.items():
            try:
                estimates[name] = engine.estimate_cost(image)
            except Exception:
                estimates[name] = None
        return estimates

    def get_breaker(self, name: str) -> CircuitBreaker:
        """Get the circuit breaker for a specific engine (for inspection)."""
        return self._breakers[name]

    def available_engines(self) -> List[str]:
        """List engines whose circuit breaker is not open."""
        return [n for n in self._engines if self._breakers[n].allow_request()]

    # ------------------------------------------------------------------
    # Internal routing
    # ------------------------------------------------------------------

    def _call_engine(
        self, name: str, image: bytes, options: OcrOptions
    ) -> OcrResult:
        """Call a specific engine, respecting its circuit breaker."""
        if name not in self._engines:
            raise OcrError(f"Unknown OCR backend: {name}")

        breaker = self._breakers[name]
        if not breaker.allow_request():
            logger.warning(
                "Backend '%s' is temporarily disabled (circuit open)", name
            )
            raise OcrError(
                f"Backend '{name}' is temporarily disabled (circuit open)"
            )

        logger.debug("Calling engine '%s'", name)
        try:
            result = self._engines[name].recognize(image, options)
            breaker.record_success()
            logger.debug("Engine '%s' succeeded", name)
            return result
        except Exception as exc:
            breaker.record_failure()
            logger.warning(
                "Engine '%s' failed: %s", name, exc
            )
            raise

    def _auto_recognize(self, image: bytes, options: OcrOptions) -> OcrResult:
        """Auto-route: pick cheapest available, fallback on failure.

        Strategy:
        1. Estimate costs for all engines.
        2. Sort by cost (cheapest first; Pix2Text/free = 0).
        3. Try each available engine in order.
        4. On failure, fall through to the next engine in the fallback chain.
        5. Pix2Text is the ultimate fallback (never fails).

        If ALL engines fail (extremely unlikely with Pix2Text), raises the
        last captured error.
        """
        ordered = self._route_order(image)
        logger.info("Auto routing order: %s", ordered)
        last_error: Optional[Exception] = None

        for name in ordered:
            breaker = self._breakers[name]
            if not breaker.allow_request():
                logger.debug("Skipping engine '%s' (circuit open)", name)
                continue

            try:
                result = self._engines[name].recognize(image, options)
                breaker.record_success()
                logger.info("Auto route succeeded with engine '%s'", name)
                return result
            except Exception as exc:
                breaker.record_failure()
                last_error = exc
                logger.warning(
                    "Auto route: engine '%s' failed, trying next: %s",
                    name, exc,
                )
                continue

        # If we get here, every engine was either circuit-broken or failed.
        # This should not happen because Pix2Text is always in the chain.
        if last_error is not None:
            raise last_error
        raise OcrError("All OCR engines are unavailable")

    def _route_order(self, image: bytes) -> List[str]:
        """Determine engine order by estimated cost (cheapest first).

        Engines with no cost estimate (free, like Pix2Text) are placed first.
        Engines that fail to estimate are placed last.
        The final order always follows the fallback chain as a tiebreaker.
        """
        estimates: List[Tuple[str, Optional[CostEstimate]]] = []
        for name in _FALLBACK_CHAIN:
            if name not in self._engines:
                continue
            try:
                est = self._engines[name].estimate_cost(image)
            except Exception:
                est = None
            estimates.append((name, est))

        # Sort: free (None) first, then by cost ascending, preserving
        # fallback chain order as tiebreaker.
        chain_rank = {n: i for i, n in enumerate(_FALLBACK_CHAIN)}

        def sort_key(item: Tuple[str, Optional[CostEstimate]]) -> Tuple:
            name, est = item
            cost = est.estimated_cost_usd if est is not None else 0.0
            return (cost, chain_rank.get(name, 999))

        estimates.sort(key=sort_key)
        return [name for name, _ in estimates]
