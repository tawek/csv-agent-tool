# CSV Import Heuristics Restart

## User request

- There is an ongoing effort to introduce heuristics on CSV import.
- The intended preference is to use what was already set in the project's settings.
- The current changes may be bad and/or unconsulted.
- Start afresh instead of continuing the current partial implementation.
- Clarified need: users should not be burdened with discovering the correct import setup for an opened CSV file.
- Import should auto-detect the CSV settings and carry on.
- If the user specifies settings in the project, those settings should apply on export.
- Import settings and export settings may be different.
- Initially, export settings should be copied from the detected import settings after import.
- Before first import, export settings are effectively undefined/not yet established.

## Constraints

- Follow spec-first workflow before any replacement implementation.
- Treat the current `project/csv-auto-detect/` effort as superseded unless specific artifacts are intentionally reused after review.
- Avoid touching unrelated working-tree changes.

## Explicit non-goals for this reset step

- Do not continue the existing partial implementation as-is.
- Do not commit or push anything.

## Implementation Notes (2026-06-17)

### Key design decisions

1. **Backward compatibility via properties** (`CsvConfig.delimiter`, `.fields`, etc.): Rather than updating every call site at once, existing code that accesses `project.csv.delimiter` continues to work because `CsvConfig` has backward-compat properties that delegate to `export_settings`. The few read-path call sites (`open_project`, `load_csv`) are updated to explicitly use `.import_settings`.

2. **`CsvConfig` without `slots=True`**: Properties and `@dataclass(slots=True)` can't coexist when the property names differ from field names. Since `CsvConfig` now has properties mirroring the old flat field names, I removed `slots=True` only from `CsvConfig`. The sub-dataclasses `CsvReadSettings` and `CsvWriteSettings` keep `slots=True`.

3. **Legacy detection in `from_dict`**: The new format has `import_settings` or `export_settings` keys at the top level. If neither is present, the dict is treated as legacy flat data and populates both import/export settings from the same flat values, with `export_settings_initialized=True`.

4. **First-import seeding**: Done in `load_csv()` — after a successful import, if `export_settings_initialized` is `False`, copy `delimiter` and `quotechar` from the detected import settings and set the flag. Import-only attributes (`encoding`, `newline`) are set on `import_settings`; export-visible attributes (`write_header`, `export_path`, `export_only_visible`, `export_order`, `fields`) remain untouched.

5. **Settings dialog preserves import settings**: `SettingsDialog.get_config()` now constructs a `CsvConfig` with the form's export settings but retains `self._config.csv.import_settings`. This prevents the dialog from overwriting auto-detected import settings with the export form values.

### Files changed

| File | Change |
|------|--------|
| `src/product_description_tool/config.py` | Added `CsvReadSettings`, `CsvWriteSettings`; refactored `CsvConfig` with sub-objects + backward compat properties; updated `from_dict`/`to_dict` |
| `src/product_description_tool/csv_repository.py` | `load()` accepts `CsvReadSettings`, `save()` accepts `CsvWriteSettings`; renamed `_dialect_from_config` → `_dialect_from_settings` |
| `src/product_description_tool/main_window.py` | Read paths use `.import_settings`; write paths use `.export_settings`; first-import seeding in `load_csv()`; settings dialog only updates export settings |
| `src/product_description_tool/dialogs.py` | `get_config()` preserves import settings from dialog's initial config |
| `tests/test_config.py` | New tests for split model, backward compat, legacy handling, CsvReadSettings/CsvWriteSettings serialization |
| `tests/test_csv_repository.py` | Updated all tests to use `CsvReadSettings`/`CsvWriteSettings`; new test for default `CsvConfig` export_order round-trip |
| `tests/test_main_window.py` | New `TestCsvImportExportSettings` class: first-import seeding, subsequent import preservation, settings dialog import preservation |
| `project/csv-import-heuristics-restart/status.md` | Updated with implementation status |
| `project/csv-import-heuristics-restart/action-register.md` | AR-2 and AR-5 closed |
