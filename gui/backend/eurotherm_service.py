"""
Eurotherm Service — Thread-safe furnace temperature control.

Wraps the existing EurothermController so that serial communication
runs on a background QThread and never blocks the GUI.

Architecture
------------
GUI thread                          Worker thread
───────────                         ─────────────
EurothermService  ──signals──►  _EurothermWorker
   (public API)                   (serial I/O)
                  ◄──signals──

All cross-thread calls use Qt's queued signal→slot mechanism.
The GUI thread never touches the serial port directly.

Signals (emitted on the GUI thread)
------------------------------------
temperature_read : float
    Emitted periodically (every POLL_INTERVAL_MS) with the current
    furnace temperature in °C.
set_point_reached : float
    Emitted when the furnace accepts the new set-point.
error_occurred : str
    Emitted on any communication error.
connection_changed : bool
    Emitted when connection state changes (True = connected).
"""

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
import sys
import pathlib

# Make the project root importable so we can reuse eurotherm_control.py
_project_root = str(pathlib.Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from eurotherm_control import EurothermController          # noqa: E402
from constants import (                                    # noqa: E402
    EUROTHERM_COM_PORT,
    EUROTHERM_DEVICE_ADDRESS,
    EUROTHERM_BAUD_RATE,
    EUROTHERM_TIMEOUT,
)
from seebeck_measurement.instruments import get_eurotherm  # noqa: E402

# How long to wait between successive temperature reads.
# Using a single-shot pattern (reschedule *after* each read completes)
# so reads never pile up when the serial port is slow or the furnace
# is under load.  1 s gives a smooth live display at 9600 baud —
# each MODBUS float read is only ~20 bytes each way (~20 ms on wire).
POLL_INTERVAL_MS = 1000


# =====================================================================
# Worker (lives on the background QThread)
# =====================================================================

class _EurothermWorker(QObject):
    """
    Worker that lives on a QThread and owns the serial connection.

    All serial I/O happens here — the GUI never touches the controller
    directly; it invokes slots via queued signal-slot connections.
    """

    # Outbound signals (forwarded to EurothermService → GUI)
    temperature_read        = Signal(float)
    temperature_read_failed = Signal()      # read succeeded protocol-wise but returned None
    set_point_reached       = Signal(float)
    error_occurred          = Signal(str)
    connection_changed      = Signal(bool)

    def __init__(self):
        super().__init__()
        # get_eurotherm() returns EurothermController (local) or
        # RemoteEurothermController (remote) depending on REMOTE_MODE.
        self._controller = get_eurotherm()
        # _polling flag controls whether single-shot reschedule continues.
        self._polling: bool = False

    # -- slots invoked from the GUI thread via queued connections -----------

    @Slot()
    def connect_to_furnace(self):
        """Open the serial port and begin periodic temperature polling."""
        try:
            ok = self._controller.connect()
            self.connection_changed.emit(ok)
            if ok:
                # Emit one immediate reading so the UI updates right away.
                temp = self._controller.read_temperature()
                if temp is not None:
                    self.temperature_read.emit(temp)
                self._start_polling()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            self.connection_changed.emit(False)

    @Slot()
    def disconnect_from_furnace(self):
        """Stop polling and close the serial port."""
        self._stop_polling()
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
                self.error_occurred.emit(
                    f"Failed to set temperature to {target:.1f} °C"
                )
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    @Slot(float)
    def set_ramp_rate(self, rate: float):
        """Set the furnace ramp rate in °C/min."""
        try:
            if not self._controller.is_connected():
                self.error_occurred.emit("Eurotherm not connected")
                return
            self._controller.set_ramp_rate(rate)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    @Slot()
    def read_temperature(self):
        """Read current furnace temperature, emit it, then reschedule."""
        try:
            if not self._controller.is_connected():
                return
            temp = self._controller.read_temperature()
            if temp is not None:
                self.temperature_read.emit(temp)
            else:
                # Controller responded but returned no usable value
                # (bad CRC, short frame, timeout, etc.).
                self.temperature_read_failed.emit()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            # Reschedule only after this read is fully done — prevents overlap.
            if self._polling:
                QTimer.singleShot(POLL_INTERVAL_MS, self.read_temperature)

    # -- internal helpers --------------------------------------------------

    def _start_polling(self):
        """Begin the single-shot polling chain."""
        if self._polling:
            return  # already running
        self._polling = True
        QTimer.singleShot(POLL_INTERVAL_MS, self.read_temperature)

    def _stop_polling(self):
        """Signal the polling chain to stop after the current read."""
        self._polling = False


# =====================================================================
# Service (public API — lives on the GUI thread)
# =====================================================================

class EurothermService(QObject):
    """
    Public API that the GUI uses.

    Usage
    -----
    >>> service = EurothermService()
    >>> service.temperature_read.connect(update_label)
    >>> service.start()                 # spawns the worker thread
    >>> service.set_temperature(150.0)  # non-blocking, thread-safe
    """

    # Re-export worker signals so the GUI only talks to this object.
    temperature_read        = Signal(float)
    temperature_read_failed = Signal()
    set_point_reached       = Signal(float)
    error_occurred          = Signal(str)
    connection_changed      = Signal(bool)

    # Private signals used to invoke worker slots across threads.
    # Qt delivers these via the worker thread's event loop (queued).
    _request_connect = Signal()
    _request_disconnect = Signal()
    _request_set_temp = Signal(float)
    _request_set_rate = Signal(float)
    _request_read_temp = Signal()

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = _EurothermWorker()
        self._worker.moveToThread(self._thread)

        # Forward worker signals → our own signals (auto-queued because
        # the worker lives on a different thread).
        self._worker.temperature_read.connect(self.temperature_read)
        self._worker.temperature_read_failed.connect(self.temperature_read_failed)
        self._worker.set_point_reached.connect(self.set_point_reached)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.connection_changed.connect(self.connection_changed)

        # Wire private request signals → worker slots (queued delivery).
        self._request_connect.connect(self._worker.connect_to_furnace)
        self._request_disconnect.connect(self._worker.disconnect_from_furnace)
        self._request_set_temp.connect(self._worker.set_temperature)
        self._request_set_rate.connect(self._worker.set_ramp_rate)
        self._request_read_temp.connect(self._worker.read_temperature)

    # -- public methods (safe to call from any thread) ---------------------

    def start(self):
        """Start the background thread and connect to the furnace."""
        if self._thread.isRunning():
            return
        self._thread.start()
        # Emit a signal; Qt queues it for the worker's event loop.
        self._request_connect.emit()

    def stop(self):
        """Disconnect and stop the background thread gracefully."""
        if not self._thread.isRunning():
            return
        self._request_disconnect.emit()
        self._thread.quit()
        self._thread.wait(3000)

    def set_temperature(self, target_celsius: float):
        """Request the furnace to ramp to *target_celsius* °C."""
        self._request_set_temp.emit(target_celsius)

    def set_ramp_rate(self, rate_per_min: float):
        """Set the furnace ramp rate in °C/min before sending a setpoint."""
        self._request_set_rate.emit(rate_per_min)

    def read_temperature(self):
        """Request a single temperature reading (result via signal)."""
        self._request_read_temp.emit()
