"""
Graph Panel — placeholder for live measurement plots.

This is a stub that reserves screen space and shows placeholder axes.
Full graph logic (Seebeck V1 vs V2 fit, T1/T2 vs time, σ vs T, etc.)
will be wired in a later iteration.
"""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class GraphPanel(QGroupBox):
    """Right-side panel reserved for live measurement graphs."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(title, parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 20, 8, 8)

        placeholder = QLabel("Graph area\n(will be populated during measurement)")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            "color: #666680; font-style: italic; font-size: 12px; background: transparent;"
        )
        layout.addWidget(placeholder)
