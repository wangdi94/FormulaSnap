# AGENTS.md — sidecar/sidecar (FastAPI Server)

> Part of FormulaSnap project.

## Architecture

FastAPI app on `127.0.0.1:8477`. Entry: `main.py` → `uvicorn.run()`.
4 endpoints: `/health`, `/api/ocr`, `/api/stats`, `/api/validate-config`.
CORS middleware allows localhost:1420 and tauri://localhost.

## Engine Registration

`server.py` defines `register_engine()` and `_engines` dict for `/api/ocr`. **Called by `main.py` at startup** via `_register_engines()` — registers all 5 engines.

Real engine logic lives in `EngineManager` (ocr_engines/manager.py), which has its own `_build_default_engines()`. These two registries are **separate** but both wired.

Tests bypass this by `@patch("sidecar.api.server.get_engine")`.

Frontend uses `lib/sidecarClient.ts` which calls the sidecar HTTP API directly.

## Where to Look

| File | Purpose |
|------|---------|
| `main.py` | Entry point, uvicorn config |
| `api/server.py` | FastAPI app, routes, CORS |
| `api/__init__.py` | Empty |
| `__init__.py` | Module docstring only |
| `ocr_engines/` | Engine implementations (separate AGENTS.md) |

## Anti-Patterns

- Don't add new endpoints to `server.py` without wiring engines — `register_engine()` path must be called from `main.py`
- Don't use `print()` for logging — `cost_tracker.py:92` has debug `print()` (use `logging` module)
- `server.py:158` uses broad `except Exception` — catch specific engine exceptions instead
