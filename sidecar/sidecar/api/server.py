import asyncio
import base64
import binascii
import logging
import os
import signal
import threading
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sidecar.cache import OcrCache, ocr_cache
from sidecar.ocr_engines.cost_tracker import RateLimitExceededError, cost_tracker
from sidecar.ocr_engines.interface import (
    ApiKeyError,
    NetworkError,
    OcrBackend,
    OcrError,
    OcrOptions,
    RateLimitError,
)
from sidecar.ocr_engines.key_manager import key_manager

logger = logging.getLogger(__name__)


_SHUTDOWN_TIMEOUT = 10.0  # seconds per engine aclose()
_SHUTDOWN_TOKEN: str = os.environ.get("FORMULASNAP_SHUTDOWN_TOKEN", "") or str(uuid.uuid4())
logger.info("Shutdown token: %s", _SHUTDOWN_TOKEN)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    logger.info("Shutting down: closing OCR engines...")
    for name, engine in _engines.items():
        aclose_fn = getattr(engine, "aclose", None)
        if aclose_fn is None:
            continue
        try:
            await asyncio.wait_for(aclose_fn(), timeout=_SHUTDOWN_TIMEOUT)
            logger.info("Closed engine: %s", name)
        except TimeoutError:
            logger.warning("Timeout closing engine %s after %.1fs", name, _SHUTDOWN_TIMEOUT)
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
# Request logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    if path == "/health":
        return await call_next(request)

    start = time.time()
    response: Response = await call_next(request)
    elapsed_ms = round((time.time() - start) * 1000)
    logger.info(
        "%s %s -> %d [%dms]",
        request.method,
        path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OcrRequest(BaseModel):
    image_base64: str = Field(..., max_length=20_000_000)
    backend: str = "pix2text"


class OcrResponse(BaseModel):
    latex: str
    confidence: float | None = None
    backend: str
    timing_ms: int
    cost_estimate: dict | None = None


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


class ShutdownRequest(BaseModel):
    token: str = ""


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


def get_registered_engines() -> list[str]:
    """Return list of currently registered engine names."""
    return list(_engines.keys())


def validate_image(image_bytes: bytes) -> None:
    """Validate decoded image bytes before passing to OCR engine."""
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": "EMPTY_IMAGE", "message": "Empty image data"},
        )
    if len(image_bytes) > 15_000_000:
        raise HTTPException(
            status_code=413,
            detail={"error": "IMAGE_TOO_LARGE", "message": "Image too large (max 15MB)"},
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "engines": list(_engines.keys())}


@app.post("/shutdown")
async def shutdown(request: Request, body: ShutdownRequest = ShutdownRequest()):
    """优雅关闭端点：需要 token 认证，返回 200 后通过信号触发 uvicorn graceful shutdown。"""
    # Token 可来自请求体或 X-Shutdown-Token 头
    token = body.token or request.headers.get("X-Shutdown-Token", "")
    if token != _SHUTDOWN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid shutdown token")
    logger.info("收到 shutdown 请求，准备退出...")

    # 使用定时器延迟发送信号，确保 HTTP 响应先发送完成
    def _do_signal():
        logger.info("发送 SIGTERM 信号触发 graceful shutdown")
        signal.raise_signal(signal.SIGTERM)

    threading.Timer(0.5, _do_signal).start()
    return {"status": "shutting_down"}


@app.post("/api/ocr", response_model=OcrResponse)
async def ocr_endpoint(request: OcrRequest):
    try:
        image_bytes = base64.b64decode(request.image_base64)
        validate_image(image_bytes)

        cache_key = f"{OcrCache.hash_bytes(image_bytes)}:{request.backend}"
        cached = ocr_cache.get(cache_key)
        if cached is not None:
            return OcrResponse(
                latex=cached.latex,
                confidence=cached.confidence,
                backend=cached.backend,
                timing_ms=cached.timing_ms,
                cost_estimate=cached.cost_estimate.__dict__ if cached.cost_estimate else None,
            )

        engine = get_engine(request.backend)

        # Pre-call rate limit check — prevents API calls when over limit
        cost_tracker.check_limit_only()

        result = await asyncio.wait_for(
            engine.recognize(image_bytes, OcrOptions()), timeout=120
        )

        tokens = result.cost_estimate.tokens_used if result.cost_estimate else 0
        cost = result.cost_estimate.estimated_cost_usd if result.cost_estimate else 0.0
        cost_tracker.record_call(
            backend=result.backend,
            tokens_used=tokens,
            cost_usd=cost,
        )

        ocr_cache.set(cache_key, result)

        return OcrResponse(
            latex=result.latex,
            confidence=result.confidence,
            backend=result.backend,
            timing_ms=result.timing_ms,
            cost_estimate=result.cost_estimate.__dict__ if result.cost_estimate else None,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"error": "TIMEOUT", "message": "OCR request timed out after 120s"},
        )
    except RateLimitExceededError as e:
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
    except binascii.Error:
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


@app.get("/api/engines/status")
async def engines_status_endpoint():
    """Return status of registered OCR engines."""
    registered = list(_engines.keys())
    return {"registered": registered, "count": len(registered)}


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
