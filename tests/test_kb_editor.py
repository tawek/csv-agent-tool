from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

from PySide6.QtWidgets import QMessageBox, QPlainTextEdit

from product_description_tool import message_box
from product_description_tool.highlighter import MarkdownSyntaxHighlighter
from product_description_tool.kb_editor import MarkdownEditor, open_external


# ---------------------------------------------------------------------------
# MarkdownEditor — shared reusable editor widget
# ---------------------------------------------------------------------------


def test_markdown_editor_is_plain_text_edit(qtbot) -> None:
    """The MarkdownEditor is a QPlainTextEdit (the shared editor widget)."""
    editor = MarkdownEditor()
    qtbot.addWidget(editor)
    assert isinstance(editor, QPlainTextEdit)


def test_markdown_editor_has_markdown_syntax_highlighter(qtbot) -> None:
    """The editor has a MarkdownSyntaxHighlighter attached to its document."""
    editor = MarkdownEditor()
    qtbot.addWidget(editor)
    # The highlighter is stored as _highlighter, set in __init__
    assert hasattr(editor, "_highlighter")
    assert isinstance(editor._highlighter, MarkdownSyntaxHighlighter)


def test_markdown_editor_accepts_and_returns_text(qtbot) -> None:
    """Plain text can be set and retrieved from the editor."""
    editor = MarkdownEditor()
    qtbot.addWidget(editor)

    editor.setPlainText("# Hello\n\nThis is **bold** text.")
    assert editor.toPlainText() == "# Hello\n\nThis is **bold** text."


def test_markdown_editor_tab_stop_is_four_spaces(qtbot) -> None:
    """Tab stop distance is set to 4 space characters."""
    editor = MarkdownEditor()
    qtbot.addWidget(editor)
    # The tab stop is a positive float; verify it is reasonable.
    tab_stop = editor.tabStopDistance()
    assert tab_stop > 0
    # Verify it approximates 4 * average char width
    expected = editor.fontMetrics().horizontalAdvance(" ") * 4
    assert abs(tab_stop - expected) < 1.0


def test_markdown_editor_accepts_editing_via_keyboard(qtbot) -> None:
    """Simulated typing produces expected content."""
    editor = MarkdownEditor()
    qtbot.addWidget(editor)
    editor.show()

    editor.setFocus()
    qtbot.keyClicks(editor, "Hello **world**")
    assert editor.toPlainText() == "Hello **world**"


def test_markdown_editor_shared_across_modules() -> None:
    """MarkdownEditor is imported and used in both main_window and kb_window.

    This test asserts the shared-widget contract by checking that the
    same class is referenced from both modules at import time.
    """
    from product_description_tool import main_window as mw
    from product_description_tool import kb_window as kw

    # Both modules import MarkdownEditor from kb_editor
    assert mw.MarkdownEditor is MarkdownEditor
    assert kw.MarkdownEditor is MarkdownEditor


# ---------------------------------------------------------------------------
# open_external — OS-level file launcher
# ---------------------------------------------------------------------------


def test_open_external_linux_uses_xdg_open(monkeypatch) -> None:
    """On Linux, open_external calls xdg-open with the given path."""
    called_args = []

    def fake_run(cmd, **kwargs):
        called_args.append(cmd)
        return MagicMock()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("sys.platform", "linux")

    open_external("/some/path/file.txt")

    assert len(called_args) == 1
    assert called_args[0] == ["xdg-open", "/some/path/file.txt"]


def test_open_external_darwin_uses_open(monkeypatch) -> None:
    """On macOS, open_external calls 'open' with the given path."""
    called_args = []

    def fake_run(cmd, **kwargs):
        called_args.append(cmd)
        return MagicMock()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("sys.platform", "darwin")

    open_external("/some/path/file.txt")

    assert len(called_args) == 1
    assert called_args[0] == ["open", "/some/path/file.txt"]


def test_open_external_linux_failure_shows_warning(monkeypatch) -> None:
    """On Linux, when subprocess.run fails, a QMessageBox warning is shown."""
    import subprocess

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("xdg-open not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("sys.platform", "linux")

    warning_messages = []

    def fake_warning(*args, **kwargs):
        warning_messages.append((args, kwargs))
        return QMessageBox.StandardButton.Ok

    message_box.set_response("warning", fake_warning)

    open_external("/nonexistent/file.txt")

    message_box.reset()
    assert len(warning_messages) >= 1
    title_text = warning_messages[0][0]
    combined = " ".join(str(t) for t in title_text)
    assert "Open failed" in combined or "Could not open" in combined
