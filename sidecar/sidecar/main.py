import logging
import multiprocessing
import os

import uvicorn

from sidecar.api.server import app, register_engine
from sidecar.logging_config import setup_logging
from sidecar.ocr_engines.key_manager import key_manager


def _register_engines():
    """Register OCR engines based on available API keys.

    Pix2Text is always registered (local engine, no key needed).
    Other engines are only registered if their API keys are configured.
    """
    from sidecar.ocr_engines.pix2text_engine import Pix2TextEngine

    registered: list[str] = []

    register_engine("pix2text", Pix2TextEngine())
    registered.append("pix2text")

    mathpix_app_id = key_manager.get_key("mathpix", "app_id")
    mathpix_app_key = key_manager.get_key("mathpix", "app_key")
    if mathpix_app_id and mathpix_app_key:
        from sidecar.ocr_engines.mathpix_engine import MathpixEngine

        register_engine("mathpix", MathpixEngine())
        registered.append("mathpix")

    if key_manager.get_key("openai", "api_key"):
        from sidecar.ocr_engines.openai_engine import OpenAIEngine

        register_engine("openai", OpenAIEngine())
        registered.append("openai")

    if key_manager.get_key("claude", "api_key"):
        from sidecar.ocr_engines.claude_engine import ClaudeEngine

        register_engine("claude", ClaudeEngine())
        registered.append("claude")

    if key_manager.get_key("gemini", "api_key"):
        from sidecar.ocr_engines.gemini_engine import GeminiEngine

        register_engine("gemini", GeminiEngine())
        registered.append("gemini")

    return registered


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting FormulaSnap sidecar...")
    registered = _register_engines()
    logger.info("Registered OCR engines: %s", ", ".join(registered))
    # Prevent uvicorn from overriding our custom logging config
    reload_enabled = os.environ.get("FORMULASNAP_SIDECAR_RELOAD", "").lower() == "true"
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8477,
        log_config=None,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
