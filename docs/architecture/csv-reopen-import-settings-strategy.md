# CSV Reopen Import Settings Strategy

## Context

Feature workspace: `project/csv-reopen-import-settings/`

Relevant specification areas:
- Use Case 3: Open an Existing Project
- Use Case 4: Save the Current Project
- Use Case 5: Import a CSV File
- Use Case 6: Export the CSV

The user has now provided an authoritative rule set that supersedes the earlier reopen discussion:

- The user should not need to care about the format of the imported CSV.
- Whatever format the CSV had when imported should remain the format the project operates on.
- Project settings encompass only the explicit **Export CSV** feature.
- Export settings may be seeded from the imported CSV format on initial import.
- The imported/project CSV is saved using the same format as used for importing and is not controlled by project settings.
- Any prior requirement that gives project settings control over the project-working CSV format must be removed.

## Architectural contract

There are **two distinct CSV contracts** and they must stay separate.

### 1. Project-working CSV contract

This contract governs the CSV that the project imports, keeps in memory, saves as its sibling project CSV, and reopens later.

- The low-level format contract is the format established by CSV import.
- In the current persisted model, `project.csv.import_settings` is the durable holder of that format contract.
- `save_project()` must write the sibling project CSV using that persisted import-derived format.
- `open_project()` must read the sibling project CSV using that same persisted import-derived format.
- The user does not manage this contract through project settings.

### 2. Explicit export CSV contract

This contract governs only the user-invoked **Export CSV** action.

- `project.csv.export_settings` belongs only to explicit export behavior.
- Export settings may be initialized from detected import settings on first successful import.
- After seeding, export settings are independent and may diverge without affecting project save/reopen.
- Changes in project settings affect explicit export output only, not the sibling project CSV used for normal project persistence.

## Decision

**Reject the prior export-settings-based reopen recommendation.**

The correct contract is:

- project save/reopen uses the import-derived project-working CSV format, and
- explicit export uses export settings.

For backward compatibility, a project that truly has **no persisted working-CSV import settings** may use reopen heuristics as a one-time fallback. That fallback does not change the primary contract for current projects.

Under this rule, the sibling project CSV is a persistence artifact of the imported working document, not an export artifact controlled by project settings.

## Why this is the correct boundary

- It matches the user's mental model: imported CSV format stays stable without extra user work.
- It keeps project settings scoped to the explicit export feature only.
- It prevents unrelated settings changes from silently changing the format of the project-owned CSV.
- It restores a coherent artifact boundary:
  - import/reopen/save of the project-working CSV use one stable contract,
  - explicit export uses a separate user-configurable contract.

## Rejected prior recommendation

### Reopen/save using `project.csv.export_settings`

Reject.

Reason: this makes the project-working CSV format depend on project settings that the user expects to affect only explicit export. It also allows unrelated settings edits to rewrite the project CSV in a different format, violating the user's requirement that the project continue operating on the imported CSV format.

### Heuristics as the primary reopen contract for the sibling project CSV

Reject.

Reason: once a CSV has been imported successfully, the project already has a persisted deterministic working-format contract. Reopen should use that contract, not inference.

## Backward-compatibility fallback for missing persisted import settings

### Rule

Heuristic reopen is allowed **only** when the saved project data proves that import settings are absent, not merely default-valued.

- If the persisted project payload contains `csv.import_settings`, reopen must use those persisted values.
- If the persisted project payload is legacy flat CSV config data (no nested `import_settings` / `export_settings` structure), existing legacy loading rules remain the contract and heuristics are not used.
- If the persisted project payload uses the new nested CSV shape but omits `csv.import_settings` entirely, reopen may fall back to `CsvRepository.detect_settings()` on the sibling project CSV before loading it.
- If the sibling CSV does not exist, the existing empty-document path still applies.

### Why absence must be shape-based, not value-based

The current dataclass loaders normalize missing settings into concrete defaults. After `CsvConfig.from_dict()` runs, these two cases become indistinguishable:

- import settings were intentionally persisted with default values, and
- import settings were never persisted at all.

Therefore backward-compatibility detection must be based on the **raw project JSON shape** before config normalization, not on comparisons against default `CsvReadSettings` values.

### Required implementation boundary

The absence check belongs at the repository/load boundary where raw persisted data is still visible.

