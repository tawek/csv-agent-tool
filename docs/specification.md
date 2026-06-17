# Functional Specification

## Overview

Product Description Tool is a desktop batch editor for rewriting product descriptions from CSV data using large-language-model (LLM) backends. Users load CSV files, define prompt templates that map CSV input columns to generated HTML output columns, preview results inline, and export the processed CSV.

The application runs on Python 3.14+ with PySide6, supports Ollama and OpenAI-compatible providers, and is distributed as a packaged desktop binary via PyInstaller. The packaged Windows distribution includes an `install.bat` helper that copies the built app into `C:\apps\product-description-tool` while showing visible progress or status so the install does not appear stalled during large file copies.

## Use Case 1: Configure the Application

**Actor:** User (first-time setup)

**Description:** The user configures the LLM provider, generation parameters, and project CSV export settings. CSV import settings are primarily established by import auto-detection rather than by making the user pre-configure them.

**Trigger:** User selects **File > Settings** (or clicks the Settings action).

**Preconditions:** The application has started with a default or previously saved `AppConfig`.

**Flow:**

1. A `SettingsDialog` opens with three tabs: **Provider**, **Generation**, and **Export CSV options**.
2. The user selects the active provider from the dropdown (`ollama` or `openai`).
3. For the active provider the user configures:
   - **Ollama:** Base URL, model name, and arbitrary options JSON.
   - **OpenAI-compatible:** Base URL, API key, model name, and arbitrary options JSON.
4. The user can refresh the model list from the active provider endpoint via a refresh button.
5. The user sets generation parameters: temperature (0.0-2.0), top-p (0.0-1.0), max output tokens (1-200000).
6. The settings UI labels this area as **Export CSV options** to make its scope explicit.
7. The user configures CSV export behavior there: delimiter (`;` by default), quote char, encoding, newline character, whether to write headers, and the default state of the "export only visible rows" checkbox (a boolean option). When a saved app or project CSV config omits either `delimiter` or `export_only_visible`, the application falls back to the same defaults used for a fresh `CsvConfig` (`;` and `True`, respectively).
8. The CSV settings shown in project settings are the project's export settings only. They control the explicit **Export CSV** feature and do not control how the project's working or sibling project CSV is saved or reopened.
9. Import heuristics are limited to low-level parsing characteristics (`encoding`, `delimiter`, `quotechar`, `newline`). They must not guess prompt mappings, source columns, output columns, field visibility, field labels, export order, or any other prompt/project semantics.
10. The user manages per-column visibility, display labels, whitespace-stripping flags, and CSV export column order through the editable fields configuration in the **CSV** tab.
11. The user may reset the fields configuration to match the currently loaded CSV headers. Resetting restores the current document header order as the export column order and recreates field entries for all current headers.
12. The user confirms or cancels. On confirm, the provider config and generation config are saved to the persistent `ConfigStore` (JSON on disk). The project-scoped export `CsvConfig` is applied to export-related behavior and table-model field presentation, including the configured export column order.

**Postconditions:** The updated configuration is persisted and immediately applied to the working session.

**Error conditions:** Invalid provider JSON, missing API keys, or unresolvable provider endpoints are reported to the user. CSV tabular field settings must contain single-character delimiters and quote chars.

## Use Case 2: Create a New Project

**Actor:** User

**Description:** The user starts a fresh editing session.

**Trigger:** User selects **File > New**.

**Preconditions:** None; or there is an existing project with potentially unsaved changes.

**Flow:**

