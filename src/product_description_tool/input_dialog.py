from __future__ import annotations

from typing import Callable

from PySide6 import QtCore, QtWidgets

__all__ = [
    "set_test_mode",
    "set_response",
    "reset",
    "get_text",
    "get_int",
    "get_double",
    "get_item",
]

# ---------------------------------------------------------------------------
# Configuration (set by tests or production code)
# ---------------------------------------------------------------------------

_test_mode: bool = False
_responses: dict[str, Callable[..., tuple] | tuple] = {}

# ---------------------------------------------------------------------------
# Public API — drop-in replacements for QInputDialog static methods
# ---------------------------------------------------------------------------


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
    return _responses.get(method, _defaults.get(method, _fallback))


def _fallback(*args: object, **kwargs: object) -> tuple:
    """Default fallback for unknown methods."""
    return ("", False)


_defaults: dict[str, tuple] = {
    "getText": ("", False),
    "getInt": (0, False),
    "getDouble": (0.0, False),
    "getItem": ("", False),
}


def get_text(
    parent: QtWidgets.QWidget | None,
    title: str,
    label: str,
    *,
    echo: QtWidgets.QLineEdit.EchoMode | None = None,
    text: str = "",
    flags: QtCore.Qt.WindowFlags | None = None,
    inputMethodHints: QtCore.Qt.InputMethodHint | None = None,
) -> tuple[str, bool]:
    """Show a text-input dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getText")
        if callable(response):
            return response(
                parent, title, label, echo, text, flags, inputMethodHints
            )
        return response
    kwargs: dict[str, object] = {}
    if echo is not None:
        kwargs["echo"] = echo
    if text:
        kwargs["text"] = text
    if flags is not None:
        kwargs["flags"] = flags
    if inputMethodHints is not None:
        kwargs["inputMethodHints"] = inputMethodHints
    return QtWidgets.QInputDialog.getText(parent, title, label, **kwargs)


def get_int(
    parent: QtWidgets.QWidget | None,
    title: str,
    label: str,
    min: int = 0,
    max: int = 99,
    step: int = 1,
    value: int = 0,
    flags: QtCore.Qt.WindowFlags | None = None,
) -> tuple[int, bool]:
    """Show an integer-input dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getInt")
        if callable(response):
            return response(parent, title, label, min, max, step, value, flags)
        return response
    return QtWidgets.QInputDialog.getInt(
        parent, title, label, min, max, step, value, flags
    )


def get_double(
    parent: QtWidgets.QWidget | None,
    title: str,
    label: str,
    value: float = 0,
    min: float = 0,
    max: float = 99,
    decimals: int = 1,
    step: float = 1,
    flags: QtCore.Qt.WindowFlags | None = None,
) -> tuple[float, bool]:
    """Show a double-input dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getDouble")
        if callable(response):
            return response(
                parent, title, label, value, min, max, decimals, step, flags
            )
        return response
    return QtWidgets.QInputDialog.getDouble(
        parent, title, label, value, min, max, decimals, step, flags
    )


def get_item(
    parent: QtWidgets.QWidget | None,
    title: str,
    label: str,
    items: list[str],
    currentItem: int = 0,
    editable: bool = True,
    flags: QtCore.Qt.WindowFlags | None = None,
) -> tuple[str, bool]:
    """Show an item-selection dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getItem")
        if callable(response):
            return response(
                parent, title, label, items, currentItem, editable, flags
            )
        return response
    return QtWidgets.QInputDialog.getItem(
        parent, title, label, items, currentItem, editable, flags
    )
