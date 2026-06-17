# Qt dialog test-safety audit

## Scope

Audit of production `PySide6.QtWidgets` dialog usage that can block unattended pytest runs.

Reference pattern reviewed: `src/product_description_tool/message_box.py:1-147`.

## Existing safe pattern

`message_box.py` provides a good model for static Qt dialogs:

- module-level `set_test_mode()` toggle
- per-method default responses
- per-method override hooks via `set_response()`
- `reset()` cleanup for fixtures
- production behavior delegates to the real Qt static method

`tests/conftest.py:10-23` already enables this abstraction globally for tests, but it only covers `message_box.py` callers.

## Priority summary

1. **QFileDialog** — highest priority wrapper candidate
2. **QInputDialog** — high priority wrapper candidate
3. **Raw modal `QDialog.exec()` / custom dialog subclasses** — blocking risk exists, but these are better handled with targeted fakes/monkeypatches than a generic wrapper
4. **QFontDialog / QColorDialog / QProgressDialog / QErrorMessage / similar standard dialogs** — no production usages found

## Findings by dialog type

### 1. QFileDialog

- **Can hang unattended tests?** Yes. Static `getOpenFileName()`, `getSaveFileName()`, and `getExistingDirectory()` block waiting for user input.
- **Production usage count:** 5
- **Current fixture coverage:** Not covered by `tests/conftest.py`.
- **Current test handling:** Per-test monkeypatching.
- **Recommendation:** Add a dedicated wrapper module (for example `file_dialog.py`) that mirrors the `message_box.py` pattern and supports canned responses for:
  - `getOpenFileName`
  - `getSaveFileName`
  - `getExistingDirectory`

Production usages:

- `src/product_description_tool/main_window.py:366` — `QFileDialog.getOpenFileName()` in `open_project()`
- `src/product_description_tool/main_window.py:402` — `QFileDialog.getSaveFileName()` in `save_project()`
- `src/product_description_tool/main_window.py:425` — `QFileDialog.getOpenFileName()` in `load_csv()`
- `src/product_description_tool/dialogs.py:881` — `QFileDialog.getSaveFileName()` in `ExportDialog._browse_path()`
- `src/product_description_tool/kb_window.py:262` — `QFileDialog.getExistingDirectory()` in `KnowledgeBaseManager._set_directory()`

Existing test patterns:

- `tests/test_main_window.py:229-233` — helper monkeypatches `main_window.QFileDialog.getOpenFileName`
- `tests/test_main_window.py:283-286` — monkeypatches `main_window.QFileDialog.getSaveFileName`
- `tests/test_main_window.py:1160` — additional `getOpenFileName` patch site
- `tests/test_dialogs.py:290-293` — monkeypatches `dialogs.QFileDialog.getSaveFileName`
- `tests/test_kb_window.py:92-96` and `118-121` — monkeypatches `QFileDialog.getExistingDirectory`

Architectural note: this is the cleanest next abstraction after `message_box.py` because all usages are static convenience calls with simple return tuples/strings.

### 2. QInputDialog

- **Can hang unattended tests?** Yes. Static `getText()` blocks waiting for user input.
- **Production usage count:** 4
- **Current fixture coverage:** Not covered by `tests/conftest.py`.
- **Current test handling:** Per-test monkeypatching.
- **Recommendation:** Add a dedicated wrapper module (for example `input_dialog.py`) using the same test-mode contract as `message_box.py`, with canned responses for `getText()` returning `(value, accepted)`.

Production usages:

- `src/product_description_tool/kb_csv_editor.py:211` — `QInputDialog.getText()` in `CsvEditorDialog._add_column()`
- `src/product_description_tool/kb_window.py:486` — `QInputDialog.getText()` in `KnowledgeBaseManager._copy_selected()`
- `src/product_description_tool/kb_window.py:524` — `QInputDialog.getText()` in `KnowledgeBaseManager._rename_selected()`
- `src/product_description_tool/main_window.py:623` — `QInputDialog.getText()` in `MainWindow.add_prompt()`

Existing test patterns:

- `tests/test_kb_csv_editor.py:274-277`, `294-297`, `318-321`, `520-521` — monkeypatches `QInputDialog.getText`
- `tests/test_kb_window.py:263-266`, `284-287`, `305-308`, `584-587`, `622-625`, `691-692`, `720-721` — monkeypatches `QInputDialog.getText`

Architectural note: this is also a strong wrapper candidate because the call surface is narrow today. If future code needs `getItem()` / `getInt()` / `getDouble()`, extend the same module rather than adding new ad hoc monkeypatching.

### 3. Raw modal QDialog / custom QDialog subclasses

