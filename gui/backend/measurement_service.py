"""
Measurement Service — Thread-safe sigma / seebeck measurement execution.

Runs the actual measurement functions on a background QThread so the GUI
stays responsive.  Mirrors exactly what ``run_sigma.py``,
``run_seebeck.py`` and ``run_combined.py`` do in the terminal, but emits
Qt signals for log messages and results instead of printing to stdout.

Architecture
------------
GUI thread                          Worker thread
───────────                         ─────────────
MeasurementService  ──signals──►  _MeasurementWorker
   (public API)                      (instrument I/O)
                    ◄──signals──

Abort
-----
``request_abort()`` sets a ``threading.Event``.  The worker checks
``_abort_event.is_set()`` between major steps (before sigma, before
seebeck, between VDP iterations) and bails out cleanly if set.
"""

from __future__ import annotations

import logging
import threading
import traceback
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

import sys
import pathlib

_project_root = str(pathlib.Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from output_manager import (                                # noqa: E402
    create_single_measurement_structure,
    finalize_logging,
)
from measure_sigma import measure_sigma, save_results_to_csv  # noqa: E402
from seebeck_measurement import SeebeckMeasurement           # noqa: E402
from constants import read_current_temperature                # noqa: E402

# Instrument name constants (avoids duplicating literals).
_INST_PS  = "Power Supply"
_INST_DAQ = "Multimeter"


# ─── Custom log handler that emits a Qt signal ──────────────────────────

class _QtLogHandler(logging.Handler):
    """Logging handler that calls a callback for every log record.

    The callback is thread-safe because Qt signal emission from a
    non-GUI thread is automatically queued.
    """

    def __init__(self, callback):
        super().__init__(level=logging.INFO)
        self._callback = callback

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._callback(msg)
        except Exception:
            self.handleError(record)


# ─── Abort sentinel ─────────────────────────────────────────────────────

class MeasurementAborted(Exception):
    """Raised when the user requests an abort."""


# =====================================================================
# Worker (lives on the background QThread)
# =====================================================================

class _MeasurementWorker(QObject):
    """Executes sigma / seebeck measurements on a background thread."""

    # Outbound signals → forwarded by MeasurementService to the GUI.
    log_message          = Signal(str)
    status_message       = Signal(str)
    instrument_status    = Signal(str, str)   # (name, state)
    sigma_completed      = Signal(dict)
    seebeck_completed    = Signal(dict)
    seebeck_data_point   = Signal(dict)       # real-time T1, T2, V1, V2, time
    measurement_finished = Signal(bool, str)  # (success, summary)

    def __init__(self):
        super().__init__()
        self._abort_event = threading.Event()

    # ── public control ───────────────────────────────────────────────────

    def reset_abort(self):
        self._abort_event.clear()

    def request_abort(self):
        self._abort_event.set()

    @property
    def aborted(self) -> bool:
        return self._abort_event.is_set()

    # ── helpers ──────────────────────────────────────────────────────────

    def _check_abort(self, stage: str = ""):
        """Raise ``MeasurementAborted`` if the abort flag is set."""
        if self.aborted:
            raise MeasurementAborted(f"Aborted during {stage}" if stage else "Aborted")

    def _interruptible_sleep(self, seconds: float, stage: str = ""):
        """Sleep in small increments, checking abort between each."""
        remaining = seconds
        while remaining > 0:
            chunk = min(remaining, 0.25)
            time.sleep(chunk)
            remaining -= chunk
            self._check_abort(stage)

    def _log(self, msg: str):
        self.log_message.emit(msg)

    def _make_logger(self, file_logger: logging.Logger) -> logging.Logger:
        """Attach a Qt handler to *file_logger* so messages also reach the GUI."""
        qt_handler = _QtLogHandler(self._log)
        qt_handler.setFormatter(logging.Formatter("%(message)s"))
        file_logger.addHandler(qt_handler)
        return file_logger

    def _set_instruments(self, state: str):
        """Emit status for both Power Supply and Multimeter."""
        self.instrument_status.emit(_INST_PS, state)
        self.instrument_status.emit(_INST_DAQ, state)

    # ── sigma sub-routine ────────────────────────────────────────────────

    def _run_sigma(self, config: dict, current_temp: float,
                   sigma_folder: Path, temp_logger, global_logger) -> Optional[dict]:
        """Execute σ measurement.  Returns results dict or None."""
        self._check_abort("before sigma")
        self._log("━━ Starting σ (conductivity) measurement ━━")
        self.status_message.emit("Measuring σ …")
        self._set_instruments("active")

        temp_logger.info("Starting SIGMA measurement …")
        thickness = config["thickness"]
        diameter  = config["diameter"]
        sample_name = config["sample_name"]

        try:
            self._log(f"Sample: {thickness} mm × {diameter} mm  |  5 VDP iterations")
            results = measure_sigma(
                sample_t=thickness, sample_dia=diameter,
                verbose=True, logger=temp_logger,
            )

            if results:
                results["temperature"] = current_temp
                save_results_to_csv(
                    results,
                    f"{sample_name}_{current_temp:.1f}C",
                    str(sigma_folder),
                )
                # Log detailed results
                self._log(f"Current measured: {results.get('current', 0):.6f} A")
                raw = results.get('sigma_raw')
                if raw is not None:
                    for idx, s in enumerate(raw):
                        self._log(f"  Iteration {idx+1}: σ = {s:.2f} S/cm")
                self._log(
                    f"Valid: {results.get('valid_count', '?')}/5  |  "
                    f"Std dev: {results.get('std_dev', 0):.4f}"
                )
                self._log(f"σ = {results['corr_sigma']:.2e} S/cm  ✓")
                global_logger.info(
                    f"SIGMA completed: {results['corr_sigma']:.2e} S/cm"
                )
                self.sigma_completed.emit(results)
            else:
                self._log("σ measurement returned no results ✗")
                global_logger.error("Sigma measurement returned no results")
            return results
        except MeasurementAborted:
            raise
        except Exception as exc:
            self._log(f"σ measurement error: {exc}")
            global_logger.error(f"Sigma failed: {exc}")
            temp_logger.error(traceback.format_exc())
            return None
        finally:
            self._set_instruments("idle")

    # ── seebeck sub-routine ──────────────────────────────────────────────

    def _run_seebeck(self, config: dict, current_temp: float,
                     seebeck_folder: Path, temp_logger, global_logger) -> Optional[dict]:
        """Execute Seebeck measurement.  Returns results dict or None."""
        self._check_abort("before seebeck")
        self._log("━━ Starting Seebeck coefficient measurement ━━")
        self.status_message.emit("Measuring Seebeck …")
        self._set_instruments("active")

        temp_logger.info("Starting SEEBECK measurement …")
        sample_name  = config["sample_name"]
        seebeck_time = config.get("seebeck_time", 480.0)
        filename = f"{sample_name}_{current_temp:.1f}C"

        try:
            measurement = SeebeckMeasurement(enable_plotting=False)

            # Monkey-patch the plotter update to also emit a Qt signal
            _orig_update = None
            if measurement.plotter is not None:
                _orig_update = measurement.plotter.update

            _worker_ref = self

            class _QtPlotBridge:
                """Intercepts Seebeck plotter calls and emits data to GUI."""
                def update(_, t, t1, t2, v1, v2):  # noqa: N805,N803
                    _worker_ref.seebeck_data_point.emit({
                        "time": t, "T1": t1, "T2": t2,
                        "V1": v1, "V2": v2,
                    })
                    if _orig_update:
                        _orig_update(t, t1, t2, v1, v2)

            # Replace the plotter with our bridge so data reaches the GUI
            measurement.plotter = _QtPlotBridge()

            results = measurement.run_measurement(
                filename=filename,
                measurement_time=seebeck_time,
                output_folder=str(seebeck_folder),
                logger=temp_logger,
            )
            results["temperature"] = current_temp

            self._log(
                f"S = {results['Seebeck']:.2f} µV/K  "
                f"(R² = {results['adj_r_square']:.4f})  ✓"
            )
            global_logger.info(
                f"SEEBECK completed: {results['Seebeck']:.2f} µV/K"
            )
            self.seebeck_completed.emit(results)
            return results
        except MeasurementAborted:
            raise
        except Exception as exc:
            self._log(f"Seebeck measurement error: {exc}")
            global_logger.error(f"Seebeck failed: {exc}")
            temp_logger.error(traceback.format_exc())
            return None
        finally:
            self._set_instruments("idle")

    # ── sleep monkey-patch helpers ──────────────────────────────────────

    def _install_abortable_sleep(self):
        """Replace ``time.sleep`` with an abort-aware version.

        Returns the original ``time.sleep`` so it can be restored later.
        """
        _real_sleep = time.sleep

        def _abortable_sleep(seconds):
            remaining = seconds
            while remaining > 0:
                chunk = min(remaining, 0.25)
                _real_sleep(chunk)
                remaining -= chunk
                if self.aborted:
                    raise MeasurementAborted("Aborted during sleep")

        time.sleep = _abortable_sleep
        return _real_sleep

    # ── folder / logger bootstrap ────────────────────────────────────────

    def _prepare_folders(self, config, current_temp, do_sigma, do_seebeck):
        """Create output folders and loggers; return context tuple."""
        mtype = "sigma" if do_sigma else "seebeck"
        result = create_single_measurement_structure(
            config["sample_name"], mtype, temperature=current_temp,
        )
        _, global_logger, temp_folder, temp_logger, _ = result

        sigma_folder   = temp_folder / "Sigma"
        seebeck_folder = temp_folder / "Seebeck"
        if do_sigma:
            sigma_folder.mkdir(parents=True, exist_ok=True)
        if do_seebeck:
            seebeck_folder.mkdir(parents=True, exist_ok=True)

        self._make_logger(global_logger)
        self._make_logger(temp_logger)
        global_logger.info(
            f"Starting measurement — {config['sample_name']} "
            f"({config['thickness']} mm × {config['diameter']} mm) "
            f"at {current_temp:.1f} °C"
        )
        return global_logger, temp_folder, temp_logger, sigma_folder, seebeck_folder

    # ── main entry point (called via signal) ─────────────────────────────

    @Slot(dict)
    def run(self, config: dict):
        """Execute the full measurement sequence.

        Parameters
        ----------
        config : dict
            sample_name       : str
            diameter           : float  (mm)
            thickness          : float  (mm)
            measure_sigma      : bool
            measure_seebeck    : bool
            seebeck_time       : float  (seconds, default 480)
        """
        self.reset_abort()
        do_sigma   = config["measure_sigma"]
        do_seebeck = config["measure_seebeck"]

        global_logger: Optional[logging.Logger] = None
        temp_logger:   Optional[logging.Logger] = None

        _real_sleep = self._install_abortable_sleep()

        try:
            # ── Read current temperature ──────────────────────────────────
            self._log("Reading current temperature …")
            self.status_message.emit("Reading temperature …")
            current_temp = read_current_temperature()
            self._log(f"Current temperature: {current_temp:.1f} °C")
            self._check_abort("temperature read")

            # ── Create folder structure ───────────────────────────────────
            (global_logger, temp_folder, temp_logger,
             sigma_folder, seebeck_folder) = self._prepare_folders(
                config, current_temp, do_sigma, do_seebeck)

            # ── Run measurements ─────────────────────────────────────────
            sigma_results = (
                self._run_sigma(config, current_temp, sigma_folder,
                                temp_logger, global_logger)
                if do_sigma else None
            )

            if do_sigma and do_seebeck:
                self._check_abort("between measurements")
                self._log("Safety pause (2 s) …")
                self._interruptible_sleep(2.0, "safety pause")

            seebeck_results = (
                self._run_seebeck(config, current_temp, seebeck_folder,
                                  temp_logger, global_logger)
                if do_seebeck else None
            )

            # ── Summary ──────────────────────────────────────────────────
            parts = []
            if sigma_results:
                parts.append(f"σ = {sigma_results['corr_sigma']:.2e} S/cm")
            if seebeck_results:
                parts.append(f"S = {seebeck_results['Seebeck']:.2f} µV/K")

            summary = " │ ".join(parts) if parts else "No results"
            self._log(f"Measurement complete — {summary}")
            self._log(f"Data saved → {temp_folder}")
            self.status_message.emit(f"Complete — {summary}")
            finalize_logging(temp_logger, success=True)
            finalize_logging(global_logger, success=True)
            self.measurement_finished.emit(True, summary)

        except MeasurementAborted:
            self._log("Measurement ABORTED by user")
            self.status_message.emit("Measurement aborted")
            self._finalize_loggers(global_logger, temp_logger, "User aborted")
            self._set_instruments("idle")
            self.measurement_finished.emit(False, "Aborted by user")

        except Exception as exc:
            self._log(f"FATAL: {exc}")
            self.status_message.emit(f"Error: {exc}")
            self._finalize_loggers(global_logger, temp_logger, str(exc))
            self._set_instruments("idle")
            self.measurement_finished.emit(False, str(exc))

        finally:
            # Always restore the real time.sleep
            time.sleep = _real_sleep

    def _finalize_loggers(self, global_logger, temp_logger, error_msg: str):
        """Close file loggers on failure / abort."""
        if temp_logger:
            finalize_logging(temp_logger, success=False, error_msg=error_msg)
        if global_logger:
            finalize_logging(global_logger, success=False, error_msg=error_msg)


# =====================================================================
# Service (public API — lives on the GUI thread)
# =====================================================================

class MeasurementService(QObject):
    """Public API consumed by ``MainWindow``.

    Usage
    -----
    >>> svc = MeasurementService()
    >>> svc.log_message.connect(log_panel.append)
    >>> svc.start(config_dict)
    """

    # Re-exported signals (auto-queued from worker thread).
    log_message          = Signal(str)
    status_message       = Signal(str)
    instrument_status    = Signal(str, str)
    sigma_completed      = Signal(dict)
    seebeck_completed    = Signal(dict)
    seebeck_data_point   = Signal(dict)
    measurement_finished = Signal(bool, str)

    # Private signal to invoke the worker's ``run`` slot across threads.
    _request_run = Signal(dict)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = _MeasurementWorker()
        self._worker.moveToThread(self._thread)

        # Forward worker signals → own signals.
        self._worker.log_message.connect(self.log_message)
        self._worker.status_message.connect(self.status_message)
        self._worker.instrument_status.connect(self.instrument_status)
        self._worker.sigma_completed.connect(self.sigma_completed)
        self._worker.seebeck_completed.connect(self.seebeck_completed)
        self._worker.seebeck_data_point.connect(self.seebeck_data_point)
        self._worker.measurement_finished.connect(self.measurement_finished)

        # Wire the run request.
        self._request_run.connect(self._worker.run)

    # ── public API ───────────────────────────────────────────────────────

    def start(self, config: dict):
        """Begin a measurement run with *config*.  Non-blocking."""
        if not self._thread.isRunning():
            self._thread.start()
        self._request_run.emit(config)

    def request_abort(self):
        """Ask the running measurement to stop as soon as possible."""
        self._worker.request_abort()

    def stop(self):
        """Shut down the worker thread (call on application exit)."""
        self._worker.request_abort()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()
