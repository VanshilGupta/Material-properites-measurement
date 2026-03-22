"""Single graph panel widget with header, maximize button, and pyqtgraph plot."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore    import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QApplication,
)
from PySide6.QtGui import QImage, QPainter
from gui.styles import (
    BG_PRIMARY, BG_PANEL, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER,
    SUCCESS, DANGER,
)

# Axis label styling for all graph panels.
_LABEL_STYLE = {"color": "#FFFFFF", "font-size": "13px", "font-weight": "bold"}

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

        # Export buttons — small icon-style buttons
        self._save_png_btn = QPushButton("\U0001F4E5")  # 📥
        self._save_png_btn.setObjectName("IconButton")
        self._save_png_btn.setToolTip("Save graph as PNG")
        self._save_png_btn.setCursor(Qt.PointingHandCursor)
        self._save_png_btn.setFixedSize(26, 22)
        self._save_png_btn.clicked.connect(self._export_png)

        self._save_csv_btn = QPushButton("\U0001F4CA")  # 📊
        self._save_csv_btn.setObjectName("IconButton")
        self._save_csv_btn.setToolTip("Save plotted data as CSV")
        self._save_csv_btn.setCursor(Qt.PointingHandCursor)
        self._save_csv_btn.setFixedSize(26, 22)
        self._save_csv_btn.clicked.connect(self._export_csv)

        self._copy_btn = QPushButton("\U0001F4CB")  # 📋
        self._copy_btn.setObjectName("IconButton")
        self._copy_btn.setToolTip("Copy graph to clipboard")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.setFixedSize(26, 22)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)

        self._max_btn = QPushButton("\u26f6")
        self._max_btn.setObjectName("IconButton")
        self._max_btn.setToolTip("Maximize this graph")
        self._max_btn.setCursor(Qt.PointingHandCursor)
        self._max_btn.clicked.connect(self.maximize_requested)

        hl.addWidget(title_lbl)
        hl.addStretch()
        hl.addWidget(self._save_png_btn)
        hl.addWidget(self._save_csv_btn)
        hl.addWidget(self._copy_btn)
        hl.addWidget(self._max_btn)

        return header

    def _build_plot(self) -> pg.PlotWidget:
        self._plot = pg.PlotWidget()
        self._plot.setBackground(BG_PRIMARY)

        # Axes — bold white labels for readability on dark background
        x_axis = self._plot.getAxis("bottom")
        y_axis = self._plot.getAxis("left")

        x_text = f"{self._x_label} ({self._x_unit})" if self._x_unit else self._x_label
        y_text = f"{self._y_label} ({self._y_unit})" if self._y_unit else self._y_label

        x_axis.setLabel(x_text, **_LABEL_STYLE)
        y_axis.setLabel(y_text, **_LABEL_STYLE)

        # Tick label font: white, slightly larger
        tick_font = pg.QtGui.QFont("Segoe UI", 10)
        x_axis.setTickFont(tick_font)
        y_axis.setTickFont(tick_font)
        x_axis.setTextPen("#FFFFFF")
        y_axis.setTextPen("#FFFFFF")

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

        # ── Crosshair + tooltip on hover ──────────────────────────────
        self._vline = pg.InfiniteLine(angle=90, movable=False,
                                      pen=pg.mkPen("#ffffff", width=1, style=Qt.DashLine))
        self._hline = pg.InfiniteLine(angle=0, movable=False,
                                      pen=pg.mkPen("#ffffff", width=1, style=Qt.DashLine))
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        self._plot.addItem(self._vline, ignoreBounds=True)
        self._plot.addItem(self._hline, ignoreBounds=True)

        self._tooltip = pg.TextItem(color="#FFFFFF", anchor=(0, 1))
        self._tooltip.setVisible(False)
        self._plot.addItem(self._tooltip, ignoreBounds=True)

        self._proxy = pg.SignalProxy(
            self._plot.scene().sigMouseMoved, rateLimit=60,
            slot=self._on_mouse_moved,
        )

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

        self._ref_lines: list[pg.InfiniteLine] = []

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

    def set_data_named(self, curve_name: str, x, y):
        """Replace the entire dataset of a named curve."""
        curve = self._named_curves.get(curve_name)
        if curve is not None:
            curve.setData(np.asarray(x), np.asarray(y))

    def add_horizontal_line(self, y: float, pen=None,
                            label: str = "") -> pg.InfiniteLine:
        """Add a horizontal reference line at *y*."""
        if pen is None:
            pen = pg.mkPen(color="#FFFFFF", width=1, style=Qt.DashLine)
        line = pg.InfiniteLine(
            pos=y, angle=0, pen=pen,
            label=label, labelOpts={"color": "#FFFFFF"},
        )
        self._plot.addItem(line)
        self._ref_lines.append(line)
        return line

    def clear_reference_lines(self):
        """Remove all reference lines previously added."""
        for line in self._ref_lines:
            self._plot.removeItem(line)
        self._ref_lines.clear()

    def clear_data(self):
        """Remove all plotted points, reference lines, from all curves."""
        self._curve.setData([], [])
        for c in self._named_curves.values():
            c.setData([], [])
        self.clear_reference_lines()

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

    # ── Hover crosshair + tooltip ─────────────────────────────────────

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        vb = self._plot.plotItem.vb
        if not self._plot.sceneBoundingRect().contains(pos):
            self._vline.setVisible(False)
            self._hline.setVisible(False)
            self._tooltip.setVisible(False)
            return

        mouse_point = vb.mapSceneToView(pos)
        x, y = mouse_point.x(), mouse_point.y()

        self._vline.setPos(x)
        self._hline.setPos(y)
        self._vline.setVisible(True)
        self._hline.setVisible(True)

        # Collect all visible curves
        curves = (list(self._named_curves.items())
                  if self._named_curves else [("value", self._curve)])

        # First pass — find the nearest x across every curve
        nearest_x = None
        best_dist = float("inf")
        for _name, curve in curves:
            xd, _yd = curve.getData()
            if xd is None or len(xd) == 0:
                continue
            idx = int(np.argmin(np.abs(xd - x)))
            dist = abs(xd[idx] - x)
            if dist < best_dist:
                best_dist = dist
                nearest_x = xd[idx]

        if nearest_x is None:
            self._tooltip.setVisible(False)
            return

        # Second pass — show every curve's value at *nearest_x*
        x_unit = self._x_unit or ""
        y_unit = self._y_unit or ""
        lines = [f"{self._x_label}: {nearest_x:.2f} {x_unit}"]
        for name, curve in curves:
            xd, yd = curve.getData()
            if xd is None or len(xd) == 0:
                continue
            idx = int(np.argmin(np.abs(xd - nearest_x)))
            display_name = name if name != "value" else self._y_label
            lines.append(f"  {display_name}: {yd[idx]:.2f} {y_unit}")

        self._tooltip.setText("\n".join(lines))
        self._tooltip.setPos(x, y)
        self._tooltip.setVisible(True)

    # ── Export helpers ─────────────────────────────────────────────────────

    def _export_png(self):
        """Save the current plot as a PNG file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Graph as PNG",
            f"{self._title.replace(' ', '_')}.png",
            "PNG Images (*.png);;All Files (*)",
        )
        if path:
            try:
                import pyqtgraph.exporters
                exporter = pyqtgraph.exporters.ImageExporter(
                    self._plot.plotItem
                )
                exporter.parameters()['width'] = 1200
                exporter.export(path)
            except Exception:
                # Fallback: grab the widget as an image
                pixmap = self._plot.grab()
                pixmap.save(path, "PNG")

    def _export_csv(self):
        """Export plotted data to a CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Graph Data as CSV",
            f"{self._title.replace(' ', '_')}_data.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        import csv
        x_hdr = self._x_label
        curves = (list(self._named_curves.items())
                  if self._named_curves else [(self._y_label, self._curve)])

        # Gather all data
        all_x = None
        columns = {}
        for name, curve in curves:
            xd, yd = curve.getData()
            if xd is None or len(xd) == 0:
                continue
            if all_x is None:
                all_x = xd
            columns[name] = yd

        if all_x is None:
            return

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([x_hdr] + list(columns.keys()))
            for i in range(len(all_x)):
                row = [all_x[i]]
                for col in columns.values():
                    row.append(col[i] if i < len(col) else "")
                writer.writerow(row)

    def _copy_to_clipboard(self):
        """Copy the plot image to the system clipboard."""
        pixmap = self._plot.grab()
        QApplication.clipboard().setPixmap(pixmap)
