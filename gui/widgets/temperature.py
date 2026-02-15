"""
Temperature Settings Panel.

• "Set Furnace T" button → sends a temperature to the Eurotherm right away.
• Start / Stop / Step inputs → for automated temperature sweeps.
"""

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QPushButton, QWidget,
)
from PySide6.QtCore import Signal

import sys, pathlib
_project_root = str(pathlib.Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
from constants import DEFAULT_START_TEMP, DEFAULT_END_TEMP, DEFAULT_TEMP_STEP


class TemperatureSettingsPanel(QGroupBox):
    """Panel for temperature control and sweep configuration."""

    # Emitted when user clicks "Set Furnace T": carries temperature in °C
    set_furnace_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__("Temperature Settings", parent)
        self._build_ui()
        self._connect_signals()

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 24, 12, 12)
        main_layout.setSpacing(14)

        # --- Direct set-temperature row -----------------------------------
        set_row = QHBoxLayout()
        self.set_btn = QPushButton("Set Furnace T")
        self.set_btn.setToolTip("Send this temperature to the Eurotherm right now")
        self.set_btn.setMinimumWidth(130)

        self.arrow_label = QLabel("→")
        self.arrow_label.setStyleSheet("font-size: 18px; background: transparent;")

        self.direct_temp_spin = QDoubleSpinBox()
        self.direct_temp_spin.setRange(0.0, 1000.0)
        self.direct_temp_spin.setDecimals(1)
        self.direct_temp_spin.setSuffix(" °C")
        self.direct_temp_spin.setValue(25.0)
        self.direct_temp_spin.setMinimumWidth(100)

        set_row.addWidget(self.set_btn)
        set_row.addWidget(self.arrow_label)
        set_row.addWidget(self.direct_temp_spin)
        set_row.addStretch()
        main_layout.addLayout(set_row)

        # --- Current furnace temperature readout --------------------------
        readout_row = QHBoxLayout()
        readout_label = QLabel("Current T:")
        readout_label.setStyleSheet("background: transparent;")
        self.current_temp_label = QLabel("-- °C")
        self.current_temp_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #66bb6a; background: transparent;"
        )
        readout_row.addWidget(readout_label)
        readout_row.addWidget(self.current_temp_label)
        readout_row.addStretch()
        main_layout.addLayout(readout_row)

        # --- Sweep settings (start / stop / step) -------------------------
        sweep_box = QGroupBox("Sweep Range")
        sweep_form = QFormLayout(sweep_box)
        sweep_form.setSpacing(8)

        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 1000.0)
        self.start_spin.setDecimals(1)
        self.start_spin.setSuffix(" °C")
        self.start_spin.setValue(DEFAULT_START_TEMP)
        sweep_form.addRow("Start:", self.start_spin)

        self.stop_spin = QDoubleSpinBox()
        self.stop_spin.setRange(0.0, 1000.0)
        self.stop_spin.setDecimals(1)
        self.stop_spin.setSuffix(" °C")
        self.stop_spin.setValue(DEFAULT_END_TEMP)
        sweep_form.addRow("Stop:", self.stop_spin)

        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(1.0, 500.0)
        self.step_spin.setDecimals(1)
        self.step_spin.setSuffix(" °C")
        self.step_spin.setValue(DEFAULT_TEMP_STEP)
        sweep_form.addRow("Step:", self.step_spin)

        main_layout.addWidget(sweep_box)
        main_layout.addStretch()

    # ── Signals ────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.set_btn.clicked.connect(self._on_set_clicked)

    def _on_set_clicked(self):
        self.set_furnace_requested.emit(self.direct_temp_spin.value())

    # ── Public helpers ─────────────────────────────────────────────────

    def update_current_temperature(self, temp_c: float):
        """Update the on-screen readout (called from backend signal)."""
        self.current_temp_label.setText(f"{temp_c:.1f} °C")

    def get_sweep_params(self) -> tuple:
        """Return (start, stop, step) in °C."""
        return (
            self.start_spin.value(),
            self.stop_spin.value(),
            self.step_spin.value(),
        )
