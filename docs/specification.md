# Functional Specification

## Overview

Product Description Tool is a desktop batch editor for rewriting product descriptions from CSV data using large-language-model (LLM) backends. Users load CSV files, define prompt templates that map CSV input columns to generated HTML output columns, preview results inline, and export the processed CSV.

The application runs on Python 3.14+ with PySide6, supports Ollama and OpenAI-compatible providers, and is distributed as a packaged desktop binary via PyInstaller.

## Use Case 1: Configure the Application

**Actor:** User (first-time setup)

**Description:** The user configures the LLM provider, generation parameters, and CSV import/export settings.

**Trigger:** User selects **File > Settings** (or clicks the Settings action).

**Preconditions:** The application has started with a default or previously saved `AppConfig`.

**Flow:**

1. A `SettingsDialog` opens with three tabs: **Provider**, **Generation**, and **CSV**.
2. The user selects the active provider from the dropdown (`ollama` or `openai`).
3. For the active provider the user configures:
   - **Ollama:** Base URL, model name, and arbitrary options JSON.
   - **OpenAI-compatible:** Base URL, API key, model name, and arbitrary options JSON.
4. The user can refresh the model list from the active provider endpoint via a refresh button.
5. The user sets generation parameters: temperature (0.0-2.0), top-p (0.0-1.0), max output tokens (1-200000).
6. The user configures CSV I/O: original description column name, delimiter, quote char, encoding, newline character, whether to write headers, and the default state of the "export only visible rows" checkbox (a boolean option).
7. The user manages per-column visibility and display labels through an editable table of fields. They may reset the fields table to match the currently loaded CSV headers.
8. The user confirms or cancels. On confirm, the provider config and generation config are saved to the persistent `ConfigStore` (JSON on disk). The project-scoped `CsvConfig` is applied to the working document and table model.

**Postconditions:** The updated configuration is persisted and immediately applied to the working session.

**Error conditions:** Invalid provider JSON, missing API keys, or unresolvable provider endpoints are reported to the user. CSV tabular field settings must contain single-character delimiters and quote chars.

## Use Case 2: Create a New Project

**Actor:** User

**Description:** The user starts a fresh editing session.

**Trigger:** User selects **File > New**.

**Preconditions:** None; or there is an existing project with potentially unsaved changes.

**Flow:**

1. The application checks whether the current project has unsaved changes (`_project_modified`). If dirty, the user is prompted to save.
2. On dismissal of the save prompt or after saving, a new `Project` is created with an empty `CsvConfig` derived from the current app config defaults.
3. The in-memory `CsvDocument` is reset to empty headers and rows.
4. The project path, external CSV path, and all filters are cleared.
5. The UI is refreshed: prompt controls, table view, and preview selectors are reset.

**Postconditions:** A clean slate with no rows, no prompts, and no saved project file.

## Use Case 3: Open an Existing Project

**Actor:** User

**Description:** The user loads a previously saved project along with its CSV data and prompt definitions.

**Trigger:** User selects **File > Open**.

**Preconditions:** A project file (`*.project.json`) exists on disk.

**Flow:**

1. The application checks for unsaved changes in the current session and prompts the user to save if dirty.
2. A file dialog opens, pre-focused on the directory of the previously opened project.
3. The user selects a `.project.json` file.
4. The `ProjectRepository` loads the project definition, including all `ProjectPrompt` objects.
5. For each prompt with a `prompt_file` sidecar, the prompt text is read from the sibling `.prompt.txt` file.
6. The repository resolves the sibling CSV path (e.g., `catalog.project.json` maps to `catalog.csv`). If the sibling CSV exists, it is loaded using the project's `CsvConfig`. Otherwise, an empty `CsvDocument` is constructed from the project's field keys and prompt output fields.
7. The current project, document, and paths are set. Filters are cleared.
8. Prompt controls, table view, and preview selectors are refreshed.

**Postconditions:** The project prompts, CSV data, and field metadata are all loaded and visible in the UI.

