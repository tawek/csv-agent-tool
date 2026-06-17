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
6. The user configures CSV I/O: delimiter (`;` by default), quote char, encoding, newline character, whether to write headers, and the default state of the "export only visible rows" checkbox (a boolean option). When a saved app or project CSV config omits either `delimiter` or `export_only_visible`, the application falls back to the same defaults used for a fresh `CsvConfig` (`;` and `True`, respectively).
7. The user manages per-column visibility, display labels, whitespace-stripping flags, and CSV export column order through the editable fields configuration in the **CSV** tab.
8. The user may reset the fields configuration to match the currently loaded CSV headers. Resetting restores the current document header order as the export column order and recreates field entries for all current headers.
9. The user confirms or cancels. On confirm, the provider config and generation config are saved to the persistent `ConfigStore` (JSON on disk). The project-scoped `CsvConfig` is applied to the working document and table model, including the configured export column order.

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
4. The project path, external CSV path, project-scoped knowledge-base directory, and all filters are cleared.
5. The UI is refreshed: prompt controls, the reusable prompt editor, table view, preview selectors, and knowledge-base management state are reset.

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
4. The `ProjectRepository` loads the project definition, including all `ProjectPrompt` objects and the project's configured knowledge-base directory.
5. For each prompt with a `prompt_file` sidecar, the prompt text is read from the sibling `.prompt.txt` file.
6. The repository resolves the sibling CSV path (e.g., `catalog.project.json` maps to `catalog.csv`). If the sibling CSV exists, it is loaded using the project's `CsvConfig`. Otherwise, an empty `CsvDocument` is constructed from the project's field keys and prompt output fields.
7. The current project, document, and paths are set. Any configured knowledge-base directory becomes the active project-scoped knowledge-base root. Filters are cleared.
8. Prompt controls, the reusable prompt editor, table view, preview selectors, and knowledge-base management state are refreshed.

**Postconditions:** The project prompts, CSV data, and field metadata are all loaded and visible in the UI.

## Use Case 4: Save the Current Project

**Actor:** User

**Description:** The user persists the current project definition and the working CSV data to disk.

**Trigger:** User selects **File > Save** or **File > Save As**.

**Preconditions:** A project is open (new or loaded).

**Flow:**

1. For **Save As**, a file dialog prompts for a destination path. The path is normalized to end in `.project.json`.
2. The `ProjectRepository.save()` method writes each prompt's text to a sidecar `.prompt.txt` file in the same directory.
3. The project metadata (prompts, enabled states, prompt-to-output-column mapping, project-scoped knowledge-base directory, CSV config, and field metadata including labels, visibility, whitespace-stripping flags, and export column order) is written to `*.project.json`.
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
   - An **"Export only visible rows"** checkbox. The checkbox state reflects the effective `export_only_visible` setting from the project CSV config. If that setting is absent in persisted config data, the effective default is `True`. If no filters are active (i.e., `filter_patterns` is empty), the checkbox is grayed out and unchecked.
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
   5e. Before writing, the application derives the export header order from the project's current CSV field configuration.
      - The configured order is normalized against the current `CsvDocument` headers before export.
      - Duplicate configured column names are collapsed to their first occurrence.
      - Configured column names that are no longer present in the current document are ignored.
      - Any current document headers not named by the normalized configured order are appended in their current document-header order.
      - Export still includes every column present in the current `CsvDocument` exactly once; hidden columns are not omitted by this feature.
      - If the field configuration has been reset from the current CSV, the export order matches the current document header order.
   5f. The `CsvRepository.save()` method writes the (possibly filtered) `CsvDocument` to the target path using the project's `CsvConfig` and the derived export column order.
   5g. The `export_path` is updated in the project's CSV config to the target path, and the dirty flag is set so the change is persisted on next project save.
   5h. The dialog closes.
6. The status bar shows confirmation of the export location and the number of rows exported.

**Postconditions:** The CSV file exists on disk with the selected rows from the working document.

