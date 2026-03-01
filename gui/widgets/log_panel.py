"""Log Panel — timestamped messages at the bottom of the window.

Resized via the vertical splitter in MainWindow.  A collapse button
in the header lets the user toggle the log area visibility.
"""

from datetime import datetime
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton,
)


class LogPanel(QWidget):
    """Read-only scrollable log area with Clear and Collapse buttons.

    Signals
    -------
    collapse_requested()
        Emitted when the user clicks the ▲/▼ toggle button.
    """

    collapse_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("SectionHeader")
        header.setFixedHeight(24)

        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 0, 6, 0)

        # Collapse / expand toggle
        self._toggle_btn = QPushButton("\u25bc")
        self._toggle_btn.setObjectName("IconButton")
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setToolTip("Collapse log panel")
        self._toggle_btn.setFixedSize(20, 18)
        self._toggle_btn.clicked.connect(self.collapse_requested)
        hl.addWidget(self._toggle_btn)

        log_lbl = QLabel("LOG")
        log_lbl.setObjectName("SectionLabel")
        hl.addWidget(log_lbl)
        hl.addStretch()

        # Clear button — small, unobtrusive
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("LogClearButton")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setToolTip("Clear all log messages")
        self._clear_btn.setFixedHeight(18)
        self._clear_btn.clicked.connect(self.clear)
        hl.addWidget(self._clear_btn)

        root.addWidget(header)

        # Text area
        self.text_area = QPlainTextEdit()
        self.text_area.setObjectName("LogArea")
        self.text_area.setReadOnly(True)
        self.text_area.setMaximumBlockCount(2000)
        root.addWidget(self.text_area, stretch=1)

    # ── Public API ────────────────────────────────────────────────────────

    @Slot(str)
    def append(self, message: str):
        """Add a timestamped line and scroll to the bottom."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.text_area.appendPlainText(f"[{ts}]  {message}")

    def clear(self):
        """Remove all messages from the log area."""
        # Reset maximumBlockCount around clear to work around a Qt quirk
        # where appendPlainText stops working after clear() with a max set.
        self.text_area.setMaximumBlockCount(0)
        self.text_area.clear()
        self.text_area.setMaximumBlockCount(2000)

    def set_collapsed(self, collapsed: bool):
        """Update the toggle button icon to match collapsed state."""
        self._collapsed = collapsed
        if collapsed:
            self._toggle_btn.setText("\u25b2")
            self._toggle_btn.setToolTip("Expand log panel")
        else:
            self._toggle_btn.setText("\u25bc")
            self._toggle_btn.setToolTip("Collapse log panel")
