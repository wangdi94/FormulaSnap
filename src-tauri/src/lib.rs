mod db;
mod history;
mod hotkey;
mod logger;
pub mod permissions;
mod screenshot;
mod sidecar;
mod tray;

use std::sync::Mutex;
use tauri::WindowEvent;
use tauri::Manager;

pub struct DbConn(pub Mutex<rusqlite::Connection>);

/// 截取全屏并返回 base64 编码的 PNG 图片。
/// 前端可通过 invoke('capture_screen_base64') 调用。
#[tauri::command]
fn capture_screen_base64() -> Result<String, String> {
    let png_bytes = screenshot::capture_screen().map_err(|e| e.to_string())?;
    use base64::Engine;
    Ok(base64::engine::general_purpose::STANDARD.encode(&png_bytes))
}

/// 截取指定区域并返回 base64 编码的 PNG 图片。
#[tauri::command]
fn capture_region_base64(x: u32, y: u32, width: u32, height: u32) -> Result<String, String> {
    let png_bytes = screenshot::capture_region(x, y, width, height).map_err(|e| e.to_string())?;
    use base64::Engine;
    Ok(base64::engine::general_purpose::STANDARD.encode(&png_bytes))
}

/// 截取全屏并返回 base64（供区域选择使用）。
#[tauri::command]
fn capture_screen_for_selection() -> Result<String, String> {
    let png_bytes = screenshot::capture_screen().map_err(|e| e.to_string())?;
    use base64::Engine;
    Ok(base64::engine::general_purpose::STANDARD.encode(&png_bytes))
}

/// 打开透明全屏区域选择窗口。
#[tauri::command]
fn open_selection_window(app: tauri::AppHandle) -> Result<(), String> {
    use tauri::WebviewWindowBuilder;

    if let Some(existing) = app.get_webview_window("selection") {
        let _ = existing.show();
        let _ = existing.set_focus();
        return Ok(());
    }

    WebviewWindowBuilder::new(&app, "selection", tauri::WebviewUrl::App("/selection".into()))
        .title("选择区域")
        .transparent(true)
        .decorations(false)
        .fullscreen(true)
        .always_on_top(true)
        .build()
        .map_err(|e| e.to_string())?;

    Ok(())
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

    builder.invoke_handler(tauri::generate_handler![
            get_history,
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
                .expect("failed to get app data dir");
            std::fs::create_dir_all(&app_dir).expect("failed to create app data dir");

            if let Err(e) = logger::init_logger(&app_dir) {
                eprintln!("Failed to initialize logger: {}", e);
            }

            let db_path = app_dir.join("app.db");

            let conn = rusqlite::Connection::open(&db_path).expect("failed to open database");
            db::initialize_database(&conn).expect("failed to initialize database");

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
                        let _ = win.hide();
                    }
                });
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                sidecar::stop_sidecar(app_handle);
            }
        });
}
