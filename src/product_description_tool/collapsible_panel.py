from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget


class PanelState(Enum):
    """Explicit four-state model for panel layout management.

    Values:
        MAXIMIZED: Pane fills available space; cannot grow further.
        NORMAL: Pane at regular shared size.
        MINIMIZED: Pane body hidden, only header visible; cannot shrink further.
        TEMPORARY_MINIMIZED: Automatically minimized because another panel is
            maximized. Visually identical to MINIMIZED but restorable to NORMAL
            when the maximized panel returns to NORMAL.
    """

    MAXIMIZED = "maximized"
    NORMAL = "normal"
    MINIMIZED = "minimized"
    TEMPORARY_MINIMIZED = "temporary_minimized"


class CollapsiblePanel(QWidget):
    """A UI section panel with '+' (grow) and '-' (shrink) header buttons.

    State transitions are governed by Use Case 25. Cross-panel coordination
    (e.g. maximizing one panel temp-minimizes others) is handled by the
    :class:`MainWindow` owner.
    """

    toggled = Signal(bool)

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self._state = PanelState.NORMAL
        self.setStyleSheet(
            """
            QWidget#panelHeaderRow {
                background-color: transparent;
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

        # Plain QWidget header – no click-to-toggle (spec-neutralized).
        self.header_row = QWidget()
        self.header_row.setObjectName("panelHeaderRow")
        header_layout = QHBoxLayout(self.header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        # '-' button: always shows "-", disabled when panel cannot shrink further
        self.minimize_button = QToolButton()
        self.minimize_button.setObjectName("panelMinimize")
        self.minimize_button.setToolTip("Shrink pane")
        self.minimize_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.minimize_button.setFixedSize(20, 20)
        self.minimize_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(14)
        self.minimize_button.setFont(font)
        self.minimize_button.setText("-")
        self.minimize_button.setStyleSheet(
            """
            QToolButton#panelMinimize {
                border: none;
                padding: 2px;
                color: palette(button-text);
            }
            QToolButton#panelMinimize:hover {
                background-color: palette(midlight);
            }
            """
        )
        header_layout.addWidget(self.minimize_button)

        # '+' button: always shows "+", disabled when panel cannot grow further
        self.maximize_button = QToolButton()
        self.maximize_button.setObjectName("panelMaximize")
        self.maximize_button.setToolTip("Grow pane")
        self.maximize_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.maximize_button.setFixedSize(20, 20)
        self.maximize_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.maximize_button.setFont(font)
        self.maximize_button.setText("+")
        self.maximize_button.setStyleSheet(
            """
            QToolButton#panelMaximize {
                border: none;
                padding: 2px;
                color: palette(button-text);
            }
            QToolButton#panelMaximize:hover {
                background-color: palette(midlight);
            }
            """
        )
        header_layout.addWidget(self.maximize_button)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("panelTitle")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.title_label)
        layout.addWidget(self.header_row)

        self.body_frame = QFrame()
        self.body_frame.setObjectName("panelBody")
        body_layout = QVBoxLayout(self.body_frame)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(8)

        self.content = QWidget()
        body_layout.addWidget(self.content)
        layout.addWidget(self.body_frame)

        self._update_button_states()

    # ── Public state API ────────────────────────────────────────────────

    @property
    def title(self) -> str:
        """Panel header title text."""
        return self.title_label.text()

    @property
    def state(self) -> PanelState:
        """Current panel state (maximized / normal / minimized / temporary minimised)."""
        return self._state

    def set_state(self, value: PanelState) -> None:
        """Set a new panel state and update the body visibility accordingly."""
        self._state = value
        expanded = value in (PanelState.MAXIMIZED, PanelState.NORMAL)
        self.body_frame.setVisible(expanded)
        self._update_button_states()
        self.toggled.emit(expanded)

    # ── Derived convenience properties ──────────────────────────────────

    @property
    def expanded(self) -> bool:
        """True when the panel body is visible (maximized or normal)."""
        return self._state in (PanelState.MAXIMIZED, PanelState.NORMAL)

    @property
    def collapsed(self) -> bool:
        """True when the panel body is hidden (minimized or temporary minimised)."""
        return not self.expanded

    # ── Layout helpers ──────────────────────────────────────────────────

    def header_height(self) -> int:
        """Height of the header row including layout margins."""
        margins = self.layout().contentsMargins()
        return self.header_row.sizeHint().height() + margins.top() + margins.bottom()

    # ── Grow / shrink logic ─────────────────────────────────────────────

    def can_grow(self) -> bool:
        """Whether '+' is enabled – disabled only when maximized."""
        return self._state != PanelState.MAXIMIZED

    def can_shrink(self) -> bool:
        """Whether '-' is enabled – disabled when minimized (either kind)."""
        return self._state not in (PanelState.MINIMIZED, PanelState.TEMPORARY_MINIMIZED)

    def grow(self) -> None:
        """Handle a '+' click on this panel (local transition only).

        Cross-panel side effects (temp-minimizing other panels) are the
        caller's responsibility.
        """
        if self._state in (PanelState.MINIMIZED, PanelState.TEMPORARY_MINIMIZED):
            self.set_state(PanelState.NORMAL)
        elif self._state == PanelState.NORMAL:
            self.set_state(PanelState.MAXIMIZED)
        # MAXIMIZED: no-op (button is disabled)

    def shrink(self) -> None:
        """Handle a '-' click on this panel (local transition only)."""
        if self._state == PanelState.MAXIMIZED:
            self.set_state(PanelState.NORMAL)
        elif self._state == PanelState.NORMAL:
            self.set_state(PanelState.MINIMIZED)
        # MINIMIZED / TEMPORARY_MINIMIZED: no-op (button is disabled)

    # ── Compatibility shim ──────────────────────────────────────────────

    def set_expanded(self, expanded: bool) -> None:
        """Legacy compatibility – maps to the state model.

        Expanded  → NORMAL
        Collapsed → MINIMIZED
        """
        if expanded:
            self.set_state(PanelState.NORMAL)
        else:
            self.set_state(PanelState.MINIMIZED)

    # ── Internal helpers ────────────────────────────────────────────────

    def _update_button_states(self) -> None:
        """Refresh '+' / '-' enabled state to match current panel state."""
        self.maximize_button.setEnabled(self.can_grow())
        self.minimize_button.setEnabled(self.can_shrink())
