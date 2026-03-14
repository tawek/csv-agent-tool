# Project Model

## Purpose

In this application, a "project" is the editable unit of work. It represents the thing a user creates, opens, modifies, processes, and saves while working on a batch of product descriptions.

The project model is broader than the `.project.json` file alone. In practice it includes:

- project metadata and prompt definitions
- CSV-related settings and field visibility/labels
- the current in-memory CSV document being edited and processed
- the mapping between prompts and output columns

## Core Types

### `Project`

Defined in `src/product_description_tool/project.py`.

`Project` contains:

- `prompts: list[ProjectPrompt]`
- `csv: CsvConfig`

This is the persisted project definition. It does not hold the row data directly. Row data lives in a separate `CsvDocument`.

### `ProjectPrompt`

Each prompt describes one processing target column.

Fields:

- `output_field`: CSV column that will receive generated HTML
- `prompt`: prompt template text, usually containing placeholders like `{{sku}}`
- `enabled`: whether the prompt participates in "Process All"
- `prompt_file`: optional sidecar filename used when the project is saved

Important behavior:

- prompt identity is effectively `output_field`
- `MainWindow.add_prompt()` rejects duplicates by `output_field`
- adding a prompt ensures the output column exists in the working document

### `CsvConfig`

Defined in `src/product_description_tool/config.py`.

This is project-scoped configuration, not just display settings. It controls:

- `original_description`: which column is treated as the source description
- `result_description`: preferred result field
- `fields`: per-column label and visibility metadata
- `delimiter`, `quotechar`, `encoding`, `newline`, `write_header`: CSV I/O behavior

This means a project carries both processing intent and CSV import/export rules.

### `CsvDocument`

Defined in `src/product_description_tool/csv_repository.py`.

This is the live row data currently loaded in the UI:

- `headers`
- `rows`
- `source_path`
- detected/effective CSV dialect settings

`CsvDocument` is runtime state, not part of the `Project` dataclass itself.

## On-Disk Layout

Saving a project writes more than one file.

Example:

```text
catalog.project.json
catalog.csv
summary.prompt.txt
seo.prompt.txt
```

Behavior:

- the project definition is saved to `*.project.json`
- the project's working CSV data is saved to a sibling `*.csv`
- each prompt body is saved into its own sidecar `*.prompt.txt` file

The file naming rules live in `ProjectRepository`:

- `normalize_project_path()` ensures the `.project.json` suffix
- `project_csv_path()` maps `catalog.project.json` to `catalog.csv`
- `_prompt_filename()` sanitizes `output_field` into a prompt filename

## What Is Persisted

Persisted in the project:

- prompt list
- enabled/disabled state per prompt
- prompt-to-output-column mapping
- project CSV settings
- project field labels/visibility
- prompt text via sidecar files

Persisted in the sibling project CSV:

- current headers
- current row values, including generated output columns

Not persisted as part of the project file itself:

- current table selection
- current filters
- activity dialog state
- whether a background worker is running
- unsaved-modified flag
- imported/exported external CSV path

## Lifecycle In The UI

The main lifecycle lives in `src/product_description_tool/main_window.py`.

### New Project

`new_project()`:

- checks for unsaved changes
- creates a fresh `Project` using `_default_project()`
- resets the `CsvDocument` to empty headers and rows
- clears `project_path`
- clears `current_external_csv_path`
- clears filters

The default project inherits CSV defaults from the current app config:

```python
Project(csv=CsvConfig.from_dict(self.config.csv.to_dict()))
```

### Open Project

`open_project()`:

- loads `Project` from `*.project.json`
- resolves the sibling `*.csv`
- loads that CSV if it exists
- otherwise creates an empty `CsvDocument` using field config keys and prompt output fields
- resets `current_external_csv_path`

This is important: opening a project is expected to restore both the project definition and its project-owned CSV dataset when available.

### Save Project

`save_project()`:

- writes the `Project`
- writes the sibling project CSV using `self.project.csv`
- updates `project_path`
- clears the dirty flag

This is the canonical save path for a user's work session.

## External CSV Import/Export vs Project Save

There are two distinct CSV flows in the app.

### Project-owned CSV

Used by `open_project()` and `save_project()`.

- path is derived from the project path
- treated as the durable dataset belonging to the project

### External CSV import/export

Used by `load_csv()` and `save_csv()`.

- `load_csv()` imports arbitrary CSV into the current project session
- `save_csv()` exports the current `CsvDocument` to an arbitrary location
- this path is tracked separately as `current_external_csv_path`

This distinction matters for agents. Importing a CSV does not make that file the project file. Saving the project later writes to the project sibling CSV, not back to the imported source path.

## How Processing Uses The Project

The project defines what processing means.

### Prompt-driven processing

Each `ProjectPrompt` corresponds to one generation pass into one output column.

- `preview_selected_row()` runs the current prompt against the selected row only
- `process_all_rows()` runs all enabled prompts across all visible rows

Visible rows matter because filters limit processing scope. `process_all_rows()` uses `_visible_row_specs()`, so hidden rows are skipped.

### Template validation

Before processing, `_validate_ready_for_generation()` checks:

- the document has rows
- `project.csv.original_description` exists as a real column
- every prompt template only references known CSV headers

Placeholder validation is implemented by `PromptRenderer`.

### Output-column invariants

Prompt output columns are treated as required project columns.

`_sync_project_with_document()` ensures:

- every document header has a `FieldConfig`
- every prompt `output_field` exists as a column in the `CsvDocument`

This is a key invariant for future changes: a prompt should never target a column that does not exist in the current document model.

## Runtime State Around The Project

The live editing session in `MainWindow` combines several pieces:

- `self.project`: persisted project definition
- `self.document`: live CSV data
- `self.project_path`: current saved/opened project path
- `self.current_external_csv_path`: last imported/exported arbitrary CSV path
- `self.filter_patterns`: active table filters
- `self._project_modified`: dirty state

When reasoning about bugs, keep these separate. Many UI issues come from changing one without syncing the others.

## Agent Notes

Future agents working in this area should preserve these behaviors:

- opening a project should still work even if the sibling CSV is missing
- saving a project must continue to save both the project definition and the sibling CSV
- adding a prompt must continue to materialize its output column
- disabling a  prompt should exclude it from "Process All" but not delete its column or content
- filtering the table should continue to scope batch processing
- project CSV settings must remain compatible with `CsvRepository.load()` and `CsvRepository.save()`

Watch for these easy mistakes:

- conflating global app config with project config
- storing row data inside `Project` instead of `CsvDocument`
- breaking the sibling-file contract between `.project.json` and `.csv`
- forgetting that prompt text is stored in sidecar files, not only inline JSON

## Relevant Files

- `src/product_description_tool/project.py`
- `src/product_description_tool/main_window.py`
- `src/product_description_tool/config.py`
- `src/product_description_tool/csv_repository.py`
- `src/product_description_tool/generation.py`
- `src/product_description_tool/worker.py`
- `tests/test_project.py`
- `tests/test_main_window.py`
