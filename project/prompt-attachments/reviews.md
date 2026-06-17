# Reviews

## QA review — 2026-06-17

- **Artifacts reviewed:** prompt-attachment source changes, `tests/test_main_window.py`, `tests/test_attachments.py`
- **Output artifact:** `docs/qa/prompt-attachments-tests.md`
- **Decision:** pass
- **Findings:**
  - `DEV-1` — test doubles needed to accept the new `attachments` keyword argument. Fixed and closed.

## Architect review — 2026-06-17

- **Artifacts reviewed:** `docs/specification.md`, prompt-attachment mockups, `src/product_description_tool/`, `tests/`, `docs/qa/prompt-attachments-tests.md`
- **Decision:** approved after one low-severity fix
- **Findings:**
  - `AR-1` — when no KB directory is configured, the blocked KB-file add action should explicitly explain why it is unavailable. Fixed and closed.

## Review closure summary

- `QA-BLOCK-1` — closed
- `DEV-1` — closed
- `AR-1` — closed
- Current action register status: closed
