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

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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


class RateLimitExceededError(Exception):
    """Raised when a rate limit would be exceeded.

    Attributes:
        message: Human-readable error message.
        retry_after: Seconds to wait before the next call is allowed.
    """

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class CostTracker:
    """Thread-safe OCR cost tracker with rate limiting.

    Rate limits enforced:
        - Maximum 100 calls per UTC day.
        - Minimum 2 seconds between consecutive calls.

    NOTE: Call records are persisted to ``~/.formulasnap/cost_stats.json``
    for survival across process restarts. Records older than 24 hours are
    pruned on load.

    Usage:
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0)

        try:
            tracker.check_rate_limit()
        except RateLimitExceededError as e:
            logger.debug("Rate limited, retry after %ss", e.retry_after)
            return

        # ... make API call ...
        tracker.record_call("openai", tokens_used=765, cost_usd=0.005)
    """

    def __init__(
        self,
        daily_limit: int = 100,
        min_interval_secs: float = 2.0,
        time_fn: Callable[[], float] | None = None,
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

        # Batch write state: defer disk I/O until threshold is met.
        self._BATCH_COUNT = 5
        self._BATCH_INTERVAL = 30.0
        self._pending_count: int = 0
        self._last_write_time: float = self._time()

        # Persistence: load saved records from disk (if any).
        # Only enabled when using real time (time_fn is None) — test
        # callers that pass a custom time_fn skip file I/O.
        if time_fn is None:
            self._data_file: Path | None = (
                Path.home() / ".formulasnap" / "cost_stats.json"
            )
            self._load_from_file()
        else:
            self._data_file = None

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------

    def check_rate_limit(self) -> None:
        """Check whether a new API call is allowed under rate limits.

        Raises:
            RateLimitExceededError: If the daily limit is reached or the
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
                    raise RateLimitExceededError(
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
                raise RateLimitExceededError(
                    f"Daily limit of {self._daily_limit} calls reached. "
                    f"Resets in {seconds_until_midnight:.0f}s",
                    retry_after=seconds_until_midnight,
                )

    def check_limit_only(self) -> None:
        """Check whether a new API call is allowed without recording it.

        Use this for pre-call validation: call before the API request,
        then call record_call() after a successful response.

        Raises:
            RateLimitExceededError: If the daily limit is reached or the
                minimum interval has not elapsed since the last call.
        """
        self.check_rate_limit()

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
            self._maybe_save(now)

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
            RateLimitExceededError: If rate limits would be exceeded.
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
                    raise RateLimitExceededError(
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
                raise RateLimitExceededError(
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
            self._maybe_save(now)

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

    _EVICTION_SECS = 24 * 60 * 60  # 24 hours

    def _evict_old_records(self, now: float) -> None:
        """Remove records older than 24 hours.

        Called internally while the lock is held. Since records are appended
        in chronological order, we can drop a prefix slice efficiently.

        Args:
            now: Current Unix timestamp.
        """
        cutoff = now - self._EVICTION_SECS
        # Records are append-sorted by timestamp — find the first to keep
        first_keep = 0
        for i, r in enumerate(self._records):
            if r.timestamp >= cutoff:
                first_keep = i
                break
        else:
            # All records are older than cutoff — clear entirely
            self._records.clear()
            return

        if first_keep > 0:
            del self._records[:first_keep]

    def _count_calls_today(self, now: float) -> int:
        """Count calls made in the current UTC day.

        Args:
            now: Current Unix timestamp.

        Returns:
            Number of calls made today (UTC).
        """
        self._evict_old_records(now)
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

    # ------------------------------------------------------------------
    # Batch Write
    # ------------------------------------------------------------------

    def _maybe_save(self, now: float) -> None:
        """Conditionally persist records based on batch thresholds.

        Writes to disk only when pending count >= _BATCH_COUNT OR
        elapsed time since last write >= _BATCH_INTERVAL. Called
        internally while the lock is held.
        """
        self._pending_count += 1
        elapsed = now - self._last_write_time
        if self._pending_count >= self._BATCH_COUNT or elapsed >= self._BATCH_INTERVAL:
            self._save_to_file()
            self._pending_count = 0
            self._last_write_time = now

    def flush(self) -> None:
        """Force-write any pending records to disk.

        Call this on application shutdown to avoid data loss.
        """
        with self._lock:
            if self._pending_count > 0:
                self._save_to_file()
                self._pending_count = 0
                self._last_write_time = self._time()

    # ------------------------------------------------------------------
    # JSON Persistence
    # ------------------------------------------------------------------

    def _load_from_file(self) -> None:
        """Load persistent records from the JSON data file (if it exists).

        Filters out records older than 24 hours relative to
        ``self._time()`` so that stale data is not retained across restarts.
        Errors are logged and silently swallowed to avoid crashing on
        corrupt files or permissions.
        """
        data_file = self._data_file
        if data_file is None or not data_file.exists():
            return

        try:
            with open(data_file) as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.warning("Cost stats file has invalid format (not a list)")
                return

            cutoff = self._time() - self._EVICTION_SECS
            loaded = 0
            for item in data:
                ts = item.get("timestamp", 0)
                if ts >= cutoff:
                    self._records.append(CallRecord(
                        backend=item["backend"],
                        tokens_used=item["tokens_used"],
                        cost_usd=item["cost_usd"],
                        timestamp=ts,
                    ))
                    loaded += 1

            logger.info("Loaded %d cost records from %s", loaded, self._data_file)
        except Exception:
            logger.warning(
                "Failed to load cost stats from %s", self._data_file, exc_info=True,
            )

    def _save_to_file(self) -> None:
        """Persist all current records to the JSON data file.

        Creates the parent directory if needed. Errors are logged and
        silently swallowed so that a write failure never breaks the caller.
        """
        data_file = self._data_file
        if data_file is None:
            return

        if not self._records:
            # Nothing to persist — remove the file if it exists to keep
            # the filesystem clean.
            try:
                if data_file.exists():
                    data_file.unlink()
            except Exception:
                logger.warning(
                    "Failed to remove empty cost stats file", exc_info=True,
                )
            return

        try:
            data_file.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "backend": r.backend,
                    "tokens_used": r.tokens_used,
                    "cost_usd": r.cost_usd,
                    "timestamp": r.timestamp,
                }
                for r in self._records
            ]
            with open(data_file, "w") as f:
                json.dump(data, f)
        except Exception:
            logger.warning(
                "Failed to save cost stats to %s", self._data_file, exc_info=True,
            )


# Module-level singleton for global use
cost_tracker = CostTracker()