1. The application checks whether the current project has unsaved changes (`_project_modified`). If dirty, the user is prompted to save.
2. On dismissal of the save prompt or after saving, a new `Project` is created with a CSV configuration baseline derived from the current app config defaults. Import settings are not yet established from file content, and export settings are not yet established unless the user explicitly configures them in project settings.
3. The in-memory `CsvDocument` is reset to empty headers and rows.
4. The project path, external CSV path, project-scoped knowledge-base directory, prompt-attachment metadata, and all filters are cleared.
5. The UI is refreshed: prompt controls, the reusable prompt editor, prompt-attachment management state, table view, preview selectors, and knowledge-base management state are reset.

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
4. The `ProjectRepository` loads the project definition, including all `ProjectPrompt` objects, each prompt's attachment metadata, and the project's configured knowledge-base directory.
5. For each prompt with a `prompt_file` sidecar, the prompt text is read from the sibling `.prompt.txt` file.
6. The repository resolves the sibling CSV path (e.g., `catalog.project.json` maps to `catalog.csv`). If the sibling CSV exists, it is loaded using the persisted low-level CSV settings from the project's import-derived working CSV contract (`encoding`, `delimiter`, `quotechar`, `newline`). Persisted export settings are not used as the reopen contract for the sibling project CSV, and heuristics are not the normal reopen path for that project-owned artifact.
   - Backward-compatibility fallback: if the raw persisted project payload uses the nested project CSV config shape but truly omits `csv.import_settings`, reopen may heuristically detect the sibling project CSV format and load with those detected low-level settings.
   - This heuristic path is fallback-only. It must not replace the normal persisted import-settings contract for current projects, and it must not be triggered merely because persisted import settings equal default values.
   - Legacy flat CSV config payloads continue to follow their existing load rules rather than this nested-shape missing-settings fallback.
   - After a successful fallback reopen, the next project save persists the detected import settings so later reopens return to the deterministic normal path.
   Otherwise, an empty `CsvDocument` is constructed from the project's field keys and prompt output fields.
7. The current project, document, and paths are set. Any configured knowledge-base directory becomes the active project-scoped knowledge-base root. Filters are cleared.
8. Prompt controls, the reusable prompt editor, prompt-attachment management state, table view, preview selectors, and knowledge-base management state are refreshed.

**Postconditions:** The project prompts, CSV data, and field metadata are all loaded and visible in the UI.

## Use Case 4: Save the Current Project

**Actor:** User

**Description:** The user persists the current project definition and the working CSV data to disk.

**Trigger:** User selects **File > Save** or **File > Save As**.

**Preconditions:** A project is open (new or loaded).

**Flow:**

1. For **Save As**, a file dialog prompts for a destination path. The path is normalized to end in `.project.json`.
2. The `ProjectRepository.save()` method writes each prompt's text to a sidecar `.prompt.txt` file in the same directory.
3. The project metadata (prompts, enabled states, prompt-to-output-column mapping, per-prompt attachment metadata, project-scoped knowledge-base directory, CSV import settings, CSV export settings, and field metadata including labels, visibility, whitespace-stripping flags, and export column order) is written to `*.project.json`.
4. The working `CsvDocument` is written to the sibling `*.csv` file using the project's persisted import-derived working CSV settings. Those persisted low-level settings remain the deterministic reopen contract for that sibling project CSV on later project open. If the current session was reopened through the backward-compatibility missing-`csv.import_settings` fallback, this save persists the detected import settings so future reopens no longer depend on heuristics.
5. The `project_path` is updated, and the dirty flag is cleared.

**Postconditions:** The `*.project.json`, sibling `*.csv`, and all `.prompt.txt` sidecar files exist on disk with the latest state.

## Use Case 5: Import a CSV File

**Actor:** User

**Description:** The user loads an arbitrary CSV file into the current session. The application auto-detects import parsing settings so the normal import path does not require the user to figure out the correct setup first.

**Trigger:** User selects **CSV > Import**.

**Preconditions:** A project session is active (may be empty or contain existing data).

**Flow:**

