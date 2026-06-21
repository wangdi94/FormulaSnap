use std::sync::Arc;

use axum::extract::State;
use axum::http::StatusCode;
use axum::Json;
use base64::Engine;
use serde_json::json;
use tokio::sync::{broadcast, Mutex};

use crate::cache::OcrCache;
use crate::cost_tracker::{CostTracker, RateLimitError};
use crate::engines::{EngineRegistry, OcrOptions};
use crate::types::{OcrError, OcrRequest, OcrResponse, ShutdownRequest};

// ── 应用状态 ─────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct AppState {
    pub shutdown_tx: broadcast::Sender<()>,
    pub engines: Arc<EngineRegistry>,
    pub cache: Arc<OcrCache>,
    pub cost_tracker: Arc<Mutex<CostTracker>>,
}

// ── 已注册引擎列表 ───────────────────────────────────────────────────────

/// 硬编码的引擎列表，与 Python 版本一致
const REGISTERED_ENGINES: &[&str] = &["openai", "claude", "gemini", "mathpix", "pix2text"];

// ── 健康检查 ─────────────────────────────────────────────────────────────

/// GET /health — 健康检查，返回服务状态和已注册引擎
pub async fn health() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "engines": REGISTERED_ENGINES
    }))
}

// ── 关闭 ─────────────────────────────────────────────────────────────────

/// POST /shutdown — 请求关闭 sidecar
///
/// 验证 token 后发送关闭信号，触发优雅关闭流程。
/// Token 通过环境变量 `FORMULASNAP_SHUTDOWN_TOKEN` 配置，
/// 未设置时使用基于时间戳的默认值。
pub async fn shutdown(
    State(state): State<AppState>,
    Json(request): Json<ShutdownRequest>,
) -> Result<(StatusCode, Json<serde_json::Value>), (StatusCode, Json<serde_json::Value>)> {
    let expected_token = get_shutdown_token();

    if request.token != expected_token {
        return Err((
            StatusCode::UNAUTHORIZED,
            Json(json!({
                "error": "UNAUTHORIZED",
                "message": "无效的关闭令牌"
            })),
        ));
    }

    // 发送关闭信号（忽略接收端错误：可能没有监听者）
    let _ = state.shutdown_tx.send(());

    Ok((
        StatusCode::OK,
        Json(json!({
            "status": "shutting_down"
        })),
    ))
}

/// 获取关闭令牌：环境变量优先，否则使用基于时间戳的默认值
fn get_shutdown_token() -> String {
    std::env::var("FORMULASNAP_SHUTDOWN_TOKEN").unwrap_or_else(|_| {
        // 无 uuid 依赖，使用纳秒时间戳生成默认令牌
        use std::time::{SystemTime, UNIX_EPOCH};
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        format!("formulasnap-{nanos:x}")
    })
}

// ── OCR 识别 ─────────────────────────────────────────────────────────────

const MAX_IMAGE_SIZE: usize = 15 * 1024 * 1024;
const OCR_TIMEOUT_SECS: u64 = 120;

