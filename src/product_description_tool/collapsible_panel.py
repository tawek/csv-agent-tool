from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget


class _HeaderRow(QWidget):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CollapsiblePanel(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self._expanded = True
        self.setStyleSheet(
            """
            QWidget#panelHeaderRow {
                background-color: transparent;
            }
            QToolButton#panelToggle {
                background-color: palette(button);
                color: palette(button-text);
                border: none;
                border-radius: 0;
                padding: 4px 6px 4px 4px;
                min-height: 20px;
                font-weight: 600;
                text-align: left;
            }
            QToolButton#panelToggle:hover {
                background-color: palette(midlight);
            }
            QLabel#panelTitle {
                color: palette(button-text);
                background-color: palette(button);
                padding: 4px 8px 4px 2px;
                min-height: 20px;
                font-weight: 600;
            }
            QFrame#panelBody {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_row = _HeaderRow()
        self.header_row.setObjectName("panelHeaderRow")
        self.header_row.clicked.connect(self._toggle_from_header)
        header_layout = QHBoxLayout(self.header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self.toggle_button = QToolButton()
        self.toggle_button.setObjectName("panelToggle")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setText("")
        self.toggle_button.setFixedWidth(20)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.clicked.connect(self.set_expanded)
        header_layout.addWidget(self.toggle_button)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("panelTitle")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        layout.addWidget(self.header_row)

        self.body_frame = QFrame()
        self.body_frame.setObjectName("panelBody")
        body_layout = QVBoxLayout(self.body_frame)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(8)

        self.content = QWidget()
        body_layout.addWidget(self.content)
        layout.addWidget(self.body_frame)

    @property
    def title(self) -> str:
        return self.title_label.text()

    @property
    def expanded(self) -> bool:
        return self._expanded

    def header_height(self) -> int:
        margins = self.layout().contentsMargins()
        return self.header_row.sizeHint().height() + margins.top() + margins.bottom()

    def _toggle_from_header(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.toggle_button.setChecked(self._expanded)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow
        )
        self.body_frame.setVisible(self._expanded)
        self.toggled.emit(self._expanded)
