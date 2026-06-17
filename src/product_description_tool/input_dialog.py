from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QInputDialog


# ---------------------------------------------------------------------------
# Configuration (set by tests or production code)
# ---------------------------------------------------------------------------

_test_mode: bool = False
_responses: dict[str, Callable[..., tuple] | tuple] = {}

# Defaults: ("", False) — empty text + cancelled
_DEFAULTS: dict[str, Callable[..., tuple]] = {
    "getText": lambda *args, **kwargs: ("", False),
    "getInt": lambda *args, **kwargs: (0, False),
    "getDouble": lambda *args, **kwargs: (0.0, False),
    "getItem": lambda *args, **kwargs: ("", False),
}


def set_test_mode(enabled: bool) -> None:
    """Enable or disable test mode.

    In test mode all input-dialog calls return predetermined values
    without spawning blocking dialogs.
    """
    global _test_mode
    _test_mode = enabled


def set_response(
    method: str,
    response: Callable[..., tuple] | tuple,
) -> None:
    """Override the return value for *method* in test mode.

    *response* can be a callable (receiving same args as QInputDialog static
    method) or a plain tuple matching the return signature of the method.
    """
    _responses[method] = response


def reset() -> None:
    """Reset test-mode overrides to defaults."""
    _responses.clear()


def _get_response(method: str) -> Callable[..., tuple] | tuple:
    """Return the configured response for *method*, falling back to defaults."""
    return _responses.get(method, _DEFAULTS.get(method, lambda *a, **k: ("", False)))


# ---------------------------------------------------------------------------
# Public API — drop-in replacements for QInputDialog static methods
# ---------------------------------------------------------------------------


def get_text(
    parent,
    title: str,
    label: str,
    text: str = "",
    flags: int = 0,
    validator=None,
) -> tuple[str, bool]:
    """Show a text-input dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getText")
        if callable(response):
            return response(parent, title, label, text, flags, validator)
        return response
    return QInputDialog.getText(parent, title, label, text, flags, validator)


def get_int(
    parent,
    title: str,
    label: str,
    min: int = 0,
    max: int = 99,
    step: int = 1,
    base: int = 10,
    text: str = "",
) -> tuple[int, bool]:
    """Show an integer-input dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getInt")
        if callable(response):
            return response(parent, title, label, min, max, step, base, text)
        return response
    return QInputDialog.getInt(parent, title, label, min, max, step, base, text)


def get_double(
    parent,
    title: str,
    label: str,
    min: float = 0,
    max: float = 99,
    decimals: int = 1,
    text: str = "",
) -> tuple[float, bool]:
    """Show a double-input dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getDouble")
        if callable(response):
            return response(parent, title, label, min, max, decimals, text)
        return response
    return QInputDialog.getDouble(parent, title, label, min, max, decimals, text)


def get_item(
    parent,
    title: str,
    label: str,
    items: list[str],
    current: int = 0,
    editable: bool = True,
) -> tuple[str, bool]:
    """Show an item-selection dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getItem")
        if callable(response):
            return response(parent, title, label, items, current, editable)
        return response
    return QInputDialog.getItem(parent, title, label, items, current, editable)
