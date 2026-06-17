# KB Directory Dialog Fix

- User-reported bug: opening the Knowledge Base directory chooser crashes at runtime with a `TypeError` from `QFileDialog.getExistingDirectory(...)`.
- Requested behavior: the Knowledge Base manager should let the user browse for a directory without crashing.
- Constraint: keep the existing file-dialog abstraction and test-mode behavior intact.
- Non-goal: no workflow or UI redesign for the Knowledge Base manager.
