"""OCR cost tracking and rate limiting.

Records every API call with backend name, token count, cost, and timestamp.
Enforces rate limits: max 100 calls per day, minimum 2-second interval between calls.

Usage:
    from sidecar.ocr_engines.cost_tracker import cost_tracker

    # Before making an API call, check rate limits
    cost_tracker.check_rate_limit()

    # After a successful call, record it
    cost_tracker.record_call(backend="openai", tokens_used=765, cost_usd=0.005)

    # Get current statistics
    stats = cost_tracker.get_stats()
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class CallRecord:
    """A single OCR API call record.

    Attributes:
        backend: Name of the OCR backend (e.g., "openai", "mathpix").
        tokens_used: Number of tokens consumed.
        cost_usd: Cost in US dollars.
        timestamp: Unix timestamp when the call was made.
    """

    backend: str
    tokens_used: int
    cost_usd: float
    timestamp: float


@dataclass
class StatsSnapshot:
    """Statistics snapshot returned by get_stats().

    Attributes:
        total_calls: Total number of recorded API calls.
        total_tokens: Total tokens consumed across all calls.
        estimated_cost_usd: Total estimated cost in US dollars.
        calls_today: Number of calls made today (UTC).
        daily_limit: Maximum calls allowed per day.
        remaining_today: Remaining calls allowed today.
    """

    total_calls: int
    total_tokens: int
    estimated_cost_usd: float
    calls_today: int
    daily_limit: int
    remaining_today: int


class RateLimitExceeded(Exception):
    """Raised when a rate limit would be exceeded.

    Attributes:
        message: Human-readable error message.
        retry_after: Seconds to wait before the next call is allowed.
    """

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class CostTracker:
    """Thread-safe OCR cost tracker with rate limiting.

    Rate limits enforced:
        - Maximum 100 calls per UTC day.
        - Minimum 2 seconds between consecutive calls.

    Usage:
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0)

        try:
            tracker.check_rate_limit()
        except RateLimitExceeded as e:
            logger.debug("Rate limited, retry after %ss", e.retry_after)
            return

        # ... make API call ...
        tracker.record_call("openai", tokens_used=765, cost_usd=0.005)
    """

    def __init__(
        self,
        daily_limit: int = 100,
        min_interval_secs: float = 2.0,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        """Initialize the cost tracker.

        Args:
            daily_limit: Maximum API calls allowed per UTC day.
            min_interval_secs: Minimum seconds between consecutive calls.
            time_fn: Optional time function override for testing.
                     Defaults to time.time().
        """
        self._daily_limit = daily_limit
        self._min_interval = min_interval_secs
        self._time = time_fn or time.time

        self._lock = threading.Lock()
        self._records: list[CallRecord] = []
        self._last_call_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------

    def check_rate_limit(self) -> None:
        """Check whether a new API call is allowed under rate limits.

        Raises:
            RateLimitExceeded: If the daily limit is reached or the
                minimum interval has not elapsed since the last call.
        """
        now = self._time()

        with self._lock:
            # Check minimum interval
            if self._last_call_time > 0:
                elapsed = now - self._last_call_time
                if elapsed < self._min_interval:
                    retry_after = self._min_interval - elapsed
                    logger.warning(
                        "Rate limit: minimum interval not elapsed (%.1fs < %.1fs)",
                        elapsed, self._min_interval,
                    )
                    raise RateLimitExceeded(
                        f"Minimum interval not elapsed. "
                        f"Retry after {retry_after:.1f}s",
                        retry_after=retry_after,
                    )

            # Check daily limit
            calls_today = self._count_calls_today(now)
            if calls_today >= self._daily_limit:
                seconds_until_midnight = self._seconds_until_utc_midnight(now)
                logger.warning(
                    "Rate limit: daily limit of %d calls reached",
                    self._daily_limit,
                )
                raise RateLimitExceeded(
                    f"Daily limit of {self._daily_limit} calls reached. "
                    f"Resets in {seconds_until_midnight:.0f}s",
                    retry_after=seconds_until_midnight,
                )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_call(
        self,
        backend: str,
        tokens_used: int,
        cost_usd: float,
    ) -> CallRecord:
        """Record a completed OCR API call.

        Args:
            backend: Name of the OCR backend.
            tokens_used: Number of tokens consumed.
            cost_usd: Cost in US dollars.

        Returns:
            The created CallRecord.
        """
        now = self._time()

        record = CallRecord(
            backend=backend,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            timestamp=now,
        )

        with self._lock:
            self._records.append(record)
            self._last_call_time = now

        logger.debug(
            "Recorded call: backend=%s tokens=%d cost=$%.6f",
            backend, tokens_used, cost_usd,
        )
        return record

    def check_and_record(
        self,
        backend: str,
        tokens_used: int,
        cost_usd: float,
    ) -> CallRecord:
        """Atomically check rate limits and record a call.

        Combines check_rate_limit() and record_call() into a single
        atomic operation under the lock, eliminating TOCTOU race conditions
        where concurrent requests could both pass the rate limit check
        before either records their call.

        Args:
            backend: Name of the OCR backend.
            tokens_used: Number of tokens consumed.
            cost_usd: Cost in US dollars.

        Returns:
            The created CallRecord.

        Raises:
            RateLimitExceeded: If rate limits would be exceeded.
        """
        now = self._time()

        with self._lock:
            # Check minimum interval
            if self._last_call_time > 0:
                elapsed = now - self._last_call_time
                if elapsed < self._min_interval:
                    retry_after = self._min_interval - elapsed
                    logger.warning(
                        "Rate limit: minimum interval not elapsed (%.1fs < %.1fs)",
                        elapsed, self._min_interval,
                    )
                    raise RateLimitExceeded(
                        f"Minimum interval not elapsed. "
                        f"Retry after {retry_after:.1f}s",
                        retry_after=retry_after,
                    )

            # Check daily limit
            calls_today = self._count_calls_today(now)
            if calls_today >= self._daily_limit:
                seconds_until_midnight = self._seconds_until_utc_midnight(now)
                logger.warning(
                    "Rate limit: daily limit of %d calls reached",
                    self._daily_limit,
                )
                raise RateLimitExceeded(
                    f"Daily limit of {self._daily_limit} calls reached. "
                    f"Resets in {seconds_until_midnight:.0f}s",
                    retry_after=seconds_until_midnight,
                )

            record = CallRecord(
                backend=backend,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                timestamp=now,
            )
            self._records.append(record)
            self._last_call_time = now

        logger.debug(
            "Recorded call: backend=%s tokens=%d cost=$%.6f",
            backend, tokens_used, cost_usd,
        )
        return record

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> StatsSnapshot:
        """Return current cost and rate limit statistics.

        Returns:
            StatsSnapshot with aggregate statistics.
        """
        now = self._time()

        with self._lock:
            total_calls = len(self._records)
            total_tokens = sum(r.tokens_used for r in self._records)
            total_cost = sum(r.cost_usd for r in self._records)
            calls_today = self._count_calls_today(now)

        remaining = max(0, self._daily_limit - calls_today)

        return StatsSnapshot(
            total_calls=total_calls,
            total_tokens=total_tokens,
            estimated_cost_usd=round(total_cost, 6),
            calls_today=calls_today,
            daily_limit=self._daily_limit,
            remaining_today=remaining,
        )

    def get_records(self) -> list[CallRecord]:
        """Return a copy of all call records.

        Returns:
            List of CallRecord instances.
        """
        with self._lock:
            return list(self._records)

    def reset(self) -> None:
        """Clear all records. Primarily for testing."""
        with self._lock:
            self._records.clear()
            self._last_call_time = 0.0

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _count_calls_today(self, now: float) -> int:
        """Count calls made in the current UTC day.

        Args:
            now: Current Unix timestamp.

        Returns:
            Number of calls made today (UTC).
        """
        today_start = self._utc_day_start(now)
        return sum(1 for r in self._records if r.timestamp >= today_start)

    @staticmethod
    def _utc_day_start(timestamp: float) -> float:
        """Get the Unix timestamp for the start of the UTC day.

        Args:
            timestamp: Unix timestamp.

        Returns:
            Unix timestamp for 00:00:00 UTC of the same day.
        """
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start.timestamp()

    @staticmethod
    def _seconds_until_utc_midnight(timestamp: float) -> float:
        """Calculate seconds until the next UTC midnight.

        Args:
            timestamp: Current Unix timestamp.

        Returns:
            Seconds until next UTC midnight.
        """
        from datetime import timedelta

        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        next_midnight = (dt + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (next_midnight - dt).total_seconds()


# Module-level singleton for global use
cost_tracker = CostTracker()