## Use Case 4: Save the Current Project

**Actor:** User

**Description:** The user persists the current project definition and the working CSV data to disk.

**Trigger:** User selects **File > Save** or **File > Save As**.

**Preconditions:** A project is open (new or loaded).

**Flow:**

1. For **Save As**, a file dialog prompts for a destination path. The path is normalized to end in `.project.json`.
2. The `ProjectRepository.save()` method writes each prompt's text to a sidecar `.prompt.txt` file in the same directory.
3. The project metadata (prompts, enabled states, prompt-to-output-column mapping, CSV config, field labels/visibility) is written to `*.project.json`.
4. The working `CsvDocument` is written to the sibling `*.csv` file using the project's `CsvConfig`.
5. The `project_path` is updated, and the dirty flag is cleared.

**Postconditions:** The `*.project.json`, sibling `*.csv`, and all `.prompt.txt` sidecar files exist on disk with the latest state.

## Use Case 5: Import a CSV File

**Actor:** User

**Description:** The user loads an arbitrary CSV file into the current session without creating a project association.

**Trigger:** User selects **CSV > Import**.

**Preconditions:** A project session is active (may be empty or contain existing data).

**Flow:**

1. A file dialog opens. The user selects a `.csv` file.
2. The `CsvRepository.load()` method reads the file using the current `CsvConfig` (encoding, delimiter, quote char).
3. The `CsvDocument` is replaced with the imported headers and rows. The `source_path` and detected `dialect` are recorded.
4. The table view, preview selectors, and prompt controls are refreshed to match the new columns.
5. The dirty flag is set because the imported data is not yet part of a saved project.
6. `current_external_csv_path` is updated to the imported file's path.

**Postconditions:** The table displays the imported CSV data. The imported CSV is not yet tied to the project's sibling file.

## Use Case 6: Export the CSV

**Actor:** User

**Description:** The user writes the current `CsvDocument` (including any generated columns) to a CSV file, choosing whether to export all rows or only visible (unfiltered) rows.

**Trigger:** User clicks the **Export** button in the CSV Data panel or selects **CSV > Export** from the menu bar.

**Preconditions:** A `CsvDocument` with headers and rows is loaded.

**Flow:**

1. The application determines the initial target path: if the project has a saved `export_path` in its CSV config, that value is used; otherwise the target path defaults to the project's sibling CSV file (derived from the `.project.json` path). If no project is loaded (standalone import), the field starts empty.
2. An `ExportDialog` opens with the following controls:
   - A **target path** text field pre-populated with the resolved target path from step 1.
   - A **Browse** button next to the target path field that opens a file save dialog to set the destination path.
   - An **"Export only visible rows"** checkbox. The default state is determined by: first check the `export_only_visible` setting from the project CSV config; if not set, fall back to checking whether active filters exist (i.e., `filter_patterns` is non-empty).
   - An **Export** button and a **Cancel** button.
3. The user may adjust the target path by typing or clicking **Browse**.
4. The user checks or unchecks the visibility option.
5. The user clicks **Export**:
   5a. If the target path is empty, the export is aborted and a warning is shown; the dialog remains open.
   5b. If the target file already exists on disk, an overwrite confirmation dialog is shown with a message indicating the file will be replaced.
      - If the user confirms overwrite, the export proceeds.
      - If the user declines, the overwrite dialog closes and the user returns to the export dialog.
   5c. The appropriate subset of rows is collected:
      - If **Export only visible rows** is checked, the application iterates over the proxy model's visible rows, mapping each back to its source row index via `proxy_model.mapToSource()`, and builds a `CsvDocument` containing only those rows.
      - If the checkbox is unchecked, the full `CsvDocument` is used.
   5d. If no visible rows exist and the checkbox is checked, a warning dialog is shown and the export is aborted; the export dialog remains open.
   5e. The `CsvRepository.save()` method writes the (possibly filtered) `CsvDocument` to the target path using the project's `CsvConfig`.
   5f. The `export_path` is updated in the project's CSV config to the target path, and the dirty flag is set so the change is persisted on next project save.
   5g. The dialog closes.
