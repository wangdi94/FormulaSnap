/// 日志配置模块
///
/// 提供统一的日志初始化功能，包括：
/// - 控制台输出（INFO 级别）
/// - 文件输出（DEBUG 级别，按日轮转，保留 3 个备份）
/// - 日志目录：`~/.config/formulasnap/logs/`
///
/// 注意：`tracing-appender` 仅支持基于时间的轮转，不支持基于大小的轮转。
/// 本实现使用按日轮转作为替代方案。
use std::fs;

use tracing::level_filters::LevelFilter;
use tracing_appender::rolling::{RollingFileAppender, Rotation};
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::Layer;

/// 初始化日志系统
///
/// 配置双输出：
/// - 控制台：INFO 级别
/// - 文件：DEBUG 级别，按日轮转，最多保留 4 个文件（当前 + 3 备份）
pub fn setup_logging() {
    // 确定日志目录（跨平台）
    let log_dir = dirs::config_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("formulasnap")
        .join("logs");

    // 确保日志目录存在
    fs::create_dir_all(&log_dir).expect("无法创建日志目录");

    // 控制台输出层（INFO 级别）
    let console_layer = tracing_subscriber::fmt::layer()
        .with_writer(std::io::stdout)
        .with_filter(LevelFilter::INFO);

    // 文件输出层（DEBUG 级别，按日轮转，保留 3 个备份）
    let file_appender = RollingFileAppender::builder()
        .rotation(Rotation::DAILY)
        .filename_prefix("formulasnap-sidecar")
        .max_log_files(4) // 当前 + 3 备份
        .build(&log_dir)
        .expect("无法初始化文件日志追加器");

    let file_layer = tracing_subscriber::fmt::layer()
        .with_writer(file_appender)
        .with_filter(LevelFilter::DEBUG);

    // 初始化订阅者
    tracing_subscriber::registry()
        .with(console_layer)
        .with(file_layer)
        .init();

    tracing::info!("日志系统初始化完成（目录：{}）", log_dir.display());
}
