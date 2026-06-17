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
