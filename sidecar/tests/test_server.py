import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sidecar.api.server import _engines, app, get_engine, register_engine
from sidecar.ocr_engines.cost_tracker import cost_tracker
from sidecar.ocr_engines.interface import (
    ApiKeyError,
    NetworkError,
    OcrError,
    RateLimitError,
    ValidationResult,
)


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
    data = response.json()
    assert data["status"] == "ok"
    assert "engines" in data
    assert isinstance(data["engines"], list)


def test_shutdown_endpoint(client):
    with patch("sidecar.api.server.os._exit"):
        response = client.post("/shutdown")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shutting_down"


def test_shutdown_graceful(client):
    import asyncio

    from sidecar.api.server import lifespan

    with patch("sidecar.api.server.os._exit"):
        response = client.post("/shutdown")
        assert response.status_code == 200
        assert response.json() == {"status": "shutting_down"}

    mock_engine = MagicMock()
    mock_engine.aclose = AsyncMock()
    _engines["test_engine"] = mock_engine

    async def _verify_cleanup():
        async with lifespan(app):
            pass
        mock_engine.aclose.assert_called_once()

    asyncio.run(_verify_cleanup())


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


# ---------------------------------------------------------------------------
# Image validation
# ---------------------------------------------------------------------------


def test_ocr_empty_image_returns_400(client):
    response = client.post(
        "/api/ocr",
        json={"image_base64": "", "backend": "pix2text"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "EMPTY_IMAGE"
    assert "Empty image" in detail["message"]


def test_ocr_oversized_image_returns_413():
    from fastapi import HTTPException

    from sidecar.api.server import validate_image

    with pytest.raises(HTTPException) as exc_info:
        validate_image(b"x" * 15_000_001)
    assert exc_info.value.status_code == 413


def test_ocr_corrupt_image_returns_400(client):
    response = client.post(
        "/api/ocr",
        json={"image_base64": "!!!invalid-corrupt!!!", "backend": "openai"},
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


def test_ocr_rate_limit_before_call(client):
    """Verify 429 is returned BEFORE engine.recognize() when daily limit exceeded."""
    mock_engine = MagicMock()
    mock_engine.recognize = AsyncMock()
    register_engine("openai", mock_engine)

    for _ in range(100):
        cost_tracker.record_call(backend="openai", tokens_used=100, cost_usd=0.001)

    response = client.post(
        "/api/ocr",
        json={"image_base64": "dGVzdA==", "backend": "openai"},
    )

    assert response.status_code == 429
    mock_engine.recognize.assert_not_called()


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------


def test_ocr_endpoint_timeout_returns_504(client):
    """Verify that a slow engine triggers timeout → HTTP 504."""
    async def _fake_wait_for(coro, *, timeout=None):
        coro.close()
        raise asyncio.TimeoutError()

    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_engine.recognize = AsyncMock(return_value=MagicMock())
        mock_get_engine.return_value = mock_engine

        with patch.object(asyncio, "wait_for", side_effect=_fake_wait_for):
            response = client.post(
                "/api/ocr",
                json={"image_base64": "dGVzdA==", "backend": "pix2text"},
            )
            assert response.status_code == 504
            detail = response.json()["detail"]
            assert detail["error"] == "TIMEOUT"
            assert "120s" in detail["message"]


def test_ocr_endpoint_timeout_error_caught_directly(client):
    """Verify that asyncio.TimeoutError from engine is caught → HTTP 504."""
    with patch("sidecar.api.server.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_engine.recognize = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_get_engine.return_value = mock_engine

        response = client.post(
            "/api/ocr",
            json={"image_base64": "dGVzdA==", "backend": "pix2text"},
        )
        assert response.status_code == 504
        detail = response.json()["detail"]
        assert detail["error"] == "TIMEOUT"
        assert "120s" in detail["message"]
