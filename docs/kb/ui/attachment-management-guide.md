# Attachment Management UI Guide

## Purpose

Capture the intended UX principles for prompt attachments.

## Guidance

- Keep prompt text authoring separate from attachment management.
- Use a dedicated attachment-management surface rather than cluttering the main prompt editor.
- Keep knowledge-base file selection and CSV-column selection as separate flows.
- Prefer reuse of existing knowledge-base browsing concepts for KB-file selection in a select-only mode.
- Keep CSV-column selection simple and specialized rather than virtualizing columns into a file tree.

## Ordering guidance

- Default KB-file attachments before CSV-column attachments.
- Allow manual reordering.
- If a CSV-column attachment is moved above KB-file attachments, show a subtle warning that this may increase prompt cost because stable-prefix caching is less likely to help.