1. A file dialog opens. The user selects a `.csv` file.
2. Before reading rows, the application auto-detects effective CSV import parsing settings for `encoding`, `delimiter`, `quotechar`, and `newline` from the selected file. If a heuristic cannot determine a usable value, the application falls back to the application's CSV defaults for that attribute.
3. CSV import heuristics are limited to low-level parsing characteristics. They must not infer or modify prompt definitions, source-column semantics, output-column mappings, field labels, field visibility, or export order.
4. In the normal success path, the application imports immediately with the detected settings. The user is not required to review or confirm the detected import settings before the document is loaded.
5. The `CsvRepository.load()` method reads the file using the detected import settings.
6. The `CsvDocument` is replaced with the imported headers and rows. The `source_path` and detected `dialect` are recorded.
7. The detected import settings become the project's current working-CSV format contract for that imported document and persist on the next project save.
8. Those persisted import-derived settings are the contract later used to save and reopen the project's sibling working CSV.
9. For backward compatibility only, a project reopen that succeeds because the raw nested project payload truly lacked `csv.import_settings` may temporarily rely on heuristic sibling-CSV detection, but the next project save must persist the detected import settings so future reopens use the normal deterministic contract.
10. If the project does not yet have established export settings, the application initializes the project's export settings from the detected import settings immediately after the first successful import. After this first-import seeding step, import-derived working CSV settings and export settings are independent.
11. Once export settings exist, later imports must not silently overwrite them with newly detected import settings.
12. The table view, preview selectors, and prompt controls are refreshed to match the new columns.
13. The dirty flag is set because the imported data is not yet part of a saved project.
14. `current_external_csv_path` is updated to the imported file's path.

**Postconditions:** The table displays the imported CSV data. The imported CSV is not yet tied to the project's sibling file.

**Error conditions:**
- If the selected file cannot be parsed with the detected settings, the current document remains unchanged.
- If the application offers a retry or correction path after auto-detection fails, that recovery path may ask the user to review or edit import settings, but only as an exception path after the automatic import attempt did not succeed.

**Invariants:**
- Import auto-detection is the primary import path; the normal successful import flow does not require user confirmation of detected parsing settings.
- Import heuristics are restricted to CSV parsing characteristics and do not perform source-column auto-detection or other prompt/project inference.
- Import-derived working CSV settings and export settings are separate concepts and may differ for the same project.
- Persisted import-derived settings define how the application saves and reopens the saved sibling project CSV.
- The only allowed heuristic reopen path for the sibling project CSV is the backward-compatibility case where the raw nested project payload truly omitted `csv.import_settings`; after that path succeeds once, the next save persists detected import settings so later reopens are deterministic.
- Before the first successful import, export settings are not yet established for the project.
- The first successful import seeds initial export settings from the detected import settings exactly once unless the project already had export settings.
- Importing a CSV does not silently rewrite prompt definitions or column-level project metadata beyond normal synchronization with the newly loaded document headers.

## Use Case 6: Export the CSV

**Actor:** User

**Description:** The user writes the current `CsvDocument` (including any generated columns) to a CSV file, choosing whether to export all rows or only visible (unfiltered) rows. Export always uses the project's export settings rather than the most recent import heuristics, except that the first successful import may have seeded those export settings. Export settings belong only to this explicit export flow and do not control project save/reopen of the sibling working CSV or the backward-compatibility missing-import-settings fallback.

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
    5f. The `CsvRepository.save()` method writes the (possibly filtered) `CsvDocument` to the target path using the project's export `CsvConfig` and the derived export column order.
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
- Export uses project-configured export settings, not the current file's import heuristics, unless those export settings were established earlier by the first-import seeding rule.
- Project save/reopen of the sibling working CSV uses the persisted import-derived working CSV settings, not the export settings from this explicit export flow.
- Export settings are never used as evidence that `csv.import_settings` is present or absent for the backward-compatibility sibling-CSV reopen fallback.
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
3. Prompt attachments are managed separately from prompt text so the main prompt editor stays focused on authoring the template itself.
4. On every change, the `ProjectPrompt.prompt` field is updated. The dirty flag is set.
5. Template text may use two placeholder forms:
   - `{{column_name}}` references a CSV column or another prompt output field.
   - `{{@relative/path.ext}}` references a knowledge-base file within the project's configured knowledge-base directory.
6. Knowledge-base references are project-scoped:
   - The knowledge-base directory is configured per project.
   - Supported referenced file types include directly readable text formats (`.md`, `.markdown`, `.txt`, `.csv`) and additional local file types that the application's MarkItDown-backed conversion capability can successfully convert to Markdown for prompt use.
   - Packaged desktop builds bundle the MarkItDown runtime dependencies required for the application's supported local conversion formats, including PDF conversion.
   - Referenced paths are interpreted relative to the configured knowledge-base directory.
   - Referenced paths must not escape the configured knowledge-base directory.
   - Directly readable text formats are inserted from the source file contents.
   - Convertible non-text formats are inserted from their converted Markdown representation.
   - Converted output may be reused from a transparent local cache keyed by the current source file content; when the source file changes, the application regenerates the converted Markdown before use.
   - Included file content is inserted verbatim into the rendered prompt and is not recursively rendered for additional placeholders.
