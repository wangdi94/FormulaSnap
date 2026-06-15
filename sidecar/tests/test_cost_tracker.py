"""Tests for cost_tracker.py and key_manager.py.

Covers:
- Rate limiting (daily limit, minimum interval)
- Cost statistics tracking
- Key manager CRUD operations
"""

from unittest.mock import MagicMock, patch

import pytest

from sidecar.ocr_engines.cost_tracker import (
    CostTracker,
    RateLimitExceededError,
    StatsSnapshot,
)
from sidecar.ocr_engines.key_manager import (
    EncryptedFileBackend,
    FileBackend,
    KeyManager,
    _Fernet,
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

        with pytest.raises(RateLimitExceededError) as exc_info:
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

        with pytest.raises(RateLimitExceededError) as exc_info:
            tracker.check_rate_limit()

        assert "Daily limit" in str(exc_info.value)
        assert exc_info.value.retry_after is not None

    def test_daily_limit_resets_next_day(self):
        from datetime import datetime, timezone

        day1_start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        current_time = day1_start
        tracker = CostTracker(daily_limit=2, min_interval_secs=0.0, time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01
        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01

        with pytest.raises(RateLimitExceededError):
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

        with pytest.raises(RateLimitExceededError) as exc_info:
            tracker.check_rate_limit()

        assert exc_info.value.retry_after == pytest.approx(1.0)

    def test_custom_daily_limit(self):
        current_time = 1000.0
        tracker = CostTracker(daily_limit=3, min_interval_secs=0.0, time_fn=lambda: current_time)

        for i in range(3):
            tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
            current_time += 0.01

        with pytest.raises(RateLimitExceededError):
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
        """check_and_record raises RateLimitExceededError within min interval."""
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=2.0, time_fn=lambda: current_time)

        tracker.record_call("openai", tokens_used=100, cost_usd=0.001)
        current_time = 1001.0

        with pytest.raises(RateLimitExceededError) as exc_info:
            tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)

        assert exc_info.value.retry_after is not None
        assert exc_info.value.retry_after > 0
        assert tracker.get_stats().total_calls == 1

    def test_check_and_record_fails_at_daily_limit(self):
        """check_and_record raises RateLimitExceededError at daily limit."""
        current_time = 1000.0
        tracker = CostTracker(daily_limit=2, min_interval_secs=0.0, time_fn=lambda: current_time)

        tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01
        tracker.check_and_record("openai", tokens_used=100, cost_usd=0.001)
        current_time += 0.01

        with pytest.raises(RateLimitExceededError) as exc_info:
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
            except RateLimitExceededError:
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
        """Encrypted backend is preferred over env vars; plaintext is last resort."""
        master_key = _Fernet.generate_key()
        enc_dir = tmp_path / "enc"
        encrypted = EncryptedFileBackend(config_dir=enc_dir, master_key=master_key)
        encrypted.set_key("openai", "api_key", "sk-encrypted")

        plain_dir = tmp_path / "plain"
        file_backend = FileBackend(config_dir=plain_dir)
        file_backend.set_key("openai", "api_key", "sk-stored")

        mock_keyring = MagicMock()
        mock_keyring.get_key.return_value = None

        km = KeyManager(
            keyring_backend=mock_keyring,
            file_backend=file_backend,
            encrypted_backend=encrypted,
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"}):
            result = km.get_key("openai", "api_key")
            assert result == "sk-encrypted"

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

    def test_set_key_no_duplicate(self, tmp_path):
        """When keyring succeeds, file backend should NOT be written to."""
        file_backend = FileBackend(config_dir=tmp_path)
        mock_keyring = MagicMock()
        mock_keyring.set_key.return_value = None

        km = KeyManager(keyring_backend=mock_keyring, file_backend=file_backend)
        km.set_key("openai", "api_key", "sk-keyring-ok")

        mock_keyring.set_key.assert_called_once_with("openai", "api_key", "sk-keyring-ok")
        assert file_backend.get_key("openai", "api_key") is None

    def test_concurrent_set_key(self, tmp_path):
        """Concurrent set_key calls from multiple threads should not lose keys."""
        import threading

        file_backend = FileBackend(config_dir=tmp_path)
        mock_keyring = MagicMock()
        mock_keyring.set_key.side_effect = RuntimeError("no keyring")

        km = KeyManager(keyring_backend=mock_keyring, file_backend=file_backend)

        n_threads = 10
        barrier = threading.Barrier(n_threads)

        def worker(i):
            barrier.wait()
            km.set_key(f"service_{i}", "api_key", f"key_{i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(n_threads):
            assert file_backend.get_key(f"service_{i}", "api_key") == f"key_{i}"


# =========================================================================
# Batch Write Tests
# =========================================================================


class TestBatchWrite:
    """Tests for batched disk write optimization."""

    def test_defer_write_below_count_threshold(self):
        """_save_to_file is NOT called when pending count < 5."""
        tracker = CostTracker(time_fn=lambda: 1000.0)
        with patch.object(tracker, '_save_to_file') as mock_save:
            tracker.record_call("openai", 100, 0.001)
            tracker.record_call("openai", 100, 0.001)
            tracker.record_call("openai", 100, 0.001)
            assert mock_save.call_count == 0

    def test_flush_at_count_threshold(self):
        """_save_to_file is called once when 5 calls accumulated."""
        current_time = 1000.0
        tracker = CostTracker(time_fn=lambda: current_time)
        with patch.object(tracker, '_save_to_file') as mock_save:
            for i in range(5):
                tracker.record_call("openai", 100, 0.001)
                current_time += 3.0
            assert mock_save.call_count == 1

    def test_flush_at_time_threshold(self):
        """_save_to_file is called when 30s elapsed since last write."""
        current_time = 1000.0
        tracker = CostTracker(time_fn=lambda: current_time)
        with patch.object(tracker, '_save_to_file') as mock_save:
            tracker.record_call("openai", 100, 0.001)
            current_time = 1030.1
            tracker.record_call("openai", 100, 0.001)
            assert mock_save.call_count == 1

    def test_flush_method_forces_write(self):
        """flush() forces disk write regardless of thresholds."""
        tracker = CostTracker(time_fn=lambda: 1000.0)
        with patch.object(tracker, '_save_to_file') as mock_save:
            tracker.record_call("openai", 100, 0.001)
            assert mock_save.call_count == 0
            tracker.flush()
            assert mock_save.call_count == 1

    def test_memory_accuracy_regardless_of_write_timing(self):
        """Records accumulate correctly in memory without disk writes."""
        current_time = 1000.0
        tracker = CostTracker(time_fn=lambda: current_time)
        with patch.object(tracker, '_save_to_file'):
            for i in range(3):
                tracker.record_call("openai", 100, 0.001)
                current_time += 3.0
            stats = tracker.get_stats()
            assert stats.total_calls == 3
            assert stats.total_tokens == 300
            assert stats.estimated_cost_usd == pytest.approx(0.003)

    def test_batch_write_via_check_and_record(self):
        """Batch logic also applies to check_and_record()."""
        current_time = 1000.0
        tracker = CostTracker(daily_limit=100, min_interval_secs=0.0, time_fn=lambda: current_time)
        with patch.object(tracker, '_save_to_file') as mock_save:
            for i in range(4):
                tracker.check_and_record("openai", 100, 0.001)
                current_time += 0.01
            assert mock_save.call_count == 0
            tracker.check_and_record("openai", 100, 0.001)
            assert mock_save.call_count == 1

    def test_flush_noop_when_no_pending(self):
        """flush() is a no-op when nothing pending."""
        tracker = CostTracker(time_fn=lambda: 1000.0)
        with patch.object(tracker, '_save_to_file') as mock_save:
            tracker.flush()
            assert mock_save.call_count == 0

    def test_batch_resets_counter_after_flush(self):
        """After flush, pending count resets so next batch starts fresh."""
        current_time = 1000.0
        tracker = CostTracker(time_fn=lambda: current_time)
        with patch.object(tracker, '_save_to_file') as mock_save:
            for i in range(5):
                tracker.record_call("openai", 100, 0.001)
                current_time += 3.0
            assert mock_save.call_count == 1
            # After flush at 5, need 5 more to trigger next flush
            for i in range(4):
                tracker.record_call("openai", 100, 0.001)
                current_time += 3.0
            assert mock_save.call_count == 1  # still only 1
            tracker.record_call("openai", 100, 0.001)
            assert mock_save.call_count == 2  # now 2


# =========================================================================
# Daily Count Optimization Tests
# =========================================================================


class TestDailyCount:
    """Tests for incremental daily count cache."""

    def test_daily_count_increments_incrementally(self):
        """Each record_call increments today's count by 1."""
        from datetime import datetime, timezone

        day_start = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp()
        current_time = day_start
        tracker = CostTracker(time_fn=lambda: current_time)

        assert tracker.get_stats().calls_today == 0

        tracker.record_call("openai", 100, 0.001)
        current_time += 3.0
        assert tracker.get_stats().calls_today == 1

        tracker.record_call("mathpix", 200, 0.002)
        current_time += 3.0
        assert tracker.get_stats().calls_today == 2

        tracker.record_call("claude", 300, 0.003)
        assert tracker.get_stats().calls_today == 3

    def test_daily_count_resets_cross_midnight(self):
        """Count resets to 0 after UTC midnight, then increments from new day."""
        from datetime import datetime, timezone

        day1 = datetime(2024, 6, 15, 23, 59, 58, tzinfo=timezone.utc).timestamp()
        current_time = day1
        tracker = CostTracker(time_fn=lambda: current_time)

        tracker.record_call("openai", 100, 0.001)
        current_time += 1.0
        tracker.record_call("openai", 100, 0.001)

        assert tracker.get_stats().calls_today == 2

        day2 = datetime(2024, 6, 16, 0, 0, 1, tzinfo=timezone.utc).timestamp()
        current_time = day2

        assert tracker.get_stats().calls_today == 0

        tracker.record_call("openai", 100, 0.001)
        assert tracker.get_stats().calls_today == 1

    def test_daily_count_o1_after_record(self):
        """After record_call, get_stats().calls_today uses cached counter (O(1)).

        Verifies the counter stays correct without re-scanning all records.
        """
        from datetime import datetime, timezone

        day_start = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp()
        current_time = day_start
        tracker = CostTracker(time_fn=lambda: current_time)

        for i in range(50):
            tracker.record_call("openai", 100, 0.001)
            current_time += 3.0

        assert tracker.get_stats().calls_today == 50

        for i in range(50):
            tracker.record_call("mathpix", 200, 0.002)
            current_time += 3.0

        assert tracker.get_stats().calls_today == 100

    def test_daily_count_resets_on_clear(self):
        """reset() zeroes the daily count and refreshes the date stamp."""
        from datetime import datetime, timezone

        day_start = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp()
        current_time = day_start
        tracker = CostTracker(time_fn=lambda: current_time)

        tracker.record_call("openai", 100, 0.001)
        tracker.record_call("openai", 100, 0.001)
        assert tracker.get_stats().calls_today == 2

        tracker.reset()
        assert tracker.get_stats().calls_today == 0
