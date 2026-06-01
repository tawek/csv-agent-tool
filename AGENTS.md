# AGENTS.md

## Project Summary

This repository contains a desktop batch editor for rewriting product descriptions from CSV data with either a local Ollama backend or an OpenAI-compatible endpoint. The app is a PySide6 GUI launched from `src/product_description_tool/__main__.py`.

## Environment

- Python: `>=3.14`
- Package manager: `uv`
- GUI toolkit: `PySide6`
- Test stack: `pytest`, `pytest-qt`

Install dependencies with:

```bash
uv sync --extra dev
```

## Common Commands

Run the app from source:

```bash
uv run product-description-tool
```

Run the test suite headlessly:

```bash
QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest
```

Build the packaged desktop app:

```bash
uv run pyinstaller packaging/product_description_tool.spec
```

## Repository Map

- `src/product_description_tool/app.py`: creates `QApplication`, loads config, opens the main window.
- `src/product_description_tool/main_window.py`: main UI orchestration, menu actions, CSV/project workflows, previews, and batch processing control.
- `src/product_description_tool/config.py`: dataclass-based app and CSV config models plus persistent config storage under the user config directory.
- `src/product_description_tool/project.py`: `.project.json` persistence and prompt sidecar file handling.
- `src/product_description_tool/csv_repository.py`: CSV load/save behavior and column management.
- `src/product_description_tool/generation.py`: prompt preparation and row-processing orchestration.
- `src/product_description_tool/providers.py`: Ollama and OpenAI-compatible streaming provider implementations.
- `src/product_description_tool/worker.py`: background generation worker used by the GUI thread.
- `src/product_description_tool/dialogs.py`: settings, filters, activity log, and HTML editor dialogs.
- `src/product_description_tool/preview.py`, `highlighter.py`, `filter_proxy.py`, `table_model.py`, `collapsible_panel.py`: UI support components.
- `tests/`: pytest coverage for CSV I/O, dialogs, proxy filtering, project persistence, providers, prompt rendering, and main-window behavior.
- `packaging/product_description_tool.spec`: PyInstaller entry for desktop builds.

## Documentation Layout

- `README.md`: short project overview, setup, and top-level entry points.
- `docs/`: capability-specific documentation for future agents and maintainers.
- `docs/project.md`: current reference for the application project model and lifecycle.

When a feature needs deeper explanation than a short README note, add or extend a focused document under `docs/`.

## Working Rules

- Prefer `uv run ...` for all local commands.
- Keep GUI-related changes covered by tests where possible, especially in `tests/test_main_window.py`.
- Preserve headless test behavior. The suite expects `QT_QPA_PLATFORM=offscreen` and `PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1`.
- Treat `build/`, `dist/`, `*.egg-info/`, `__pycache__/`, and `.pytest_cache/` as generated artifacts. Do not edit them.
- Keep project file compatibility stable. `project.py` writes `.project.json` files plus prompt sidecars, and `config.py` serializes specific JSON keys.
- Provider changes should preserve streaming and cancellation behavior for both Ollama and OpenAI-compatible endpoints.
- When changing prompt rendering or CSV field handling, verify both persistence and UI-selection flows because `MainWindow` ties them together tightly.

## Workflow: Spec-First, Two-Phase Commits

All changes follow a strict two-phase workflow with explicit review gates. **Never skip the spec update step or combine spec and implementation into a single commit.**

### Approval Gates

At each phase boundary, you must stop and ask the user for explicit approval before proceeding. Never assume consent — always ask.

- After Phase 1: ask **"Does this spec change look correct? Shall I proceed to planning?"**
- After Phase 2: ask **"Does this plan look correct? Shall I proceed to implementation?"**
- After Phase 3: ask **"Does the implementation look correct? Shall I commit?"**

### Phase 1: Spec Change (Write First)

**Entry criteria:** A new feature request, bug report, or behavior modification has been identified. No code has been written yet.

**Flow:**

