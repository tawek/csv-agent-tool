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

### Convertible types — `CONVERTIBLE_EXTENSIONS`
- `.pdf`
- `.pptx`, `.ppt`
- `.docx`, `.doc`
- `.xlsx`, `.xls`
- `.html`, `.htm`
- `.epub`

These require **MarkItDown** for conversion to Markdown before they can be
used as attachment content. Conversion results are cached by source content
hash under `~/.cache/product-description-tool/kb-markitdown/`.

### All KB extensions — `ALL_KB_EXTENSIONS`
Union of direct-read + convertible sets: 14 extensions total.

Used by:
- `main_window.py::_gather_available_kb_files()` (line 644) — scans the KB
  directory for attachment-picker candidates.
- `generation.py::validate_attachments()` (line 125) — validates attachment
  file extensions.
- `prompt_renderer.py::SUPPORTED_KB_EXTENSIONS` (line 18) — alias for
  `ALL_KB_EXTENSIONS`, used in `_validate_kb_refs()` and `render()`.
- `prompt_renderer.py::CONVERTIBLE_EXTENSIONS` — imported directly for
  conversion-path branching.

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
3. Convertible: check cache first (by SHA-256 content hash).
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
`main_window.py::_gather_available_kb_files()` (line 637):
- Scans the KB directory recursively (`kb_path.rglob("*")`).
- Filters by `entry.suffix.lower() in ALL_KB_EXTENSIONS`.
- Returns relative paths for the `AddKbAttachmentsDialog` picker.

### Attachment manager status display
`dialogs.py::AttachmentManager._resolve_kb_file_status()` (line 1298):
Shows status per attachment row. **Has a bug** (see below).

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
   - KB file attachments: within KB root, file exists, extension in
     `SUPPORTED_KB_EXTENSIONS`, readable / convertible.
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

## Known Bug: `_resolve_kb_file_status` in AttachmentManager

**File:** `src/product_description_tool/dialogs.py`, line 1310

```python
# Current (buggy) code:
if candidate.suffix.lower() not in {".md", ".markdown", ".csv"}:
    return "Unsupported type"
```

**Problem:** The status check only recognizes `.md`, `.markdown`, and `.csv`
as valid. This:
1. Misses `.txt` (which is in `DIRECT_READ_EXTENSIONS`).
2. Rejects all convertible types (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`,
   `.epub`, etc.) as "Unsupported type" even though they are fully supported
   KB file types.

`dialogs.py` does not import `kb_conversion` or any extension constants.
The fix would be to use `ALL_KB_EXTENSIONS` (or `DIRECT_READ_EXTENSIONS`)
from `kb_conversion.py` and also handle the convertible-type status
(possibly using `KnowledgeBaseContentService`.

## Requirements for Adding New File Types

1. **Add the extension** to `CONVERTIBLE_EXTENSIONS` in
   `src/product_description_tool/kb_conversion.py` (line 18-25).
2. **Confirm MarkItDown support** — test that
   `markitdown.MarkItDown().convert(path)` works for the format. If not,
   install additional extras (e.g., `markitdown[<extra>]`) and update the
   dependency in `pyproject.toml`.
3. **Update kb_window.py** `_open_file_for_edit()` (line 321) if the new type
   should be viewable (convertible types already go through the `elif suffix
   in CONVERTIBLE_EXTENSIONS` branch to the read-only viewer).
4. **Fix `_resolve_kb_file_status()`** in `dialogs.py` line 1310 to use
   `ALL_KB_EXTENSIONS` or similar, so the status display doesn't falsely
   report convertible files as unsupported.
5. **Update tests** in `tests/test_kb_conversion.py`:
   `TestClassification.test_convertible_extensions` for new convertible
   types.
6. **Update PyInstaller spec** at `packaging/product_description_tool.spec`
   if the new format requires additional data files or submodules for the
   packaged build.
7. **Update `test_pyproject_uses_markitdown_local_conversion_extras`** in
   `tests/test_packaging.py` if a new markitdown extra is needed.
