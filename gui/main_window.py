"""
Main Window — two-panel layout with smart splitter-based collapse.

Layout
------
+------------------------------------------------------------+
|  [Logo]          Equipment Name                     [Exit]  |  TopBar
+------------------------------------------------------------+
| <| Config (left, >300px)    |  S vs T graph (pyqtgraph)    |
|   | 1. Sample Info          |                               |
|   | 2. Method Configuration |-------------------------------+
|   | 3. Temperature Profile  |  sigma vs T graph (pyqtgraph) |
|   |                         |                               |
|   | 4. STATUS & EXECUTION   |                               |
+------------------------------------------------------------+
|  LOG  (resizable via splitter)                              |
+------------------------------------------------------------+
|  Status bar                                                 |
+------------------------------------------------------------+

Collapse behaviour
------------------
* The horizontal splitter lets the user resize the left panel.
* If the left panel is dragged below a threshold (200 px) it
  snaps shut (auto-collapse).  The splitter handle disappears
  so it cannot be reopened by dragging.
* A persistent arrow button (always visible) restores the panel.
"""

import pathlib
import pyqtgraph as pg
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QMessageBox,
    QApplication, QSplitter, QScrollArea, QToolTip,
    QDialog, QFrame, QGridLayout, QStackedWidget,
    QFileDialog,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QSettings

from gui.styles import (
    STYLESHEET, TEXT_SECONDARY, SUCCESS,
    ACCENT, DANGER, BORDER,
)
from gui.widgets import (
    SampleInfoPanel,
    TemperatureProfilePanel,
    MethodConfigPanel,
    GraphPanel,
    LogPanel,
)
from gui.backend import EurothermService, MeasurementService

_GUI_DIR   = pathlib.Path(__file__).resolve().parent
_ROOT_DIR  = _GUI_DIR.parent
_ASSET_DIR = _ROOT_DIR / "assets"

_LEFT_INITIAL_FRAC  = 0.50   # fraction of window width for left panel on startup
_LEFT_MAX_FRAC      = 0.70   # splitter can go beyond but inputs stop growing here
_LEFT_MIN_THRESHOLD = 200    # px — below this, auto-collapse kicks in
_COLLAPSE_STRIP_W   = 28     # px — width of the always-visible arrow strip


# ===========================================================================
# Pre-flight confirmation dialog
# ===========================================================================

class _MeasurementConfirmDialog(QDialog):
    """Structured summary dialog shown before any measurement run.

    Lets the operator review sample details, selected measurements,
    and temperature mode before committing to a run.
    """

    def __init__(self, m_cfg: dict, t_cfg: dict,
                 sample_name: str, diameter: float, thickness: float,
                 current_temp: float = None, output_dir: str = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Measurement")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._build_ui(m_cfg, t_cfg, sample_name, diameter, thickness,
                       current_temp, output_dir)

    def _build_ui(self, m_cfg, t_cfg, name, dia, thk, current_temp, output_dir):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(0)

        # ── Title ────────────────────────────────────────────────
        title_lbl = QLabel("Confirm Measurement")
        title_lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #FFFFFF; "
            "background: transparent; padding-bottom: 2px;"
        )
        root.addWidget(title_lbl)

        sub_lbl = QLabel("Review details before starting the run.")
        sub_lbl.setStyleSheet(
            f"font-size: 11px; color: {TEXT_SECONDARY}; background: transparent;"
        )
        root.addWidget(sub_lbl)
        root.addSpacing(18)

        # ── SAMPLE ────────────────────────────────────────────────
        root.addWidget(self._make_section_label("SAMPLE"))
        sample_grid = QGridLayout()
        sample_grid.setContentsMargins(0, 6, 0, 0)
        sample_grid.setHorizontalSpacing(20)
        sample_grid.setVerticalSpacing(4)
        self._add_row(sample_grid, 0, "Name",      name)
        self._add_row(sample_grid, 1, "Diameter",  f"{dia:.2f} mm")
        self._add_row(sample_grid, 2, "Thickness", f"{thk:.2f} mm")
        root.addLayout(sample_grid)
        root.addSpacing(16)

        # ── TEMPERATURE ───────────────────────────────────────────
        if current_temp is not None:
            root.addWidget(self._make_section_label("TEMPERATURE"))
            temp_col = QVBoxLayout()
            temp_col.setContentsMargins(0, 6, 0, 0)
            temp_col.setSpacing(4)

            if m_cfg["cycle_mode"]:
                start = t_cfg["start_temp"]
                stop  = t_cfg["stop_temp"]
                step  = int(t_cfg["step"])
                temps = list(range(int(start), int(stop) + 1, step)) if step > 0 else [int(start)]
                temp_str = ", ".join(f"{t} °C" for t in temps)
                temp_col.addWidget(self._make_value_label(f"▸  {temp_str}"))
            else:
                temp_col.addWidget(
                    self._make_value_label(f"▸  {current_temp:.1f} °C  (current)")
                )
            root.addLayout(temp_col)
            root.addSpacing(16)

        # ── MEASUREMENTS ──────────────────────────────────────────
        root.addWidget(self._make_section_label("MEASUREMENTS"))
        meas_col = QVBoxLayout()
        meas_col.setContentsMargins(0, 6, 0, 0)
        meas_col.setSpacing(4)
        if m_cfg["measure_conductivity"]:
            meas_col.addWidget(self._make_value_label("▸  Electrical Conductivity (σ)"))
        if m_cfg["measure_seebeck"]:
            meas_col.addWidget(self._make_value_label("▸  Seebeck Coefficient (S)"))
        root.addLayout(meas_col)
        root.addSpacing(16)

        # ── MODE ─────────────────────────────────────────────────
        root.addWidget(self._make_section_label("MODE"))
        mode_col = QVBoxLayout()
        mode_col.setContentsMargins(0, 6, 0, 0)
        mode_col.setSpacing(4)

        if m_cfg["cycle_mode"]:
            direction = "Heating Only" if m_cfg["heating_only"] else "Heating + Cooling"
            mode_col.addWidget(self._make_value_label("Temperature Cycle"))
            cycle_grid = QGridLayout()
            cycle_grid.setContentsMargins(0, 4, 0, 0)
            cycle_grid.setHorizontalSpacing(20)
            cycle_grid.setVerticalSpacing(4)
            self._add_row(cycle_grid, 0, "Start",     f"{t_cfg['start_temp']:.0f} °C")
            self._add_row(cycle_grid, 1, "Stop",      f"{t_cfg['stop_temp']:.0f} °C")
            self._add_row(cycle_grid, 2, "Step",      f"{t_cfg['step']:.0f} °C")
            self._add_row(cycle_grid, 3, "Ramp Rate", f"{t_cfg['rate']:.1f} °C/min")
            self._add_row(cycle_grid, 4, "Direction", direction)
            mode_col.addLayout(cycle_grid)
        else:
            mode_col.addWidget(
                self._make_value_label("Single measurement at current temperature")
            )

        root.addLayout(mode_col)
        root.addSpacing(16)

        # ── DATA PATH ────────────────────────────────────────────
        root.addWidget(self._make_section_label("DATA PATH"))
        path_col = QVBoxLayout()
        path_col.setContentsMargins(0, 6, 0, 0)
        path_col.setSpacing(4)
        display_path = output_dir if output_dir else "./data/"
        path_lbl = QLabel(f"▸  {display_path}")
        path_lbl.setWordWrap(True)
        path_lbl.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; background: transparent;"
        )
        path_col.addWidget(path_lbl)
        root.addLayout(path_col)
        root.addSpacing(22)

        # ── Divider ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        root.addWidget(sep)
        root.addSpacing(14)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("ExitButton")
        cancel_btn.setFixedWidth(90)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        btn_row.addSpacing(10)

        start_btn = QPushButton("▶  Start Run")
        start_btn.setObjectName("RunButton")
        start_btn.setFixedWidth(140)
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.clicked.connect(self.accept)
        btn_row.addWidget(start_btn)

        root.addLayout(btn_row)

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _make_section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; letter-spacing: 1.5px; "
            f"color: {TEXT_SECONDARY}; background: transparent;"
        )
        return lbl

    @staticmethod
    def _make_value_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; background: transparent;"
        )
        return lbl

    @staticmethod
    def _add_row(grid: QGridLayout, row: int, key: str, value: str):
        key_lbl = QLabel(key)
        key_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet("color: #E8E8E8; font-weight: bold; background: transparent;")
        grid.addWidget(key_lbl, row, 0)
        grid.addWidget(val_lbl, row, 1)


