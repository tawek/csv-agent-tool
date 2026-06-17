# Action Register

# Action Register

## Open findings

| ID | Source | Finding | Disposition | Owner | Target | Status |
|----|--------|---------|-------------|-------|--------|--------|
| AR-1 | Validation | `test_view_converted_file_handles_markitdown_unavailable` hangs under pytest-qt when monkeypatching `_check_markitdown`. Implementation logic is correct (proven in standalone execution). Coverage for the behavior exists in `test_kb_conversion.py`. | `defer` | QA | Post-implementation test fix | `open` |
| AR-2 | Architect | Packaging follow-up installs `markitdown[outlook]` while KB support does not currently expose `.msg`, and KB conversion still advertises `.doc` / `.ppt` although MarkItDown 0.1.6 only provides `.docx` / `.pptx` converters. | `monitor` | Product/Architect | Future KB contract-alignment cleanup | `open` |

Rationale for defer: The implementation behavior is correct and covered by other passing tests. The hang is a pytest-qt interaction issue with monkeypatch on a specific method. Fixing the test (e.g., patching `load_markdown` directly or patching the `markitdown` import) is a QA-owned test concern.

Rationale for monitor: The packaging follow-up correctly satisfies the PDF/Office-installation goal and does not create a packaged-build blocker. The remaining issue is contract alignment between the dependency set and the app's exposed supported-file list.
