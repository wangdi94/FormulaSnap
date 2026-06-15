"""Tests for lazy engine loading — only register engines with valid API keys."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sidecar.api.server import _engines, app, register_engine
from sidecar.ocr_engines.cost_tracker import cost_tracker


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_cost_tracker():
    cost_tracker.reset()
    yield


@pytest.fixture(autouse=True)
def clear_engines():
    _engines.clear()
    yield
    _engines.clear()


# ---------------------------------------------------------------------------
# _register_engines() lazy loading tests
# ---------------------------------------------------------------------------


def _mock_key_manager_get_key(available_keys: dict[str, dict[str, str]] | None = None):
    """Create a mock key_manager.get_key that returns keys from available_keys.

    Args:
        available_keys: Dict of {service: {key_name: value}}.
            If None, no keys are available.
    """
    if available_keys is None:
        available_keys = {}

    def _get_key(service: str, key_name: str = "api_key"):
        return available_keys.get(service, {}).get(key_name)

    return _get_key


class TestLazyEngineRegistration:
    """Test that _register_engines() only registers engines with valid API keys."""

    def setup_method(self):
        _engines.clear()

    def test_only_pix2text_registered_when_no_keys(self):
        """When no API keys exist, only Pix2Text (local engine) should be registered."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({})

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        # Only pix2text should be registered
        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "pix2text" in registered_names
        assert len(registered_calls) == 1

    def test_mathpix_registered_when_both_keys_exist(self):
        """Mathpix should be registered when both app_id and app_key are available."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({
            "mathpix": {"app_id": "test_id", "app_key": "test_key"},
        })

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "pix2text" in registered_names
        assert "mathpix" in registered_names

    def test_mathpix_not_registered_when_only_app_id(self):
        """Mathpix should NOT be registered when only app_id is available."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({
            "mathpix": {"app_id": "test_id"},
        })

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "mathpix" not in registered_names

    def test_openai_registered_when_key_exists(self):
        """OpenAI should be registered when api_key is available."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({
            "openai": {"api_key": "sk-test123"},
        })

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "openai" in registered_names

    def test_claude_registered_when_key_exists(self):
        """Claude should be registered when api_key is available."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({
            "claude": {"api_key": "sk-ant-test123"},
        })

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "claude" in registered_names

    def test_gemini_registered_when_key_exists(self):
        """Gemini should be registered when api_key is available."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({
            "gemini": {"api_key": "AIza-test123"},
        })

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "gemini" in registered_names

    def test_all_engines_registered_when_all_keys_exist(self):
        """All engines should be registered when all API keys are available."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({
            "mathpix": {"app_id": "test_id", "app_key": "test_key"},
            "openai": {"api_key": "sk-test123"},
            "claude": {"api_key": "sk-ant-test123"},
            "gemini": {"api_key": "AIza-test123"},
        })

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "pix2text" in registered_names
        assert "mathpix" in registered_names
        assert "openai" in registered_names
        assert "claude" in registered_names
        assert "gemini" in registered_names
        assert len(registered_calls) == 5

    def test_partial_keys_register_subset(self):
        """Only engines with valid keys should be registered."""
        from sidecar.main import _register_engines

        mock_km = MagicMock()
        mock_km.get_key = _mock_key_manager_get_key({
            "openai": {"api_key": "sk-test123"},
            "gemini": {"api_key": "AIza-test123"},
        })

        with patch("sidecar.main.key_manager", mock_km):
            with patch("sidecar.main.register_engine") as mock_register:
                _register_engines()

        registered_calls = mock_register.call_args_list
        registered_names = [call[0][0] for call in registered_calls]
        assert "pix2text" in registered_names
        assert "openai" in registered_names
        assert "gemini" in registered_names
        assert "mathpix" not in registered_names
        assert "claude" not in registered_names
        assert len(registered_calls) == 3


# ---------------------------------------------------------------------------
# /health endpoint engine status tests
# ---------------------------------------------------------------------------


class TestHealthEndpointEngineStatus:
    """Test that /health endpoint reports engine status."""

    def test_health_includes_engines_field(self, client):
        """Health response should include registered engines list."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "engines" in data

    def test_health_engines_empty_when_none_registered(self, client):
        """When no engines are registered, engines list should be empty."""
        response = client.get("/health")
        data = response.json()
        assert data["engines"] == []

    def test_health_engines_lists_registered(self, client):
        """Registered engines should appear in the engines list."""
        mock_engine = MagicMock()
        register_engine("pix2text", mock_engine)
        register_engine("openai", mock_engine)

        response = client.get("/health")
        data = response.json()
        assert "pix2text" in data["engines"]
        assert "openai" in data["engines"]
        assert len(data["engines"]) == 2


# ---------------------------------------------------------------------------
# /api/engines/status endpoint tests
# ---------------------------------------------------------------------------


class TestEnginesStatusEndpoint:
    """Test the /api/engines/status endpoint."""

    def test_engines_status_endpoint_exists(self, client):
        """The /api/engines/status endpoint should return 200."""
        response = client.get("/api/engines/status")
        assert response.status_code == 200

    def test_engines_status_returns_registered_list(self, client):
        """Endpoint should return list of registered engine names."""
        mock_engine = MagicMock()
        register_engine("pix2text", mock_engine)

        response = client.get("/api/engines/status")
        data = response.json()
        assert "registered" in data
        assert "pix2text" in data["registered"]

    def test_engines_status_empty_when_none_registered(self, client):
        """When no engines registered, registered list should be empty."""
        response = client.get("/api/engines/status")
        data = response.json()
        assert data["registered"] == []
        assert data["count"] == 0

    def test_engines_status_count(self, client):
        """Endpoint should report count of registered engines."""
        mock_engine = MagicMock()
        register_engine("pix2text", mock_engine)
        register_engine("openai", mock_engine)

        response = client.get("/api/engines/status")
        data = response.json()
        assert data["count"] == 2
