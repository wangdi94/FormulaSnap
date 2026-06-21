//! OCR 引擎 trait 定义和相关类型。
//!
//! 与 Python sidecar 的 `interface.py` 保持一致：
//! - `OcrBackend` trait → Python `OcrBackend` Protocol
//! - 各结构体 → Python 对应的 dataclass

pub mod claude;
pub mod openai;

use std::collections::HashMap;

use async_trait::async_trait;

// ── 请求选项 ──────────────────────────────────────────────────────────────

/// OCR 识别请求选项
#[derive(Debug, Clone, Default)]
pub struct OcrOptions {
    /// 指定使用的后端名称，为空时由引擎管理器自动选择
    pub backend: String,
    /// 识别超时时间（毫秒），None 时使用引擎默认值
    pub timeout: Option<u64>,
}

// ── 成本估算 ──────────────────────────────────────────────────────────────

/// OCR 操作的成本估算
#[derive(Debug, Clone)]
pub struct CostEstimate {
    /// 消耗的 token 数量（LLM 后端）
    pub tokens_used: u64,
    /// 估算成本（美元）
    pub estimated_cost_usd: f64,
}

// ── 识别结果 ──────────────────────────────────────────────────────────────

/// OCR 识别结果
#[derive(Debug, Clone)]
pub struct OcrResult {
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

// ── 速率限制 ──────────────────────────────────────────────────────────────

/// 后端 API 速率限制状态
#[derive(Debug, Clone)]
pub struct RateLimitStatus {
    /// 每日调用上限
    pub daily_limit: u64,
    /// 今日已调用次数
    pub calls_today: u64,
    /// 今日剩余调用次数
    pub remaining_today: u64,
    /// 最小调用间隔（秒）
    pub interval_seconds: u64,
}

// ── 配置验证 ──────────────────────────────────────────────────────────────

/// 后端配置验证结果
#[derive(Debug, Clone)]
pub struct ValidationResult {
    /// 配置是否有效
    pub valid: bool,
    /// 人类可读的验证消息
    pub message: String,
}

// ── OCR 引擎 trait ────────────────────────────────────────────────────────

/// OCR 引擎 trait，与 Python `OcrBackend` Protocol 对应。
///
/// 所有引擎实现此 trait 即可注册到 `EngineRegistry`。
/// 要求 `Send + Sync` 以支持多线程异步调用。
#[async_trait]
pub trait OcrBackend: Send + Sync {
    /// 识别图片中的数学公式
    ///
    /// # Arguments
    /// * `image` - 原始图片字节（PNG、JPEG 等）
    /// * `options` - 识别选项
    ///
    /// # Returns
    /// 识别结果，包含 LaTeX 字符串和元数据
    async fn recognize(&self, image: &[u8], options: OcrOptions) -> Result<OcrResult, OcrError>;

    /// 估算识别成本
    ///
    /// 对 LLM 后端返回 token 消耗和费用估算，
    /// 对本地引擎（如 Pix2Text）返回 None。
    fn estimate_cost(&self, image: &[u8]) -> Option<CostEstimate>;

    /// 验证引擎配置（API 密钥、端点等）
    fn validate_config(&self) -> ValidationResult;

    /// 获取当前速率限制状态
    ///
    /// 返回 None 表示该后端不跟踪速率限制（如本地引擎）。
    fn get_rate_limit_status(&self) -> Option<RateLimitStatus>;
}

// ── 引擎错误类型 ──────────────────────────────────────────────────────────

/// OCR 引擎错误
#[derive(Debug, thiserror::Error)]
pub enum OcrError {
    /// API 密钥缺失或无效
    #[error("API 密钥错误: {0}")]
    ApiKeyError(String),

    /// API 速率限制
    #[error("速率限制已超出: {0}")]
    RateLimitError(String),

    /// 网络通信错误
    #[error("网络错误: {0}")]
    NetworkError(String),

    /// OCR 识别超时
    #[error("OCR 识别超时")]
    Timeout,

    /// 图片数据无效
    #[error("无效的图片数据: {0}")]
    InvalidImage(String),

    /// 引擎内部错误
    #[error("OCR 错误: {0}")]
    EngineError(String),
}

// ── 引擎注册表 ────────────────────────────────────────────────────────────

/// 引擎注册表，存储所有已注册的 OCR 引擎
pub struct EngineRegistry {
    /// 引擎名称 → 引擎实例的映射
    pub engines: HashMap<String, Box<dyn OcrBackend>>,
}

// ── 测试 ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// 验证 OcrOptions 默认值
    #[test]
    fn test_ocr_options_default() {
        let opts = OcrOptions::default();
        assert_eq!(opts.backend, "");
        assert!(opts.timeout.is_none());
    }

    /// 验证 CostEstimate 构造
    #[test]
    fn test_cost_estimate() {
        let est = CostEstimate {
            tokens_used: 1000,
            estimated_cost_usd: 0.01,
        };
        assert_eq!(est.tokens_used, 1000);
        assert!((est.estimated_cost_usd - 0.01).abs() < f64::EPSILON);
    }

    /// 验证 OcrResult 构造
    #[test]
    fn test_ocr_result() {
        let result = OcrResult {
            latex: "x^2".to_string(),
            confidence: Some(0.95),
            backend: "pix2text".to_string(),
            timing_ms: 120,
            cost_estimate: None,
        };
        assert_eq!(result.latex, "x^2");
        assert_eq!(result.confidence, Some(0.95));
        assert!(result.cost_estimate.is_none());
    }

    /// 验证 RateLimitStatus 构造
    #[test]
    fn test_rate_limit_status() {
        let status = RateLimitStatus {
            daily_limit: 100,
            calls_today: 15,
            remaining_today: 85,
            interval_seconds: 2,
        };
        assert_eq!(status.remaining_today, 85);
    }

    /// 验证 ValidationResult 构造
    #[test]
    fn test_validation_result() {
        let valid = ValidationResult {
            valid: true,
            message: "配置有效".to_string(),
        };
        assert!(valid.valid);

        let invalid = ValidationResult {
            valid: false,
            message: "缺少 API 密钥".to_string(),
        };
        assert!(!invalid.valid);
    }

    /// 验证 OcrError 错误消息
    #[test]
    fn test_ocr_error_messages() {
        let err = OcrError::ApiKeyError("key invalid".to_string());
        assert!(err.to_string().contains("key invalid"));

        let err = OcrError::Timeout;
        assert_eq!(err.to_string(), "OCR 识别超时");
    }

    /// 验证 EngineRegistry 结构
    #[test]
    fn test_engine_registry() {
        let registry = EngineRegistry {
            engines: HashMap::new(),
        };
        assert!(registry.engines.is_empty());
    }
}
