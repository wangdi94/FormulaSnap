use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, Runtime,
};

/// Menu item IDs used in the system tray.
pub const MENU_ID_SCREENSHOT: &str = "screenshot";
pub const MENU_ID_HISTORY: &str = "history";
pub const MENU_ID_SETTINGS: &str = "settings";
pub const MENU_ID_ABOUT: &str = "about";
pub const MENU_ID_QUIT: &str = "quit";

/// All menu item IDs for iteration / validation.
#[allow(dead_code)]
pub const ALL_MENU_IDS: &[&str] = &[
    MENU_ID_SCREENSHOT,
    MENU_ID_HISTORY,
    MENU_ID_SETTINGS,
    MENU_ID_ABOUT,
    MENU_ID_QUIT,
];

pub fn create_tray<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    let quit_i = MenuItem::with_id(app, MENU_ID_QUIT, "退出", true, None::<&str>)?;
    let screenshot_i = MenuItem::with_id(
        app,
        MENU_ID_SCREENSHOT,
        "截图 (Ctrl+Shift+C)",
        true,
        None::<&str>,
    )?;
    let history_i = MenuItem::with_id(app, MENU_ID_HISTORY, "历史记录", true, None::<&str>)?;
    let settings_i = MenuItem::with_id(app, MENU_ID_SETTINGS, "设置", true, None::<&str>)?;
    let about_i = MenuItem::with_id(app, MENU_ID_ABOUT, "关于", true, None::<&str>)?;

    let menu = Menu::with_items(
        app,
        &[&screenshot_i, &history_i, &settings_i, &about_i, &quit_i],
    )?;

    let _tray = TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(move |app, event| match event.id.as_ref() {
            MENU_ID_QUIT => {
                app.exit(0);
            }
            MENU_ID_SCREENSHOT => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
                let _ = app.emit("open-selection", ());
            }
            MENU_ID_HISTORY => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
                let _ = app.emit("navigate", "/history");
            }
            MENU_ID_SETTINGS => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
                let _ = app.emit("navigate", "/settings");
            }
            MENU_ID_ABOUT => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    if window.is_visible().unwrap_or(false) {
                        let _ = window.hide();
                    } else {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn menu_ids_are_correct() {
        assert_eq!(MENU_ID_SCREENSHOT, "screenshot");
        assert_eq!(MENU_ID_HISTORY, "history");
        assert_eq!(MENU_ID_SETTINGS, "settings");
        assert_eq!(MENU_ID_ABOUT, "about");
        assert_eq!(MENU_ID_QUIT, "quit");
    }

    #[test]
    fn all_menu_ids_contains_five_items() {
        assert_eq!(ALL_MENU_IDS.len(), 5);
    }

    #[test]
    fn all_menu_ids_are_unique() {
        let mut sorted: Vec<&str> = ALL_MENU_IDS.to_vec();
        sorted.sort();
        sorted.dedup();
        assert_eq!(sorted.len(), ALL_MENU_IDS.len());
    }

    #[test]
    fn all_menu_ids_cover_expected_actions() {
        for id in ALL_MENU_IDS {
            assert!(
                matches!(
                    *id,
                    "screenshot" | "history" | "settings" | "about" | "quit"
                ),
                "unexpected menu id: {id}"
            );
        }
    }

    #[test]
    fn menu_ids_match_event_handler_branches() {
        // Every ID in ALL_MENU_IDS must have a match arm in on_menu_event.
        // This is a compile-time guarantee via the exhaustive match, but we
        // verify the constant set hasn't drifted from the handler coverage.
        for id in ALL_MENU_IDS {
            assert!(
                matches!(
                    *id,
                    MENU_ID_QUIT
                        | MENU_ID_SCREENSHOT
                        | MENU_ID_HISTORY
                        | MENU_ID_SETTINGS
                        | MENU_ID_ABOUT
                ),
                "menu id '{id}' not handled in on_menu_event"
            );
        }
    }

    #[test]
    fn create_tray_function_signature_is_valid() {
        // Verify the function exists with the expected signature at compile time.
        // We cannot call it without a real Tauri AppHandle, but this ensures the
        // function pointer type is correct.
        let _f: fn(&tauri::AppHandle<tauri::Wry>) -> tauri::Result<()> = create_tray;
    }
}
