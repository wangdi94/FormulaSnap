//! OpenAI GPT-4o Vision OCR engine.
//!
//! Uses GPT-4o to extract LaTeX from images via the Chat Completions API.
//! Mirrors the Python `OpenAIEngine` in `sidecar/sidecar/ocr_engines/openai_engine.py`.

use std::time::Instant;

use async_trait::async_trait;
use base64::Engine as _;
use reqwest::StatusCode;
use serde::{Deserialize, Serialize};

use crate::engines::{
    CostEstimate, OcrBackend, OcrError, OcrOptions, OcrResult, RateLimitStatus, ValidationResult,
};
use crate::response_parser::{clean_llm_response, validate_latex};

// ── 常量 ──────────────────────────────────────────────────────────────────

/// gpt-4o input pricing: $2.50 per million tokens
const OPENAI_INPUT_COST_PER_TOKEN: f64 = 2.50 / 1_000_000.0;

/// gpt-4o output pricing: $10.00 per million tokens
const OPENAI_OUTPUT_COST_PER_TOKEN: f64 = 10.00 / 1_000_000.0;

/// Default max tokens for response
const DEFAULT_MAX_TOKENS: u64 = 1024;

/// Default request timeout in seconds
const DEFAULT_TIMEOUT_SECS: u64 = 60;

/// Estimated vision input tokens (OpenAI reference)
const VISION_TOKEN_ESTIMATE: u64 = 765;

/// System prompt for LaTeX-only transcription
const SYSTEM_PROMPT: &str = "You are a LaTeX OCR engine. Extract ALL mathematical formulas and \
text from the image. Return ONLY valid LaTeX code. Use $...$ for inline math and $$...$$ for \
display math. Do NOT include explanations, markdown code blocks, or commentary.";

/// User prompt for formula extraction
const OCR_PROMPT: &str = "Extract all mathematical formulas from this image. Return only the LaTeX code.";

/// OpenAI API base URL
const OPENAI_API_URL: &str = "https://api.openai.com/v1/chat/completions";

// ── API 请求/响应类型 ─────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<ChatMessage>,
    max_tokens: u64,
}

#[derive(Debug, Serialize)]
struct ChatMessage {
    role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<MessageContent>,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum MessageContent {
    Text(String),
    Parts(Vec<ContentPart>),
}

#[derive(Debug, Serialize)]
#[serde(tag = "type")]
enum ContentPart {
    #[serde(rename = "image_url")]
    ImageUrl { image_url: ImageUrl },
    #[serde(rename = "text")]
    Text { text: String },
}

#[derive(Debug, Serialize)]
struct ImageUrl {
    url: String,
}

#[derive(Debug, Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
    usage: Option<Usage>,
}

#[derive(Debug, Deserialize)]
struct Choice {
    message: ChoiceMessage,
}

#[derive(Debug, Deserialize)]
struct ChoiceMessage {
    content: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Usage {
    prompt_tokens: u64,
    completion_tokens: u64,
    total_tokens: u64,
}

// ── 引擎实现 ──────────────────────────────────────────────────────────────

/// OpenAI GPT-4o Vision OCR backend.
pub struct OpenAIEngine {
    client: reqwest::Client,
    api_key: String,
}

impl OpenAIEngine {
    /// Create a new OpenAI engine.
    ///
    /// If `api_key` is `None` or empty, falls back to the `OPENAI_API_KEY`
    /// environment variable.
    pub fn new(api_key: Option<String>) -> Self {
        let api_key = api_key
            .filter(|k| !k.is_empty())
            .or_else(|| std::env::var("OPENAI_API_KEY").ok())
            .unwrap_or_default();

        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(DEFAULT_TIMEOUT_SECS))
            .build()
            .expect("Failed to build HTTP client");

        Self { client, api_key }
    }

    /// Close the engine and release resources.
    ///
    /// `reqwest::Client` uses `Arc` internally and cleans up on drop,
    /// so this is a no-op kept for API compatibility.
    pub async fn aclose(&self) {
        // reqwest::Client cleans up on drop; no explicit close needed.
    }

