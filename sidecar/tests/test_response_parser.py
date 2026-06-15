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


from sidecar.ocr_engines.response_parser import (
    MAX_LATEX_LENGTH,
    clean_llm_response,
    validate_latex,
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
        assert any(
            keyword in result.message.lower()
            for keyword in ["long", "length", "超"]
        )

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


# =========================================================================
# Edge-case tests
# =========================================================================


class TestEdgeCases:
    """Edge-case coverage for validate_latex and clean_llm_response."""

    # --- 1. Dangerous commands: each rejected individually ----------------

    def test_dangerous_commands(self):
        """Every dangerous command variant is individually rejected."""
        dangerous_inputs = [
            ("\\input{file}", "input"),
            ("\\write18{ls}", "write"),
            ("\\exec{code}", "exec"),
            ("\\immediate\\write18{cmd}", "immediate"),
            # Boundary: command at end of string
            ("x + \\input{f}", "input"),
            # Boundary: command followed by digit (not letter)
            ("\\write18", "write"),
        ]
        for latex, label in dangerous_inputs:
            result = validate_latex(latex)
            assert result.valid is False, f"Expected rejection for '{label}': {latex}"
            assert "dangerous" in result.message.lower() or label in result.message.lower()

    def test_shell_escape_not_in_blocklist(self):
        """\\shellescape is NOT in the current dangerous-command regex.

        This test documents the current behavior — if \\shellescape should
        be blocked, update _DANGEROUS_COMMANDS in response_parser.py.
        """
        result = validate_latex("\\shellescape{cmd}")
        # Currently passes because \shellescape is not in the regex
        assert result.valid is True

    # --- 2. Unmatched brackets: various combos ---------------------------

    def test_unmatched_brackets(self):
        """Various unbalanced bracket combinations are rejected."""
        cases = [
            ("{a + b", "open brace"),
            ("a + b}", "close brace"),
            ("[a + b", "open bracket"),
            ("a + b]", "close bracket"),
            ("(a + b", "open paren"),
            ("a + b)", "close paren"),
            # Mismatched pairs
            ("{a + b]", "brace closed by bracket"),
            ("[a + b}", "bracket closed by brace"),
            ("(a + b}", "paren closed by brace"),
            ("{a + b)", "brace closed by paren"),
        ]
        for latex, label in cases:
            result = validate_latex(latex)
            assert result.valid is False, f"Expected rejection for '{label}': {latex}"

    # --- 3. Deeply nested brackets (up to 50 levels) --------------------

    def test_nested_brackets_deep(self):
        """50 levels of nested braces should validate correctly."""
        depth = 50
        nested = "{" * depth + "x" + "}" * depth
        result = validate_latex(nested)
        assert result.valid is True

    def test_nested_brackets_deep_unbalanced(self):
        """50 opens + 49 closes = one unmatched brace → rejected."""
        depth = 50
        nested = "{" * depth + "x" + "}" * (depth - 1)
        result = validate_latex(nested)
        assert result.valid is False

    def test_nested_mixed_bracket_types(self):
        """Mixed bracket nesting: { [ ( x ) ] } should pass."""
        result = validate_latex("{ [ ( x ) ] }")
        assert result.valid is True

    def test_nested_mixed_bracket_mismatch(self):
        """{ [ ( x ) } ] has brace closed by bracket → rejected."""
        result = validate_latex("{ [ ( x ) } ]")
        assert result.valid is False

    # --- 4. Math delimiter imbalance ------------------------------------

    def test_delimiter_imbalance(self):
        """Unmatched $, $$, \\(, \\[ pairs are rejected."""
        cases = [
            ("$x + y", "single open dollar"),
            ("x + y$", "single close dollar"),
            ("$$$x$$", "three dollars (odd)"),
            ("$x$ $y", "two pairs, second unclosed"),
            ("\\(x + y", "open paren delimiter"),
            ("x + y\\)", "close paren delimiter"),
            ("\\[x + y", "open bracket delimiter"),
            ("x + y\\]", "close bracket delimiter"),
        ]
        for latex, label in cases:
            result = validate_latex(latex)
            assert result.valid is False, f"Expected rejection for '{label}': {latex}"

    def test_delimiter_balance_valid_combinations(self):
        """Correctly paired delimiters should pass."""
        cases = [
            "$x$",
            "$$x$$",
            "\\(x\\)",
            "\\[x\\]",
            "$x$ and $y$",
            "$$a$$ and $$b$$",
        ]
        for latex in cases:
            result = validate_latex(latex)
            assert result.valid is True, f"Expected valid: {latex}"

    # --- 5. Extremely long input (>10KB) --------------------------------

    def test_extremely_long_input(self):
        """A 10KB+ LaTeX string should be rejected by the length check."""
        # Build a realistic long LaTeX expression: repeated \frac{a}{b} + ...
        chunk = "\\frac{a}{b} + "
        # Each chunk ~15 chars → need ~700 chunks for >10_000 chars
        repeats = (MAX_LATEX_LENGTH // len(chunk)) + 10
        long_latex = chunk * repeats
        assert len(long_latex) > MAX_LATEX_LENGTH

        result = validate_latex(long_latex)
        assert result.valid is False
        assert "long" in result.message.lower() or "length" in result.message.lower()

    def test_long_valid_latex_at_boundary(self):
        """Exactly MAX_LATEX_LENGTH chars of valid LaTeX should pass length check."""
        # Use a simple repeating pattern that is structurally valid
        # "x + " is 4 chars each → 2500 repeats = 10_000 chars
        latex = "x + " * (MAX_LATEX_LENGTH // 4)
        assert len(latex) == MAX_LATEX_LENGTH

        result = validate_latex(latex)
        # Should not fail due to length (bracket/delimiter checks pass too)
        assert result.valid is True

    # --- 6. Unicode / math symbols --------------------------------------

    def test_unicode_math_symbols(self):
        """Greek letters, integrals, sums, and other Unicode math symbols."""
        cases = [
            "\\alpha + \\beta = \\gamma",
            "\\int_{0}^{\\infty} e^{-x} \\, dx",
            "\\sum_{i=1}^{n} x_i^2",
            "\\prod_{k=1}^{n} \\frac{1}{k}",
            "\\partial f / \\partial x",
            "\\nabla \\cdot \\vec{F}",
            "\\forall x \\in \\mathbb{R}",
            "\\exists y : y > 0",
            "\\lim_{x \\to 0} \\frac{\\sin x}{x}",
            "\\lambda \\otimes \\mu \\oplus \\nu",
        ]
        for latex in cases:
            result = validate_latex(latex)
            assert result.valid is True, f"Expected valid for unicode math: {latex}"

    def test_unicode_in_clean_response(self):
        """clean_llm_response should preserve Unicode math symbols."""
        raw = "```latex\n\\alpha + \\beta\\n```"
        result = clean_llm_response(raw)
        assert "\\alpha" in result
        assert "\\beta" in result

    # --- 7. Empty and whitespace-only inputs -----------------------------

    def test_empty_and_whitespace(self):
        """Empty string, spaces-only, and tabs-only should all clean to empty."""
        cases = [
            "",
            "   ",
            "\t\t\t",
            "\n\n\n",
            "  \t \n  ",
            "\r\n",
        ]
        for raw in cases:
            result = clean_llm_response(raw)
            assert result == "", f"Expected empty for {raw!r}, got {result!r}"

    def test_empty_latex_validates(self):
        """Empty string is structurally valid (no brackets/delimiters to mismatch)."""
        result = validate_latex("")
        assert result.valid is True

    # --- 8. Mixed dangerous + valid content ------------------------------

    def test_mixed_dangerous_and_valid(self):
        """A valid-looking formula with a dangerous command embedded is rejected."""
        cases = [
            # Dangerous command buried in valid expression
            "\\frac{a}{b} + \\input{malicious} + \\sqrt{x}",
            # Valid preamble, dangerous at end
            "\\alpha + \\beta \\write18{rm}",
            # Dangerous in subscript
            "\\sum_{\\exec{cmd}}^{n} x_i",
        ]
        for latex in cases:
            result = validate_latex(latex)
            assert result.valid is False, f"Expected rejection for mixed input: {latex}"
