# Testing Policy

## Hard rules

- All unattended test commands run by agents must use a hard timeout cap of **30 seconds or less per invocation** unless a shorter cap is more appropriate.
- GUI tests must stub, fake, or monkeypatch blocking modal dialogs such as `QMessageBox` so tests cannot hang waiting for user input.
- GUI tests that open modal viewer/editor dialogs must monkeypatch `QDialog.exec()` or otherwise intercept the dialog before it blocks.
- Cache-sensitive tests must use a per-test temporary cache directory or explicitly clear the relevant cache before the assertion run.
- Prefer focused, sharded test commands when a large file or suite cannot complete inside the timeout cap.

## Current guidance

- Shared non-blocking `QMessageBox` behavior is provided through `tests/conftest.py`.
- Tests that require special button choices or message capture should override the shared defaults locally.
- File-dialog wrappers return the path string the application consumes; tests should supply wrapper responses that match the wrapper contract, not the raw Qt return tuple unless the wrapper explicitly documents that shape.
- Validate the narrowest affected scope first, then broaden only when the command still fits inside the timeout rule.

## Example validation style

- Run one or a few targeted tests for the changed behavior.
- Run related module tests in separate invocations when needed.
- Avoid one oversized test invocation that violates the timeout policy.
