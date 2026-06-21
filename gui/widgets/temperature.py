"""Temperature Profile panel — target temperature and cycle settings."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QPushButton, QSizePolicy,
)

# Fixed pixel width for every label in the cycle-settings rows.
# Both columns of labels share this width so the spinboxes always
# start at the same horizontal position.
_CYCLE_LBL_W  = 46   # "Start:" / "Stop:" / "Step:"
_CYCLE_SPIN_W = 88   # comfortable minimum; expands until capped below
_CYCLE_SPIN_MAX = 155  # stops growing here; extra panel width = whitespace


class TemperatureProfilePanel(QGroupBox):
    """Panel for target temperature, ramp rate, and cycle settings.

    Signals
    -------
    set_temp_requested(target_celsius, ramp_rate)
        Emitted when user clicks SET — carries both the target temperature
        and the ramp rate so the controller can apply them atomically.
    """

    set_temp_requested = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__("TEMPERATURE PROFILE", parent)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 18, 10, 10)
        vbox.setSpacing(12)

        # ── Target Temperature & Ramp Rate ────────────────────────────────
        target_lbl = QLabel("Target temperature:")
        target_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        vbox.addWidget(target_lbl)

        target_row = QHBoxLayout()
        target_row.setSpacing(8)

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(25.0, 1500.0)
        self.target_spin.setValue(350.0)
        self.target_spin.setSuffix("  \u00b0C")
        self.target_spin.setDecimals(1)
        self.target_spin.setFixedWidth(120)
        self.target_spin.setCursor(Qt.PointingHandCursor)
        self.target_spin.setToolTip("Target temperature for the Eurotherm controller")

        self.set_btn = QPushButton("SET")
        self.set_btn.setCursor(Qt.PointingHandCursor)
        self.set_btn.setToolTip("Send target temperature and ramp rate to the controller")
        self.set_btn.setFixedWidth(54)
        self.set_btn.clicked.connect(self._on_set_clicked)

        # Rate spinner — always visible and enabled, not a cycle-only field.
        rate_prefix = QLabel("Rate:")
        rate_prefix.setStyleSheet("background: transparent; color: #909090;")

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.1, 50.0)
        self.rate_spin.setValue(10.0)
        self.rate_spin.setSuffix("  \u00b0C/min")
        self.rate_spin.setDecimals(1)
        self.rate_spin.setFixedWidth(170)
        self.rate_spin.setCursor(Qt.PointingHandCursor)
        self.rate_spin.setToolTip(
            "Ramp rate: how fast the furnace approaches the target (°C/min)"
        )

        target_row.addWidget(self.target_spin)
        target_row.addWidget(self.set_btn)
        target_row.addSpacing(10)
        target_row.addWidget(rate_prefix)
        target_row.addWidget(self.rate_spin)
        target_row.addStretch()
        vbox.addLayout(target_row)

        # ── Cycle Settings ────────────────────────────────────────────────
        cycle_lbl = QLabel("Cycle Settings:")
        cycle_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        vbox.addWidget(cycle_lbl)

        # Helper to build a labelled spinbox with consistent sizing.
        def _spin(label_text, lo, hi, default, suffix, tooltip):
            lbl = QLabel(label_text)
            lbl.setFixedWidth(_CYCLE_LBL_W)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sp = QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(default)
            sp.setSuffix(suffix)
            sp.setDecimals(1)
            sp.setMinimumWidth(_CYCLE_SPIN_W)
            sp.setMaximumWidth(_CYCLE_SPIN_MAX)
            sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            sp.setCursor(Qt.PointingHandCursor)
            sp.setToolTip(tooltip)
            return lbl, sp

        start_lbl, self.start_spin = _spin(
            "Start:", 25.0, 1500.0, 50.0, "  \u00b0C",
            "Start temperature of the measurement cycle",
        )
        stop_lbl, self.stop_spin = _spin(
            "Stop:", 25.0, 1500.0, 200.0, "  \u00b0C",
            "Stop temperature of the measurement cycle",
        )
        step_lbl, self.step_spin = _spin(
            "Step:", 1.0, 200.0, 25.0, "  \u00b0C",
            "Temperature step between measurements",
        )

        # Left-column labels align left, flush with "Cycle Settings:" header.
        start_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        step_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Row 0: Start | Stop
        row0 = QHBoxLayout()
        row0.setSpacing(6)
        row0.addWidget(start_lbl)
        row0.addWidget(self.start_spin)
        row0.addSpacing(10)
        row0.addWidget(stop_lbl)
        row0.addWidget(self.stop_spin)
        row0.addStretch()
        vbox.addLayout(row0)

        # Row 1: Step (Rate has moved to the target row)
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(step_lbl)
        row1.addWidget(self.step_spin)
        row1.addStretch()
        vbox.addLayout(row1)

        # Cycle-only widgets — disabled until cycle mode is active.
        self._cycle_widgets = [
            self.start_spin, self.stop_spin, self.step_spin,
        ]
        self.set_cycle_enabled(False)

    # ── Private slots ─────────────────────────────────────────────────────

    def _on_set_clicked(self):
        self.set_temp_requested.emit(
            self.target_spin.value(),
            self.rate_spin.value(),
        )

    # ── Public API ────────────────────────────────────────────────────────

    def set_cycle_enabled(self, enabled: bool):
        """Enable or disable cycle-settings spinboxes (always visible)."""
        for w in self._cycle_widgets:
            w.setEnabled(enabled)

    def get_settings(self) -> dict:
        return {
            "target_temp": self.target_spin.value(),
            "rate":        self.rate_spin.value(),
            "start_temp":  self.start_spin.value(),
            "stop_temp":   self.stop_spin.value(),
            "step":        self.step_spin.value(),
        }
