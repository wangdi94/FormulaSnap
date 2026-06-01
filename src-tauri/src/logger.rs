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
            // mutex 中毒时降级到 stderr
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
    let _ = std::fs::remove_file(&oldest);

    for i in (1..MAX_ROTATED_FILES).rev() {
        let from = log_path.with_extension(format!("log.{}", i));
        let to = log_path.with_extension(format!("log.{}", i + 1));
        let _ = std::fs::rename(&from, &to);
    }

    let _ = std::fs::rename(log_path, log_path.with_extension("log.1"));
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
