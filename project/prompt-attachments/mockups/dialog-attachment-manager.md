# Prompt Attachment Manager Mockup

## Purpose

- Let the user manage the selected prompt's attachment metadata in one dedicated surface.
- Support add, remove, and reorder without cluttering the main prompt editor.
- Make the default ordering bias visible: KB-file attachments come before CSV-column attachments unless the user explicitly reorders them.

## Input artifacts consumed

- `docs/specification.md` — especially Use Case 28 plus preview/processing validation in Use Cases 11 and 12.
- `project/prompt-attachments/implementation-notes.md`
- `project/prompt-attachments/status.md`

## Recommended title

- **Prompt Attachments — {output_field}**

## Modal vs modeless behavior

- Recommended: modal dialog relative to the main window.
- Rationale: keeps the workflow focused and matches the spec's dedicated management surface without becoming another always-open panel.

## Rough layout sections

```text
+------------------------------------------------------------------+
| Prompt Attachments — seo_description                             |
|------------------------------------------------------------------|
| Info                                                             |
| Attachments are stored as prompt metadata and are appended       |
| automatically to the effective prompt with source provenance.    |
| By default, KB files are placed before CSV columns.              |
| The prompt text itself is not modified.                          |
|------------------------------------------------------------------|
| Attachments (ordered processing order)                           |
| +--------------------------------------------------------------+ |
| | # | Type           | Source                          | Notes | |
| | 1 | KB file        | style/brand-voice.md           | ...   | |
| | 2 | KB file        | taxonomy/categories.csv        | ...   | |
| | 3 | CSV column     | product_specs                  | ...   | |
| +--------------------------------------------------------------+ |
|                                                                  |
| [Add KB Files…] [Add Columns…] [Remove] [Move Up] [Move Down]   |
| Fine print: Moving a CSV-column attachment above any KB-file    |
| attachment may increase prompt cost because KB content may be   |
| reprocessed instead of benefiting from a more stable prefix.    |
|------------------------------------------------------------------|
| Validation / status area                                         |
| - Missing KB root configured                                     |
| - Selected source no longer exists                               |
|------------------------------------------------------------------|
|                                             [Close]              |
+------------------------------------------------------------------+
```

## Controls and labels

- Read-only info/help text
  - Explains automatic append behavior.
  - Explains provenance/context is included when attachments are appended.
- Attachment list/table
  - Columns:
    - **#** (effective order)
    - **Type** (`KB file` or `CSV column`)
    - **Source** (relative path or column name)
    - **Notes** (optional derived status such as `Available`, `Missing`, `Current row value used at runtime`)
- **Add KB Files…**
   - Opens a dedicated select-only knowledge-base explorer style dialog.
   - Newly added KB-file attachments are inserted before the first CSV-column attachment when one exists; otherwise they are appended at the end of the list.
   - Disabled when no project knowledge-base directory is configured.
- **Add Columns…**
   - Opens a separate simple CSV-column picker dialog.
   - Newly added CSV-column attachments are inserted after the last KB-file attachment so KB files remain first by default.
   - Enabled when at least one valid current column exists.
- **Remove**
   - Removes selected attachment(s).
  - Disabled when nothing is selected.
- **Move Up**
  - Reorders selected item upward by one.
  - Disabled for first item or when no single movable selection is active.
- **Move Down**
  - Reorders selected item downward by one.
  - Disabled for last item or when no single movable selection is active.
- **Close**
  - Closes the manager.

## Primary and secondary actions

- Primary actions inside this dialog: **Add KB Files…** and **Add Columns…**.
- Secondary actions: **Remove**, **Move Up**, **Move Down**, **Close**.

## Selection behavior

- Recommended list selection: single-selection for reorder simplicity.
- Remove may optionally support multi-select deletion, but reorder should operate on one selected row at a time.
- After add, select the first newly appended item or the last appended item.
- After remove, selection should move to the next remaining item if present.

## Validation and error states

- No prompt selected before opening: manager should not open; launching control should be disabled in main window.
- No knowledge-base directory configured:
  - **Add KB Files…** disabled.
  - **Add Columns…** remains available if valid columns exist.
  - Show explanatory text: `Knowledge-base file attachments require a configured project knowledge-base directory.`
- No valid CSV columns available:
  - **Add Columns…** disabled.
  - Show explanatory text such as `No current CSV columns are available to attach.`
- Empty attachment list:
  - Show empty-state helper text such as `No attachments configured for this prompt.`
  - **Remove** and reorder buttons disabled.
- CSV-column attachment moved above one or more KB-file attachments:
  - Show the small fine-print cost warning directly under the list.
  - This is informational only; it does not block saving or reordering.
- Persisted invalid attachment detected:
  - Display visible warning in status area and/or Notes column.
  - Do not silently delete or rewrite the entry.
  - Preview/process validation remains blocked until fixed, per spec.

## Interaction notes

- Changes should apply immediately to in-memory prompt metadata and mark the project dirty.
- The list order shown here is the processing order used when building the effective prompt.
- Default insertion behavior should keep KB-file attachments before CSV-column attachments, but the user may still reorder to any persisted order.
- Source paths for KB files should be displayed relative to the project knowledge-base root.
- CSV column entries should include both ordinary CSV headers and prompt output columns if those are valid current document columns per spec.
- The manager should not show attachment content bodies; this surface is for metadata management only.
- There is no unified mixed picker and no virtual `columns as knowledge-base branch` abstraction.

## Open questions

- Should this dialog include a read-only preview of the appended template block format for the selected attachment? Useful, but not explicitly required by spec.
- Should invalid persisted attachments be removable while still marked invalid? Recommended yes, but the exact affordance is not specified.
- The current spec text still describes one modal picker that can select both source types at once; should that contract be updated to match the clarified separate-flow UX now reflected in these mockups?
