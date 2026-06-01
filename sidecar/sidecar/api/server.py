from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import AsyncIterator, Optional
import base64
import binascii
import logging
import os
import threading

from sidecar.ocr_engines.interface import (
    OcrBackend, OcrOptions, OcrError,
    ApiKeyError, RateLimitError, NetworkError,
)
from sidecar.ocr_engines.cost_tracker import cost_tracker, RateLimitExceeded
from sidecar.ocr_engines.key_manager import key_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    logger.info("Shutting down: closing OCR engines...")
    for name, engine in _engines.items():
        aclose_fn = getattr(engine, "aclose", None)
        if aclose_fn is not None:
            try:
                await aclose_fn()
                logger.info("Closed engine: %s", name)
            except Exception:
                logger.warning("Error closing engine %s", name, exc_info=True)


app = FastAPI(title="FormulaSnap Sidecar", lifespan=lifespan)

# CORS for localhost
_sidecar_port = os.environ.get("SIDECAR_PORT", "8477")
_allowed_origins = [
    f"http://localhost:{_sidecar_port}",
    "http://localhost:1420",
    "tauri://localhost",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OcrRequest(BaseModel):
    image_base64: str = Field(..., max_length=20_000_000)
    backend: str = "pix2text"


class OcrResponse(BaseModel):
    latex: str
    confidence: Optional[float] = None
    backend: str
    timing_ms: int
    cost_estimate: Optional[dict] = None


class ValidateConfigRequest(BaseModel):
    backend: str


class StatsResponse(BaseModel):
    total_calls: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    calls_today: int = 0
    daily_limit: int = 100
    remaining_today: int = 100


class SaveKeyRequest(BaseModel):
    backend: str
    key: str = Field(..., min_length=1)


class KeyStatusItem(BaseModel):
    backend: str
    configured: bool


class KeysResponse(BaseModel):
    keys: list[KeyStatusItem]


# ---------------------------------------------------------------------------
# Engine registry & stats
# ---------------------------------------------------------------------------

# NOTE: _engines is only accessed from the FastAPI event loop (single-threaded).
# No locking is needed because uvicorn serves requests on one thread by default.
_engines: dict[str, OcrBackend] = {}


def get_engine(backend: str) -> OcrBackend:
    if backend not in _engines:
        raise HTTPException(status_code=400, detail=f"Unknown backend: {backend}")
    return _engines[backend]


def register_engine(backend: str, engine: OcrBackend) -> None:
    _engines[backend] = engine


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/shutdown")
async def shutdown():
    """优雅关闭端点：返回 200 后触发进程退出。"""
    logger.info("收到 shutdown 请求，准备退出...")

    # 使用定时器延迟退出，确保 HTTP 响应先发送完成
    def _do_exit():
        logger.info("执行进程退出")
        os._exit(0)

    threading.Timer(0.5, _do_exit).start()
    return {"status": "shutting_down"}


@app.post("/api/ocr", response_model=OcrResponse)
async def ocr_endpoint(request: OcrRequest):
    try:
        engine = get_engine(request.backend)
        image_bytes = base64.b64decode(request.image_base64)

        result = await engine.recognize(image_bytes, OcrOptions())

        tokens = result.cost_estimate.tokens_used if result.cost_estimate else 0
        cost = result.cost_estimate.estimated_cost_usd if result.cost_estimate else 0.0
        cost_tracker.check_and_record(
            backend=result.backend,
            tokens_used=tokens,
            cost_usd=cost,
        )

        return OcrResponse(
            latex=result.latex,
            confidence=result.confidence,
            backend=result.backend,
            timing_ms=result.timing_ms,
            cost_estimate=result.cost_estimate.__dict__ if result.cost_estimate else None,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e),
                "retry_after": e.retry_after,
            },
        )
    except ApiKeyError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": "API_KEY_ERROR", "message": str(e)},
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMIT_ERROR", "message": str(e), "retry_after": e.retry_after},
        )
    except NetworkError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "NETWORK_ERROR", "message": str(e)},
        )
    except OcrError as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "OCR_ERROR", "message": str(e)},
        )
    except binascii.Error as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_IMAGE", "message": "Invalid base64 image data"},
        )


@app.get("/api/stats", response_model=StatsResponse)
async def stats_endpoint():
    stats = cost_tracker.get_stats()
    return StatsResponse(
        total_calls=stats.total_calls,
        total_tokens=stats.total_tokens,
        estimated_cost_usd=stats.estimated_cost_usd,
        calls_today=stats.calls_today,
        daily_limit=stats.daily_limit,
        remaining_today=stats.remaining_today,
    )


@app.post("/api/validate-config")
async def validate_config_endpoint(request: ValidateConfigRequest):
    try:
        engine = get_engine(request.backend)
        result = engine.validate_config()
        return {"valid": result.valid, "message": result.message}
    except (OcrError, ValueError) as e:
        return {"valid": False, "message": str(e)}


# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------

# Mapping: frontend backend field → (key_manager service, key_manager key_name)
_KEY_MAPPING: dict[str, tuple[str, str]] = {
    "openai": ("openai", "api_key"),
    "claude": ("claude", "api_key"),
    "gemini": ("gemini", "api_key"),
    "mathpix_app_id": ("mathpix", "app_id"),
    "mathpix_app_key": ("mathpix", "app_key"),
}


@app.post("/api/keys")
async def save_key_endpoint(request: SaveKeyRequest):
    mapping = _KEY_MAPPING.get(request.backend)
    if mapping is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend: {request.backend}",
        )
    service, key_name = mapping
    try:
        key_manager.set_key(service, key_name, request.key)
        return {"status": "ok", "backend": request.backend}
    except Exception as e:
        logger.error("Failed to save key for %s: %s", request.backend, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/keys", response_model=KeysResponse)
async def list_keys_endpoint():
    results: list[KeyStatusItem] = []
    for backend, (service, key_name) in _KEY_MAPPING.items():
        value = key_manager.get_key(service, key_name)
        results.append(KeyStatusItem(backend=backend, configured=value is not None))
    return KeysResponse(keys=results)
