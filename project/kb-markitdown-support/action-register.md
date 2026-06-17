# Action Register

# Action Register

## Open findings

| ID | Source | Finding | Disposition | Owner | Target | Status |
|----|--------|---------|-------------|-------|--------|--------|
| AR-1 | Validation | `test_view_converted_file_handles_markitdown_unavailable` hangs under pytest-qt when monkeypatching `_check_markitdown`. Implementation logic is correct (proven in standalone execution). Coverage for the behavior exists in `test_kb_conversion.py`. | `defer` | QA | Post-implementation test fix | `open` |

Rationale for defer: The implementation behavior is correct and covered by other passing tests. The hang is a pytest-qt interaction issue with monkeypatch on a specific method. Fixing the test (e.g., patching `load_markdown` directly or patching the `markitdown` import) is a QA-owned test concern.
