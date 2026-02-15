"""
Main Window — assembles every panel into the final layout.

Layout map (matches the hand-drawn sketch):
┌──────────────────────────────────────────────────────────┐
│  [Logo]       Equipment Name                    [EXIT]   │
├────────────┬─────────────────────┬───────────────────────┤
│ Measurement│  Sample Information │  S vs T  graph        │
│ Settings   │                    │                        │
│            ├─────────────────────┤────────────────────────┤
│  (radios / │  Temperature        │  σ vs T  graph        │
│   checks)  │  Settings           │                        │
│            │                    │                        │
│            │         [RUN]      │                        │
├────────────┴─────────────────────┴───────────────────────┤
│  Status bar                                              │
└──────────────────────────────────────────────────────────┘
"""

import sys, pathlib
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QMessageBox, QApplication,
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize

from gui.styles import STYLESHEET
from gui.widgets import (
    SampleInfoPanel,
    TemperatureSettingsPanel,
    MeasurementSettingsPanel,
    GraphPanel,
)
from gui.backend import EurothermService


# Resolve paths relative to this file
_GUI_DIR   = pathlib.Path(__file__).resolve().parent
_ROOT_DIR  = _GUI_DIR.parent
_ASSET_DIR = _ROOT_DIR / "assets"


class MainWindow(QMainWindow):
    """Top-level application window."""

    WINDOW_TITLE = "Thermoelectric Measurement System"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(1200, 720)
        self.setStyleSheet(STYLESHEET)

        # ── Backend services ──────────────────────────────────────────
        self.eurotherm = EurothermService(self)

        # ── Build the UI ──────────────────────────────────────────────
        self._build_top_bar()
        self._build_body()
        self._build_status_bar()

        # ── Wire backend ↔ frontend ──────────────────────────────────
        self._connect_backend()

    # ==================================================================
    # Top Bar
    # ==================================================================

    def _build_top_bar(self):
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(56)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 4, 12, 4)

        # Logo
        self.logo_label = QLabel()
        logo_path = _ASSET_DIR / "logo.png"
        if logo_path.exists():
            pm = QPixmap(str(logo_path)).scaled(
                40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.logo_label.setPixmap(pm)
        else:
            self.logo_label.setText("⚛")
            self.logo_label.setStyleSheet(
                "font-size: 28px; background: transparent; padding: 0 8px;"
            )
        h.addWidget(self.logo_label)

        # Title
        title = QLabel(self.WINDOW_TITLE)
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        h.addStretch()
        h.addWidget(title)
        h.addStretch()

        # Exit button
        exit_btn = QPushButton("EXIT")
        exit_btn.setObjectName("ExitButton")
        exit_btn.setToolTip("Close the application immediately")
        exit_btn.clicked.connect(self._on_exit)
        h.addWidget(exit_btn)

        self.setMenuWidget(bar)  # places it above the central widget

    # ==================================================================
    # Body (three columns)
    # ==================================================================

    def _build_body(self):
        central = QWidget()
        self.setCentralWidget(central)
        body = QHBoxLayout(central)
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(10)

        # ── Left column: Measurement Settings ─────────────────────────
        self.measurement_panel = MeasurementSettingsPanel()
        self.measurement_panel.setFixedWidth(240)
        body.addWidget(self.measurement_panel)

        # ── Middle column: Sample Info + Temp Settings + RUN ──────────
        mid_col = QVBoxLayout()
        mid_col.setSpacing(10)

        self.sample_panel = SampleInfoPanel()
        mid_col.addWidget(self.sample_panel)

        self.temp_panel = TemperatureSettingsPanel()
        mid_col.addWidget(self.temp_panel)

        # RUN button
        self.run_btn = QPushButton("RUN")
        self.run_btn.setObjectName("RunButton")
        self.run_btn.setToolTip("Start the measurement sequence")
        self.run_btn.clicked.connect(self._on_run)
        mid_col.addWidget(self.run_btn, alignment=Qt.AlignCenter)

        mid_col.addStretch()
        body.addLayout(mid_col, stretch=2)

        # ── Right column: Graph placeholders ──────────────────────────
        graph_col = QVBoxLayout()
        graph_col.setSpacing(10)

        self.graph_seebeck = GraphPanel("S vs T")
        graph_col.addWidget(self.graph_seebeck)

        self.graph_sigma = GraphPanel("σ vs T")
        graph_col.addWidget(self.graph_sigma)

        body.addLayout(graph_col, stretch=3)

    # ==================================================================
    # Status Bar
    # ==================================================================

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_label = QLabel("Ready")
        sb.addWidget(self.status_label)

    # ==================================================================
    # Backend ↔ Frontend wiring
    # ==================================================================

    def _connect_backend(self):
        # Temperature display
        self.eurotherm.temperature_read.connect(
            self.temp_panel.update_current_temperature
        )
        # "Set Furnace T" button → backend
        self.temp_panel.set_furnace_requested.connect(self._on_set_furnace)
        # Backend errors → status bar
        self.eurotherm.error_occurred.connect(self._show_error)
        # Connection state
        self.eurotherm.connection_changed.connect(self._on_connection_state)
        # Set-point confirmation
        self.eurotherm.set_point_reached.connect(self._on_setpoint_sent)

    # ==================================================================
    # Slot implementations
    # ==================================================================

    def _on_set_furnace(self, target_c: float):
        """User clicked 'Set Furnace T'."""
        self.status_label.setText(f"Setting furnace to {target_c:.1f} °C …")
        self.eurotherm.set_temperature(target_c)

    def _on_setpoint_sent(self, target_c: float):
        self.status_label.setText(f"Furnace set-point → {target_c:.1f} °C  ✓")

    def _on_connection_state(self, connected: bool):
        if connected:
            self.status_label.setText("Eurotherm connected")
        else:
            self.status_label.setText("Eurotherm disconnected")

    def _show_error(self, msg: str):
        self.status_label.setText(f"Error: {msg}")

    def _on_run(self):
        """Validate settings and (later) kick off the measurement."""
        if not self.measurement_panel.validate():
            return

        name = self.sample_panel.get_sample_name()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a sample name.")
            return

        # Summarise what will happen
        meas = []
        if self.measurement_panel.measure_seebeck():
            meas.append("Seebeck")
        if self.measurement_panel.measure_sigma():
            meas.append("σ")
        mode = "Room Temp" if self.measurement_panel.is_room_temp() else "High Temp"
        cycle = "Heating only" if self.measurement_panel.is_heating_only() else "Heat + Cool"
        start, stop, step = self.temp_panel.get_sweep_params()

        info = (
            f"Sample: {name}\n"
            f"Diameter: {self.sample_panel.get_diameter()} mm, "
            f"Thickness: {self.sample_panel.get_thickness()} mm\n"
            f"Measure: {', '.join(meas)}\n"
            f"Mode: {mode}  |  Cycle: {cycle}\n"
        )
        if not self.measurement_panel.is_room_temp():
            info += f"Sweep: {start} → {stop} °C, step {step} °C\n"

        QMessageBox.information(self, "Measurement Summary", info + "\n(Run logic coming soon)")

    def _on_exit(self):
        """Immediately close the application."""
        self.eurotherm.stop()
        QApplication.instance().quit()

    # ── overrides ─────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Ensure clean shutdown on window close."""
        self.eurotherm.stop()
        event.accept()
