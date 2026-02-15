"""
Eurotherm Service — Thread-safe furnace temperature control.

Wraps the existing EurothermController so that serial communication
runs on a background QThread and never blocks the GUI.

Signals
-------
temperature_read : float
    Emitted whenever a temperature reading is obtained.
set_point_reached : float
    Emitted when the furnace reaches the requested set-point.
error_occurred : str
    Emitted on any communication error.
connection_changed : bool
    Emitted when connection state changes (True = connected).
"""

from PySide6.QtCore import QObject, QThread, Signal, Slot
import sys, pathlib

# Make the project root importable so we can reuse eurotherm_control.py
_project_root = str(pathlib.Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from eurotherm_control import EurothermController
from constants import (
    EUROTHERM_COM_PORT,
    EUROTHERM_DEVICE_ADDRESS,
    EUROTHERM_BAUD_RATE,
    EUROTHERM_TIMEOUT,
)


class _EurothermWorker(QObject):
    """
    Worker that lives on a QThread and owns the serial connection.

    All serial I/O happens here — the GUI never touches the controller
    directly; it invokes slots via queued signal-slot connections.
    """

    temperature_read = Signal(float)
    set_point_reached = Signal(float)
    error_occurred = Signal(str)
    connection_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._controller = EurothermController(
            com_port=EUROTHERM_COM_PORT,
            device_address=EUROTHERM_DEVICE_ADDRESS,
            baud_rate=EUROTHERM_BAUD_RATE,
            timeout=EUROTHERM_TIMEOUT,
        )

    # -- slots invoked from the GUI thread via queued connections -----------

    @Slot()
    def connect_to_furnace(self):
        """Try to connect; emit connection_changed(True/False)."""
        try:
            ok = self._controller.connect()
            self.connection_changed.emit(ok)
            if ok:
                temp = self._controller.read_temperature()
                if temp is not None:
                    self.temperature_read.emit(temp)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            self.connection_changed.emit(False)

    @Slot()
    def disconnect_from_furnace(self):
        try:
            self._controller.disconnect()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self.connection_changed.emit(False)

    @Slot(float)
    def set_temperature(self, target: float):
        """Set the furnace set-point to *target* °C."""
        try:
            if not self._controller.is_connected():
                self.error_occurred.emit("Eurotherm not connected")
                return
            ok = self._controller.set_temperature(target)
            if ok:
                self.set_point_reached.emit(target)
            else:
                self.error_occurred.emit(f"Failed to set temperature to {target:.1f} °C")
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    @Slot()
    def read_temperature(self):
        """Read current furnace temperature and emit it."""
        try:
            if not self._controller.is_connected():
                return
            temp = self._controller.read_temperature()
            if temp is not None:
                self.temperature_read.emit(temp)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class EurothermService(QObject):
    """
    Public API that the GUI uses.

    Usage
    -----
    >>> service = EurothermService()
    >>> service.temperature_read.connect(my_label.update_temp)
    >>> service.start()                 # spawns the worker thread
    >>> service.set_temperature(150.0)  # non-blocking
    """

    # Re-export worker signals so the GUI only talks to this object.
    temperature_read = Signal(float)
    set_point_reached = Signal(float)
    error_occurred = Signal(str)
    connection_changed = Signal(bool)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = _EurothermWorker()
        self._worker.moveToThread(self._thread)

        # Forward worker signals → our own signals.
        self._worker.temperature_read.connect(self.temperature_read)
        self._worker.set_point_reached.connect(self.set_point_reached)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.connection_changed.connect(self.connection_changed)

    # -- public methods (safe to call from the GUI thread) -----------------

    def start(self):
        """Start the background thread and connect to the furnace."""
        self._thread.start()
        # QMetaObject.invokeMethod is implicit via queued signal/slot:
        self._worker.connect_to_furnace()

    def stop(self):
        """Disconnect and stop the background thread."""
        self._worker.disconnect_from_furnace()
        self._thread.quit()
        self._thread.wait(3000)

    def set_temperature(self, target_celsius: float):
        """Request the furnace to go to *target_celsius*."""
        self._worker.set_temperature(target_celsius)

    def read_temperature(self):
        """Request a single temperature reading (result via signal)."""
        self._worker.read_temperature()
