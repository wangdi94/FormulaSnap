from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import base64

from sidecar.ocr_engines.interface import (
    OcrBackend, OcrOptions, OcrError,
    ApiKeyError, RateLimitError, NetworkError,
)
from sidecar.ocr_engines.cost_tracker import cost_tracker, RateLimitExceeded

app = FastAPI(title="FormulaSnap Sidecar")

# CORS for localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OcrRequest(BaseModel):
    image_base64: str
    backend: str = "pix2text"


class OcrResponse(BaseModel):
    latex: str
    confidence: float
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


# ---------------------------------------------------------------------------
# Engine registry & stats
# ---------------------------------------------------------------------------

_engines: dict[str, OcrBackend] = {}
_stats: dict = {"total_calls": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}


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


@app.post("/api/ocr", response_model=OcrResponse)
async def ocr_endpoint(request: OcrRequest):
    try:
        cost_tracker.check_rate_limit()

        engine = get_engine(request.backend)
        image_bytes = base64.b64decode(request.image_base64)
        result = await engine.recognize(image_bytes, OcrOptions())

        tokens = result.cost_estimate.tokens_used if result.cost_estimate else 0
        cost = result.cost_estimate.estimated_cost_usd if result.cost_estimate else 0.0
        cost_tracker.record_call(
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
    except Exception as e:
        return {"valid": False, "message": str(e)}