**Error conditions:**
- Empty target path: export is aborted, dialog remains open, a warning is shown.
- All rows filtered out and "only visible" is checked: export is aborted, dialog remains open, a warning is shown.
- Write failure (disk full, permissions, etc.): a critical error dialog is shown and the export is aborted.

**Invariants:**
- The exported CSV always includes all column headers from the current document exactly once, even if some columns are hidden in the UI (column visibility does not affect export).
- When an export column order is configured, the exported header row and each exported data row follow the normalized configured order: current columns only, no duplicates, with any otherwise-unmentioned current columns appended in current document order.
- Resetting the fields configuration from the current CSV restores the export column order to the current document header order.
- The checkbox state and target path are independent — changing one does not reset the other.
- The export dialog remains open on any error or abort, allowing the user to correct the issue.
- Exporting visible rows creates a temporary in-memory `CsvDocument` and never modifies `self.document`.
- The `export_path` is stored in the project's CSV config and persists across sessions. The export column order is also part of the project's CSV field configuration and persists across project save/load cycles. On a standalone (non-project) CSV import, `export_path` is not persisted to disk but `current_external_csv_path` is updated in memory.
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

**Trigger:** User types in the prompt editor in the Prompts panel.

**Preconditions:** A prompt is selected.

**Flow:**

1. Template text uses `{{column_name}}` placeholders that are substituted from CSV row data at processing time.
2. The prompt editor is a reusable embedded markdown-capable text editor. It supports plain-text prompt editing in the Prompts panel and provides markdown syntax highlighting while the user edits.
3. On every change, the `ProjectPrompt.prompt` field is updated. The dirty flag is set.
4. Template text may use two placeholder forms:
   - `{{column_name}}` references a CSV column or another prompt output field.
   - `{{@relative/path.ext}}` references a knowledge-base file within the project's configured knowledge-base directory.
5. Knowledge-base references are project-scoped:
   - The knowledge-base directory is configured per project.
   - Supported referenced file types are `.md`, `.markdown`, and `.csv`.
   - Referenced paths are interpreted relative to the configured knowledge-base directory.
   - Referenced paths must not escape the configured knowledge-base directory.
   - Included file content is inserted verbatim into the rendered prompt and is not recursively rendered for additional placeholders.
6. The template is validated before preview or batch processing starts:
   - Unknown `{{column_name}}` placeholders cause an error dialog.
   - Every `{{@...}}` reference must resolve to an existing supported file within the configured knowledge-base directory.
   - Missing, unsupported, unreadable, or escaping knowledge-base references cause an error dialog and block preview and processing.

**Postconditions:** The prompt template text is updated in the project definition and will be persisted on next save.

## Use Case 25: Panel Layout Management

**Actor:** User

**Description:** The user controls the layout of the three panes (CSV Data, Prompts, Description) through two header buttons on each pane: `+` to grow the pane and `-` to shrink it. Each pane can be in one of four layout states: maximized, normal, minimized, or temporary minimized.

**Preconditions:** The application window is open and all three panes are present.

### Panel States

- **Maximized:** The pane occupies the available content area. A maximized pane cannot grow further.
- **Normal:** The pane is visible at its regular shared size.
- **Minimized:** The pane body is hidden and only the header row remains visible. A minimized pane cannot shrink further.
- **Temporary minimized:** The pane is minimized automatically because another pane is maximized. It is not user-reachable via `-` and is restored to normal when the maximized pane returns to normal. It looks the same as minimized while active.

### Header Controls

Each pane header contains exactly two buttons on the left:
- `+` grows the pane.
- `-` shrinks the pane.

Button enabled and disabled state communicates whether the pane can grow or shrink further:
- `+` is disabled only when the pane is maximized.
- `-` is disabled only when the pane is minimized.

### Trigger

User clicks the `+` or `-` button in any pane header.

### Flow

