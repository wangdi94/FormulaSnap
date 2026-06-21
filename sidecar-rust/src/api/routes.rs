use axum::Json;
use serde_json::json;

// ── 健康检查 ─────────────────────────────────────────────────────────────

/// GET /health — 健康检查，返回服务状态和已注册引擎
pub async fn health() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "engines": []
    }))
}

// ── 关闭 ─────────────────────────────────────────────────────────────────

/// POST /shutdown — 请求关闭 sidecar（占位实现）
pub async fn shutdown() -> Json<serde_json::Value> {
    // TODO: 实际关闭逻辑将在此实现
    Json(json!({
        "status": "ok",
        "message": "shutdown requested"
    }))
}

// ── OCR 识别 ─────────────────────────────────────────────────────────────

/// POST /api/ocr — OCR 识别请求（占位实现）
pub async fn ocr() -> Json<serde_json::Value> {
    // TODO: 将接入引擎管理器进行实际 OCR
    Json(json!({
        "status": "ok",
        "message": "OCR endpoint placeholder"
    }))
}

// ── 统计信息 ─────────────────────────────────────────────────────────────

/// GET /api/stats — 返回调用统计（占位实现）
pub async fn stats() -> Json<serde_json::Value> {
    // TODO: 将返回实际统计信息
    Json(json!({
        "status": "ok",
        "total_calls": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "calls_today": 0,
        "daily_limit": 100,
        "remaining_today": 100
    }))
}

// ── 引擎状态 ─────────────────────────────────────────────────────────────

/// GET /api/engines/status — 返回已注册引擎状态（占位实现）
pub async fn engines_status() -> Json<serde_json::Value> {
    // TODO: 将查询引擎管理器获取实际状态
    Json(json!({
        "status": "ok",
        "registered": [],
        "count": 0
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
