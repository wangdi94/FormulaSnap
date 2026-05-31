import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from sidecar.api.server import app, register_engine, _engines, get_engine
from sidecar.ocr_engines.interface import (
    ValidationResult, ApiKeyError, RateLimitError, NetworkError, OcrError,
)
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


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ocr_endpoint_valid_request(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.latex = "$x^2$"
        mock_result.confidence = 0.95
        mock_result.backend = "pix2text"
        mock_result.timing_ms = 100
        mock_result.cost_estimate = None
        mock_engine.recognize = AsyncMock(return_value=mock_result)
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "dGVzdA==", "backend": "pix2text"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["latex"] == "$x^2$"
        assert data["confidence"] == 0.95
        assert data["backend"] == "pix2text"
        assert data["timing_ms"] == 100
        assert data["cost_estimate"] is None


def test_ocr_endpoint_invalid_backend(client):
    response = client.post(
        "/api/ocr",
        json={"image_base64": "dGVzdA==", "backend": "invalid"},
    )
    assert response.status_code == 400


def test_ocr_endpoint_missing_field(client):
    response = client.post(
        "/api/ocr",
        json={"image_base64": "dGVzdA=="},
    )
    # Missing field falls back to default "pix2text", which is not registered → 400
    assert response.status_code == 400


def test_stats_endpoint(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_calls" in data
    assert "total_tokens" in data
    assert "estimated_cost_usd" in data


def test_validate_config_endpoint(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_engine.validate_config.return_value = ValidationResult(
            valid=True, message="OK"
        )
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/validate-config",
            json={"backend": "pix2text"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["message"] == "OK"


def test_register_engine_makes_engine_available():
    mock_engine = MagicMock()
    register_engine("test_backend", mock_engine)
    assert "test_backend" in _engines
    assert get_engine("test_backend") is mock_engine


def test_get_engine_raises_for_unregistered():
    with pytest.raises(Exception):
        get_engine("nonexistent")


def test_ocr_endpoint_with_registered_engine(client):
    mock_engine = MagicMock()
    mock_result = MagicMock()
    mock_result.latex = "\\sqrt{x}"
    mock_result.confidence = 0.9
    mock_result.backend = "test_engine"
    mock_result.timing_ms = 50
    mock_result.cost_estimate = None
    mock_engine.recognize = AsyncMock(return_value=mock_result)
    register_engine("test_engine", mock_engine)

    response = client.post(
        "/api/ocr",
        json={"image_base64": "dGVzdA==", "backend": "test_engine"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["latex"] == "\\sqrt{x}"
    assert data["backend"] == "test_engine"


# ---------------------------------------------------------------------------
# Error response mapping
# ---------------------------------------------------------------------------


def test_ocr_endpoint_api_key_error_returns_401(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_engine.recognize = AsyncMock(side_effect=ApiKeyError("bad key"))
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "dGVzdA==", "backend": "openai"},
        )
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert detail["error"] == "API_KEY_ERROR"


def test_ocr_endpoint_rate_limit_error_returns_429(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_engine.recognize = AsyncMock(
            side_effect=RateLimitError("rate limited", retry_after=60)
        )
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "dGVzdA==", "backend": "openai"},
        )
        assert response.status_code == 429
        detail = response.json()["detail"]
        assert detail["error"] == "RATE_LIMIT_ERROR"
        assert detail["retry_after"] == 60


def test_ocr_endpoint_network_error_returns_503(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_engine.recognize = AsyncMock(
            side_effect=NetworkError("connection failed")
        )
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "dGVzdA==", "backend": "openai"},
        )
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["error"] == "NETWORK_ERROR"


def test_ocr_endpoint_generic_ocr_error_returns_500(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_engine.recognize = AsyncMock(
            side_effect=OcrError("something broke")
        )
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "dGVzdA==", "backend": "openai"},
        )
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["error"] == "OCR_ERROR"


def test_ocr_endpoint_invalid_base64_returns_400(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "!!!invalid-base64!!!", "backend": "openai"},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "INVALID_IMAGE"


def test_ocr_endpoint_null_confidence_for_llm(client):
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.latex = "$x^2$"
        mock_result.confidence = None
        mock_result.backend = "openai"
        mock_result.timing_ms = 100
        mock_result.cost_estimate = None
        mock_engine.recognize = AsyncMock(return_value=mock_result)
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "dGVzdA==", "backend": "openai"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] is None
