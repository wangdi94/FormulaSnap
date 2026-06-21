mod api;
mod cache;
mod cost_tracker;
mod engines;
mod key_manager;
mod logging;
mod response_parser;
mod types;

#[tokio::main]
async fn main() {
    // 初始化日志
    logging::setup_logging();

    tracing::info!("FormulaSnap Rust Sidecar 启动中...");

    // 启动 HTTP 服务器（阻塞直到收到关闭信号）
    api::run_server().await;
}