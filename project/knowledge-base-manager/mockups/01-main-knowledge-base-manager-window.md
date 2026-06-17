# Mockup 1: Main Knowledge-Base Manager Window

## Purpose

- Covers `docs/specification.md` Use Case 21 and Use Case 22.
- Dedicated, separate window for managing the current project's knowledge-base directory and files.
- Developer-facing layout sketch, not visual design polish.

## Window Summary

- Window title: `Knowledge Base Manager`
- Opens only within an active project session.
- Primary responsibilities:
  - show current KB root,
  - let the user set/change/clear it,
  - browse files under that root,
  - run file actions within that root,
  - open files or folders externally,
  - launch embedded modal editors for supported file types.

## Layout Sketch

```text
+----------------------------------------------------------------------------------+
| Knowledge Base Manager                                                           |
|----------------------------------------------------------------------------------|
| Knowledge base directory: [ /path/to/project/kb                          ] [Set] |
|                           [Clear] [Open in File Explorer]                        |
|----------------------------------------------------------------------------------|
| Explorer                                                          | Details      |
|------------------------------------------------------------------|--------------|
| [Root: kb/]                                                      | Name: faq.md |
|                                                                  | Type: .md    |
| kb/                                                              | Path: faq.md |
| |- faq.md                                                        | Size: 12 KB  |
| |- style-guide.md                                                | Modified: ...|
| |- tables/                                                       |--------------|
| |  |- size-chart.csv                                             | Actions      |
| |- snippets/                                                     | [Open Ext.]  |
|    |- tone.txt                                                   | [View/Edit]  |
|                                                                  | [Copy]       |
|                                                                  | [Rename]     |
|                                                                  | [Delete]     |
|------------------------------------------------------------------|--------------|
| Status: Root configured. 14 items.                                               |
+----------------------------------------------------------------------------------+
```

## Regions

### 1. Directory Controls

- Label + read-only path field showing the currently configured project-scoped KB directory.
- `Set` button:
  - opens folder picker,
  - applies selection to the current in-memory project.
- `Clear` button:
  - removes the configured KB directory from the current project.
- `Open in File Explorer` button:
  - opens the configured KB root in the OS file explorer.
  - disabled when no KB root is configured.

## Explorer Pane

- Tree or tree-table rooted at the configured KB directory.
- Shows files and subdirectories only within the KB root.
- Navigation stays constrained to the configured root.
- If no KB root is configured:
  - explorer area remains visible but empty or disabled,
  - inline empty state explains that a KB directory must be set first.

Suggested empty state copy:

```text
No knowledge-base directory configured.
Choose a folder to enable browsing and file actions.
```

## Details / Actions Pane

- Updates based on current explorer selection.
- Shows at minimum:
  - file or folder name,
  - relative path within KB root,
  - type,
  - optional size / modified timestamp if already available.
- Action buttons:
  - `Open Externally`: always available for files, per spec.
  - `View/Edit`: enabled for supported embedded types:
    - `.md`
    - `.markdown`
    - supported plain-text files
    - `.csv`
  - `Copy`
  - `Rename`
  - `Delete`

## Interaction Notes

- Double-click behavior should be conservative and type-aware:
  - folder: navigate/select,
  - supported embedded file: likely open `View/Edit`,
  - unsupported file: likely open externally.
- Copy, rename, and delete refresh the explorer after success.
- Delete must confirm with the selected item name/path.
- Any action that would escape the KB root must be rejected.

## Disabled States

- No project session: window should not open from normal flow.
- No KB root configured:
  - explorer disabled,
  - file actions disabled,
  - `Open in File Explorer` disabled,
  - `Set` remains enabled,
  - `Clear` disabled if already empty.
- No selection in explorer:
  - selection-dependent actions disabled.

## Modal Launch Points

- `View/Edit` on `.md`, `.markdown`, or supported text files opens the modal text editor dialog.
- `View/Edit` on `.csv` opens the modal CSV editor dialog.
- `Open Externally` is separate and should not be blocked by embedded-editor support.

## Open Questions

- The spec requires copy, rename, and delete, but does not yet define whether these are toolbar buttons, context-menu items, or both. Current mockup shows a persistent action pane; adding a right-click context menu too may be useful but is not yet mandated.
- The spec says the explorer is rooted at the KB directory, but does not explicitly require breadcrumbs. A simple rooted tree is sufficient unless navigation friction shows up later.
