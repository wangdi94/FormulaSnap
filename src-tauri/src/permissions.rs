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
        // SAFETY: AXIsProcessTrusted() 是 Apple 官方 API，返回 u8（0=false, 非0=true），
        // 无副作用，线程安全，调用总是安全的。
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
    if let Err(e) = app.emit("accessibility-permission-status", status) {
        log::debug!("发送 accessibility-permission-status 事件失败: {}", e);
    }
}

/// 打开 macOS 系统偏好设置的辅助功能权限页面。
///
/// 非 macOS 平台调用无效果。
pub fn open_accessibility_settings() {
    #[cfg(target_os = "macos")]
    {
        // macOS Ventura (13)+ 使用新的 System Settings URL scheme
        // 旧版本使用 System Preferences
        match std::process::Command::new("open")
            .arg("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
            .spawn()
        {
            Ok(child) => {
                log::debug!("已打开辅助功能设置页面 (PID: {:?})", child.id());
            }
            Err(e) => {
                log::warn!("打开辅助功能设置页面失败: {}", e);
            }
        }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_check_accessibility_returns_true_on_non_macos() {
        // On non-macOS platforms, check_accessibility() always returns true.
        // On macOS, it depends on actual system permission — we only assert
        // the non-macOS guarantee here.
        #[cfg(not(target_os = "macos"))]
        {
            assert!(check_accessibility());
        }
    }

    #[test]
    fn test_accessibility_permission_status_struct_fields() {
        let status = AccessibilityPermissionStatus {
            granted: true,
            platform: "linux".to_string(),
        };
        assert!(status.granted);
        assert_eq!(status.platform, "linux");

        let status_false = AccessibilityPermissionStatus {
            granted: false,
            platform: "macos".to_string(),
        };
        assert!(!status_false.granted);
        assert_eq!(status_false.platform, "macos");
    }

    #[test]
    fn test_accessibility_permission_status_is_serializable() {
        let status = AccessibilityPermissionStatus {
            granted: true,
            platform: "test".to_string(),
        };
        // AccessibilityPermissionStatus derives Serialize — verify it compiles
        // and serializes without panicking.
        let json = serde_json::to_string(&status).unwrap();
        assert!(json.contains("granted"));
        assert!(json.contains("platform"));
    }

    #[test]
    fn test_get_accessibility_permission_function_signature() {
        // Verify the function exists with the expected signature at compile time.
        let _f: fn() -> AccessibilityPermissionStatus = get_accessibility_permission;
    }

    #[test]
    fn test_get_accessibility_permission_returns_correct_platform() {
        let status = get_accessibility_permission();
        #[cfg(target_os = "macos")]
        assert_eq!(status.platform, "macos");
        #[cfg(not(target_os = "macos"))]
        assert_eq!(status.platform, std::env::consts::OS);
    }

    #[test]
    fn test_open_accessibility_settings_cmd_function_signature() {
        // Verify the function exists with the expected signature at compile time.
        let _f: fn() = open_accessibility_settings_cmd;
    }

    #[test]
    fn test_open_accessibility_settings_function_signature() {
        let _f: fn() = open_accessibility_settings;
    }

    #[test]
    fn test_recheck_accessibility_function_signature() {
        // Verify the function exists with the expected signature at compile time.
        // recheck_accessibility takes AppHandle and returns AccessibilityPermissionStatus.
        let _f: fn(AppHandle) -> AccessibilityPermissionStatus = recheck_accessibility;
    }
}