# ===========================================================================
# Measurement completion summary dialog
# ===========================================================================

class _MeasurementSummaryDialog(QDialog):
    """Summary dialog shown when a measurement finishes (success or failure)."""

    def __init__(self, success: bool, summary: str,
                 metadata: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Measurement Complete" if success else "Measurement Failed")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._build_ui(success, summary, metadata or {})

    def _build_ui(self, success: bool, summary: str, meta: dict):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(0)

        # ── Icon & Title ─────────────────────────────────────────
        icon = "\u2714" if success else "\u2716"
        colour = SUCCESS if success else DANGER
        title_text = "Measurement Complete" if success else "Measurement Failed"

        title_lbl = QLabel(f"{icon}  {title_text}")
        title_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {colour}; "
            "background: transparent; padding-bottom: 2px;"
        )
        root.addWidget(title_lbl)
        root.addSpacing(16)

        # ── Results ──────────────────────────────────────────────
        root.addWidget(self._make_section_label("RESULTS"))
        results_col = QVBoxLayout()
        results_col.setContentsMargins(0, 6, 0, 0)
        results_col.setSpacing(6)

        for part in summary.split("\u2502"):
            part = part.strip()
            if part:
                val_lbl = QLabel(f"  {part}")
                val_lbl.setStyleSheet(
                    f"color: {ACCENT}; font-weight: bold; font-size: 13px; "
                    "background: transparent;"
                )
                results_col.addWidget(val_lbl)
        if not summary or summary == "No results":
            hint = QLabel("  No measurement results were produced.")
            hint.setStyleSheet(
                f"color: {TEXT_SECONDARY}; background: transparent;"
            )
            results_col.addWidget(hint)

        root.addLayout(results_col)

        # ── Details (temperature, path, timing) ──────────────────
        if meta:
            root.addSpacing(14)
            root.addWidget(self._make_section_label("DETAILS"))
            details_grid = QGridLayout()
            details_grid.setContentsMargins(0, 6, 0, 0)
            details_grid.setHorizontalSpacing(20)
            details_grid.setVerticalSpacing(4)
            row = 0
            if "temperature" in meta and meta["temperature"]:
                self._add_row(details_grid, row, "Temperature",
                              f"{meta['temperature']:.1f} \u00b0C")
                row += 1
            if meta.get("sigma_elapsed", 0) > 0:
                self._add_row(details_grid, row, "\u03c3 time",
                              f"{meta['sigma_elapsed']:.1f} s")
                row += 1
            if meta.get("seebeck_elapsed", 0) > 0:
                self._add_row(details_grid, row, "Seebeck time",
                              f"{meta['seebeck_elapsed']:.1f} s")
                row += 1
            if "total_elapsed" in meta:
                self._add_row(details_grid, row, "Total time",
                              f"{meta['total_elapsed']:.1f} s")
                row += 1
            if meta.get("data_path"):
                path_lbl = QLabel(str(meta["data_path"]))
                path_lbl.setWordWrap(True)
                path_lbl.setStyleSheet(
                    f"color: {TEXT_SECONDARY}; font-size: 11px; "
                    "background: transparent;"
                )
                self._add_row(details_grid, row, "Data saved", "")
                details_grid.addWidget(path_lbl, row, 1)
                row += 1
            root.addLayout(details_grid)

        root.addSpacing(22)

        # ── Divider ──────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        root.addWidget(sep)
        root.addSpacing(14)

        # ── Close button ─────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        close_btn = QPushButton("OK")
        close_btn.setObjectName("RunButton")
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        root.addLayout(btn_row)

    @staticmethod
    def _make_section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; letter-spacing: 1.5px; "
            f"color: {TEXT_SECONDARY}; background: transparent;"
        )
        return lbl

    @staticmethod
    def _add_row(grid: QGridLayout, row: int, key: str, value: str):
        key_lbl = QLabel(key)
        key_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            "color: #E8E8E8; font-weight: bold; background: transparent;"
        )
        grid.addWidget(key_lbl, row, 0)
        grid.addWidget(val_lbl, row, 1)


class _RunButton(QPushButton):
    """START RUN button that shows its tooltip even when disabled.

    Qt normally suppresses tooltip events for disabled widgets; this
    subclass forwards them so the user always sees why the button is off.
    """

    def event(self, e: QEvent) -> bool:
        if e.type() == QEvent.Type.ToolTip and not self.isEnabled():
            QToolTip.showText(e.globalPos(), self.toolTip(), self)
            return True
        return super().event(e)


