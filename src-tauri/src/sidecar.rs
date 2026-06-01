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
        let url = format!("http://localhost:{}/shutdown", SIDECAR_PORT);
        let shutdown_ok = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(2))
            .build()
            .ok()
            .and_then(|client| client.post(&url).send().ok())
            .is_some();

        if shutdown_ok {
            log::info!("已发送 shutdown 请求，等待 sidecar 退出...");
            std::thread::sleep(Duration::from_millis(500));
        }

        if let Ok(mut guard) = self.child.lock() {
            if let Some(child) = guard.take() {
                if let Err(e) = child.kill() {
                    log::error!("Drop: 关闭 sidecar 失败: {}", e);
                } else {
                    log::info!("Drop: sidecar 进程已关闭");
                }
            }
        }
    }
}

/// 启动 Python sidecar 子进程，并在后台线程中轮询健康检查。
pub fn start_sidecar(app: &AppHandle) -> Result<(), String> {
    let sidecar_command = app
        .shell()
        .sidecar("formulasnap-sidecar")
        .map_err(|e| format!("创建 sidecar 命令失败: {}", e))?;

    let (rx, child) = sidecar_command
        .spawn()
        .map_err(|e| format!("启动 sidecar 进程失败: {}", e))?;

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