1. Each pane header always shows exactly two buttons on the left: `+` and `-`.
2. Clicking `+` grows the targeted pane by one step:
   - minimized or temporary minimized → normal
   - normal → maximized
   - maximized → no change because `+` is disabled
3. Clicking `-` shrinks the targeted pane by one step:
   - maximized → normal
   - normal → minimized
   - minimized → no change because `-` is disabled
4. Temporary minimized is never entered by clicking `-` directly.
5. When a pane becomes maximized, every other pane that is currently normal becomes temporary minimized.
6. When a pane becomes maximized, every other pane that is already minimized remains minimized.
7. When a maximized pane is shrunk back to normal, all panes that were temporary minimized because of that maximized state are restored to normal.
8. After each state change, all pane buttons refresh their enabled or disabled state to reflect whether each pane can grow or shrink further.

**Postconditions:** The window layout reflects the resulting pane states (maximized, normal, minimized, or temporary minimized). No data or functionality is affected — this is purely a UI layout change.

**Error conditions:** No error conditions.

**Invariants:**
- Panel layout controls are purely cosmetic — they do not affect data, processing, or any other application functionality.
- Each pane has exactly two header buttons on the left: `+` and `-`.
- Button meaning is fixed by symbol: `+` always grows and `-` always shrinks.
- Enabled and disabled button state, rather than changing symbols, communicates whether the pane can grow or shrink further.
- Only one pane can be maximized at a time.
- Temporary minimized is visually indistinguishable from minimized but remains a distinct internal state because it is restorable to normal when the active maximized pane is de-maximized.
- Maximizing one pane temporarily minimizes only other panes that are currently normal; explicitly minimized panes remain minimized.

## Use Case 11: Preview a Single Row

**Actor:** User

**Description:** The user generates an LLM response for one row and one prompt to preview the output.

**Trigger:** User selects a row in the table, selects a prompt, and clicks **Preview** (or selects **Process > Current** / presses Ctrl+Enter).

**Preconditions:** At least one row is loaded. One prompt is selected and valid. The row's data satisfies all template placeholders. Any referenced knowledge-base files resolve successfully within the project's configured knowledge-base directory.

**Flow:**

1. Validation runs before the worker is created:
   - The document has rows.
   - The prompt template references only known headers or prompt output fields where allowed.
   - Every `{{@...}}` reference resolves to an existing supported file under the project's configured knowledge-base directory.
   - If the prompt contains any missing, unsupported, unreadable, or escaping knowledge-base reference, preview is aborted and an error dialog is shown.
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

**Preconditions:** At least one prompt is enabled. Rows are loaded. Template validation passes, including validation of all referenced knowledge-base files.

**Flow:**

1. Before any worker is created, validation runs for all enabled prompts:
   - Column and prompt-output placeholders must be valid.
   - Every `{{@...}}` reference must resolve to an existing supported file under the project's configured knowledge-base directory.
   - Missing, unsupported, unreadable, or escaping knowledge-base references abort processing and are reported before any row is processed.
2. If the row count exceeds 10, a confirmation dialog warns the user that the run may take a long time.
3. All rows (regardless of table filters) are collected as row specs.
4. All enabled prompts are collected.
5. An activity dialog opens. A worker is created on a background thread.
6. For each prompt, the worker iterates over all rows, streaming chunks back to the UI. Each generated row updates the table model and the preview panel if the row is the currently selected one.
7. The user may cancel at any time via the Cancel button in the activity dialog.
8. On completion, the dirty flag is set for each row whose output changed.

**Postconditions:** All enabled prompts have generated HTML in their output columns for every row in the CSV.

## Use Case 13: Process Visible Rows

**Actor:** User

**Description:** The user triggers batch generation only for rows that are currently visible (not filtered out).

**Trigger:** User clicks the dropdown arrow on the **Process** button and selects **Visible Rows** (or selects **Process > Visible Rows**).

