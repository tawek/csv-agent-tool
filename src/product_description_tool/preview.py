from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

try:
    if os.environ.get("PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE") == "1":
        raise ImportError
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


_WORD_PATTERN = re.compile(r"\S+")
_SECTION_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_PARAGRAPH_TAGS = {"br", "li", "p"}


@dataclass(slots=True)
class HtmlContentStats:
    sections: int = 0
    paragraphs: int = 0
    words: int = 0
    characters: int = 0


class _HtmlContentStatsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stats = HtmlContentStats()

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        del attrs
        self._count_tag(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        del attrs
        self._count_tag(tag)

    def handle_data(self, data: str) -> None:
        self.stats.words += len(_WORD_PATTERN.findall(data))
        self.stats.characters += sum(1 for character in data if not character.isspace())

    def _count_tag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _PARAGRAPH_TAGS:
            self.stats.paragraphs += 1
        if normalized in _SECTION_TAGS:
            self.stats.sections += 1


def analyze_html_content(html: str) -> HtmlContentStats:
    parser = _HtmlContentStatsParser()
    parser.feed(html)
    parser.close()
    return parser.stats


def format_html_stats(stats: HtmlContentStats) -> str:
    return (
        f"Sections: {stats.sections}, Paragraphs: {stats.paragraphs}, "
        f"Words: {stats.words}, Characters: {stats.characters}"
    )


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
