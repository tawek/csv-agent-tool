# Test-time modal dialog blocking risk analysis

## Scope
Reviewed `tests/conftest.py`, `tests/test_main_window.py`, `tests/test_dialogs.py`, `tests/test_kb_window.py`, `tests/test_kb_csv_editor.py`, `tests/test_kb_editor.py`, plus modal-dialog call sites in `src/product_description_tool/`.

## Root cause
**Highest-likelihood root cause:** the suite has **no shared non-blocking `QMessageBox` fixture**. `tests/conftest.py` only sets environment variables (`tests/conftest.py:1-4`). As a result, most protection is **ad hoc and file-local**. If a test accidentally reaches an unpatched warning/critical/question path, Qt can open a real modal dialog and stall headless CI.

Post-fix note: the knowledge-base viewer hang showed a second failure mode. Even with message boxes neutralized, a cache hit can bypass the unavailable-conversion branch and let a modal `QDialog.exec()` path remain live. That means cache isolation is part of the prevention story for GUI tests that depend on a specific conversion outcome.

### Evidence
- `tests/conftest.py:1-4` contains only env setup; no dialog stubs.
- `tests/test_main_window.py:205-214` has the only autouse dialog patch, but it covers just `main_window.QMessageBox.warning` and only returns `Discard` for the **"Unsaved changes"** title.
- Other files rely on per-test monkeypatches only when the author anticipated a specific modal path.

## (1) Where modal dialogs are already stubbed vs. not stubbed

### Already stubbed
- **`tests/test_main_window.py`**
  - Local autouse unsaved-changes warning stub: `205-214`.
  - Specific question stub for large-run confirmation: `583-586`.
  - Specific critical stubs/captures: `731-736`, `1187-1192`, `1247-1252`.
  - Specific file-dialog stubs: `229-232`, `282-285`, `1157-1164`.
- **`tests/test_kb_window.py`**
  - Information stub: `228-232`.
  - Question stubs: `325-329`, `346-349`, `369-372`, `651-655`, `736-739`.
  - Critical stubs: `490-494`, `516-520`, `539-543`, `571-575`, `640-644`, `1083-1087`.
  - `QDialog.exec` interception for embedded editors: `805`, `836`, `854`, `888`, `920`, plus CSV editor exec stubs `980`, `1001`.
  - `QFileDialog` / `QInputDialog` stubs at many call sites, e.g. `90-94`, `116-120`, `261-264`, `302-305`, `579-582`, `616-619`, `685-688`, `715-718`.
- **`tests/test_kb_csv_editor.py`**
  - Critical stub for unreadable file: `152-155`.
  - Information stubs: `252-256`, `369-373`.
  - Warning stub: `317-321`.
  - Question stubs: `344-347`, `390-393`, `507-510`.
  - `QInputDialog` stubs: `278-282`, `298-302`, `322-326`, `530-534`.
- **`tests/test_kb_editor.py`**
  - Warning stub for `open_external()` failure: `130-134`.
- **`tests/test_dialogs.py`**
  - Only `QFileDialog.getSaveFileName` is stubbed: `290-293`.

### Not stubbed / only partially stubbed
- **Global/shared level:** no suite-wide `QMessageBox` protection at all (`tests/conftest.py:1-4`).
- **`tests/test_main_window.py`**
  - Most direct calls to `preview_selected_row()`, `process_all_rows()`, `edit_selected_description()`, `open_settings()`, `new_project()`, `open_project()` run without a shared catch-all for unexpected warnings/criticals/questions.
  - The autouse patch does **not** cover `QMessageBox.critical`, `information`, `question`, or non-"Unsaved changes" warnings.
- **`tests/test_dialogs.py`**
  - No protection for `SettingsDialog` message boxes in `dialogs.py:518-534` and `774-775`.
  - No protection for `ExportDialog` message boxes in `dialogs.py:893-910`.
- **`tests/test_kb_window.py` / `tests/test_kb_csv_editor.py`**
  - Many expected modal paths are patched, but there is still no fallback if a different error path is hit.

## (2) Likely hang/timeout hotspots

### 1. `MainWindow` flow tests — highest risk
**Why:** many tests call flow methods directly, but only one narrow warning title is auto-stubbed.

Hot source sites:
- `src/product_description_tool/main_window.py:728-835` — preview/process precondition warnings and validation criticals.
- `src/product_description_tool/main_window.py:964-971` — generation failure critical.
- `src/product_description_tool/main_window.py:1134-1149` — edit flow warnings and modal editor.
- `src/product_description_tool/main_window.py:1526-1555` — unsaved-changes / close-event warnings.
- `src/product_description_tool/main_window.py:384`, `411`, `433`, `482` — open/save/import/export failure criticals.

