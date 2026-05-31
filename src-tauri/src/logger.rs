use log::{Level, LevelFilter, Log, Metadata, Record};
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::sync::Mutex;

struct FileLogger {
    file: Mutex<File>,
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
            record.module_path().unwrap_or("unknown"),
            record.args()
        );

        if let Ok(mut file) = self.file.lock() {
            if file.write_all(message.as_bytes()).is_err() {
                eprint!("{}", message);
            }
            if file.flush().is_err() {
                eprintln!("[logger] flush failed");
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

pub fn init_logger(app_data_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let logs_dir = app_data_dir.join("logs");
    std::fs::create_dir_all(&logs_dir)
        .map_err(|e| format!("创建日志目录失败: {}", e))?;

    let log_path = logs_dir.join("formulasnap.log");
    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("打开日志文件失败: {}", e))?;

    let logger = FileLogger {
        file: Mutex::new(file),
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