7. The template is validated before preview or batch processing starts:
   - Unknown `{{column_name}}` placeholders cause an error dialog.
   - Every `{{@...}}` reference must resolve to an existing supported file within the configured knowledge-base directory.
   - If a referenced file requires conversion, the application's MarkItDown integration must be available and working before preview or processing starts.
   - Missing, unsupported, unreadable, escaping, conversion-unavailable, or conversion-failed knowledge-base references cause an error dialog and block preview and processing.

**Postconditions:** The prompt template text is updated in the project definition and will be persisted on next save.

## Use Case 28: Manage Prompt Attachments

**Actor:** User

**Description:** The user manages structured prompt attachments for the selected prompt without embedding those sources directly in the prompt text.

**Trigger:** User opens the selected prompt's attachment management UI from the Prompts area.

**Preconditions:** A prompt is selected.

**Flow:**

1. The main prompt editor remains dedicated to prompt text. Attachment editing is opened in a separate attachment-management dialog or window so the Prompts panel stays uncluttered.
2. The attachment-management UI lists the selected prompt's attachments in their current persisted order.
3. Each attachment is metadata, not prompt text. Each attachment records:
   - a source type of either knowledge-base file or CSV column,
   - a source identifier (knowledge-base relative path or CSV column name), and
   - its order within the prompt's attachment list.
4. The user may add attachments through separate source-specific selection flows rather than one mixed picker.
5. The attachment manager exposes distinct add actions or an equivalent explicit source-type choice for the two supported source types:
   - **Add knowledge-base file attachment** opens a small modal select-only knowledge-base-file picker rooted at the project's configured knowledge-base directory. This flow behaves like a simplified knowledge-base explorer for choosing supported files.
   - **Add CSV-column attachment** opens a small modal column-selection flow specialized for CSV columns, such as a dedicated list or dropdown of available columns.
6. The application must not present CSV columns as a virtual knowledge-base branch, folder, or directory analogue. Knowledge-base files and CSV columns remain separate concepts in the selection UX even though both become attachments in the same ordered list.
7. Knowledge-base-file attachment selection may include both directly readable knowledge-base files and non-editable local files that the application can convert to Markdown for prompt use.
8. Each add flow may support selecting one or more sources of its own type in a single confirmation.
9. When the user confirms an add action, the chosen sources are inserted into the selected prompt's attachment list in a default order that places knowledge-base-file attachments before CSV-column attachments so the effective prompt's knowledge-base prefix remains stable by default.
   - Adding one or more knowledge-base-file attachments places those new file attachments after any existing knowledge-base-file attachments and before any existing CSV-column attachments.
   - Adding one or more CSV-column attachments places those new column attachments after all existing attachments.
   - Within a single add action, the chosen sources preserve the order returned by that source-specific selection flow unless the user later reorders them.
10. The user may remove any existing attachment from the list.
11. The user may reorder attachments within the list, including moving CSV-column attachments above knowledge-base-file attachments. The displayed order is the effective processing order.
12. Attachment changes update the selected prompt's metadata and mark the project dirty.
13. If the effective order places any CSV-column attachment before any knowledge-base-file attachment, the attachment-management UI shows a small fine-print warning that this arrangement may increase prompt cost because knowledge-base-file content may need to be reprocessed instead of benefiting from stable-prefix caching.

**Postconditions:** The selected prompt has an ordered attachment list stored as prompt metadata, separate from the prompt text.

