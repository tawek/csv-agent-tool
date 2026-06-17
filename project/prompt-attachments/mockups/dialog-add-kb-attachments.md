# Add KB File Attachments Mockup

## Purpose

- Provide a small modal dialog for selecting one or more knowledge-base files as prompt attachments.
- Reuse the knowledge-base explorer concept in a simplified, select-only flow.

## Input artifacts consumed

- `docs/specification.md` — especially Use Case 28 and the validation expectations in Use Cases 11 and 12.
- `project/prompt-attachments/implementation-notes.md`
- `project/prompt-attachments/status.md`

## Recommended title

- **Add Knowledge-Base Attachments**

## Modal vs modeless behavior

- Modal dialog.

## Rough layout sections

```text
+----------------------------------------------------------------+
| Add Knowledge-Base Attachments                                 |
|----------------------------------------------------------------|
| Select one or more knowledge-base files to append as prompt    |
| attachments. The prompt text itself will not be modified.      |
|----------------------------------------------------------------|
| [Search ______________________________ ]                        |
|                                                                |
| Knowledge-base files                                           |
| > style/                                                       |
|   [ ] brand-voice.md                                           |
| > taxonomy/                                                    |
|   [ ] categories.csv                                           |
|   [ ] attributes.md                                            |
|                                                                |
| Helper / empty / error text                                    |
|----------------------------------------------------------------|
| [Cancel]                                      [Add Selected]   |
+----------------------------------------------------------------+
```

## Controls and labels

- Intro/help text
  - Explains that selected items become prompt attachments, not inline prompt text.
- **Search** field
  - Filters visible KB files by relative path/name.
- Select-only KB explorer list/tree
  - Shows only supported file types: `.md`, `.markdown`, `.csv`.
  - Folder rows expand/collapse.
  - File rows provide multi-select checkboxes or equivalent selection affordance.
- **Add Selected**
  - Returns all selected KB files in visible order.
  - In the attachment manager, newly added KB-file attachments are inserted before any existing CSV-column attachments by default.
  - Disabled when nothing is selected.
- **Cancel**
  - Closes without changes.

## Primary and secondary actions

- Primary action: **Add Selected**
- Secondary action: **Cancel**

## Validation and error states

- No knowledge-base directory configured:
  - This dialog should not open from the manager.
  - If opened defensively, show blocking message and disable selection.
- No supported KB files found:
  - Show empty state: `No supported knowledge-base files are available.`
  - **Add Selected** disabled.
- Search produces no matches:
  - Show `No knowledge-base files match the current search.`

## Interaction notes

- Keep this dialog simpler than the full knowledge-base manager: selection only, no file editing or file-management actions.
- Display paths relative to the configured project knowledge-base root.
- Returned add order should be deterministic; recommended rule is top-to-bottom visible order among selected files.
- This dialog does not manage mixed-type placement directly; default placement is handled by the attachment manager's KB-first ordering rule.
- Do not present CSV columns here.

## Open questions

- Should the simplified KB explorer allow selecting folders indirectly through children selection helpers, or only direct file selection? Direct file selection is the safer default.
