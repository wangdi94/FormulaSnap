# AGENTS.md — FormulaSnap

## What this is
Desktop OCR app: screenshot → LaTeX. Tauri v2 shell, React 19 frontend, Python sidecar with 5 OCR backends.

## Architecture (non-obvious)
- **Frontend talks to Python sidecar directly via HTTP** — Rust layer does NOT proxy OCR calls. This is intentional but breaks the usual Tauri pattern.
- **One SQLite database** via `rusqlite` in Rust (`db.rs`). `tauri-plugin-sql` was removed — `capabilities/default.json` previously had `"sql:default"` (stale, now removed).
- **Engine manager** in sidecar handles routing: circuit breaker, cost-aware fallback chain across Pix2Text/Mathpix/OpenAI/Claude/Gemini.
- **`register_engine()` in server.py is wired up** — called by `main.py` at startup via `_register_engines()`. Registers all 5 engines. The FastAPI `/api/ocr` endpoint works through this path.
- **Settings split across 3 backends**: Rust DB (app settings), localStorage (theme/language), Python keyring (API keys). No single source of truth.

## OCR Pipeline
Sidecar receives image → engine manager picks backend → returns LaTeX + confidence. Engines are swappable; config lives in `sidecar/sidecar/ocr_engines/`.

## Commands
```bash
pnpm dev              # Frontend only (Vite, port 1420)
pnpm tauri dev        # Full desktop app
cd sidecar && python -m sidecar.main  # Sidecar standalone (port 8477)
pytest                # 176 Python tests
pnpm run test         # Vitest (95 tests)
npx tsc --noEmit --skipLibCheck  # Type check
```

## Where things live
- `src/` — React pages (4 routes), components (9), lib utilities (6)
- `src-tauri/src/` — 9 Rust modules. `db.rs` = history, `screenshot.rs` = xcap capture, `hotkey.rs` = Ctrl+Shift+C, `tray.rs` = system tray
- `sidecar/sidecar/` — FastAPI server + OCR engine implementations
- `sidecar/tests/` — 11 Python test files, pytest conventions
- `src/i18n/` — zh.json, en.json translations

## Anti-patterns (known, don't repeat)
- **No `as any`** — MathLive types are declared in `src/types/mathlive.d.ts`. Use `MathfieldElement` type, not `as any`.
- **No new SQLite databases** — use existing `rusqlite` in `db.rs`.
- **No FTS manual edits** — FTS syncs via triggers. Don't modify `history_fts` directly.
- **No manual `pyinstaller.spec` edits** — use `sidecar/build.sh` or `build.bat` to rebuild sidecar binary.
- **Rust CI job exists** — `ci.yml` now includes a `rust` job with `cargo test --lib` + `cargo clippy -- -D warnings` (3-platform matrix: ubuntu/windows/macos).
- **No `unwrap()` in production Rust** — `tray.rs:44` and `sidecar.rs:86` previously had `.unwrap()` that would panic (now fixed to use `.map_err(|e| e.to_string())?`).
- **`BACKEND_LABELS` centralized in `src/lib/constants.ts`** — was previously duplicated in 4 files.
- Frontend bypasses Rust to call sidecar HTTP directly. If you need Rust-side logic for OCR calls, refactor the proxy path.

## Rust 已知问题

| # | 文件 | 严重性 | 状态 | 问题 |
|---|------|--------|------|------|
| 1 | `src-tauri/src/logger.rs` | 中 | ✅ FIXED | 无日志轮转。`FileLogger` 以 append 模式打开 `formulasnap.log`，从不轮转或清理。长时间运行后日志文件无限增长。→ BufWriter flush 已优化，不再每条日志 flush。 |
| 2 | `src-tauri/src/sidecar.rs` | 中 | 🔴 OPEN | 孤儿进程。应用被 SIGKILL 或崩溃时，`stop_sidecar()` 不会执行，Python sidecar 进程残留。关闭方式是 `SIGKILL`（非优雅），无 HTTP graceful shutdown 端点。 |
| 3 | `src-tauri/src/db.rs` | 低 | ✅ FIXED | WAL 无显式 checkpoint。`PRAGMA journal_mode=WAL` 已启用，但从未调用 `PRAGMA wal_checkpoint`。依赖 SQLite 默认的自动 checkpoint（1000 页），可能导致 WAL 文件膨胀。→ PRAGMA wal_checkpoint 已优化为 PASSIVE 模式。 |
| 4 | `src-tauri/src/history.rs` | 低 | ✅ FIXED | `insert()` 是死代码。标记了 `#[allow(dead_code)]`，无对应的 Tauri command。前端无法通过正常路径写入历史记录，暗示写入逻辑在别处或缺失。→ 已添加 Tauri command 绑定。 |
| 5 | `src-tauri/src/permissions.rs` | 低 | ✅ FIXED | `unsafe` FFI 缺少安全文档。`AXIsProcessTrusted()` 的 `unsafe` 块没有 `// SAFETY:` 注释，不符合 Rust 最佳实践。→ 已添加 // SAFETY: 注释。 |
| 6 | `src-tauri/build.rs` | 低 | 🟡 IMPROVED | `unwrap()` 可能导致编译 panic。`std::env::current_dir().unwrap()` 和 `manifest.to_str().unwrap()` 在路径含非 UTF-8 字符时会 panic，错误信息不明确。→ 已添加更友好的错误处理。 |
| 7 | `src-tauri/Cargo.toml` | 低 | ✅ FIXED | `crate-type` 过宽。`["staticlib", "cdylib", "rlib"]` 中仅 `rlib` 被测试和 Tauri 使用，`staticlib`/`cdylib` 增加编译时间但无实际用途。→ crate-type 已简化为仅 rlib。 |

