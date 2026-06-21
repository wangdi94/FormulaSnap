mod db;
mod history;
mod hotkey;
mod logger;
pub mod permissions;
mod screenshot;
mod sidecar;
mod tray;

use std::sync::Mutex;
use tauri::Manager;
use tauri::WindowEvent;

use base64::Engine;

/// 数据库连接包装器。
///
/// 使用 `std::sync::Mutex` 而非 `parking_lot::Mutex`，原因：
/// 1. 标准库，无额外依赖
/// 2. SQLite 是单写者模型，锁竞争极低，`parking_lot` 的性能优势可忽略
/// 3. 已有中毒处理代码（`sidecar.rs` 中使用 `match` 模式处理 `PoisonError`）
pub struct DbConn(pub Mutex<rusqlite::Connection>);

/// 截取全屏并返回 base64 编码的 PNG 图片。
/// 前端可通过 invoke('capture_screen_base64') 调用。
#[tauri::command]
fn capture_screen_base64() -> Result<String, String> {
    let png_bytes = screenshot::capture_screen()?;
    Ok(base64::engine::general_purpose::STANDARD.encode(&png_bytes))
}

/// 截取指定区域并返回 base64 编码的 PNG 图片。
#[tauri::command]
fn capture_region_base64(x: u32, y: u32, width: u32, height: u32) -> Result<String, String> {
    let png_bytes = screenshot::capture_region(x, y, width, height)?;
    Ok(base64::engine::general_purpose::STANDARD.encode(&png_bytes))
}

/// 截取全屏并返回 base64（供区域选择使用）。
#[tauri::command]
fn capture_screen_for_selection() -> Result<String, String> {
    capture_screen_base64()
}

/// 打开透明全屏区域选择窗口。
#[tauri::command]
fn open_selection_window(app: tauri::AppHandle) -> Result<(), String> {
    use tauri::WebviewWindowBuilder;

    if let Some(existing) = app.get_webview_window("selection") {
        if let Err(e) = existing.eval("window.location.reload()") {
            log::warn!("刷新选择窗口失败: {}", e);
        }
        if let Err(e) = existing.show() {
            log::warn!("显示选择窗口失败: {}", e);
        }
        if let Err(e) = existing.set_focus() {
            log::warn!("聚焦选择窗口失败: {}", e);
        }
        return Ok(());
    }

    let sel_win = WebviewWindowBuilder::new(
        &app,
        "selection",
        tauri::WebviewUrl::App("/selection".into()),
    )
    .title("选择区域")
    .decorations(false)
    .fullscreen(true)
    .always_on_top(true)
    .visible(false)
    .build()
    .map_err(|e| e.to_string())?;

    // 等待 WebView2 初始化完成后再显示，避免白屏竞态
    std::thread::sleep(std::time::Duration::from_millis(200));

    sel_win.show().map_err(|e| e.to_string())?;
    sel_win.set_focus().map_err(|e| e.to_string())?;

    Ok(())
}

#[tauri::command]
fn insert_history(
    state: tauri::State<'_, DbConn>,
    latex: String,
    backend: String,
    confidence: f64,
    screenshot_path: Option<String>,
) -> Result<i64, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    history::insert(
        &conn,
        &latex,
        &backend,
        confidence,
        screenshot_path.as_deref(),
    )
    .map_err(|e| e.to_string())
}

#[tauri::command]
fn get_history(
    state: tauri::State<'_, DbConn>,
    limit: i64,
    offset: i64,
) -> Result<Vec<history::HistoryEntry>, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    history::list(&conn, limit, offset).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_history_by_id(
    state: tauri::State<'_, DbConn>,
    id: i64,
) -> Result<Option<history::HistoryEntry>, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    history::get_by_id(&conn, id).map_err(|e| e.to_string())
}

#[tauri::command]
fn delete_history(state: tauri::State<'_, DbConn>, id: i64) -> Result<bool, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    history::delete(&conn, id).map_err(|e| e.to_string())
}

#[tauri::command]
fn search_history(
    state: tauri::State<'_, DbConn>,
    query: String,
) -> Result<Vec<history::HistoryEntry>, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    history::search(&conn, &query).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_setting(state: tauri::State<'_, DbConn>, key: String) -> Result<Option<String>, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare("SELECT value FROM settings WHERE key = ?1")
        .map_err(|e| e.to_string())?;
    let mut rows = stmt
        .query_map([&key], |row| row.get(0))
        .map_err(|e| e.to_string())?;
    match rows.next() {
        Some(row) => Ok(Some(row.map_err(|e| e.to_string())?)),
        None => Ok(None),
    }
}

#[tauri::command]
fn save_setting(state: tauri::State<'_, DbConn>, key: String, value: String) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?1, ?2)",
        (&key, &value),
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init());

    // updater 插件仅在 macOS 和 Windows 上启用
    #[cfg(any(target_os = "macos", target_os = "windows"))]
    let builder = builder.plugin(tauri_plugin_updater::Builder::new().build());

    builder
        .invoke_handler(tauri::generate_handler![
            get_history,
            insert_history,
            get_history_by_id,
            delete_history,
            search_history,
            get_setting,
            save_setting,
            capture_screen_base64,
            capture_region_base64,
            capture_screen_for_selection,
            open_selection_window,
            sidecar::get_sidecar_port,
            permissions::get_accessibility_permission,
            permissions::open_accessibility_settings_cmd,
            permissions::recheck_accessibility
        ])
        .setup(|app| {
            let app_dir = app
                .path()
                .app_data_dir()
                .map_err(|e| format!("获取应用数据目录失败: {}", e))?;
            std::fs::create_dir_all(&app_dir)
                .map_err(|e| format!("创建应用数据目录失败: {}", e))?;

            if let Err(e) = logger::init_logger(&app_dir) {
                eprintln!("Failed to initialize logger: {}", e);
                logger::init_stderr_fallback();
            }

            let prev = std::panic::take_hook();
            std::panic::set_hook(Box::new(move |panic_info| {
                log::logger().flush();
                prev(panic_info);
            }));

            let db_path = app_dir.join("app.db");

            let conn = rusqlite::Connection::open(&db_path)
                .map_err(|e| format!("打开数据库失败: {}", e))?;
            db::initialize_database(&conn).map_err(|e| format!("初始化数据库失败: {}", e))?;

            app.manage(DbConn(Mutex::new(conn)));

            permissions::check_and_guide(app.handle());

            if let Err(e) = hotkey::register_hotkeys(app.handle()) {
                log::error!("Failed to register hotkeys: {}", e);
            }

            if let Err(e) = tray::create_tray(app.handle()) {
                log::error!("Failed to create tray: {}", e);
            }

            if let Err(e) = sidecar::start_sidecar(app.handle()) {
                log::error!("Failed to start sidecar: {}", e);
            }

            // 窗口关闭时最小化到系统托盘，而非退出应用
            if let Some(main_window) = app.get_webview_window("main") {
                let win = main_window.clone();
                main_window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        if let Err(e) = win.hide() {
                            log::warn!("隐藏主窗口失败: {}", e);
                        }
                    }
                });
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .unwrap_or_else(|e| {
            eprintln!("Tauri 应用构建失败: {}", e);
            // 安全：构建失败发生在 setup 之前，sidecar 子进程尚未启动，
            // 因此无需清理 sidecar 资源。exit(1) 在此场景下是安全的。
            std::process::exit(1);
        })
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                sidecar::stop_sidecar(app_handle);
            }
        });
}
