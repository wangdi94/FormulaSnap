"""Unified logging configuration for FormulaSnap sidecar.

Provides structured logging with file output and proper log levels.

Usage:
    from sidecar.logging_config import setup_logging

    setup_logging()  # Call once at startup
"""

from __future__ import annotations

import logging
import os
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _get_app_data_dir() -> Path:
    """Get the platform-specific application data directory.

    Returns:
        Path to the application data directory:
        - macOS: ~/Library/Application Support/formulasnap/
        - Windows: %APPDATA%/formulasnap/
        - Linux: ~/.config/formulasnap/
    """
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "formulasnap"


def setup_logging(
    level: int | str | None = None,
    log_dir: Path | None = None,
) -> logging.Logger:
    """Configure logging for the FormulaSnap sidecar.

    Sets up:
    - Console handler (INFO level)
    - RotatingFileHandler (DEBUG level, 5MB max, 3 backups)
    - Log format: [%(asctime)s] %(levelname)s %(name)s: %(message)s

    Args:
        level: Log level (default: DEBUG, or LOG_LEVEL env var).
        log_dir: Directory for log files (default: <app_data_dir>/logs/).

    Returns:
        Root logger configured for the application.
    """
    # Determine log level
    if level is None:
        level_str = os.environ.get("LOG_LEVEL", "DEBUG").upper()
        log_level: int = getattr(logging, level_str, logging.DEBUG)
    elif isinstance(level, str):
        log_level = getattr(logging, level.upper(), logging.DEBUG)
    else:
        log_level = level

    # Determine log directory
    if log_dir is None:
        log_dir = _get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "formulasnap-sidecar.log"

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Only remove handlers we previously added (tagged with _formulasnap).
    # This preserves handlers installed by third-party libraries or the runtime.
    root_logger.handlers[:] = [
        h for h in root_logger.handlers
        if getattr(h, "_formulasnap", False)
    ]

    # Log format
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler._formulasnap = True  # type: ignore[attr-defined]
    root_logger.addHandler(console_handler)

    # File handler (DEBUG level, rotating)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler._formulasnap = True  # type: ignore[attr-defined]
    root_logger.addHandler(file_handler)

    # Log startup message
    root_logger.info("Logging initialized (level=%s, file=%s)", 
                     logging.getLevelName(log_level), log_file)

    return root_logger
