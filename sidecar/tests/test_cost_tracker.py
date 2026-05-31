"""Tests for cost_tracker.py and key_manager.py.

Covers:
- Rate limiting (daily limit, minimum interval)
- Cost statistics tracking
- Key manager CRUD operations
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from sidecar.ocr_engines.cost_tracker import (
    CostTracker,
    RateLimitExceeded,
    CallRecord,
    StatsSnapshot,
)
from sidecar.ocr_engines.key_manager import (
    KeyManager,
    FileBackend,
    _mask_key,
)


# =========================================================================
# CostTracker Tests
# =========================================================================


class TestCostTracker:
    """Tests for the CostTracker class."""

    def test_record_call_increments_stats(self):
        tracker = CostTracker(time_fn=lambda: 1000.0)
        tracker.record_call("openai", tokens_used=765, cost_usd=0.005)

        stats = tracker.get_stats()
        assert stats.total_calls == 1
        assert stats.total_tokens == 765
        assert stats.estimated_cost_usd == pytest.approx(0.005)

    def test_record_multiple_calls(self):
        current_time = 1000.0
        tracker = CostTracker(time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=765, cost_usd=0.005)
        current_time += 3.0
        tracker.record_call("mathpix", tokens_used=500, cost_usd=0.002)

        stats = tracker.get_stats()
        assert stats.total_calls == 2
        assert stats.total_tokens == 1265
        assert stats.estimated_cost_usd == pytest.approx(0.007)

    def test_get_stats_returns_correct_snapshot(self):
        tracker = CostTracker(time_fn=lambda: 1000.0)
        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)

        stats = tracker.get_stats()
        assert isinstance(stats, StatsSnapshot)
        assert stats.total_calls == 1
        assert stats.total_tokens == 100
        assert stats.estimated_cost_usd == pytest.approx(0.001)
        assert stats.daily_limit == 100
        assert stats.remaining_today == 99

    def test_reset_clears_all_records(self):
        tracker = CostTracker(time_fn=lambda: 1000.0)
        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        tracker.record_call("mathpix", tokens_used=200, cost_usd=0.002)

        tracker.reset()

        stats = tracker.get_stats()
        assert stats.total_calls == 0
        assert stats.total_tokens == 0
        assert stats.estimated_cost_usd == 0.0

    def test_get_records_returns_copy(self):
        tracker = CostTracker(time_fn=lambda: 1000.0)
        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)

        records = tracker.get_records()
        assert len(records) == 1
        assert records[0].backend == "openai"

        records.clear()
        assert len(tracker.get_records()) == 1


# =========================================================================
# Rate Limiting Tests
# =========================================================================


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_check_rate_limit_passes_within_limits(self):
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0, time_fn=lambda: 1000.0)
        tracker.check_rate_limit()

    def test_check_rate_limit_fails_within_min_interval(self):
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0, time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time = 1001.0

        with pytest.raises(RateLimitExceeded) as exc_info:
            tracker.check_rate_limit()

        assert exc_info.value.retry_after is not None
        assert exc_info.value.retry_after > 0

    def test_check_rate_limit_passes_after_min_interval(self):
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0, time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time = 1003.0

        tracker.check_rate_limit()

    def test_daily_limit_blocks_after_100_calls(self):
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=0.0, time_fn=lambda: current_time)

        for i in range(100):
            tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
            current_time += 0.01

        with pytest.raises(RateLimitExceeded) as exc_info:
            tracker.check_rate_limit()

        assert "Daily limit" in str(exc_info.value)
        assert exc_info.value.retry_after is not None

    def test_daily_limit_resets_next_day(self):
        from datetime import datetime, timezone, timedelta

        day1_start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        current_time = day1_start
        tracker = CostTracker(daily_limit=2, min_interval_secs=0.0, time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01
        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01

        with pytest.raises(RateLimitExceeded):
            tracker.check_rate_limit()

        day2_start = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        current_time = day2_start

        tracker.check_rate_limit()

    def test_remaining_today_decrements(self):
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=0.0, time_fn=lambda: current_time)

        assert tracker.get_stats().remaining_today == 100

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01

        assert tracker.get_stats().remaining_today == 99

    def test_rate_limit_exceeded_has_retry_after(self):
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0, time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time = 1001.0

        with pytest.raises(RateLimitExceeded) as exc_info:
            tracker.check_rate_limit()

        assert exc_info.value.retry_after == pytest.approx(1.0)

    def test_custom_daily_limit(self):
        current_time = 1000.0
        tracker = CostTracker(daily_limit=3, min_interval_secs=0.0, time_fn=lambda: current_time)

        for i in range(3):
            tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
            current_time += 0.01

        with pytest.raises(RateLimitExceeded):
            tracker.check_rate_limit()

        assert tracker.get_stats().remaining_today == 0


# =========================================================================
# Atomic check_and_record Tests
# =========================================================================


class TestCheckAndRecord:
    """Tests for the atomic check_and_record() method."""

    def test_check_and_record_success(self):
        """check_and_record atomically checks and records a call."""
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0, time_fn=lambda: 1000.0)

        record = tracker.check_and_record("openai", tokens_used=765, cost_usd=0.005)

        assert record.backend == "openai"
        assert record.tokens_used == 765
        assert record.cost_usd == 0.005
        assert tracker.get_stats().total_calls == 1

    def test_check_and_record_fails_within_min_interval(self):
        """check_and_record raises RateLimitExceeded within min interval."""
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0, time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time = 1001.0

        with pytest.raises(RateLimitExceeded) as exc_info:
            tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)

        assert exc_info.value.retry_after is not None
        assert exc_info.value.retry_after > 0
        assert tracker.get_stats().total_calls == 1

    def test_check_and_record_fails_at_daily_limit(self):
        """check_and_record raises RateLimitExceeded at daily limit."""
        current_time = 1000.0
        tracker = CostTracker(daily_limit=2, min_interval_secs=0.0, time_fn=lambda: current_time)

        tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01
        tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01

        with pytest.raises(RateLimitExceeded) as exc_info:
            tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)

        assert "Daily limit" in str(exc_info.value)
        assert tracker.get_stats().total_calls == 2

    def test_check_and_record_atomic_under_contention(self):
        """check_and_record is atomic even under thread contention."""
        import threading

        current_time = 1000.0
        time_lock = threading.Lock()

        def time_fn():
            with time_lock:
                return current_time

        tracker = CostTracker(daily_limit=5, min_interval_secs=0.0, time_fn=time_fn)

        results = {"success": 0, "limited": 0}
        barrier = threading.Barrier(10)

        def worker():
            nonlocal current_time
            barrier.wait()
            try:
                tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)
                results["success"] += 1
            except RateLimitExceeded:
                results["limited"] += 1

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results["success"] == 5
        assert results["limited"] == 5
        assert tracker.get_stats().total_calls == 5


# =========================================================================
# KeyManager Tests
# =========================================================================


class TestKeyManager:
    """Tests for the KeyManager class."""

    def test_mask_key_short_key(self):
        assert _mask_key("abc") == "****"

    def test_mask_key_normal_key(self):
        masked = _mask_key("sk-abc123xyz9")
        assert masked == "sk-a****xyz9"

    def test_mask_key_empty(self):
        assert _mask_key("") == "****"

    def test_file_backend_set_and_get(self, tmp_path):
        backend = FileBackend(config_dir=tmp_path)
        backend.set_key("openai", "api_key", "sk-test123")

        result = backend.get_key("openai", "api_key")
        assert result == "sk-test123"

    def test_file_backend_get_nonexistent(self, tmp_path):
        backend = FileBackend(config_dir=tmp_path)
        assert backend.get_key("openai", "api_key") is None

    def test_file_backend_delete(self, tmp_path):
        backend = FileBackend(config_dir=tmp_path)
        backend.set_key("openai", "api_key", "sk-test123")

        deleted = backend.delete_key("openai", "api_key")
        assert deleted is True
        assert backend.get_key("openai", "api_key") is None

    def test_file_backend_delete_nonexistent(self, tmp_path):
        backend = FileBackend(config_dir=tmp_path)
        assert backend.delete_key("openai", "api_key") is False

    def test_file_backend_multiple_services(self, tmp_path):
        backend = FileBackend(config_dir=tmp_path)
        backend.set_key("openai", "api_key", "sk-openai")
        backend.set_key("mathpix", "app_id", "mathpix-id")

        assert backend.get_key("openai", "api_key") == "sk-openai"
        assert backend.get_key("mathpix", "app_id") == "mathpix-id"

    def test_key_manager_uses_env_var(self, tmp_path):
        file_backend = FileBackend(config_dir=tmp_path)
        km = KeyManager(file_backend=file_backend)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"}):
            result = km.get_key("openai", "api_key")
            assert result == "sk-env-key"

    def test_key_manager_prefers_stored_over_env(self, tmp_path):
        file_backend = FileBackend(config_dir=tmp_path)
        file_backend.set_key("openai", "api_key", "sk-stored")

        km = KeyManager(file_backend=file_backend)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"}):
            result = km.get_key("openai", "api_key")
            assert result == "sk-stored"

    def test_key_manager_set_key_stores_in_file(self, tmp_path):
        file_backend = FileBackend(config_dir=tmp_path)
        mock_keyring = MagicMock()
        mock_keyring.get_key.return_value = None
        mock_keyring.set_key.side_effect = RuntimeError("not available")

        km = KeyManager(keyring_backend=mock_keyring, file_backend=file_backend)
        km.set_key("openai", "api_key", "sk-new-key")

        assert file_backend.get_key("openai", "api_key") == "sk-new-key"

    def test_key_manager_delete_removes_from_file(self, tmp_path):
        file_backend = FileBackend(config_dir=tmp_path)
        file_backend.set_key("openai", "api_key", "sk-to-delete")

        mock_keyring = MagicMock()
        mock_keyring.delete_key.return_value = False

        km = KeyManager(keyring_backend=mock_keyring, file_backend=file_backend)
        deleted = km.delete_key("openai", "api_key")

        assert deleted is True
        assert file_backend.get_key("openai", "api_key") is None

    def test_key_manager_list_services(self, tmp_path):
        file_backend = FileBackend(config_dir=tmp_path)
        file_backend.set_key("openai", "api_key", "sk-1")
        file_backend.set_key("mathpix", "app_id", "id-2")

        km = KeyManager(file_backend=file_backend)
        services = km.list_services()

        assert set(services) == {"openai", "mathpix"}
