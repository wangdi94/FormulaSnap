use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use serde::{Deserialize, Serialize};
use thiserror::Error;

// ── 支撑类型 ──────────────────────────────────────────────────────────────

/// OCR 操作的成本估算
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostEstimate {
    /// 消耗的 token 数量（LLM 后端）
    pub tokens_used: u64,
    /// 估算成本（美元）
    pub estimated_cost_usd: f64,
}

/// 后端 API 密钥状态
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyInfo {
    /// 后端名称
    pub backend: String,
    /// 是否已配置密钥
    pub configured: bool,
}

// ── 请求类型 ──────────────────────────────────────────────────────────────

/// OCR 识别请求
#[derive(Debug, Clone, Deserialize)]
pub struct OcrRequest {
    /// Base64 编码的图片数据
    pub image_base64: String,
    /// OCR 后端名称，默认 "pix2text"
    #[serde(default = "default_backend")]
    pub backend: String,
}

fn default_backend() -> String {
    "pix2text".to_string()
}

/// 关闭请求
#[derive(Debug, Clone, Deserialize)]
pub struct ShutdownRequest {
    /// 关闭令牌
    #[serde(default)]
    pub token: String,
}

/// 验证配置请求
#[derive(Debug, Clone, Deserialize)]
pub struct ValidateConfigRequest {
    /// 要验证的后端名称
    pub backend: String,
}

/// 保存 API 密钥请求
#[derive(Debug, Clone, Deserialize)]
pub struct SaveKeyRequest {
    /// 后端名称
    pub backend: String,
    /// API 密钥值
    pub key: String,
}

// ── 响应类型 ──────────────────────────────────────────────────────────────

/// OCR 识别响应
#[derive(Debug, Clone, Serialize)]
pub struct OcrResponse {
    /// 识别出的 LaTeX 字符串
    pub latex: String,
    /// 置信度 0.0–1.0，LLM 引擎为 None
    pub confidence: Option<f64>,
    /// 使用的后端名称
    pub backend: String,
    /// 识别耗时（毫秒）
    pub timing_ms: u64,
    /// 成本估算
    pub cost_estimate: Option<CostEstimate>,
}

/// 统计信息响应
#[derive(Debug, Clone, Serialize)]
pub struct StatsResponse {
    /// 总 API 调用次数
    pub total_calls: u64,
    /// 总消耗 token 数
    pub total_tokens: u64,
    /// 总估算成本（美元）
    pub estimated_cost_usd: f64,
    /// 今日调用次数
    pub calls_today: u64,
    /// 每日调用上限
    pub daily_limit: u64,
    /// 今日剩余调用次数
    pub remaining_today: u64,
}

/// 密钥状态响应
#[derive(Debug, Clone, Serialize)]
pub struct KeysResponse {
    /// 所有后端的密钥状态列表
    pub keys: Vec<KeyInfo>,
}

/// 健康检查响应
#[derive(Debug, Clone, Serialize)]
pub struct HealthResponse {
    /// 服务状态
    pub status: String,
    /// 已注册的引擎列表
    pub engines: Vec<String>,
}

/// 引擎状态响应
#[derive(Debug, Clone, Serialize)]
pub struct EngineStatusResponse {
    /// 已注册的引擎名称列表
    pub registered: Vec<String>,
    /// 已注册引擎数量
    pub count: usize,
}

// ── 错误类型 ──────────────────────────────────────────────────────────────

/// OCR 相关错误
#[derive(Debug, Error)]
pub enum OcrError {
    /// 空图片数据
    #[error("空图片数据")]
    EmptyImage,

    /// 图片过大（超过 15MB）
    #[error("图片过大，超过 15MB 限制")]
    ImageTooLarge,

    /// 无效的图片格式
    #[error("无效的图片格式: {0}")]
    InvalidImage(String),

    /// OCR 识别超时
    #[error("OCR 识别超时")]
    Timeout,

    /// 速率限制已超出
    #[error("速率限制已超出，建议等待 {retry_after:?} 秒")]
    RateLimitExceeded {
        /// 建议等待秒数
        retry_after: Option<u64>,
    },

    /// API 密钥缺失或无效
    #[error("API 密钥错误: {0}")]
    ApiKeyError(String),

    /// API 速率限制
    #[error("API 速率限制: {0}")]
    RateLimitError(String),

    /// 网络通信错误
    #[error("网络错误: {0}")]
    NetworkError(String),

    /// OCR 引擎返回错误
    #[error("OCR 错误: {0}")]
    OcrError(String),

    /// 内部服务器错误
    #[error("内部服务器错误: {0}")]
    InternalError(String),

    /// LaTeX 解析/验证错误
    #[error("LaTeX 解析错误: {0}")]
    ParseError(String),
}

impl IntoResponse for OcrError {
    fn into_response(self) -> Response {
        let (status, error_code, message) = match &self {
            OcrError::EmptyImage => (StatusCode::BAD_REQUEST, "EMPTY_IMAGE", self.to_string()),
            OcrError::ImageTooLarge => (StatusCode::PAYLOAD_TOO_LARGE, "IMAGE_TOO_LARGE", self.to_string()),
            OcrError::InvalidImage(_) => (StatusCode::BAD_REQUEST, "INVALID_IMAGE", self.to_string()),
            OcrError::Timeout => (StatusCode::GATEWAY_TIMEOUT, "TIMEOUT", self.to_string()),
            OcrError::RateLimitExceeded { .. } => (StatusCode::TOO_MANY_REQUESTS, "RATE_LIMIT_EXCEEDED", self.to_string()),
            OcrError::ApiKeyError(_) => (StatusCode::UNAUTHORIZED, "API_KEY_ERROR", self.to_string()),
            OcrError::RateLimitError(_) => (StatusCode::TOO_MANY_REQUESTS, "RATE_LIMIT_ERROR", self.to_string()),
            OcrError::NetworkError(_) => (StatusCode::SERVICE_UNAVAILABLE, "NETWORK_ERROR", self.to_string()),
            OcrError::OcrError(_) => (StatusCode::INTERNAL_SERVER_ERROR, "OCR_ERROR", self.to_string()),
            OcrError::InternalError(_) => (StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", self.to_string()),
            OcrError::ParseError(_) => (StatusCode::BAD_REQUEST, "PARSE_ERROR", self.to_string()),
        };

        let body = serde_json::json!({
            "error": error_code,
            "message": message,
        });

        (status, axum::Json(body)).into_response()
    }
}
