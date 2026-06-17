# Mockup 3: Modal CSV Editor Dialog

## Purpose

- Covers `docs/specification.md` Use Case 27.
- Modal grid editor for KB CSV files with simple spreadsheet-style editing.
- Must remain faithful to the current spec while surfacing unresolved CSV-structure controls explicitly.

## Dialog Summary

- Dialog title example: `Edit Knowledge Base CSV - size-chart.csv`
- Modal with explicit `Save` and `Cancel` actions.
- Includes an external-open action for the same file.
- Uses heuristically detected CSV settings on open.

## Layout Sketch

```text
+--------------------------------------------------------------------------------+
| Edit Knowledge Base CSV - size-chart.csv                                       |
|--------------------------------------------------------------------------------|
| File: size-chart.csv                                                           |
| Path: tables/size-chart.csv                                                    |
| CSV: delimiter=,   quote="   encoding=detected                                |
|--------------------------------------------------------------------------------|
| [Open Externally]                                                              |
|--------------------------------------------------------------------------------|
|      | A              | B              | C                                     |
|------|----------------|----------------|----------------                       |
| 1    | size           | chest_cm       | waist_cm                              |
| 2    | S              | 86-91          | 71-76                                 |
| 3    | M              | 96-101         | 81-86                                 |
| 4    | L              | 106-111        | 91-96                                 |
|      |                |                |                                       |
|--------------------------------------------------------------------------------|
|                                                     [Save] [Cancel]            |
+--------------------------------------------------------------------------------+
```

## Core Supported Editing From Current Spec

- Edit existing text cells.
- Enter text into empty cells.
- Clear text cell values.
- Replace text cell values.
- Open the file externally.
- Save or cancel.

## Suggested Dialog Regions

### 1. File / CSV Metadata

- Show file name and relative path.
- Show detected CSV read settings in compact form for developer clarity.
- This metadata is informational unless a later spec revision makes it user-editable.

## Grid Area

- Spreadsheet-like table view.
- Cell editing should feel lightweight and direct.
- Vertical and horizontal scrolling expected for larger files.
- Row-number gutter is useful.
- Column labels may be lettered (`A`, `B`, `C`) or use first-row data if the implementation treats the file differently; current spec does not constrain this tightly.

## Footer Actions

- `Save`: writes the current grid state back to disk and closes.
- `Cancel`: closes without saving.
- `Open Externally`: separate action, not a substitute for embedded editing.

## Open Question: Row / Column Add-Remove Controls

- The feature notes in `project/knowledge-base-manager/implementation-notes.md` explicitly say the CSV editor must support:
  - adding and removing rows,
  - adding and removing columns,
  - simple spreadsheet behavior.
- The current spec for Use Case 27 explicitly covers cell editing, clearing, and replacing, but does not yet spell out the exact row/column add-remove controls or flow.
- Because of that, this mockup does not silently invent final controls.

Placeholder toolbar area if the spec is expanded:

```text
[ Add Row ? ] [ Remove Row ? ] [ Add Column ? ] [ Remove Column ? ]
```

Developer note:

- If row/column structural editing is intended for the first implementation, the spec should be updated to define:
  - whether controls are toolbar buttons, context-menu actions, or both,
  - how selection drives add/remove behavior,
  - whether delete removes structure or only clears cell content,
  - whether column names are user-editable headers or anonymous CSV positions.

## Additional Open Questions

- The spec requires heuristic CSV detection, but does not say whether detected delimiter/quote settings are shown only as info or can be overridden before save.
- The spec says "view or edit" but currently defines an editable flow. If a read-only inspection mode is desired, it should be added explicitly.
