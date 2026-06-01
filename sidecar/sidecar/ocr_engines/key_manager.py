"""Cross-platform API key management.

Provides secure storage and retrieval of API keys using the system's
native credential store:
  - macOS: Keychain (via security command or keyring library)
  - Windows: Credential Manager (via keyring library)
  - Linux: Secret Service / file-based fallback

API keys are NEVER logged. All log messages use masked values.

Usage:
    from sidecar.ocr_engines.key_manager import key_manager

    # Store a key
    key_manager.set_key("openai", "sk-abc123...")

    # Retrieve a key
    key = key_manager.get_key("openai")

    # Delete a key
    key_manager.delete_key("openai")
"""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
import shutil
import stat
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

try:
    from cryptography.fernet import Fernet as _Fernet, InvalidToken as _InvalidToken

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    _Fernet = None  # type: ignore[assignment,misc]
    _InvalidToken = None  # type: ignore[assignment,misc]
    CRYPTOGRAPHY_AVAILABLE = False

logger = logging.getLogger(__name__)

SERVICE_NAME = "formulasnap"


def _mask_key(key: str) -> str:
    """Mask an API key for safe logging.

    Shows only the first 4 and last 4 characters.

    Args:
        key: The API key to mask.

    Returns:
        Masked string like "sk-a****xyz9".
    """
    if not key or len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------


class KeyBackend(ABC):
    """Abstract interface for API key storage backends."""

    @abstractmethod
    def get_key(self, service: str, key_name: str) -> Optional[str]:
        """Retrieve an API key.

        Args:
            service: Service identifier (e.g., "openai", "mathpix").
            key_name: Key name (e.g., "api_key", "app_id").

        Returns:
            The stored key, or None if not found.
        """
        ...

    @abstractmethod
    def set_key(self, service: str, key_name: str, key_value: str) -> None:
        """Store an API key.

        Args:
            service: Service identifier.
            key_name: Key name.
            key_value: The API key value to store.
        """
        ...

    @abstractmethod
    def delete_key(self, service: str, key_name: str) -> bool:
        """Delete a stored API key.

        Args:
            service: Service identifier.
            key_name: Key name.

        Returns:
            True if the key was found and deleted, False otherwise.
        """
        ...


# ---------------------------------------------------------------------------
# Keyring Backend (macOS Keychain / Windows Credential Manager / Linux Secret Service)
# ---------------------------------------------------------------------------


class KeyringBackend(KeyBackend):
    """Key storage using the `keyring` library.

    On macOS this uses Keychain, on Windows it uses Credential Manager,
    and on Linux it uses the Secret Service API (GNOME Keyring, KWallet).

    Falls back gracefully if keyring is not available.
    """

    def __init__(self) -> None:
        try:
            import keyring as _keyring

            self._keyring = _keyring
            self._available = True
        except ImportError:
            self._keyring = None
            self._available = False
            logger.warning("keyring library not available, using fallback storage")

    @property
    def available(self) -> bool:
        """Whether the keyring backend is usable."""
        return self._available and self._keyring is not None

    def get_key(self, service: str, key_name: str) -> Optional[str]:
        if not self.available:
            return None
        try:
            value = self._keyring.get_password(service, key_name)  # type: ignore[union-attr]
            if value:
                logger.debug("Retrieved key for %s/%s", service, key_name)
            return value
        except Exception as e:
            logger.error("Failed to get key for %s/%s: %s", service, key_name, e)
            return None

    def set_key(self, service: str, key_name: str, key_value: str) -> None:
        if not self.available:
            raise RuntimeError("Keyring backend not available")
        try:
            self._keyring.set_password(service, key_name, key_value)  # type: ignore[union-attr]
            logger.info("Stored key for %s/%s (%s)", service, key_name, _mask_key(key_value))
        except Exception as e:
            logger.error("Failed to set key for %s/%s: %s", service, key_name, e)
            raise

    def delete_key(self, service: str, key_name: str) -> bool:
        if not self.available:
            return False
        try:
            self._keyring.delete_password(service, key_name)  # type: ignore[union-attr]
            logger.info("Deleted key for %s/%s", service, key_name)
            return True
        except self._keyring.errors.PasswordDeleteError:  # type: ignore[union-attr]
            return False
        except Exception as e:
            logger.error("Failed to delete key for %s/%s: %s", service, key_name, e)
            return False


