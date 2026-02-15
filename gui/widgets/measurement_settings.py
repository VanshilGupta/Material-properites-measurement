"""
Measurement Settings Panel  (left sidebar).

Three sections stacked vertically:
1. Temperature Mode   — Room Temp ● | High Temp ○
2. Cycle Mode         — Heating Cycle ● | Heating + Cooling Cycle ○
3. Measurement Type   — Seebeck Coeff ☑ | Electrical Conductivity ☑ | Both ☑
"""

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QRadioButton, QCheckBox, QButtonGroup, QLabel, QMessageBox,
)
from PySide6.QtCore import Signal


class MeasurementSettingsPanel(QGroupBox):
    """Left-side panel with all measurement configuration radio/check boxes."""

    # Emitted whenever settings change.
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__("Measurement Settings", parent)
        self._build_ui()
        self._connect_signals()

    # ── UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 22, 10, 10)
        outer.setSpacing(14)

        # --- 1. Temperature mode ------------------------------------------
        temp_box = QGroupBox("Temperature Mode")
        temp_lay = QVBoxLayout(temp_box)
        self.radio_room_temp = QRadioButton("Room Temperature")
        self.radio_high_temp = QRadioButton("High Temperature")
        self.radio_room_temp.setChecked(True)

        self._temp_group = QButtonGroup(self)
        self._temp_group.addButton(self.radio_room_temp)
        self._temp_group.addButton(self.radio_high_temp)

        temp_lay.addWidget(self.radio_room_temp)
        temp_lay.addWidget(self.radio_high_temp)
        outer.addWidget(temp_box)

        # --- 2. Cycle mode ------------------------------------------------
        cycle_box = QGroupBox("Cycle Mode")
        cycle_lay = QVBoxLayout(cycle_box)
        self.radio_heating_only = QRadioButton("Heating Cycle")
        self.radio_heating_cooling = QRadioButton("Heating + Cooling Cycle")
        self.radio_heating_only.setChecked(True)

        self._cycle_group = QButtonGroup(self)
        self._cycle_group.addButton(self.radio_heating_only)
        self._cycle_group.addButton(self.radio_heating_cooling)

        cycle_lay.addWidget(self.radio_heating_only)
        cycle_lay.addWidget(self.radio_heating_cooling)
        outer.addWidget(cycle_box)

        # --- 3. Measurement type ------------------------------------------
        meas_box = QGroupBox("Measurement Type")
        meas_lay = QVBoxLayout(meas_box)
        self.chk_seebeck = QCheckBox("Seebeck Coefficient")
        self.chk_sigma   = QCheckBox("Electrical Conductivity")
        self.chk_both    = QCheckBox("Both")

        # Default: both checked
        self.chk_both.setChecked(True)

        meas_lay.addWidget(self.chk_seebeck)
        meas_lay.addWidget(self.chk_sigma)
        meas_lay.addWidget(self.chk_both)
        outer.addWidget(meas_box)

        outer.addStretch()

    # ── Signal wiring ──────────────────────────────────────────────────

    def _connect_signals(self):
        # Temperature mode affects whether sweep settings are relevant
        self._temp_group.buttonToggled.connect(self._on_change)
        self._cycle_group.buttonToggled.connect(self._on_change)

        # Measurement type: "Both" toggles the other two
        self.chk_both.toggled.connect(self._on_both_toggled)
        self.chk_seebeck.toggled.connect(self._on_individual_toggled)
        self.chk_sigma.toggled.connect(self._on_individual_toggled)

    def _on_both_toggled(self, checked: bool):
        if checked:
            self.chk_seebeck.blockSignals(True)
            self.chk_sigma.blockSignals(True)
            self.chk_seebeck.setChecked(False)
            self.chk_sigma.setChecked(False)
            self.chk_seebeck.blockSignals(False)
            self.chk_sigma.blockSignals(False)
        self._on_change()

    def _on_individual_toggled(self, _checked: bool):
        # If either individual is checked, uncheck "Both"
        if self.chk_seebeck.isChecked() or self.chk_sigma.isChecked():
            self.chk_both.blockSignals(True)
            self.chk_both.setChecked(False)
            self.chk_both.blockSignals(False)
        self._on_change()

    def _on_change(self):
        self.settings_changed.emit()

    # ── Public getters ─────────────────────────────────────────────────

    def is_room_temp(self) -> bool:
        return self.radio_room_temp.isChecked()

    def is_high_temp(self) -> bool:
        return self.radio_high_temp.isChecked()

    def is_heating_only(self) -> bool:
        return self.radio_heating_only.isChecked()

    def is_heating_cooling(self) -> bool:
        return self.radio_heating_cooling.isChecked()

    def measure_seebeck(self) -> bool:
        return self.chk_seebeck.isChecked() or self.chk_both.isChecked()

    def measure_sigma(self) -> bool:
        return self.chk_sigma.isChecked() or self.chk_both.isChecked()

    def validate(self) -> bool:
        """Return True if at least one measurement type is selected."""
        if not (self.chk_seebeck.isChecked() or self.chk_sigma.isChecked() or self.chk_both.isChecked()):
            QMessageBox.warning(
                self,
                "No Measurement Selected",
                "Please select at least one measurement type\n"
                "(Seebeck, Conductivity, or Both).",
            )
            return False
        return True
