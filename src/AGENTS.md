# src/ — Frontend Domain Knowledge

## Structure

```
src/
├── pages/          # 4 route pages (Home, History, HistoryDetail, Settings)
├── components/     # 9 UI components
├── lib/            # 7 utility modules (no hooks directory)
├── types/          # 5 type definition files
├── i18n/           # zh.json, en.json (flat keys, not nested)
├── __tests__/      # Vitest tests
└── assets/         # Static assets
```

## Where to Look

- **OCR flow**: `components/CaptureFlow.tsx` — state machine driving capture→recognize→display
- **Sidecar communication**: `lib/sidecarClient.ts` — HTTP client to Python sidecar (port 8477)
- **Settings persistence**: `lib/settings.ts` — Tauri invoke to Rust DB; `lib/theme.ts` + `lib/i18n.ts` use localStorage
- **Formula rendering**: `components/FormulaPreview.tsx` — MathLive `<math-field>` custom element
- **Clipboard operations**: `lib/clipboard.ts` — uses `@tauri-apps/plugin-clipboard-manager`
- **Auto-updater**: `lib/updater.ts` — wraps `@tauri-apps/plugin-updater`
- **Toast notifications**: `components/Toast.tsx` — context provider with `useToast()` hook

## Key Patterns

### CaptureFlow State Machine
`CaptureFlow.tsx` implements a 5-state machine: `idle → capturing → ocr-loading → result → error`. States drive conditional rendering. Error state supports retry logic via `FlowError.retryable` flag.

### Event-Driven Rust→React Bridge
Rust emits events via `@tauri-apps/api/event`. Key events:
- `capture-requested` — triggers OCR flow with base64 image payload
- `navigate` — routes React app from Rust (tray menu, hotkey)

### MathLive Integration
- Types declared in `types/mathlive.d.ts` (augments `React.JSX.IntrinsicElements`)
- Use `MathfieldElement` type, never `as any`
- Import `mathlive` once (side-effect import in `FormulaPreview.tsx`)
- `<math-field>` custom element for formula rendering/editing

### SidecarClient Architecture
`lib/sidecarClient.ts` talks directly to Python sidecar via HTTP (not through Rust). Exports: `callOcr()`, `healthCheck()`, `getStats()`, `validateConfig()`, `waitForReady()`. Custom `SidecarError` class wraps HTTP errors with typed detail.

## Anti-Patterns

- **No direct fetch to sidecar** — use `SidecarClient` from `lib/sidecarClient.ts`
- **No `as any` for MathLive** — use `MathfieldElement` from `types/mathlive.d.ts`
- **No hardcoded backend labels** — `BACKEND_LABELS` is duplicated in 4 files (CaptureFlow, HistoryPage, HistoryDetailPage, BackendIndicator). Extract to shared constant before adding new backends.
- **No new localStorage keys without documenting split** — theme/language go in localStorage; app settings go in Rust DB via `invoke()`. Don't mix.
- **No nested i18n keys** — translations use flat dot-notation keys (`"settings.theme.light"`), not objects.

## Data Flow

```
User action → CaptureFlow state change
  → invoke('capture_screen_base64') [Rust screenshot]
  → SidecarClient.callOcr(base64) [HTTP to Python]
  → OcrResponse { latex, confidence, backend, timing_ms }
  → FormulaPreview renders <math-field>
  → clipboard.ts copies (LaTeX/MathML/PNG)
  → invoke('save_setting') persists to Rust DB
```

## Tests

Write in `src/__tests__/` or colocated `*.test.ts`. Vitest with jsdom + globals. 24 existing tests. Use `lib/clipboard.test.ts` as reference for mocking Tauri plugins.