**Error conditions:**
- If the user tries to add a knowledge-base-file attachment when no project knowledge-base directory is configured, the add flow is blocked and the user is informed.
- If the user tries to execute a prompt whose selected knowledge-base-file attachment requires conversion but the MarkItDown integration is unavailable or failing, the application warns that the file cannot be included and blocks the run rather than silently omitting it.
- If no valid selectable sources exist for the requested source type, that source-specific add flow may open in an empty state or its add action may be disabled, but the application must not create invalid attachment entries silently.

**Invariants:**
- Prompt attachments are additive prompt metadata and do not rewrite or inject text into the saved prompt template.
- Existing inline placeholder behavior remains supported: `{{column}}` and `{{@path}}` keep their current meaning and may still be used even when prompt attachments are configured.
- Attachment order is user-controlled and persists across project save/load cycles.
- The attachment-management UX keeps knowledge-base-file selection and CSV-column selection as separate flows; the application must not rely on a single mixed source picker or a virtualized "columns as knowledge-base tree nodes" model.
- The default attachment insertion behavior prefers knowledge-base-file attachments before CSV-column attachments, but users may override that order manually.

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

**Preconditions:** At least one row is loaded. One prompt is selected and valid. The row's data satisfies all template placeholders and attachment references. Any referenced knowledge-base files resolve successfully within the project's configured knowledge-base directory.

**Flow:**

1. Validation runs before the worker is created:
    - The document has rows.
    - The prompt template references only known headers or prompt output fields where allowed.
    - Every `{{@...}}` reference resolves to an existing supported file under the project's configured knowledge-base directory.
    - Every knowledge-base-file attachment resolves to an existing supported file under the project's configured knowledge-base directory.
    - Every CSV-column attachment references an existing current CSV header or current prompt output column available in the working document.
    - If the prompt contains any missing, unsupported, unreadable, or escaping knowledge-base reference, preview is aborted and an error dialog is shown.
    - If the prompt contains any missing or invalid attachment source, preview is aborted and an error dialog is shown identifying the invalid attachment.
2. A `GenerationWorker` is created on a `QThread` with the selected row and the single prompt.
3. Before provider generation starts, the application builds the effective prompt by rendering the prompt template as usual and then appending each configured attachment automatically in attachment order.
    - Appended attachment content includes provenance/context that makes clear it is an attachment and identifies its source.
    - Knowledge-base-file attachments append the referenced file contents using the attachment's relative path as provenance.
    - CSV-column attachments append the current row's value for the referenced column using the column name as provenance.
    - The default attachment ordering behavior is intended to keep knowledge-base-file content earlier than row-varying CSV-column content so the prompt prefix stays more stable by default, though user-defined reordering still takes precedence.
4. An `ActivityDialog` opens showing the provider, model, generation parameters, input/output character counts, and a progress indicator.
5. The worker streams chunks from the provider back to the UI via signals. Each chunk is appended to the cell in the table model.
6. The description preview panel on the right updates live with the generated HTML.
7. On completion, cancellation, or failure, the activity dialog is closed and the status bar shows the result.

**Postconditions:** The selected row's output column contains the generated HTML fragment.

## Use Case 12: Process All CSV Rows

**Actor:** User

**Description:** The user triggers batch generation across all rows and all enabled prompts.

**Trigger:** User clicks **Process** or selects **Process > All CSV Rows** (Ctrl+P).

**Preconditions:** At least one prompt is enabled. Rows are loaded. Template and attachment validation pass, including validation of all referenced knowledge-base files.

**Flow:**

1. Before any worker is created, validation runs for all enabled prompts:
    - Column and prompt-output placeholders must be valid.
    - Every `{{@...}}` reference must resolve to an existing supported file under the project's configured knowledge-base directory.
    - Every knowledge-base-file attachment must resolve to an existing supported file under the project's configured knowledge-base directory.
    - Every CSV-column attachment must reference an existing current CSV header or current prompt output column available in the working document.
    - Missing, unsupported, unreadable, or escaping knowledge-base references abort processing and are reported before any row is processed.
    - Missing attachment sources or invalid attachment types abort processing and are reported before any row is processed.
