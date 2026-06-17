# KB MarkItDown Conversion Design

## Purpose

Define the minimal architectural extension for adding MarkItDown-backed knowledge-base conversion without changing the existing editable-file workflows described in Use Cases 10, 11, 21, 22, 26, 27, 28, and 29.

## Problem Statement

The current knowledge-base flow only supports directly readable/editable files (`.md`, `.markdown`, `.txt`, `.csv`). The requested extension adds:

- internal viewing of supported non-editable KB files such as PDFs after conversion to Markdown,
- reuse of that converted Markdown for inline KB prompt references and KB-file prompt attachments,
- clear warning/failure behavior when conversion is unavailable, and
- packaged-app support for the conversion dependency without turning KB conversion into a runtime-discovery subsystem.

This must preserve the current project model and the current editable KB behavior.

## Scope and Non-Goals

### In scope

- Local-file conversion to Markdown for KB viewing and prompt use.
- Transparent local cache keyed by source-file hash.
- Packaging plan for MarkItDown as an application dependency.

### Out of scope

- Remote URL conversion.
- Editing converted PDFs/Office files and writing changes back to the source format.
- OCR/plugin/cloud-converter flows.
- Project-file schema changes.

## Architectural Decision Summary

1. Add a dedicated conversion boundary instead of spreading conversion logic across `prompt_renderer.py`, `generation.py`, and `kb_window.py`.
2. Use **direct in-process MarkItDown library calls as the primary backend**, provided the package exposes a stable enough Python API for the required local-file conversions.
3. Keep current direct-read behavior for `.md`, `.markdown`, `.txt`, and `.csv` unchanged.
4. Treat converted files as **view-only** inside the KB manager.
5. Reuse converted Markdown for prompt embedding and KB-file attachments through a shared cache/service.
6. Do not persist any conversion metadata in `.project.json`.

## Primary integration choice: library first

The clarified direction is to keep this feature KISS and treat MarkItDown as a normal Python dependency if viable.

### Decision

Use a project-owned Python service API inside the app, with **direct MarkItDown library usage as the default and preferred execution path**.

### Why this is now preferred

- It matches the user's requested simplification.
- It avoids PATH-vs-bundled runtime ranking logic.
- It keeps packaging aligned with the application's normal Python dependency model.
- It is sufficient for a cacheable local conversion feature unless the package proves unusable in-process.

### Narrow fallback

If implementation evidence shows that MarkItDown's Python API is missing, unstable, or insufficient for the required file types, the app may add a **contained CLI fallback behind the same service boundary**. That fallback is a technical contingency, not the planned architecture.

## Proposed Module Boundary

### New module

`src/product_description_tool/kb_conversion.py` (planned)

Primary responsibilities:

- classify KB files as direct-read vs convertible vs unsupported,
- enforce local-file-only conversion boundaries,
- convert files to Markdown,
- manage cache lookup/write/invalidation,
- expose stable errors/messages to UI and generation layers.

### Proposed public surface

- `KnowledgeBaseContentService`
  - `validate_reference(path, kb_root, purpose)`
  - `load_markdown(path, kb_root, purpose)`
  - `get_view_model(path, kb_root)`
- `ConversionCache`
  - maps `(source_hash, normalized_relative_path, converter_identity)` to cached markdown artifact

`purpose` should distinguish at least:

- `viewer`
- `inline_reference`
- `attachment`

This keeps UI wording purpose-specific while preserving one conversion mechanism.

## Likely Source Touch Points

### `prompt_renderer.py`

- Replace hard-coded KB extension checks with service-based validation.
- Preserve placeholder extraction and path-boundary validation ownership unless that logic is moved wholesale into the content service.

### `generation.py`

- Replace direct `read_text()` behavior for KB placeholders and KB-file attachments with `KnowledgeBaseContentService.load_markdown()`.
- Keep prompt assembly logic in `GenerationService`; do not move prompt ordering or provider orchestration.

### `kb_window.py`

- Preserve editable behavior for `.md`, `.markdown`, `.txt`, `.csv`.
- Add a read-only internal Markdown-view path for convertible files.
- Keep file management and root-boundary enforcement in the KB manager.

### `project.py`

- No schema change recommended.
- Existing attachment metadata remains valid because attachments still point to KB-relative source paths.

### Packaging

