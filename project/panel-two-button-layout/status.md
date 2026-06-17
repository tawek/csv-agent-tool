# Panel Two-Button Layout Status

- Status: completed
- Scope: Replaced the previous panel layout controls with fixed `+` and `-` buttons and explicit maximized / normal / minimized / temporary-minimized handling.
- Validation: `QT_QPA_PLATFORM=offscreen PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE=1 uv run pytest` → 144 passed.
- Architect gate: passed with no findings.
