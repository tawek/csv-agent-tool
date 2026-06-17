# QA Report: Prompt Attachments Feature

**Date:** 2026-06-17
**Author:** QA Engineer
**Status:** Complete — all test objectives met

## Scope

Implementation of test coverage for the prompt-attachments feature (Use Case 28 in `docs/specification.md`) and resolution of the outstanding `FakeGenerationService` test-double mismatch.

## Boundary Conditions

- **Source changes** were applied by Product Developer before this QA task. QA edits only `tests/`.
- **No source code was modified** — all changes are in test files.
- **All tests run headlessly** at `QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1`.

## Artifacts Modified / Created

| File | Change |
|------|--------|
| `tests/test_main_window.py` | Fixed `FakeGenerationService` and 3 subclasses to accept `attachments` kwarg. Added 14 new MainWindow-level attachment UI tests. |
| `tests/test_attachments.py` | **New file** — 68 tests covering validation, effective prompt building, AttachmentManager internals, dialog integration, and persistence. |

## Test Results

```
324 passed in 2.20s
```

| Test file | Count | Status |
|-----------|-------|--------|
| `tests/test_main_window.py` | 74 (60 existing + 14 new) | All pass |
| `tests/test_attachments.py` | 68 (new) | All pass |
| Other existing test files | ~182 | All pass (unchanged) |

## Coverage Summary

### 1. Test-double mismatch resolved (DEV-1)

All four `FakeGenerationService` variants now accept `attachments=None`:

- `FakeGenerationService.process_row` — `attachments=None` added
- `FakeGenerationService.process_rows` — `attachments=None` added, now passes `knowledge_base_dir` and `attachments` through to `process_row`
- `FakeGenerationService.prepare_prompt` — `attachments=None` added
- `FakeGenerationService.validate_attachments` — added as no-op (matches real signature)
- `SlowCancellableGenerationService.process_row` — accepts and passes through `attachments`
- `BlockingCancellableGenerationService.process_row` — accepts `attachments`
- `DelayedCancelGenerationService.process_row` — accepts `attachments`

**Result:** 6 previously-broken test paths are now unblocked. No existing test regressed.

### 2. Validation tests (`GenerationService.validate_attachments`)

9 test cases covering:
- Valid CSV-column attachment (passes)
- Missing CSV-column attachment (raises ValueError)
- Valid KB-file attachment (passes)
- KB-file without configured KB directory (raises ValueError)
- KB-file path escaping the KB root (raises ValueError)
- KB-file not found (raises ValueError)
- KB-file pointing to a directory (raises ValueError)
- KB-file unsupported file type (raises ValueError)
- Unknown source_type (raises ValueError)
- Mixed valid attachments pass
- First invalid attachment fails early

### 3. Effective prompt building tests (`GenerationService.build_effective_prompt`)

11 test cases covering:
- No attachments — template returned unchanged
- CSV-column attachment — value appended with provenance
- KB-file attachment — file content appended with provenance
- Mixed attachments in KB-first order — order respected
- CSV-before-KB user ordering — user order respected
- Empty CSV column value — still appended with provenance
- Missing KB file — graceful empty content
- No KB directory — graceful empty content
- Escaping KB path — graceful empty content
- Multiple attachments (4) — all included in correct order

### 4. AttachmentManager cost-warning logic

7 test cases:
- KB before CSV — no warning
- Only CSV columns — no warning
- Only KB files — no warning
- CSV before KB — warning shown
- Warning clears on reorder
- Multiple CSV before KB — warning shown
- KB first, then CSV — no warning (even with multiple CSV after)

### 5. AttachmentManager KB-first insertion ordering

7 test cases:
- KB inserted before existing CSV column
- KB appended when no CSV columns exist
- KB grouped with existing KB files, before CSV columns
- CSV columns appended at end
- CSV columns appended into empty list
- Multiple KB then multiple CSV — KB-group/CSV-group order
- KB inserted after existing CSV columns — KB placed before first CSV

### 6. AttachmentManager status resolution

7 test cases covering all `_resolve_kb_file_status` outcomes (Available, Missing KB root, Path escapes, File not found, Unsupported type) and both `_resolve_column_status` outcomes (Available, Column not found).

### 7. AttachmentManager dialog integration

10 test cases:
- Add KB files via insert method
- Add CSV columns via insert method
- Remove attachment
- Move up
- Move down
- Remove button disabled without selection
- Table reflects attachment data
- Add KB Files button enabled/disabled
- Add Columns button enabled/disabled

### 8. Persistence / serialization

12 test cases:
- `PromptAttachment.to_dict` / `from_dict` round-trip (KB and CSV)
- `ProjectPrompt.to_dict` includes attachments
- `ProjectPrompt.from_dict` restores attachments
- Attachments key absent when empty
- Empty attachments list not serialized
- Legacy data without attachments key loads cleanly
- Corrupt (non-list) attachments loads cleanly
- Full `ProjectRepository` save/load cycle (single and multiple attachments)
- Attachments appear in JSON manifest
- Attachments + KB directory round-trip together
- Prompt sidecar text unaffected by attachments

### 9. MainWindow UI integration

14 test cases:
- Attachment count label shown/hidden
- Plural label text
- Attachment button enabled/disabled with/without prompt
- Open attachment manager updates prompt attachments (with fake dialog)
- Cancel attachment manager leaves attachments unchanged
- Invalid column attachment blocks validation
- Valid column attachment passes validation
- Invalid KB attachment blocks validation
- Valid KB attachment passes validation
- Preview with attachments doesn't crash
- Batch processing with attachments doesn't crash

## Commands Executed

```bash
# Run all existing tests (to verify FakeGenerationService fix)
QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest tests/test_main_window.py -x -q

# Run new attachment-specific tests
QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest tests/test_attachments.py -x -q -v

# Run full suite for final validation
QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest -x -q
```

## Action Register Disposition

| ID | Finding | Disposition | Status |
|----|---------|-------------|--------|
| QA-BLOCK-1 | `QMessageBox` stubbing inconsistent | fix now | closed (resolved in prior work) |
| DEV-1 | `FakeGenerationService.process_row` missing `attachments` kwarg | fix now | **closed** (resolved in this task) |

## Findings / Open Items

None. All test objectives achieved.
