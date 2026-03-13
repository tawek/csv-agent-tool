from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


class HtmlSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.rules = []

        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#005f73"))
        tag_format.setFontWeight(700)
        self.rules.append((QRegularExpression(r"</?[\w:-]+"), tag_format))

        attr_format = QTextCharFormat()
        attr_format.setForeground(QColor("#9b2226"))
        self.rules.append((QRegularExpression(r"\b[\w:-]+(?=\=)"), attr_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#2a9d8f"))
        self.rules.append((QRegularExpression(r'"[^"]*"'), string_format))

        punctuation_format = QTextCharFormat()
        punctuation_format.setForeground(QColor("#6c757d"))
        self.rules.append((QRegularExpression(r"/?>"), punctuation_format))

    def highlightBlock(self, text: str) -> None:
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)
