## User request capture

- Add a user-friendly way to attach knowledge-base files to a prompt without inserting `{{@path}}` directly into the prompt text.
- Keep existing `{{@path}}` prompt embedding support unchanged.
- Keep existing `{{column}}` placeholder support unchanged.
- Allow users to treat CSV columns as attachment sources instead of only inline placeholders.
- Attached knowledge-base files and attached columns should be appended to the effective prompt automatically using a clear template that explains they are attachments and where they came from.
- Attachment selection should use a small modal dialog that can return multiple selected attachment sources at once.
- Users must be able to manage attachments: add, remove, and reorder them.
- Avoid cluttering the main window; attachment editing should be delegated to a separate window.
- Do not mix CSV-column and knowledge-base-file selection into one unified picker.
- CSV-column selection should stay a simple dedicated selection flow, such as a dropdown/list specialized for columns.
- Knowledge-base-file selection should use a dedicated simplified knowledge-base explorer, ideally reusing the existing KB browsing concepts in a select-only mode.
- Avoid introducing a virtualized "columns as KB branch/directory" concept because it adds unnecessary complexity.
- By default, KB-file attachments should be placed before CSV-column attachments so the prompt prefix stays more constant.
- Users may still reorder CSV-column attachments above KB-file attachments.
- If any CSV-column attachment is placed above any KB-file attachment, show a small warning that this may increase prompt cost because KB-file content may be reprocessed instead of benefiting from stable-prefix caching.

## Constraints and non-goals

- Do not remove or regress existing inline placeholder behavior for `{{column}}` and `{{@path}}`.
- Keep the main window/prompt editor panel relatively uncluttered.
