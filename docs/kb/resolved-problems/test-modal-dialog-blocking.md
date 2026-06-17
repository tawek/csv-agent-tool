# Resolved Problem: Test Modal Dialog Blocking

## Problem

Headless GUI tests could appear to pass individual test bodies and then hang during teardown because a real modal dialog was still reachable.

## Root cause

- Blocking `QMessageBox` paths were not safely neutralized for unattended runs.
- A naive warning stub can be incorrect for unsaved-changes flows if it effectively chooses `Save`, which can open a file dialog during teardown.
- A cache hit can hide the branch under test, so the modal dialog path may appear to be fixed while the real failure still exists on a cold cache.
- Modal viewer/editor tests that reach `QDialog.exec()` still need an explicit intercept even when the message-box layer is stubbed.

## Preferred resolution

- Provide shared non-blocking `QMessageBox` defaults in `tests/conftest.py`.
- For warning dialogs, choose a teardown-safe default when the button set represents `Save / Discard / Cancel`.
- Let individual tests override the shared defaults when they need precise button behavior or assertions.
- Give cache-sensitive tests an isolated temporary cache directory, or clear the relevant cache before the test body runs.
- Monkeypatch `QDialog.exec()` in tests that intentionally open a modal viewer/editor dialog.

## Wrapper contract note

- File-dialog wrappers should return the path string the application code consumes.
- Tests that need to fake file selection should supply wrapper responses that match the wrapper contract, not the raw Qt tuple, unless the wrapper explicitly documents a tuple return.

## Policy impact

- Modal dialog stubbing is mandatory for unattended GUI tests.
- Test commands should be sharded to respect the 30-second command cap.
