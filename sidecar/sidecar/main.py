import logging

import uvicorn
from sidecar.api.server import app, register_engine
from sidecar.logging_config import setup_logging


def _register_engines():
    from sidecar.ocr_engines.pix2text_engine import Pix2TextEngine
    from sidecar.ocr_engines.mathpix_engine import MathpixEngine
    from sidecar.ocr_engines.openai_engine import OpenAIEngine
    from sidecar.ocr_engines.claude_engine import ClaudeEngine
    from sidecar.ocr_engines.gemini_engine import GeminiEngine

    register_engine("pix2text", Pix2TextEngine())
    register_engine("mathpix", MathpixEngine())
    register_engine("openai", OpenAIEngine())
    register_engine("claude", ClaudeEngine())
    register_engine("gemini", GeminiEngine())


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting FormulaSnap sidecar...")
    _register_engines()
    logger.info("Registered OCR engines: pix2text, mathpix, openai, claude, gemini")
    uvicorn.run(app, host="127.0.0.1", port=8477)


if __name__ == "__main__":
    main()
