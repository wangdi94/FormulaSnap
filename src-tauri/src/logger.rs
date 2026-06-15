use log::{Level, LevelFilter, Log, Metadata, Record};
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::Path;
use std::sync::Mutex;

struct FileLogger {
    file: Mutex<BufWriter<File>>,
}

impl Log for FileLogger {
    fn enabled(&self, _metadata: &Metadata) -> bool {
        true
    }

    fn log(&self, record: &Record) {
        if !self.enabled(record.metadata()) {
            return;
        }

        let now = chrono::Local::now();
        let level = match record.level() {
            Level::Error => "ERROR",
            Level::Warn => "WARN ",
            Level::Info => "INFO ",
            Level::Debug => "DEBUG",
            Level::Trace => "TRACE",
        };

        let message = format!(
            "[{}] {} {}: {}\n",
            now.format("%Y-%m-%d %H:%M:%S"),
            level,
            // 安全：module_path() 仅在宏展开不完整时返回 None，正常日志调用不会触发
            record.module_path().unwrap_or("unknown"),
            record.args()
        );

        if let Ok(mut file) = self.file.lock() {
            if file.write_all(message.as_bytes()).is_err() {
                eprint!("{}", message);
            }
        } else {
            log::warn!("日志文件 mutex 中毒，降级到 stderr 输出");
            eprint!("{}", message);
        }
    }

    fn flush(&self) {
        if let Ok(mut file) = self.file.lock() {
            if file.flush().is_err() {
                eprintln!("flush log failed");
            }
        }
    }
}

impl Drop for FileLogger {
    fn drop(&mut self) {
        if let Ok(mut file) = self.file.lock() {
            if let Err(e) = file.flush() {
                eprintln!("Drop 时日志刷新失败: {}", e);
            }
        }
    }
}

const MAX_LOG_SIZE: u64 = 10 * 1024 * 1024;
const MAX_ROTATED_FILES: u32 = 3;

/// Rotates log files: .log.3 deleted, .log.2→.log.3, .log.1→.log.2, .log→.log.1
fn rotate_logs(log_path: &Path) {
    let should_rotate = match std::fs::metadata(log_path) {
        Ok(meta) => meta.len() > MAX_LOG_SIZE,
        Err(_) => false,
    };

    if !should_rotate {
        return;
    }

    let oldest = log_path.with_extension(format!("log.{}", MAX_ROTATED_FILES));
    if let Err(e) = std::fs::remove_file(&oldest) {
        log::warn!("删除旧日志文件 {:?} 失败: {}", oldest, e);
    }

    for i in (1..MAX_ROTATED_FILES).rev() {
        let from = log_path.with_extension(format!("log.{}", i));
        let to = log_path.with_extension(format!("log.{}", i + 1));
        if let Err(e) = std::fs::rename(&from, &to) {
            log::warn!("轮转日志文件 {:?} → {:?} 失败: {}", from, to, e);
        }
    }

    if let Err(e) = std::fs::rename(log_path, log_path.with_extension("log.1")) {
        log::warn!("轮转当前日志文件 {:?} 失败: {}", log_path, e);
    }
}

pub fn init_logger(app_data_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let logs_dir = app_data_dir.join("logs");
    std::fs::create_dir_all(&logs_dir).map_err(|e| format!("创建日志目录失败: {}", e))?;

    let log_path = logs_dir.join("formulasnap.log");
    rotate_logs(&log_path);

    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("打开日志文件失败: {}", e))?;

    let logger = FileLogger {
        file: Mutex::new(BufWriter::new(file)),
    };

    log::set_boxed_logger(Box::new(logger))?;

    let level_filter = match std::env::var("FORMULASNAP_LOG_LEVEL")
        .unwrap_or_default()
        .to_lowercase()
        .as_str()
    {
        "error" => LevelFilter::Error,
        "warn" | "warning" => LevelFilter::Warn,
        "info" => LevelFilter::Info,
        "debug" => LevelFilter::Debug,
        "trace" => LevelFilter::Trace,
        _ => LevelFilter::Info,
    };
    log::set_max_level(level_filter);

    Ok(())
}

/// Stderr fallback logger — 当文件日志初始化失败时使用，Warn 及以上输出到 stderr。
struct StderrLogger;

impl Log for StderrLogger {
    fn enabled(&self, metadata: &Metadata) -> bool {
        metadata.level() <= Level::Warn
    }

    fn log(&self, record: &Record) {
        if self.enabled(record.metadata()) {
            eprintln!(
                "[{}] {}: {}",
                record.level(),
                record.module_path().unwrap_or("unknown"),
                record.args()
            );
        }
    }

    fn flush(&self) {}
}

static STDERR_LOGGER: StderrLogger = StderrLogger;

