"""LLM response parser and LaTeX validator.

Parses raw LLM responses to extract clean LaTeX, and validates
the LaTeX for structural correctness and safety.

Usage:
    from sidecar.ocr_engines.response_parser import (
        clean_llm_response,
        validate_latex,
        ValidationResult,
    )

    cleaned = clean_llm_response(raw_llm_output)
    result = validate_latex(cleaned)
    if result.valid:
        use(cleaned)
    else:
        log(result.message)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_LATEX_LENGTH: int = 10_000
"""Maximum allowed LaTeX string length. Responses beyond this are rejected."""

_DANGEROUS_COMMANDS = re.compile(
    r"\\(?:input|write|exec|immediate)(?![a-zA-Z])"
)
"""Regex matching TeX commands that can execute system code.

Uses a negative lookahead instead of \\b because TeX commands like
\\write18 are followed by digits (which \\b considers word chars).
"""

# Matches ``` optionally prefixed by language tag (latex, tex, etc.)
_CODE_BLOCK_RE = re.compile(
    r"```(?:latex|tex)?\s*\n(.*?)\n\s*```",
    re.DOTALL | re.IGNORECASE,
)

# A line is "LaTeX-like" if it contains common LaTeX markers.
_LATEX_LINE_RE = re.compile(
    r"(?:\\[a-zA-Z]+|[${}\\^_&])"
)

# Collapse runs of 3+ newlines down to 2
_NEWLINE_RUNS_RE = re.compile(r"\n{3,}")

# Remove escaped braces/brackets/parens before bracket matching
_ESCAPED_BRACKET_RE = re.compile(r"\\[{}()\[\]]")

# Math mode delimiter pairs (open -> close)
_MATH_DELIMITERS = [
    ("$$", "$$"),
    ("\\(", "\\)"),
    ("\\[", "\\]"),
    ("$", "$"),
]


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of LaTeX validation.

    Attributes:
        valid: Whether the LaTeX is structurally valid and safe.
        message: Human-readable message; empty string when valid.
    """

    valid: bool
    message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clean_llm_response(raw: str) -> str:
    """Clean a raw LLM response into pure LaTeX.

    Processing steps:
    1. Extract content from markdown code blocks (```latex ... ```).
    2. Strip explanatory / chatty text surrounding the LaTeX.
    3. Collapse excessive blank lines.
    4. Strip leading/trailing whitespace.

    Args:
        raw: The raw string returned by an LLM.

    Returns:
        Cleaned LaTeX string (may be empty).
    """
    if not raw or not raw.strip():
        return ""

    text = raw.strip()

    # --- Step 1: Extract from markdown code block if present ----------
    code_match = _CODE_BLOCK_RE.search(text)
    if code_match:
        text = code_match.group(1).strip()
        if not text:
            return ""
        return _post_clean(text)

    # --- Step 2: Strip explanatory text --------------------------------
    text = _strip_explanatory_text(text)

    return _post_clean(text)


def validate_latex(latex: str) -> ValidationResult:
    """Validate LaTeX for structural correctness and safety.

    Checks performed (in order):
    1. Length limit.
    2. Dangerous command detection.
    3. Bracket / brace matching: {}, [], ().
    4. Math-mode delimiter pairing: $, $$, \\( \\), \\[ \\].

    This function does **not** auto-correct errors.

    Args:
        latex: The LaTeX string to validate.

    Returns:
        ValidationResult with ``valid=True`` if safe and well-formed.
    """
    # --- Length check ---------------------------------------------------
    if len(latex) > MAX_LATEX_LENGTH:
        return ValidationResult(
            valid=False,
            message=f"LaTeX response too long ({len(latex)} chars, max {MAX_LATEX_LENGTH})",
        )

    # --- Dangerous command check ----------------------------------------
    danger = _check_dangerous_commands(latex)
    if danger is not None:
        return danger

    # --- Bracket matching -----------------------------------------------
    bracket = _check_bracket_matching(latex)
    if bracket is not None:
        return bracket

    # --- Math-mode delimiter pairing ------------------------------------
    delimiter = _check_math_delimiters(latex)
    if delimiter is not None:
        return delimiter

    return ValidationResult(valid=True, message="")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _post_clean(text: str) -> str:
    """Collapse blank lines and strip surrounding whitespace."""
    text = _NEWLINE_RUNS_RE.sub("\n\n", text)
    return text.strip()


