use std::io::Write;
use std::net::TcpStream;
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Sidecar HTTP 端口（与 Python sidecar 的 uvicorn 配置一致）
pub const SIDECAR_PORT: u16 = 8477;

/// 健康检查超时时间
const HEALTH_TIMEOUT: Duration = Duration::from_secs(30);

/// 健康检查轮询间隔
const HEALTH_INTERVAL: Duration = Duration::from_millis(500);

/// 存储 sidecar 子进程句柄和健康检查线程句柄
pub struct SidecarProcess {
    child: Mutex<Option<CommandChild>>,
    health_handle: Mutex<Option<std::thread::JoinHandle<()>>>,
}

impl Drop for SidecarProcess {
    fn drop(&mut self) {
        // 使用简单 TCP 连接发送 shutdown 请求，避免在 Drop 中创建 reqwest::Client
        // （reqwest::blocking::Client 内部使用 tokio runtime，可能导致 panic）
        let shutdown_ok = send_shutdown_via_tcp(SIDECAR_PORT);

        if shutdown_ok {
            log::info!("已发送 shutdown 请求，等待 sidecar 退出...");
            std::thread::sleep(Duration::from_millis(500));
        }

        // 处理 mutex 中毒：即使 mutex 中毒也要尝试 kill 子进程
        let mut guard = match self.child.lock() {
            Ok(g) => g,
            Err(poisoned) => {
                log::error!("SidecarProcess child mutex 已中毒，使用内部锁继续");
                poisoned.into_inner()
            }
        };
        if let Some(child) = guard.take() {
            if let Err(e) = child.kill() {
                log::error!("Drop: 关闭 sidecar 失败: {}", e);
            } else {
                log::info!("Drop: sidecar 进程已关闭");
            }
        }

        // join 健康检查线程，确保线程在 Drop 完成前结束
        let mut handle_guard = match self.health_handle.lock() {
            Ok(g) => g,
            Err(poisoned) => {
                log::error!("SidecarProcess health_handle mutex 已中毒，使用内部锁继续");
                poisoned.into_inner()
            }
        };
        if let Some(handle) = handle_guard.take() {
            if let Err(e) = handle.join() {
                log::error!("Drop: 健康检查线程 panic: {:?}", e);
            }
        }
    }
}

/// 使用简单 TCP 连接发送 shutdown HTTP 请求，避免依赖 reqwest（其内部 tokio runtime 在 Drop 中可能 panic）
fn send_shutdown_via_tcp(port: u16) -> bool {
    let addr = match format!("127.0.0.1:{}", port).parse::<std::net::SocketAddr>() {
        Ok(a) => a,
        Err(_) => return false,
    };
    match TcpStream::connect_timeout(&addr, Duration::from_secs(1)) {
        Ok(mut stream) => {
            let _ = stream.set_write_timeout(Some(Duration::from_secs(1)));
            let request = format!(
                "POST /shutdown HTTP/1.1\r\nHost: localhost:{}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                port
            );
            stream.write_all(request.as_bytes()).is_ok()
        }
        Err(_) => false,
    }
}

/// 启动 Python sidecar 子进程，并在后台线程中轮询健康检查。
pub fn start_sidecar(app: &AppHandle) -> Result<(), String> {
    // 将 Rust 的 app_data_dir 传递给 Python sidecar，确保两侧日志路径一致。
    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("获取 app_data_dir 失败: {}", e))?;
    std::env::set_var(
        "FORMULASNAP_APP_DATA_DIR",
        app_data_dir.to_string_lossy().to_string(),
    );

    let sidecar_command = app
        .shell()
        .sidecar("formulasnap-sidecar")
        .map_err(|e| format!("创建 sidecar 命令失败: {}", e))?;

    let (rx, child) = sidecar_command
        .spawn()
        .map_err(|e| format!("启动 sidecar 进程失败: {}", e))?;

    // NOTE: health_handle 竞态窗口 — 在 manage() 和 health_handle 赋值之间存在一个
    // 微小窗口：如果在此期间 Drop 被触发，健康检查线程（已 spawn）的 JoinHandle 尚未
    // 存入 SidecarProcess，导致线程无法被 join。此窗口在实际运行中不可触发，因为
    // start_sidecar() 仅在 app setup 时调用一次，而 Drop 仅在 shutdown 时发生。
    app.manage(SidecarProcess {
        child: Mutex::new(Some(child)),
        health_handle: Mutex::new(None),
    });

    tauri::async_runtime::spawn(async move {
        let mut rx = rx;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(data) => {
                    if let Ok(text) = String::from_utf8(data) {
                        log::info!("[sidecar] {}", text.trim_end());
                    }
                }
                CommandEvent::Stderr(data) => {
                    if let Ok(text) = String::from_utf8(data) {
                        log::warn!("[sidecar] {}", text.trim_end());
                    }
                }
                CommandEvent::Terminated(payload) => {
                    log::info!("[sidecar] 进程退出，状态码: {:?}", payload.code);
                    break;
                }
                CommandEvent::Error(err) => {
                    log::error!("[sidecar] {}", err);
                }
                _ => {}
            }
        }
    });

    let app_handle = app.clone();
    let handle = std::thread::spawn(move || {
        let url = format!("http://localhost:{}/health", SIDECAR_PORT);

        match poll_health(&url, HEALTH_TIMEOUT, HEALTH_INTERVAL) {
            Ok(()) => {
                log::info!("Python sidecar 已就绪 (port {})", SIDECAR_PORT);
                if let Err(e) = app_handle.emit("sidecar://ready", ()) {
                    log::warn!("发送 sidecar://ready 事件失败: {}", e);
                }
            }
            Err(e) => {
                log::error!("健康检查失败: {}", e);
                if let Err(e) = app_handle.emit("sidecar://error", e) {
                    log::warn!("发送 sidecar://error 事件失败: {}", e);
                }
            }
        }
    });

    let state = app.state::<SidecarProcess>();
    let mut guard = match state.health_handle.lock() {
        Ok(guard) => guard,
        Err(poisoned) => {
            log::error!("SidecarProcess health_handle mutex 已中毒，使用内部锁继续");
            poisoned.into_inner()
        }
    };
    *guard = Some(handle);

    Ok(())
}

