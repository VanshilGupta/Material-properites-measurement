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
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QMessageBox,
    QApplication, QSplitter, QScrollArea, QToolTip,
)
from PySide6.QtGui import QPixmap

from gui.styles import STYLESHEET, TEXT_SECONDARY, SUCCESS
from gui.widgets import (
    SampleInfoPanel,
    TemperatureProfilePanel,
    MethodConfigPanel,
    GraphPanel,
    LogPanel,
)
from gui.backend import EurothermService

_GUI_DIR   = pathlib.Path(__file__).resolve().parent
_ROOT_DIR  = _GUI_DIR.parent
_ASSET_DIR = _ROOT_DIR / "assets"

_LEFT_INITIAL_FRAC  = 0.50   # fraction of window width for left panel on startup
_LEFT_MAX_FRAC      = 0.70   # splitter can go beyond but inputs stop growing here
_LEFT_MIN_THRESHOLD = 200    # px — below this, auto-collapse kicks in
_COLLAPSE_STRIP_W   = 28     # px — width of the always-visible arrow strip


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
        self._temp_read_count = 0   # throttle heartbeat log: print every 30 reads (≈30 s)

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

        self.graph_splitter = QSplitter(Qt.Vertical)

        self.graph_seebeck = GraphPanel(
            title="S vs T   (Seebeck Coefficient)",
            x_label="Temperature", y_label="S",
            x_unit="\u00b0C", y_unit="\u00b5V/K",
        )
        self.graph_sigma = GraphPanel(
            title="\u03c3 vs T   (Electrical Conductivity)",
            x_label="Temperature", y_label="\u03c3",
            x_unit="\u00b0C", y_unit="S/cm",
        )

        self.graph_splitter.addWidget(self.graph_seebeck)
        self.graph_splitter.addWidget(self.graph_sigma)
        self.graph_splitter.setStretchFactor(0, 1)
        self.graph_splitter.setStretchFactor(1, 1)

        self.graph_seebeck.maximize_requested.connect(
            lambda: self._toggle_graph_maximize(0)
        )
        self.graph_sigma.maximize_requested.connect(
            lambda: self._toggle_graph_maximize(1)
        )

        right_vl.addWidget(self.graph_splitter, stretch=1)

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
        self.v_splitter.addWidget(self.log_panel)
        self.v_splitter.setStretchFactor(0, 5)
        self.v_splitter.setStretchFactor(1, 1)
        self.v_splitter.setSizes([560, 120])

        outer.addWidget(self.v_splitter)

    # ==================================================================
    # Status Bar
    # ==================================================================

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_label = QLabel("Ready")
        sb.addWidget(self.status_label)

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

        # Set initial button state and tooltip immediately
        self._update_run_btn_state()

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

        can_run = name_ok and dia_ok and thk_ok and meas_ok and cycle_ok
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
            self.run_btn.setToolTip("Cannot start:\n" + "\n".join(reasons))

    def _update_current_temp(self, temp_c: float):
        self.current_temp_lbl.setText(f"{temp_c:.1f}  \u00b0C")
        self._temp_read_count += 1
        # Log a heartbeat every 30 successful reads (≈ every 30 s) so the
        # operator can confirm live polling without flooding the log panel.
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
        msg = "Eurotherm connected" if connected else "Eurotherm disconnected"
        self.status_label.setText(msg)
        self.log_panel.append(msg)

    def _show_error(self, msg: str):
        self.status_label.setText(f"Error: {msg}")
        self.log_panel.append(f"ERROR: {msg}")

    # -- Run / Abort ---------------------------------------------------

    def _on_run(self):
        """Validate inputs and start the measurement sequence."""
        name = self.sample_panel.get_sample_name()
        if not name:
            QMessageBox.warning(self, "Missing Name",
                                "Please enter a sample name.")
            return

        m_cfg = self.method_panel.get_settings()
        t_cfg = self.temp_panel.get_settings()

        meas = []
        if m_cfg["measure_seebeck"]:
            meas.append("Seebeck")
        if m_cfg["measure_conductivity"]:
            meas.append("\u03c3")
        if not meas:
            QMessageBox.warning(self, "No Measurement",
                                "Please select at least one measurement type.")
            return

        if m_cfg["cycle_mode"]:
            direction = ("Heating only" if m_cfg["heating_only"]
                         else "Heating + Cooling")
            cycle_info = (
                f"Cycle: {t_cfg['start_temp']} \u2192 {t_cfg['stop_temp']} \u00b0C, "
                f"step {t_cfg['step']} \u00b0C, rate {t_cfg['rate']} \u00b0C/min  |  {direction}"
            )
        else:
            cycle_info = "Single measurement at current temperature"

        info = (
            f"Sample: {name}\n"
            f"Diameter: {self.sample_panel.get_diameter()} mm, "
            f"Thickness: {self.sample_panel.get_thickness()} mm\n"
            f"Measure: {', '.join(meas)}\n"
            f"{cycle_info}\n"
        )

        self.log_panel.append(f"Starting measurement \u2014 {name}")
        self.log_panel.append(info.replace("\n", " | "))
        self._set_running(True)

        # TODO: hook into actual measurement backend
        QMessageBox.information(
            self, "Measurement Summary",
            info + "\n(Run logic coming soon)",
        )

    def _on_abort(self):
        reply = QMessageBox.question(
            self, "Abort Measurement",
            "Are you sure you want to abort the running measurement?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.log_panel.append("Measurement ABORTED by user")
            self.status_label.setText("Measurement aborted")
            self._set_running(False)
            # TODO: stop measurement threads

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

    # -- Graph maximize / restore ------------------------------------------

    def _toggle_graph_maximize(self, index: int):
        sizes = self.graph_splitter.sizes()
        total = sum(sizes)
        other = 1 - index
        if sizes[other] < 30:
            half = total // 2
            self.graph_splitter.setSizes([half, total - half])
        else:
            new = [0, 0]
            new[index] = total
            self.graph_splitter.setSizes(new)

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
        self.eurotherm.stop()
        QApplication.instance().quit()

    def closeEvent(self, event):
        self.eurotherm.stop()
        event.accept()
