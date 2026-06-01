# AGENTS.md — sidecar/tests

> Part of FormulaSnap project.

## Overview
Tests for OCR sidecar: engine implementations, manager routing, FastAPI endpoints, response parsing.

## Structure (9 files)
- `test_interface.py` — Dataclass + error hierarchy contract
- `test_manager.py` — EngineManager routing, circuit breaker, fallback (436 lines, largest)
- `test_server.py` — FastAPI TestClient endpoint tests
- `test_cost_tracker.py` — Rate limiting + KeyManager CRUD
- `test_response_parser.py` — LaTeX validation, markdown cleaning, dangerous command detection
- `test_claude.py` — ClaudeVision engine
- `test_gemini.py` — Gemini engine
- `test_pix2text.py` — Pix2Text engine (local OCR)
- `test_mathpix.py` — Mathpix HTTP API engine
- `test_llm_base.py` — OpenAI engine

## Conventions
- `setup_method(self)` — per-test setup, no fixtures
- `_make_*` helpers for test data factories
- `_mock_*` helpers for building fake API responses
- `@patch("sidecar.ocr_engines.xxx_engine.yyy")` decorator-style mocking
- Patch module-level variables, not imports
- `pytest.raises(ExceptionType, match="pattern")` for error assertions

## Anti-patterns
- Don't use pytest fixtures — use `setup_method`
- Don't import symbols to mock — patch module-level variables
- No `as any` or `cast` — use proper type assertions

## Running
```bash
pytest                                    # All tests (pytest.ini points here)
pytest sidecar/tests/test_manager.py -v   # Single file
pytest -k "test_name" -v                  # Single test
```
- 30s timeout per test (configured in pytest.ini)
- Tests use `_make_image()` for fixture data
