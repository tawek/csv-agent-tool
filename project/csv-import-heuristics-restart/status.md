# csv-import-heuristics-restart Status

## Current State

✅ **Architectural review gate passed.** Final confirmation review completed after AR-11 remediation; all findings closed.

## Completed Work

### Contract Changes (`config.py`)
- Added `CsvReadSettings` dataclass for import-oriented CSV parsing parameters (`delimiter`, `quotechar`, `encoding`, `newline`).
- Added `CsvWriteSettings` dataclass for export-oriented CSV settings including all parsing parameters plus `write_header`, `export_path`, `export_only_visible`, `export_order`, `fields`.
- Refactored `CsvConfig` from a flat dataclass to a container with `import_settings`, `export_settings`, and `export_settings_initialized` flag.
- Added backward-compatible properties (`delimiter`, `quotechar`, etc.) that delegate to `export_settings`, ensuring existing call sites continue to work.
- Updated `CsvConfig.from_dict()` to detect legacy flat data (no `import_settings`/`export_settings` keys) and populate both settings from the flat values, marking export as initialized. New-style serialisation uses nested sub-structures.
- Updated `CsvConfig.to_dict()` to produce `{"import_settings": ..., "export_settings": ..., "export_settings_initialized": ...}`.
- **FIX (AR-9):** `ConfigStore.save()` now includes `"csv": config.csv.to_dict()` so app-level CSV settings survive save/load round-trip.

### Repository Changes (`csv_repository.py`)
- `CsvRepository.load()` now accepts `CsvReadSettings` instead of `CsvConfig`.
- `CsvRepository.save()` now accepts `CsvWriteSettings` instead of `CsvConfig`.
- `_dialect_from_config()` renamed to `_dialect_from_settings()` and typed for both `CsvReadSettings | CsvWriteSettings`.
- **NEW (AR-6):** `CsvRepository.detect_settings(path)` — inspects a CSV file and returns detected `CsvReadSettings` with heuristics for encoding, delimiter, quotechar, and newline. Encoding: BOM-aware (utf-8-sig/utf-16-le/utf-16-be), UTF-8, then latin-1 fallback. Newline: CRLF-detection (returns `''`), LF-only (returns `'\n'`), CR-only (returns `''`). Delimiter: scores `,`, `;`, `\t`, `|`, `^`, `~`, `:` by per-line field-count consistency with quotechar-aware parsing, with tiebreakers preferring `;` > `,` > others and penalising the non-matching quotechar. Falls back to `CsvReadSettings` defaults on error or single-column data.
- **NEW (AR-6):** Helper methods `_detect_encoding`, `_detect_newline`, `_detect_dialect` factored for testability.

### Workflow Changes (`main_window.py`)
- `open_project()`: loads sibling CSV using `project.csv.import_settings`.
- `load_csv()`: **REWRITTEN (AR-6/AR-7)** — now calls `csv_repository.detect_settings(path)` first to obtain file-specific heuristics, uses those detected settings for loading, persists the **full** `CsvReadSettings` (encoding, delimiter, quotechar, newline) as `import_settings`, and on first import seeds the **full** parsing contract (encoding, delimiter, quotechar, newline) into `export_settings`.
- `save_project()`: saves sibling CSV using `project.csv.export_settings`.
- `_export_csv()`: exports using `project.csv.export_settings`.
- `open_settings()`: updates `project.csv.export_settings` and copies `export_settings_initialized` from the dialog result, preserving import settings (AR-8).
- **FIX (AR-10):** `open_settings()` now also copies `export_settings_initialized` into `self.config.csv` before `ConfigStore.save()`, so the flag persists across app restarts.

### Dialog Changes (`dialogs.py`)
- `SettingsDialog.get_config()` now returns `export_settings_initialized=True` because the user explicitly confirmed settings (AR-8).
- Import settings from the dialog's initial config are still preserved — only export/initialization state changes.

