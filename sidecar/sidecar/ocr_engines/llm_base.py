"""LLM-based OCR provider base class.

Provides shared utilities for LLM-based OCR engines:
- System prompt for LaTeX-only transcription
- Response parsing (strip markdown blocks)
- Token estimation
"""

from __future__ import annotations

import re
from typing import Optional


SYSTEM_PROMPT = (
    "You are a LaTeX OCR engine. Extract ALL mathematical formulas and text "
    "from the image. Return ONLY valid LaTeX code. Use $...$ for inline math "
    "and $$...$$ for display math. Do NOT include explanations, markdown code "
    "blocks, or commentary."
)


class LlmProvider:
    """Base class for LLM-based OCR providers.

    Subclasses (OpenAI, Claude, Gemini) inherit shared prompt construction,
    response parsing, and token estimation logic.
    """

    def _build_ocr_prompt(self) -> str:
        """Return the system prompt for LaTeX-only transcription."""
        return SYSTEM_PROMPT

    def _parse_response(self, raw: str) -> str:
        """Clean LLM response to extract pure LaTeX.

        Strips markdown code fences and surrounding whitespace.
        """
        # Remove opening markdown code block (```latex or just ```)
        cleaned = re.sub(r"```(?:latex)?\s*\n?", "", raw)
        # Remove closing code fence
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE)
        # Strip leading/trailing whitespace
        cleaned = cleaned.strip()
        return cleaned

    def _estimate_tokens(self, image: bytes) -> int:
        """Rough token estimate for a vision model image input.

        Vision models encode images as ~765 tokens (OpenAI reference).
        """
        return 765
