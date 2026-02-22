"""Measurement Settings panel — Seebeck & conductivity parameters."""

from PySide6.QtCore    import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QSpinBox,
    QPushButton, QRadioButton, QCheckBox, QButtonGroup,
)
from gui.styles import (
    TEXT_SECONDARY, ACCENT,
    BG_PANEL, BORDER,
)


class MeasurementSettingsPanel(QWidget):
    """Left-panel widget for measurement parameters.

    Signals
    -------
    cycle_toggled(bool)
        Emitted when the Enable Cycle toggle changes state.
    """

    cycle_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ── Private builders ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addWidget(self._build_seebeck_box())
        root.addWidget(self._build_sigma_box())
        root.addWidget(self._build_cycle_box())
        root.addStretch()

    # ── Seebeck ───────────────────────────────────────────────────────────

    def _build_seebeck_box(self) -> QGroupBox:
        box = QGroupBox("Seebeck Measurement")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setContentsMargins(8, 8, 8, 8)

        self.delta_t_spin = QDoubleSpinBox()
        self.delta_t_spin.setRange(0.5, 50.0)
        self.delta_t_spin.setValue(5.0)
        self.delta_t_spin.setSuffix("  °C")
        self.delta_t_spin.setDecimals(1)
        self.delta_t_spin.setToolTip("Temperature differential applied across the sample")

        self.seebeck_avg_spin = QSpinBox()
        self.seebeck_avg_spin.setRange(1, 20)
        self.seebeck_avg_spin.setValue(3)
        self.seebeck_avg_spin.setToolTip("Number of readings averaged per Seebeck data-point")

        self.voltage_delay_spin = QDoubleSpinBox()
        self.voltage_delay_spin.setRange(0.1, 30.0)
        self.voltage_delay_spin.setValue(2.0)
        self.voltage_delay_spin.setSuffix("  s")
        self.voltage_delay_spin.setDecimals(1)
        self.voltage_delay_spin.setToolTip("Stabilisation delay before voltage reading")

        form.addRow("ΔT:", self.delta_t_spin)
        form.addRow("Averages:", self.seebeck_avg_spin)
        form.addRow("V Delay:", self.voltage_delay_spin)
        return box

    # ── Conductivity ──────────────────────────────────────────────────────

    def _build_sigma_box(self) -> QGroupBox:
        box = QGroupBox("Conductivity Measurement")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setContentsMargins(8, 8, 8, 8)

        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0.001, 1000.0)
        self.current_spin.setValue(10.0)
        self.current_spin.setSuffix("  mA")
        self.current_spin.setDecimals(3)
        self.current_spin.setToolTip("DC current injected for 4-probe resistance measurement")

        self.sigma_avg_spin = QSpinBox()
        self.sigma_avg_spin.setRange(1, 20)
        self.sigma_avg_spin.setValue(3)
        self.sigma_avg_spin.setToolTip("Number of readings averaged per conductivity data-point")

        self.current_delay_spin = QDoubleSpinBox()
        self.current_delay_spin.setRange(0.1, 30.0)
        self.current_delay_spin.setValue(1.0)
        self.current_delay_spin.setSuffix("  s")
        self.current_delay_spin.setDecimals(1)
        self.current_delay_spin.setToolTip("Stabilisation delay after applying current")

        form.addRow("Current:", self.current_spin)
        form.addRow("Averages:", self.sigma_avg_spin)
        form.addRow("I Delay:", self.current_delay_spin)
        return box

    # ── Temperature Cycle ────────────────────────────────────────────────

    def _build_cycle_box(self) -> QGroupBox:
        box = QGroupBox("Temperature Cycle")
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(8, 10, 8, 8)
        vbox.setSpacing(10)

        # ── Enable toggle (pill button) ───────────────────────────────────
        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)

        toggle_label = QLabel("Enable Cycle:")
        toggle_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        toggle_label.setMinimumWidth(90)

        self.cycle_toggle = QPushButton("○  OFF")
        self.cycle_toggle.setObjectName("ToggleButton")
        self.cycle_toggle.setCheckable(True)
        self.cycle_toggle.setChecked(False)
        self.cycle_toggle.setToolTip(
            "Enable automatic temperature cycling between Start and End temperatures"
        )
        self.cycle_toggle.toggled.connect(self._on_cycle_toggled)

        toggle_row.addWidget(toggle_label)
        toggle_row.addWidget(self.cycle_toggle)
        toggle_row.addStretch()
        vbox.addLayout(toggle_row)

        # ── Cycle direction radios ────────────────────────────────────────
        self.radio_heat       = QRadioButton("Heating Cycle")
        self.radio_heat_cool  = QRadioButton("Heating + Cooling")
        self.radio_heat.setChecked(True)

        self._dir_group = QButtonGroup(self)
        self._dir_group.addButton(self.radio_heat)
        self._dir_group.addButton(self.radio_heat_cool)

        direction_label = QLabel("Direction:")
        direction_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        direction_label.setMinimumWidth(90)

        radio_col = QVBoxLayout()
        radio_col.setSpacing(4)
        radio_col.addWidget(self.radio_heat)
        radio_col.addWidget(self.radio_heat_cool)

        direction_row = QHBoxLayout()
        direction_row.addWidget(direction_label)
        direction_row.addLayout(radio_col)
        direction_row.addStretch()
        vbox.addLayout(direction_row)

        # ── Cycle range spinboxes ─────────────────────────────────────────
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.cycle_start_spin = QDoubleSpinBox()
        self.cycle_start_spin.setRange(25.0, 1500.0)
        self.cycle_start_spin.setValue(100.0)
        self.cycle_start_spin.setSuffix("  °C")
        self.cycle_start_spin.setDecimals(1)
        self.cycle_start_spin.setToolTip("Start temperature for cycle")

        self.cycle_end_spin = QDoubleSpinBox()
        self.cycle_end_spin.setRange(25.0, 1500.0)
        self.cycle_end_spin.setValue(800.0)
        self.cycle_end_spin.setSuffix("  °C")
        self.cycle_end_spin.setDecimals(1)
        self.cycle_end_spin.setToolTip("End temperature for cycle")

        self.cycle_step_spin = QDoubleSpinBox()
        self.cycle_step_spin.setRange(1.0, 200.0)
        self.cycle_step_spin.setValue(50.0)
        self.cycle_step_spin.setSuffix("  °C")
        self.cycle_step_spin.setDecimals(1)
        self.cycle_step_spin.setToolTip("Temperature step between measurements")

        form.addRow("Start T:", self.cycle_start_spin)
        form.addRow("End T:", self.cycle_end_spin)
        form.addRow("Step:", self.cycle_step_spin)
        vbox.addLayout(form)

        # ── Options checkboxes ────────────────────────────────────────────
        self.auto_save_chk   = QCheckBox("Auto-save data")
        self.plot_live_chk   = QCheckBox("Plot live data")
        self.plot_live_chk.setChecked(True)

        vbox.addWidget(self.auto_save_chk)
        vbox.addWidget(self.plot_live_chk)

        # Store all cycle-gated widgets for enable/disable
        self._cycle_widgets = [
            self.radio_heat, self.radio_heat_cool,
            self.cycle_start_spin, self.cycle_end_spin, self.cycle_step_spin,
        ]
        self._set_cycle_widgets_enabled(False)

        return box

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_cycle_toggled(self, checked: bool):
        self.cycle_toggle.setText("●  ON" if checked else "○  OFF")
        self._set_cycle_widgets_enabled(checked)
        self.cycle_toggled.emit(checked)

    def _set_cycle_widgets_enabled(self, enabled: bool):
        for w in self._cycle_widgets:
            w.setEnabled(enabled)

    # ── Public API ────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        """Return all measurement settings as a plain dict."""
        return {
            "delta_t":        self.delta_t_spin.value(),
            "seebeck_avg":    self.seebeck_avg_spin.value(),
            "voltage_delay":  self.voltage_delay_spin.value(),
            "current_ma":     self.current_spin.value(),
            "sigma_avg":      self.sigma_avg_spin.value(),
            "current_delay":  self.current_delay_spin.value(),
            "cycle_enabled":  self.cycle_toggle.isChecked(),
            "cycle_heat_only": self.radio_heat.isChecked(),
            "cycle_start":    self.cycle_start_spin.value(),
            "cycle_end":      self.cycle_end_spin.value(),
            "cycle_step":     self.cycle_step_spin.value(),
            "auto_save":      self.auto_save_chk.isChecked(),
            "plot_live":      self.plot_live_chk.isChecked(),
        }
