"""Tests for key_manager.py — Fernet alias and restore_master_key.

Covers:
- _Fernet import alias availability
- restore_master_key error handling (NameError regression)
- generate_key() static method
"""

import pytest
from pathlib import Path

from sidecar.ocr_engines.key_manager import (
    EncryptedFileBackend,
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