/// 注册 stderr fallback logger（`set_logger` 只能调用一次，已注册则静默忽略）。
pub fn init_stderr_fallback() {
    if log::set_logger(&STDERR_LOGGER).is_ok() {
        log::set_max_level(LevelFilter::Warn);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Once;

    static TEST_LOGGER_INIT: Once = Once::new();
    static LOG_CAPTURE: std::sync::Mutex<Vec<String>> = std::sync::Mutex::new(Vec::new());

    struct CaptureLogger;

    impl log::Log for CaptureLogger {
        fn enabled(&self, _: &log::Metadata) -> bool {
            true
        }

        fn log(&self, record: &log::Record) {
            if let Ok(mut buf) = LOG_CAPTURE.lock() {
                buf.push(format!("{}", record.args()));
            }
        }

        fn flush(&self) {}
    }

    fn setup_test_logger() {
        TEST_LOGGER_INIT.call_once(|| {
            log::set_boxed_logger(Box::new(CaptureLogger)).ok();
            log::set_max_level(log::LevelFilter::Trace);
        });
    }

    fn take_logs() -> Vec<String> {
        LOG_CAPTURE.lock().unwrap().drain(..).collect()
    }

    #[test]
    fn it_compiles() {
        // 验证模块可被测试框架发现
    }

    /// 验证 StderrLogger 实现了 Log trait 且 enabled() 正确过滤级别。
    #[test]
    fn stderr_logger_filters_by_level() {
        let logger = StderrLogger;
        let warn_meta = log::Metadata::builder()
            .level(Level::Warn)
            .target("test")
            .build();
        let info_meta = log::Metadata::builder()
            .level(Level::Info)
            .target("test")
            .build();
        let error_meta = log::Metadata::builder()
            .level(Level::Error)
            .target("test")
            .build();

        assert!(logger.enabled(&warn_meta), "Warn 应该启用");
        assert!(!logger.enabled(&info_meta), "Info 应该禁用");
        assert!(logger.enabled(&error_meta), "Error 应该启用");
    }

    /// 验证 StderrLogger::log() 不 panic。
    #[test]
    fn stderr_logger_log_does_not_panic() {
        let logger = StderrLogger;
        let record = log::RecordBuilder::new()
            .level(Level::Error)
            .target("test")
            .module_path(Some("logger::tests"))
            .args(format_args!("fallback test message"))
            .build();

        logger.log(&record);
        logger.flush();
    }

    /// 验证轮转失败时输出 warning 日志。
    #[test]
    fn test_rotation_failure_warns() {
        setup_test_logger();
        let dir = std::env::temp_dir().join("formulasnap_test_rotation_failure");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let log_path = dir.join("formulasnap.log");

        // 创建大文件触发轮转
        std::fs::write(&log_path, vec![b'x'; (MAX_LOG_SIZE + 100) as usize]).unwrap();

        // 创建目录阻挡 rename，使轮转失败
        let blocked = log_path.with_extension("log.1");
        let _ = std::fs::create_dir(&blocked);

        rotate_logs(&log_path);

        let logs = take_logs();
        assert!(
            logs.iter().any(|l| l.contains("失败")),
            "轮转失败时应输出 warning，实际日志: {:?}",
            logs
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    /// 验证 mutex 中毒时输出 diagnostic warning。
    #[test]
    fn test_mutex_poison_warns() {
        setup_test_logger();
        let dir = std::env::temp_dir().join("formulasnap_test_mutex_poison");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let log_path = dir.join("test.log");
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .unwrap();

        let logger = FileLogger {
            file: Mutex::new(BufWriter::new(file)),
        };

        // 通过 panic 中毒 mutex
        let poison_result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _guard = logger.file.lock().unwrap();
            panic!("intentional poison");
        }));
        assert!(poison_result.is_err(), "应触发 panic");
        assert!(logger.file.is_poisoned(), "mutex 应已中毒");

        let record = log::RecordBuilder::new()
            .level(Level::Error)
            .target("test")
            .module_path(Some("logger::tests"))
            .args(format_args!("test message after poison"))
            .build();

        logger.log(&record);

        let logs = take_logs();
        assert!(
            logs.iter()
                .any(|l| l.contains("中毒") || l.contains("mutex")),
            "mutex 中毒时应输出 diagnostic warning，实际日志: {:?}",
            logs
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    /// 验证 BufWriter 正确缓冲日志——多次写入不立即刷盘，显式 flush 后才写入。
    #[test]
    fn test_buffered_logging() {
        let dir = std::env::temp_dir().join("formulasnap_test_buffered_logging");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let log_path = dir.join("test.log");

        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .unwrap();

        let logger = FileLogger {
            file: Mutex::new(BufWriter::new(file)),
        };

        for i in 0..10 {
            let msg = format!("buffered message {}", i);
            let record = log::RecordBuilder::new()
                .level(Level::Info)
                .target("test")
                .module_path(Some("logger::tests"))
                .args(format_args!("{}", msg))
                .build();
            logger.log(&record);
        }

        let size_before_flush = std::fs::metadata(&log_path).unwrap().len();
        assert_eq!(
            size_before_flush, 0,
            "BufWriter 应缓冲日志，flush 前文件大小应为 0"
        );

        logger.flush();
        let size_after_flush = std::fs::metadata(&log_path).unwrap().len();
        assert!(
            size_after_flush > 0,
            "flush 后文件大小应 > 0，实际: {}",
            size_after_flush
        );

        drop(logger);

        let _ = std::fs::remove_dir_all(&dir);
    }
}
