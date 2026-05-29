"""Tests for LLM response parser and LaTeX validator.

Covers:
- Markdown code block cleaning (```latex ... ```)
- Explanatory text stripping (LLM chatty output)
- Dangerous command detection (\\input, \\write, \\exec, \\immediate)
- Empty / whitespace-only response handling
- Long response warnings
- LaTeX bracket matching: {}, [], ()
- Math mode delimiter pairing: $...$, $$...$$, \\(...\\), \\[...\\]
"""

import pytest

from sidecar.ocr_engines.response_parser import (
    clean_llm_response,
    validate_latex,
    ValidationResult,
    MAX_LATEX_LENGTH,
)


# =========================================================================
# clean_llm_response
# =========================================================================


class TestCleanLLMResponse:
    """Tests for the clean_llm_response function."""

    # --- Markdown code block removal -----------------------------------

    def test_strips_latex_code_block(self):
        raw = "```latex\n\\frac{a}{b}\n```"
        assert clean_llm_response(raw) == "\\frac{a}{b}"

    def test_strips_generic_code_block(self):
        raw = "```\nx^2 + y^2 = z^2\n```"
        assert clean_llm_response(raw) == "x^2 + y^2 = z^2"

    def test_strips_code_block_with_extra_whitespace(self):
        raw = "  ```latex\n  E = mc^2\n  ```  "
        assert clean_llm_response(raw) == "E = mc^2"

    def test_strips_multiple_code_blocks_keeps_first(self):
        raw = "```latex\n\\alpha\n```\nSome text\n```latex\n\\beta\n```"
        result = clean_llm_response(raw)
        assert "\\alpha" in result
        # second block should not be returned as primary content

    # --- Explanatory text stripping ------------------------------------

    def test_strips_leading_explanation(self):
        raw = "The LaTeX for this equation is:\n$$E = mc^2$$"
        result = clean_llm_response(raw)
        assert "$$E = mc^2$$" in result
        assert "The LaTeX" not in result

    def test_strips_trailing_explanation(self):
        raw = "$$E = mc^2$$\n\nThis is Einstein's famous equation."
        result = clean_llm_response(raw)
        assert "$$E = mc^2$$" in result
        assert "Einstein" not in result

    def test_strips_both_leading_and_trailing_text(self):
        raw = "Here is the result:\n\\frac{a}{b}\nHope this helps!"
        result = clean_llm_response(raw)
        assert result == "\\frac{a}{b}"

    def test_preserves_pure_latex_without_explanation(self):
        raw = "\\int_0^1 x^2 \\, dx"
        assert clean_llm_response(raw) == "\\int_0^1 x^2 \\, dx"

    # --- Whitespace handling -------------------------------------------

    def test_strips_surrounding_whitespace(self):
        raw = "   \n  E = mc^2  \n  "
        assert clean_llm_response(raw) == "E = mc^2"

    def test_normalizes_internal_blank_lines(self):
        raw = "\\alpha\n\n\n\n\\beta"
        result = clean_llm_response(raw)
        # should collapse excessive blank lines but keep content
        assert "\\alpha" in result
        assert "\\beta" in result

    # --- Empty / degenerate inputs -------------------------------------

    def test_empty_string_returns_empty(self):
        assert clean_llm_response("") == ""

    def test_whitespace_only_returns_empty(self):
        assert clean_llm_response("   \n\t\n  ") == ""

    def test_code_block_with_empty_content(self):
        raw = "```latex\n\n```"
        result = clean_llm_response(raw)
        assert result == ""

    # --- Idempotency ---------------------------------------------------

    def test_already_clean_latex_unchanged(self):
        latex = "\\sqrt{x^2 + y^2}"
        assert clean_llm_response(latex) == "\\sqrt{x^2 + y^2}"


# =========================================================================
# validate_latex
# =========================================================================


