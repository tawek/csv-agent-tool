# Message Box Abstraction Design

## Purpose

Define a stable application-owned boundary for modal message boxes so GUI tests do not depend on patching `QMessageBox` directly across multiple import sites.

## Problem

Current tests patch `QMessageBox` at multiple levels:

- `PySide6.QtWidgets.QMessageBox.*` in `tests/conftest.py`
- module-local imports such as `product_description_tool.main_window.QMessageBox.*`
- per-test monkeypatches for capture and button selection

Because `QMessageBox` is imported into many modules, patching one symbol does not reliably patch all call sites. This creates blocking-dialog risk under `pytest-qt` and makes per-test overrides fragile.

## Decision

Introduce a single application-owned wrapper module, `src/product_description_tool/message_box.py`, and migrate application code to call that wrapper instead of `QMessageBox` directly.

This is the preferred approach over adding more global monkeypatching because it:

1. creates one patch/configuration seam owned by the app,
2. removes dependency on Qt import topology,
3. keeps test control explicit and deterministic, and
4. reduces future modal-test regressions.

## Boundary

The wrapper should be intentionally thin.

### Minimum public API

- `information(parent, title, text, buttons=..., default_button=...)`
- `warning(parent, title, text, buttons=..., default_button=...)`
- `critical(parent, title, text, buttons=..., default_button=...)`
- `question(parent, title, text, buttons=..., default_button=...)`

Return type should remain `QMessageBox.StandardButton` so existing calling code can keep its comparisons.

Do not invent a richer dialog model unless a real product requirement appears.

## Test-mode control

Do **not** auto-detect pytest by importing pytest internals or by guessing from event-loop state.

Preferred order:

1. explicit module-level override API used by tests,
2. optional environment-variable default as a suite-wide safety net.

Recommended environment variable:

- `PRODUCT_DESCRIPTION_TOOL_TEST_MODE=1`

Rationale:

- explicit and app-owned,
- independent of pytest-qt,
- usable from `conftest.py` before widgets are exercised,
- avoids hidden production/test branching based on framework heuristics.

## Test configuration model

Use a small stateful configuration API in the wrapper, designed for fixture use.

Recommended capabilities:

- set/reset global test mode
- set default return values per severity/method (`information`, `warning`, `critical`, `question`)
- optionally record calls for assertions
- reset all state between tests

Recommended shape:

- one reset operation that restores production defaults
- one configuration operation for per-method return values
- one read-only call log accessor if tests need to inspect shown messages

Keep configuration module-local; do not thread it through window constructors.

## Return-value policy

Always return actual `QMessageBox.StandardButton` values from the wrapper, both in production and test mode.

Reasons:

- preserves current call-site comparisons,
- avoids a second enum/translation layer,
- minimizes migration cost across ~79 usages.

For methods that normally default to `Ok`, the test default should return `StandardButton.Ok`.
For `question`, default test return should be conservative, usually `StandardButton.No`.
For existing save/discard/cancel flows, tests should configure the exact desired button explicitly.

## Migration guidance

1. Replace direct `QMessageBox.*` usage in app modules with wrapper calls.
2. Leave `QMessageBox.StandardButton` comparisons in place initially.
3. Remove broad Qt-level monkeypatching from `conftest.py` after wrapper adoption.
4. Convert per-test overrides to wrapper configuration calls.

## Non-goals

- no user-visible behavior change,
- no custom dialog rendering,
- no dependency injection refactor across the UI layer.

## Tradeoff

The wrapper introduces small global state for tests. That is acceptable here because the alternative already relies on broader global monkeypatching, and the wrapper centralizes that state behind an application-owned contract.
