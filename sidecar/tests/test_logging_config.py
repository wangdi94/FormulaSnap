"""Tests for sidecar.logging_config module."""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path
from unittest.mock import patch

from sidecar.logging_config import _get_app_data_dir, setup_logging


class TestGetAppDataDir:
    """Tests for _get_app_data_dir()."""

    def setup_method(self):
        """Clear environment variable before each test."""
        self._env_patcher = patch.dict(os.environ, {}, clear=False)
        self._env_patcher.start()

    def teardown_method(self):
        self._env_patcher.stop()

    def test_env_override_returns_custom_path(self):
        """FORMULASNAP_APP_DATA_DIR env var takes highest priority."""
        with patch.dict(os.environ, {"FORMULASNAP_APP_DATA_DIR": "/tmp/test-app-data"}):
            result = _get_app_data_dir()
        assert result == Path("/tmp/test-app-data")

    def test_darwin_path(self):
        """macOS: ~/Library/Application Support/formulasnap."""
        with patch("sidecar.logging_config.platform.system", return_value="Darwin"):
            result = _get_app_data_dir()
        expected = Path.home() / "Library" / "Application Support" / "formulasnap"
        assert result == expected

    def test_windows_path(self):
        """Windows: %APPDATA%/formulasnap."""
        with (
            patch("sidecar.logging_config.platform.system", return_value="Windows"),
            patch.dict(os.environ, {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}),
        ):
            result = _get_app_data_dir()
        assert result == Path("C:\\Users\\test\\AppData\\Roaming") / "formulasnap"

    def test_windows_path_fallback(self):
        """Windows without APPDATA: uses ~/AppData/Roaming/formulasnap."""
        fake_home = Path("C:\\Users\\testuser")
        with (
            patch("sidecar.logging_config.platform.system", return_value="Windows"),
            patch.dict(os.environ, {}, clear=True),
            patch.object(Path, "home", return_value=fake_home),
        ):
            result = _get_app_data_dir()
        expected = fake_home / "AppData" / "Roaming" / "formulasnap"
        assert result == expected

    def test_linux_path(self):
        """Linux: ~/.config/formulasnap."""
        with patch("sidecar.logging_config.platform.system", return_value="Linux"):
            result = _get_app_data_dir()
        expected = Path.home() / ".config" / "formulasnap"
        assert result == expected

    def test_linux_path_xdg_override(self):
        """Linux with XDG_CONFIG_HOME set."""
        with (
            patch("sidecar.logging_config.platform.system", return_value="Linux"),
            patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}),
        ):
            result = _get_app_data_dir()
        assert result == Path("/custom/config") / "formulasnap"


class TestSetupLogging:
    """Tests for setup_logging()."""

    def setup_method(self):
        """Reset root logger handlers before each test."""
        root = logging.getLogger()
        root.handlers.clear()
        self._env_patcher = patch.dict(os.environ, {}, clear=False)
        self._env_patcher.start()

    def teardown_method(self):
        root = logging.getLogger()
        root.handlers.clear()
        self._env_patcher.stop()

    def test_returns_root_logger(self):
        """setup_logging returns the root logger."""
        result = setup_logging(log_dir=Path("/tmp/formulasnap-test-logs"))
        assert result is logging.getLogger()

    def test_default_log_level_is_debug(self):
        """Without explicit level, root logger level is DEBUG."""
        setup_logging(log_dir=Path("/tmp/formulasnap-test-logs"))
        assert logging.getLogger().level == logging.DEBUG

    def test_explicit_string_level(self):
        """Passing a string level like 'WARNING' configures it correctly."""
        setup_logging(level="WARNING", log_dir=Path("/tmp/formulasnap-test-logs"))
        assert logging.getLogger().level == logging.WARNING

    def test_explicit_int_level(self):
        """Passing an integer log level works."""
        setup_logging(level=logging.ERROR, log_dir=Path("/tmp/formulasnap-test-logs"))
        assert logging.getLogger().level == logging.ERROR

    def test_env_log_level(self):
        """LOG_LEVEL env var is respected when no level is passed."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}):
            setup_logging(log_dir=Path("/tmp/formulasnap-test-logs"))
        assert logging.getLogger().level == logging.INFO

    def test_creates_two_handlers(self):
        """Console + file handler = 2 handlers added."""
        setup_logging(log_dir=Path("/tmp/formulasnap-test-logs"))
        handlers = logging.getLogger().handlers
        assert len(handlers) == 2

    def test_console_handler_level_is_info(self):
        """Console handler always logs at INFO level."""
        setup_logging(log_dir=Path("/tmp/formulasnap-test-logs"))
        console = [
            h for h in logging.getLogger().handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(console) == 1
        assert console[0].level == logging.INFO

    def test_file_handler_level_is_debug(self):
        """File handler logs at DEBUG level."""
        setup_logging(log_dir=Path("/tmp/formulasnap-test-logs"))
        file_handlers = [
            h for h in logging.getLogger().handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1
        assert file_handlers[0].level == logging.DEBUG

    def test_log_file_is_created(self, tmp_path: Path):
        """Log file is created in the specified directory."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir)
        log_file = log_dir / "formulasnap-sidecar.log"
        assert log_file.exists()

    def test_removes_non_formulasnap_handlers(self):
        """Non-formulasnap handlers are removed on setup_logging call."""
        external = logging.StreamHandler()
        logging.getLogger().addHandler(external)
        setup_logging(log_dir=Path("/tmp/formulasnap-test-logs"))
        assert external not in logging.getLogger().handlers

    def test_keeps_formulasnap_tagged_handlers(self):
        """Handlers tagged with _formulasnap are kept during re-setup."""
        log_dir = Path("/tmp/formulasnap-test-logs")
        setup_logging(log_dir=log_dir)
        # All handlers after first call should have _formulasnap tag
        for h in logging.getLogger().handlers:
            assert getattr(h, "_formulasnap", False) is True
