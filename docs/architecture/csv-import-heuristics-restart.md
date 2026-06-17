# CSV Import Heuristics Restart

## Problem Statement

The clarified user intent changes the design center:

- import should auto-detect CSV parsing settings and continue without burdening the user in the normal path,
- export should use user/project-configured settings,
- import settings and export settings may differ,
- the first successful import should seed initial export settings from the detected import settings,
- before that first import, export settings are effectively not yet established.

This affects **Use Case 1**, **Use Case 3**, **Use Case 4**, **Use Case 5**, and **Use Case 6** in `docs/specification.md`.

## Scope

In scope:
- separating persisted import settings from persisted export settings,
- defining first-import export seeding,
- keeping import auto-detection as the primary workflow,
- defining exception-path UX when auto-detection fails,
- identifying required contract changes in config/project persistence.

Out of scope:
- source-column auto-detection,
- prompt/output-column inference,
- prompt or field remapping logic,
- batch-processing behavior changes.

## Architectural Decisions

### 1. Import and export settings are separate persisted concerns

The project needs two different CSV-setting roles:

1. **Import settings**: the parsing settings last established by successful import/open behavior for reading CSV data.
2. **Export settings**: the user/project-controlled settings used for project save and explicit export writes.

These settings may start equal, but they must be allowed to diverge afterward.

### 2. Import auto-detection is primary

Normal CSV import should be:

1. sniff file,
2. derive import settings,
3. load file,
4. refresh UI.

No confirmation dialog should be required on the normal success path. A review/edit dialog is only justified as a recovery path after auto-detection fails or yields an unusable parse.

### 3. First successful import seeds export settings once

After the first successful import into a project that does not yet have established export settings:

- copy the detected import parsing values into export settings,
- mark export settings as established,
- allow later user editing of export settings through project settings.

Subsequent imports update import settings only. They must not silently rewrite existing export settings.

### 4. Export settings remain authoritative for writes

Project save and CSV export must always use export settings, not the latest sniffed import settings, except when those export settings were initially seeded by the first successful import.

### 5. Heuristics remain parsing-only

Heuristics may inspect file bytes/text to guess:

- encoding,
- delimiter,
- quotechar,
- newline.

They must not infer:

- source columns,
- prompt output columns,
- prompt mappings,
- field labels,
- field visibility,
- export order.

## Contract Impact: Current `CsvConfig` is not sufficient

The current persisted `CsvConfig` shape in `config.py` mixes read and write concerns into a single flat object:

- `delimiter`
- `quotechar`
- `encoding`
- `newline`
- `write_header`
- export-only state such as `export_path`, `export_only_visible`, and `export_order`

That model cannot cleanly express all required states:

1. **separate import vs export parsing settings**,
2. **export settings not yet established before first import**,
3. **first-import seeding already consumed**,
4. **later divergence between import and export settings**.

Because `CsvConfig` always contains concrete parsing values, the current model also cannot distinguish:

- export settings intentionally chosen by the user, versus
- placeholder defaults present only because the dataclass requires concrete values.

## Recommended Persistence Shape

Recommended direction:

- keep backward compatibility during migration,
- introduce explicit sub-structures rather than more hidden semantics on the existing flat fields.

Preferred conceptual shape:

- `csv.import_settings`
- `csv.export_settings`
- `csv.export_settings_initialized` (or equivalent explicit state)
- existing field/export metadata (`fields`, `export_order`, `export_path`, `export_only_visible`) attached to export behavior where appropriate.

Two practical implementation options:

### Option A: Split dataclasses under `CsvConfig` (preferred)

- `CsvReadSettings` for `delimiter`, `quotechar`, `encoding`, `newline`
- `CsvWriteSettings` for `delimiter`, `quotechar`, `encoding`, `newline`, `write_header`, `export_path`, `export_only_visible`, `export_order`, `fields`
- top-level `CsvConfig` becomes a container for both plus initialization state

Why preferred:

- makes ownership clearer,
- makes first-import initialization explicit,
- reduces future ambiguity in `main_window.py` and `csv_repository.py`.

### Option B: Keep `CsvConfig` flat but add companion state

- retain current export-facing fields for compatibility,
- add a separate persisted import-settings structure,
- add an explicit `export_initialized` boolean or provenance marker.

Why less desirable:

- preserves mixed responsibilities,
- increases risk that future call sites keep using the wrong settings object.

## Recommended Module Boundaries

### `config.py`

Own the dataclass contract and JSON serialization for the separated CSV settings model.

