# File Attachments and Conversion

## Overview

The prompt-attachments feature allows users to attach files from a
**Knowledge Base** (KB) directory or **CSV columns** to individual prompts.
Attached content is automatically appended to the effective prompt with
provenance markers during generation and preview.

## Supported File Types

Defined in `src/product_description_tool/kb_conversion.py`:

### Direct-read (text) types — `DIRECT_READ_EXTENSIONS`
- `.md`, `.markdown`
- `.txt`
- `.csv`

These files are read as UTF-8 text and returned as-is (CSV included as raw
text). No conversion is applied.

### Known convertible examples — `CONVERTIBLE_EXTENSIONS`
- `.pdf`
- `.pptx`, `.ppt`
- `.docx`, `.doc`
- `.xlsx`, `.xls`
- `.html`, `.htm`
- `.epub`

These require **MarkItDown** for conversion to Markdown before they can be
used as attachment content. Conversion results are cached by source content
hash under `~/.cache/product-description-tool/kb-markitdown/`.

### Runtime support model
The app now treats KB conversion as capability-based rather than allowlist-based:

- direct-read suffixes still open as UTF-8 text without conversion,
- any other KB file can be selected for attachment or in-app viewing, and
- MarkItDown determines at runtime whether conversion succeeds for that file.

`ALL_KB_EXTENSIONS` remains as a catalog of direct-read plus commonly known convertible examples, but picker and validation flows must not use it as a hard gate.

Used by:
- `prompt_renderer.py::SUPPORTED_KB_EXTENSIONS` remains a compatibility alias for tests and documentation, but runtime validation is performed by `KnowledgeBaseContentService.load_markdown()`.

## MarkItDown Integration

### Dependency
```toml
markitdown[docx,outlook,pdf,pptx,xls,xlsx]>=0.1.6
```
From `pyproject.toml` line 9.

### Runtime detection
`KnowledgeBaseContentService._check_markitdown()` attempts `import markitdown`
and caches the result. Used by:
- `validate_supported()` — returns error if conversion needed but MarkItDown
  unavailable.
- `load_markdown()` — raises `MarkItDownUnavailableError` if conversion is
  needed and MarkItDown is not importable.

### Conversion flow (`kb_conversion.py::load_markdown()`)
1. Classify suffix via `classify_suffix()`.
2. Direct-read: return UTF-8 text as-is.
3. Any other file: check cache first (by SHA-256 content hash).
4. Cache miss → instantiate `markitdown.MarkItDown()`, call
   `.convert(str(source_path))`, store cache entry + metadata JSON.
5. Return `result.text_content`.

### Cache invalidation
Cache key incorporates SHA-256 of source bytes, file suffix, and converter
identity (`markitdown-<version>`). Source change → different hash → cache
miss.

### PyInstaller packaging
The spec file (`packaging/product_description_tool.spec`) explicitly collects
markitdown submodules and data files, plus the `magika` data files used by
markitdown for file-type detection.

## Where File Types Are Filtered/Selected

### KB file browsing (filesystem tree)
`kb_window.py` — `QFileSystemModel` with `setNameFilters(["*"])` (line 62):
shows **all** files in the KB directory, not filtered by extension.
The attachment picker only shows `ALL_KB_EXTENSIONS` files (see below).

### Attachment file picker
`main_window.py::_gather_available_kb_files()` scans the KB directory recursively and returns every file path. `AddKbAttachmentsDialog` presents those files in a tree-like directory picker rooted at the KB directory.

### Attachment manager status display
`dialogs.py::AttachmentManager._resolve_kb_file_status()` uses `KnowledgeBaseContentService.validate_supported()` so the table reflects actual conversion availability rather than a hardcoded extension allowlist.

### CSV import/export dialogs
All use the same hardcoded filter: `"CSV Files (*.csv);;All Files (*)"` in:
- `main_window.py` line 530 (import CSV)
- `dialogs.py` line 902 (export CSV path selection)
- `dialogs.py::ExportDialog._browse_path` line 902

### Project file dialogs
`main_window.py` lines 440, 494: `"Project Files (*.project.json);;All Files (*)"`

## Attachment Flow Summary

1. **User clicks "Attachments…"** button in `MainWindow` prompt header.
2. `_open_attachment_manager()` gathers KB files via
   `_gather_available_kb_files()` (using `ALL_KB_EXTENSIONS`) and CSV columns
   from the current document headers.
3. **`AttachmentManager` dialog** opens — shows current attachments in a
   table with type, source, and status.
4. **User adds** KB files (via `AddKbAttachmentsDialog`) or CSV columns (via
   `AddColumnAttachmentsDialog`).
5. **Validation** during preview/generation via
   `GenerationService.validate_attachments()` checks:
   - Column attachments: header exists.
   - KB file attachments: within KB root, file exists, and can be read directly or converted successfully.
6. **Effective prompt construction** via
   `GenerationService.build_effective_prompt()` appends attachment content
   with headers like:
   ```
   --- Attachment: column 'sku' ---
   <value>
   --- End attachment ---
   ```
   For KB convertible files, `KnowledgeBaseContentService.load_markdown()` is
   called (with caching), which uses MarkItDown for conversion.

## Requirements for Adding New File Types

1. **Confirm MarkItDown support** — test that
   `markitdown.MarkItDown().convert(path)` works for the format. If not,
   install additional extras (e.g., `markitdown[<extra>]`) and update the
   dependency in `pyproject.toml`.
2. **Update `CONVERTIBLE_EXTENSIONS`** only when you want the new format listed as a known example or called out explicitly in tests/documentation.
3. **Update tests** in `tests/test_kb_conversion.py`:
   `TestClassification.test_convertible_extensions` for new known convertible
   types.
4. **Update PyInstaller spec** at `packaging/product_description_tool.spec`
   if the new format requires additional data files or submodules for the
   packaged build.
5. **Update `test_pyproject_uses_markitdown_local_conversion_extras`** in
   `tests/test_packaging.py` if a new markitdown extra is needed.
