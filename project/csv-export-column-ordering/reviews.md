# CSV Export Column Ordering Reviews

## Architect Review 1 — Feature implementation

- Verdict: acceptable with caveats
- Key findings:
  - `export_order` should be normalized/deduplicated
  - `CsvConfig` ownership/persistence split remains conceptually mixed
  - export-dialog contract naming could be cleaner
  - nearby CSV defaults needed consistency review

## QA Review 1 — Feature regression coverage

- Result: regression coverage added for export ordering and settings behavior
- Focus covered:
  - repository export ordering
  - dialog reorder/reset behavior
  - config round-trip behavior

## Architect Review 2 — Follow-up fixes

- Verdict: approved with caveats
- Closed items:
  - export-time `export_order` normalization/deduplication
  - default consistency for omitted `export_only_visible` and delimiter values
- Remaining caveats:
  - persisted `export_order` is not canonicalized on load/save
  - explicit `null` handling remains asymmetric for `export_only_visible`
