# QA Validation: GPT-5 max_completion_tokens Fix

**Date**: 2026-06-17
**Reviewer**: QA Engineer
**Scope**: Single-parameter rename `max_tokens` → `max_completion_tokens` in `OpenAIProvider.generate()` SDK call.

---

## Artifacts Consumed

| Artifact | Path |
|----------|------|
| Implementation notes | `project/gpt5-max-completion-tokens/implementation-notes.md` |
| Status | `project/gpt5-max-completion-tokens/status.md` |
| Action register | `project/gpt5-max-completion-tokens/action-register.md` |
| Source | `src/product_description_tool/providers.py` |
| Existing tests | `tests/test_providers.py` |

---

## Review Scope

1. Confirm the fix correctly maps `max_output_tokens` → `max_completion_tokens` in the OpenAI SDK call.
2. Confirm no other SDK call sites are affected by the old parameter.
3. Confirm regression test coverage validates the change.
4. Run the provider test suite to verify all tests pass.

---

## Findings

### F1: Fix is correctly applied

`providers.py:232` shows:

```python
max_completion_tokens=max_output_tokens,
```

This is the only `chat.completions.create()` call in the entire source tree. The parameter has been renamed from `max_tokens` to `max_completion_tokens`, which is the parameter GPT-5 models expect.

### F2: No other affected call sites

- Only one `chat.completions.create()` call exists (`providers.py:224`).
- `dialogs.py` references `max_tokens` only as UI labels/storage names for the spin box that feeds into `max_output_tokens` — these are unrelated to the SDK parameter.
- `OllamaProvider` uses `num_predict` in its own payload dict; it is unaffected.

### F3: Regression test validates the new parameter

`tests/test_providers.py:166`:

```python
assert captured["max_completion_tokens"] == 111
```

`test_openai_provider_uses_sdk` (lines 120–169):
- Patches `OpenAI` with a fake that captures all kwargs to `chat.completions.create()`.
- Verifies `max_completion_tokens` is passed with the correct value (111).
- Also verifies `stream`, `extra_body`, `api_key`, `base_url`, and the `http_client` type.
- Assertion at line 166 would fail if the parameter were reverted to `max_tokens`.

**Minor gap**: The test does not explicitly assert the absence of `max_tokens` in the kwargs. If a future change accidentally added **both** parameters, the current assertion would still pass. Given the direct single-call structure with no conditional logic, this is low risk.

### F4: Test suite passes

```text
$ ./scripts/pytest.sh tests/test_providers.py
============================= test session starts ==============================
platform darwin -- Python 3.14.4, pytest-9.0.2, pluggy-1.6.0
PySide6 6.10.2 -- Qt runtime 6.10.2 -- Qt compiled 6.10.2
rootdir: /Users/tomaswys/projects/product-description-tool
configfile: pyproject.toml
plugins: anyio-4.12.1, qt-4.5.0
collected 6 items

tests/test_providers.py ......                                           [100%]

============================== 6 passed in 0.33s ===============================
```

All 6 tests pass in 0.33s.

---

## Coverage Assessment

| Concern | Status |
|---------|--------|
| Correct parameter name in SDK call | ✅ Verified |
| No stale `max_tokens` in the same call | ✅ Verified |
| All provider tests pass | ✅ Verified |
| Ollama provider unaffected | ✅ Verified |
| No other `chat.completions.create()` call sites | ✅ Verified |
| Explicit assertion that old param is absent | ⚠️ Not covered (low risk) |

---

## Conclusion

**PASS** — The implementation correctly addresses the bug. The regression test adequately covers the change. The minor gap of not asserting the absence of the old `max_tokens` parameter is low-risk and does not warrant a change at this time.

No action-register entries require updating beyond adding this QA review outcome.
