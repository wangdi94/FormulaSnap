use regex::Regex;
use std::sync::OnceLock;

use crate::types::OcrError;

const MAX_LATEX_LENGTH: usize = 10_000;

static CODE_BLOCK_RE: OnceLock<Regex> = OnceLock::new();
static LATEX_LINE_RE: OnceLock<Regex> = OnceLock::new();
static NEWLINE_RUNS_RE: OnceLock<Regex> = OnceLock::new();
static ESCAPED_BRACKET_RE: OnceLock<Regex> = OnceLock::new();
static DANGEROUS_COMMANDS_RE: OnceLock<Regex> = OnceLock::new();

fn code_block_re() -> &'static Regex {
    CODE_BLOCK_RE.get_or_init(|| {
        Regex::new(r"(?s)```(?:latex|tex)?\s*\n(.*?)\n\s*```").unwrap()
    })
}

fn latex_line_re() -> &'static Regex {
    LATEX_LINE_RE.get_or_init(|| {
        Regex::new(r"(?:\\[a-zA-Z]+|[${}\\^_&])").unwrap()
    })
}

fn newline_runs_re() -> &'static Regex {
    NEWLINE_RUNS_RE.get_or_init(|| Regex::new(r"\n{3,}").unwrap())
}

fn escaped_bracket_re() -> &'static Regex {
    ESCAPED_BRACKET_RE.get_or_init(|| Regex::new(r"\\[{}()\[\]]").unwrap())
}