- **Can hang unattended tests?** Yes, when `exec()` is reached.
- **Production usage count:** 11 `exec()` call sites in source modules.
- **Current fixture coverage:** No global coverage in `tests/conftest.py`.
- **Current test handling:** Targeted fake dialog classes or monkeypatching `exec()`.
- **Recommendation:** Do **not** create one generic wrapper for all modal dialogs. Prefer targeted patterns:
  - replace the dialog class at the import site (`HtmlEditorDialog`, `SettingsDialog`, `AttachmentManager`)
  - monkeypatch `exec()` for ad hoc `QDialog` instances created inline

Production usages:

- `src/product_description_tool/kb_window.py:380` — inline text-editor `QDialog.exec()`
- `src/product_description_tool/kb_window.py:396` — `CsvEditorDialog.exec()`
- `src/product_description_tool/kb_window.py:464` — inline converted-file viewer `QDialog.exec()`
- `src/product_description_tool/main_window.py:468` — `ExportDialog.exec()`
- `src/product_description_tool/main_window.py:503` — `SettingsDialog.exec()`
- `src/product_description_tool/main_window.py:614` — `AttachmentManager.exec()`
- `src/product_description_tool/main_window.py:1154` — `HtmlEditorDialog.exec()`
- `src/product_description_tool/main_window.py:1181` — `FilterDialog.exec()`
- `src/product_description_tool/dialogs.py:1440` — `AddKbAttachmentsDialog.exec()`
- `src/product_description_tool/dialogs.py:1454` — `AddColumnAttachmentsDialog.exec()`

Inline modal dialog construction worth noting:

- `src/product_description_tool/kb_window.py:352` — inline editable `QDialog`
- `src/product_description_tool/kb_window.py:439` — inline read-only viewer `QDialog`

Existing test patterns:

- `tests/test_main_window.py:299` — replaces `HtmlEditorDialog` with `FakeDialog`
- `tests/test_main_window.py:626` — replaces `SettingsDialog` with `FakeSettingsDialog`
- `tests/test_main_window.py:1372-1373` and `1403-1404` — replaces `AttachmentManager`
- `tests/test_kb_window.py:810`, `841`, `859`, `893`, `925`, `1276`, `1310`, `1343` — monkeypatches `QDialog.exec()` for inline modal dialogs
- `tests/test_kb_window.py:985`, `1006` — monkeypatches `CsvEditorDialog.exec()`
- `tests/test_attachments.py:762-889` — tests `AttachmentManager` mostly by operating on the dialog object directly, avoiding nested modal execution

Architectural note: these dialogs carry richer widget state than static dialogs, so a `message_box.py`-style global canned-response wrapper is usually the wrong boundary. If the project wants more consistency here, a small helper such as `dialog_runner.py` could centralize `exec()` calls in future code, but that is optional and lower priority than static dialog wrappers.

### 4. Other standard Qt dialogs searched

No production usages found for:

- `QFontDialog`
- `QColorDialog`
- `QProgressDialog`
- `QErrorMessage`
- `QWizard`
- `QPrintDialog`
- `QPageSetupDialog`

Search result: no matches under `src/product_description_tool/*.py`.

## Coverage and extension recommendation

### Best next step

Extend the current abstraction family with two new modules:

- `src/product_description_tool/file_dialog.py`
- `src/product_description_tool/input_dialog.py`

Each should follow the `message_box.py` contract shape:

- `set_test_mode(enabled: bool)`
- `set_response(method: str, response: ...)`
- `reset()`
- thin public functions mirroring Qt static methods

Then extend `tests/conftest.py` with autouse setup/reset for those wrappers, just as it already does for `message_box.py`.

### Why wrapper modules instead of more fixture monkeypatching?

- keeps production call sites explicit and test-aware
- removes repetitive monkeypatch boilerplate across tests
- gives one stable contract for future dialogs
- avoids patching PySide internals differently in each test module

### What not to over-abstract yet

Do not build a generic wrapper for every `QDialog.exec()` call today. The current codebase uses custom dialog classes and inline modal dialogs with custom widget manipulation; those are better controlled with targeted fakes in tests.

## Additional architectural observation

The repository is currently in a mixed state for message boxes:

- `kb_window.py`, `kb_editor.py`, and `kb_csv_editor.py` use `message_box.py`
- `main_window.py` and `dialogs.py` still contain many direct `QMessageBox` calls

That inconsistency means the global `tests/conftest.py` safety net does not yet protect all message-box usage. If the team continues the wrapper strategy, finishing the `QMessageBox` migration would improve consistency before or alongside new dialog wrappers.