**Preconditions:** At least one prompt is enabled. Rows are loaded. Filters may be active. Template validation, including validation of all referenced knowledge-base files, passes.

**Flow:**

1. The application collects row specs by iterating over the proxy model's visible rows, mapping each back to its source row index.
2. The same validation and batch processing flow as Use Case 12 is followed, limited to the visible rows.

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

**Description:** The user views side-by-side HTML previews of any source field and the generated result for the currently selected row.

**Trigger:** Automatic on row selection change or generation chunk arrival.

**Preconditions:** A row is selected. Left and right preview field combos are populated.

**Flow:**

1. When the left preview field selector is auto-populated (e.g., on row selection or prompt change), the application determines which column to select as the "source" field:
   - If the prompt template references exactly one CSV column, that column is selected.
   - If the prompt template references multiple CSV columns, the application measures the content length (character count) of each referenced column across all rows in the document, selects the column with the highest total content length, and uses that as the default.
   - If no columns are referenced, the selector defaults to empty and the left preview pane shows nothing.
2. The user selects fields in the left (source) and right (result) combo boxes.
3. The description panel renders the HTML of each field using `HtmlPreview`, which uses `QTextBrowser` by default (Qt WebEngine is disabled at startup for compatibility with remote X11 and headless environments).
4. Stats below each preview show section count, paragraph count, word count, and character count.
5. When a generation is in progress, the right preview updates live as chunks stream in.

**Postconditions:** The user sees a rendered comparison of source and generated HTML descriptions.

## Use Case 19: Manage the Project File

**Actor:** User

**Description:** The user works with the project's on-disk representation, which consists of a `.project.json` manifest, a sibling `.csv` data file, per-prompt `.prompt.txt` sidecar files, and an optional project-scoped knowledge-base directory reference.

**Trigger:** Saving or opening a project.

**Preconditions:** The project has prompts and/or CSV data.

**Flow:**

1. **On save:** Each prompt's text is written to `{output_field_sanitized}.prompt.txt` in the project directory. The project manifest is written to `*.project.json`. The sibling CSV is written to `*.csv`.
2. **Knowledge-base directory persistence:**
   - A project may store a configured knowledge-base directory in its manifest.
   - When possible, the stored knowledge-base directory path is relative to the `.project.json` file location.
   - If a relative representation is not possible, an absolute path may be stored.
   - The knowledge-base directory setting is saved separately from the files inside that directory; saving the project persists the directory reference only.
3. **On load:** Prompts with `prompt_file` references have their text read from sidecars. The sibling CSV is loaded if present. If a knowledge-base directory is configured, it is resolved relative to the project file when stored as a relative path.
4. Column naming: prompt output fields are sanitized to alphanumeric, dot, underscore, and hyphen characters, replacing all others with underscores.

**Postconditions:** The project's on-disk layout is consistent and reconstructible, including its project-scoped knowledge-base directory setting.

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

## Use Case 21: Manage the Project Knowledge Base

**Actor:** User

**Description:** The user manages the current project's knowledge-base directory and browses its files in a dedicated management window.

**Trigger:** User selects the single **Knowledge Base** entry in the main application UI.

**Preconditions:** A project session is active.

**Flow:**

1. The main application UI exposes a single **Knowledge Base** entry for knowledge-base access; separate direct knowledge-base actions are not required in the menu structure.
2. Selecting that entry opens a separate knowledge-base management window for the current project.
3. The window shows the currently configured project-scoped knowledge-base directory, if any.
4. The user may set or change the knowledge-base directory by browsing for a folder.
5. The user may clear the configured knowledge-base directory.
6. The window provides a file and directory explorer rooted at the configured knowledge-base directory.
7. If no knowledge-base directory is configured, file-browsing and file-management actions that require a root directory are unavailable until the user sets one.
8. The user may ask the application to open the knowledge-base directory in the operating system's external file explorer.
9. The window provides a **Close** action so the user can exit the knowledge-base manager directly from that screen.
10. Changes to the configured knowledge-base directory are applied to the current project and are persisted on the next project save.