def _strip_explanatory_text(text: str) -> str:
    """Remove leading and trailing non-LaTeX explanation lines.

    Strategy:
    - Walk lines from the top; drop lines that are clearly English prose.
    - Walk lines from the bottom; same.
    - Keep at least one line if everything looks like prose
      (the caller may have a valid single-line expression).
    """
    lines = text.split("\n")
    if not lines:
        return text

    # Find first LaTeX-like line
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_latex_like(stripped):
            start = i
            break
    else:
        # No LaTeX-like line found; return as-is (could be "x + y")
        return text

    # Find last LaTeX-like line
    end = len(lines) - 1
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if _is_latex_like(stripped):
            end = i
            break

    result_lines = lines[start : end + 1]
    return "\n".join(result_lines)


def _is_latex_like(line: str) -> bool:
    """Heuristic: does this line look like it contains LaTeX?"""
    if not line:
        return False
    return bool(_LATEX_LINE_RE.search(line))


def _check_dangerous_commands(latex: str) -> ValidationResult | None:
    """Return ValidationResult(valid=False) if a dangerous command is found."""
    match = _DANGEROUS_COMMANDS.search(latex)
    if match:
        cmd = match.group(0)
        return ValidationResult(
            valid=False,
            message=f"Dangerous LaTeX command detected: {cmd}",
        )
    return None


def _check_bracket_matching(latex: str) -> ValidationResult | None:
    """Check that {}, [], () are properly matched.

    Respects LaTeX escape: \\{ and \\} are literal, not delimiters.
    """
    # Remove escaped braces/brackets/parens so they don't interfere
    sanitized = _ESCAPED_BRACKET_RE.sub("", latex)

    stack: list[tuple[str, int]] = []
    pairs = {"{": "}", "[": "]", "(": ")"}

    for ch in sanitized:
        if ch in pairs:
            stack.append((ch, 0))
        elif ch in pairs.values():
            if not stack:
                return ValidationResult(
                    valid=False,
                    message=f"Unmatched closing '{ch}'",
                )
            open_ch, _ = stack.pop()
            if pairs[open_ch] != ch:
                return ValidationResult(
                    valid=False,
                    message=f"Mismatched brackets: '{open_ch}' closed by '{ch}'",
                )

    if stack:
        open_ch, _ = stack[-1]
        return ValidationResult(
            valid=False,
            message=f"Unmatched opening '{open_ch}'",
        )

    return None


def _check_math_delimiters(latex: str) -> ValidationResult | None:
    """Check that math-mode delimiters are properly paired.

    Order matters: $$ before $, \\( before ( alone.

    When open == close (e.g. ``$`` or ``$$``), occurrences are counted
    and the total must be even (paired).
    """
    for open_d, close_d in _MATH_DELIMITERS:
        same = open_d == close_d
        count = 0
        i = 0
        while i < len(latex):
            if latex[i : i + len(open_d)] == open_d:
                count += 1
                i += len(open_d)
            elif not same and latex[i : i + len(close_d)] == close_d:
                count -= 1
                if count < 0:
                    return ValidationResult(
                        valid=False,
                        message=f"Unmatched closing math delimiter '{close_d}'",
                    )
                i += len(close_d)
            else:
                i += 1

        if same:
            if count % 2 != 0:
                return ValidationResult(
                    valid=False,
                    message=f"Unclosed math delimiter '{open_d}'",
                )
        else:
            if count != 0:
                return ValidationResult(
                    valid=False,
                    message=f"Unclosed math delimiter '{open_d}'",
                )

    return None