pub async fn ocr(
    State(state): State<AppState>,
    Json(request): Json<OcrRequest>,
) -> Result<Json<OcrResponse>, OcrError> {
    let image_data = base64::engine::general_purpose::STANDARD
        .decode(&request.image_base64)
        .map_err(|e| OcrError::InvalidImage(format!("Base64 解码失败: {}", e)))?;

    if image_data.is_empty() {
        return Err(OcrError::EmptyImage);
    }
    if image_data.len() > MAX_IMAGE_SIZE {
        return Err(OcrError::ImageTooLarge);
    }

    let image_hash = OcrCache::hash_bytes(&image_data);
    let cache_key = format!("{}:{}", image_hash, request.backend);

    if let Some(cached) = state.cache.get(&cache_key) {
        tracing::info!("OCR cache hit for key: {}", &cache_key[..16.min(cache_key.len())]);
        return Ok(Json(OcrResponse {
            latex: cached.latex,
            confidence: cached.confidence,
            backend: cached.backend,
            timing_ms: cached.timing_ms,
            cost_estimate: None,
        }));
    }

    {
        let tracker = state.cost_tracker.lock().await;
        tracker.check_rate_limit().map_err(|e| match e {
            RateLimitError::DailyLimitExceeded {
                retry_after_secs,
                ..
            } => OcrError::RateLimitExceeded {
                retry_after: Some(retry_after_secs),
            },
            RateLimitError::IntervalTooShort { retry_after_secs } => {
                OcrError::RateLimitError(format!("调用间隔过短，{} 秒后可重试", retry_after_secs))
            }
        })?;
    }

    let backend = request.backend.clone();
    let engines = state.engines.clone();
    let recognize_future = async { engines.recognize(&backend, &image_data, &OcrOptions::default()).await };

    let result = match tokio::time::timeout(
        std::time::Duration::from_secs(OCR_TIMEOUT_SECS),
        recognize_future,
    )
    .await
    {
        Ok(Ok(result)) => result,
        Ok(Err(e)) => {
            return Err(match e {
                crate::engines::OcrError::ApiKeyError(msg) => OcrError::ApiKeyError(msg),
                crate::engines::OcrError::RateLimitError(msg) => OcrError::RateLimitError(msg),
                crate::engines::OcrError::NetworkError(msg) => OcrError::NetworkError(msg),
                crate::engines::OcrError::Timeout => OcrError::Timeout,
                crate::engines::OcrError::InvalidImage(msg) => OcrError::InvalidImage(msg),
                crate::engines::OcrError::EngineError(msg) => OcrError::OcrError(msg),
            })
        }
        Err(_) => return Err(OcrError::Timeout),
    };

    {
        let tracker = state.cost_tracker.lock().await;
        let cost = result
            .cost_estimate
            .as_ref()
            .map(|c| c.estimated_cost_usd)
            .unwrap_or(0.0);
        let tokens = result
            .cost_estimate
            .as_ref()
            .map(|c| c.tokens_used)
            .unwrap_or(0);
        tracker.check_and_record(&result.backend, tokens, cost).ok();
    }

    let response = OcrResponse {
        latex: result.latex.clone(),
        confidence: result.confidence,
        backend: result.backend.clone(),
        timing_ms: result.timing_ms,
        cost_estimate: result.cost_estimate.map(|c| crate::types::CostEstimate {
            tokens_used: c.tokens_used,
            estimated_cost_usd: c.estimated_cost_usd,
        }),
    };

    state.cache.set(
        cache_key,
        result.latex,
        result.confidence,
        &result.backend,
        result.timing_ms,
    );

    Ok(Json(response))
}

// ── 统计信息 ─────────────────────────────────────────────────────────────

/// GET /api/stats — 返回调用统计
pub async fn stats(State(state): State<AppState>) -> Json<serde_json::Value> {
    let snapshot = state.cost_tracker.lock().await.get_stats();
    Json(json!({
        "status": "ok",
        "total_calls": snapshot.total_calls,
        "total_tokens": snapshot.total_tokens,
        "estimated_cost_usd": snapshot.estimated_cost_usd,
        "calls_today": snapshot.calls_today,
        "daily_limit": snapshot.daily_limit,
        "remaining_today": snapshot.remaining_today
    }))
}

// ── 引擎状态 ─────────────────────────────────────────────────────────────

/// GET /api/engines/status — 返回已注册引擎状态
pub async fn engines_status(State(state): State<AppState>) -> Json<serde_json::Value> {
    let registered: Vec<String> = state.engines.engines.keys().cloned().collect();
    let count = registered.len();
    Json(json!({
        "status": "ok",
        "registered": registered,
        "count": count
    }))
}

// ── 配置验证 ─────────────────────────────────────────────────────────────

/// POST /api/validate-config — 验证后端配置（占位实现）
pub async fn validate_config() -> Json<serde_json::Value> {
    // TODO: 将验证实际后端配置
    Json(json!({
        "status": "ok",
        "message": "validate-config endpoint placeholder"
    }))
}

// ── API 密钥管理 ─────────────────────────────────────────────────────────

/// GET /api/keys — 获取所有后端密钥状态（占位实现）
pub async fn get_keys() -> Json<serde_json::Value> {
    // TODO: 将查询实际密钥状态
    Json(json!({
        "status": "ok",
        "keys": []
    }))
}

/// PUT /api/keys — 保存 API 密钥（占位实现）
pub async fn save_key() -> Json<serde_json::Value> {
    // TODO: 将保存密钥到 keyring
    Json(json!({
        "status": "ok",
        "message": "save-key endpoint placeholder"
    }))
}

