# Add Column Attachments Mockup

## Purpose

- Provide a small modal dialog for selecting one or more CSV columns as prompt attachments.
- Keep column attachment selection as a simple dedicated flow, separate from KB browsing.

## Input artifacts consumed

- `docs/specification.md` — especially Use Case 28 and the validation expectations in Use Cases 11 and 12.
- `project/prompt-attachments/implementation-notes.md`
- `project/prompt-attachments/status.md`

## Recommended title

- **Add Column Attachments**

## Modal vs modeless behavior

- Modal dialog.

## Rough layout sections

```text
+---------------------------------------------------------------+
| Add Column Attachments                                        |
|---------------------------------------------------------------|
| Select one or more current CSV columns to append as prompt    |
| attachments. The prompt text itself will not be modified.     |
|---------------------------------------------------------------|
| [Search ______________________________ ]                      |
|                                                               |
| Available columns                                             |
| [ ] title                                                     |
| [ ] bullets                                                   |
| [ ] product_specs                                             |
| [ ] seo_description                                           |
|                                                               |
| Helper / empty / error text                                   |
|---------------------------------------------------------------|
| [Cancel]                                     [Add Selected]   |
+---------------------------------------------------------------+
```

## Controls and labels

- Intro/help text
  - Explains that selected items become prompt attachments whose current row values are appended at runtime.
- **Search** field
  - Filters visible columns by name.
- Column list
  - Flat list, no folder/tree concepts.
  - Multi-select checkboxes or equivalent selection affordance.
  - Entries are column names only.
- **Add Selected**
  - Returns all selected columns in visible order.
  - In the attachment manager, newly added column attachments are inserted after the last KB-file attachment by default.
  - Disabled when nothing is selected.
- **Cancel**
  - Closes without changes.

## Primary and secondary actions

- Primary action: **Add Selected**
- Secondary action: **Cancel**

## Validation and error states

- No valid columns available:
  - Show empty state: `No current CSV columns are available.`
  - **Add Selected** disabled.
- Search produces no matches:
  - Show `No columns match the current search.`

## Interaction notes

- This dialog must not reuse KB-tree terminology or visuals beyond generic list selection patterns.
- There is no virtual KB branch/directory abstraction for columns.
- Valid entries may include ordinary CSV headers and current prompt output columns if they exist as current document columns per spec.
- Returned add order should be deterministic; recommended rule is top-to-bottom visible order among selected columns.
- This dialog does not ask the user to choose mixed-type placement; default placement is managed by the attachment manager's KB-first ordering rule.

## Open questions

- Should prompt output columns be visually distinguished from imported CSV headers in this list, or should all valid current columns appear uniformly? The spec allows them, but display treatment is not specified.
