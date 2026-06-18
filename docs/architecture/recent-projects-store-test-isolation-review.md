# Recent projects menu + test isolation review

Date: 2026-06-19

## Scope reviewed

- `src/product_description_tool/main_window.py` recent menu label rendering
- `src/product_description_tool/config.py` `RecentProjectsStore`
- `tests/conftest.py` recent-store isolation fixture
- `tests/test_config.py` recent-store tests
- `tests/test_main_window.py` recent-menu tests

## Final decision

- **Recent menu display change: approved.**
- **`RecentProjectsStore` constructor/test updates: approved.**
- **Test-isolation fixture: not approved in its current form.**

Because the fixture monkeypatches `platformdirs.user_config_dir`, but `config.py` binds `user_config_dir` via `from platformdirs import user_config_dir`, the patch does **not** change what `RecentProjectsStore()` calls after `product_description_tool.config` has already been imported. In this test suite, those imports occur at module import time, before fixture execution.

Therefore the current fixture does **not** provide the claimed architectural guarantee that default-constructed `RecentProjectsStore()` instances are redirected away from the production config directory.

## Detailed findings

### 1. `MainWindow._build_recent_menu`

The UI change fits the existing contract and fixes the reported issue.

- `RecentProjectsStore.save()` persists resolved absolute paths.
- `RecentProjectsStore.load()` returns resolved `Path` objects.
- Showing `str(path.resolve())` in the menu is consistent with the persisted/shared contract.
- Keeping `action.setData(str(path))` is also consistent because `path` is already resolved on load.

No production regression is apparent here. The menu now shows the same canonical path shape the store manages.

### 2. `RecentProjectsStore`

The constructor remains aligned with project patterns:

- optional dependency injection via `path=` for tests and special callers,
- default path resolution for normal runtime,
- no test-only branching in production code.

The updated tests in `tests/test_config.py` are better than the previous construct-then-mutate pattern because they exercise the public constructor contract directly.

### 3. Test isolation fixture

The intent is correct, but the patch point is wrong.

Current fixture:

- patches `platformdirs.user_config_dir`

Actual production call site:

- `product_description_tool.config.user_config_dir`

Because `config.py` imported the function directly, monkeypatching the source module later does not update the already-bound local name in `config.py`.

Implication:

- tests that explicitly pass `RecentProjectsStore(path=...)` are isolated,
- but tests that create `MainWindow(config_store=...)` without injecting `recent_store=` still construct a default `RecentProjectsStore()` using the real config path,
- so the suite can still read or write the real `~/.config/.../recent.json` depending on exercised behavior.

This is an architectural contract issue, not just a stylistic one, because the fixture currently claims a repo-wide safety guarantee it does not actually enforce.

## Recommended correction

Keep the solution test-only, but patch the symbol actually used by production code:

1. **Preferred:** monkeypatch `product_description_tool.config.user_config_dir` to `tmp_path`.
2. **Alternative:** monkeypatch `product_description_tool.config.RecentProjectsStore.__init__` or inject `recent_store=` in every `MainWindow` test, though both are less clean.

The first option best preserves the runtime contract while ensuring default construction remains test-safe.

## Contract consistency assessment

- `MainWindow` and `RecentProjectsStore` are consistent with each other.
- The targeted recent-project tests are consistent with the new UI behavior.
- `tests/conftest.py` is **not** consistent with the actual import contract used by `config.py`.

## Non-test side effects

None identified in production code:

- menu labels now carry more useful information,
- persistence format is unchanged,
- default runtime path selection is unchanged,
- no new behavior was introduced outside tests.

## Suggested action register entry

- ID: AR-1
  - source: Architect
  - finding: The autouse recent-store fixture patches `platformdirs.user_config_dir`, but `RecentProjectsStore()` uses the already-imported `product_description_tool.config.user_config_dir`, so tests are not guaranteed to avoid the production `recent.json` path.
  - disposition: fix now
  - owner: Product Developer
  - target: current task
  - architect-review: not approved until the fixture patches the correct symbol or equivalent test-safe isolation is implemented.

## Approval status

**Not architecturally approved for final user reporting yet.**

Approval can be granted once the test fixture is corrected so default-constructed `RecentProjectsStore()` instances in tests are actually redirected away from the production config directory.
