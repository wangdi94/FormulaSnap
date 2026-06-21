pub mod routes;

use axum::{middleware, Router};
use std::time::Instant;
use tokio::net::TcpListener;
use tower_http::cors::{Any, CorsLayer};
use tracing::info;

/// 构建应用 Router：挂载所有路由 + CORS + 请求日志中间件
fn build_router() -> Router {
    // CORS 配置：允许前端开发服务器和 Tauri webview
    let cors = CorsLayer::new()
        .allow_origin([
            "http://localhost:1420".parse::<axum::http::HeaderValue>().unwrap(),
            "tauri://localhost".parse::<axum::http::HeaderValue>().unwrap(),
            "http://localhost:8477".parse::<axum::http::HeaderValue>().unwrap(),
        ])
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        .route("/health", axum::routing::get(routes::health))
        .route("/shutdown", axum::routing::post(routes::shutdown))
        .route("/api/ocr", axum::routing::post(routes::ocr))
        .route("/api/stats", axum::routing::get(routes::stats))
        .route("/api/engines/status", axum::routing::get(routes::engines_status))
        .route("/api/validate-config", axum::routing::post(routes::validate_config))
        .route("/api/keys", axum::routing::get(routes::get_keys).put(routes::save_key))
        .layer(middleware::from_fn(request_logging))
        .layer(cors)
}

/// 请求日志中间件：记录方法、路径、状态码、耗时（跳过 /health）
async fn request_logging(
    req: axum::extract::Request,
    next: axum::middleware::Next,
) -> axum::response::Response {
    let method = req.method().clone();
    let uri = req.uri().clone();
    let path = uri.path().to_string();

    // 跳过 /health 的日志，避免刷屏
    if path == "/health" {
        return next.run(req).await;
    }

    let start = Instant::now();
    let response = next.run(req).await;
    let elapsed = start.elapsed();

    info!(
        method = %method,
        path = %path,
        status = %response.status().as_u16(),
        elapsed_ms = %elapsed.as_millis(),
        "请求处理完成"
    );

    response
}

/// 启动 HTTP 服务器，绑定 127.0.0.1:8477，支持 SIGTERM 优雅关闭
pub async fn run_server() {
    let router = build_router();

    let listener = TcpListener::bind("127.0.0.1:8477")
        .await
        .expect("无法绑定到 127.0.0.1:8477");

    info!("FormulaSnap Rust Sidecar 监听 127.0.0.1:8477");

    // 使用 tokio graceful shutdown：SIGTERM / ctrl_c 时停止接受新连接
    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect("服务器运行出错");
}

/// 等待 SIGTERM 或 Ctrl+C 信号
async fn shutdown_signal() {
    let ctrl_c = tokio::signal::ctrl_c();

    #[cfg(unix)]
    {
        let mut sigterm =
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
                .expect("无法注册 SIGTERM 处理器");

        tokio::select! {
            _ = ctrl_c => {
                info!("收到 Ctrl+C 信号，正在优雅关闭...");
            }
            _ = sigterm.recv() => {
                info!("收到 SIGTERM 信号，正在优雅关闭...");
            }
        }
    }

    #[cfg(not(unix))]
    {
        ctrl_c.await.ok();
        info!("收到关闭信号，正在优雅关闭...");
    }
}
