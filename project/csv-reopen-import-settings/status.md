# Status — IMPLEMENTED

- Current state: **all items closed.**
- Active step: none.
- Blockers: none.
- Next actions:
   - QA may add regression coverage for the backward-compatibility reopen fallback and for divergence between project-working CSV format and explicit export settings.
   - Architect review is handed off if required.

## QA validation result

- **2026-06-18**: QA regression tests added and verified. 11 new tests across `test_main_window.py` (4), `test_dialogs.py` (1), and `test_project.py` (6).
- All 423 tests pass (0 failed).
- QA report: `docs/qa/csv-reopen-import-settings-validation.md`.
- Action register: QA-1 closed. No open findings.

## Implementation result

### Earlier (previous implementation step)

- `main_window.py` — `save_project()` writes the sibling project CSV using import-derived low-level settings (delimiter, quotechar, encoding, newline) instead of `project.csv.export_settings`. A new `CsvWriteSettings` is constructed from the import-derived values with `write_header=True` and defaults for export-oriented fields.
- `dialogs.py` — CSV settings tab label changed from `"CSV"` to `"Export CSV options"` to make the export-only scope visible in the UI.
- `_export_csv()` explicitly still uses `project.csv.export_settings` — unchanged and correct.
- `open_project()` already read the sibling CSV using `project.csv.import_settings` — correct and preserved.

### Current step (backward-compatibility fallback)

- `project.py` — added `ProjectRepository.csv_import_settings_usable()` method.
  - Inspects the **raw project JSON** before `CsvConfig.from_dict()` normalisation.
  - Returns `True` for both legacy flat CSV config (compatibly populated) and new nested shape with `import_settings` present.
  - Returns `False` **only** when the new nested CSV config shape exists but `import_settings` is truly absent.
  - This is a shape-based check, not a value-based comparison against defaults.
- `main_window.py` — `open_project()` updated:
  - Before loading the project, checks `csv_import_settings_usable()`.
  - When the flag signals missing `import_settings`, runs `CsvRepository.detect_settings()` on the sibling CSV and overrides `project.csv.import_settings` with detected values.
  - The sibling CSV is then loaded with those detected values.
  - Since `save_project()` reads `project.csv.import_settings`, the next save automatically persists the detected settings — the project self-heals to the normal deterministic contract.
- All source changes respect the flat-package scope: `src/product_description_tool/project.py` and `src/product_description_tool/main_window.py` only.
- Test suite: **412 passed, 0 failed.**

## Architecture result

- The authoritative rule is now fully reflected in spec, architecture guidance, and implementation:
  - Imported CSV format remains the project's working CSV format for save/reopen.
  - Project settings apply only to the explicit Export CSV feature.
  - Export settings may be seeded from first import, but must not control the sibling project CSV.
- The backward-compatibility path is now implemented as specified:
  - Heuristics on reopen only when raw nested payload truly lacks `csv.import_settings`.
  - Detection is shape-based (raw JSON key presence), not value-based (compared to defaults).
  - Legacy flat CSV config payloads are excluded from the fallback.
  - Successful fallback reopen is self-healing: next save persists detected import settings.

## Spec result

- `docs/specification.md` already updated in the previous implementation step (Use Cases 1, 3, 4, 5, 6, and 19).
- The spec now distinguishes:
  - the primary deterministic contract: sibling project CSV save/reopen uses persisted import-derived settings, and
  - the fallback-only compatibility path: heuristic sibling-CSV detection is allowed only when the raw nested project payload truly omits `csv.import_settings`.
- The spec's self-healing requirement is satisfied: the next save after a fallback reopen persists detected import settings.
