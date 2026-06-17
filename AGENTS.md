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

## Workflow: Spec-First Execution

### Golden Rule

Follow the spec-first workflow for any feature, bug fix, or behavior change. Keep the user informed with concise progress updates, but do not require mandatory approval gates between spec, implementation, commit, and push unless the user explicitly asks for review pauses.

### Workflow Steps

#### Step 1: Update the Spec

**Entry criteria:** A feature request, bug report, or behavior change has been identified. No code has been written yet.

1. **Understand the change.** Determine whether this is a new feature, a modification to existing behavior, or a bug fix.
2. **Update `docs/specification.md`** to describe the correct expected behavior:
   - For new features: add a Use Case section describing the actor, trigger, flow, and invariants.
   - For bug fixes: update the relevant Use Case to describe the *correct* behavior.
   - For behavior modifications: update the affected Use Case(s).
3. **Present or summarize the spec changes** to the user before or alongside implementation work, depending on the task flow. Do not skip the spec update when one is required.

#### Step 2: Implement

**Entry criteria:** The relevant spec update has been made when required, or the change is confirmed to be implementation-only.

1. **Make the minimum changes** needed to satisfy the spec. Follow existing patterns and conventions.
2. **Write or update tests.** Cover the new or modified behavior, especially in `tests/test_main_window.py`.
3. **Run validation:**
    ```bash
    QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest
    ```
4. **Track review follow-ups explicitly.** When QA, Architect, or another specialist reports findings, record them in an action register and assign each one a disposition: fix now, defer, reject, or monitor. Do not treat the review as closed until every finding has a disposition.
5. **Show or summarize the code changes** and test results to the user. Reference the Use Case numbers and spec sections the implementation satisfies, and include any open or deferred follow-up items.

#### Action Register Procedure

When a review produces findings, maintain an **Action Register** with one entry per finding.

**Where to record it:**
- In the live session `todowrite` list for execution tracking.
- In a git-tracked per-feature workspace at `project/<feature>/`, with at least an `action-register.md` file.
- In the user-facing update/final report under a dedicated **Action Register** heading.

**Scoping rule:**
- Do not keep a single long-lived root `TODO.md` for all work.
- Prefer one workspace per feature, sprint, or review stream so records remain scoped and reviewable in git.

**Recommended workspace contents:**
- `action-register.md` — required review findings and dispositions
- `reviews.md` — architect/QA review summaries and decisions
- `implementation-notes.md` — technical notes, follow-up rationale, and handoff context
- `status.md` — current state, next steps, and closure summary

**Required entry format:**
- **ID** — short stable identifier such as `AR-1`, `QA-2`
- **Source** — Architect, QA, Problem Solver, etc.
- **Finding** — concise description of the issue or recommendation
- **Disposition** — exactly one of: `fix now`, `defer`, `reject`, `monitor`
- **Owner** — who is responsible for the next step
- **Target** — current task, follow-up task, or later milestone
- **Status** — `open`, `in_progress`, `closed`

**Closure rule:**
- A review is not closed until every finding has a disposition.
- The task is not reported complete while any `fix now` item remains open.
- Deferred or rejected items must include a short rationale in the user report.

#### Step 3: Commit

**Entry criteria:** The implementation is complete, validated, and ready to record in version control.

1. Stage `docs/specification.md` and create the spec commit. Message should reference the Use Case number(s).
2. Stage all code and test changes. Create the implementation commit. Message should reference the Use Case number(s) and note they follow the approved spec update.
3. **Never combine spec and implementation in a single commit.**

#### Step 4: Push

**Entry criteria:** The relevant commits are complete and ready to publish.

1. Push when the task calls for updating the remote repository.
2. Report the push result to the user, including any relevant branch or remote details.

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

If unsure whether something needs a spec change, prefer clarifying with the user.

### Bug Fix Variant

For bug fixes:
1. Update the spec to describe the *correct* behavior.
2. Present or summarize the spec change for the user.
3. Implement the fix to match the updated spec.
4. Add regression tests if appropriate.
5. Show or summarize the implementation and validation results.
6. Commit and push according to the normal workflow when the task calls for it.

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

## Architectural Review Gate