1. **Understand the change.** Determine whether this is a new feature, a modification to existing behavior, or a bug fix.
2. **Update `docs/specification.md`.**
   - For new features: add a new Use Case section (numbered sequentially) describing the actor, trigger, preconditions, flow, postconditions, invariants, and error conditions.
   - For bug fixes: update the relevant Use Case to describe the *correct* expected behavior (not the buggy current behavior). Add an "Error conditions" section if one is missing.
   - For behavior modifications: update the affected Use Case(s) and any impacted invariants or data flow descriptions.
3. **Commit the spec.** Stage `docs/specification.md` and create a commit. Message should reference the Use Case number(s) being added or modified.
4. **Present the spec changes.** Clearly describe what the spec change says and why. Do not write any code.
5. **Ask the user for approval.** Present the spec to the user and ask: **"Does this spec change look correct? Shall I proceed to planning?"**

**Exit criteria:** The user has explicitly approved the spec change. The spec commit exists. No implementation code has been written.

### Phase 2: Planning (Before Any Code)

**This step is mandatory. Never skip planning.** A good plan must contain all of the following:

1. **Spec traceability.** List every Use Case section and flow step that this implementation must satisfy. Reference specific line numbers or descriptions in the spec.
2. **Affected modules.** Enumerate every file that will be read or written, with a one-line reason for each change.
3. **New classes or methods.** Describe each new function, method, or class — its name, signature, purpose, and which flow step it fulfills.
4. **Existing code modifications.** List every existing method that will be changed, what the change is, and why.
5. **Test plan.** Identify which tests need to be written or updated, referencing the behavior they will cover.
6. **Backward compatibility.** Note any data format changes (e.g., new config keys, new project JSON fields) and whether existing files will still load correctly.
7. **Dependencies and ordering.** Specify which changes must happen before others (e.g., data models before UI, imports before usage).

**Flow:**

1. Present the plan to the user as a structured list or todo-style output.
2. Do not write any code during planning.
3. **Ask the user for approval.** Present the plan to the user and ask: **"Does this plan look correct? Shall I proceed to implementation?"**

**Exit criteria:** The user has explicitly approved the plan. No code has been written yet.

### Phase 3: Implementation (After Plan Approval)

**Entry criteria:** The implementation plan has been reviewed and explicitly approved by the user.

**Flow:**

4. **Implement the code in the order specified by the plan.** Make the minimum changes needed to satisfy the spec. Follow existing patterns and conventions.
5. **Write or update tests.** Cover the new or modified behavior, especially in `tests/test_main_window.py` for UI flows.
6. **Run validation.** Execute the test suite:
    ```bash
    QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest
    ```
    For packaging changes, also run PyInstaller.
7. **Submit the implementation for review.** Show the code changes, tests, and test results. Reference the Use Case numbers and flow steps the implementation satisfies.
8. **Ask the user for approval.** Present the implementation to the user and ask: **"Does the implementation look correct? Shall I commit?"**

**Exit criteria:** The user has explicitly approved the implementation. The implementation commit is ready.

### Commit Discipline

- **Commit 1:** Spec-only changes (`docs/specification.md`). Message should reference the Use Case number(s) being added or modified.
- **Commit 2:** Implementation changes (code + tests). Message should reference the same Use Case number(s) and note that they follow the approved spec update.
- **Never** put spec and implementation in the same commit unless explicitly instructed (e.g., for emergency hotfixes with no review path).

### Bug Fix Variant

For bug fixes, the workflow is:

1. Update the spec to describe the *correct* behavior (not the buggy behavior).
2. Review and commit the spec update.
3. Present the implementation plan and **ask for user approval** before writing any code.
4. Implement the fix to match the approved plan.
5. Add regression tests if appropriate.
6. Review and commit the implementation.

This ensures the spec always reflects the desired behavior, not whatever is currently broken.

## Validation Expectations

For most code changes, run:

```bash
QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest
```

For packaging-related changes, also run:

```bash
uv run pyinstaller packaging/product_description_tool.spec
```