6. The status bar shows confirmation of the export location and the number of rows exported.

**Postconditions:** The CSV file exists on disk with the selected rows from the working document.

**Error conditions:**
- Empty target path: export is aborted, dialog remains open, a warning is shown.
- All rows filtered out and "only visible" is checked: export is aborted, dialog remains open, a warning is shown.
- Write failure (disk full, permissions, etc.): a critical error dialog is shown and the export is aborted.

**Invariants:**
- The exported CSV always includes all column headers from the original document, even if some columns are hidden in the UI (column visibility does not affect export).
- The checkbox state and target path are independent — changing one does not reset the other.
- The export dialog remains open on any error or abort, allowing the user to correct the issue.
- Exporting visible rows creates a temporary in-memory `CsvDocument` and never modifies `self.document`.
- The `export_path` is stored in the project's CSV config and persists across sessions. On a standalone (non-project) CSV import, `export_path` is not persisted to disk but `current_external_csv_path` is updated in memory.
- The initial target path for export is always the input CSV path; the user must explicitly change it via typing or Browse.

## Use Case 7: Add a Prompt

**Actor:** User

**Description:** The user defines a new processing target: an output column and a prompt template that generates HTML for it.

**Trigger:** User clicks the **Add** button in the Prompts panel.

**Preconditions:** None.

**Flow:**

1. An input dialog prompts the user for a CSV output field name (e.g., `seo_description`).
2. The application checks for an existing prompt with the same output field. If one exists, it selects that prompt in the dropdown and notifies the user.
3. If the field is new, a `ProjectPrompt` is appended with the output field and empty prompt text.
4. The output column is ensured in the `CsvDocument` via `_ensure_column()` — added to headers if missing, and initialized as empty string in all rows.
5. A `FieldConfig` is created for the column with `show=True` and `label` matching the field name.
6. The prompt selector dropdown, table view, and preview selectors are refreshed. The dirty flag is set.

**Postconditions:** A new prompt appears in the dropdown with an empty template. Its output column exists in the CSV document.

## Use Case 8: Delete a Prompt

**Actor:** User

**Description:** The user removes a prompt from the project.

**Trigger:** User selects a prompt in the dropdown and clicks **Delete**.

**Preconditions:** At least one prompt exists.

**Flow:**

1. A confirmation dialog asks whether to delete the prompt for the selected output field.
2. On confirmation, the `ProjectPrompt` is removed from the project's prompt list.
3. The prompt controls, preview selectors, and interactive state are refreshed. The dirty flag is set.

**Postconditions:** The prompt is removed. Its output column remains in the CSV document (disabling a prompt does not delete its column either).

## Use Case 9: Enable / Disable a Prompt

**Actor:** User

**Description:** The user controls whether a prompt participates in batch processing.

**Trigger:** User clicks the **Enabled** toggle button in the Prompts panel.

**Preconditions:** A prompt is selected.

**Flow:**

1. The button's check state is flipped. The prompt's `enabled` attribute is updated to match.
2. The button text reflects the new state ("Enabled" or "Disabled").
3. The interactive state of the Process button is updated — it is only enabled when at least one prompt is enabled.
4. The dirty flag is set if the state changed.

**Postconditions:** Enabled prompts are processed during batch runs; disabled prompts are skipped.

## Use Case 10: Edit a Prompt Template

**Actor:** User

**Description:** The user writes or modifies the prompt template text for the selected output column.

**Trigger:** User types in the prompt editor text area in the Prompts panel.

**Preconditions:** A prompt is selected.

**Flow:**

1. Template text uses `{{column_name}}` placeholders that are substituted from CSV row data at processing time.
2. On every change, the `ProjectPrompt.prompt` field is updated. The dirty flag is set.
3. The template is validated (at process time) against the current document headers. Unknown placeholders cause an error dialog.

**Postconditions:** The prompt template text is updated in the project definition and will be persisted on next save.

