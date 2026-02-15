"""
Sample Information Panel.

Collects: sample name, diameter (mm), and thickness (mm).
"""

from PySide6.QtWidgets import (
    QGroupBox, QFormLayout, QLineEdit, QDoubleSpinBox,
)
from PySide6.QtCore import Signal

import sys, pathlib
_project_root = str(pathlib.Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
from constants import DEFAULT_SAMPLE_DIAMETER, DEFAULT_SAMPLE_THICKNESS


class SampleInfoPanel(QGroupBox):
    """Panel for entering sample metadata."""

    # Emitted whenever any field changes: (name, diameter_mm, thickness_mm)
    sample_changed = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__("Sample Information", parent)
        self._build_ui()
        self._connect_signals()

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(10)

        # Sample name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. BiTe-001")
        layout.addRow("Name:", self.name_edit)

        # Diameter
        self.diameter_spin = QDoubleSpinBox()
        self.diameter_spin.setRange(0.1, 100.0)
        self.diameter_spin.setDecimals(2)
        self.diameter_spin.setSuffix("  mm")
        self.diameter_spin.setValue(DEFAULT_SAMPLE_DIAMETER)
        layout.addRow("Diameter:", self.diameter_spin)

        # Thickness
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(0.01, 50.0)
        self.thickness_spin.setDecimals(2)
        self.thickness_spin.setSuffix("  mm")
        self.thickness_spin.setValue(DEFAULT_SAMPLE_THICKNESS)
        layout.addRow("Thickness:", self.thickness_spin)

    # ── Signals ────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.name_edit.textChanged.connect(self._emit_change)
        self.diameter_spin.valueChanged.connect(self._emit_change)
        self.thickness_spin.valueChanged.connect(self._emit_change)

    def _emit_change(self):
        self.sample_changed.emit(
            self.name_edit.text().strip(),
            self.diameter_spin.value(),
            self.thickness_spin.value(),
        )

    # ── Public getters ─────────────────────────────────────────────────

    def get_sample_name(self) -> str:
        return self.name_edit.text().strip()

    def get_diameter(self) -> float:
        return self.diameter_spin.value()

    def get_thickness(self) -> float:
        return self.thickness_spin.value()