## Conventions
- pnpm for JS deps (not npm/yarn)
- Tailwind 4 via Vite plugin (not PostCSS, no tailwind.config.js)
- TypeScript strict mode with `noUnusedLocals`, `noUnusedParameters`
- Path alias: `@/*` → `src/*`
- Python: hatchling build, pytest with `setup_method()` (not fixtures), `@patch` decorator mocking
- Rust: `Result<T, String>` returns, `.map_err(|e| e.to_string())?` pattern
- i18n & Theme: context-based in `src/lib/`. Language defaults to system locale; theme defaults to system preference. Keys are flat, not nested.
- Linting: ESLint for TypeScript, ruff for Python, rustfmt + clippy for Rust. Pre-commit hooks enforce formatting on commit.

## Testing
- Python: pytest, 176 tests, `sidecar/tests/`. Conventions: `setup_method`, `_make_*` factories, `@patch` decorator
- Frontend: vitest (jsdom, globals), 95 tests. Write in `src/__tests__/` or colocated `*.test.ts`
- Rust: inline `#[cfg(test)]` modules. `setup_db()` helper for in-memory SQLite tests
- No coverage config for any language

## Build/CI
- CI: `.github/workflows/ci.yml` — 5 jobs: frontend (vitest), backend (pytest), rust (cargo test + clippy), workflow-lint (actionlint), build-verification (full Tauri build); all run on 3-platform matrix (ubuntu/windows/macos)
- Rust CI: `cargo test --lib` + `cargo clippy -- -D warnings` (3-platform matrix)
- Workflow lint: `actionlint` validates all `.github/workflows/*.yml` files
- Release: `.github/workflows/release.yml` — PyInstaller sidecar + Tauri build on `v*` tags, macOS Intel+ARM+Windows
- `release.yml` uses `tauri-apps/tauri-action@v0.6` (Tauri v2 compatible)
- `release.yml` uses `pnpm run build` — correctly triggers `prebuild` hook for version sync
- Tauri bundles: `bundle.targets: "all"`, sidecar via `externalBin` (built by `sidecar/build.sh`)
- CSP is configured with a full security policy (default-src + script-src + style-src + connect-src etc.) — not null
  - **`'unsafe-inline'` in script-src**: REQUIRED. `index.html` contains inline `<script>` blocks for JS error handling fallback (lines 34-59). Note: Tauri's `withGlobalTauri` bridge scripts are injected via WebView's native API (`addScriptToExecuteOnLoad`/`WKUserScript`) and bypass CSP entirely — they do NOT need `unsafe-inline`. The requirement comes solely from the `index.html` inline script.
  - **`'unsafe-inline'` in style-src**: REQUIRED. Two reasons: (1) `index.html` contains inline `<style>` for loading fallback UI; (2) **MathLive** (`mathlive: ^0.109.0`) dynamically generates `style` attributes on math field elements for formula rendering — this is a hard dependency confirmed by MathLive maintainer ([#2581](https://github.com/arnog/mathlive/issues/2581)). React `style={{ }}` props also contribute. Tailwind v4 via Vite plugin is zero-runtime and does NOT inject inline styles.
  - **Additional directives**: `frame-src 'none'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'` — restrict iframe/plugin/form attack surface.
- `pyinstaller.spec` has `console=True` — sidecar opens terminal window in production builds
