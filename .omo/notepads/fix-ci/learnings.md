# Learnings — fix-ci

## 2026-05-29 Plan Context
- CI has 3 root causes: pnpm version missing, test mocks incomplete, pix2text too large
- All 7 tasks are independent and can run in parallel
- Engine files must NOT be modified (only test files)
- pix2text_engine.py:127-132 checks `Pix2Text is None`, NOT `PIX2TEXT_AVAILABLE`
- test_pix2text.py:120 only patches PIX2TEXT_AVAILABLE but Pix2Text may still be non-None
