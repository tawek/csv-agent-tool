# KB MarkItDown support request

- Extend existing knowledge-base capabilities; do not overhaul the KB feature set.
- Add support for PDF and other non-Markdown/plain-text files in the knowledge base.
- KB explorer/manager should not edit converted documents; it may only view them through the internal Markdown viewer after converting the source document to Markdown.
- Prefer integrating MarkItDown as a library dependency of this project if possible.
- Only fall back to CLI-style invocation if direct library use proves technically necessary.
- When a file requiring conversion is used for prompt embedding or as an attachment, the app should warn if no working conversion tool is available; in that case the file must not be included because it cannot be converted to Markdown.
- Conversion should create a local cached Markdown artifact keyed by the source file hash.
- Cached Markdown should be reused transparently for embeddings and attachments.
- When the source file changes, the cached conversion must be regenerated.
- If packaging guidance is needed, keep it aligned with shipping MarkItDown as a normal Python dependency of the application rather than as a separately discovered tool runtime.

## User correction / simplification

- Treat MarkItDown as a normal Python dependency if that is viable.
- Disregard the earlier executable-bundling and local-PATH-preference ideas if the package can simply be bundled with the application as a Python library dependency.
- Prefer a KISS design over runtime tool discovery heuristics.
- Avoid Node.js/Ruby-style external-tool assumptions unless MarkItDown actually requires them.

## Explicit unknowns to resolve

- Whether the MarkItDown package exposes a stable enough Python API for the needed conversions in this app.
- What file types it supports well enough for KB viewing, embedding, and attachments.
- Whether any technically required CLI fallback should be hidden entirely behind an internal Python service boundary.

## Packaging follow-up (2026-06-17)

- User requested verification that PDF conversion really works in the dev environment and in packaged builds.
- Current state before this follow-up: the project depends on plain `markitdown`, which leaves optional converters like PDF support unavailable unless extras were installed manually.
- Required change: depend on the full local converter extra set the app can actually ship (`docx`, `outlook`, `pdf`, `pptx`, `xls`, `xlsx`) so the app and build environment install the optional converter stack without the unsatisfied cloud-preview extras pulled by `markitdown[all]`.
- Required change: ensure the PyInstaller spec explicitly carries MarkItDown runtime pieces needed by packaged builds, including MarkItDown submodules and `magika` model data.
