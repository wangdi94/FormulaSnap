# AGENTS.md — FormulaSnap

## What this is
Desktop OCR app: screenshot → LaTeX. Tauri v2 shell, React frontend, Python sidecar with 5 OCR backends.

## Architecture (non-obvious)
- **Frontend talks to Python sidecar directly via HTTP** — Rust layer does NOT proxy OCR calls. This is intentional but breaks the usual Tauri pattern.
- **One SQLite database** via `rusqlite` in Rust (`db.rs`). `tauri-plugin-sql` is registered but has empty migrations — dead weight, don't use it.
- **Engine manager** in sidecar handles routing: circuit breaker, cost-aware fallback chain across Pix2Text/Mathpix/OpenAI/Claude/Gemini.
- **Settings split across 3 backends**: Rust DB (app settings), localStorage (theme/language), Python keyring (API keys). No single source of truth.

## OCR Pipeline
Sidecar receives image → engine manager picks backend → returns LaTeX + confidence. Engines are swappable; config lives in `sidecar/sidecar/ocr_engines/`.

## Commands
```bash
pnpm dev              # Frontend only (Vite, port 1420)
pnpm tauri dev        # Full desktop app
cd sidecar && python -m sidecar.main  # Sidecar standalone (port 8477)
pytest                # 176 Python tests
pnpm run test         # Vitest (24 tests)
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
- **No new SQLite databases** — use existing `rusqlite` in `db.rs`. Don't add `tauri-plugin-sql` migrations.
- **No FTS manual edits** — FTS syncs via triggers. Don't modify `history_fts` directly.
- **No manual `pyinstaller.spec` edits** — use `sidecar/build.sh` or `build.bat` to rebuild sidecar binary.
- **No Rust CI job** — GitHub Actions only runs frontend + backend Python. Add `cargo test`/`clippy` if adding Rust CI.
- Frontend bypasses Rust to call sidecar HTTP directly. If you need Rust-side logic for OCR calls, refactor the proxy path.

## Conventions
- pnpm for JS deps (not npm/yarn)
- Tailwind 4 via Vite plugin (not PostCSS, no tailwind.config.js)
- TypeScript strict mode with `noUnusedLocals`, `noUnusedParameters`
- Path alias: `@/*` → `src/*`
- Python: hatchling build, pytest with `setup_method()` (not fixtures), `@patch` decorator mocking
- Rust: `Result<T, String>` returns, `.map_err(|e| e.to_string())?` pattern
- i18n & Theme: context-based in `src/lib/`. Language defaults to system locale; theme defaults to system preference. Keys are flat, not nested.

## Testing
- Python: pytest, 176 tests, `sidecar/tests/`. Conventions: `setup_method`, `_make_*` factories, `@patch` decorator
- Frontend: vitest (jsdom, globals), 24 tests. Write in `src/__tests__/` or colocated `*.test.ts`
- Rust: inline `#[cfg(test)]` modules. `setup_db()` helper for in-memory SQLite tests
- No coverage config for any language

## Build/CI
- CI: `.github/workflows/ci.yml` — frontend (vitest) + backend (pytest) jobs, 3-platform matrix (ubuntu/windows/macos)
- No Rust CI job, no lint/format checks. Add `cargo test`/`clippy` if adding Rust CI.
- Release: `.github/workflows/release.yml` — PyInstaller sidecar + Tauri build on `v*` tags, macOS Intel+ARM+Windows
- Tauri bundles: `bundle.targets: "all"`, sidecar via `externalBin` (built by `sidecar/build.sh`)
- CSP disabled (`"csp": null`) — security concern
