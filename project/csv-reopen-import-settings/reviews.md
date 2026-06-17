# Reviews

## 2026-06-18 — QA regression-test review

- Reviewer: QA Engineer
- Inputs reviewed:
  - `project/csv-reopen-import-settings/implementation-notes.md`
  - `project/csv-reopen-import-settings/status.md`
  - `project/csv-reopen-import-settings/action-register.md`
  - `project/csv-reopen-import-settings/reviews.md` (prior architect addenda)
  - `docs/architecture/csv-reopen-import-settings-strategy.md`
  - `docs/specification.md`
  - `src/product_description_tool/main_window.py`
  - `src/product_description_tool/project.py`
  - `src/product_description_tool/dialogs.py`
  - `src/product_description_tool/config.py`
  - `tests/test_main_window.py` (existing + new tests)
  - `tests/test_dialogs.py` (existing + new test)
  - `tests/test_project.py` (existing + new tests)
- Summary:
  - 11 new regression tests added covering all four required areas:
    1. Sibling project CSV save/reopen using import-derived settings rather than export settings.
    2. Settings UI tab label reads "Export CSV options".
    3. Backward-compatible reopen fallback when new-shape project payload omits `csv.import_settings`.
    4. Self-healing persistence after fallback reopen.
  - `csv_import_settings_usable()` tested at the unit level for all shape permutations.
  - All 423 tests pass (412 pre-existing + 11 new).
  - No regressions.
- Decision: **Approved — no open findings.**

## 2026-06-18 — Architect pre-implementation review

- Reviewer: Code Architect
- Inputs reviewed:
  - `project/csv-reopen-import-settings/implementation-notes.md`
  - `project/csv-reopen-import-settings/status.md`
  - `docs/specification.md`
  - `src/product_description_tool/main_window.py`
  - `src/product_description_tool/config.py`
  - `src/product_description_tool/csv_repository.py`
  - `tests/test_main_window.py` CSV import/export settings tests
- Summary:
  - Confirmed an architectural contract mismatch: project reopen reads the sibling project CSV with persisted `import_settings`, while project save writes that sibling CSV with `export_settings`.
  - Recommended strategy: auto-detect read settings from the sibling project CSV during reopen.
  - Rejected strategy: reusing first-import settings for reopen, because it binds reopen to the wrong artifact contract once import and export settings diverge.
  - Specification update is required before implementation because Use Case 3 currently documents the incorrect reopen contract.
- Decision: **Approved for implementation after spec update**.
- Output artifact:
  - `docs/architecture/csv-reopen-import-settings-strategy.md`

## 2026-06-18 — Architect reassessment addendum

- Reviewer: Code Architect
- Additional inputs reviewed:
  - user clarification that they changed non-CSV settings, then saved/exited
  - `docs/architecture/csv-reopen-import-settings-strategy.md`
  - `src/product_description_tool/main_window.py`
  - `src/product_description_tool/config.py`
- Reassessment summary:
  - The prior recommendation to use reopen heuristics is no longer the preferred contract.
  - Current save behavior is decisive: `save_project()` rewrites the sibling project CSV with `project.csv.export_settings`, even when the save was triggered by unrelated settings changes.
  - Therefore the sibling CSV's most coherent reopen contract is the same persisted low-level export settings used to write it.
  - Persisted `import_settings` remain the contract of the last explicit external import, not of the project-owned sibling CSV.
  - Heuristics remain appropriate for explicit import of unknown external CSV files, but not as the primary reopen contract for a project-managed saved artifact.
- Revised decision: **Approved for implementation after spec update, with reopen based on persisted export settings rather than heuristics.**

## 2026-06-18 — Architect superseding addendum

- Reviewer: Code Architect
- Additional inputs reviewed:
  - authoritative user clarification recorded in `project/csv-reopen-import-settings/implementation-notes.md`
  - `docs/architecture/csv-reopen-import-settings-strategy.md`
  - `src/product_description_tool/main_window.py`
  - `src/product_description_tool/config.py`
  - `src/product_description_tool/csv_repository.py`
