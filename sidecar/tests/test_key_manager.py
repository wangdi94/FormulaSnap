"""Tests for key_manager.py — Fernet alias, restore_master_key, cache,
encrypted backend preference, and lazy migration.

Covers:
- _Fernet import alias availability
- restore_master_key error handling (NameError regression)
- generate_key() static method
- KeyManager in-memory TTL cache (hit, expiry, invalidation)
- EncryptedFileBackend preferred over FileBackend
- Lazy migration from plaintext to encrypted storage
"""

import time
from unittest.mock import MagicMock

import pytest

from sidecar.ocr_engines.key_manager import (
    EncryptedFileBackend,
    FileBackend,
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
            encrypted_backend=None,
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
            encrypted_backend=None,
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


class TestEncryptedBackendPreference:
    """EncryptedFileBackend should be preferred over FileBackend."""

    def test_get_key_uses_encrypted_before_plaintext(self, tmp_path):
        """When a key exists in both encrypted and plaintext, encrypted wins."""
        master_key = _Fernet.generate_key()
        encrypted = EncryptedFileBackend(config_dir=tmp_path, master_key=master_key)
        encrypted.set_key("openai", "api_key", "encrypted-value")

        plaintext = FileBackend(config_dir=tmp_path)
        plaintext.set_key("openai", "api_key", "plaintext-value")

        no_keyring = MagicMock()
        no_keyring.get_key.return_value = None

        km = KeyManager(
            keyring_backend=no_keyring,
            file_backend=plaintext,
            encrypted_backend=encrypted,
        )

        assert km.get_key("openai", "api_key") == "encrypted-value"

    def test_set_key_uses_encrypted_before_plaintext(self, tmp_path):
        """set_key writes to encrypted backend, not plaintext."""
        master_key = _Fernet.generate_key()
        encrypted = EncryptedFileBackend(config_dir=tmp_path, master_key=master_key)

        plaintext = FileBackend(config_dir=tmp_path / "plain")

        no_keyring = MagicMock()
        no_keyring.set_key.side_effect = RuntimeError("no keyring")

        km = KeyManager(
            keyring_backend=no_keyring,
            file_backend=plaintext,
            encrypted_backend=encrypted,
        )

        km.set_key("openai", "api_key", "new-secret")

        assert encrypted.get_key("openai", "api_key") == "new-secret"
        assert plaintext.get_key("openai", "api_key") is None

    def test_explicit_encrypted_backend_is_used(self, tmp_path):
        """Passing an explicit EncryptedFileBackend is used by KeyManager."""
        master_key = _Fernet.generate_key()
        encrypted = EncryptedFileBackend(config_dir=tmp_path, master_key=master_key)

        no_keyring = MagicMock()
        no_keyring.get_key.return_value = None
        no_file = MagicMock()
        no_file.get_key.return_value = None
        no_file._load_keys.return_value = {}

        km = KeyManager(
            keyring_backend=no_keyring,
            file_backend=no_file,
            encrypted_backend=encrypted,
        )

        assert km._encrypted is encrypted

    def test_no_encrypted_when_explicitly_none(self):
        """Passing encrypted_backend=None disables encrypted storage."""
        no_keyring = MagicMock()
        no_keyring.get_key.return_value = None
        no_file = MagicMock()
        no_file.get_key.return_value = None
        no_file._load_keys.return_value = {}

        km = KeyManager(
            keyring_backend=no_keyring,
            file_backend=no_file,
            encrypted_backend=None,
        )

        assert km._encrypted is None


class TestLazyMigration:
    """Keys found in plaintext FileBackend should be migrated to encrypted."""

    def test_plaintext_key_migrated_on_read(self, tmp_path):
        """get_key migrates a plaintext key to encrypted backend."""
        plain_dir = tmp_path / "plain"
        enc_dir = tmp_path / "enc"

        plaintext = FileBackend(config_dir=plain_dir)
        plaintext.set_key("openai", "api_key", "sk-abc123")

        master_key = _Fernet.generate_key()
        encrypted = EncryptedFileBackend(config_dir=enc_dir, master_key=master_key)

        no_keyring = MagicMock()
        no_keyring.get_key.return_value = None

        km = KeyManager(
            keyring_backend=no_keyring,
            file_backend=plaintext,
            encrypted_backend=encrypted,
        )

        result = km.get_key("openai", "api_key")

        assert result == "sk-abc123"
        assert encrypted.get_key("openai", "api_key") == "sk-abc123"
        assert plaintext.get_key("openai", "api_key") is None

    def test_no_migration_when_key_only_in_encrypted(self, tmp_path):
        """No migration needed when key already lives in encrypted backend."""
        master_key = _Fernet.generate_key()
        encrypted = EncryptedFileBackend(config_dir=tmp_path, master_key=master_key)
        encrypted.set_key("openai", "api_key", "already-encrypted")

        plaintext = FileBackend(config_dir=tmp_path / "plain")

        no_keyring = MagicMock()
        no_keyring.get_key.return_value = None

        km = KeyManager(
            keyring_backend=no_keyring,
            file_backend=plaintext,
            encrypted_backend=encrypted,
        )

        assert km.get_key("openai", "api_key") == "already-encrypted"
        assert plaintext.get_key("openai", "api_key") is None

    def test_list_services_merges_both_backends(self, tmp_path):
        """list_services returns services from both encrypted and plaintext."""
        plain_dir = tmp_path / "plain"
        enc_dir = tmp_path / "enc"

        plaintext = FileBackend(config_dir=plain_dir)
        plaintext.set_key("mathpix", "app_id", "mpx-id")

        master_key = _Fernet.generate_key()
        encrypted = EncryptedFileBackend(config_dir=enc_dir, master_key=master_key)
        encrypted.set_key("openai", "api_key", "sk-enc")

        no_keyring = MagicMock()

        km = KeyManager(
            keyring_backend=no_keyring,
            file_backend=plaintext,
            encrypted_backend=encrypted,
        )

        services = km.list_services()
        assert "openai" in services
        assert "mathpix" in services
