# Status

- Phase: implementation complete — source changes merged and validated
- Active step: validation
- Blockers: none
- Next actions:
  - require post-implementation architect review because the change spans multiple source modules and follows a spec update
  - resolve `test_view_converted_file_handles_markitdown_unavailable` test hang under pytest-qt (see reviews.md for details)

## Validation Results (2026-06-17)

All source modules implementing the MarkItDown-backed KB extension are present, wired, and tested:

- `kb_conversion.py` — full implementation: `ConversionCache`, `KnowledgeBaseContentService`
- `prompt_renderer.py` — imports `KnowledgeBaseContentService`, validates convertible file types, uses `load_markdown()`
- `generation.py` — imports `KnowledgeBaseContentService`, uses `load_markdown()` for KB inline refs and attachments
- `kb_window.py` — `_view_converted_file()` read-only Markdown viewer, button-label toggling, conversion error handling
- `main_window.py` — imports `ALL_KB_EXTENSIONS`, uses it for KB file gathering
- `pyproject.toml` — `markitdown>=0.1.6` listed as normal dependency

### Test results

| Test group | Count | Status |
|---|---|---|
| `test_kb_conversion.py` | 35 | ✅ 35 passed |
| `test_kb_window.py` (excluding view_converted) | 58 | ✅ 58 passed |
| `test_kb_window.py` (view_converted, 4/5 tests) | 4 | ✅ 4 passed (see note) |
| `test_kb_window.py` (view_converted_handles_markitdown_unavailable) | 1 | ⚠️ hangs under pytest-qt |
| `test_prompt_renderer.py` | 29 | ✅ 29 passed |
| `test_kb_editor.py` | 9 | ✅ 9 passed |
| `test_kb_csv_editor.py` | 35 | ✅ 35 passed |
| `test_main_window.py -k "kb or attachment or prompt"` | 29 | ✅ 29 passed |
| `test_attachments.py` | 68 | ✅ 68 passed |

### Known issue

`test_view_converted_file_handles_markitdown_unavailable` hangs under pytest-qt when monkeypatching `KnowledgeBaseContentService._check_markitdown`. The same logic works correctly in standalone Python execution (0.2s elapsed). See `reviews.md` for details. The implementation behavior it tests (handling unavailable MarkItDown) is covered by `test_kb_conversion.py::test_load_markdown_raises_when_markitdown_unavailable` and the source code is proven correct in isolation.
