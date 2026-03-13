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

## Validation Expectations

For most code changes, run:

```bash
QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest
```

For packaging-related changes, also run:

```bash
uv run pyinstaller packaging/product_description_tool.spec
```
