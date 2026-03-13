from __future__ import annotations

import os

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

try:
    if os.environ.get("PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE") == "1":
        raise ImportError
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


class HtmlPreview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if QWebEngineView is None:
            self.viewer = QTextBrowser()
            self._webengine = False
        else:
            self.viewer = QWebEngineView()
            self._webengine = True
        layout.addWidget(self.viewer)

    def set_html(self, html: str) -> None:
        if self._webengine:
            self.viewer.setHtml(html)
        else:
            self.viewer.setHtml(html)
