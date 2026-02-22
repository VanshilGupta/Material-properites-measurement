"""
Sample Information Panel.

Collects: sample name, diameter (mm), and thickness (mm).
"""

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QLabel, QSizePolicy,
)
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCore import Signal, Qt


class SampleInfoPanel(QGroupBox):
    """Panel for entering sample metadata."""

    sample_changed = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__("SAMPLE INFORMATION", parent)
        self._build_ui()
        self._connect_signals()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 18, 10, 10)
        vbox.setSpacing(0)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        # ── Name ─────────────────────────────────────────────────────────
        # Expands with the panel up to a comfortable cap; IBeam cursor by default.
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. BiTe-001")
        self.name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.name_edit.setMaximumWidth(460)
        form.addRow("Name:", self.name_edit)

        # ── Diameter + Thickness on one row ──────────────────────────────
        # Both inputs are fixed-width numeric fields; trailing stretch ensures
        # the row never overflows past the Name field's right edge.
        self.diameter_edit = QLineEdit()
        self.diameter_edit.setPlaceholderText("e.g. 5.00")
        self.diameter_edit.setValidator(QDoubleValidator(0.001, 100.0, 2))
        self.diameter_edit.setFixedWidth(110)
        self.diameter_edit.setToolTip("Sample diameter in millimetres")

        self.thickness_edit = QLineEdit()
        self.thickness_edit.setPlaceholderText("e.g. 2.00")
        self.thickness_edit.setValidator(QDoubleValidator(0.001, 50.0, 2))
        self.thickness_edit.setFixedWidth(110)
        self.thickness_edit.setToolTip("Sample thickness in millimetres")

        thk_lbl = QLabel("Thickness:")
        thk_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        dim_row = QHBoxLayout()
        dim_row.setSpacing(5)
        dim_row.addWidget(self.diameter_edit)
        dim_row.addWidget(QLabel("mm"))
        dim_row.addSpacing(14)
        dim_row.addWidget(thk_lbl)
        dim_row.addWidget(self.thickness_edit)
        dim_row.addWidget(QLabel("mm"))
        # Trailing stretch absorbs all extra form-field width so the "mm"
        # label never drifts right past the Name field's right edge.
        dim_row.addStretch()

        form.addRow("Diameter:", dim_row)

        vbox.addLayout(form)

    # ── Signals ──────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.name_edit.textChanged.connect(self._emit_change)
        self.diameter_edit.textChanged.connect(self._emit_change)
        self.thickness_edit.textChanged.connect(self._emit_change)

    def _emit_change(self):
        self.sample_changed.emit(
            self.name_edit.text().strip(),
            self.get_diameter(),
            self.get_thickness(),
        )

    # ── Public getters ───────────────────────────────────────────────────

    def get_sample_name(self) -> str:
        return self.name_edit.text().strip()

    def get_diameter(self) -> float:
        try:
            return float(self.diameter_edit.text())
        except ValueError:
            return 0.0

    def get_thickness(self) -> float:
        try:
            return float(self.thickness_edit.text())
        except ValueError:
            return 0.0
