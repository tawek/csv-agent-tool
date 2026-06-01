# Product Description Tool

Desktop batch editor for loading CSV files, rewriting product descriptions with an LLM, previewing HTML output, and saving processed CSV data.

## Documentation

Capability-specific documentation lives in `docs/`.

- `docs/project.md`: explains the application's project model, persistence layout, and processing lifecycle

Add more focused technical documentation there as the codebase grows instead of expanding the README with implementation detail.

## Run from source

```bash
uv sync --extra dev
uv run product-description-tool
```

## Package

### Local build (Linux)

```bash
uv run pyinstaller packaging/product_description_tool.spec
```

### Windows build

See `docs/build-windows.md` for the procedure to build a Windows executable using the remote Windows machine. The process involves SSH access to the remote machine, setting up a build environment, and running PyInstaller there.