class MainWindow(QMainWindow):
    """Top-level application window."""

    WINDOW_TITLE = "Thermoelectric Measurement System"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)

        self._left_collapsed   = False
        self._saved_left_width = 0   # set properly in showEvent
        self._measurement_running = False
        self._initial_split_done  = False

        # Backend
        self.eurotherm = EurothermService(self)
        # The cycle shares the Eurotherm's single COM-port connection.
        self.measurement_svc = MeasurementService(self, furnace=self.eurotherm)
        self._temp_read_count = 0   # throttle heartbeat log: print every 30 reads (≈30 s)

        # Instrument status tracking
        self._instrument_states: dict[str, str] = {
            "Eurotherm": "disconnected",
            "Power Supply": "idle",
            "Multimeter": "idle",
        }

        # Ramp state tracking
        self._ramp_target: float | None = None

        # Output folder (persisted via QSettings)
        self._settings = QSettings("ONS", "ThermoelectricMeasurement")
        self._output_dir: str | None = self._settings.value("output_dir", None)

        # Summary data for cycle mode (Seebeck vs Temp, Sigma vs Temp)
        # Each list stores (temp, value) tuples so they stay aligned even
        # when one measurement type fails at a particular temperature.
        self._summary_sigma: list[tuple[float, float]] = []
        self._summary_seebeck: list[tuple[float, float]] = []

        # Build
        self._build_top_bar()
        self._build_body()
        self._build_status_bar()
        self._connect_backend()

        # Connect to the Eurotherm furnace on startup.
        # The service runs on a background thread so this never blocks
        # the UI; if the furnace is unreachable an error_occurred signal
        # will update the log & status bar automatically.
        self.eurotherm.start()

    # ==================================================================
    # Top Bar
    # ==================================================================

    def _build_top_bar(self):
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(50)

        hl = QHBoxLayout(bar)
        hl.setContentsMargins(12, 4, 12, 4)

        # Logo
        logo_lbl = QLabel()
        logo_path = _ASSET_DIR / "logo.png"
        if logo_path.exists():
            pm = QPixmap(str(logo_path)).scaled(
                34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            logo_lbl.setPixmap(pm)
        else:
            logo_lbl.setText("\u269b")
            logo_lbl.setStyleSheet(
                "font-size: 24px; background: transparent; padding: 0 6px;"
            )
        hl.addWidget(logo_lbl)

        # Title (centred)
        title = QLabel(self.WINDOW_TITLE)
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        hl.addStretch()
        hl.addWidget(title)
        hl.addStretch()

        # Output folder button
        self._folder_btn = QPushButton("\U0001F4C1")
        self._folder_btn.setObjectName("IconButton")
        self._folder_btn.setToolTip(
            self._output_dir or "No output folder selected (using default)"
        )
        self._folder_btn.setCursor(Qt.PointingHandCursor)
        self._folder_btn.setFixedSize(34, 28)
        self._folder_btn.clicked.connect(self._on_select_output_folder)
        hl.addWidget(self._folder_btn)

        # Exit button
        exit_btn = QPushButton("Exit")
        exit_btn.setObjectName("ExitButton")
        exit_btn.setToolTip("Close the application")
        exit_btn.setCursor(Qt.PointingHandCursor)
        exit_btn.clicked.connect(self._on_exit)
        hl.addWidget(exit_btn)

        self.setMenuWidget(bar)

    # ==================================================================
    # Body
    # ==================================================================

    def _build_body(self):
        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Vertical splitter: body | log ────────────────────────────────
        self.v_splitter = QSplitter(Qt.Vertical)

        # ── Body row: collapse_strip + h_splitter ────────────────────────
        body_widget = QWidget()
        body_hl = QHBoxLayout(body_widget)
        body_hl.setContentsMargins(0, 0, 0, 0)
        body_hl.setSpacing(0)

        # Collapse strip (always visible, thin)
        collapse_strip = QWidget()
        collapse_strip.setFixedWidth(_COLLAPSE_STRIP_W)

        strip_vl = QVBoxLayout(collapse_strip)
        strip_vl.setContentsMargins(3, 8, 3, 8)
        strip_vl.setSpacing(0)

        self._collapse_btn = QPushButton("\u25c0")
        self._collapse_btn.setObjectName("IconButton")
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setToolTip("Collapse configuration panel")
        self._collapse_btn.clicked.connect(self._toggle_sidebar)

        strip_vl.addWidget(self._collapse_btn)
        strip_vl.addStretch()

        body_hl.addWidget(collapse_strip)

        # ── Horizontal splitter: left | right ────────────────────────────
        self.h_splitter = QSplitter(Qt.Horizontal)
        self.h_splitter.splitterMoved.connect(self._on_h_splitter_moved)

        # ── LEFT PANEL ───────────────────────────────────────────────────
        self._left_panel = QWidget()
        self._left_panel.setMinimumWidth(220)   # sensible collapse floor
        left_vl = QVBoxLayout(self._left_panel)
        left_vl.setContentsMargins(0, 0, 0, 0)
        left_vl.setSpacing(0)

        # Scrollable sections 1-3
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_vl = QVBoxLayout(scroll_content)
        # Right margin is deliberately larger so sections never merge with the
        # vertical scrollbar (7 px wide) — 20 px gives a comfortable buffer.
        scroll_vl.setContentsMargins(8, 10, 20, 10)
        scroll_vl.setSpacing(14)

        self.sample_panel = SampleInfoPanel()
        scroll_vl.addWidget(self.sample_panel)

        self.method_panel = MethodConfigPanel()
        scroll_vl.addWidget(self.method_panel)

        self.temp_panel = TemperatureProfilePanel()
        scroll_vl.addWidget(self.temp_panel)

        scroll_vl.addStretch()
        scroll.setWidget(scroll_content)
        left_vl.addWidget(scroll, stretch=1)

        # ── Section 4: STATUS & EXECUTION (pinned to bottom) ─────────────
        status_card = QWidget()
        status_card.setObjectName("StatusCard")
        status_vl = QVBoxLayout(status_card)
        status_vl.setContentsMargins(12, 10, 12, 12)
        status_vl.setSpacing(8)

        temp_header = QLabel("CURRENT TEMPERATURE")
        temp_header.setAlignment(Qt.AlignCenter)
        temp_header.setStyleSheet(
            f"font-size: 10px; font-weight: bold; letter-spacing: 1px; "
            f"color: {TEXT_SECONDARY}; background: transparent;"
        )
        status_vl.addWidget(temp_header)

        self.current_temp_lbl = QLabel("\u2014  \u00b0C")
        self.current_temp_lbl.setAlignment(Qt.AlignCenter)
        self.current_temp_lbl.setObjectName("CurrentTempValue")
        # Cap width so the value readout doesn't sprawl across a wide panel.
        self.current_temp_lbl.setMaximumWidth(220)
        # Centre it horizontally regardless of panel width.
        temp_val_row = QHBoxLayout()
        temp_val_row.addStretch()
        temp_val_row.addWidget(self.current_temp_lbl)
        temp_val_row.addStretch()
        status_vl.addLayout(temp_val_row)

        # Ramp indicator row
        self._ramp_indicator = QLabel("")
        self._ramp_indicator.setAlignment(Qt.AlignCenter)
        self._ramp_indicator.setStyleSheet(
            f"font-size: 11px; color: {ACCENT}; background: transparent;"
        )
        self._ramp_indicator.setVisible(False)
        status_vl.addWidget(self._ramp_indicator)

        self._stop_ramp_btn = QPushButton("\u25a0  Stop Ramp")
        self._stop_ramp_btn.setStyleSheet(
            f"background: {DANGER}; color: white; border-radius: 4px; "
            "padding: 3px 12px; font-size: 11px;"
        )
        self._stop_ramp_btn.setCursor(Qt.PointingHandCursor)
        self._stop_ramp_btn.setFixedHeight(24)
        self._stop_ramp_btn.setVisible(False)
        self._stop_ramp_btn.clicked.connect(self._on_stop_ramp)
        ramp_btn_row = QHBoxLayout()
        ramp_btn_row.addStretch()
        ramp_btn_row.addWidget(self._stop_ramp_btn)
        ramp_btn_row.addStretch()
        status_vl.addLayout(ramp_btn_row)

        self.run_btn = _RunButton("\u25b6  START RUN")
        self.run_btn.setObjectName("RunButton")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setEnabled(False)   # enabled only when all fields are valid
        self.run_btn.clicked.connect(self._on_run)

        self.abort_btn = QPushButton("\u25a0  ABORT")
        self.abort_btn.setObjectName("AbortButton")
        self.abort_btn.setCursor(Qt.PointingHandCursor)
        self.abort_btn.setToolTip("Stop the running measurement immediately")
        self.abort_btn.setVisible(False)
        self.abort_btn.clicked.connect(self._on_abort)

        # Centre the buttons regardless of panel width
        run_row = QHBoxLayout()
        run_row.addStretch()
        run_row.addWidget(self.run_btn)
        run_row.addStretch()
        status_vl.addLayout(run_row)

        abort_row = QHBoxLayout()
        abort_row.addStretch()
        abort_row.addWidget(self.abort_btn)
        abort_row.addStretch()
        status_vl.addLayout(abort_row)

        left_vl.addWidget(status_card)

        self.h_splitter.addWidget(self._left_panel)

        # ── RIGHT PANEL ──────────────────────────────────────────────────
        right = QWidget()
        right_vl = QVBoxLayout(right)
        right_vl.setContentsMargins(0, 0, 0, 0)
        right_vl.setSpacing(0)

        self.graph_stack = QStackedWidget()

        # ─── Page 0: Placeholder ─────────────────────────────────────
        placeholder = QWidget()
        ph_vl = QVBoxLayout(placeholder)
        ph_vl.setAlignment(Qt.AlignCenter)
        self._placeholder_label = QLabel(
            "Select a measurement type and\nclick START RUN to begin"
        )
        self._placeholder_label.setAlignment(Qt.AlignCenter)
        self._placeholder_label.setWordWrap(True)
        self._placeholder_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 14px; "
            "background: transparent; padding: 40px;"
        )
        ph_vl.addWidget(self._placeholder_label)
        self.graph_stack.addWidget(placeholder)  # index 0

        # ─── Page 1: Sigma view ──────────────────────────────────────
        sigma_view = QWidget()
        sigma_vl = QVBoxLayout(sigma_view)
        sigma_vl.setContentsMargins(0, 0, 0, 0)
        sigma_vl.setSpacing(0)

        self.sigma_graph_splitter = QSplitter(Qt.Vertical)
        sigma_vl.addWidget(self.sigma_graph_splitter, stretch=1)

        self.graph_sigma_iter = GraphPanel(
            title="Conductivity  (\u03c3 per Iteration)",
            x_label="Iteration", y_label="\u03c3",
            x_unit="", y_unit="S/cm",
            curves=[("\u03c3", "#5B9BD5")],
        )
        # make iterations plot as dots only
        c1 = self.graph_sigma_iter._named_curves["\u03c3"]
        c1.setSymbol("o")
        c1.setSymbolBrush("#5B9BD5")
        c1.setPen(None)

        self.graph_sigma_vs_temp = GraphPanel(
            title="Conductivity vs Temperature",
            x_label="Temperature", y_label="\u03c3",
            x_unit="\u00b0C", y_unit="S/cm",
            curves=[("\u03c3 vs T", "#4EC94E")],
        )
        c2 = self.graph_sigma_vs_temp._named_curves["\u03c3 vs T"]
        c2.setSymbol("o")
        c2.setSymbolBrush("#4EC94E")
        
        self.sigma_graph_splitter.addWidget(self.graph_sigma_iter)
        self.sigma_graph_splitter.addWidget(self.graph_sigma_vs_temp)
        self.sigma_graph_splitter.setStretchFactor(0, 1)
        self.sigma_graph_splitter.setStretchFactor(1, 1)
        
        self.graph_sigma_iter.maximize_requested.connect(
            lambda: self._toggle_sigma_maximize(0)
        )
        self.graph_sigma_vs_temp.maximize_requested.connect(
            lambda: self._toggle_sigma_maximize(1)
        )
        self.graph_stack.addWidget(sigma_view)  # index 1

        # ─── Page 2: Seebeck view ───────────────────────────────────
        seebeck_view = QWidget()
        seebeck_vl = QVBoxLayout(seebeck_view)
        seebeck_vl.setContentsMargins(0, 0, 0, 0)
        seebeck_vl.setSpacing(0)

        self.seebeck_graph_splitter = QSplitter(Qt.Vertical)

        self.graph_seebeck_t = GraphPanel(
            title="Temperature   (T\u2081 / T\u2082 vs Time)",
            x_label="Time", y_label="Temperature",
            x_unit="min", y_unit="\u00b0C",
            curves=[("T\u2081", "#E06B67"), ("T\u2082", "#5B9BD5")],
        )
        self.graph_seebeck_v = GraphPanel(
            title="Voltage   (V\u2081 / V\u2082 vs Time)",
            x_label="Time", y_label="Voltage",
            x_unit="min", y_unit="\u00b5V",
            curves=[("V\u2081", "#4EC94E"), ("V\u2082", "#F0A500")],
        )
        self.graph_seebeck_vs_temp = GraphPanel(
            title="Seebeck vs Temperature",
            x_label="Temperature", y_label="Seebeck Coefficient",
            x_unit="\u00b0C", y_unit="\u00b5V/K",
            curves=[("S vs T", "#F0A500")],
        )
        c3 = self.graph_seebeck_vs_temp._named_curves["S vs T"]
        c3.setSymbol("o")
        c3.setSymbolBrush("#F0A500")
        # V₁ vs V₂ fit graph — created now, added to splitter at seebeck end
        self.graph_fit = GraphPanel(
            title="V\u2081 vs V\u2082   (Seebeck Fit)",
            x_label="V\u2081", y_label="V\u2082",
            x_unit="\u00b5V", y_unit="\u00b5V",
            curves=[("Data", "#5B9BD5"), ("Fit", "#E06B67")],
        )
        self._fit_graph_added = False

        self.seebeck_graph_splitter.addWidget(self.graph_seebeck_t)
        self.seebeck_graph_splitter.addWidget(self.graph_seebeck_v)
        self.seebeck_graph_splitter.addWidget(self.graph_seebeck_vs_temp)
        self.seebeck_graph_splitter.setStretchFactor(0, 1)
        self.seebeck_graph_splitter.setStretchFactor(1, 1)
        self.seebeck_graph_splitter.setStretchFactor(2, 1)

        self.graph_seebeck_t.maximize_requested.connect(
            lambda: self._toggle_graph_maximize(0)
        )
        self.graph_seebeck_v.maximize_requested.connect(
            lambda: self._toggle_graph_maximize(1)
        )
        self.graph_seebeck_vs_temp.maximize_requested.connect(
            lambda: self._toggle_graph_maximize(2)
        )
        self.graph_fit.maximize_requested.connect(
            lambda: self._toggle_graph_maximize(3)
        )

        seebeck_vl.addWidget(self.seebeck_graph_splitter, stretch=1)
        self.graph_stack.addWidget(seebeck_view)  # index 2

        right_vl.addWidget(self.graph_stack, stretch=1)

        self.h_splitter.addWidget(right)
        self.h_splitter.setStretchFactor(0, 0)
        self.h_splitter.setStretchFactor(1, 1)
        # Initial sizes are set in showEvent once the window has a real geometry.
        # Put a temporary placeholder so Qt doesn't complain.
        self.h_splitter.setSizes([640, 640])

        body_hl.addWidget(self.h_splitter, stretch=1)

        self.v_splitter.addWidget(body_widget)

        # ── Log panel (bottom, resizable via splitter) ────────────────────
        self.log_panel = LogPanel()
        self.log_panel.collapse_requested.connect(self._toggle_log_panel)
        self.v_splitter.addWidget(self.log_panel)
        self.v_splitter.setStretchFactor(0, 5)
        self.v_splitter.setStretchFactor(1, 1)
        self.v_splitter.setSizes([560, 120])
        self._log_collapsed = False
        self._saved_log_height = 120

        outer.addWidget(self.v_splitter)

    # ==================================================================
    # Status Bar
    # ==================================================================

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_label = QLabel("Ready")
        sb.addWidget(self.status_label, stretch=1)

        # ── Instrument status indicators (right side) ─────────────────────
        # Each instrument gets a coloured dot (12 px) and a label with
        # generous spacing between groups — no separator lines.
        self._inst_dots: dict[str, QLabel] = {}
        self._inst_labels: dict[str, QLabel] = {}

        instruments = ("Eurotherm", "Power Supply", "Multimeter")
        for i, name in enumerate(instruments):
            # Spacer between groups (except before the first one)
            if i > 0:
                spacer = QLabel("")
                spacer.setFixedWidth(20)
                spacer.setStyleSheet("background: transparent;")
                sb.addPermanentWidget(spacer)

            dot = QLabel()
            dot.setProperty("class", "InstrumentDot")
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(
                f"min-width:12px; max-width:12px; min-height:12px; max-height:12px; "
                f"border-radius:6px; background:{BORDER};"
            )

            lbl = QLabel(name)
            lbl.setProperty("class", "InstrumentLabel")
            lbl.setStyleSheet(
                f"font-size:11px; color:{TEXT_SECONDARY}; background:transparent; "
                f"padding:0; margin-left:2px;"
            )

            self._inst_dots[name] = dot
            self._inst_labels[name] = lbl

            sb.addPermanentWidget(dot)
            sb.addPermanentWidget(lbl)

        # Right-side padding so the last label doesn't sit against the edge
        end_spacer = QLabel("")
        end_spacer.setFixedWidth(10)
        end_spacer.setStyleSheet("background: transparent;")
        sb.addPermanentWidget(end_spacer)

        self._refresh_instrument_dot("Eurotherm", "disconnected")

    # ==================================================================
    # Backend wiring
    # ==================================================================

    def _connect_backend(self):
        # Live temperature readout
        self.eurotherm.temperature_read.connect(self._update_current_temp)
        self.eurotherm.temperature_read_failed.connect(self._on_temp_read_failed)

        # SET T button -> backend
        self.temp_panel.set_temp_requested.connect(self._on_set_furnace)

        # Backend events
        self.eurotherm.error_occurred.connect(self._show_error)
        self.eurotherm.connection_changed.connect(self._on_connection_state)
        self.eurotherm.set_point_reached.connect(self._on_setpoint_sent)

        # Experiment mode toggle -> enable/disable cycle settings
        self.method_panel.mode_changed.connect(self.temp_panel.set_cycle_enabled)
        # Mode change also affects RUN button validity
        self.method_panel.mode_changed.connect(self._update_run_btn_state)

        # RUN button validation: re-check whenever relevant fields change
        self.sample_panel.sample_changed.connect(self._update_run_btn_state)
        self.method_panel.settings_changed.connect(self._update_run_btn_state)

        # ── Measurement service wiring ────────────────────────────────────
        self.measurement_svc.log_message.connect(self.log_panel.append)
        self.measurement_svc.status_message.connect(
            lambda msg: self.status_label.setText(msg)
        )
        self.measurement_svc.instrument_status.connect(self._on_instrument_status)
        self.measurement_svc.measurement_finished.connect(self._on_measurement_finished)
        self.measurement_svc.seebeck_data_point.connect(self._on_seebeck_data_point)
        self.measurement_svc.sigma_data_point.connect(self._on_sigma_data_point)
        self.measurement_svc.sigma_completed.connect(self._on_sigma_completed)
        self.measurement_svc.seebeck_fit_ready.connect(self._on_seebeck_fit_ready)
        self.measurement_svc.phase_changed.connect(self._on_phase_changed)
        
        self.measurement_svc.cycle_point_starting.connect(self._on_cycle_point_starting)
        self.measurement_svc.cycle_point_completed.connect(self._on_cycle_point_completed)

        # Update placeholder text when measurement checkboxes change
        self.method_panel.settings_changed.connect(self._update_graph_placeholder)

        # Set initial button state and tooltip immediately
        self._update_run_btn_state()
        self._update_graph_placeholder()

    # ==================================================================
    # Slot implementations
    # ==================================================================

    def _update_run_btn_state(self, *_):
        """Enable START RUN only when all required fields are valid.
        Updates the tooltip dynamically to explain what is missing.
        """
        name_ok = bool(self.sample_panel.get_sample_name())
        dia_ok  = self.sample_panel.get_diameter() > 0.0
        thk_ok  = self.sample_panel.get_thickness() > 0.0
        meas_ok = (
            self.method_panel.chk_seebeck.isChecked()
            or self.method_panel.chk_conductivity.isChecked()
        )
        # In Temperature Cycle mode a direction radio MUST be selected.
        is_cycle  = self.method_panel.is_cycle_mode()
        cycle_ok  = (
            not is_cycle
            or self.method_panel.radio_heat_only.isChecked()
            or self.method_panel.radio_heat_cool.isChecked()
        )
        # Disable RUN while temperature is ramping to a setpoint.
        ramp_ok = self._ramp_target is None

        can_run = name_ok and dia_ok and thk_ok and meas_ok and cycle_ok and ramp_ok
        self.run_btn.setEnabled(can_run)

        if can_run:
            self.run_btn.setToolTip("Start the measurement sequence")
        else:
            reasons = []
            if not name_ok:
                reasons.append("\u2022 Enter a sample name")
            if not dia_ok:
                reasons.append("\u2022 Enter sample diameter")
            if not thk_ok:
                reasons.append("\u2022 Enter sample thickness")
            if not cycle_ok:
                reasons.append("\u2022 Select Heating Only or Heating + Cooling")
            if not meas_ok:
                reasons.append("\u2022 Select at least one measurement (Seebeck or \u03c3)")
            if not ramp_ok:
                reasons.append("\u2022 Temperature ramp in progress")
            self.run_btn.setToolTip("Cannot start:\n" + "\n".join(reasons))

    def _update_current_temp(self, temp_c: float):
        self._last_known_temp = temp_c
        self.current_temp_lbl.setText(f"{temp_c:.1f}  \u00b0C")
        # Ramp indicator auto-clear when arrived
        if self._ramp_target is not None:
            if abs(temp_c - self._ramp_target) <= 2.0:
                # Arrived
                self._ramp_indicator.setVisible(False)
                self._stop_ramp_btn.setVisible(False)
                self._ramp_target = None
                self._update_run_btn_state()

        # Log a heartbeat every 30 successful reads (≈ every 30 s) so the
        # operator can confirm live polling without flooding the log panel.
        self._temp_read_count += 1
        if self._temp_read_count % 30 == 1:   # also fires on the very first read
            self.log_panel.append(
                f"[Eurotherm] T = {temp_c:.1f} \u00b0C  \u2713"
            )

    def _on_temp_read_failed(self):
        """Called when the controller responded but returned no usable value."""
        self.log_panel.append(
            "[Eurotherm] \u26a0 Temperature read failed — "
            "no valid response from controller"
        )
        self.status_label.setText("Eurotherm: read failed — check connection")

    def _on_set_furnace(self, target_c: float, rate: float):
        self.status_label.setText(
            f"Setting furnace \u2192 {target_c:.1f} \u00b0C  "
            f"@ {rate:.1f} \u00b0C/min \u2026"
        )
        # Update Ramp UI
        self._ramp_target = target_c
        msg = f"\u2b06 Ramping \u2192 {target_c:.1f} \u00b0C" if target_c > getattr(self,("_last_known_temp"), 0) else f"\u2b07 Cooling \u2192 {target_c:.1f} \u00b0C"
        self._ramp_indicator.setText(msg)
        self._ramp_indicator.setVisible(True)
        self._stop_ramp_btn.setVisible(True)
        self._update_run_btn_state() # Disable RUN while ramping

        self.log_panel.append(
            f"Setting furnace \u2192 {target_c:.1f} \u00b0C  "
            f"(ramp {rate:.1f} \u00b0C/min)"
        )
        # Send ramp rate first so the controller applies it before the setpoint.
        self.eurotherm.set_ramp_rate(rate)
        self.eurotherm.set_temperature(target_c)

    def _on_setpoint_sent(self, target_c: float):
        msg = f"Furnace set-point \u2192 {target_c:.1f} \u00b0C  \u2713"
        self.status_label.setText(msg)
        self.log_panel.append(msg)

    def _on_connection_state(self, connected: bool):
        state = "connected" if connected else "disconnected"
        msg = f"Eurotherm {state}"
        self.status_label.setText(msg)
        self.log_panel.append(msg)
        self._on_instrument_status("Eurotherm", state)

    def _show_error(self, msg: str):
        self.status_label.setText(f"Error: {msg}")
        self.log_panel.append(f"ERROR: {msg}")

    # -- GUI Utilities -------------------------------------------------

    def _on_stop_ramp(self):
        """Halt temperature ramping by setting the setpoint to current temp."""
        curr = getattr(self, "_last_known_temp", 25.0)
        self._ramp_target = None
        self._ramp_indicator.setVisible(False)
        self._stop_ramp_btn.setVisible(False)
        self.eurotherm.set_temperature(curr)
        self.log_panel.append(f"Ramp stopped at {curr:.1f} \u00b0C")
        self._update_run_btn_state()

    def _on_select_output_folder(self):
        """Prompt user for a persistent output directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", 
            self._output_dir or "",
            QFileDialog.ShowDirsOnly
        )
        if dir_path:
            self._output_dir = dir_path
            self._settings.setValue("output_dir", dir_path)
            self._folder_btn.setToolTip(f"Output folder: {dir_path}")

    # -- Run / Abort ---------------------------------------------------

    def _on_run(self):
        """Validate inputs, show confirmation dialog, then start the measurement."""
        name = self.sample_panel.get_sample_name()
        if not name:
            QMessageBox.warning(self, "Missing Name",
                                "Please enter a sample name.")
            return

        m_cfg = self.method_panel.get_settings()
        t_cfg = self.temp_panel.get_settings()

        if not (m_cfg["measure_conductivity"] or m_cfg["measure_seebeck"]):
            QMessageBox.warning(self, "No Measurement",
                                "Please select at least one measurement type.")
            return

        diameter  = self.sample_panel.get_diameter()
        thickness = self.sample_panel.get_thickness()

        dlg = _MeasurementConfirmDialog(
            m_cfg, t_cfg, name, diameter, thickness,
            current_temp=getattr(self, "_last_known_temp", None),
            output_dir=self._output_dir,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # ── Operator confirmed — build log summary and kick off the run ──
        meas_names = []
        if m_cfg["measure_conductivity"]:
            meas_names.append("σ")
        if m_cfg["measure_seebeck"]:
            meas_names.append("Seebeck")

        mode_info = (
            f"cycle {t_cfg['start_temp']:.0f}→{t_cfg['stop_temp']:.0f} °C"
            if m_cfg["cycle_mode"]
            else "current temperature"
        )
        self.log_panel.append(
            f"Starting — {name}  |  {', '.join(meas_names)} at {mode_info}"
        )
        self._set_running(True)

        # Resolve seebeck experiment time (testing mode or default)
        if m_cfg.get("testing_mode", False):
            seebeck_time = m_cfg.get("seebeck_time_min", 8.0) * 60.0
        else:
            seebeck_time = 480.0  # 8 minutes default

        # Resolve stability wait time (testing mode or default 20 min)
        if m_cfg.get("testing_mode", False):
            stability_time = m_cfg.get("stability_time_min", 20.0) * 60.0
        else:
            stability_time = 1200.0  # 20 minutes default

        config = {
            "sample_name":     name,
            "diameter":        diameter,
            "thickness":       thickness,
            "measure_sigma":   m_cfg["measure_conductivity"],
            "measure_seebeck": m_cfg["measure_seebeck"],
            "seebeck_time":    seebeck_time,
            "base_dir":        self._output_dir,
        }

        # Clear cycle summary graphs
        self._summary_seebeck.clear()
        self._summary_sigma.clear()
        self.graph_sigma_vs_temp.clear_data()
        self.graph_seebeck_vs_temp.clear_data()

        # Cycle mode: generate temperature list and add cycle params
        if m_cfg["cycle_mode"]:
            import numpy as np
            start = t_cfg["start_temp"]
            stop  = t_cfg["stop_temp"]
            step  = t_cfg["step"]
            # Generate list: start, start+step, ..., up to stop (inclusive)
            if start <= stop:
                temperatures = list(np.arange(start, stop + step * 0.01, step))
            else:
                temperatures = list(np.arange(start, stop - step * 0.01, -step))
            # Append cooling leg if Heating + Cooling is selected
            if not m_cfg["heating_only"] and len(temperatures) > 1:
                cooling = list(reversed(temperatures[:-1]))
                temperatures.extend(cooling)

            config["cycle_mode"]      = True
            config["temperatures"]    = [float(t) for t in temperatures]
            config["rate"]            = t_cfg["rate"]
            config["stability_time"]  = stability_time
            config["heating_only"]    = m_cfg["heating_only"]

        self.measurement_svc.start(config)

    def _on_abort(self):
        reply = QMessageBox.question(
            self, "Abort Measurement",
            "Are you sure you want to abort the running measurement?\n\n"
            "Instruments will be safely shut down.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.measurement_svc.request_abort()
            self.log_panel.append("Abort requested — waiting for safe shutdown …")
            self.status_label.setText("Aborting …")

    def _on_measurement_finished(self, success: bool, summary: str, metadata: dict):
        """Called when the measurement worker finishes (success or abort)."""
        self._set_running(False)

        # Auto-export summary if we just finished a cycle
        if success and self.method_panel.is_cycle_mode():
            dp = metadata.get("data_path")
            if dp:
                self._export_cycle_summary(dp)

        if success:
            self.log_panel.append(f"\u2714  {summary}")
        else:
            self.log_panel.append(f"\u2716  {summary}")
        # Show summary dialog to the operator
        dlg = _MeasurementSummaryDialog(
            success, summary, metadata=metadata, parent=self,
        )
        dlg.exec()

    def _set_running(self, running: bool):
        """Toggle run/abort buttons and lock or unlock all user-editable controls."""
        self._measurement_running = running
        self.run_btn.setVisible(not running)
        self.abort_btn.setVisible(running)

        # Lock the entire configuration area while a run is in progress.
        # Graphs (right panel) and splitters remain interactive.
        self.sample_panel.setEnabled(not running)
        self.method_panel.setEnabled(not running)
        self.temp_panel.setEnabled(not running)
        self._folder_btn.setEnabled(not running)

        # Clear graphs at the start of a new run so old data doesn't persist.
        if running:
            self.graph_sigma_iter.clear_data()
            self.graph_seebeck_t.clear_data()
            self.graph_seebeck_v.clear_data()
            self.graph_fit.clear_data()
            # Remove fit graph from splitter if it was added previously
            if self._fit_graph_added:
                self.graph_fit.setParent(None)
                self._fit_graph_added = False

    def _on_cycle_point_starting(self, idx: int, tgt_temp: float):
        self.graph_sigma_iter.clear_data()
        self.graph_seebeck_t.clear_data()
        self.graph_seebeck_v.clear_data()
        self.graph_fit.clear_data()
        # You could also update a section title to "Cycle [X/Y] - Z °C"

    def _on_cycle_point_completed(self, actual_temp: float, sigma_res: dict, seebeck_res: dict, folder_path: str = ""):
        if sigma_res:
            corr = sigma_res.get("corr_sigma", 0.0)
            self._summary_sigma.append((actual_temp, corr))
            self.graph_sigma_vs_temp.append_to("\u03c3 vs T", actual_temp, corr)
            self.graph_sigma_vs_temp._plot.autoRange()
            if folder_path:
                import os
                self.graph_sigma_iter.save_clean_png(os.path.join(folder_path, "Sigma", "sigma_iterations.png"))
        if seebeck_res:
            sb = seebeck_res.get("Seebeck", 0.0)
            self._summary_seebeck.append((actual_temp, sb))
            self.graph_seebeck_vs_temp.append_to("S vs T", actual_temp, sb)
            self.graph_seebeck_vs_temp._plot.autoRange()

    def _export_cycle_summary(self, dir_path: str):
        import traceback, csv, os
        try:
            name = self.sample_panel.get_sample_name()
            if self._summary_sigma:
                temps = [t for t, _ in self._summary_sigma]
                vals  = [s for _, s in self._summary_sigma]
                csv_path = os.path.join(dir_path, f"{name}_Sigma_vs_Temp.csv")
                with open(csv_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Temperature (°C)", "Conductivity (S/cm)"])
                    for t, s in self._summary_sigma:
                        writer.writerow([f"{t:.2f}", f"{s:.6e}"])
                png_path = os.path.join(dir_path, f"{name}_Sigma_vs_Temp.png")
                self._export_matplotlib_png(
                    temps, vals, png_path,
                    "Conductivity vs Temperature",
                    "Temperature (\u00b0C)", "Conductivity (S/cm)", "green"
                )

            if self._summary_seebeck:
                temps = [t for t, _ in self._summary_seebeck]
                vals  = [s for _, s in self._summary_seebeck]
                csv_path = os.path.join(dir_path, f"{name}_Seebeck_vs_Temp.csv")
                with open(csv_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Temperature (°C)", "Seebeck Coefficient (µV/K)"])
                    for t, s in self._summary_seebeck:
                        writer.writerow([f"{t:.2f}", f"{s:.6f}"])
                png_path = os.path.join(dir_path, f"{name}_Seebeck_vs_Temp.png")
                self._export_matplotlib_png(
                    temps, vals, png_path,
                    "Seebeck vs Temperature",
                    "Temperature (\u00b0C)", "Seebeck Coefficient (\u00b5V/K)", "orange"
                )

            self.log_panel.append(f"\u2714 Saved cycle summary graphs and CSVs to {dir_path}")
        except Exception as e:
            self.log_panel.append(f"\u26a0 Failed to export cycle summary: {e}")
            print(traceback.format_exc())

    def _export_matplotlib_png(self, x_data, y_data, path, title, xlabel, ylabel, color):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(x_data, y_data, marker='o', linestyle='-', color=color, linewidth=2, markersize=8)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)

    # -- Real-time Seebeck data --------------------------------------------

    def _on_seebeck_data_point(self, data: dict):
        """Plot a new Seebeck data point on the live graphs."""
        t_min = data["time"] / 60.0  # seconds → minutes
        T1 = data["T1"]
        T2 = data["T2"]
        V1 = data["V1"] * 1e6  # V → µV
        V2 = data["V2"] * 1e6

        self.graph_seebeck_t.append_to("T\u2081", t_min, T1)
        self.graph_seebeck_t.append_to("T\u2082", t_min, T2)
        self.graph_seebeck_v.append_to("V\u2081", t_min, V1)
        self.graph_seebeck_v.append_to("V\u2082", t_min, V2)

    # -- Real-time Sigma data -----------------------------------------------

    def _on_sigma_data_point(self, data: dict):
        """Plot a new sigma data point on the conductivity graph."""
        iteration = data.get("iteration", 0)
        sigma = data.get("sigma", None)
        if sigma is not None and sigma > 0:
            self.graph_sigma_iter.append_to("\u03c3", iteration, sigma)

            # Show measurement label next to pointer
            self.graph_sigma_iter.add_text(iteration, sigma, f"{sigma:.2e}", color="#5B9BD5")

    def _on_sigma_completed(self, results: dict):
        """Draw the corrected-sigma median line after σ measurement finishes."""
        corr_sigma = results.get("corr_sigma")
        if corr_sigma is not None and corr_sigma > 0:
            self.graph_sigma_iter.add_horizontal_line(
                corr_sigma,
                pen=pg.mkPen("#F0A500", width=1, style=Qt.DashLine),
                label=f"σ = {corr_sigma:.4e} S/cm",
            )

    def _on_seebeck_fit_ready(self, data: dict):
        """Add the V₁ vs V₂ fit graph to the seebeck splitter."""
        import numpy as np
        v1 = np.array(data["V1"])  # already µV
        v2 = np.array(data["V2"])
        slope = data["slope"]
        intercept = data["intercept"]
        adj_r2 = data.get("adj_r_square", 0)
        seebeck = data.get("seebeck", 0)

        # Plot raw data and fit line
        self.graph_fit.set_data_named("Data", v1, v2)
        v1_sorted = np.sort(v1)
        fit_y = slope * v1_sorted + intercept
        self.graph_fit.set_data_named("Fit", v1_sorted, fit_y)

        # Add annotation with fit results
        self.graph_fit.add_horizontal_line(
            0,  # invisible, just for the label
            pen=pg.mkPen(None),
            label=(
                f"S = {seebeck:.3f} \u00b5V/K  |  "
                f"adj R\u00b2 = {adj_r2:.5f}"
            ),
        )

        # Add to seebeck splitter if not already there
        if not self._fit_graph_added:
            self.seebeck_graph_splitter.addWidget(self.graph_fit)
            self._fit_graph_added = True
            # Re-balance the splitter evenly across all graphs
            count = self.seebeck_graph_splitter.count()
            total = sum(self.seebeck_graph_splitter.sizes())
            each = total // count
            self.seebeck_graph_splitter.setSizes([each] * count)

    def _on_phase_changed(self, phase: str):
        """Switch the right panel graph stack based on the current phase."""
        if phase == "sigma":
            self.graph_stack.setCurrentIndex(1)
        elif phase == "seebeck":
            self.graph_stack.setCurrentIndex(2)
        # 'idle' keeps the current view so results remain visible

    def _update_graph_placeholder(self, *_):
        """Update placeholder text based on measurement selection."""
        m = self.method_panel.get_settings()
        sigma = m.get("measure_conductivity", False)
        seebeck = m.get("measure_seebeck", False)
        if sigma and seebeck:
            txt = "\u03c3 + Seebeck selected\nClick START RUN to begin"
        elif sigma:
            txt = "\u03c3 measurement selected\nClick START RUN to begin"
        elif seebeck:
            txt = "Seebeck measurement selected\nClick START RUN to begin"
        else:
            txt = "Select a measurement type and\nclick START RUN to begin"
        self._placeholder_label.setText(txt)

    # -- Sidebar collapse (splitter-aware) ---------------------------------

    def showEvent(self, event):
        """Set the left panel to 50 % of the available width on first show."""
        super().showEvent(event)
        if not self._initial_split_done:
            self._initial_split_done = True
            avail = self.width() - _COLLAPSE_STRIP_W
            left  = int(avail * _LEFT_INITIAL_FRAC)
            right = avail - left
            self.h_splitter.setSizes([left, right])
            self._saved_left_width = left

    def _on_h_splitter_moved(self, pos: int, index: int):
        """Auto-collapse when left panel is dragged below threshold."""
        if self._left_collapsed:
            return
        left_width = self.h_splitter.sizes()[0]
        if 0 < left_width < _LEFT_MIN_THRESHOLD:
            self._collapse_left()

    def _toggle_sidebar(self):
        if self._left_collapsed:
            self._expand_left()
        else:
            self._collapse_left()

    def _collapse_left(self):
        sizes = self.h_splitter.sizes()
        self._saved_left_width = max(sizes[0], 300)
        self._left_panel.setVisible(False)
        self._left_collapsed = True
        self._collapse_btn.setText("\u25b6")
        self._collapse_btn.setToolTip("Expand configuration panel")

    def _expand_left(self):
        self._left_panel.setVisible(True)
        total = sum(self.h_splitter.sizes())
        # Restore previous width but never exceed 70% of available space.
        max_left = int(total * _LEFT_MAX_FRAC)
        restore  = min(self._saved_left_width, max_left)
        self.h_splitter.setSizes([restore, total - restore])
        self._left_collapsed = False
        self._collapse_btn.setText("\u25c0")
        self._collapse_btn.setToolTip("Collapse configuration panel")

    # -- Log panel collapse / expand ---------------------------------------

    def _toggle_log_panel(self):
        """Toggle the log panel between collapsed (header-only) and expanded."""
        if self._log_collapsed:
            # Expand
            sizes = self.v_splitter.sizes()
            total = sum(sizes)
            restore = min(self._saved_log_height, total // 3)
            self.v_splitter.setSizes([total - restore, restore])
            self._log_collapsed = False
        else:
            # Collapse — save current height, shrink to header-only (24 px)
            sizes = self.v_splitter.sizes()
            if sizes[1] > 30:
                self._saved_log_height = sizes[1]
            total = sum(sizes)
            self.v_splitter.setSizes([total - 24, 24])
            self._log_collapsed = True
        self.log_panel.set_collapsed(self._log_collapsed)

    # -- Graph maximize / restore ------------------------------------------

    def _toggle_graph_maximize(self, index: int):
        splitter = self.seebeck_graph_splitter
        sizes = splitter.sizes()
        total = sum(sizes)
        count = len(sizes)
        if count == 0: return
        # Check if all *other* panels are collapsed
        others_collapsed = all(
            s < 30 for i, s in enumerate(sizes) if i != index
        )
        if others_collapsed:
            # Restore even split
            each = total // count
            splitter.setSizes([each] * count)
        else:
            # Maximize requested panel, collapse all others
            new_sizes = [0] * count
            new_sizes[index] = total
            splitter.setSizes(new_sizes)

    def _toggle_sigma_maximize(self, index: int):
        splitter = self.sigma_graph_splitter
        sizes = splitter.sizes()
        total = sum(sizes)
        count = len(sizes)
        if count == 0: return
        others_collapsed = all(
            s < 30 for i, s in enumerate(sizes) if i != index
        )
        if others_collapsed:
            each = total // count
            splitter.setSizes([each] * count)
        else:
            new_sizes = [0] * count
            new_sizes[index] = total
            splitter.setSizes(new_sizes)

    # -- Instrument status indicators --------------------------------------

    def _on_instrument_status(self, name: str, state: str):
        """Update the coloured dot and tooltip for an instrument."""
        self._instrument_states[name] = state
        self._refresh_instrument_dot(name, state)

    def _refresh_instrument_dot(self, name: str, state: str):
        """Set dot colour based on state."""
        colour_map = {
            "disconnected": BORDER,       # grey
            "connected":    SUCCESS,      # green
            "idle":         SUCCESS,      # green
            "active":       ACCENT,       # blue (measuring)
        }
        colour = colour_map.get(state, BORDER)
        dot = self._inst_dots.get(name)
        lbl = self._inst_labels.get(name)
        if dot:
            dot.setStyleSheet(
                f"min-width:12px; max-width:12px; min-height:12px; max-height:12px; "
                f"border-radius:6px; background:{colour};"
            )
            dot.setToolTip(f"{name}: {state}")
        if lbl:
            lbl.setToolTip(f"{name}: {state}")

    # -- Exit / close ------------------------------------------------------

    def _on_exit(self):
        if self._measurement_running:
            reply = QMessageBox.question(
                self, "Measurement Running",
                "A measurement is in progress. Exit anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self.measurement_svc.stop()
        self.eurotherm.stop()
        QApplication.instance().quit()

    def closeEvent(self, event):
        self.measurement_svc.stop()
        self.eurotherm.stop()
        event.accept()
