# CSV Export Column Ordering Action Register

Scope: CSV export column ordering feature and follow-up fixes.

| ID | Source | Finding | Disposition | Owner | Target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AR-1 | Architect | `export_order` persistence and export flow needed normalization and deduplication so saved ordering remains stable and export columns are not repeated. | fix now | Product Developer | Current feature stream | closed |
| AR-4 | Architect | Persisted `export_order` values are still not canonicalized on load/save; current behavior is acceptable after the follow-up fix, but drift in stored ordering shape should be monitored until a broader persistence cleanup is taken on. | monitor | Architect + Product Developer | Re-evaluate during config persistence cleanup | open |
| AR-2 | Architect | `CsvConfig` currently mixes project-scoped export behavior with app-level persistence concerns; ownership and persistence boundaries should be split more cleanly. | defer | Architect + Product Developer | Follow-up design pass for config boundaries | open |
| AR-3 | Architect | Export-dialog naming and contract surface should be cleaned up so UI terminology and save/export responsibilities are easier to reason about. | defer | Product Developer | Follow-up cleanup after feature stabilization | open |
| QA-1 | QA | CSV defaults needed to stay consistent when persisted config omits values, specifically for `export_only_visible` and delimiter fallback behavior. | fix now | Product Developer | Current feature stream | closed |
| QA-2 | QA | Save/load/export behavior should have stronger integration coverage across persisted config, project reload, and exported column ordering. | monitor | QA Engineer | Add coverage when adjacent export/config work resumes | open |
| QA-3 | QA | Explicit `null` handling remains asymmetric between `export_only_visible` and delimiter persistence; current behavior is acceptable after the CSV default-consistency fix, but should be watched if config-shape cleanup proceeds. | monitor | Architect + QA Engineer | Re-evaluate during config persistence cleanup | open |
