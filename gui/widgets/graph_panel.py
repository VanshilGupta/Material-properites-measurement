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
    SUCCESS, DANGER,
)

# Axis labels and tick text need to be clearly legible on the dark
# (BG_PRIMARY = #1A1A1A) plot background, so we use TEXT_PRIMARY.
_AXIS_COLOR = TEXT_PRIMARY

# Palette for extra curves (index 0 = default ACCENT, 1+ = extras).
_CURVE_COLORS = [
    "#E06B67",   # warm red
    "#5B9BD5",   # blue (same as ACCENT)
    "#4EC94E",   # green
    "#D4A84D",   # amber
]


class GraphPanel(QWidget):
    """A titled graph panel with an optional maximize button.

    Supports multiple named curves via ``add_curve()`` / ``append_to()``.

    Signals
    -------
    maximize_requested()
        Emitted when the user clicks the ⛶ button.
    """

    maximize_requested = Signal()

    def __init__(self, title: str, x_label: str, y_label: str,
                 x_unit: str = "", y_unit: str = "",
                 curves: list[tuple[str, str]] | None = None,
                 parent=None):
        """
        Parameters
        ----------
        title, x_label, y_label, x_unit, y_unit
            Axis / header labels.
        curves
            Optional list of ``(name, colour)`` tuples for multi-curve.
            If *None*, a single default ACCENT curve is created.
        """
        super().__init__(parent)
        self._title   = title
        self._x_label = x_label
        self._y_label = y_label
        self._x_unit  = x_unit
        self._y_unit  = y_unit
        self._curve_specs = curves  # [(name, colour), …] or None
        self._named_curves: dict[str, pg.PlotDataItem] = {}
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

        # Create curves
        if self._curve_specs:
            # Multi-curve mode: create named curves with legend
            self._plot.addLegend(
                offset=(10, 10),
                brush=pg.mkBrush(color=(30, 30, 30, 180)),
                pen=pg.mkPen(color=BORDER),
            )
            for name, colour in self._curve_specs:
                pen = pg.mkPen(color=colour, width=2)
                curve = self._plot.plot([], [], pen=pen, symbol="o",
                                        symbolSize=3, symbolBrush=colour,
                                        symbolPen=colour, name=name)
                self._named_curves[name] = curve
            # Default single-curve API points to the first curve
            self._curve = list(self._named_curves.values())[0]
        else:
            # Single-curve mode (backward-compatible)
            pen = pg.mkPen(color=ACCENT, width=2)
            self._curve = self._plot.plot([], [], pen=pen, symbol="o",
                                          symbolSize=5, symbolBrush=ACCENT,
                                          symbolPen="w")

        return self._plot

    # ── Public API ────────────────────────────────────────────────────────

    def append_point(self, x: float, y: float):
        """Add a single (x, y) data point to the default curve."""
        self._append_to_curve(self._curve, x, y)

    def append_to(self, curve_name: str, x: float, y: float):
        """Add a data point to a named curve."""
        curve = self._named_curves.get(curve_name)
        if curve is not None:
            self._append_to_curve(curve, x, y)

    def set_data(self, x, y):
        """Replace the entire dataset of the default curve."""
        self._curve.setData(np.asarray(x), np.asarray(y))

    def clear_data(self):
        """Remove all plotted points from all curves."""
        self._curve.setData([], [])
        for c in self._named_curves.values():
            c.setData([], [])

    # ── Internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _append_to_curve(curve: pg.PlotDataItem, x: float, y: float):
        xd, yd = curve.getData()
        if xd is None:
            xd, yd = np.array([x]), np.array([y])
        else:
            xd = np.append(xd, x)
            yd = np.append(yd, y)
        curve.setData(xd, yd)
