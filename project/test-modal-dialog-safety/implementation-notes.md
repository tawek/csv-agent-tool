# Implementation Notes — Test Modal Dialog Safety

## User intent snapshot

- Make sure test hangs from modal dialogs do not happen again.
- Record the durable pattern for safe GUI tests.
- Capture the cache-isolation rule that prevented the knowledge-base viewer hang.

## Practical rules

- Use the wrapper modules for blocking dialogs: `message_box`, `file_dialog`, and `input_dialog`.
- For modal viewer/editor dialogs that still use `QDialog.exec()`, tests should monkeypatch `exec()` or otherwise intercept the dialog before it blocks.
- Give cache-backed tests a fresh temporary cache directory per test run.
- Treat tuple-shaped file-dialog responses as a caller concern only when the wrapper explicitly documents them; the app-facing wrapper should return the path string that production code expects.

## Non-goals

- Do not reintroduce direct `PySide6.QtWidgets.QMessageBox`, `QFileDialog`, or `QInputDialog` monkeypatching in tests.
- Do not share one global cache directory across the whole suite if the behavior under test depends on cache misses.
