from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class HtmlSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.rules = []

        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#005f73"))
        tag_format.setFontWeight(QFont.Weight.Bold)
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


class MarkdownSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Markdown text."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        # Headers: # through ######
        hdr_fmt = QTextCharFormat()
        hdr_fmt.setForeground(QColor("#005f73"))
        hdr_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r"^#{1,6}\s.*$"), hdr_fmt))

        # Bold **text** or __text__
        bold_fmt = QTextCharFormat()
        bold_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r"\*\*[^*]+\*\*"), bold_fmt))
        self.rules.append((QRegularExpression(r"__[^_]+__"), bold_fmt))

        # Italic *text* or _text_
        italic_fmt = QTextCharFormat()
        italic_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"\*[^*]+\*"), italic_fmt))
        self.rules.append((QRegularExpression(r"_[^_]+_"), italic_fmt))

        # Inline code `text`
        code_fmt = QTextCharFormat()
        code_fmt.setForeground(QColor("#2a9d8f"))
        code_fmt.setFontFamilies(["monospace", "Courier New"])
        self.rules.append((QRegularExpression(r"`[^`]+`"), code_fmt))

        # Links [text](url)
        link_fmt = QTextCharFormat()
        link_fmt.setForeground(QColor("#005f73"))
        link_fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        link_fmt.setUnderlineColor(QColor("#005f73"))
        self.rules.append((QRegularExpression(r"\[[^\]]+\]\([^\)]+\)"), link_fmt))

        # Unordered list markers: -, *, + at line start
        list_fmt = QTextCharFormat()
        list_fmt.setForeground(QColor("#9b2226"))
        self.rules.append((QRegularExpression(r"^[\*\-\+]\s"), list_fmt))

        # Ordered list markers: 1. 2. etc at line start
        ol_fmt = QTextCharFormat()
        ol_fmt.setForeground(QColor("#9b2226"))
        self.rules.append((QRegularExpression(r"^\d+\.\s"), ol_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)