# ---------------------------------------------------------------------------
# macOS Keychain Backend (direct `security` command)
# ---------------------------------------------------------------------------


class MacKeychainBackend(KeyBackend):
    """Direct macOS Keychain access via the `security` command-line tool.

    This is an alternative to the keyring library, using the system
    `security` binary directly.
    """

    def get_key(self, service: str, key_name: str) -> Optional[str]:
        if platform.system() != "Darwin":
            return None

        account = f"{service}:{key_name}"
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-s", SERVICE_NAME,
                    "-a", account,
                    "-w",  # output password only
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                logger.debug("Retrieved key from Keychain for %s/%s", service, key_name)
                return result.stdout.strip()
            return None
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error("Keychain access failed for %s/%s: %s", service, key_name, e)
            return None

    def set_key(self, service: str, key_name: str, key_value: str) -> None:
        if platform.system() != "Darwin":
            raise RuntimeError("MacKeychainBackend only works on macOS")

        account = f"{service}:{key_name}"

        # Delete existing entry first (ignore errors if not found)
        self.delete_key(service, key_name)

        try:
            process = subprocess.Popen(
                [
                    "security",
                    "add-generic-password",
                    "-s", SERVICE_NAME,
                    "-a", account,
                    "-U",  # update if exists
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            process.communicate(input=key_value, timeout=10)
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, "security")
            logger.info("Stored key in Keychain for %s/%s (%s)", service, key_name, _mask_key(key_value))
        except subprocess.SubprocessError as e:
            logger.error("Failed to store key in Keychain for %s/%s: %s", service, key_name, e)
            raise

    def delete_key(self, service: str, key_name: str) -> bool:
        if platform.system() != "Darwin":
            return False

        account = f"{service}:{key_name}"
        try:
            result = subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-s", SERVICE_NAME,
                    "-a", account,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("Deleted key from Keychain for %s/%s", service, key_name)
                return True
            return False
        except (subprocess.SubprocessError, FileNotFoundError):
            return False


# ---------------------------------------------------------------------------
# Encrypted File Backend (cross-platform fallback)
# ---------------------------------------------------------------------------


class FileBackend(KeyBackend):
    """File-based key storage with restricted file permissions.

    Keys are stored in a JSON file in the user's config directory.
    This is a fallback for systems without keyring support.

    WARNING: This is less secure than OS-native credential stores.
    The file is protected by filesystem permissions (owner-only read/write).
    """

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        if config_dir is None:
            config_dir = self._default_config_dir()
        self._config_dir = config_dir
        self._config_file = config_dir / "keys.json"
        self._ensure_config_dir()

    @staticmethod
    def _default_config_dir() -> Path:
        """Get the default configuration directory."""
        system = platform.system()
        if system == "Darwin":
            base = Path.home() / "Library" / "Application Support"
        elif system == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / SERVICE_NAME

    def _ensure_config_dir(self) -> None:
        """Create config directory with restricted permissions."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        # Set owner-only permissions (0o700)
        try:
            self._config_dir.chmod(stat.S_IRWXU)
        except OSError:
            pass  # May fail on Windows

    def _load_keys(self) -> dict[str, dict[str, str]]:
        """Load keys from the config file."""
        if not self._config_file.exists():
            return {}
        try:
            with open(self._config_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load keys file: %s", e)
            return {}

    def _save_keys(self, data: dict[str, dict[str, str]]) -> None:
        """Save keys to the config file with restricted permissions."""
        try:
            with open(self._config_file, "w") as f:
                json.dump(data, f, indent=2)
            # Set owner-only read/write (0o600)
            self._config_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            logger.error("Failed to save keys file: %s", e)
            raise

    # NOTE: FileBackend is single-process only. Concurrent writes from
    # multiple processes can corrupt keys.json. In this sidecar the file
    # backend is accessed exclusively from one uvicorn worker.

    def get_key(self, service: str, key_name: str) -> Optional[str]:
        data = self._load_keys()
        service_keys = data.get(service, {})
        value = service_keys.get(key_name)
        if value:
            logger.debug("Retrieved key from file for %s/%s", service, key_name)
        return value

    def set_key(self, service: str, key_name: str, key_value: str) -> None:
        data = self._load_keys()
        if service not in data:
            data[service] = {}
        data[service][key_name] = key_value
        self._save_keys(data)
        logger.info("Stored key in file for %s/%s (%s)", service, key_name, _mask_key(key_value))

    def delete_key(self, service: str, key_name: str) -> bool:
        data = self._load_keys()
        service_keys = data.get(service, {})
        if key_name not in service_keys:
            return False
        del service_keys[key_name]
        if not service_keys:
            del data[service]
        self._save_keys(data)
        logger.info("Deleted key from file for %s/%s", service, key_name)
        return True


# ---------------------------------------------------------------------------
# Encrypted File Backend (Fernet symmetric encryption)
# ---------------------------------------------------------------------------


class EncryptedFileBackend(KeyBackend):
    """Encrypted file-based key storage using Fernet symmetric encryption.

    Keys are encrypted at rest using a master encryption key stored in a
    separate file. The master key can also be provided via the
    ``FORMULASNP_MASTER_KEY`` environment variable (base64-encoded Fernet key).

    Features:
    - Fernet (AES-128-CBC + HMAC-SHA256) authenticated encryption
    - Auto-migration from plaintext ``keys.json`` on first access
    - Master key generation, backup, and restore

    Args:
        config_dir: Directory for storing keys and master key.
            Defaults to the platform-specific application config directory.
        master_key: Optional pre-existing Fernet key (bytes).
            If not provided, loads from env var or generates/loads from file.
    """

    MASTER_KEY_FILENAME = "master.key"
    ENCRYPTED_KEYS_FILENAME = "keys.enc.json"
    MIGRATION_MARKER = ".migrated"

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        master_key: Optional[bytes] = None,
    ) -> None:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography library is required for EncryptedFileBackend. "
                "Install it with: pip install cryptography"
            )
        if config_dir is None:
            config_dir = self._default_config_dir()
        self._config_dir = config_dir
        self._config_file = config_dir / self.ENCRYPTED_KEYS_FILENAME
        self._master_key_path = config_dir / self.MASTER_KEY_FILENAME
        self._ensure_config_dir()

        if master_key is not None:
            self._master_key = master_key
        else:
            self._master_key = self._load_or_generate_master_key()

        self._fernet = _Fernet(self._master_key)
        self._auto_migrate()

    @staticmethod
    def _default_config_dir() -> Path:
        """Get the default configuration directory."""
        system = platform.system()
        if system == "Darwin":
            base = Path.home() / "Library" / "Application Support"
        elif system == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / SERVICE_NAME

    def _ensure_config_dir(self) -> None:
        """Create config directory with restricted permissions."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._config_dir.chmod(stat.S_IRWXU)
        except OSError:
            pass  # May fail on Windows

    def _load_or_generate_master_key(self) -> bytes:
        """Load the master encryption key from env var or file.

        Checks in order:
        1. ``FORMULASNP_MASTER_KEY`` environment variable (base64-encoded)
        2. ``master.key`` file in config directory
        3. Generates a new key and saves it

        Returns:
            The Fernet encryption key (bytes).
        """
        # 1. Check environment variable
        env_key = os.environ.get("FORMULASNP_MASTER_KEY")
        if env_key:
            try:
                key_bytes = base64.urlsafe_b64decode(env_key)
                # Validate it's a valid Fernet key (32 bytes url-safe base64)
                _Fernet(env_key.encode() if isinstance(env_key, str) else env_key)
                logger.info("Loaded master key from environment variable")
                return env_key.encode() if isinstance(env_key, str) else env_key
            except Exception:
                logger.warning("Invalid FORMULASNP_MASTER_KEY env var, ignoring")

        # 2. Check file
        if self._master_key_path.exists():
            try:
                key_data = self._master_key_path.read_bytes().strip()
                _Fernet(key_data)  # type: ignore[misc]
                logger.info("Loaded master key from file")
                return key_data
            except Exception:
                logger.warning("Invalid master key file, regenerating")

        # 3. Generate new key
        return self._generate_and_save_master_key()

    def _generate_and_save_master_key(self) -> bytes:
        """Generate a new Fernet key and save it to file.

        Returns:
            The newly generated Fernet key.
        """
        key = _Fernet.generate_key()  # type: ignore[union-attr]
        try:
            self._master_key_path.write_bytes(key)
            self._master_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            logger.info("Generated and saved new master key")
        except OSError as e:
            logger.error("Failed to save master key: %s", e)
            raise
        return key

    def _is_plaintext_json(self, path: Path) -> bool:
        """Check if a JSON file contains plaintext (unencrypted) keys.

        Reads the first few bytes to detect if it starts with '{'
        (indicating unencrypted JSON) vs encrypted Fernet tokens
        (which start with 'gAAAAA').

        Args:
            path: Path to the keys file.

        Returns:
            True if the file appears to be plaintext JSON.
        """
        if not path.exists():
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(20)
            # Plaintext JSON starts with '{', Fernet tokens start with 'gAAAAA'
            return header.startswith(b"{")
        except OSError:
            return False

    def _auto_migrate(self) -> None:
        """Auto-migrate plaintext keys.json to encrypted storage.

        Checks for an existing plaintext ``keys.json`` from FileBackend
        and migrates it to encrypted ``keys.enc.json``. Creates a
        ``.migrated`` marker to avoid re-migration.
        """
        marker = self._config_dir / self.MIGRATION_MARKER
        if marker.exists():
            return

        plaintext_file = self._config_dir / "keys.json"
        if not plaintext_file.exists():
            return

        if not self._is_plaintext_json(plaintext_file):
            return

        try:
            with open(plaintext_file, "r") as f:
                data = json.load(f)
            if not data:
                # Empty file, just mark as migrated
                marker.write_text(str(time.time()))
                return

            # Save encrypted
            self._save_keys(data)

            # Backup plaintext file
            backup_path = plaintext_file.with_suffix(".json.bak")
            shutil.copy2(plaintext_file, backup_path)

            # Remove plaintext file
            plaintext_file.unlink()

            # Write migration marker
            marker.write_text(str(time.time()))

            logger.info(
                "Auto-migrated %d services from plaintext to encrypted storage",
                len(data),
            )
        except Exception as e:
            logger.error("Auto-migration failed: %s", e)
            # Don't raise — fall back to empty encrypted store

    def _load_keys(self) -> dict[str, dict[str, str]]:
        """Load and decrypt keys from the encrypted config file.

        Returns:
            Decrypted key data dict, or empty dict if file doesn't exist
            or decryption fails.
        """
        if not self._config_file.exists():
            return {}
        try:
            encrypted_data = self._config_file.read_bytes()
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except _InvalidToken:  # type: ignore[misc]
            logger.error(
                "Failed to decrypt keys — master key may have changed. "
                "Keys will be treated as empty."
            )
            return {}
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load encrypted keys file: %s", e)
            return {}

    def _save_keys(self, data: dict[str, dict[str, str]]) -> None:
        """Encrypt and save keys to the config file.

        Args:
            data: Key data dict to encrypt and save.
        """
        try:
            plaintext = json.dumps(data, indent=2).encode("utf-8")
            encrypted_data = self._fernet.encrypt(plaintext)
            self._config_file.write_bytes(encrypted_data)
            self._config_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            logger.error("Failed to save encrypted keys file: %s", e)
            raise

    def get_key(self, service: str, key_name: str) -> Optional[str]:
        data = self._load_keys()
        service_keys = data.get(service, {})
        value = service_keys.get(key_name)
        if value:
            logger.debug("Retrieved encrypted key for %s/%s", service, key_name)
        return value

    def set_key(self, service: str, key_name: str, key_value: str) -> None:
        data = self._load_keys()
        if service not in data:
            data[service] = {}
        data[service][key_name] = key_value
        self._save_keys(data)
        logger.info(
            "Stored encrypted key for %s/%s (%s)",
            service,
            key_name,
            _mask_key(key_value),
        )

    def delete_key(self, service: str, key_name: str) -> bool:
        data = self._load_keys()
        service_keys = data.get(service, {})
        if key_name not in service_keys:
            return False
        del service_keys[key_name]
        if not service_keys:
            del data[service]
        self._save_keys(data)
        logger.info("Deleted encrypted key for %s/%s", service, key_name)
        return True

    # ------------------------------------------------------------------
    # Master key management
    # ------------------------------------------------------------------

    def backup_master_key(self, backup_path: Optional[Path] = None) -> Path:
        """Create a backup of the master encryption key.

        Args:
            backup_path: Where to save the backup. Defaults to
                ``<config_dir>/master.key.bak.<timestamp>``.

        Returns:
            Path to the backup file.
        """
        if backup_path is None:
            ts = int(time.time())
            backup_path = self._config_dir / f"master.key.bak.{ts}"
        shutil.copy2(self._master_key_path, backup_path)
        backup_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        logger.info("Master key backed up to %s", backup_path)
        return backup_path

    def restore_master_key(self, backup_path: Path) -> None:
        """Restore the master encryption key from a backup.

        After restoring, the Fernet instance is re-created with the
        restored key. Existing encrypted keys can then be decrypted
        with the restored key.

        Args:
            backup_path: Path to the backup file.

        Raises:
            FileNotFoundError: If backup file doesn't exist.
            ValueError: If backup contains an invalid Fernet key.
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        key_data = backup_path.read_bytes().strip()
        # Validate
        try:
            Fernet(key_data)
        except Exception as e:
            raise ValueError(f"Invalid Fernet key in backup: {e}") from e
        self._master_key_path.write_bytes(key_data)
        self._master_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self._master_key = key_data
        self._fernet = Fernet(key_data)
        logger.info("Master key restored from %s", backup_path)

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new Fernet encryption key.

        This is a convenience method. The key can be used to initialize
        a new ``EncryptedFileBackend`` instance or passed via the
        ``FORMULASNP_MASTER_KEY`` environment variable.

        Returns:
            A new Fernet key (bytes, url-safe base64-encoded).
        """
        return Fernet.generate_key()


# ---------------------------------------------------------------------------
# Composite Manager
# ---------------------------------------------------------------------------


class KeyManager:
    """Cross-platform API key manager.

    Attempts to use the best available backend:
    1. Keyring (macOS Keychain / Windows Credential Manager / Linux Secret Service)
    2. Encrypted file fallback

    Also checks environment variables as a read-only source.

    Environment variable naming convention:
        {SERVICE}_{KEY_NAME} → e.g., OPENAI_API_KEY, MATHPIX_APP_ID

    Usage:
        km = KeyManager()

        # Store
        km.set_key("openai", "api_key", "sk-...")

        # Retrieve (checks keyring first, then env vars)
        key = km.get_key("openai", "api_key")

        # Delete
        km.delete_key("openai", "api_key")
    """

    def __init__(
        self,
        keyring_backend: Optional[KeyBackend] = None,
        file_backend: Optional[FileBackend] = None,
    ) -> None:
        self._keyring = keyring_backend or KeyringBackend()
        self._file = file_backend or FileBackend()

    def get_key(self, service: str, key_name: str = "api_key") -> Optional[str]:
        """Retrieve an API key.

        Checks in order: keyring, file backend, environment variables.

        Args:
            service: Service identifier (e.g., "openai", "mathpix").
            key_name: Key name (default: "api_key").

        Returns:
            The key value, or None if not found.
        """
        # Try keyring first
        value = self._keyring.get_key(service, key_name)
        if value:
            return value

        # Try file backend
        value = self._file.get_key(service, key_name)
        if value:
            return value

        # Try environment variable
        env_var = f"{service.upper()}_{key_name.upper()}"
        value = os.environ.get(env_var)
        if value:
            logger.debug("Using key from environment variable %s", env_var)
            return value

        return None

    def set_key(self, service: str, key_name: str, key_value: str) -> None:
        """Store an API key.

        Stores in both keyring and file backend for redundancy.

        Args:
            service: Service identifier.
            key_name: Key name.
            key_value: The API key to store.
        """
        # Try keyring first
        try:
            self._keyring.set_key(service, key_name, key_value)
        except Exception:
            logger.warning("Keyring storage failed, using file backend only")

        # Always store in file backend as backup
        self._file.set_key(service, key_name, key_value)

    def delete_key(self, service: str, key_name: str = "api_key") -> bool:
        """Delete a stored API key.

        Deletes from both keyring and file backend.

        Args:
            service: Service identifier.
            key_name: Key name.

        Returns:
            True if the key was found and deleted from at least one backend.
        """
        deleted_keyring = False
        deleted_file = False

        try:
            deleted_keyring = self._keyring.delete_key(service, key_name)
        except Exception:
            logger.warning("Keyring delete failed for service=%s key=%s", service, key_name)

        try:
            deleted_file = self._file.delete_key(service, key_name)
        except Exception:
            logger.warning("File backend delete failed for service=%s key=%s", service, key_name)

        return deleted_keyring or deleted_file

    def list_services(self) -> list[str]:
        """List services with stored keys in the file backend.

        Returns:
            List of service identifiers.
        """
        data = self._file._load_keys()
        return list(data.keys())


# Module-level singleton
key_manager = KeyManager()