## Use Case 11: Preview a Single Row

**Actor:** User

**Description:** The user generates an LLM response for one row and one prompt to preview the output.

**Trigger:** User selects a row in the table, selects a prompt, and clicks **Preview** (or selects **Process > Current** / presses Ctrl+Enter).

**Preconditions:** At least one row is loaded. One prompt is selected and valid. The row's data satisfies all template placeholders.

**Flow:**

1. Validation runs: the document has rows, the original description column exists, and the prompt template references only known headers.
2. A `GenerationWorker` is created on a `QThread` with the selected row and the single prompt.
3. An `ActivityDialog` opens showing the provider, model, generation parameters, input/output character counts, and a progress indicator.
4. The worker streams chunks from the provider back to the UI via signals. Each chunk is appended to the cell in the table model.
5. The description preview panel on the right updates live with the generated HTML.
6. On completion, cancellation, or failure, the activity dialog is closed and the status bar shows the result.

**Postconditions:** The selected row's output column contains the generated HTML fragment.

## Use Case 12: Process All CSV Rows

**Actor:** User

**Description:** The user triggers batch generation across all rows and all enabled prompts.

**Trigger:** User clicks **Process** or selects **Process > All CSV Rows** (Ctrl+P).

**Preconditions:** At least one prompt is enabled. Rows are loaded. Template validation passes.

**Flow:**

1. If the row count exceeds 10, a confirmation dialog warns the user that the run may take a long time.
2. All rows (regardless of table filters) are collected as row specs.
3. All enabled prompts are collected.
4. An activity dialog opens. A worker is created on a background thread.
5. For each prompt, the worker iterates over all rows, streaming chunks back to the UI. Each generated row updates the table model and the preview panel if the row is the currently selected one.
6. The user may cancel at any time via the Cancel button in the activity dialog.
7. On completion, the dirty flag is set for each row whose output changed.

**Postconditions:** All enabled prompts have generated HTML in their output columns for every row in the CSV.

## Use Case 13: Process Visible Rows

**Actor:** User

**Description:** The user triggers batch generation only for rows that are currently visible (not filtered out).

**Trigger:** User clicks the dropdown arrow on the **Process** button and selects **Visible Rows** (or selects **Process > Visible Rows**).

**Preconditions:** At least one prompt is enabled. Rows are loaded. Filters may be active.

**Flow:**

1. The application collects row specs by iterating over the proxy model's visible rows, mapping each back to its source row index.
2. The same batch processing flow as Use Case 12 is followed, limited to the visible rows.

**Postconditions:** Only visible (unfiltered) rows are processed for enabled prompts.

## Use Case 14: Filter the Table

**Actor:** User

**Description:** The user restricts the rows displayed in the table by applying wildcard text filters per column.

**Trigger:** User clicks the **Filter** button.

**Preconditions:** A CSV document with headers is loaded.

**Flow:**

1. A `FilterDialog` opens listing all visible columns with text inputs and wildcard instructions.
2. Current filter values are pre-populated. The user can add, edit, or clear filters. "Clear All" resets every field.
3. On confirmation, the filter patterns are stored in `MainWindow.filter_patterns`.
4. Each pattern is applied to the `WildcardFilterProxyModel` as a column-specific `fnmatch` pattern (case-insensitive).
5. The table view re-renders to show only matching rows. The Filter button text updates to show the active filter count.

**Postconditions:** The table displays only rows matching all active filter patterns. Batch processing is scoped to visible rows.

## Use Case 15: Edit a Cell Inline as HTML

**Actor:** User

**Description:** The user manually edits the HTML content of a selected cell in a preview field.

**Trigger:** User selects a row and a field in the left or right preview combo box, then clicks the corresponding **Edit** button (or uses **Edit > Original** / **Edit > Result** menu actions with Ctrl+O / Ctrl+R).

**Preconditions:** A row is selected. A field is selected in the preview selector.

**Flow:**

