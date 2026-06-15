"""Circuit Breaker and Engine Manager for OCR engines.

Provides:
- Per-backend circuit breaker pattern (disable after failures, auto-recover).
- Cost-aware fallback chain with automatic engine routing.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence
from enum import Enum

from sidecar.ocr_engines.interface import OcrBackend, OcrError, OcrOptions, OcrResult

logger = logging.getLogger(__name__)


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

    def get_state(self) -> _CircuitState:
        """Current state, auto-transitioning OPEN → HALF_OPEN after timeout.

        Returns the current circuit breaker state. If the breaker is OPEN
        and the recovery timeout has elapsed, transitions to HALF_OPEN
        before returning.
        """
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
        state = self.get_state()  # triggers auto-transition
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
# Engine Manager — fallback chain with circuit breaker
# ---------------------------------------------------------------------------

# Default fallback priority: cheapest/most-reliable first.
_FALLBACK_CHAIN: tuple[str, ...] = (
    "gemini",
    "openai",
    "claude",
    "mathpix",
    "pix2text",
)


class EngineManager:
    """Cost-aware engine router with circuit breaker and fallback chain.

    Engines are tried in priority order (cheapest / most-preferred first).
    Each engine has its own circuit breaker: after 3 consecutive failures
    the engine is disabled for 60 s, then auto-recovers via HALF_OPEN.

    Args:
        engines: Sequence of ``(name, engine_instance)`` tuples.
            The order defines the fallback priority.  If not provided,
            engines must be registered via :meth:`register`.
    """

    def __init__(
        self,
        engines: Sequence[tuple[str, OcrBackend]] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._chain: list[tuple[str, OcrBackend, CircuitBreaker]] = []
        self._breakers: dict[str, CircuitBreaker] = {}

        if engines:
            for name, engine in engines:
                self.register(name, engine)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, engine: OcrBackend) -> None:
        """Add an engine to the fallback chain.

        Args:
            name: Engine identifier (e.g. ``"pix2text"``).
            engine: Engine instance implementing :class:`OcrBackend`.
        """
        with self._lock:
            if name in self._breakers:
                return
            breaker = CircuitBreaker()
            self._chain.append((name, engine, breaker))
            self._breakers[name] = breaker

    def get_breaker(self, name: str) -> CircuitBreaker | None:
        """Return the circuit breaker for *name*, or ``None`` if unregistered."""
        return self._breakers.get(name)

    @property
    def engine_names(self) -> list[str]:
        """Ordered list of registered engine names."""
        return [name for name, _, _ in self._chain]

    # ------------------------------------------------------------------
    # Recognition with fallback
    # ------------------------------------------------------------------

    async def recognize(
        self,
        image: bytes,
        options: OcrOptions | None = None,
    ) -> OcrResult:
        """Recognize *image* using the fallback chain.

        Engines are tried in priority order.  An engine is skipped when its
        circuit breaker is OPEN.  On failure the breaker is tripped and the
        next engine is tried.  Returns the first successful result.

        Raises:
            OcrError: When **all** engines in the chain fail.
        """
        if options is None:
            options = OcrOptions()

        with self._lock:
            chain = list(self._chain)

        if not chain:
            raise OcrError("No OCR engines registered")

        errors: list[str] = []

        for name, engine, breaker in chain:
            if not breaker.allow_request():
                logger.debug("Skipping %s — circuit OPEN", name)
                errors.append(f"{name}: circuit breaker open")
                continue

            try:
                result = await engine.recognize(image, options)
                breaker.record_success()
                logger.debug("Recognized via %s", name)
                return result
            except Exception as exc:
                breaker.record_failure()
                errors.append(f"{name}: {exc}")
                logger.warning("Engine %s failed: %s", name, exc)

        raise OcrError(
            "All OCR engines failed:\n" + "\n".join(errors)
        )