2. If the row count exceeds 10, a confirmation dialog warns the user that the run may take a long time.
3. All rows (regardless of table filters) are collected as row specs.
4. All enabled prompts are collected.
5. An activity dialog opens. A worker is created on a background thread.
6. For each prompt, the worker iterates over all rows. For each row, the effective prompt is built by rendering the template and then appending the prompt's configured attachments in order with provenance/context before the provider call is made.
   - By default, attachment insertion behavior prefers knowledge-base-file attachments before CSV-column attachments to keep the prompt prefix more stable across rows, but any persisted user reorder is honored exactly.
7. Provider output streams back to the UI. Each generated row updates the table model and the preview panel if the row is the currently selected one.
8. The user may cancel at any time via the Cancel button in the activity dialog.
9. On completion, the dirty flag is set for each row whose output changed.

**Postconditions:** All enabled prompts have generated HTML in their output columns for every row in the CSV.

## Use Case 13: Process Visible Rows

**Actor:** User

**Description:** The user triggers batch generation only for rows that are currently visible (not filtered out).

**Trigger:** User clicks the dropdown arrow on the **Process** button and selects **Visible Rows** (or selects **Process > Visible Rows**).

**Preconditions:** At least one prompt is enabled. Rows are loaded. Filters may be active. Template and attachment validation, including validation of all referenced knowledge-base files, pass.

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

**Description:** The user works with the project's on-disk representation, which consists of a `.project.json` manifest, a sibling `.csv` data file, per-prompt `.prompt.txt` sidecar files, per-prompt attachment metadata stored in the manifest, and an optional project-scoped knowledge-base directory reference.

**Trigger:** Saving or opening a project.

**Preconditions:** The project has prompts and/or CSV data.

**Flow:**

1. **On save:** Each prompt's text is written to `{output_field_sanitized}.prompt.txt` in the project directory. The project manifest is written to `*.project.json`. The sibling CSV is written to `*.csv`.
   - Prompt attachment metadata is stored in the manifest as structured prompt metadata separate from prompt text sidecars.
   - Attachment metadata preserves source type, source identifier, and order.
2. **Knowledge-base directory persistence:**
   - A project may store a configured knowledge-base directory in its manifest.
   - When possible, the stored knowledge-base directory path is relative to the `.project.json` file location.
   - If a relative representation is not possible, an absolute path may be stored.
   - The knowledge-base directory setting is saved separately from the files inside that directory; saving the project persists the directory reference only.
3. **On load:** Prompts with `prompt_file` references have their text read from sidecars. Prompt attachment metadata is restored from the manifest without modifying prompt text. The sibling CSV is loaded if present using the persisted import-derived working CSV settings recorded in the project config, not the export settings and not heuristics as the normal path. If the raw nested project payload truly omits `csv.import_settings`, the application may use heuristic sibling-CSV format detection as a backward-compatibility fallback only; after that fallback succeeds, the next save persists the detected import settings so later loads return to the normal deterministic path. If a knowledge-base directory is configured, it is resolved relative to the project file when stored as a relative path.
4. Column naming: prompt output fields are sanitized to alphanumeric, dot, underscore, and hyphen characters, replacing all others with underscores.

**Postconditions:** The project's on-disk layout is consistent and reconstructible, including its project-scoped knowledge-base directory setting.

