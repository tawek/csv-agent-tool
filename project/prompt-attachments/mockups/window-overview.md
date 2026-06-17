# Prompt Attachments Window Overview

## Purpose

- Define how prompt-attachment management fits into the main prompt-authoring workflow.
- Keep the main prompt editor focused on template text while routing attachment editing to a separate surface.

## Input artifacts consumed

- `docs/specification.md` — especially Use Case 10, Use Case 11, Use Case 12, Use Case 19, and Use Case 28.
- `project/prompt-attachments/implementation-notes.md`
- `project/prompt-attachments/status.md`

## Main-window touchpoint

- The existing prompt editor stays in the Prompts panel.
- Add one attachment-related entry point near the selected prompt controls, not inside the prompt text area.
- Suggested control label: **Attachments…**
- Optional nearby passive summary text: `3 attachments configured`.
- The main window does not expose separate KB-vs-column add controls directly; that split happens inside the attachment manager.

## Rough layout in main window

```text
+--------------------------------------------------------------+
| Prompts                                                      |
| [Prompt selector v] [Add] [Delete] [Enabled] [Attachments…] |
| 3 attachments configured                                     |
|--------------------------------------------------------------|
| Prompt template editor                                       |
|                                                              |
| {{title}} ...                                                |
|                                                              |
+--------------------------------------------------------------+
```

## Controls and labels

- **Attachments…** button
  - Opens the attachment-management dialog/window for the selected prompt.
  - Enabled only when a prompt is selected.
- Summary label/text
  - Shows count of configured attachments for the selected prompt.
  - Should update immediately after add/remove/reorder.

## Primary and secondary actions

- Primary action from the main window: **Attachments…**
- No add/remove/reorder actions occur directly in the main window.

## Modal vs modeless behavior

- Main window remains modeless as usual.
- Attachment editing itself occurs in a separate dedicated surface.
- Spec allows “dialog or window”; recommended implementation direction for clarity is a dedicated management dialog/window launched from **Attachments…**.

## Validation and error states

- If no prompt is selected, **Attachments…** is disabled.
- If attachment metadata later becomes invalid because sources changed, that should not be edited inline here; validation errors surface during management and before preview/process per spec.

## Interaction notes

- Attachment metadata remains separate from prompt text and must not inject text into the saved editor content.
- The main prompt editor should not display appended attachment bodies; it stays an authoring surface for template text only.
- The UI should communicate somewhere in the attachment flow that attachments are appended automatically to the effective prompt with source provenance/context.
- The attachment flow should branch into two dedicated add dialogs: one simplified KB explorer for files and one simple column picker for CSV columns.
- The attachment flow should communicate that new attachments default to KB files first and CSV columns afterward, while still permitting manual reordering.

## Open questions

- Should the attachment manager open as a modal dialog or a separate non-modal utility window? The spec permits either; implementation should choose based on consistency with the existing knowledge-base manager.
- Should the summary text list source types (example: `2 files, 1 column`) or only a total count? Current spec only requires manageability, not summary granularity.
- The current spec wording for Use Case 28 still describes one mixed add picker; should that be revised to match the clarified separate-flow design?
