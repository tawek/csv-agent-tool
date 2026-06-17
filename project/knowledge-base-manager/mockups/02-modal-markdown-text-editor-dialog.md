# Mockup 2: Modal Markdown / Text Editor Dialog

## Purpose

- Covers `docs/specification.md` Use Case 26.
- Reuses the same markdown-capable embedded editor concept as the main prompt editor.
- Modal dialog for supported KB text files.

## Dialog Summary

- Dialog title examples:
  - `Edit Knowledge Base File - faq.md`
  - `Edit Knowledge Base File - tone.txt`
- Modal with explicit `Save` and `Cancel` actions.
- Includes an external-open action for the same file.

## Layout Sketch

```text
+----------------------------------------------------------------------------+
| Edit Knowledge Base File - faq.md                                          |
|----------------------------------------------------------------------------|
| File: faq.md                                                               |
| Path: snippets/faq.md                                                      |
| Type: Markdown                                                             |
|----------------------------------------------------------------------------|
| [Open Externally]                                                          |
|----------------------------------------------------------------------------|
|                                                                            |
|  # FAQ                                                                     |
|                                                                            |
|  ## Shipping                                                               |
|  Orders ship within 2 business days.                                       |
|                                                                            |
|  ## Returns                                                                |
|  ...                                                                       |
|                                                                            |
|----------------------------------------------------------------------------|
|                                                     [Save] [Cancel]        |
+----------------------------------------------------------------------------+
```

## Behavior Notes

- On open, load current file contents into the editor.
- `.md` and `.markdown`:
  - markdown syntax highlighting enabled.
- supported plain-text files:
  - editable as plain text,
  - no markdown-specific behavior required.
- `Open Externally`:
  - launches the selected file in the OS-associated application.

## Expected Controls

- Header metadata:
  - file name,
  - relative path within KB root,
  - file type.
- Main editor area:
  - multi-line text editor,
  - same shared editor component family as prompt editing.
- Footer buttons:
  - `Save`: write file and close.
  - `Cancel`: close without saving.

## Suggested Interaction Details

- `Save` should be enabled when editing is allowed; dirty-state-specific enablement is optional.
- Closing via window close button should behave like cancel unless the implementation later adds unsaved-change confirmation.
- After successful save, the manager window should refresh file metadata visible in the explorer.

## Open Questions

- The current spec requires `Save`, `Cancel`, and `Open Externally`, but does not explicitly define unsaved-change confirmation on close. If desired, that behavior should be added to the spec rather than assumed.
- The spec says "view or edit" but the current flow reads as editable-by-default. If a separate read-only mode is intended later, that should be specified explicitly.