**Invariants:**
- Prompt text persistence and prompt attachment persistence are separate concerns: prompt text remains in `.prompt.txt` sidecars, while attachment metadata remains in the `.project.json` manifest.
- Older project files without prompt-attachment metadata remain loadable; the effective attachment list for such prompts is empty.
- Existing inline `{{column}}` and `{{@path}}` placeholder behavior remains backward compatible and does not require migration into attachment metadata.
- Missing `csv.import_settings` fallback is a backward-compatibility bridge for nested-shape project payloads only; it is not the primary reopen contract for sibling project CSV data.

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
4. The user may set or change the knowledge-base directory by browsing for a folder. The folder-selection dialog must open successfully on supported PySide6 builds and must not fail because of an incompatible dialog-options argument type.
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
4. For directly editable knowledge-base files, the explorer offers embedded edit actions as defined by Use Cases 26 and 27.
5. For supported non-editable local files that require conversion (for example PDFs and other formats the application's MarkItDown integration can convert), the explorer offers an internal Markdown view action as defined by Use Case 29.
6. The user may copy a file within the knowledge-base root.
7. The user may rename a file within the knowledge-base root.
8. The application may also offer file deletion within the knowledge-base root.
9. If deletion is offered and the user invokes it, the application shows a confirmation dialog identifying the file to be removed before deletion completes.
10. After a successful copy, rename, or delete action, the explorer refreshes to show the current filesystem state.

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

## Use Case 29: View a Convertible Knowledge-Base File as Markdown

**Actor:** User

**Description:** The user opens a supported non-editable knowledge-base file, such as a PDF, in an internal Markdown viewer after local conversion.

**Trigger:** User chooses a view action for a supported convertible knowledge-base file from the knowledge-base explorer.

**Preconditions:** A project-scoped knowledge-base directory is configured, the selected file exists within that directory, the file is inside that root, and the file type is one the application's MarkItDown integration can convert for local viewing.

**Flow:**

1. The application determines whether its MarkItDown integration is available and working.
2. If a cached converted Markdown artifact already exists for the current source-file content, that cached Markdown is reused.
3. Otherwise, the application converts the local source file to Markdown and stores the result in a transparent local cache keyed by the current source file content.
4. The application opens a modal internal Markdown viewer for the converted output.
5. The viewer is read-only for converted files; it does not allow saving changes back to the source document.
6. The viewer also provides an action to open the original source file externally.
7. If the source file later changes on disk, the next internal view request regenerates the converted Markdown instead of reusing the stale cached version.

**Postconditions:** The user can inspect a Markdown rendering of the selected source document inside the application without modifying the original file.

**Error conditions:** Unavailable MarkItDown integration, unsupported file type, unreadable source file, failed conversion, or invalid cache reuse is reported to the user and the internal view is not opened.

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
| Knowledge-base conversion service | `kb_conversion.py` (planned) | Resolve directly readable vs convertible KB files, use the app's MarkItDown integration to convert supported local files, manage conversion cache, and provide Markdown content for viewing and prompt use |
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
- Prompt templates can also reference project-scoped knowledge-base files via `{{@relative/path.ext}}`; directly readable text formats (`.md`, `.markdown`, `.txt`, `.csv`) are supported natively, additional local file types may be supported through MarkItDown-backed conversion to Markdown, paths are resolved relative to the configured knowledge-base directory, escaping that directory is forbidden, and included content is inserted without recursive rendering.
- Prompt attachments are ordered prompt metadata, separate from prompt text, and support exactly two source types: project knowledge-base files and CSV columns.
- Prompt attachments are managed in a separate attachment-management UI so the main prompt editor remains focused on prompt text authoring.
- During preview and processing, attachments are appended automatically to the effective prompt after normal template rendering, with source provenance/context preserved in the appended text.
- Prompt execution may reuse a transparent local Markdown conversion cache keyed by source-file content for convertible knowledge-base files; if the source changes, the application regenerates the converted Markdown before reuse.
- Validation for prompt execution covers both inline placeholders and prompt attachments; missing columns, missing knowledge-base files, unsupported file types, unreadable files, escaping knowledge-base paths, unavailable or failing MarkItDown integration, and conversion failures block execution.
- The application provides a separate project-scoped knowledge-base management window for setting or clearing the knowledge-base directory, browsing files under that root, performing copy/rename actions within that root, optionally deleting files there with confirmation, opening files externally, opening supported text/CSV files in modal embedded editors, and opening supported convertible files in a read-only internal Markdown viewer.
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
  → Validate CSV placeholders + knowledge-base references + prompt attachments
  → Prompt dependency graph built and topologically sorted (or cycle detected)
  → GenerationService.prepare_prompt() → PromptRenderer.render() → append ordered attachment content with provenance
  → ProviderClient.generate() → Streaming chunks
  → GenerationWorker.row_generated → TableModel.set_cell()
  → HtmlPreview.set_html() → Rendered output

User saves project
  → ProjectRepository.save() → *.project.json + *.prompt.txt sidecars
  → CsvRepository.save() → per-field whitespace normalization (if `strip_html_whitespace`), then writes *.csv sibling
```
