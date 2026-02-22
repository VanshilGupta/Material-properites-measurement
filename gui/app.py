"""
Application entry point — creates QApplication, shows the main window.

This file is also the target for PyInstaller / cx_Freeze when building
a standalone .exe:

    pyinstaller --onefile --windowed app.py
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
import pathlib

# Ensure the project root is on sys.path so that `constants`, `eurotherm_control`,
# etc. can be imported inside sub-modules.
_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Thermoelectric Measurement System")

    # Application icon (same logo used in the title bar)
    icon_path = pathlib.Path(__file__).resolve().parent.parent / "assets" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Size to half screen BEFORE show() so Qt doesn't override it
    screen_geo = app.primaryScreen().availableGeometry()
    target_w = max(1000, screen_geo.width() // 2)
    target_h = max(520, screen_geo.height() // 2)
    window = MainWindow()
    window.resize(target_w, target_h)
    window.move(
        screen_geo.x() + (screen_geo.width() - target_w) // 2,
        screen_geo.y() + (screen_geo.height() - target_h) // 2,
    )
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
