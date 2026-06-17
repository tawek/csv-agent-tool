# Request: CSV reopen import settings blocker

- Recent CSV heuristics broke project reopen.
- The CSV settings used during first file import are not being persisted.
- On project reopen, those settings are effectively treated as required, causing reopen failure.
- User clarification supersedes earlier options:
  - the user should not need to care about import CSV format details,
  - the project's working CSV should remain in the same format as originally imported,
  - project settings should control only the explicit Export CSV feature,
  - export settings may be seeded from the imported CSV format on first import,
  - save/reopen of the project-owned CSV should use the persisted import-side format, not export settings.
- This is a blocker.
- Non-goal: unrelated CSV workflow changes beyond fixing reopen reliability.
