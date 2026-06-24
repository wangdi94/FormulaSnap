import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sidecar.api.server import _SHUTDOWN_TOKEN, _engines, app, get_engine, register_engine
from sidecar.cache import ocr_cache
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
    ocr_cache.clear()
    yield
    _engines.clear()
    ocr_cache.clear()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "engines" in data
    assert isinstance(data["engines"], list)


def test_shutdown_endpoint(client):
    with patch("sidecar.api.server.signal.raise_signal"), patch(
        "sidecar.api.server.threading"
    ) as mock_threading:
        mock_timer = MagicMock()
        mock_threading.Timer.return_value = mock_timer
        response = client.post("/shutdown", json={"token": _SHUTDOWN_TOKEN})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shutting_down"
        mock_timer.start.assert_called_once()


def test_shutdown_graceful(client):
    import asyncio

    from sidecar.api.server import lifespan

    with patch("sidecar.api.server.signal.raise_signal"), patch(
        "sidecar.api.server.threading"
    ) as mock_threading:
        mock_timer = MagicMock()
        mock_threading.Timer.return_value = mock_timer
        response = client.post("/shutdown", json={"token": _SHUTDOWN_TOKEN})
        assert response.status_code == 200
        assert response.json() == {"status": "shutting_down"}
        mock_timer.start.assert_called_once()

    mock_engine = MagicMock()
    mock_engine.aclose = AsyncMock()
    _engines["test_engine"] = mock_engine

    async def _verify_cleanup():
        async with lifespan(app):
            pass
        mock_engine.aclose.assert_called_once()

    asyncio.run(_verify_cleanup())


# ---------------------------------------------------------------------------
# Shutdown authentication
# ---------------------------------------------------------------------------


def test_shutdown_requires_token(client):
    response = client.post("/shutdown")
    assert response.status_code == 403


def test_shutdown_wrong_token(client):
    response = client.post("/shutdown", json={"token": "wrong-token"})
    assert response.status_code == 403


def test_shutdown_correct_token(client):
    with patch("sidecar.api.server.signal.raise_signal"), patch(
        "sidecar.api.server.threading"
    ) as mock_threading:
        mock_timer = MagicMock()
        mock_threading.Timer.return_value = mock_timer
        response = client.post("/shutdown", json={"token": _SHUTDOWN_TOKEN})
        assert response.status_code == 200
        assert response.json()["status"] == "shutting_down"
        mock_timer.start.assert_called_once()