- Superseding summary:
  - The earlier export-settings-based reopen recommendation is now explicitly rejected.
  - The correct boundary is between the **project-working CSV** contract and the **explicit export CSV** contract.
  - The imported CSV format must remain the format the project saves and reopens with.
  - Project settings control only the explicit export feature.
  - Export settings may still be seeded from first import, but they must not control the sibling project CSV used for normal project persistence.
  - Under the current persisted model, `project.csv.import_settings` remains the right durable contract for the project-working CSV format.
  - Current implementation is architecturally inconsistent because `save_project()` writes the sibling project CSV with `project.csv.export_settings`.
- Superseding decision: **Previous architect recommendation withdrawn. New required direction: spec update first, then implementation must make project save/reopen use import-derived settings for the sibling project CSV, while leaving export settings scoped to explicit export only.**

## 2026-06-18 — Architect backward-compatibility addendum

- Reviewer: Code Architect
- Additional inputs reviewed:
  - `project/csv-reopen-import-settings/implementation-notes.md`
  - `project/csv-reopen-import-settings/status.md`
  - `project/csv-reopen-import-settings/action-register.md`
  - `docs/architecture/csv-reopen-import-settings-strategy.md`
  - `docs/specification.md`
  - `src/product_description_tool/config.py`
  - `src/product_description_tool/project.py`
  - `src/product_description_tool/main_window.py`
- Addendum summary:
  - The primary contract remains unchanged: current projects must persist and use import-derived working CSV settings for sibling project CSV save/reopen.
  - A backward-compatibility reopen heuristic is acceptable only for projects whose persisted data truly lacks `csv.import_settings`.
  - The absence test must be based on the raw persisted project JSON shape before `CsvConfig.from_dict()` normalizes missing values to defaults.
  - Value-based checks against default `CsvReadSettings` are architecturally unsafe because they cannot distinguish “missing” from “persisted default values”.
  - The cleanest boundary is to surface an explicit repository/load-time signal indicating whether import settings were persisted, then branch in the reopen flow on that signal.
  - After a successful backward-compatibility reopen, the next save should repersist detected import settings so the project returns to the normal deterministic contract.
- Decision: **Approved as architecture guidance. Implementation follow-up required for the raw-shape absence check and backward-compatibility reopen fallback.**

## 2026-06-18 — Architect post-implementation review

- Reviewer: Code Architect
- Inputs reviewed:
  - `project/csv-reopen-import-settings/implementation-notes.md`
  - `project/csv-reopen-import-settings/status.md`
  - `project/csv-reopen-import-settings/action-register.md`
  - `project/csv-reopen-import-settings/reviews.md`
  - `docs/architecture/csv-reopen-import-settings-strategy.md`
  - `docs/specification.md`
  - `src/product_description_tool/main_window.py`
  - `src/product_description_tool/project.py`
  - `src/product_description_tool/dialogs.py`
  - `tests/test_main_window.py`
  - `tests/test_project.py`
  - `tests/test_dialogs.py`
- Review summary:
  - `MainWindow.save_project()` now restores the intended artifact boundary: the sibling project CSV is written with low-level values from `project.csv.import_settings`, while explicit export remains on `project.csv.export_settings`.
  - `MainWindow.open_project()` still uses `project.csv.import_settings` as the normal reopen contract and now branches to heuristic detection only for the backward-compatibility case.
  - The missing-import-settings fallback is implemented at the repository/load boundary through `ProjectRepository.csv_import_settings_usable()`, which inspects raw persisted JSON shape before `CsvConfig.from_dict()` normalization. This matches the architecture requirement that absence detection be shape-based rather than value-based.
  - The fallback shape handling is appropriately constrained:
    - legacy flat CSV payloads remain on legacy loading rules,
    - nested payloads with persisted `import_settings` do not trigger heuristics,
    - nested payloads missing `import_settings` do trigger heuristic detection,
    - detected settings are written back on the next save via the normal `save_project()` path, giving the required self-healing behavior.
  - `SettingsDialog` tab wording and `MainWindow.open_settings()` behavior keep project CSV settings export-only, which matches the updated specification and user-facing contract.
  - Relevant regression coverage exists for import/export settings separation and preservation of import settings across settings edits, but targeted regression coverage for the nested-shape missing-`csv.import_settings` reopen fallback and the settings-tab wording remains a follow-up gap rather than an architectural blocker.
- Decision: **PASS — architecturally approved.**
- Follow-up:
  - Non-blocking QA follow-up recommended for explicit regression coverage of the backward-compatibility fallback path and export-only settings wording.