Most exposed current tests:
- `tests/test_main_window.py:324`, `353`, `373`, `447`, `501`, `527`, `554`, `603`, `618`, `634`, `671`, `738`, `1133`, `1166`.

Interpretation: these tests are stable only while setup remains perfect. A small regression that changes selection, prompt state, validation state, or teardown behavior can turn into a blocking modal instead of a clean assertion failure.

### 2. Dialog-unit tests for `SettingsDialog` / `ExportDialog` — medium-high risk
Hot source sites:
- `src/product_description_tool/dialogs.py:518-534` — refresh-model warning/information.
- `src/product_description_tool/dialogs.py:774-775` — invalid-settings critical.
- `src/product_description_tool/dialogs.py:893-910` — export validation warning/question.

Current gap:
- `tests/test_dialogs.py` has no `QMessageBox` fixture and mostly exercises happy paths. As soon as negative-path tests are added, this file is a direct hang candidate.

### 3. Knowledge-base manager tests — medium risk
Hot source sites:
- `src/product_description_tool/kb_window.py:264-496`.

Why medium, not highest:
- This file has many targeted stubs already.
- But filesystem-heavy tests still lack a shared fallback for unexpected critical/warning paths such as read/write failures (`320-365`, `414-418`, `449-496`).
- Some branches are cache-sensitive. If the cache is warm, the test may not exercise the modal path it intends to cover.

### 4. CSV editor tests — medium risk
Hot source sites:
- `src/product_description_tool/kb_csv_editor.py:93-98`, `192-195`, `218-223`, `235-253`, `291-296`.

Why medium:
- Negative-path tests already patch anticipated dialogs.
- Still no fallback if a different save/load/selection path misfires.

## (3) Smallest effective test-infrastructure fix strategy

### Recommended minimal fix
Add a **single autouse fixture in `tests/conftest.py`** that monkeypatches:
- `QMessageBox.information`
- `QMessageBox.warning`
- `QMessageBox.critical`
- `QMessageBox.question`

Default behavior should be deterministic and non-blocking, e.g.:
- `information` / `warning` / `critical` -> return `QMessageBox.StandardButton.Ok`
- `question` -> return `QMessageBox.StandardButton.No`

### Why this is the smallest effective fix
- It addresses the **actual shared gap** instead of patching dozens of tests.
- Existing tests that need a different answer (`Yes`, `Discard`, captured text, etc.) can keep overriding the shared default with local `monkeypatch.setattr(...)` exactly as they already do.
- It avoids touching application code.

### Nice-to-have follow-up
Expose the fixture as a lightweight recorder/spies helper so tests can assert title/text without reimplementing capture lambdas. But that is optional; the autouse no-block fixture is the key fix.

## (4) Test files to update first

1. **`tests/conftest.py`** — first priority
   - Root shared fix location.
   - Current file has no modal protection at all.

2. **`tests/test_main_window.py`** — second priority
   - Remove reliance on the title-specific warning-only autouse patch (`205-214`) in favor of the shared fixture.
   - Keep local overrides only where button choice matters.

3. **`tests/test_dialogs.py`** — third priority
   - Most obvious remaining gap: dialog-focused tests without any `QMessageBox` safety net.
   - Add/adjust negative-path coverage once shared fixture exists.

4. **`tests/test_kb_window.py`** — fourth priority
   - Retain current targeted assertions, but let the shared fixture catch unexpected modal paths.

5. **`tests/test_kb_csv_editor.py`** — fifth priority
   - Same rationale as KB window; mostly good local coverage, missing only shared fallback.

## Ranked hypotheses
1. **Most likely:** missing suite-wide `QMessageBox` stub is the main timeout risk. Evidence: `tests/conftest.py:1-4` and heavy per-test patching elsewhere.
2. **Likely contributing factor:** `test_main_window.py`'s local autouse fixture is too narrow (`205-214`), so many other modal paths remain live.
3. **Less likely but real:** file-dialog / input-dialog blocking can still happen in future tests, but current repository has better local coverage there than for message boxes.

## Developer handoff
- **Primary change location:** `tests/conftest.py`
- **First cleanup consumer:** `tests/test_main_window.py:205-214`
- **Most important source hotspots to keep in mind while updating tests:**
  - `src/product_description_tool/main_window.py:728-835, 964-971, 1526-1555`
  - `src/product_description_tool/dialogs.py:518-534, 774-775, 893-910`
  - `src/product_description_tool/kb_window.py:264-496`
  - `src/product_description_tool/kb_csv_editor.py:93-98, 192-195, 218-223, 235-253, 291-296`
