# ODT conversion quality request

- Improve ODT conversion quality for real KB documents; current output is not acceptable.
- Use `sample/kb/shopvibe-overview.odt` as the concrete quality reference.
- Review the upstream MarkItDown ODT converter work in microsoft/markitdown PR #1940 for ideas.
- Preserve meaningful document structure in converted Markdown instead of flattening most content into plain paragraphs.
- Keep the change minimal and local to KB conversion unless broader refactoring is clearly necessary.

## Expected quality targets

- Preserve headings.
- Preserve bullet and numbered list items.
- Preserve table structure.
- Preserve preformatted/code-like blocks when they are represented in the ODT styles.
- Continue returning plain Markdown text suitable for KB preview and prompt embedding.
