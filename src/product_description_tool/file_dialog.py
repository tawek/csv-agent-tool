from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QFileDialog


# ---------------------------------------------------------------------------
# Configuration (set by tests or production code)
# ---------------------------------------------------------------------------

_test_mode: bool = False
_responses: dict[str, Callable[..., tuple[str, str | None]] | tuple[str, str | None]] = {}

# Defaults: return empty string + None (cancellation-like)
_DEFAULTS: dict[str, Callable[..., tuple[str, str | None]]] = {
    "getOpenFileName": lambda *args, **kwargs: ("", ""),
    "getSaveFileName": lambda *args, **kwargs: ("", ""),
    "getExistingDirectory": lambda *args, **kwargs: "",
}


def set_test_mode(enabled: bool) -> None:
    """Enable or disable test mode.

    In test mode all file-dialog calls return predetermined values
    without spawning blocking dialogs.
    """
    global _test_mode
    _test_mode = enabled


def set_response(
    method: str,
    response: Callable[..., tuple[str, str | None]] | tuple[str, str | None],
) -> None:
    """Override the return value for *method* in test mode.

    *response* can be a callable (receiving same args as QMessageBox static
    method) or a plain tuple ``(path, filter)``.
    """
    _responses[method] = response


def reset() -> None:
    """Reset test-mode overrides to defaults."""
    _responses.clear()


def _get_response(method: str) -> Callable[..., tuple[str, str | None]] | tuple[str, str | None]:
    """Return the configured response for *method*, falling back to defaults."""
    return _responses.get(method, _DEFAULTS.get(method, lambda *a, **k: ("", "")))


# ---------------------------------------------------------------------------
# Public API — drop-in replacements for QFileDialog static methods
# ---------------------------------------------------------------------------


def get_open_file_name(
    parent=None,
    caption: str = "",
    directory: str = "",
    filter: str = "",
    initial_filter: str = "",
) -> str:
    """Show a file-open dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getOpenFileName")
        if callable(response):
            result = response(parent, caption, directory, filter, initial_filter)
            return result[0] if isinstance(result, tuple) else result
        return response[0]
    return QFileDialog.getOpenFileName(parent, caption, directory, filter, initial_filter)[0]


def get_save_file_name(
    parent=None,
    caption: str = "",
    directory: str = "",
    filter: str = "",
    initial_filter: str = "",
) -> str:
    """Show a file-save dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getSaveFileName")
        if callable(response):
            result = response(parent, caption, directory, filter, initial_filter)
            return result[0] if isinstance(result, tuple) else result
        return response[0]
    return QFileDialog.getSaveFileName(parent, caption, directory, filter, initial_filter)[0]


def get_existing_directory(
    parent=None,
    caption: str = "",
    directory: str = "",
    options: int | QFileDialog.Option = 0,
) -> str:
    """Show an existing-directory dialog.

    In test mode returns a predetermined value without spawning a dialog.
    """
    if _test_mode:
        response = _get_response("getExistingDirectory")
        if callable(response):
            return response(parent, caption, directory, options)
        return response
    dialog_options = options
    if not isinstance(dialog_options, QFileDialog.Option):
        dialog_options = QFileDialog.Option(dialog_options)
    return QFileDialog.getExistingDirectory(parent, caption, directory, dialog_options)
