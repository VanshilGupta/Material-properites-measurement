"""Generate a simple placeholder logo for the app."""

import sys, pathlib

_ROOT = str(pathlib.Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)

size = 128
pm = QPixmap(size, size)
pm.fill(QColor("#282840"))

painter = QPainter(pm)
painter.setRenderHint(QPainter.Antialiasing)

# Circle
painter.setBrush(QColor("#4fc3f7"))
painter.setPen(Qt.NoPen)
painter.drawEllipse(8, 8, size - 16, size - 16)

# Text
painter.setPen(QColor("#1e1e2e"))
font = QFont("Segoe UI", 36, QFont.Bold)
painter.setFont(font)
painter.drawText(pm.rect(), Qt.AlignCenter, "TM")

painter.end()

out_path = pathlib.Path(__file__).resolve().parent / "assets" / "logo.png"
pm.save(str(out_path))
print(f"Logo saved to {out_path}")