**Postconditions:** The project has either no knowledge-base directory or one active knowledge-base root that is available for prompt references and browsing.

**Error conditions:** Invalid, unreadable, or inaccessible directories are rejected and reported to the user.

## Use Case 22: Browse and Manage Knowledge-Base Files

**Actor:** User

**Description:** The user browses project knowledge-base files and performs the requested file-management actions from the knowledge-base management window.

**Trigger:** User selects items and actions in the knowledge-base explorer.

**Preconditions:** A project-scoped knowledge-base directory is configured and accessible.

**Flow:**

1. The explorer displays folders and files under the configured knowledge-base directory.
2. The user may navigate through subdirectories within that root.
3. For any file, the application always offers an external viewer or editor action that opens the selected file with the operating system's default associated application.
4. The user may copy a file within the knowledge-base root.
5. The user may rename a file within the knowledge-base root.
6. The application may also offer file deletion within the knowledge-base root.
7. If deletion is offered and the user invokes it, the application shows a confirmation dialog identifying the file to be removed before deletion completes.
8. After a successful copy, rename, or delete action, the explorer refreshes to show the current filesystem state.

**Postconditions:** The knowledge-base directory contents reflect any completed copy, rename, or delete action.

**Error conditions:** Failed filesystem operations, naming conflicts, or attempts to operate outside the configured knowledge-base root are rejected and reported to the user.

## Use Case 26: View or Edit a Knowledge-Base Markdown or Text File

**Actor:** User

**Description:** The user opens a knowledge-base markdown or text file in a modal embedded editor.

**Trigger:** User chooses a view or edit action for a supported knowledge-base text file from the knowledge-base explorer.

**Preconditions:** A project-scoped knowledge-base directory is configured, the selected file exists within that directory, and its type is `.md` or `.txt`.

**Flow:**

1. The application opens a modal embedded text editor dialog for the selected file.
2. The dialog exposes **Save** and **Cancel** buttons.
3. The current file contents are loaded into the editor.
4. Markdown files (`.md`) display markdown syntax highlighting in the embedded editor.
5. Plain-text files (`.txt`) display as editable text without requiring an external application.
6. The user edits the file and chooses one of the following outcomes:
   - **Save:** the file is written back to disk and the dialog closes.
   - **Cancel:** the dialog closes without saving changes.
7. The dialog also provides an action to open the same file in an external viewer or editor.
8. After saving, the knowledge-base explorer refreshes any visible metadata affected by the change.

**Postconditions:** The selected text file is either unchanged (cancel) or saved with the user's edits.

**Error conditions:** Unsupported file types for embedded text editing, unreadable files, or save failures are reported to the user.

## Use Case 27: View or Edit a Knowledge-Base CSV File

**Actor:** User

**Description:** The user opens a knowledge-base CSV file in a modal grid editor with simple spreadsheet behavior.

**Trigger:** User chooses a view or edit action for a CSV file from the knowledge-base explorer.

**Preconditions:** A project-scoped knowledge-base directory is configured and the selected CSV file exists within that directory.

**Flow:**

1. The application opens a modal CSV editor dialog for the selected file.
2. The dialog exposes **Save** and **Cancel** buttons.
3. Before showing the grid, the application heuristically detects the CSV settings needed to open the file.
4. The file contents are shown in a grid or table.
5. The user may edit existing text cells, enter text into empty cells, and clear or replace text cell values.
6. The dialog supports adding and removing rows.
7. The dialog supports adding and removing columns.
8. The dialog provides an action to open the same CSV file in an external viewer or editor.
9. The user chooses one of the following outcomes:
     - **Save:** the CSV file is written back to disk and the dialog closes.
     - **Cancel:** the dialog closes without saving changes.
10. After saving, the knowledge-base explorer refreshes any visible metadata affected by the change.

**Postconditions:** The selected CSV file is either unchanged (cancel) or saved with the user's grid edits.

