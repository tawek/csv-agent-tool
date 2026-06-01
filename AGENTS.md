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
- `docs/build-windows.md`: complete procedure for building Windows executables via SSH remote machine.

When a feature needs deeper explanation than a short README note, add or extend a focused document under `docs/`.

## Working Rules

- Prefer `uv run ...` for all local commands.
- Keep GUI-related changes covered by tests where possible, especially in `tests/test_main_window.py`.
- Preserve headless test behavior. The suite expects `QT_QPA_PLATFORM=offscreen` and `PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1`.
- Treat `build/`, `dist/`, `*.egg-info/`, `__pycache__/`, and `.pytest_cache/` as generated artifacts. Do not edit them.
- Keep project file compatibility stable. `project.py` writes `.project.json` files plus prompt sidecars, and `config.py` serializes specific JSON keys.
- Provider changes should preserve streaming and cancellation behavior for both Ollama and OpenAI-compatible endpoints.
- When changing prompt rendering or CSV field handling, verify both persistence and UI-selection flows because `MainWindow` ties them together tightly.

## Workflow: Spec-First, No Commits or Pushes Without Approval

### Golden Rule

**NEVER commit code or push to remote without explicit user approval.** This is the single most important rule. Violating this is a critical failure.

### Explicit Approval Definition

**Explicit approval** means the user says one of:
- "yes"
- "approved"
- "looks good"
- "go ahead"
- "commit" (only when asked about committing)
- "push" (only when asked about pushing)

**These do NOT count as approval:**
- "run" — this means execute the tool
- "go" — this means proceed with execution
- "continue" — this means continue the current operation
- "fix it" — this means fix the problem, not approve changes
- "try" / "test" / "show" — any command that could mean "execute"
- Silence or ambiguity — if unsure, ask

When in doubt, **always ask**.

### Approval Gates

You must stop and ask for approval at each phase boundary. **Never proceed without explicit approval.**

1. **After spec update:** Ask **"Does this spec change look correct? Shall I proceed to implementation?"**
2. **After implementation:** Ask **"Does the implementation look correct? Shall I commit?"**
3. **After commit:** Ask **"Shall I push?"** — only push when the user explicitly says "yes" to pushing.

### Workflow Steps

#### Step 1: Update the Spec

**Entry criteria:** A feature request, bug report, or behavior change has been identified. No code has been written yet.

1. **Understand the change.** Determine whether this is a new feature, a modification to existing behavior, or a bug fix.
2. **Update `docs/specification.md`** to describe the correct expected behavior:
   - For new features: add a Use Case section describing the actor, trigger, flow, and invariants.
   - For bug fixes: update the relevant Use Case to describe the *correct* behavior.
   - For behavior modifications: update the affected Use Case(s).
3. **Present the spec changes** to the user. Do not write any code. Do not commit anything.
4. **Ask for approval.** Present the spec and ask: **"Does this spec change look correct? Shall I proceed to implementation?"**
5. **Wait for explicit approval.** Do not proceed until the user says "yes", "approved", "looks good", or similar.

#### Step 2: Implement (After Spec Approval)

**Entry criteria:** The user has explicitly approved the spec change.

1. **Make the minimum changes** needed to satisfy the spec. Follow existing patterns and conventions.
2. **Write or update tests.** Cover the new or modified behavior, especially in `tests/test_main_window.py`.
3. **Run validation:**
    ```bash
    QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest
    ```
4. **Show the code changes** and test results to the user. Reference the Use Case numbers and spec sections the implementation satisfies.
5. **Ask for commit approval.** Present the changes and ask: **"Does the implementation look correct? Shall I commit?"**
6. **Wait for explicit approval.** Do not commit until the user says "yes", "commit", "approved", or similar.

#### Step 3: Commit (After Commit Approval)

**Entry criteria:** The user has explicitly approved the commit.

1. Stage `docs/specification.md` and create the spec commit. Message should reference the Use Case number(s).
2. Stage all code and test changes. Create the implementation commit. Message should reference the Use Case number(s) and note they follow the approved spec update.
3. **Never combine spec and implementation in a single commit.**

#### Step 4: Push (After Explicit Push Approval)

**Entry criteria:** The user has explicitly approved the push.

1. **Only push when the user explicitly says "push" or "yes" to a push question.**
2. If the user has not been asked about pushing, ask: **"Shall I push?"**
3. **Never push without this explicit approval.**

### What Counts as a Spec Change

Only the following require a spec update:
- New features
- Bug fixes (describing the correct behavior)
- Behavior modifications

**These do NOT require a spec update:**
- Typos in documentation
- Cosmetic changes already covered by existing specs
- Changes to implementation details that don't affect external behavior
- Adding or removing comments
- Refactoring internal code structure

If unsure whether something needs a spec change, **ask the user**.

### Bug Fix Variant

For bug fixes:
1. Update the spec to describe the *correct* behavior.
2. Present the spec to the user and ask for approval.
3. Implement the fix to match the approved spec.
4. Add regression tests if appropriate.
5. Show the implementation and ask for commit approval.
6. Only commit and push after explicit approval.

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
