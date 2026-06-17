# CSV Reopen Import Settings — Validation Report

**Date:** 2026-06-18  
**Scope:** QA regression tests for the CSV reopen blocker fix (feature workspace `project/csv-reopen-import-settings/`)  
**Artifact type:** QA report / validation record

## Summary

All regression tests pass. The implementation correctly enforces the two-contract separation (project-working CSV vs explicit export CSV) and the backward-compatibility reopen fallback. The self-healing invariant after fallback reopen is verified.

## Coverage

### 1. Sibling project CSV save/reopen uses import-derived settings (Use Cases 4, 6)

**Test:** `test_save_project_writes_sibling_csv_with_import_settings_not_export_settings`

Verifies that `MainWindow.save_project()` writes the sibling `.csv` file using the import-derived low-level settings (`delimiter`, `quotechar`, `encoding`, `newline`) rather than the export settings. The test:
- Imports a CSV with `;` delimiter.
- Changes export settings to `|` delimiter.
- Saves the project.
- Reads the sibling CSV directly — confirms `;` (import-derived) delimiter, not `|` (export).

**Test:** `test_open_project_reopens_sibling_csv_with_import_settings`

Verifies that `MainWindow.open_project()` reads the sibling CSV using the persisted import-derived settings even when export settings have diverged. The test:
- Imports a CSV with `;` delimiter.
- Changes export settings to `|` delimiter.
- Saves and reopens the project.
- Confirms `import_settings.delimiter` is `";"` (import-derived, not export).
- Confirms all rows load correctly.

### 2. Settings UI wording "Export CSV options" (Use Case 1, step 6)

**Test:** `test_settings_dialog_csv_tab_label_is_export_csv_options`

Verifies the CSV configuration tab in `SettingsDialog` is labelled `"Export CSV options"` to make its export-only scope visible in the UI. The test checks `dialog.tabs.tabText(2)` (third tab, after Provider and Generation).

### 3. Backward-compatible reopen fallback when new-shape payload omits `csv.import_settings` (Use Case 3)

**Test:** `test_open_project_missing_import_settings_uses_fallback`

Verifies that when the raw project JSON uses the new nested CSV shape but truly lacks `csv.import_settings`, reopen falls back to `CsvRepository.detect_settings()` on the sibling CSV. The test:
- Creates a project with nested CSV shape.
- Manually removes `import_settings` from the JSON.
- Creates a sibling CSV with `;` delimiter.
- Confirms `ProjectRepository.csv_import_settings_usable()` returns `False`.
- Opens the project — verifies import settings are detected as `;`.
- Verifies data loads correctly.

**Unit tests for `csv_import_settings_usable()` in `test_project.py`:**

| Test | Input shape | Expected |
|------|-------------|----------|
| `test_new_shape_with_import_settings_returns_true` | Nested CSV with `import_settings` | `True` |
| `test_new_shape_without_import_settings_returns_false` | Nested CSV without `import_settings` | `False` |
| `test_legacy_flat_shape_returns_true` | Legacy flat CSV config | `True` |
| `test_nested_with_all_settings_returns_true` | Nested with both settings | `True` |
| `test_empty_csv_key_legacy_fallback` | `csv: {}` (empty dict) | `True` (legacy) |
| `test_no_csv_key_legacy_fallback` | No `csv` key at all | `True` (legacy) |

These confirm the shape-based detection rule from the architecture strategy: absence detection is based on raw JSON key presence, not value comparison against defaults.

### 4. Self-healing persistence after fallback (Use Cases 3, 4 invariant)

**Test:** `test_self_healing_after_fallback_reopen`

Verifies that after a successful backward-compatibility fallback reopen, the next `save_project()` persists the detected import settings so later reopens return to the deterministic normal contract. The test:
- Sets up a project requiring fallback reopen.
- Opens it (triggers fallback with `;` detection).
- Saves the project again.
- Reads the JSON and confirms `import_settings` is present with the correct `delimiter` and `quotechar`.
- Confirms `csv_import_settings_usable()` returns `True` for the healed file.

## Test Files Modified

| File | Change |
|------|--------|
| `tests/test_main_window.py` | Added 4 tests to `TestCsvImportExportSettings` (lines ~1812–end) |
| `tests/test_dialogs.py` | Added 1 test: `test_settings_dialog_csv_tab_label_is_export_csv_options` |
| `tests/test_project.py` | Added 6 tests in `TestCsvImportSettingsUsable` class |

## Results

- **Total suite:** 423 passed, 0 failed
- **New tests:** 11 passed, 0 failed
- **Regressions:** None detected

## Findings

All items from the action register (ARC-1 through ARC-4) are addressed:

| ID | Finding status | Verification |
|----|---------------|--------------|
| ARC-1 | **closed** | Export-settings-based reopen is rejected; sibling CSV uses import-derived settings (verified by save/reopen tests). |
| ARC-2 | **closed** | Spec updated: Use Cases 1, 3, 4, 5, 6, 19 reflect correct contract. Tab label verified as "Export CSV options". |
| ARC-3 | **closed** | `save_project()` uses import-derived settings (verified by `test_save_project_writes_sibling_csv_with_import_settings_not_export_settings`). |
| ARC-4 | **closed** | `csv_import_settings_usable()` uses shape-based raw JSON detection (verified by 6 unit tests). Fallback branch verified end-to-end. |

## Coverage Gaps

No critical gaps identified. Potential enhancement areas (non-blocking):

1. The self-healing test could also verify that `export_settings` remain unchanged after the fallback+save cycle (currently implied but not explicitly asserted).
2. A corner-case test for the scenario where both the sibling CSV does not exist AND `import_settings` are missing — the `_empty_document_for_project` path is exercised indirectly by existing tests.