Required outcomes:
- represent import settings separately from export settings,
- represent "export settings not yet established" explicitly,
- preserve compatibility for older saved configs/projects where feasible.

### `project.py`

Own the persisted project-file shape for the new CSV contract.

Required outcomes:
- load/save both import and export settings,
- preserve upgrade behavior for legacy project files that only contain one flat CSV settings block,
- define how first-import-seeded export settings are serialized.

### `csv_repository.py`

Keep file parsing/sniffing logic here, not in `MainWindow`.

Recommended responsibilities:
- add a pure helper that inspects a candidate CSV file and returns guessed parsing attributes,
- keep `load()` focused on reading with already-resolved import settings,
- keep `save()` focused on writing with export settings,
- avoid mixing UI decisions with repository code.

Suggested sniffing result artifact can be a small dataclass containing:
- guessed values per parsing attribute,
- optional notes/confidence,
- enough data for a failure-recovery dialog if one is needed.

### `dialogs.py`

Do not add mandatory import confirmation UI for the normal path.

If needed, add only a targeted recovery dialog for failed auto-detection / failed parse retry.

Reasoning:
- it preserves the clarified requirement that import should not burden the user,
- it keeps manual intervention exceptional,
- it avoids turning every import into a settings exercise.

### `main_window.py`

`MainWindow` remains the workflow orchestrator:

- select file,
- ask repository/service layer for detected import settings,
- import immediately on success,
- seed export settings only if not yet established,
- update project/document/session state,
- only invoke recovery UI on failure.

`MainWindow` should not implement sniffing rules directly.

## Recommended Import Flow

1. User selects a CSV file.
2. Main window asks a resolver/repository helper to detect import parsing settings.
3. Application attempts import immediately with those detected settings.
4. On success, persist the effective import settings into project import state.
5. If export settings are not yet established, copy the effective import settings into export settings and mark them established.
6. Refresh document-dependent UI and set dirty state.
7. On failure, keep the current document unchanged and optionally offer a recovery dialog initialized from the detected values plus defaults.

## Save/Open Consequences

### Open project

When opening a saved project sibling CSV, use persisted import settings to read the sibling file, not export settings.

### Save project / export CSV

When saving the project sibling CSV or exporting to another CSV path, use export settings.

This is the core boundary that prevents read/write concerns from collapsing back together.

## Recommended Implementation Sequence

1. **Contract first**: change `CsvConfig`/project persistence to represent separated import/export settings and export-initialization state.
2. **Repository second**: add sniffing/result dataclass and read/write APIs that consume the right settings object.
3. **Workflow third**: update `MainWindow.load_csv()`, project open, save, and export paths to use the separated settings consistently.
4. **UI fourth**: adjust settings UI to edit export settings only, plus optional recovery UI for import failure.
5. **QA last**: add tests after the contract and flow are stable.

## Parallelization / Ownership

This is **not** a safe parallel code-writing task inside `src/product_description_tool/`.

Reasons:
- it changes the persisted config/project contract,
- it spans `config.py`, `project.py`, `csv_repository.py`, and `main_window.py`,
- it likely touches `dialogs.py` and settings UI semantics,
- read/write call sites must be updated consistently.

Recommended execution model:
- one Product Developer implementation lane for `src/product_description_tool/`,
- QA can work after the contract and flow are stable,
- architect review is required after implementation because this change spans multiple modules and alters persisted/shared behavior.

## Decision Points for the Implementer

1. **Migration behavior for legacy project files**
   - decide how a legacy flat `csv` block maps into split import/export settings,
   - recommended default: treat legacy values as already-established export settings and also use them as initial import settings for backward compatibility.

2. **How to represent "export not yet established"**
   - explicit boolean/state flag is preferred,
   - avoid inferring it from empty strings alone.

3. **Failure recovery UX**
   - optional targeted retry dialog,
   - do not require it on successful imports.

4. **Encoding heuristics scope**
   - with current dependencies, stay conservative unless a new dependency is explicitly approved,
   - acceptable baseline: BOM-aware handling, UTF-family checks, then fallback.

## Open Questions

1. Should app-level CSV defaults also be split into import-default and export-default structures, or should app-level settings remain export-oriented while import uses transient detection plus fallback defaults? Recommended answer: keep app-level settings export-oriented unless a later requirement explicitly introduces import presets.
2. `ConfigStore.save()` currently does not persist app-level CSV settings at all. That inconsistency should be reconciled during implementation because the new contract makes CSV-setting roles more explicit.
3. Should opening an existing project with no sibling CSV but with saved import settings preserve those import settings unchanged for the next import? Recommended answer: yes.
