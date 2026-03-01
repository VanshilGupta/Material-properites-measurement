"""Log Panel — timestamped messages at the bottom of the window.

Resized via the vertical splitter in MainWindow.  No collapse button;
the user resizes or hides the log by dragging the splitter.
"""

from datetime import datetime
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton,
)


class LogPanel(QWidget):
    """Read-only scrollable log area with a Clear button."""

    def __init__(self, parent=None):
        super().__init__(parent)
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
