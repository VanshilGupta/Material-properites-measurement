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

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
