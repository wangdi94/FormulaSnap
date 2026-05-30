use tauri::{AppHandle, Emitter};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

use crate::screenshot;

pub const CAPTURE_EVENT_NAME: &str = "capture-requested";

pub fn register_hotkeys(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let handle = app.clone();

    #[cfg(target_os = "macos")]
    let shortcut = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyC);
    #[cfg(not(target_os = "macos"))]
    let shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::KeyC);

    app.global_shortcut()
        .on_shortcut(shortcut, move |_app, _shortcut, event| {
            if event.state == ShortcutState::Pressed {
                let handle = handle.clone();
                tauri::async_runtime::spawn(async move {
                    match screenshot::capture_screen() {
                        Ok(png_bytes) => {
                            use base64::Engine;
                            let b64 = base64::engine::general_purpose::STANDARD.encode(&png_bytes);
                            let _ = handle.emit(CAPTURE_EVENT_NAME, b64);
                        }
                        Err(e) => {
                            log::error!("Screenshot capture failed: {e}");
                        }
                    }
                });
            }
        })?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capture_event_name() {
        assert_eq!(CAPTURE_EVENT_NAME, "capture-requested");
    }

    #[test]
    fn test_event_name_not_empty() {
        assert!(!CAPTURE_EVENT_NAME.is_empty());
        assert!(CAPTURE_EVENT_NAME
            .chars()
            .all(|c| c.is_ascii_lowercase() || c == '-'));
    }

    #[test]
    fn test_platform_shortcut_compiles() {
        #[cfg(target_os = "macos")]
        {
            let mods = Modifiers::SUPER | Modifiers::SHIFT;
            assert!(mods.contains(Modifiers::SUPER));
            assert!(mods.contains(Modifiers::SHIFT));
            assert!(!mods.contains(Modifiers::CONTROL));
        }

        #[cfg(not(target_os = "macos"))]
        {
            let mods = Modifiers::CONTROL | Modifiers::SHIFT;
            assert!(mods.contains(Modifiers::CONTROL));
            assert!(mods.contains(Modifiers::SHIFT));
            assert!(!mods.contains(Modifiers::SUPER));
        }
    }

    #[test]
    fn test_register_hotkeys_function_exists() {
        fn _assert_signature(f: fn(&AppHandle) -> Result<(), Box<dyn std::error::Error>>) {
            let _ = f;
        }
        _assert_signature(register_hotkeys);
    }
}