**Error conditions:** CSV parsing failures, unsupported encodings, unreadable files, or save failures are reported to the user.

## Use Case 23: Strip Whitespace from HTML Columns on Export

**Actor:** User

**Description:** The user enables per-column whitespace normalization so that consecutive spaces and line breaks in HTML column values are collapsed to a single space during CSV export.

**Trigger:** User enables the "Strip whitespace on export" checkbox in the fields table within Settings, or the application strips whitespace when `strip_html_whitespace` is `True` for a column.

**Preconditions:** A `CsvDocument` with headers and rows is loaded. The field for the HTML column has `strip_html_whitespace=True` in its `FieldConfig`.

**Flow:**

1. The user opens **File > Settings** and navigates to the **CSV** tab.
2. The fields table displays four columns: **Header**, **Visible**, **Label**, and **Strip whitespace on export** (checkbox).
3. The user checks or unchecks the "Strip whitespace on export" checkbox for any column.
4. When the CSV is saved (via **Save**, **Save As**, or **Export**), the application iterates over each row.
5. For every column whose `FieldConfig.strip_html_whitespace` is `True`, the cell value is normalized: consecutive whitespace characters (spaces, tabs, newlines, carriage returns) are replaced with a single space, and leading/trailing whitespace is trimmed.
6. The normalized rows are written to the CSV file by `CsvRepository.save()`.

**Postconditions:** The exported CSV contains whitespace-normalized HTML for columns with the strip flag enabled, while the in-memory `CsvDocument` retains its original values.

**Error conditions:** No error conditions — if a cell is empty or contains no whitespace, normalization is a no-op.

**Invariants:**
- Whitespace stripping affects export/save only; the in-memory document is not modified.
- The checkbox is per-column and persists in the project file via `FieldConfig`.
- Normalization uses `re.sub(r'\s+', ' ', value).strip()` — all Unicode whitespace sequences collapse to a single space.

## Use Case 24: Prompt Dependency Ordering

**Actor:** User

**Description:** When processing multiple prompts, the application detects dependencies between them (where one prompt's template references another prompt's output column) and processes them in the correct order. Knowledge-base file references do not participate in prompt dependency ordering.

**Trigger:** Automatic when the user initiates batch processing (Process All, Process Visible Rows, or Preview).

**Preconditions:** At least one prompt is enabled. Prompts may reference each other's output columns via `{{output_field}}` placeholders.

**Flow:**

1. Before starting processing, the application builds a dependency graph among enabled prompts:
   - For each prompt, extract all placeholders from its template using `PromptRenderer.extract_placeholders()`.
   - If a placeholder matches the `output_field` of another enabled prompt, a dependency edge is created (this prompt depends on the referenced prompt).
   - `{{@...}}` knowledge-base references are excluded from the graph and never create dependency edges.
2. The application computes a topological ordering of the prompts based on the dependency graph:
   - Prompts with no dependencies are processed first.
   - A prompt is processed only after all its dependencies have been processed.
3. If a cycle is detected during ordering:
   - The application identifies all prompts participating in the cycle.
   - A critical error dialog is shown listing the cyclic prompts and their dependencies.
   - Processing is aborted; no rows are processed.
4. If a prompt references its own output field (e.g., `{{seo_description}}` in a prompt with `output_field="seo_description"`), this is treated as a self-cycle and reported accordingly.
5. On successful ordering, the prompts are re-ordered before being passed to the worker. The dependency information is not persisted — ordering is computed at processing time.

**Postconditions:** Prompts are processed in dependency order, ensuring that referenced output columns contain data from earlier prompts.

**Error conditions:**
- Cyclic dependencies: processing is aborted with an error dialog listing the cycle participants.
- A prompt references an output field that does not exist: the placeholder validation (Use Case 11) catches this and shows an error before ordering is attempted.