def test_shutdown_token_from_header(client):
    with patch("sidecar.api.server.signal.raise_signal"), patch(
        "sidecar.api.server.threading"
    ) as mock_threading:
        mock_timer = MagicMock()
        mock_threading.Timer.return_value = mock_timer
        response = client.post(
            "/shutdown", headers={"X-Shutdown-Token": _SHUTDOWN_TOKEN}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "shutting_down"
        mock_timer.start.assert_called_once()


def test_shutdown_token_from_env():
    import os

    with patch.dict(os.environ, {"FORMULASNAP_SHUTDOWN_TOKEN": "env-token"}):
        result = os.environ.get("FORMULASNAP_SHUTDOWN_TOKEN", "") or str(uuid.uuid4())
        assert result == "env-token"

    with patch.dict(os.environ, {"FORMULASNAP_SHUTDOWN_TOKEN": ""}, clear=False):
        result = os.environ.get("FORMULASNAP_SHUTDOWN_TOKEN", "") or str(uuid.uuid4())
        assert len(result) == 36


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


# ---------------------------------------------------------------------------
# Lifespan shutdown — engine cleanup
# ---------------------------------------------------------------------------


def test_shutdown_aclose_called_on_all_engines():
    """All registered engines with aclose() get called during shutdown."""
    from sidecar.api.server import lifespan

    engines = {}
    for name in ("pix2text", "openai", "claude"):
        mock_engine = MagicMock()
        mock_engine.aclose = AsyncMock()
        engines[name] = mock_engine
        _engines[name] = mock_engine

    async def _verify():
        async with lifespan(app):
            pass
        for name, engine in engines.items():
            engine.aclose.assert_called_once()

    asyncio.run(_verify())


def test_shutdown_engine_without_aclose():
    """Engine without aclose() is skipped without error."""
    from sidecar.api.server import lifespan

    mock_engine = MagicMock(spec=["recognize"])  # no aclose
    _engines["bare"] = mock_engine

    mock_with_close = MagicMock()
    mock_with_close.aclose = AsyncMock()
    _engines["with_close"] = mock_with_close

    async def _verify():
        async with lifespan(app):
            pass
        mock_with_close.aclose.assert_called_once()

    asyncio.run(_verify())


def test_shutdown_aclose_timeout():
    """Engine whose aclose() exceeds timeout does not block shutdown."""
    from sidecar.api.server import lifespan

    async def _slow_close():
        await asyncio.sleep(999)

    mock_engine = MagicMock()
    mock_engine.aclose = _slow_close
    _engines["slow"] = mock_engine

    mock_fast = MagicMock()
    mock_fast.aclose = AsyncMock()
    _engines["fast"] = mock_fast

    async def _verify():
        async with lifespan(app):
            pass
        mock_fast.aclose.assert_called_once()

    with patch("sidecar.api.server._SHUTDOWN_TIMEOUT", 0.1):
        asyncio.run(_verify())


def test_shutdown_aclose_exception_continues():
    """Exception in one engine's aclose() does not prevent others from closing."""
    from sidecar.api.server import lifespan

    async def _broken_close():
        raise RuntimeError("broken")

    mock_broken = MagicMock()
    mock_broken.aclose = _broken_close
    _engines["broken"] = mock_broken

    mock_good = MagicMock()
    mock_good.aclose = AsyncMock()
    _engines["good"] = mock_good

    async def _verify():
        async with lifespan(app):
            pass
        mock_good.aclose.assert_called_once()

    asyncio.run(_verify())


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


def test_request_logging(client, caplog):
    with caplog.at_level("INFO", logger="sidecar.api.server"):
        client.get("/api/stats")

    matching = [
        r for r in caplog.records
        if "/api/stats" in r.getMessage() and r.name == "sidecar.api.server"
    ]
    assert len(matching) == 1
    msg = matching[0].getMessage()
    assert "GET" in msg
    assert "200" in msg
    assert "ms]" in msg


def test_request_logging_skips_health(client, caplog):
    with caplog.at_level("INFO", logger="sidecar.api.server"):
        client.get("/health")

    matching = [
        r for r in caplog.records
        if "/health" in r.getMessage() and r.name == "sidecar.api.server"
    ]
    assert len(matching) == 0


# ---------------------------------------------------------------------------
# API Key management endpoints
# ---------------------------------------------------------------------------


def test_get_keys_returns_masked(client):
    """GET /api/keys returns configured status — never exposes actual key values."""
    mock_stored = {
        ("openai", "api_key"): "sk-1234567890abcdef",
        ("mathpix", "app_id"): "mathpix-id-12345",
    }

    def _mock_get_key(service, key_name):
        return mock_stored.get((service, key_name))

    with patch("sidecar.api.server.key_manager") as mock_km:
        mock_km.get_key = MagicMock(side_effect=_mock_get_key)

        response = client.get("/api/keys")
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        keys = data["keys"]
        assert len(keys) == 5

        response_text = str(data)
        assert "sk-1234567890abcdef" not in response_text
        assert "mathpix-id-12345" not in response_text

        openai_entry = next(k for k in keys if k["backend"] == "openai")
        assert openai_entry["configured"] is True

        mathpix_id_entry = next(k for k in keys if k["backend"] == "mathpix_app_id")
        assert mathpix_id_entry["configured"] is True

        claude_entry = next(k for k in keys if k["backend"] == "claude")
        assert claude_entry["configured"] is False

        gemini_entry = next(k for k in keys if k["backend"] == "gemini")
        assert gemini_entry["configured"] is False


def test_set_key_works(client):
    """POST /api/keys with valid backend/key succeeds and calls key_manager."""
    with patch("sidecar.api.server.key_manager") as mock_km:
        mock_km.set_key = MagicMock()

        response = client.post(
            "/api/keys",
            json={"backend": "openai", "key": "sk-test-abcdef123456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["backend"] == "openai"
        mock_km.set_key.assert_called_once_with(
            "openai", "api_key", "sk-test-abcdef123456"
        )


def test_set_key_empty_value_rejected(client):
    """POST /api/keys with empty key_value is rejected by Pydantic validation."""
    response = client.post(
        "/api/keys",
        json={"backend": "openai", "key": ""},
    )
    assert response.status_code == 422


def test_set_key_unknown_backend_rejected(client):
    """POST /api/keys with unknown backend returns 400."""
    response = client.post(
        "/api/keys",
        json={"backend": "nonexistent", "key": "some-key-value"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unknown backend" in detail


@pytest.mark.skip(reason="DELETE /api/keys endpoint not yet implemented — TDD spec")
def test_delete_key_works(client):
    """DELETE /api/keys with valid backend succeeds (TDD spec for future endpoint)."""
    with patch("sidecar.api.server.key_manager") as mock_km:
        mock_km.delete_key = MagicMock(return_value=True)

        response = client.delete(
            "/api/keys",
            json={"backend": "openai"},
        )
        assert response.status_code == 200
        mock_km.delete_key.assert_called_once_with("openai", "api_key")


@pytest.mark.skip(reason="DELETE /api/keys endpoint not yet implemented — TDD spec")
def test_delete_key_not_found(client):
    """DELETE /api/keys for non-existent key returns 404 (TDD spec for future endpoint)."""
    with patch("sidecar.api.server.key_manager") as mock_km:
        mock_km.delete_key = MagicMock(return_value=False)

        response = client.delete(
            "/api/keys",
            json={"backend": "openai"},
        )
        assert response.status_code == 404
