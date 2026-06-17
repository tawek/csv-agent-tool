from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit

from product_description_tool.highlighter import MarkdownSyntaxHighlighter
from product_description_tool.message_box import warning


def open_external(path: str) -> None:
    """Open *path* with the OS default application.

    Falls back to a warning message if the platform is not supported or the
    operation fails.
    """
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=True)
        else:
            subprocess.run(["xdg-open", path], check=True)
    except Exception as exc:  # noqa: BLE001
        warning(
            None,
            "Open failed",
            f"Could not open '{path}':\n{exc}",
        )


class MarkdownEditor(QPlainTextEdit):
    """A plain-text editor with Markdown syntax highlighting.

    This widget is reusable across the application — used as the prompt
    editor in the main window's Prompts panel and as the embedded editor
    for knowledge-base Markdown and text files.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._highlighter = MarkdownSyntaxHighlighter(self.document())
        tab_stop = self.fontMetrics().horizontalAdvance(" ") * 4
        self.setTabStopDistance(tab_stop)
