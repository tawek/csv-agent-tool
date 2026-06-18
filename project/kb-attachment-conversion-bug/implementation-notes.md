## Request

- Bug fix: KB attachment selection must not be limited to markdown and csv files.
- The KB attachment picker must show selectable files from the full KB tree, including subdirectories.
- When a selected KB file is not directly readable as markdown/text/csv, the app must convert it on the fly with MarkItDown, cache by content hash, and include the converted markdown in the effective prompt.
- In the KB manager, files that require conversion must expose an in-app view flow for the converted markdown output.

## Non-goals

- No change to project attachment persistence format.
- No change to CSV-column attachment behavior.
