from __future__ import annotations

import os
from typing import Any, Callable

from PySide6.QtWidgets import QMessageBox, QWidget

# Re-export for code that references QMessageBox.StandardButton directly
QMessageBoxStandardButton = QMessageBox.StandardButton

# ---------------------------------------------------------------------------
# Configuration (set by tests or production code)
# ---------------------------------------------------------------------------

_test_mode: bool = False
_responses: dict[str, QMessageBox.StandardButton | Callable[..., QMessageBox.StandardButton]] = {}

# Defaults: non-question methods return Ok, question returns No
_DEFAULTS: dict[str, QMessageBox.StandardButton] = {
    "information": QMessageBox.StandardButton.Ok,
    "warning": QMessageBox.StandardButton.Ok,
    "critical": QMessageBox.StandardButton.Ok,
    "question": QMessageBox.StandardButton.No,
}


def set_test_mode(enabled: bool) -> None:
    """Enable or disable test mode.

    In test mode all message-box calls return predetermined values
    without spawning blocking dialogs.
    """
    global _test_mode
    _test_mode = enabled


def set_response(
    method: str,
    response: QMessageBox.StandardButton | Callable[..., QMessageBox.StandardButton],
) -> None:
    """Override the return value for *method* in test mode.

    *response* can be a :class:`QMessageBox.StandardButton` or a callable
    that accepts the same arguments as the corresponding ``QMessageBox``
    static method and returns a button.  Callables are useful when tests
    need to inspect or capture the message content.
    """
    _responses[method] = response


def reset() -> None:
    """Reset test-mode overrides to defaults."""
    _responses.clear()


def _get_response(method: str) -> QMessageBox.StandardButton | Callable[..., QMessageBox.StandardButton]:
    """Return the configured response for *method*, falling back to defaults."""
    return _responses.get(method, _DEFAULTS.get(method, QMessageBox.StandardButton.Ok))


# ---------------------------------------------------------------------------
# Public API — drop-in replacements for QMessageBox static methods
# ---------------------------------------------------------------------------


def information(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButtons = QMessageBox.StandardButton.Ok,
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    """Show an information message box.

    In test mode returns a predetermined value without spawning a dialog.
    If the configured response is a callable, it is invoked with the same
    arguments and its return value is used.
    """
    if _test_mode:
        response = _get_response("information")
        if callable(response):
            return response(parent, title, text, buttons, default_button)
        return response
    return QMessageBox.information(parent, title, text, buttons, default_button)


def warning(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButtons = QMessageBox.StandardButton.Ok,
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    """Show a warning message box.

    In test mode returns a predetermined value without spawning a dialog.
    If the configured response is a callable, it is invoked with the same
    arguments and its return value is used.
    """
    if _test_mode:
        response = _get_response("warning")
        if callable(response):
            return response(parent, title, text, buttons, default_button)
        return response
    return QMessageBox.warning(parent, title, text, buttons, default_button)


def critical(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButtons = QMessageBox.StandardButton.Ok,
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    """Show a critical error message box.

    In test mode returns a predetermined value without spawning a dialog.
    If the configured response is a callable, it is invoked with the same
    arguments and its return value is used.
    """
    if _test_mode:
        response = _get_response("critical")
        if callable(response):
            return response(parent, title, text, buttons, default_button)
        return response
    return QMessageBox.critical(parent, title, text, buttons, default_button)


def question(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButtons = QMessageBox.StandardButton.Ok,
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    """Show a question message box.

    In test mode returns a predetermined value without spawning a dialog.
    If the configured response is a callable, it is invoked with the same
    arguments and its return value is used.
    """
    if _test_mode:
        response = _get_response("question")
        if callable(response):
            return response(parent, title, text, buttons, default_button)
        return response
    return QMessageBox.question(parent, title, text, buttons, default_button)
