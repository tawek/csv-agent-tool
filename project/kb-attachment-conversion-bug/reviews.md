## Architect Review — 2026-06-18

- Scope reviewed:
  - `docs/specification.md`
  - `project/kb-attachment-conversion-bug/implementation-notes.md`
  - `project/kb-attachment-conversion-bug/action-register.md`
  - `src/product_description_tool/kb_conversion.py`
  - `src/product_description_tool/prompt_renderer.py`
  - `src/product_description_tool/generation.py`
  - `src/product_description_tool/main_window.py`
  - `src/product_description_tool/dialogs.py`
  - `src/product_description_tool/kb_window.py`
  - related tests in `tests/`

- Findings:
  - Low: `KnowledgeBaseContentService.validate_supported()` now means "MarkItDown is present so conversion may be attempted" rather than "this file is known to convert successfully". Most execution paths compensate by also calling `load_markdown()`, but `AttachmentManager._resolve_kb_file_status()` uses only `validate_supported()`, so some non-direct files can be shown as `Available` even though later preview/processing will fail conversion.
    - References: `src/product_description_tool/kb_conversion.py:170`, `src/product_description_tool/dialogs.py:1317`

- Architectural fit decision:
  - Acceptable as-is for this bug-fix scope.
  - The central capability-based conversion model is otherwise internally consistent across picker population, prompt rendering, attachment validation, KB viewing, and cache behavior.