// ── 单元测试 ─────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use tower::ServiceExt;

    fn test_router() -> axum::Router {
        let (tx, _rx) = broadcast::channel(1);
        let key_manager = Arc::new(crate::key_manager::KeyManager::new());
        let engines = Arc::new(EngineRegistry::new(&key_manager));
        let cache = Arc::new(OcrCache::new(100, 3600.0));
        let cost_tracker = Arc::new(Mutex::new(CostTracker::new(100, 0.0)));

        let state = AppState {
            shutdown_tx: tx,
            engines,
            cache,
            cost_tracker,
        };

        axum::Router::new()
            .route("/health", axum::routing::get(health))
            .route("/shutdown", axum::routing::post(shutdown))
            .route("/api/ocr", axum::routing::post(ocr))
            .route("/api/stats", axum::routing::get(stats))
            .route("/api/engines/status", axum::routing::get(engines_status))
            .with_state(state)
    }

    #[tokio::test]
    async fn test_health_returns_ok() {
        let app = test_router();

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/health")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);

        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

        assert_eq!(json["status"], "ok");
        let engines = json["engines"].as_array().unwrap();
        assert_eq!(engines.len(), 5);
        assert!(engines.contains(&serde_json::Value::String("openai".to_string())));
        assert!(engines.contains(&serde_json::Value::String("claude".to_string())));
        assert!(engines.contains(&serde_json::Value::String("gemini".to_string())));
        assert!(engines.contains(&serde_json::Value::String("mathpix".to_string())));
        assert!(engines.contains(&serde_json::Value::String("pix2text".to_string())));
    }

    #[tokio::test]
    async fn test_shutdown_valid_token() {
        std::env::set_var("FORMULASNAP_SHUTDOWN_TOKEN", "valid-test-token");
        let app = test_router();

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/shutdown")
                    .header("content-type", "application/json")
                    .body(Body::from(r#"{"token": "valid-test-token"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);

        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

        assert_eq!(json["status"], "shutting_down");
    }

    #[tokio::test]
    async fn test_shutdown_invalid_token() {
        std::env::set_var("FORMULASNAP_SHUTDOWN_TOKEN", "invalid-test-token");
        let app = test_router();

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/shutdown")
                    .header("content-type", "application/json")
                    .body(Body::from(r#"{"token": "wrong-token"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);

        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

        assert_eq!(json["error"], "UNAUTHORIZED");
    }

    #[tokio::test]
    async fn test_ocr_empty_image() {
        let app = test_router();

        let empty_b64 = base64::engine::general_purpose::STANDARD.encode(b"");
        let body = serde_json::json!({
            "image_base64": empty_b64,
            "backend": "pix2text"
        });

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/api/ocr")
                    .header("content-type", "application/json")
                    .body(Body::from(serde_json::to_string(&body).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::BAD_REQUEST);

        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json["error"], "EMPTY_IMAGE");
    }

    #[tokio::test]
    async fn test_ocr_invalid_base64() {
        let app = test_router();

        let body = serde_json::json!({
            "image_base64": "!!!not-valid-base64!!!",
            "backend": "pix2text"
        });

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/api/ocr")
                    .header("content-type", "application/json")
                    .body(Body::from(serde_json::to_string(&body).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::BAD_REQUEST);

        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json["error"], "INVALID_IMAGE");
    }

    #[tokio::test]
    async fn test_stats_returns_initial_state() {
        let app = test_router();

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/api/stats")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);

        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

        assert_eq!(json["status"], "ok");
        assert_eq!(json["total_calls"], 0);
        assert_eq!(json["total_tokens"], 0);
        assert_eq!(json["estimated_cost_usd"], 0.0);
        assert_eq!(json["calls_today"], 0);
        assert_eq!(json["daily_limit"], 100);
        assert_eq!(json["remaining_today"], 100);
    }

    #[tokio::test]
    async fn test_engines_status_returns_registered_engines() {
        let app = test_router();

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/api/engines/status")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);

        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

        assert_eq!(json["status"], "ok");
        assert_eq!(json["count"], 5);

        let registered = json["registered"].as_array().unwrap();
        assert!(registered.contains(&serde_json::Value::String("openai".to_string())));
        assert!(registered.contains(&serde_json::Value::String("claude".to_string())));
        assert!(registered.contains(&serde_json::Value::String("gemini".to_string())));
        assert!(registered.contains(&serde_json::Value::String("mathpix".to_string())));
        assert!(registered.contains(&serde_json::Value::String("pix2text".to_string())));
    }
}