**Invariants:**
- Only enabled prompts participate in the dependency graph.
- The dependency ordering is ephemeral — it is computed fresh for each processing run and not persisted in the project file.
- A prompt is considered dependent on another prompt if its template contains a placeholder matching the other prompt's `output_field` name.
- Knowledge-base file references are project-scoped prompt inputs, not prompt dependencies.

## Architecture Summary

### Components

| Component | Module | Responsibility |
|---|---|---|
| `MainWindow` | `main_window.py` | UI orchestration, menu actions, CSV/project workflows, previews, batch processing control |
| `ConfigStore` | `config.py` | Persistent app-level JSON configuration (provider, generation, CSV settings) |
| `Project` | `project.py` | In-memory project definition: prompts + CSV config + optional knowledge-base directory |
| `ProjectRepository` | `project.py` | Read/write `.project.json`, `.prompt.txt` sidecars, and project-scoped knowledge-base directory metadata |
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
| Knowledge-base management window and embedded file editors | `main_window.py` / `dialogs.py` | Project-scoped knowledge-base directory selection, browsing, file operations, external open actions, and modal embedded editing for supported files |
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
- Prompt templates can reference any CSV column by name via `{{column_name}}` placeholders.
- Prompt templates can also reference project-scoped knowledge-base files via `{{@relative/path.ext}}`; only `.md`, `.markdown`, and `.csv` files are supported, paths are resolved relative to the configured knowledge-base directory, escaping that directory is forbidden, and included content is inserted verbatim without recursive rendering.
- The application provides a separate project-scoped knowledge-base management window for setting or clearing the knowledge-base directory, browsing files under that root, performing copy/rename actions within that root, optionally deleting files there with confirmation, opening files externally, and opening supported files in modal embedded editors.
- Embedded knowledge-base editors are modal dialogs with explicit Save and Cancel actions.
- The reusable embedded markdown-capable editor is used both for prompt editing in the main window and for embedded editing of markdown knowledge-base files.
- The default CSV delimiter is `;` (semicolon). New projects, fresh installs, and any persisted CSV config missing a delimiter value use this delimiter unless the user changes it in Settings.
- The default `export_only_visible` setting is `True`. New projects, fresh installs, and any persisted CSV config missing that value use `True` as the effective setting until the user changes it.
- Generation parameters (temperature, top_p, max_output_tokens) apply to all providers and are shared across prompts in a single run.
- The dirty flag (`_project_modified`) tracks unsaved changes and triggers save prompts on project switches.
- Each field in `FieldConfig` may have `strip_html_whitespace=True`, which normalizes consecutive whitespace in the cell value to a single space during CSV export.
- Prompt dependency ordering is computed at processing time: enabled prompts are topologically sorted by output-field dependencies, and cycles are detected before processing begins.
- Knowledge-base reference validation runs before preview or processing starts; missing, unsupported, unreadable, or escaping references block the run.
- The pane maximize toggle is purely cosmetic: it hides the other two panes, expands the selected pane, and restores previous panel states on unmaximize.

### Data Flow

```
User imports CSV
  → CsvRepository.load() → CsvDocument (headers + rows, dialect inferred or using configured `;` delimiter)
  → CsvTableModel.set_document() → Table view renders

User adds prompt
  → Project.prompts.append() → CsvRepository.ensure_column()
  → FieldConfig created → Table columns expanded

User previews / processes
  → Validate CSV placeholders + knowledge-base references (exist, supported type, within KB root)
  → Prompt dependency graph built and topologically sorted (or cycle detected)
  → GenerationService.prepare_prompt() → PromptRenderer.render()
  → ProviderClient.generate() → Streaming chunks
  → GenerationWorker.row_generated → TableModel.set_cell()
  → HtmlPreview.set_html() → Rendered output

User saves project
  → ProjectRepository.save() → *.project.json + *.prompt.txt sidecars
  → CsvRepository.save() → per-field whitespace normalization (if `strip_html_whitespace`), then writes *.csv sibling
```
