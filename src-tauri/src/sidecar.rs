use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Sidecar HTTP 端口（与 Python sidecar 的 uvicorn 配置一致）
pub const SIDECAR_PORT: u16 = 8477;

/// 健康检查超时时间
const HEALTH_TIMEOUT: Duration = Duration::from_secs(30);

/// 健康检查轮询间隔
const HEALTH_INTERVAL: Duration = Duration::from_millis(500);

/// 存储 sidecar 子进程句柄
pub struct SidecarProcess(pub Mutex<Option<CommandChild>>);

/// 启动 Python sidecar 子进程，并在后台线程中轮询健康检查。
pub fn start_sidecar(app: &AppHandle) -> Result<(), String> {
    // 创建 sidecar 命令（对应 bundle.externalBin 配置）
    let sidecar_command = app
        .shell()
        .sidecar("formulasnap-sidecar")
        .map_err(|e| format!("创建 sidecar 命令失败: {}", e))?;

    // 启动子进程
    let (mut _rx, child) = sidecar_command
        .spawn()
        .map_err(|e| format!("启动 sidecar 进程失败: {}", e))?;

    // 保存子进程句柄到 Tauri 状态
    app.manage(SidecarProcess(Mutex::new(Some(child))));

    // 在后台线程中轮询健康检查，就绪后发送事件
    let app_handle = app.clone();
    std::thread::spawn(move || {
        let url = format!("http://localhost:{}/health", SIDECAR_PORT);

        match poll_health(&url, HEALTH_TIMEOUT, HEALTH_INTERVAL) {
            Ok(()) => {
                println!("[sidecar] Python sidecar 已就绪 (port {})", SIDECAR_PORT);
                let _ = app_handle.emit("sidecar://ready", ());
            }
            Err(e) => {
                eprintln!("[sidecar] 健康检查失败: {}", e);
                let _ = app_handle.emit("sidecar://error", e);
            }
        }
    });

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
    let mut guard = state.0.lock().unwrap();

    if let Some(child) = guard.take() {
        println!("[sidecar] 正在关闭 Python sidecar...");
        // CommandChild::kill() 发送 SIGKILL（Unix）或 TerminateProcess（Windows）
        if let Err(e) = child.kill() {
            eprintln!("[sidecar] 关闭 sidecar 失败: {}", e);
        } else {
            println!("[sidecar] Python sidecar 已关闭");
        }
    }
}

/// Tauri command：获取 sidecar 端口
#[tauri::command]
pub fn get_sidecar_port() -> u16 {
    SIDECAR_PORT
}