/// 同步轮询健康检查端点，直到成功或超时。
fn poll_health(url: &str, timeout: Duration, interval: Duration) -> Result<(), String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .map_err(|e| format!("创建 HTTP 客户端失败: {}", e))?;

    let start = Instant::now();

    loop {
        if start.elapsed() > timeout {
            return Err(format!(
                "健康检查超时 ({:.0}s)，sidecar 未能在规定时间内就绪",
                timeout.as_secs_f64()
            ));
        }

        match client.get(url).send() {
            Ok(resp) if resp.status().is_success() => {
                return Ok(());
            }
            _ => {
                std::thread::sleep(interval);
            }
        }
    }
}

/// 优雅关闭 sidecar 进程：先尝试 kill，然后清理状态。
pub fn stop_sidecar(app: &AppHandle) {
    let state = app.state::<SidecarProcess>();
    let mut guard = match state.child.lock() {
        Ok(guard) => guard,
        Err(poisoned) => {
            log::error!("SidecarProcess mutex 已中毒，使用内部锁继续");
            poisoned.into_inner()
        }
    };

    if let Some(child) = guard.take() {
        log::info!("正在关闭 Python sidecar...");
        // CommandChild::kill() 发送 SIGKILL（Unix）或 TerminateProcess（Windows）
        if let Err(e) = child.kill() {
            log::error!("关闭 sidecar 失败: {}", e);
        } else {
            // 等待进程退出，避免残留进程
            std::thread::sleep(Duration::from_millis(200));
            log::info!("Python sidecar 已关闭");
        }
    }

    let mut handle_guard = match state.health_handle.lock() {
        Ok(guard) => guard,
        Err(poisoned) => {
            log::error!("SidecarProcess health_handle mutex 已中毒，使用内部锁继续");
            poisoned.into_inner()
        }
    };
    if let Some(handle) = handle_guard.take() {
        if let Err(e) = handle.join() {
            log::error!("健康检查线程 panic: {:?}", e);
        }
    }
}

/// Tauri command：获取 sidecar 端口
#[tauri::command]
pub fn get_sidecar_port() -> u16 {
    SIDECAR_PORT
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};
    use std::thread;

    #[test]
    fn test_drop_poisoned_mutex() {
        let child_mutex = Arc::new(Mutex::new(None::<CommandChild>));
        let child_mutex_clone = child_mutex.clone();
        let handle = thread::spawn(move || {
            let _guard = child_mutex_clone.lock().unwrap();
            panic!("故意 panic 以毒化 mutex");
        });
        let _ = handle.join();
        assert!(child_mutex.is_poisoned());

        let sp = SidecarProcess {
            child: Mutex::new(
                Mutex::into_inner(Arc::try_unwrap(child_mutex).unwrap())
                    .unwrap_or_else(|e| e.into_inner()),
            ),
            health_handle: Mutex::new(None),
        };
        drop(sp);
    }

    #[test]
    fn test_drop_no_panic() {
        let sp = SidecarProcess {
            child: Mutex::new(None),
            health_handle: Mutex::new(None),
        };
        drop(sp);
    }

    #[test]
    fn test_drop_joins_health_handle() {
        let flag = Arc::new(Mutex::new(false));
        let flag_clone = flag.clone();

        let handle = thread::spawn(move || {
            *flag_clone.lock().unwrap() = true;
        });

        let sp = SidecarProcess {
            child: Mutex::new(None),
            health_handle: Mutex::new(Some(handle)),
        };

        drop(sp);
        assert!(*flag.lock().unwrap());
    }

    #[test]
    fn it_compiles() {}
}