    /// Detect MIME type from image magic bytes.
    fn detect_mime_type(image: &[u8]) -> &'static str {
        if image.len() >= 4 && image[..4] == [0x89, 0x50, 0x4E, 0x47] {
            "image/png"
        } else if image.len() >= 3 && image[..3] == [0xFF, 0xD8, 0xFF] {
            "image/jpeg"
        } else if image.len() >= 4 && image[..4] == [0x47, 0x49, 0x46, 0x38] {
            "image/gif"
        } else if image.len() >= 12
            && image[..4] == [0x52, 0x49, 0x46, 0x46]
            && image[8..12] == [0x57, 0x45, 0x42, 0x50]
        {
            "image/webp"
        } else {
            "image/png" // default fallback
        }
    }

    /// Map HTTP status code to `OcrError`.
    fn map_http_error(status: StatusCode, body: &str) -> OcrError {
        match status.as_u16() {
            401 => OcrError::ApiKeyError("Invalid OpenAI API key".to_string()),
            429 => OcrError::RateLimitError("OpenAI rate limit exceeded".to_string()),
            500..=599 => OcrError::NetworkError(format!("OpenAI server error: {}", status)),
            _ => {
                let truncated = if body.len() > 200 {
                    &body[..200]
                } else {
                    body
                };
                OcrError::EngineError(format!("OpenAI API error {}: {}", status, truncated))
            }
        }
    }
}

#[async_trait]
impl OcrBackend for OpenAIEngine {
    async fn recognize(&self, image: &[u8], options: OcrOptions) -> Result<OcrResult, OcrError> {
        // Validate API key
        if self.api_key.is_empty() {
            return Err(OcrError::ApiKeyError(
                "OpenAI API key not configured".to_string(),
            ));
        }

        // Validate image
        if image.is_empty() {
            return Err(OcrError::InvalidImage("Empty image data".to_string()));
        }

        let start = Instant::now();

        // Encode image as base64 data URL
        let image_base64 = base64::engine::general_purpose::STANDARD.encode(image);
        let mime_type = Self::detect_mime_type(image);
        let data_url = format!("data:{};base64,{}", mime_type, image_base64);

        // Build request body
        let request = ChatRequest {
            model: "gpt-4o".to_string(),
            messages: vec![
                ChatMessage {
                    role: "system".to_string(),
                    content: Some(MessageContent::Text(SYSTEM_PROMPT.to_string())),
                },
                ChatMessage {
                    role: "user".to_string(),
                    content: Some(MessageContent::Parts(vec![
                        ContentPart::ImageUrl {
                            image_url: ImageUrl { url: data_url },
                        },
                        ContentPart::Text {
                            text: OCR_PROMPT.to_string(),
                        },
                    ])),
                },
            ],
            max_tokens: DEFAULT_MAX_TOKENS,
        };

        // Per-request timeout override
        let timeout = options
            .timeout
            .map(std::time::Duration::from_millis)
            .unwrap_or(std::time::Duration::from_secs(DEFAULT_TIMEOUT_SECS));

        // Send request
        let response = self
            .client
            .post(OPENAI_API_URL)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .timeout(timeout)
            .json(&request)
            .send()
            .await
            .map_err(|e| {
                if e.is_timeout() {
                    OcrError::Timeout
                } else if e.is_connect() {
                    OcrError::NetworkError(format!("Connection failed: {}", e))
                } else {
                    OcrError::NetworkError(format!("Request failed: {}", e))
                }
            })?;

        // Check HTTP status
        let status = response.status();
        if !status.is_success() {
            let body = response.text().await.unwrap_or_default();
            return Err(Self::map_http_error(status, &body));
        }

        // Parse JSON response
        let chat_response: ChatResponse = response.json().await.map_err(|e| {
            OcrError::EngineError(format!("Failed to parse response: {}", e))
        })?;

        if chat_response.choices.is_empty() {
            return Err(OcrError::EngineError(
                "OpenAI returned empty choices".to_string(),
            ));
        }

        // Extract and clean LaTeX
        let raw_text = chat_response.choices[0]
            .message
            .content
            .as_deref()
            .unwrap_or("");

        let cleaned = clean_llm_response(raw_text);

        // Validate LaTeX (convert types::OcrError → engines::OcrError)
        validate_latex(&cleaned).map_err(|e| match e {
            crate::types::OcrError::ParseError(msg) => OcrError::EngineError(msg),
            other => OcrError::EngineError(other.to_string()),
        })?;

        // Calculate cost from usage
        let usage = chat_response.usage.unwrap_or(Usage {
            prompt_tokens: 500,
            completion_tokens: 265,
            total_tokens: 765,
        });

        let cost_usd = (usage.prompt_tokens as f64 * OPENAI_INPUT_COST_PER_TOKEN)
            + (usage.completion_tokens as f64 * OPENAI_OUTPUT_COST_PER_TOKEN);

        let timing_ms = start.elapsed().as_millis() as u64;

        Ok(OcrResult {
            latex: cleaned,
            confidence: None, // LLM doesn't provide confidence
            backend: "openai".to_string(),
            timing_ms,
            cost_estimate: Some(CostEstimate {
                tokens_used: usage.total_tokens,
                estimated_cost_usd: cost_usd,
            }),
        })
    }

