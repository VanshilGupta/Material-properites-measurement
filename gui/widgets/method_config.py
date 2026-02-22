"""Method Configuration panel — experiment mode, cycle direction, measurements."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QRadioButton,
    QCheckBox, QButtonGroup, QWidget,
)


class MethodConfigPanel(QGroupBox):
    """Experiment mode, cycle direction, and measurement selection.

    Signals
    -------
    mode_changed(bool)
        True when Temperature Cycle mode is active, False for Current Temperature.
    settings_changed()
        Emitted whenever any setting changes (for RUN button validation).
    """

    mode_changed     = Signal(bool)
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__("METHOD CONFIGURATION", parent)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 18, 10, 10)
        vbox.setSpacing(14)

        # ── Experiment Mode (segmented toggle) ────────────────────────────
        mode_lbl = QLabel("Experiment Mode:")
        mode_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        vbox.addWidget(mode_lbl)

        toggle = QWidget()
        toggle.setObjectName("SegmentedToggle")
        # Buttons grow with the panel up to this cap; beyond it the section
        # box simply gets more whitespace on the right.
        toggle.setMaximumWidth(460)
        t_hl = QHBoxLayout(toggle)
        t_hl.setContentsMargins(3, 3, 3, 3)
        t_hl.setSpacing(2)

        self.btn_current_t = QPushButton("Current Temperature")
        self.btn_current_t.setCheckable(True)
        self.btn_current_t.setChecked(True)
        self.btn_current_t.setObjectName("SegmentBtn")
        self.btn_current_t.setCursor(Qt.PointingHandCursor)

        self.btn_temp_cycle = QPushButton("Temperature Cycle")
        self.btn_temp_cycle.setCheckable(True)
        self.btn_temp_cycle.setObjectName("SegmentBtn")
        self.btn_temp_cycle.setCursor(Qt.PointingHandCursor)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self.btn_current_t, 0)
        self._mode_group.addButton(self.btn_temp_cycle, 1)
        self._mode_group.idToggled.connect(self._on_mode_toggled)

        t_hl.addWidget(self.btn_current_t, stretch=1)
        t_hl.addWidget(self.btn_temp_cycle, stretch=1)
        vbox.addWidget(toggle)

        # ── Cycle Mode + Measure — shared grid for column alignment ───────
        #
        #   Col 0 (left)                  Col 1 (right)
        #   ────────────────────────────────────────────
        #   "Cycle Mode:" header (spans 2 cols)
        #   [○ Heating Only]              [○ Heating + Cooling]
        #   "Measure:" header (spans 2 cols)
        #   [☐ Seebeck (S)]               [☐ Electrical Conductivity (σ)]
        #
        align_grid = QGridLayout()
        align_grid.setHorizontalSpacing(10)
        align_grid.setVerticalSpacing(6)
        # Col 2 is empty and absorbs all extra width → cols 0 & 1 hug their content
        align_grid.setColumnStretch(0, 0)
        align_grid.setColumnStretch(1, 0)
        align_grid.setColumnStretch(2, 1)

        # — Cycle Mode header —
        cycle_lbl = QLabel("Cycle Mode:")
        cycle_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        align_grid.addWidget(cycle_lbl, 0, 0, 1, 2)

        # — Radio buttons —
        self.radio_heat_only = QRadioButton("Heating Only")
        self.radio_heat_only.setCursor(Qt.PointingHandCursor)

        self.radio_heat_cool = QRadioButton("Heating + Cooling")
        self.radio_heat_cool.setCursor(Qt.PointingHandCursor)

        # Non-exclusive group so we can uncheck all when in Current T mode
        self._cycle_group = QButtonGroup(self)
        self._cycle_group.setExclusive(False)
        self._cycle_group.addButton(self.radio_heat_only)
        self._cycle_group.addButton(self.radio_heat_cool)

        # Manual mutual exclusion + notify RUN-button validator
        self.radio_heat_only.toggled.connect(self._on_heat_only_toggled)
        self.radio_heat_cool.toggled.connect(self._on_heat_cool_toggled)
        self.radio_heat_only.toggled.connect(self.settings_changed)
        self.radio_heat_cool.toggled.connect(self.settings_changed)

        align_grid.addWidget(self.radio_heat_only, 1, 0)
        align_grid.addWidget(self.radio_heat_cool, 1, 1)

        # — Measure header —
        meas_lbl = QLabel("Measure:")
        meas_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        align_grid.addWidget(meas_lbl, 2, 0, 1, 2)

        # — Checkboxes —
        self.chk_seebeck = QCheckBox("Seebeck  (S)")
        self.chk_seebeck.setChecked(False)
        self.chk_seebeck.setCursor(Qt.PointingHandCursor)

        self.chk_conductivity = QCheckBox("Electrical Conductivity  (σ)")
        self.chk_conductivity.setCursor(Qt.PointingHandCursor)

        self.chk_seebeck.stateChanged.connect(self.settings_changed)
        self.chk_conductivity.stateChanged.connect(self.settings_changed)

        align_grid.addWidget(self.chk_seebeck, 3, 0)
        align_grid.addWidget(self.chk_conductivity, 3, 1)

        vbox.addLayout(align_grid)

        # Initial state: cycle radios disabled, none checked
        self._set_cycle_widgets_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_mode_toggled(self, button_id: int, checked: bool):
        if not checked:
            return
        is_cycle = (button_id == 1)
        if is_cycle:
            # Default to Heating Only when switching into cycle mode
            self.radio_heat_only.setChecked(True)
        else:
            # Switching to Current Temperature — uncheck all radios
            self._uncheck_all_radios()
        self._set_cycle_widgets_enabled(is_cycle)
        self.mode_changed.emit(is_cycle)

    def _on_heat_only_toggled(self, checked: bool):
        """Enforce mutual exclusion manually."""
        if checked and self.radio_heat_cool.isChecked():
            self.radio_heat_cool.setChecked(False)

    def _on_heat_cool_toggled(self, checked: bool):
        """Enforce mutual exclusion manually."""
        if checked and self.radio_heat_only.isChecked():
            self.radio_heat_only.setChecked(False)

    def _uncheck_all_radios(self):
        for btn in self._cycle_group.buttons():
            btn.setChecked(False)

    def _set_cycle_widgets_enabled(self, enabled: bool):
        self.radio_heat_only.setEnabled(enabled)
        self.radio_heat_cool.setEnabled(enabled)
        if not enabled:
            self._uncheck_all_radios()

    # ── Public API ────────────────────────────────────────────────────────

    def is_cycle_mode(self) -> bool:
        return self.btn_temp_cycle.isChecked()

    def is_heating_only(self) -> bool:
        return self.radio_heat_only.isChecked()

    def get_settings(self) -> dict:
        """Return method configuration as a plain dict."""
        return {
            "cycle_mode":           self.is_cycle_mode(),
            "heating_only":         self.is_heating_only(),
            "measure_seebeck":      self.chk_seebeck.isChecked(),
            "measure_conductivity": self.chk_conductivity.isChecked(),
        }
