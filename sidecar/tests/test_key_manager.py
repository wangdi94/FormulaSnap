"""Tests for key_manager.py — Fernet alias, restore_master_key, and cache.

Covers:
- _Fernet import alias availability
- restore_master_key error handling (NameError regression)
- generate_key() static method
- KeyManager in-memory TTL cache (hit, expiry, invalidation)
"""

import time
from unittest.mock import MagicMock

import pytest

from sidecar.ocr_engines.key_manager import (
    EncryptedFileBackend,
    KeyBackend,
    KeyManager,
    _Fernet,
)


class TestFernetAlias:
    """Verify the _Fernet import alias works correctly."""

    def test_fernet_import(self):
        """_Fernet should be importable as an alias for Fernet."""
        assert _Fernet is not None
        # Verify it's the real Fernet class by calling generate_key
        key = _Fernet.generate_key()
        assert isinstance(key, bytes)
        assert len(key) > 0
        # Verify we can instantiate Fernet with the generated key
        f = _Fernet(key)
        assert f is not None


class TestEncryptedFileBackend:
    """Tests for EncryptedFileBackend covering Fernet usage."""

    def test_generate_key_static(self):
        """generate_key() should return a valid Fernet key."""
        key = EncryptedFileBackend.generate_key()
        assert isinstance(key, bytes)
        # Valid Fernet keys are 44-character url-safe base64
        assert len(key) == 44

    def test_restore_master_key_invalid_backup_raises_valueerror(self, tmp_path):
        """restore_master_key should raise ValueError (not NameError)
        when the backup file contains an invalid Fernet key."""
        # Create a backend with a valid master key
        master_key = _Fernet.generate_key()
        backend = EncryptedFileBackend(
            config_dir=tmp_path,
            master_key=master_key,
        )

        # Create a backup file with invalid Fernet key data
        backup_path = tmp_path / "master.key.bak"
        backup_path.write_bytes(b"not-a-valid-fernet-key")

        # Should raise ValueError, not NameError
        with pytest.raises(ValueError, match="Invalid Fernet key"):
            backend.restore_master_key(backup_path)

    def test_restore_master_key_missing_file_raises_filenotfound(self, tmp_path):
        """restore_master_key should raise FileNotFoundError when
        the backup file doesn't exist."""
        master_key = _Fernet.generate_key()
        backend = EncryptedFileBackend(
            config_dir=tmp_path,
            master_key=master_key,
        )

        backup_path = tmp_path / "nonexistent.bak"

        with pytest.raises(FileNotFoundError, match="Backup file not found"):
            backend.restore_master_key(backup_path)

    def test_restore_master_key_valid_backup(self, tmp_path):
        """restore_master_key should succeed with a valid backup."""
        master_key = _Fernet.generate_key()
        backend = EncryptedFileBackend(
            config_dir=tmp_path,
            master_key=master_key,
        )

        # Create a valid backup
        backup_path = tmp_path / "master.key.bak"
        new_key = _Fernet.generate_key()
        backup_path.write_bytes(new_key)

        # Should not raise
        backend.restore_master_key(backup_path)

        # Verify the master key was updated
        assert backend._master_key == new_key

        # Verify the stored key is the new key
        stored = (tmp_path / "master.key").read_bytes().strip()
        assert stored == new_key


class _CountingBackend(KeyBackend):
    """Mock backend that tracks how many times get_key is called."""

    def __init__(self, return_value: str = "test-key-123") -> None:
        self._value = return_value
        self.get_key_calls = 0

    def get_key(self, service: str, key_name: str) -> str | None:
        self.get_key_calls += 1
        return self._value

    def set_key(self, service: str, key_name: str, key_value: str) -> None:
        self._value = key_value

    def delete_key(self, service: str, key_name: str) -> bool:
        had = self._value is not None
        self._value = None
        return had


def _make_file_backend() -> MagicMock:
    fb = MagicMock()
    fb.get_key.return_value = None
    fb.delete_key.return_value = False
    fb._load_keys.return_value = {}
    return fb


class TestKeyManagerCache:

    def setup_method(self):
        self.backend = _CountingBackend("cached-val")
        self.file = _make_file_backend()
        self.km = KeyManager(
            keyring_backend=self.backend,
            file_backend=self.file,
            cache_ttl=60,
        )

    def test_cache_hit_skips_backend(self):
        first = self.km.get_key("openai", "api_key")
        second = self.km.get_key("openai", "api_key")

        assert first == "cached-val"
        assert second == "cached-val"
        assert self.backend.get_key_calls == 1

    def test_cache_different_keys_independent(self):
        self.km.get_key("openai", "api_key")
        assert self.backend.get_key_calls == 1

        self.backend._value = "mathpix-val"
        self.km.get_key("mathpix", "api_key")
        assert self.backend.get_key_calls == 2

        self.km.get_key("openai", "api_key")
        self.km.get_key("mathpix", "api_key")
        assert self.backend.get_key_calls == 2

    def test_cache_expired_calls_backend_again(self):
        km = KeyManager(
            keyring_backend=self.backend,
            file_backend=self.file,
            cache_ttl=0.1,
        )

        km.get_key("openai", "api_key")
        time.sleep(0.15)
        km.get_key("openai", "api_key")

        assert self.backend.get_key_calls == 2

    def test_set_key_invalidates_cache(self):
        self.km.get_key("openai", "api_key")
        assert self.backend.get_key_calls == 1

        self.km.set_key("openai", "api_key", "new-val")
        self.km.get_key("openai", "api_key")

        assert self.backend.get_key_calls == 2

    def test_delete_key_invalidates_cache(self):
        self.km.get_key("openai", "api_key")
        assert self.backend.get_key_calls == 1

        self.km.delete_key("openai", "api_key")
        self.km.get_key("openai", "api_key")

        assert self.backend.get_key_calls == 2
