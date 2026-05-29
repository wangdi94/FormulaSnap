import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from sidecar.api.server import app
from sidecar.ocr_engines.interface import ValidationResult
from sidecar.ocr_engines.cost_tracker import cost_tracker

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_cost_tracker():
    cost_tracker.reset()
    yield


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ocr_endpoint_valid_request():
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


def test_ocr_endpoint_invalid_backend():
    response = client.post(
        "/api/ocr",
        json={"image_base64": "dGVzdA==", "backend": "invalid"},
    )
    assert response.status_code == 400


def test_ocr_endpoint_missing_field():
    response = client.post(
        "/api/ocr",
        json={"image_base64": "dGVzdA=="},
    )
    # Missing field falls back to default "pix2text", which is not registered → 400
    assert response.status_code == 400


def test_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_calls" in data
    assert "total_tokens" in data
    assert "estimated_cost_usd" in data


def test_validate_config_endpoint():
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
