//! macOS Accessibility 权限检测与降级方案。
//!
//! - macOS: 通过 `AXIsProcessTrusted()` FFI 调用检测辅助功能权限。
//! - 非 macOS: 始终返回 `true`（无需特殊权限）。

use tauri::{AppHandle, Emitter};

#[cfg(target_os = "macos")]
#[link(name = "ApplicationServices", kind = "framework")]
extern "C" {
    /// Returns `true` if the current process is trusted for accessibility.
    /// <https://developer.apple.com/documentation/applicationservices/1459394-axisprocesstrusted>
    fn AXIsProcessTrusted() -> u8;
}

/// 检测当前进程是否拥有 macOS Accessibility（辅助功能）权限。
///
/// - macOS: 调用 `AXIsProcessTrusted()`。
/// - 其他平台: 始终返回 `true`。
pub fn check_accessibility() -> bool {
    #[cfg(target_os = "macos")]
    {
        unsafe { AXIsProcessTrusted() != 0 }
    }

    #[cfg(not(target_os = "macos"))]
    {
        true
    }
}

/// 向前端发送权限状态事件，前端负责展示引导对话框。
///
/// 事件名: `accessibility-permission-status`
/// Payload: `AccessibilityPermissionStatus` JSON
pub fn emit_permission_status(app: &AppHandle) {
    let granted = check_accessibility();
    let status = AccessibilityPermissionStatus {
        granted,
        #[cfg(target_os = "macos")]
        platform: "macos".to_string(),
        #[cfg(not(target_os = "macos"))]
        platform: std::env::consts::OS.to_string(),
    };
    let _ = app.emit("accessibility-permission-status", status);
}

/// 打开 macOS 系统偏好设置的辅助功能权限页面。
///
/// 非 macOS 平台调用无效果。
pub fn open_accessibility_settings() {
    #[cfg(target_os = "macos")]
    {
        // macOS Ventura (13)+ 使用新的 System Settings URL scheme
        // 旧版本使用 System Preferences
        let _ = std::process::Command::new("open")
            .arg("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
            .spawn();
    }
}

/// 在启动时执行权限检查：若未授权则向前端发送引导事件。
///
/// 此函数应在 Tauri `setup` 闭包中调用。无论权限状态如何，
/// 应用都**不会**阻塞——降级方案始终可用（Tray 菜单点击触发截图）。
pub fn check_and_guide(app: &AppHandle) {
    let granted = check_accessibility();

    if !granted {
        eprintln!(
            "[permissions] Accessibility permission NOT granted. \
             Global shortcuts may not work. \
             Users can still take screenshots via the tray menu."
        );
        emit_permission_status(app);
    } else {
        eprintln!("[permissions] Accessibility permission granted.");
    }
}

/// 权限状态结构体，序列化后发送给前端。
#[derive(serde::Serialize, Clone)]
pub struct AccessibilityPermissionStatus {
    pub granted: bool,
    pub platform: String,
}

/// 前端可调用的命令：获取当前 Accessibility 权限状态。
#[tauri::command]
pub fn get_accessibility_permission() -> AccessibilityPermissionStatus {
    AccessibilityPermissionStatus {
        granted: check_accessibility(),
        #[cfg(target_os = "macos")]
        platform: "macos".to_string(),
        #[cfg(not(target_os = "macos"))]
        platform: std::env::consts::OS.to_string(),
    }
}

/// 前端可调用的命令：打开系统辅助功能设置页面。
#[tauri::command]
pub fn open_accessibility_settings_cmd() {
    open_accessibility_settings();
}

/// 前端可调用的命令：重新检查权限并广播状态。
#[tauri::command]
pub fn recheck_accessibility(app: AppHandle) -> AccessibilityPermissionStatus {
    let status = get_accessibility_permission();
    let _ = app.emit("accessibility-permission-status", status.clone());
    status
}