### Tests
- All existing tests updated to use `CsvReadSettings`/`CsvWriteSettings` where applicable.
- New `TestCsvConfigSplitSettings` tests: new-style serialization, divergence, backward compat properties, legacy flat dict handling.
- New `TestCsvReadSettings` and `TestCsvWriteSettings` serialization tests.
- **NEW (AR-6):** `TestDetectSettings` in `test_csv_repository.py` — 10 test cases covering semicolon/comma/tab/pipe delimiters, UTF-8/no-BOM/BOM encoding detection, LF/CRLF newline detection, single-quote quotechar detection, single-column fallback, and missing-file defaults.
- **EXPANDED (AR-7):** `TestCsvImportExportSettings` in `test_main_window.py` — existing tests now verify `encoding` and `newline` alongside `delimiter`/`quotechar`; new `test_first_import_persists_full_import_settings` confirms the full detected contract is recorded as import settings.
- **NEW (AR-8):** `test_open_settings_before_first_import_marks_export_initialized` — after confirming Settings before any import, export settings are marked established.
- **NEW (AR-8):** `test_first_import_does_not_overwrite_manual_export_settings_after_settings` — when export settings are established (via Settings), first import does not overwrite them.
- **NEW (AR-9):** `TestConfigStoreRoundTrip` in `test_config.py` — 5 tests covering custom settings survival, fresh-default round-trip, import/export divergence round-trip, nonexistent-file defaults, and legacy (pre-AR-9) config file compatibility.
- **NEW (AR-10):** `test_open_settings_updates_config_csv_export_settings_initialized` — verifies `self.config.csv.export_settings_initialized` is set to `True` after confirming Settings.
- **NEW (AR-10):** `test_open_settings_persists_export_settings_initialized_after_restart` — verifies the flag survives ConfigStore save/load round-trip after a Settings confirmation.

## Test Results

All 413 tests passing: 22 dialog tests, 98 config+main-window tests (combined), plus CSV repository and provider tests.

## Architect Review Outcome

- **Decision:** ✅ **Gate passed.** All findings closed.
- **All findings:**
  - **AR-1** — ✅ Discarded misaligned work and restarted.
  - **AR-2** — ✅ `CsvConfig` now has split `import_settings`/`export_settings` with `export_settings_initialized` flag.
  - **AR-3** — ✅ (rejected) Normal-path import-review dialog requirement removed.
  - **AR-4** — ✅ App-level CSV persistence concern resolved by the later AR-9 remediation.
  - **AR-5** — ✅ Call sites updated: open/import uses import settings, save/export uses export settings.
  - **AR-6** — ✅ `CsvRepository.detect_settings()` owns import auto-detection.
  - **AR-7** — ✅ Full parsing contract (encoding, delimiter, quotechar, newline) persisted in import settings and seeded into export settings on first import.
  - **AR-8** — ✅ Settings dialog marks export as initialized; main window copies the flag.
  - **AR-9** — ✅ `ConfigStore.save()` includes `csv` section; legacy config backward compatible.
  - **AR-10** — ✅ `MainWindow.open_settings()` copies `export_settings_initialized` into `self.config.csv` before persistence, ensuring the flag survives restart.
  - **AR-11** — ✅ `SettingsDialog.get_config()` fallback default changed from `,` to `;`; new test `test_settings_dialog_cleared_delimiter_falls_back_to_semicolon` covers the cleared-field case.

## Changes Made (AR-11)

**File: `src/product_description_tool/dialogs.py`**
- Line 803: `_single_char_value(..., default=",")` → `_single_char_value(..., default=";")` so a cleared delimiter field falls back to `;` per Use Case 1.

**File: `tests/test_dialogs.py`**
- Added `test_settings_dialog_cleared_delimiter_falls_back_to_semicolon` — explicitly clears the delimiter field and asserts `get_config().csv.delimiter == ";"`.
