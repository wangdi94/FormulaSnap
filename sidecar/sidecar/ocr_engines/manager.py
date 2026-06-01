"""Circuit Breaker for OCR engines.

Provides per-backend circuit breaker pattern:
- Disable engines after consecutive failures.
- Auto-recover after a configurable timeout.
"""

from __future__ import annotations

import time
import threading
from enum import Enum


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
