# AGENTS.md — React Frontend (src/)

> Part of FormulaSnap project.

## Architecture

React 19 + TypeScript (strict) + Vite + Tailwind 4 via Vite plugin. No Next.js — pure SPA inside Tauri WebView.

```
src/
├── App.tsx                 # Root: BrowserRouter, SettingsProvider, ToastProvider, routes
├── main.tsx                # Entry: ReactDOM.createRoot
├── pages/                  # 5 lazy-loaded routes
│   ├── HomePage.tsx        #   / — capture trigger, recent history
│   ├── SelectionPage.tsx   #   /selection — region crop overlay (fullscreen, no layout)
│   ├── HistoryPage.tsx     #   /history — searchable history list
│   ├── HistoryDetailPage.tsx # /history/:id — single entry detail
│   └── SettingsPage.tsx    #   /settings — engine config, API keys, prefs
├── components/             # 17 React components
│   ├── CaptureFlow.tsx     #   Main capture orchestration
│   ├── capture/            #   CaptureActions, CapturePreview, OcrResultDisplay
│   ├── settings/           #   AboutSection, ApiKeySection, PreferencesSection, StatsSection
│   ├── Header.tsx          #   Top nav bar with navigation
│   ├── StatusBar.tsx       #   Bottom status bar (sidecar health, engine)
│   ├── ErrorBoundary.tsx   #   Class-based error boundary
│   ├── FormulaPreview.tsx  #   MathLive formula renderer
│   ├── RegionSelector.tsx  #   Screenshot region selection UI
│   ├── Spinner.tsx         #   Loading spinner
│   └── Toast.tsx           #   Toast notification system
├── lib/                    # 8 utility modules
│   ├── sidecarClient.ts    #   HTTP client for Python sidecar (port 8477)
│   ├── settings.ts         #   Settings persistence (localStorage + Tauri invoke)
│   ├── i18n.ts             #   Internationalization (flat keys, react-intl-like pattern)
│   ├── theme.ts            #   Theme management (light/dark/system)
│   ├── constants.ts        #   BACKEND_LABELS, getBackendOptions()
│   ├── clipboard.ts        #   Clipboard utilities
│   └── confidence.ts       #   Confidence score formatting
├── contexts/
│   └── SettingsContext.tsx  #   Settings context provider
├── types/                  # TypeScript type declarations
│   ├── ocr.ts              #   OcrBackend, OcrResponse, etc.
│   ├── history.ts          #   HistoryEntry
│   ├── settings.ts         #   AppSettings
│   ├── mathlive.d.ts       #   MathLive type declarations (no `as any`)
│   └── index.ts            #   Re-exports
├── i18n/                   # Translation files
│   ├── en.json             #   English (6.6KB)
│   └── zh.json             #   中文 (6.5KB)
├── assets/                 # Static assets
└── __tests__/              # 15 Vitest test files
```

## Key Patterns

### Sidecar Communication
Frontend calls Python sidecar **directly via HTTP** (port 8477) — not through Rust IPC. `sidecarClient.ts` uses `fetch()` with 30s OCR timeout, 5s stats timeout. Port initialized at startup via `invoke('get_sidecar_port')` with env var fallback.

### Routing
`react-router-dom` with lazy-loaded pages (`React.lazy()` + `Suspense`). `NavigationListener` subscribes to Tauri `"navigate"` event for Rust-driven navigation (system tray clicks).

### State Management
- **SettingsContext**: React context for app settings (theme, language, engine config). Persisted via Rust `save_setting`/`get_setting` commands.
- **Toast**: Context-based toast notification system.
- **No global state library** — useState + context are sufficient for this app's complexity.

## Anti-Patterns

- **No `as any`** — MathLive types declared in `types/mathlive.d.ts`. Use `MathfieldElement`.
- **No direct Rust IPC for OCR** — OCR goes through sidecar HTTP. If you need Rust in the OCR path, refactor proxy.
- **`BACKEND_LABELS`** centralized in `lib/constants.ts` — was duplicated in 4 files, don't revert.
- **Don't add new global state libraries** — context is sufficient.

## Conventions

- React 19. Use functional components, hooks, `lazy()` + `Suspense` for code splitting.
- Tailwind 4 via Vite plugin (no PostCSS, no `tailwind.config.js`). Apply dark mode via `dark:` prefix.
- Path alias `@/*` → `src/*`. Use for all imports.
- TypeScript strict: `noUnusedLocals`, `noUnusedParameters`. Fix type errors properly (no `as any`).
- i18n: flat key structure (`"backend.pix2text"` not `"backend":{"pix2text":"…"}`). Keys in en.json + zh.json.
- Theme: system preference by default. `applyTheme()` sets `class="dark"` on `<html>`.

## Testing

- Vitest (jsdom, globals), 15 test files in `src/__tests__/` + colocated `*.test.ts`.
- Run: `pnpm run test` (from project root).
- Test conventions: describe/it blocks, React Testing Library for component tests.
- `src/test/setup.ts` — global test setup (jsdom config, mock Tauri APIs).

## Commands

```bash
pnpm dev              # Dev server (Vite, port 1420)
pnpm run test         # Vitest
npx tsc --noEmit --skipLibCheck  # Type check
```
