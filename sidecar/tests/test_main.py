"""Tests for sidecar.main module."""

from __future__ import annotations

import os
from unittest.mock import patch

from sidecar.main import _register_engines, main


class TestRegisterEngines:
    """Tests for _register_engines()."""

    def setup_method(self):
        """Clear registered engines before each test."""
        from sidecar.api.server import _engines
        _engines.clear()

    def teardown_method(self):
        from sidecar.api.server import _engines
        _engines.clear()

    def test_pix2text_always_registered(self):
        """Pix2Text engine is always registered (local, no key needed)."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine") as mock_register,
        ):
            mock_km.get_key.return_value = None
            registered = _register_engines()

        assert "pix2text" in registered
        first_call_args = mock_register.call_args_list[0][0]
        assert first_call_args[0] == "pix2text"

    def test_mathpix_registered_with_both_keys(self):
        """Mathpix registers when both app_id and app_key are present."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine"),
        ):
            mock_km.get_key.return_value = "some-value"
            registered = _register_engines()

        assert "mathpix" in registered

    def test_mathpix_not_registered_without_keys(self):
        """Mathpix is not registered when keys are missing."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine"),
        ):
            mock_km.get_key.return_value = None
            registered = _register_engines()

        assert "mathpix" not in registered

    def test_openai_registered_with_key(self):
        """OpenAI registers when api_key is present."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine"),
        ):
            mock_km.get_key.return_value = "sk-test"
            registered = _register_engines()

        assert "openai" in registered

    def test_claude_registered_with_key(self):
        """Claude registers when api_key is present."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine"),
        ):
            mock_km.get_key.return_value = "claude-key"
            registered = _register_engines()

        assert "claude" in registered

    def test_gemini_registered_with_key(self):
        """Gemini registers when api_key is present."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine"),
        ):
            mock_km.get_key.return_value = "gemini-key"
            registered = _register_engines()

        assert "gemini" in registered

    def test_returns_only_pix2text_when_no_keys(self):
        """With no API keys configured, only pix2text is registered."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine"),
        ):
            mock_km.get_key.return_value = None
            registered = _register_engines()

        assert registered == ["pix2text"]

    def test_returns_all_five_when_all_keys_present(self):
        """All engines registered when all API keys are present."""
        with (
            patch("sidecar.main.key_manager") as mock_km,
            patch("sidecar.main.register_engine"),
        ):
            mock_km.get_key.return_value = "valid-key"
            registered = _register_engines()

        assert registered == ["pix2text", "mathpix", "openai", "claude", "gemini"]


class TestMain:
    """Tests for main()."""

    def setup_method(self):
        pass

    def test_calls_setup_logging(self):
        """main() calls setup_logging() to configure logging."""
        with (
            patch("sidecar.main.setup_logging") as mock_setup,
            patch("sidecar.main._register_engines", return_value=["pix2text"]),
            patch("sidecar.main.uvicorn.run"),
            patch.dict(os.environ, {}, clear=False),
        ):
            main()
            mock_setup.assert_called_once()

    def test_calls_register_engines(self):
        """main() calls _register_engines() and logs registered engines."""
        with (
            patch("sidecar.main.setup_logging"),
            patch("sidecar.main._register_engines", return_value=["pix2text", "openai"]),
            patch("sidecar.main.uvicorn.run"),
            patch.dict(os.environ, {}, clear=False),
        ):
            main()

    def test_uvicorn_run_with_correct_config(self):
        """main() starts uvicorn with correct host/port."""
        with (
            patch("sidecar.main.setup_logging"),
            patch("sidecar.main._register_engines", return_value=["pix2text"]),
            patch("sidecar.main.uvicorn.run") as mock_run,
            patch.dict(os.environ, {}, clear=False),
        ):
            main()
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8477
        assert kwargs["log_config"] is None

    def test_reload_enabled_via_env(self):
        """FORMULASNAP_SIDECAR_RELOAD=true enables reload."""
        with (
            patch("sidecar.main.setup_logging"),
            patch("sidecar.main._register_engines", return_value=["pix2text"]),
            patch("sidecar.main.uvicorn.run") as mock_run,
            patch.dict(os.environ, {"FORMULASNAP_SIDECAR_RELOAD": "true"}),
        ):
            main()
        _, kwargs = mock_run.call_args
        assert kwargs["reload"] is True

    def test_reload_disabled_by_default(self):
        """Without env var, reload is False."""
        with (
            patch("sidecar.main.setup_logging"),
            patch("sidecar.main._register_engines", return_value=["pix2text"]),
            patch("sidecar.main.uvicorn.run") as mock_run,
            patch.dict(os.environ, {}, clear=True),
        ):
            main()
        _, kwargs = mock_run.call_args
        assert kwargs["reload"] is False
