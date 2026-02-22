"""Single graph panel widget with header, maximize button, and pyqtgraph plot."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore    import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from gui.styles import (
    BG_PRIMARY, BG_PANEL, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER,
)

# Axis labels and tick text need to be clearly legible on the dark
# (BG_PRIMARY = #1A1A1A) plot background, so we use TEXT_PRIMARY.
_AXIS_COLOR = TEXT_PRIMARY


class GraphPanel(QWidget):
    """A titled graph panel with an optional maximize button.

    Signals
    -------
    maximize_requested()
        Emitted when the user clicks the ⛶ button.
    """

    maximize_requested = Signal()

    def __init__(self, title: str, x_label: str, y_label: str,
                 x_unit: str = "", y_unit: str = "", parent=None):
        super().__init__(parent)
        self._title   = title
        self._x_label = x_label
        self._y_label = y_label
        self._x_unit  = x_unit
        self._y_unit  = y_unit
        self._build_ui()

    # ── Private builders ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_plot(), stretch=1)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("SectionHeader")
        header.setFixedHeight(32)

        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 0, 6, 0)
        hl.setSpacing(6)

        title_lbl = QLabel(self._title)
        title_lbl.setObjectName("SectionLabel")

        self._max_btn = QPushButton("⛶")
        self._max_btn.setObjectName("IconButton")
        self._max_btn.setToolTip("Maximize this graph")
        self._max_btn.setCursor(Qt.PointingHandCursor)
        self._max_btn.clicked.connect(self.maximize_requested)

        hl.addWidget(title_lbl)
        hl.addStretch()
        hl.addWidget(self._max_btn)

        return header

    def _build_plot(self) -> pg.PlotWidget:
        self._plot = pg.PlotWidget()
        self._plot.setBackground(BG_PRIMARY)

        # Axes
        x_axis = self._plot.getAxis("bottom")
        y_axis = self._plot.getAxis("left")

        x_text = f"{self._x_label} ({self._x_unit})" if self._x_unit else self._x_label
        y_text = f"{self._y_label} ({self._y_unit})" if self._y_unit else self._y_label

        x_axis.setLabel(x_text, color=_AXIS_COLOR)
        y_axis.setLabel(y_text, color=_AXIS_COLOR)
        x_axis.setTextPen(_AXIS_COLOR)
        y_axis.setTextPen(_AXIS_COLOR)

        for spine in ("top", "right"):
            self._plot.showAxis(spine)
            self._plot.getAxis(spine).setTicks([])
            self._plot.getAxis(spine).setStyle(showValues=False)

        self._plot.getAxis("bottom").setPen(TEXT_SECONDARY)
        self._plot.getAxis("left").setPen(TEXT_SECONDARY)
        self._plot.getAxis("top").setPen(BORDER)
        self._plot.getAxis("right").setPen(BORDER)

        # Grid
        self._plot.showGrid(x=True, y=True, alpha=0.15)

        # Data curve
        pen = pg.mkPen(color=ACCENT, width=2)
        self._curve = self._plot.plot([], [], pen=pen, symbol="o",
                                      symbolSize=5, symbolBrush=ACCENT,
                                      symbolPen="w")

        return self._plot

    # ── Public API ────────────────────────────────────────────────────────

    def append_point(self, x: float, y: float):
        """Add a single (x, y) data point to the curve."""
        xd, yd = self._curve.getData()
        if xd is None:
            xd, yd = np.array([x]), np.array([y])
        else:
            xd = np.append(xd, x)
            yd = np.append(yd, y)
        self._curve.setData(xd, yd)

    def set_data(self, x, y):
        """Replace the entire dataset."""
        self._curve.setData(np.asarray(x), np.asarray(y))

    def clear_data(self):
        """Remove all plotted points."""
        self._curve.setData([], [])
