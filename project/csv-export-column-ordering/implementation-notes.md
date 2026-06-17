# CSV Export Column Ordering Implementation Notes

- Export order is stored in `CsvConfig.export_order`.
- Export-time normalization now:
  - drops stale configured headers not present in the current document,
  - keeps only the first occurrence of duplicate configured headers,
  - appends remaining current document headers once in document order.
- Missing persisted config values now fall back consistently for:
  - `delimiter` → `;`
  - `export_only_visible` → `True`
- Persisted `export_order` is not yet canonicalized on load/save; normalization currently happens at export time.
