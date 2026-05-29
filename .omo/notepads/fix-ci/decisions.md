# Decisions — fix-ci

## 2026-05-29 Architecture
- pix2text moved to optional extra to avoid torch download in CI
- Tests use save/restore pattern for *_AVAILABLE flags (see test_claude.py:181-192)
- CI gets timeout-minutes and fail-fast: false for resilience
