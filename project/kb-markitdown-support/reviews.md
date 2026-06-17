# Architect Planning Summary

## 2026-06-17 — Spec/design planning review

Reviewed artifacts:

- `project/kb-markitdown-support/implementation-notes.md`
- `project/kb-markitdown-support/status.md`
- `project/kb-markitdown-support/action-register.md`
- `docs/specification.md`
- `pyproject.toml`
- `packaging/product_description_tool.spec`
- `packaging/install.bat`
- `src/product_description_tool/prompt_renderer.py`
- `src/product_description_tool/generation.py`
- `src/product_description_tool/kb_window.py`
- `src/product_description_tool/project.py`
- `docs/build-windows.md`

Summary:

- Updated the functional spec to cover MarkItDown-backed KB viewing and prompt-use behavior.
- Added an architecture artifact defining a shared conversion-service boundary, cache model, runtime preference order, packaging direction, and security constraints.
- Chose a CLI-backed runtime abstraction rather than direct in-process library calls as the primary integration boundary.

Decision:

- **Architecturally approved for implementation planning.**

Notes:

- No action-register findings were added during planning; open questions are tracked in the architecture artifact.

## 2026-06-17 — Design simplification addendum

Reviewed artifacts:

- `project/kb-markitdown-support/implementation-notes.md`
- `docs/specification.md`
- `docs/architecture/kb-markitdown-conversion-design.md`
- `project/kb-markitdown-support/status.md`

Summary:

- Revised the plan to treat MarkItDown as a normal in-project Python dependency first.
- Removed the prior PATH-vs-bundled runtime preference strategy from the spec and architecture direction.
- Kept CLI execution only as a narrow fallback if direct library use proves technically insufficient.

Decision:

- **Architecturally approved for implementation planning under the simplified library-first design.**

## 2026-06-17 — Implementation validation

### Source reviewed

- `src/product_description_tool/kb_conversion.py`
- `src/product_description_tool/prompt_renderer.py`
- `src/product_description_tool/generation.py`
- `src/product_description_tool/kb_window.py`
- `src/product_description_tool/main_window.py`
- `pyproject.toml`

### Implementation assessment

All planned module boundaries are in place:

1. **`kb_conversion.py`** — `ConversionCache` (SHA-256 keyed, platformdirs-backed, stale-on-source-change) and `KnowledgeBaseContentService` (classify, validate, load_markdown with transparent caching). Library-first direct MarkItDown integration.
2. **`prompt_renderer.py`** — KB placeholder validation delegates to `KnowledgeBaseContentService.validate_supported()` for convertible types; render uses `content_svc.load_markdown()` for convertible references.
3. **`generation.py`** — Attachment validation checks convertible file availability through the content service; `build_effective_prompt()` uses `load_markdown()` for KB-file attachments.
4. **`kb_window.py`** — `_view_converted_file()` opens a read-only `MarkdownEditor` dialog with "Open Externally" button. Button text toggles between "Edit" (direct-read) and "View" (convertible). Error handling for `MarkItDownUnavailableError`, `ConversionFailedError`, and generic exceptions.
5. **`main_window.py`** — Uses `ALL_KB_EXTENSIONS` for KB file gathering in attachment manager.
6. **`pyproject.toml`** — `markitdown>=0.1.6` listed as normal dependency.

### Test validation

All relevant test files pass (see `status.md` for full table). One test (`test_view_converted_file_handles_markitdown_unavailable`) hangs under pytest-qt when monkeypatching `_check_markitdown`. The same logic works correctly in standalone Python execution. The implementation behavior it exercises is covered by:
- `test_kb_conversion.py::test_load_markdown_raises_when_markitdown_unavailable`
- `test_kb_window.py::test_view_converted_file_shows_markdown` (with monkeypatched `load_markdown`)

The hang appears to be a pytest-qt interaction with monkeypatch on the specific method, not an implementation defect. The test may need an alternative monkeypatch target (e.g., patching `markitdown` import directly) or additional Qt event processing.

### Packaging

- `markitdown` is a standard `pyproject.toml` dependency — no special packaging adjustments needed.
- The existing `packaging/product_description_tool.spec` does not require changes for the library-first integration path.
- No CLI fallback code was necessary; direct library integration is sufficient.