- `pyproject.toml`: add MarkItDown as a normal application dependency.
- `packaging/product_description_tool.spec`: no special private-runtime discovery design should be assumed up front; only package adjustments actually required by the dependency should be added.
- `packaging/install.bat`: expected to remain unchanged unless packaging the Python dependency reveals a concrete installer requirement.
- `docs/build-windows.md`: update only if the normal dependency/build workflow needs extra notes for MarkItDown.

## Supported File Model

### Direct-read and editable

- `.md`
- `.markdown`
- `.txt`
- `.csv`

These stay on the current code path.

### Convertible and non-editable

Support should be capability-based, not extension-list-only in the UI contract. Initial implementation should target the high-confidence formats already called for by the request and commonly handled by MarkItDown, especially:

- `.pdf`
- office document formats that the chosen MarkItDown dependency path actually supports
- other local formats only when conversion succeeds

The service should own the allow/deny decision. `kb_window.py` should not embed a large duplicated extension table.

## Cache Design

### Required behavior

- Transparent local cache.
- Keyed by source file hash.
- Automatically invalidated when source content changes.

### Proposed design

Cache location:

- `platformdirs.user_cache_dir("product-description-tool")/kb-markitdown/`

Cache key inputs:

- `sha256(source bytes)`
- normalized source suffix
- converter identity (`backend kind + MarkItDown version`)

Artifact layout:

- `<cache-key>.md`
- optional sibling metadata JSON with source path, source size, mtime observed, converter identity, and creation timestamp

### Rationale

The user requested source-hash invalidation. Including converter identity in the key remains useful to avoid stale output reuse if the packaged MarkItDown dependency changes across app versions, even when the integration is in-process.

## Packaging and Distribution Strategy

### Decision

Treat MarkItDown as part of the application's Python dependency set first.

### Packaging intent

- Source/dev runs should work from the active project environment once the dependency is installed.
- Packaged desktop builds should carry whatever MarkItDown library files PyInstaller must include for the app's in-process conversion path to work.
- Do not add separate PATH probing, launcher heuristics, or private sidecar runtime layouts unless packaging or API limitations force that complexity.

## Security and Robustness Constraints

1. Convert **local files only** from KB-managed paths.
2. Do not pass remote URLs to MarkItDown.
3. Disable plugins by default.
4. Do not enable OCR/cloud/document-intelligence modes for this feature.
5. If a CLI fallback becomes necessary, invoke subprocesses with argument lists, never through shell interpolation.
6. Enforce KB-root path validation before conversion.
7. Apply clear failure reporting; add timeout and stderr capture if a subprocess fallback becomes necessary.
8. Treat empty or obviously invalid conversion output as failure for prompt-use purposes.
9. Keep converted output read-only in the UI for non-editable sources.

These constraints align with MarkItDown's own warning that it performs I/O with the privileges of the current process.

## Failure Behavior

### Prompt embedding / attachments

- Validation failure is blocking.
- The app should warn that the specific KB file cannot be included because conversion is unavailable or failed.
- The run should not proceed with that file silently omitted.

### KB internal viewing

- Viewing failure is local to the file open action.
- Show an actionable error and keep external-open available.

## Minimal-Extension Rule

To preserve current KB behavior:

- keep existing modal text and CSV editors unchanged,
- do not rewrite project persistence,
- do not change attachment ordering semantics,
- add conversion only through a shared service consumed by existing flows.

This is intentionally a refactor-light extension, not a KB subsystem rewrite.

## Parallelization and Ownership

Safe sequencing for downstream work:

1. **Serial first:** spec + architecture artifacts.
2. **Serial implementation lane in `src/product_description_tool/`:** one developer, because `generation.py`, `prompt_renderer.py`, `kb_window.py`, and likely `main_window.py` share one ownership scope.
3. **Parallel after contracts stabilize:** packaging/doc updates and QA test design can proceed alongside late implementation.

No true parallel code-writing lanes are recommended inside `src/product_description_tool/` for this change.

## Open Questions

1. Does the installed MarkItDown package expose a stable direct Python API suitable for file-to-Markdown conversion in this app?
2. Which exact non-text extensions should the first release advertise explicitly in the file picker versus leaving capability-discovered?
3. Is a separate read-only viewer dialog preferable to reusing the existing markdown editor widget in read-only mode?
4. What timeout/output-size guardrails are appropriate for very large PDFs or office documents?

## Recommendation to Implementers

Start with the shared conversion service using direct MarkItDown imports. Then wire that service into prompt validation/rendering and KB viewing. Keep persistence untouched unless implementation evidence proves otherwise. Add a CLI fallback only if the package API or packaging path proves insufficient.