class TestValidateLatex:
    """Tests for the validate_latex function."""

    # --- Basic valid LaTeX ---------------------------------------------

    def test_valid_simple_expression(self):
        result = validate_latex("E = mc^2")
        assert result.valid is True
        assert result.message == ""

    def test_valid_fraction(self):
        result = validate_latex("\\frac{a}{b}")
        assert result.valid is True

    def test_valid_nested_braces(self):
        result = validate_latex("\\frac{a + \\sqrt{b}}{c}")
        assert result.valid is True

    def test_empty_latex_is_valid(self):
        result = validate_latex("")
        assert result.valid is True

    # --- Bracket matching: {} ------------------------------------------

    def test_unmatched_opening_brace(self):
        result = validate_latex("\\frac{a}{b")
        assert result.valid is False
        assert "brace" in result.message.lower() or "{" in result.message

    def test_unmatched_closing_brace(self):
        result = validate_latex("\\frac{a}b}")
        assert result.valid is False

    def test_extra_opening_brace(self):
        result = validate_latex("{a + b")
        assert result.valid is False

    # --- Bracket matching: [] ------------------------------------------

    def test_valid_square_brackets(self):
        result = validate_latex("\\sqrt[3]{x}")
        assert result.valid is True

    def test_unmatched_opening_square_bracket(self):
        result = validate_latex("\\sqrt[3{x}")
        assert result.valid is False

    # --- Bracket matching: () ------------------------------------------

    def test_valid_parentheses(self):
        result = validate_latex("(a + b) \\cdot c")
        assert result.valid is True

    def test_unmatched_opening_parenthesis(self):
        result = validate_latex("(a + b")
        assert result.valid is False

    def test_unmatched_closing_parenthesis(self):
        result = validate_latex("a + b)")
        assert result.valid is False

    # --- Math mode delimiters: $...$ -----------------------------------

    def test_valid_inline_math(self):
        result = validate_latex("$x + y$")
        assert result.valid is True

    def test_valid_display_math(self):
        result = validate_latex("$$\\int_0^1 x^2 dx$$")
        assert result.valid is True

    def test_unclosed_single_dollar(self):
        result = validate_latex("$x + y")
        assert result.valid is False
        assert "dollar" in result.message.lower() or "$" in result.message

    def test_unclosed_double_dollar(self):
        result = validate_latex("$$x + y$")
        assert result.valid is False

    # --- Math mode delimiters: \(...\) and \[...\] ---------------------

    def test_valid_paren_delimiters(self):
        result = validate_latex("\\(x + y\\)")
        assert result.valid is True

    def test_valid_bracket_delimiters(self):
        result = validate_latex("\\[x + y\\]")
        assert result.valid is True

    def test_unclosed_paren_delimiter(self):
        result = validate_latex("\\(x + y")
        assert result.valid is False
        assert "paren" in result.message.lower() or "\\(" in result.message

    def test_unclosed_bracket_delimiter(self):
        result = validate_latex("\\[x + y")
        assert result.valid is False

    # --- Dangerous command detection -----------------------------------

    def test_detects_input_command(self):
        result = validate_latex("\\input{malicious}")
        assert result.valid is False
        assert "dangerous" in result.message.lower() or "input" in result.message.lower()

    def test_detects_write_command(self):
        result = validate_latex("\\write18{rm -rf /}")
        assert result.valid is False
        assert "dangerous" in result.message.lower() or "write" in result.message.lower()

    def test_detects_exec_command(self):
        result = validate_latex("\\exec{system}")
        assert result.valid is False

    def test_detects_immediate_command(self):
        result = validate_latex("\\immediate\\write18{ls}")
        assert result.valid is False
        assert "dangerous" in result.message.lower() or "immediate" in result.message.lower()

    def test_detects_dangerous_in_nested_context(self):
        """Dangerous commands should be detected even inside braces."""
        result = validate_latex("{\\input{/etc/passwd}}")
        assert result.valid is False

    def test_safe_commands_are_not_flagged(self):
        """Common safe LaTeX commands should pass."""
        result = validate_latex("\\frac{a}{b} + \\sqrt{x} + \\alpha")
        assert result.valid is True

    # --- Edge cases: escaped braces ------------------------------------

    def test_escaped_braces_counted_correctly(self):
        """\\{ and \\} should not count as bracket delimiters."""
        result = validate_latex("\\{a\\}")
        assert result.valid is True


# =========================================================================
# ValidationResult dataclass
# =========================================================================


class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_has_valid_field(self):
        result = validate_latex("ok")
        assert hasattr(result, "valid")

    def test_has_message_field(self):
        result = validate_latex("ok")
        assert hasattr(result, "message")

    def test_valid_result_message_is_empty(self):
        result = validate_latex("x")
        assert result.message == ""

    def test_invalid_result_has_nonempty_message(self):
        result = validate_latex("\\input{bad}")
        assert len(result.message) > 0


# =========================================================================
# Long response warning
# =========================================================================


class TestLongResponseWarning:
    """Tests for long response handling."""

    def test_long_response_warns(self):
        """A response exceeding MAX_LATEX_LENGTH should produce an invalid result with a warning."""
        long_latex = "x" * (MAX_LATEX_LENGTH + 1)
        result = validate_latex(long_latex)
        assert result.valid is False
        assert "long" in result.message.lower() or "length" in result.message.lower() or "超" in result.message

    def test_response_at_limit_passes_length_check(self):
        """A response exactly at the limit should not trigger the length warning."""
        latex_at_limit = "x" * MAX_LATEX_LENGTH
        result = validate_latex(latex_at_limit)
        # Should not fail due to length (may fail for other reasons, but not length)
        if not result.valid:
            assert "long" not in result.message.lower() and "length" not in result.message.lower()

    def test_short_response_no_length_warning(self):
        result = validate_latex("x + y")
        assert result.valid is True