- Preferred location: `ProjectRepository.load()` or a closely related raw-project parsing helper.
- The loader should preserve a small explicit signal such as “import settings persisted: yes/no” for the reopen path.
- `MainWindow.open_project()` should branch on that explicit signal:
  1. persisted import settings present -> load sibling CSV with `project.csv.import_settings`,
  2. persisted import settings absent under the new nested shape -> detect settings heuristically, then load,
  3. no sibling CSV -> construct the empty document as today.

### Guardrails

- Do not treat `CsvReadSettings()` default values as proof of absence.
- Do not run heuristics when persisted import settings are present, even if they equal default values.
- Do not let the fallback overwrite or reinterpret the normal contract for projects saved by current versions.
- After a successful reopen through the backward-compatibility path, the next project save should persist the detected working-CSV import settings so later reopens return to the normal deterministic contract.

## Behavioral contract after correction

### Explicit CSV import

- `MainWindow.load_csv()` auto-detects low-level CSV parsing settings.
- The detected settings persist to `project.csv.import_settings`.
- Those settings define the working/project CSV format contract.
- On first successful import, the application may seed `project.csv.export_settings` from the same detected values exactly once.

### Project save

- `save_project()` writes project metadata to `*.project.json`.
- `save_project()` writes the sibling `*.csv` using `project.csv.import_settings`, not `project.csv.export_settings`.

### Project reopen

- `open_project()` reads the sibling `*.csv` using `project.csv.import_settings`.
- Reopen does not use `project.csv.export_settings` for the sibling project CSV.
- Reopen does not use heuristics as the normal path for the sibling project CSV.
- Reopen may use heuristics only as a backward-compatibility fallback when raw persisted project data shows that `csv.import_settings` is absent under the new nested CSV config shape.

### Explicit export

- The explicit **Export CSV** flow writes using `project.csv.export_settings`.
- Export path, export visibility options, header-writing choices, and export-oriented formatting remain export-only concerns.

## Implementation direction

This is not an implementation artifact, but the code implications are now clear:

1. `MainWindow.save_project()` currently writes the sibling project CSV with `project.csv.export_settings`; that behavior is architecturally wrong under the new contract.
2. `MainWindow.open_project()` already reads with `project.csv.import_settings`; that direction is aligned with the new contract and should remain the reopen path.
3. The reopen path needs an explicit raw-payload absence check so backward-compatibility fallback can distinguish “missing” from “persisted defaults”.
4. Settings-dialog wiring should continue treating project CSV settings as export-only.
5. No new persisted schema is required for the blocker fix if `project.csv.import_settings` remains the project-working CSV format contract; however, some non-normalized load metadata or equivalent raw-shape signal is required during reopen.

## Specification impact

**Yes, the spec must be updated again before implementation proceeds.**

Minimum required updates:

- **Use Case 3: Open an Existing Project**
  - state that the sibling project CSV is reopened with persisted import-derived settings,
  - and that heuristics are allowed only as a backward-compatibility fallback when those settings are absent in persisted new-shape project data.
- **Use Case 4: Save the Current Project**
  - state that the sibling project CSV is saved with the same import-derived format used for the working/project CSV contract.
- **Use Case 5: Import a CSV File**
  - keep the first-import seeding rule for export settings,
  - clarify that detected import settings become the ongoing working/project CSV format,
  - and that a backward-compatibility reopen fallback should repersist detected import settings on the next save.
- **Use Case 6: Export the CSV**
  - remove any language that makes export settings the reopen/save contract for the sibling project CSV.

## Tradeoffs

### Benefits

- Aligns exactly with the clarified user requirement.
- Keeps the user insulated from CSV format management in the normal import/save/reopen workflow.
- Preserves a clean semantic separation between project persistence and explicit export.
- Provides a safe compatibility path for already-saved projects missing the newer persisted working-format data.
- Avoids schema expansion for the blocker fix.

### Costs

- The current naming `import_settings` now carries both “last import” and “project-working CSV format” meaning.
- Current implementation must be corrected because save and explicit export presently share the same write settings.
- Reopen logic must retain a raw-shape signal long enough to distinguish absent settings from normalized defaults.

Those costs are acceptable for this blocker because they preserve the user's required behavior without introducing a new persisted shape.

## Non-goals

- Broad CSV workflow redesign beyond fixing reopen/save contract correctness.
- New UI for managing project-working CSV format.
- New persisted CSV settings objects solely for this blocker fix.