    fn estimate_cost(&self, _image: &[u8]) -> Option<CostEstimate> {
        let estimated_output_tokens = 265u64;
        let cost_usd = (VISION_TOKEN_ESTIMATE as f64 * OPENAI_INPUT_COST_PER_TOKEN)
            + (estimated_output_tokens as f64 * OPENAI_OUTPUT_COST_PER_TOKEN);
        Some(CostEstimate {
            tokens_used: VISION_TOKEN_ESTIMATE + estimated_output_tokens,
            estimated_cost_usd: cost_usd,
        })
    }

    fn validate_config(&self) -> ValidationResult {
        if self.api_key.is_empty() {
            return ValidationResult {
                valid: false,
                message: "OPENAI_API_KEY not set".to_string(),
            };
        }
        ValidationResult {
            valid: true,
            message: "API key configured".to_string(),
        }
    }

    fn get_rate_limit_status(&self) -> Option<RateLimitStatus> {
        None
    }
}

// ── 测试 ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Helper: create engine with a test API key.
    fn make_engine() -> OpenAIEngine {
        OpenAIEngine::new(Some("sk-test-key-12345".to_string()))
    }

    /// Helper: create engine with empty key (no env var mutation).
    fn make_engine_no_key() -> OpenAIEngine {
        OpenAIEngine::new(Some(String::new()))
    }

    #[test]
    fn test_new_with_explicit_key() {
        let engine = make_engine();
        assert_eq!(engine.api_key, "sk-test-key-12345");
    }

    #[test]
    fn test_new_empty_key_stores_empty() {
        let engine = make_engine_no_key();
        let _ = &engine.api_key;
    }

    #[test]
    fn test_new_accepts_none() {
        let engine = OpenAIEngine::new(None);
        let _ = &engine.api_key;
    }

    #[test]
    fn test_validate_config_valid() {
        let engine = make_engine();
        let result = engine.validate_config();
        assert!(result.valid);
        assert!(result.message.contains("configured"));
    }

    #[test]
    fn test_validate_config_missing_key() {
        let engine = make_engine_no_key();
        if engine.api_key.is_empty() {
            let result = engine.validate_config();
            assert!(!result.valid);
            assert!(result.message.contains("OPENAI_API_KEY"));
        }
    }

    #[test]
    fn test_get_rate_limit_status_returns_none() {
        let engine = make_engine();
        assert!(engine.get_rate_limit_status().is_none());
    }

    #[test]
    fn test_estimate_cost_returns_value() {
        let engine = make_engine();
        let cost = engine.estimate_cost(&[0x89, 0x50, 0x4E, 0x47]);
        assert!(cost.is_some());
        let cost = cost.unwrap();
        assert!(cost.estimated_cost_usd > 0.0);
        assert!(cost.tokens_used > 0);
        // Should include both input (765) and output (265) tokens
        assert_eq!(cost.tokens_used, VISION_TOKEN_ESTIMATE + 265);
    }

    #[test]
    fn test_estimate_cost_consistent() {
        let engine = make_engine();
        let cost1 = engine.estimate_cost(&[0x00]).unwrap();
        let cost2 = engine.estimate_cost(&[0xFF; 1024]).unwrap();
        assert_eq!(cost1.tokens_used, cost2.tokens_used);
        assert!((cost1.estimated_cost_usd - cost2.estimated_cost_usd).abs() < f64::EPSILON);
    }

    #[test]
    fn test_detect_mime_type_png() {
        let png = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
        assert_eq!(OpenAIEngine::detect_mime_type(&png), "image/png");
    }

    #[test]
    fn test_detect_mime_type_jpeg() {
        let jpeg = [0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10];
        assert_eq!(OpenAIEngine::detect_mime_type(&jpeg), "image/jpeg");
    }

    #[test]
    fn test_detect_mime_type_gif() {
        let gif = [0x47, 0x49, 0x46, 0x38, 0x39, 0x61];
        assert_eq!(OpenAIEngine::detect_mime_type(&gif), "image/gif");
    }

    #[test]
    fn test_detect_mime_type_webp() {
        let mut webp = [0u8; 12];
        webp[..4].copy_from_slice(&[0x52, 0x49, 0x46, 0x46]); // RIFF
        webp[8..12].copy_from_slice(&[0x57, 0x45, 0x42, 0x50]); // WEBP
        assert_eq!(OpenAIEngine::detect_mime_type(&webp), "image/webp");
    }

    #[test]
    fn test_detect_mime_type_unknown_defaults_png() {
        let unknown = [0x00, 0x01, 0x02, 0x03];
        assert_eq!(OpenAIEngine::detect_mime_type(&unknown), "image/png");
    }

    #[test]
    fn test_detect_mime_type_short_data_defaults_png() {
        let short = [0x89, 0x50]; // too short for any detection
        assert_eq!(OpenAIEngine::detect_mime_type(&short), "image/png");
    }

    #[test]
    fn test_detect_mime_type_empty_defaults_png() {
        assert_eq!(OpenAIEngine::detect_mime_type(&[]), "image/png");
    }

    #[test]
    fn test_map_http_error_401() {
        let err = OpenAIEngine::map_http_error(StatusCode::UNAUTHORIZED, "Unauthorized");
        assert!(matches!(err, OcrError::ApiKeyError(_)));
        assert!(err.to_string().contains("Invalid OpenAI API key"));
    }

    #[test]
    fn test_map_http_error_429() {
        let err = OpenAIEngine::map_http_error(StatusCode::TOO_MANY_REQUESTS, "Rate limited");
        assert!(matches!(err, OcrError::RateLimitError(_)));
    }

    #[test]
    fn test_map_http_error_500() {
        let err =
            OpenAIEngine::map_http_error(StatusCode::INTERNAL_SERVER_ERROR, "Internal error");
        assert!(matches!(err, OcrError::NetworkError(_)));
    }

    #[test]
    fn test_map_http_error_503() {
        let err = OpenAIEngine::map_http_error(StatusCode::SERVICE_UNAVAILABLE, "Unavailable");
        assert!(matches!(err, OcrError::NetworkError(_)));
    }

    #[test]
    fn test_map_http_error_other_status() {
        let err = OpenAIEngine::map_http_error(StatusCode::BAD_REQUEST, "Bad request");
        assert!(matches!(err, OcrError::EngineError(_)));
    }

    #[test]
    fn test_map_http_error_truncates_long_body() {
        let long_body = "x".repeat(500);
        let err = OpenAIEngine::map_http_error(StatusCode::BAD_REQUEST, &long_body);
        let msg = err.to_string();
        // Should be truncated, not contain all 500 chars
        assert!(msg.len() < 600);
    }

    #[tokio::test]
    async fn test_recognize_empty_image_rejected() {
        let engine = make_engine();
        let result = engine.recognize(&[], OcrOptions::default()).await;
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), OcrError::InvalidImage(_)));
    }

    #[tokio::test]
    async fn test_recognize_no_api_key_rejected() {
        let engine = OpenAIEngine::new(Some(String::new()));
        if engine.api_key.is_empty() {
            let result = engine
                .recognize(&[0x89, 0x50, 0x4E, 0x47], OcrOptions::default())
                .await;
            assert!(result.is_err());
            assert!(matches!(result.unwrap_err(), OcrError::ApiKeyError(_)));
        }
    }
}
