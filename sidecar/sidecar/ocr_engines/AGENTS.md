# AGENTS.md — OCR Engines

> Part of FormulaSnap project.

## Architecture

Protocol-based design. `OcrBackend` in `interface.py` is a `typing.Protocol` (structural subtyping, duck typing). Engines never inherit from it explicitly. Just implement the 4 methods: `recognize()`, `estimate_cost()`, `validate_config()`, `get_rate_limit_status()`.

5 dataclasses (`OcrResult`, `CostEstimate`, `OcrOptions`, `RateLimitStatus`, `ValidationResult`) and 5 error types (`OcrError` base, `ApiKeyError`, `RateLimitError`, `NetworkError`, `ParseError`). All errors inherit `OcrError` for single-catch convenience.

## Engine Manager

`manager.py` has three responsibilities:

1. **Circuit breaker** per engine. 3 consecutive failures → engine disabled for 60s → auto-recovery via HALF_OPEN state. Thread-safe (`threading.Lock`).
2. **Cost-aware routing**. `backend="auto"` estimates all engines, sorts cheapest first (free = Pix2Text at cost 0), tries in order.
3. **Fallback chain**: `gemini → openai → claude → mathpix → pix2text`. Pix2Text is the ultimate fallback (local, free, never fails conceptually).

`_FALLBACK_CHAIN` tuple defines the tiebreaker order when costs are equal.

## LLM Engines

`llm_base.py` provides `LlmProvider` base class. Three engines inherit it: `OpenAIEngine`, `ClaudeEngine`, `GeminiEngine`. All share:
- `SYSTEM_PROMPT` (LaTeX-only transcription)
- `_parse_response()` (strip markdown fences)
- `_estimate_tokens()` (765 tokens per vision image)

Each LLM engine maps SDK-specific exceptions to our error types (`_AuthenticationError → ApiKeyError`, etc.).

## Engine Implementation Pattern

Every engine file follows this structure:

```python
# 1. Optional import guard
try:
    import some_sdk
    SOME_AVAILABLE = True
    _SdkError = some_sdk.SomeError
except ImportError:
    some_sdk = None
    SOME_AVAILABLE = False
    _SdkError = Exception

# 2. Module-level variables for @patch compatibility
# Tests use: @patch("sidecar.ocr_engines.xxx_engine.some_sdk")

# 3. Engine class implements OcrBackend (duck typing, no inheritance)
class SomeEngine:
    def recognize(self, image: bytes, options: OcrOptions) -> OcrResult: ...
```

Exception: LLM engines inherit `LlmProvider` for shared prompt/parsing.

## Supporting Modules

- `cost_tracker.py`: `CostTracker` with rate limiting (100 calls/day, 2s min interval), call recording, stats. Module-level singleton `cost_tracker`.
- `key_manager.py`: Cross-platform API key storage. Cascade: keyring (OS-native) → file backend (JSON, 0o600 perms) → env vars. Module-level singleton `key_manager`. `_mask_key()` for safe logging.
- `response_parser.py`: `clean_llm_response()` strips markdown/explanatory text. `validate_latex()` checks length, dangerous commands (`\input`, `\write`, `\exec`), bracket matching, math delimiter pairing.

## Known Issues

- Manager's broad `except Exception` in `_auto_recognize` is acceptable for fallback but masks root causes. Use specific engine exceptions when possible.

## Testing Conventions

- 11 test files in `sidecar/tests/`
- `setup_method(self)` not fixtures
- `_make_*` helper factory functions in test files
- `@patch("sidecar.ocr_engines.xxx_engine.yyy")` decorator-style mocking
- Module-level variables (not imports) are the patch targets

## Module Exports

`__init__.py` re-exports interface types + `MathpixEngine`, `CostTracker`, `cost_tracker`, `KeyManager`, `key_manager`. Other engines are imported directly from their modules.