1. An `HtmlEditorDialog` opens with the current cell content and a syntax highlighter for HTML tags, attributes, and strings.
2. The user edits the text and confirms.
3. The `CsvDocument` row is updated with the new value. The table model and preview panel are refreshed.
4. The dirty flag is set if the value changed.

**Postconditions:** The cell value is updated to the user-edited HTML text.

## Use Case 16: Cancel a Long-Running Generation Run

**Actor:** User

**Description:** The user aborts an ongoing batch or preview generation.

**Trigger:** User clicks **Cancel** in the activity dialog, presses Escape, or clicks the window close button on the activity dialog.

**Preconditions:** A generation worker is running on a background thread.

**Flow:**

1. The activity dialog emits a `cancel_requested` signal.
2. `MainWindow._cancel_processing()` sets `_cancel_requested = True`, closes the activity dialog, sets `_busy = False` to re-enable non-processing controls, and calls `worker.cancel()`.
3. `GenerationWorker.cancel()` sets a `threading.Event` and calls `provider.cancel()`, which forcefully closes the underlying `httpx.Client`, unblocking any pending HTTP stream read.
4. The provider catches the resulting `httpx.HTTPError` and raises `GenerationCancelled` because the cancel flag is set.
5. The worker catches `GenerationCancelled` and emits the `cancelled` signal. The thread finishes, `_clear_worker_state()` is called, and processing controls are re-enabled.

**Postconditions:** The generation stops. Partial results for completed rows are retained. The UI is fully interactive.

## Use Case 17: View Generation Activity

**Actor:** User

**Description:** During a generation run, the user monitors progress in real time.

**Trigger:** Automatic when a preview or batch process starts.

**Preconditions:** A generation is in progress.

**Flow:**

1. The `ActivityDialog` displays:
   - A title and status label (e.g., "Processing 'seo_description' for row 5...").
   - An elapsed-time timer.
   - A record progress bar showing completed / total prompt runs.
   - The run configuration: provider name, model name, temperature, top-p, max output tokens.
   - Input stats: character count and estimated token count for the first prompt.
   - Output stats: character count and estimated token count streamed so far.
   - A "Close on finish" checkbox (default for single-row previews).
   - A Cancel button.
2. The dialog updates incrementally as chunks arrive and rows complete.
3. On finish, the dialog shows a status update and either closes automatically (if close-on-finish and single preview) or waits for the user to close it.

**Postconditions:** The user has real-time visibility into the generation process.

## Use Case 18: Preview and Compare Descriptions

**Actor:** User

**Description:** The user views side-by-side HTML previews of the original description and the generated result for the currently selected row.

**Trigger:** Automatic on row selection change or generation chunk arrival.

**Preconditions:** A row is selected. Left and right preview field combos are populated.

**Flow:**

1. The user selects fields in the left (original) and right (result) combo boxes.
2. The description panel renders the HTML of each field using `HtmlPreview`, which falls back to `QTextBrowser` when Qt WebEngine is disabled.
3. Stats below each preview show section count, paragraph count, word count, and character count.
4. When a generation is in progress, the right preview updates live as chunks stream in.

**Postconditions:** The user sees a rendered comparison of source and generated HTML descriptions.

## Use Case 19: Manage the Project File

**Actor:** User

**Description:** The user works with the project's on-disk representation, which consists of a `.project.json` manifest, a sibling `.csv` data file, and per-prompt `.prompt.txt` sidecar files.

**Trigger:** Saving or opening a project.

**Preconditions:** The project has prompts and/or CSV data.

**Flow:**

1. **On save:** Each prompt's text is written to `{output_field_sanitized}.prompt.txt` in the project directory. The project manifest is written to `*.project.json`. The sibling CSV is written to `*.csv`.
2. **On load:** Prompts with `prompt_file` references have their text read from sidecars. The sibling CSV is loaded if present.
3. Column naming: prompt output fields are sanitized to alphanumeric, dot, underscore, and hyphen characters, replacing all others with underscores.

**Postconditions:** The project's on-disk layout is consistent and reconstructible.

