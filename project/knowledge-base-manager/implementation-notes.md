# Implementation Notes — Knowledge Base Manager

## User intent snapshot

- Separate knowledge-base management window.
- Set KB dir and clear it.
- List files in a file/dir explorer.
- Edit `.md` and `.txt` in an embedded editor.
- Edit `.csv` in a grid/table editor with simple spreadsheet behavior.
- CSV editor must support editing, adding, and removing text cells, rows, and columns.
- Always allow external viewer/editor for any file.
- Allow opening the KB directory in the external file explorer.
- Embedded file view/edit is modal with Save/Cancel.
- Support copy file, rename file, and optionally delete with confirmation.
- Reuse the markdown editor as the prompt editor in the middle panel.

## Planned architecture

- Keep knowledge-base directory project-scoped.
- Add a dedicated knowledge-base management window.
- Reuse a shared markdown-capable text editor for both KB text editing and the main prompt editor.
- Isolate filesystem operations and external-app launching behind dedicated helpers for testability.

## Follow-up user intent snapshot — menu simplification

- Replace the current multi-action Knowledge Base menu structure with a single `Knowledge Base` entry.
- That single entry should open the main knowledge base manager screen.
- Remove the expectation that KB actions must remain directly exposed as separate menu actions.
- Add a `Close` button inside the knowledge base manager so users can exit the manager from the main manager screen.
- Keep the improvement simple and centered on reducing menu complexity.