fn dangerous_commands_re() -> &'static Regex {
    DANGEROUS_COMMANDS_RE.get_or_init(|| {
        Regex::new(r"\\(?:input|write|exec|immediate)").unwrap()
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationResult {
    pub valid: bool,
    pub message: String,
}

impl ValidationResult {
    fn valid() -> Self {
        Self {
            valid: true,
            message: String::new(),
        }
    }

    fn invalid(message: impl Into<String>) -> Self {
        Self {
            valid: false,
            message: message.into(),
        }
    }
}

pub fn clean_llm_response(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return String::new();
    }

    if let Some(caps) = code_block_re().captures(trimmed) {
        let content = caps.get(1).map_or("", |m| m.as_str()).trim();
        if content.is_empty() {
            return String::new();
        }
        return post_clean(content);
    }

    let text = strip_explanatory_text(trimmed);
    post_clean(&text)
}

pub fn validate_latex(latex: &str) -> Result<(), OcrError> {
    if latex.len() > MAX_LATEX_LENGTH {
        return Err(OcrError::ParseError(format!(
            "LaTeX response too long ({} chars, max {})",
            latex.len(),
            MAX_LATEX_LENGTH
        )));
    }

    if let Some(cmd) = check_dangerous_commands(latex) {
        return Err(OcrError::ParseError(format!(
            "Dangerous LaTeX command detected: {}",
            cmd
        )));
    }

    check_bracket_matching(latex)?;
    check_math_delimiters(latex)?;

    Ok(())
}

fn check_dangerous_commands(latex: &str) -> Option<String> {
    for mat in dangerous_commands_re().find_iter(latex) {
        let end = mat.end();
        let next_char = latex[end..].chars().next();
        match next_char {
            None => return Some(mat.as_str().to_string()),
            Some(c) if !c.is_ascii_alphabetic() => return Some(mat.as_str().to_string()),
            _ => continue,
        }
    }
    None
}

fn post_clean(text: &str) -> String {
    let collapsed = newline_runs_re().replace_all(text, "\n\n");
    collapsed.trim().to_string()
}

fn strip_explanatory_text(text: &str) -> String {
    let lines: Vec<&str> = text.split('\n').collect();
    if lines.is_empty() {
        return text.to_string();
    }

    let mut start = 0;
    let mut found_latex = false;
    for (i, line) in lines.iter().enumerate() {
        let stripped = line.trim();
        if stripped.is_empty() {
            continue;
        }
        if is_latex_like(stripped) {
            start = i;
            found_latex = true;
            break;
        }
    }

    if !found_latex {
        return text.to_string();
    }

    let mut end = lines.len() - 1;
    for i in (0..lines.len()).rev() {
        let stripped = lines[i].trim();
        if stripped.is_empty() {
            continue;
        }
        if is_latex_like(stripped) {
            end = i;
            break;
        }
    }

    lines[start..=end].join("\n")
}

fn is_latex_like(line: &str) -> bool {
    if line.is_empty() {
        return false;
    }
    latex_line_re().is_match(line)
}

fn check_bracket_matching(latex: &str) -> Result<(), OcrError> {
    let sanitized = escaped_bracket_re().replace_all(latex, "");
    let mut stack: Vec<char> = Vec::new();
    let pairs: std::collections::HashMap<char, char> =
        [('{', '}'), ('[', ']'), ('(', ')')].into_iter().collect();

    for ch in sanitized.chars() {
        if pairs.contains_key(&ch) {
            stack.push(ch);
        } else if pairs.values().any(|&v| v == ch) {
            let open = stack.pop().ok_or_else(|| {
                OcrError::ParseError(format!("Unmatched closing '{}'", ch))
            })?;
            if pairs.get(&open) != Some(&ch) {
                return Err(OcrError::ParseError(format!(
                    "Mismatched brackets: '{}' closed by '{}'",
                    open, ch
                )));
            }
        }
    }

    if let Some(&open) = stack.last() {
        return Err(OcrError::ParseError(format!(
            "Unmatched opening '{}'",
            open
        )));
    }

    Ok(())
}

const MATH_DELIMITERS: &[(&str, &str)] = &[
    ("$$", "$$"),
    ("\\(", "\\)"),
    ("\\[", "\\]"),
    ("$", "$"),
];

fn check_math_delimiters(latex: &str) -> Result<(), OcrError> {
    for &(open_d, close_d) in MATH_DELIMITERS {
        let same = open_d == close_d;
        let mut count: i32 = 0;
        let mut i = 0;

        while i < latex.len() {
            if latex[i..].starts_with(open_d) {
                count += 1;
                i += open_d.len();
            } else if !same && latex[i..].starts_with(close_d) {
                count -= 1;
                if count < 0 {
                    return Err(OcrError::ParseError(format!(
                        "Unmatched closing math delimiter '{}'",
                        close_d
                    )));
                }
                i += close_d.len();
            } else {
                i += 1;
            }
        }

        if same {
            if count % 2 != 0 {
                return Err(OcrError::ParseError(format!(
                    "Unclosed math delimiter '{}'",
                    open_d
                )));
            }
        } else if count != 0 {
            return Err(OcrError::ParseError(format!(
                "Unclosed math delimiter '{}'",
                open_d
            )));
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strips_latex_code_block() {
        let raw = "```latex\n\\frac{a}{b}\n```";
        assert_eq!(clean_llm_response(raw), "\\frac{a}{b}");
    }

    #[test]
    fn test_strips_generic_code_block() {
        let raw = "```\nx^2 + y^2 = z^2\n```";
        assert_eq!(clean_llm_response(raw), "x^2 + y^2 = z^2");
    }

    #[test]
    fn test_strips_code_block_with_extra_whitespace() {
        let raw = "  ```latex\n  E = mc^2\n  ```  ";
        assert_eq!(clean_llm_response(raw), "E = mc^2");
    }

    #[test]
    fn test_strips_multiple_code_blocks_keeps_first() {
        let raw = "```latex\n\\alpha\n```\nSome text\n```latex\n\\beta\n```";
        let result = clean_llm_response(raw);
        assert!(result.contains("\\alpha"));
    }

    #[test]
    fn test_strips_leading_explanation() {
        let raw = "The LaTeX for this equation is:\n$$E = mc^2$$";
        let result = clean_llm_response(raw);
        assert!(result.contains("$$E = mc^2$$"));
        assert!(!result.contains("The LaTeX"));
    }

    #[test]
    fn test_strips_trailing_explanation() {
        let raw = "$$E = mc^2$$\n\nThis is Einstein's famous equation.";
        let result = clean_llm_response(raw);
        assert!(result.contains("$$E = mc^2$$"));
        assert!(!result.contains("Einstein"));
    }

    #[test]
    fn test_strips_both_leading_and_trailing_text() {
        let raw = "Here is the result:\n\\frac{a}{b}\nHope this helps!";
        assert_eq!(clean_llm_response(raw), "\\frac{a}{b}");
    }

    #[test]
    fn test_preserves_pure_latex_without_explanation() {
        let raw = "\\int_0^1 x^2 \\, dx";
        assert_eq!(clean_llm_response(raw), "\\int_0^1 x^2 \\, dx");
    }

    #[test]
    fn test_strips_surrounding_whitespace() {
        let raw = "   \n  E = mc^2  \n  ";
        assert_eq!(clean_llm_response(raw), "E = mc^2");
    }

    #[test]
    fn test_normalizes_internal_blank_lines() {
        let raw = "\\alpha\n\n\n\n\\beta";
        let result = clean_llm_response(raw);
        assert!(result.contains("\\alpha"));
        assert!(result.contains("\\beta"));
    }

    #[test]
    fn test_empty_string_returns_empty() {
        assert_eq!(clean_llm_response(""), "");
    }

    #[test]
    fn test_whitespace_only_returns_empty() {
        assert_eq!(clean_llm_response("   \n\t\n  "), "");
    }

    #[test]
    fn test_code_block_with_empty_content() {
        let raw = "```latex\n\n```";
        assert_eq!(clean_llm_response(raw), "");
    }

    #[test]
    fn test_already_clean_latex_unchanged() {
        let latex = "\\sqrt{x^2 + y^2}";
        assert_eq!(clean_llm_response(latex), "\\sqrt{x^2 + y^2}");
    }

    #[test]
    fn test_valid_simple_expression() {
        assert!(validate_latex("E = mc^2").is_ok());
    }

    #[test]
    fn test_valid_fraction() {
        assert!(validate_latex("\\frac{a}{b}").is_ok());
    }

    #[test]
    fn test_valid_nested_braces() {
        assert!(validate_latex("\\frac{a + \\sqrt{b}}{c}").is_ok());
    }

    #[test]
    fn test_empty_latex_is_valid() {
        assert!(validate_latex("").is_ok());
    }

    #[test]
    fn test_unmatched_opening_brace() {
        let result = validate_latex("\\frac{a}{b");
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.contains('{'));
    }

    #[test]
    fn test_unmatched_closing_brace() {
        assert!(validate_latex("\\frac{a}b}").is_err());
    }

    #[test]
    fn test_extra_opening_brace() {
        assert!(validate_latex("{a + b").is_err());
    }

    #[test]
    fn test_valid_square_brackets() {
        assert!(validate_latex("\\sqrt[3]{x}").is_ok());
    }

    #[test]
    fn test_unmatched_opening_square_bracket() {
        assert!(validate_latex("\\sqrt[3{x}").is_err());
    }

    #[test]
    fn test_valid_parentheses() {
        assert!(validate_latex("(a + b) \\cdot c").is_ok());
    }

    #[test]
    fn test_unmatched_opening_parenthesis() {
        assert!(validate_latex("(a + b").is_err());
    }

    #[test]
    fn test_unmatched_closing_parenthesis() {
        assert!(validate_latex("a + b)").is_err());
    }

    #[test]
    fn test_valid_inline_math() {
        assert!(validate_latex("$x + y$").is_ok());
    }

    #[test]
    fn test_valid_display_math() {
        assert!(validate_latex("$$\\int_0^1 x^2 dx$$").is_ok());
    }

    #[test]
    fn test_unclosed_single_dollar() {
        let result = validate_latex("$x + y");
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.contains('$'));
    }

    #[test]
    fn test_unclosed_double_dollar() {
        assert!(validate_latex("$$x + y$").is_err());
    }

    #[test]
    fn test_valid_paren_delimiters() {
        assert!(validate_latex("\\(x + y\\)").is_ok());
    }

    #[test]
    fn test_valid_bracket_delimiters() {
        assert!(validate_latex("\\[x + y\\]").is_ok());
    }

    #[test]
    fn test_unclosed_paren_delimiter() {
        let result = validate_latex("\\(x + y");
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.contains("\\("));
    }

    #[test]
    fn test_unclosed_bracket_delimiter() {
        assert!(validate_latex("\\[x + y").is_err());
    }

    #[test]
    fn test_detects_input_command() {
        let result = validate_latex("\\input{malicious}");
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.to_lowercase().contains("dangerous") || msg.to_lowercase().contains("input"));
    }

    #[test]
    fn test_detects_write_command() {
        let result = validate_latex("\\write18{rm -rf /}");
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.to_lowercase().contains("dangerous") || msg.to_lowercase().contains("write"));
    }

    #[test]
    fn test_detects_exec_command() {
        assert!(validate_latex("\\exec{system}").is_err());
    }

    #[test]
    fn test_detects_immediate_command() {
        let result = validate_latex("\\immediate\\write18{ls}");
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.to_lowercase().contains("dangerous") || msg.to_lowercase().contains("immediate"));
    }

    #[test]
    fn test_detects_dangerous_in_nested_context() {
        assert!(validate_latex("{\\input{/etc/passwd}}").is_err());
    }

    #[test]
    fn test_safe_commands_are_not_flagged() {
        assert!(validate_latex("\\frac{a}{b} + \\sqrt{x} + \\alpha").is_ok());
    }

    #[test]
    fn test_escaped_braces_counted_correctly() {
        assert!(validate_latex("\\{a\\}").is_ok());
    }

    #[test]
    fn test_long_response_warns() {
        let long_latex = "x".repeat(MAX_LATEX_LENGTH + 1);
        let result = validate_latex(&long_latex);
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.to_lowercase().contains("long") || msg.to_lowercase().contains("length"));
    }

    #[test]
    fn test_response_at_limit_passes_length_check() {
        let latex_at_limit = "x".repeat(MAX_LATEX_LENGTH);
        let result = validate_latex(&latex_at_limit);
        if let Err(ref e) = result {
            let msg = format!("{}", e);
            assert!(!msg.to_lowercase().contains("long"));
            assert!(!msg.to_lowercase().contains("length"));
        }
    }

    #[test]
    fn test_short_response_no_length_warning() {
        assert!(validate_latex("x + y").is_ok());
    }

    #[test]
    fn test_dangerous_commands() {
        let dangerous_inputs = [
            ("\\input{file}", "input"),
            ("\\write18{ls}", "write"),
            ("\\exec{code}", "exec"),
            ("\\immediate\\write18{cmd}", "immediate"),
            ("x + \\input{f}", "input"),
            ("\\write18", "write"),
        ];
        for (latex, label) in dangerous_inputs {
            let result = validate_latex(latex);
            assert!(result.is_err(), "Expected rejection for '{}': {}", label, latex);
            let msg = format!("{}", result.unwrap_err());
            assert!(
                msg.to_lowercase().contains("dangerous") || msg.to_lowercase().contains(label),
                "Expected 'dangerous' or '{}' in error message for '{}': {}",
                label, latex, msg
            );
        }
    }

    #[test]
    fn test_shell_escape_not_in_blocklist() {
        assert!(validate_latex("\\shellescape{cmd}").is_ok());
    }

    #[test]
    fn test_unmatched_brackets() {
        let cases = [
            ("{a + b", "open brace"),
            ("a + b}", "close brace"),
            ("[a + b", "open bracket"),
            ("a + b]", "close bracket"),
            ("(a + b", "open paren"),
            ("a + b)", "close paren"),
            ("{a + b]", "brace closed by bracket"),
            ("[a + b}", "bracket closed by brace"),
            ("(a + b}", "paren closed by brace"),
            ("{a + b)", "brace closed by paren"),
        ];
        for (latex, label) in cases {
            assert!(
                validate_latex(latex).is_err(),
                "Expected rejection for '{}': {}",
                label, latex
            );
        }
    }

    #[test]
    fn test_nested_brackets_deep() {
        let depth = 50;
        let nested = format!("{}{}{}", "{".repeat(depth), "x", "}".repeat(depth));
        assert!(validate_latex(&nested).is_ok());
    }

    #[test]
    fn test_nested_brackets_deep_unbalanced() {
        let depth = 50;
        let nested = format!("{}{}{}", "{".repeat(depth), "x", "}".repeat(depth - 1));
        assert!(validate_latex(&nested).is_err());
    }

    #[test]
    fn test_nested_mixed_bracket_types() {
        assert!(validate_latex("{ [ ( x ) ] }").is_ok());
    }

    #[test]
    fn test_nested_mixed_bracket_mismatch() {
        assert!(validate_latex("{ [ ( x ) } ]").is_err());
    }

    #[test]
    fn test_delimiter_imbalance() {
        let cases = [
            ("$x + y", "single open dollar"),
            ("x + y$", "single close dollar"),
            ("$$$x$$", "three dollars (odd)"),
            ("$x$ $y", "two pairs, second unclosed"),
            ("\\(x + y", "open paren delimiter"),
            ("x + y\\)", "close paren delimiter"),
            ("\\[x + y", "open bracket delimiter"),
            ("x + y\\]", "close bracket delimiter"),
        ];
        for (latex, label) in cases {
            assert!(
                validate_latex(latex).is_err(),
                "Expected rejection for '{}': {}",
                label, latex
            );
        }
    }

    #[test]
    fn test_delimiter_balance_valid_combinations() {
        let cases = ["$x$", "$$x$$", "\\(x\\)", "\\[x\\]", "$x$ and $y$", "$$a$$ and $$b$$"];
        for latex in cases {
            assert!(validate_latex(latex).is_ok(), "Expected valid: {}", latex);
        }
    }

    #[test]
    fn test_extremely_long_input() {
        let chunk = "\\frac{a}{b} + ";
        let repeats = (MAX_LATEX_LENGTH / chunk.len()) + 10;
        let long_latex = chunk.repeat(repeats);
        assert!(long_latex.len() > MAX_LATEX_LENGTH);
        let result = validate_latex(&long_latex);
        assert!(result.is_err());
        let msg = format!("{}", result.unwrap_err());
        assert!(msg.to_lowercase().contains("long") || msg.to_lowercase().contains("length"));
    }

    #[test]
    fn test_long_valid_latex_at_boundary() {
        let latex = "x + ".repeat(MAX_LATEX_LENGTH / 4);
        assert_eq!(latex.len(), MAX_LATEX_LENGTH);
        assert!(validate_latex(&latex).is_ok());
    }

    #[test]
    fn test_unicode_math_symbols() {
        let cases = [
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
        ];
        for latex in cases {
            assert!(validate_latex(latex).is_ok(), "Expected valid for unicode math: {}", latex);
        }
    }

    #[test]
    fn test_unicode_in_clean_response() {
        let raw = "```latex\n\\alpha + \\beta\n```";
        let result = clean_llm_response(raw);
        assert!(result.contains("\\alpha"));
        assert!(result.contains("\\beta"));
    }

    #[test]
    fn test_empty_and_whitespace() {
        let cases = ["", "   ", "\t\t\t", "\n\n\n", "  \t \n  ", "\r\n"];
        for raw in cases {
            assert_eq!(
                clean_llm_response(raw),
                "",
                "Expected empty for {:?}",
                raw
            );
        }
    }

    #[test]
    fn test_empty_latex_validates() {
        assert!(validate_latex("").is_ok());
    }

    #[test]
    fn test_mixed_dangerous_and_valid() {
        let cases = [
            "\\frac{a}{b} + \\input{malicious} + \\sqrt{x}",
            "\\alpha + \\beta \\write18{rm}",
            "\\sum_{\\exec{cmd}}^{n} x_i",
        ];
        for latex in cases {
            assert!(
                validate_latex(latex).is_err(),
                "Expected rejection for mixed input: {}",
                latex
            );
        }
    }
}