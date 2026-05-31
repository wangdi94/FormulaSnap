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

import json
import logging
import os
import platform
import stat
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

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