When source code changes are architecturally significant, require a post-implementation review by `@code-architect` before the final user report.

Architect review is required when any of the following apply:
- The implementation spans multiple source modules in `src/product_description_tool/`.
- The change alters shared interfaces or contracts, including signals, provider contracts, config serialization, project-file shapes, or other persisted data shapes.
- The change follows a spec update for a feature, bug fix, or behavior modification.

Architect review is usually not required for a trivial isolated change that stays within one module and does not affect shared contracts, persisted shapes, or specified behavior.

When required:
1. Implement and validate the change first.
2. Have `@code-architect` review the resulting code and any related spec or architecture artifacts for architectural fit and contract consistency.
3. Record the architect's findings in the action register and assign each one a disposition.
4. Resolve any architect feedback that is not explicitly deferred or rejected with rationale before final user reporting.
5. Do not present the work as complete to the user until that review gate has passed.

## OpenCode Agent Configuration

Agents are configured in `.opencode/agents/`. Each agent is self-contained with
project-specific knowledge embedded in its system prompt.

### Agent Files

| File | Role | Model | Reasoning |
|------|------|-------|-----------|
| `leader.md` | Team Lead and Team Config Maintainer | `openai/gpt-5.4` | low |
| `problem-solver.md` | Problem Solver | `openai/gpt-5.4` | high |
| `code-architect.md` | Code Architect | `openai/gpt-5.4` | high |
| `product-developer.md` | Product Developer (Senior) | `opencode/deepseek-v4-flash-free` | — |
| `product-developer-junior.md` | Product Developer (Junior) | `llamacpp/qwen3.6-35b-a3b` | — |
| `qa-engineer.md` | QA Engineer (Senior) | `opencode/deepseek-v4-flash-free` | — |
| `code-explorer.md` | Code Explorer | `opencode/deepseek-v4-flash-free` | — |

### Usage

- **Primary agent**: `leader`
- **Specialists**: `@product-developer`, `@product-developer-junior`, `@qa-engineer`, `@code-explorer`, `@problem-solver`, `@code-architect`

The `leader` agent has direct authority to define and maintain team coordination rules and agent configuration in `AGENTS.md` and files under `.opencode/agents/`, and may edit those files directly. In normal operation, the leader should still delegate application code, specs, and tests to the appropriate specialists rather than taking on that product work personally.

### Persistent Outputs

- **Specs and docs**: `docs/` (specification, project model, architecture, QA reports)
- **Architecture docs**: `docs/architecture/<prefix>-*.md`
- **QA reports**: `docs/qa/<prefix>-*.md`
- **Feature workspaces**: `project/<feature>/` containing scoped planning and review artifacts such as `action-register.md`, `reviews.md`, `implementation-notes.md`, and `status.md`

### Parallel Work Limits

- `src/product_description_tool/` is a single shared implementation scope. Only one code-writing agent may edit it at a time.
- `tests/` is a separate QA-owned scope. QA can work in parallel only after the intended behavior and any source-facing contracts are stable enough to test.
- `docs/specification.md` and `docs/architecture/` are contract-defining artifacts. When a task changes behavior or shared interfaces, those artifacts must be updated before downstream implementation work starts.
- Architecturally significant source changes require a post-implementation `@code-architect` review before final user reporting.
- If future work requires true parallel implementation lanes, refactor the source tree first into separately ownable directories or packages.

### Permission Summary

| Agent | read | edit | bash | task |
|-------|------|------|------|------|
| Leader | allow (`AGENTS.md`, `.opencode/agents/`) for direct team-rule and agent-configuration maintenance | allow (`AGENTS.md`, `.opencode/agents/`) for direct team-rule and agent-configuration maintenance | allow | `*`: allow |
| Problem Solver | allow | deny | allow | deny |
| Code Architect | allow | allow (`docs/specification.md`, `docs/architecture/`) | allow | deny |
| Product Developer | allow | allow (`src/product_description_tool/`, `packaging/`) | allow | deny |
| Product Developer (Junior) | allow | allow (`src/product_description_tool/`, `packaging/`) | allow | deny |
| QA Engineer | allow | allow (tests/) | allow | deny |
| Code Explorer | allow | deny | allow | deny |
