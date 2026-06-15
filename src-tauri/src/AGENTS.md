# AGENTS.md — Rust Backend (src-tauri/src/)

> Part of FormulaSnap project.

## Architecture

9 files. `lib.rs` owns module declarations + 8 Tauri commands + setup closure.
`get_setting`/`save_setting` are inline in lib.rs (not extracted to a module).
`greet()` command was removed.
`main.rs` is 6 lines: calls `tauri_app_lib::run()`.

## State & Commands

```rust
pub struct DbConn(pub Mutex<rusqlite::Connection>);
// Injected: app.manage(DbConn(Mutex::new(conn)));
// Accessed: state: tauri::State<'_, DbConn>
// Lock: state.0.lock().map_err(|e| e.to_string())?
```

All commands return `Result<T, String>`. No custom error types. `.map_err(|e| e.to_string())?` everywhere.

## Database (db.rs + history.rs)

- SQLite via `rusqlite` (bundled). Schema: `history`, `settings`, `history_fts` (FTS5).
- FTS sync via triggers (AFTER INSERT/UPDATE/DELETE). Don't modify FTS manually.
- `initialize_database()` is idempotent (CREATE IF NOT EXISTS).
- `history::HistoryEntry` derives `Serialize, Deserialize` — used directly as command return type.

## Dual SQLite Gotcha

`tauri-plugin-sql` was removed from `Cargo.toml` and `lib.rs`. Dead weight: empty migrations, unused.
Only `rusqlite` via `DbConn` remains. `greet()` command also removed from `lib.rs`.

## Screenshot (screenshot.rs)

`xcap::Monitor::all()?.into_iter().next()` — PRIMARY monitor only.
Region crop clamps to image bounds via `saturating_sub`. Commands encode to base64.

## Hotkey (hotkey.rs)

Platform-conditional: `Cmd+Shift+C` (macOS) vs `Ctrl+Shift+C` (others).
`CAPTURE_EVENT_NAME` is `pub const` (shared with tray). Emits event with base64 payload.
4 inline tests: event name value, format validation, platform modifiers, function signature.

## Sidecar (sidecar.rs)

Python sidecar on port 8477. Spawns via `tauri_plugin_shell`.
Health poll: blocking HTTP in background thread, 30s timeout, 500ms interval.
Emits `"sidecar://ready"` / `"sidecar://error"` events.
Shutdown: `SIGKILL` on `RunEvent::ExitRequested`. No graceful HTTP endpoint.

## Tray (tray.rs)

Menu IDs are `pub const` with `ALL_MENU_IDS` array. Screenshot: calls `capture_screen()`, emits `"capture-requested"` with base64. History/Settings: emit `"navigate"` with path. About: show+focus only.
6 inline tests: ID values, count, uniqueness, coverage, handler match, function signature.

## Permissions (permissions.rs)

macOS-only `unsafe` FFI: `AXIsProcessTrusted()`. Non-macOS always returns `true`.
Emits `"accessibility-permission-status"` event. Only `pub mod` in lib.rs.

## Testing

Inline `#[cfg(test)]` modules in db.rs, tray.rs (6 tests), hotkey.rs (4 tests).
`setup_db()` helper: in-memory SQLite + `initialize_database()`.
Tests cover: CRUD, pagination, FTS search, empty results, idempotent migration.
Run: `cargo test` from `src-tauri/`.

## Linting

Rust: `rustfmt` + `clippy` (`cargo clippy -- -D warnings`). Pre-commit hooks enforce formatting on commit.

## Known Issues

- ✅ FIXED: logger.rs — BufWriter flush 已优化，不再每条日志 flush
- 🔴 OPEN: sidecar.rs — No `tauri-plugin-shell` sidecar cleanup on crash (process stays orphaned if app force-killed).
- ✅ FIXED: db.rs — PRAGMA wal_checkpoint 已优化为 PASSIVE 模式
- ✅ FIXED: history.rs — 已添加 Tauri command 绑定
- ✅ FIXED: permissions.rs — 已添加 // SAFETY: 注释
- 🟡 IMPROVED: build.rs — 已添加更友好的错误处理
- ✅ FIXED: Cargo.toml — crate-type 已简化为仅 rlib

## Adding a New Command

1. Write function in appropriate module (or `lib.rs` if simple).
2. Signature: `fn name(state: tauri::State<'_, DbConn>, ...) -> Result<T, String>`
3. Register in `lib.rs` `generate_handler![]` list.
4. Add inline test using `setup_db()` pattern.