## Use Case 20: Exit the Application

**Actor:** User

**Description:** The user closes the application.

**Trigger:** User selects **File > Exit**, closes the main window, or the OS sends a shutdown signal.

**Preconditions:** The main window is open.

**Flow:**

1. If there is an active generation worker, the window close is blocked until the worker thread finishes or is cancelled.
2. The `ConfigStore` persists the current app config to disk.
3. The application quits.

**Postconditions:** The application process terminates. Configuration is saved.

## Architecture Summary

### Components

| Component | Module | Responsibility |
|---|---|---|
| `MainWindow` | `main_window.py` | UI orchestration, menu actions, CSV/project workflows, previews, batch processing control |
| `ConfigStore` | `config.py` | Persistent app-level JSON configuration (provider, generation, CSV settings) |
| `Project` | `project.py` | In-memory project definition: prompts + CSV config |
| `ProjectRepository` | `project.py` | Read/write `.project.json` and `.prompt.txt` sidecars |
| `CsvDocument` | `csv_repository.py` | Live row data with headers, dialect, source path |
| `CsvRepository` | `csv_repository.py` | Read/write arbitrary CSV files using `CsvConfig` |
| `GenerationService` | `generation.py` | Prompt template rendering and row-level generation orchestration |
| `ProviderClient` (Ollama / OpenAI) | `providers.py` | Streaming LLM generation with cancellation support |
| `GenerationWorker` | `worker.py` | Qt-background-thread worker that orchestrates multi-prompt, multi-row generation |
| `ActivityDialog` | `dialogs.py` | Progress, stats, and cancellation UI during generation |
| `SettingsDialog` | `dialogs.py` | Provider, generation, and CSV configuration UI |
| `FilterDialog` | `dialogs.py` | Per-column wildcard text filtering UI |
| `ExportDialog` | `dialogs.py` | Target path selection, visibility checkbox, and overwrite confirmation for CSV export |
| `HtmlEditorDialog` | `dialogs.py` | Manual HTML cell editing with syntax highlighting |
| `WildcardFilterProxyModel` | `filter_proxy.py` | Qt proxy model for case-insensitive fnmatch filtering |
| `CsvTableModel` | `table_model.py` | Qt table model backing the CSV data grid |
| `HtmlPreview` | `preview.py` | HTML rendering widget with content statistics |
| `PromptRenderer` | `prompt_renderer.py` | `{{placeholder}}` extraction, validation, and template rendering |
| `CollapsiblePanel` | `collapsible_panel.py` | Expandable/collapsible UI section panels |

### Key Invariants

- A prompt's identity is its `output_field` name. Duplicate prompts for the same field are rejected.
- Prompt output columns must exist in the `CsvDocument` at all times. Adding a prompt materializes the column.
- The sibling CSV file (`*.csv`) and the `.project.json` form a single project unit. They are saved and loaded together.
- Filtering affects the table view display and the scope of "Process Visible Rows". It does not modify or remove data.
- The `original_description` column in `CsvConfig` defines which CSV column feeds into prompt templates as source data.
- Generation parameters (temperature, top_p, max_output_tokens) apply to all providers and are shared across prompts in a single run.
- The dirty flag (`_project_modified`) tracks unsaved changes and triggers save prompts on project switches.

### Data Flow

```
User imports CSV
  → CsvRepository.load() → CsvDocument (headers + rows)
  → CsvTableModel.set_document() → Table view renders

User adds prompt
  → Project.prompts.append() → CsvRepository.ensure_column()
  → FieldConfig created → Table columns expanded

User previews / processes
  → GenerationService.prepare_prompt() → PromptRenderer.render()
  → ProviderClient.generate() → Streaming chunks
  → GenerationWorker.row_generated → TableModel.set_cell()
  → HtmlPreview.set_html() → Rendered output

User saves project
  → ProjectRepository.save() → *.project.json + *.prompt.txt sidecars
  → CsvRepository.save() → *.csv sibling
```
