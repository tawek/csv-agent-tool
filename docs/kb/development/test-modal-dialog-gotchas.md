# Test Modal Dialog Gotchas

## Common failure modes

- A modal dialog can still appear even when the test body passed, because teardown or a later signal path reached `exec()`.
- A cache-backed code path can hide the branch you are trying to test by returning a previously converted result.
- A file-dialog wrapper may return a plain path string even if the underlying Qt call returns a tuple.

## Prevention checklist

- Use `message_box`, `file_dialog`, and `input_dialog` instead of direct Qt dialog monkeypatches.
- Monkeypatch `QDialog.exec()` for any test that opens a modal viewer or editor dialog.
- Give cache-sensitive tests a temporary cache directory so they start cold.
- Keep wrapper responses aligned with the wrapper contract, not the raw Qt API shape.

## When a test still hangs

- Check for a modal `exec()` call after the visible assertion path.
- Check for cached data that bypasses the branch you expected.
- Check teardown paths such as `closeEvent()` and unsaved-changes prompts.
