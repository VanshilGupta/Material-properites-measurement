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
    create_temp_sweep_structure,
    create_temperature_folder,
    finalize_logging,
)
from measure_sigma import (                                 # noqa: E402
    MeasurementAborted, measure_sigma,
    save_results_to_csv, save_iteration_data_to_csv,
)
from seebeck_measurement import SeebeckMeasurement           # noqa: E402
from constants import is_valid_temperature, read_current_temperature  # noqa: E402

# Instrument name constants (avoids duplicating literals).
_INST_PS  = "Power Supply"
_INST_DAQ = "Multimeter"

# Furnace set-point applied whenever a temperature cycle ends (°C).
_COOL_DOWN_TEMP_C = 25.0

# Reading the actual temperature at a cycle point: tries before the point is
# skipped, and the pause between tries (s).
_TEMP_READ_ATTEMPTS = 3
_TEMP_RETRY_DELAY_S = 10.0

# Cycle start point (no stabilisation hold): "reached" tolerance (°C), how
# often to check (s), and the slack added to the expected ramp time before
# measuring anyway (s).
_START_REACH_TOLERANCE_C = 2.0
_START_POLL_S = 10.0
_START_REACH_MARGIN_S = 30 * 60.0


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
# ``MeasurementAborted`` (imported above from measure_sigma) is raised when the
# user requests an abort.  It is defined there so the σ code can let it
# propagate — switching the power supply off — instead of swallowing it.


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
    sigma_data_point     = Signal(dict)       # real-time per-iteration sigma data
    seebeck_fit_ready    = Signal(dict)       # V1, V2 arrays + fit params
    phase_changed        = Signal(str)        # "sigma" | "seebeck" | "idle"
    
    # Cycle mode hooks
    cycle_point_starting = Signal(int, float)             # (index, target_temp)
    cycle_point_completed = Signal(float, object, object, str) # (actual_temp, sigma_res, seebeck_res, temp_folder)
    measurement_finished = Signal(bool, str, dict)  # (success, summary, metadata)

    def __init__(self, furnace=None):
        super().__init__()
        self._abort_event = threading.Event()
        # EurothermService that owns the single furnace connection; the
        # temperature cycle borrows its controller (see _acquire_furnace).
        self._furnace = furnace

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
        self.phase_changed.emit("sigma")

        temp_logger.info("Starting SIGMA measurement …")
        thickness = config["thickness"]
        diameter  = config["diameter"]
        sample_name = config["sample_name"]

        # Progress callback — emits real-time per-iteration data to the GUI
        def _sigma_progress(iter_data: dict):
            self.sigma_data_point.emit(iter_data)

        try:
            self._log(f"Sample: {thickness} mm × {diameter} mm  |  5 VDP iterations")
            results = measure_sigma(
                sample_t=thickness, sample_dia=diameter,
                verbose=True, logger=temp_logger,
                progress_callback=_sigma_progress,
            )

            if results:
                results["temperature"] = current_temp
                save_results_to_csv(
                    results,
                    f"{sample_name}_{current_temp:.1f}C",
                    str(sigma_folder),
                )
                # Save per-iteration CSV
                save_iteration_data_to_csv(
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
        self.phase_changed.emit("seebeck")

        temp_logger.info("Starting SEEBECK measurement …")
        sample_name  = config["sample_name"]
        seebeck_time = config.get("seebeck_time", 480.0)
        filename = f"{sample_name}_{current_temp:.1f}C"
        self._log(f"Duration: {seebeck_time/60:.1f} min  |  File: {filename}")

        try:
            measurement = SeebeckMeasurement(enable_plotting=False)

            # Monkey-patch the plotter with a bridge that:
            #   1. Emits real-time data to the GUI graphs
            #   2. Logs periodic status to the log panel
            #   3. Provides a no-op save_plot so the finally block doesn't crash
            _worker_ref = self
            _point_count = 0

            class _QtPlotBridge:
                """Duck-typed plotter replacement for GUI mode."""

                def update(_, t, t1, t2, v1, v2):  # noqa: N805,N803
                    nonlocal _point_count
                    _point_count += 1
                    _worker_ref.seebeck_data_point.emit({
                        "time": t, "T1": t1, "T2": t2,
                        "V1": v1, "V2": v2,
                    })
                    # Log a status line every 10 readings
                    if _point_count % 10 == 1:
                        _worker_ref._log(
                            f"Seebeck #{_point_count}  t={t:.0f}s  "
                            f"T1={t1:.2f}°C  T2={t2:.2f}°C  "
                            f"ΔT={abs(t1 - t2):.2f}°C"
                        )

                def save_plot(_, *args, **kwargs):  # noqa: N805
                    """No-op — GUI graphs replace matplotlib plots."""

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

            # Emit fit data for the V₁ vs V₂ graph in the GUI
            data_avg = results.get("data_avg")
            if data_avg is not None and len(data_avg) > 0:
                import numpy as _np
                self.seebeck_fit_ready.emit({
                    "V1": data_avg[:, 3].tolist(),   # V1 in µV
                    "V2": data_avg[:, 4].tolist(),   # V2 in µV
                    "slope": results.get("slope", 0),
                    "intercept": results.get("offset", 0),
                    "adj_r_square": results.get("adj_r_square", 0),
                    "seebeck": results.get("Seebeck", 0),
                })

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
            base_dir=config.get("base_dir"),
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

    # ── Seebeck time-series graph saving ──────────────────────────────────

    def _save_seebeck_time_series_plots(self, seebeck_folder: Path,
                                         filename: str, results: dict):
        """Save Time vs T1/T2 and Time vs V1/V2 plots to disk."""
        try:
            import matplotlib
            matplotlib.use("Agg")  # non-interactive backend
            import matplotlib.pyplot as plt
            import numpy as np

            data_avg = results.get("data_avg")
            if data_avg is None or len(data_avg) == 0:
                return

            time_min = data_avg[:, 0] / 60.0   # seconds → minutes
            T1 = data_avg[:, 1]
            T2 = data_avg[:, 2]
            V1_uV = data_avg[:, 3]  # already in µV
            V2_uV = data_avg[:, 4]

            plots_dir = seebeck_folder / "plots"
            plots_dir.mkdir(parents=True, exist_ok=True)

            # ── Time vs T1/T2 ─────────────────────────────────────────────
            fig1, ax1 = plt.subplots(figsize=(10, 5))
            ax1.plot(time_min, T1, "r-", label="T\u2081", alpha=0.8)
            ax1.plot(time_min, T2, "b-", label="T\u2082", alpha=0.8)
            ax1.set_xlabel("Time (min)", fontsize=11, fontweight="bold")
            ax1.set_ylabel("Temperature (°C)", fontsize=11, fontweight="bold")
            ax1.set_title(f"{filename} — Temperature vs Time", fontsize=13, fontweight="bold")
            ax1.legend(fontsize=10)
            ax1.grid(True, alpha=0.3)
            fig1.tight_layout()
            fig1.savefig(plots_dir / f"{filename}_time_vs_temperature.png",
                         dpi=200, bbox_inches="tight")
            plt.close(fig1)

            # ── Time vs V1/V2 ─────────────────────────────────────────────
            fig2, ax2 = plt.subplots(figsize=(10, 5))
            ax2.plot(time_min, V1_uV, "m-", label="V\u2081", alpha=0.8)
            ax2.plot(time_min, V2_uV, "c-", label="V\u2082", alpha=0.8)
            ax2.set_xlabel("Time (min)", fontsize=11, fontweight="bold")
            ax2.set_ylabel("Voltage (µV)", fontsize=11, fontweight="bold")
            ax2.set_title(f"{filename} — Voltage vs Time", fontsize=13, fontweight="bold")
            ax2.legend(fontsize=10)
            ax2.grid(True, alpha=0.3)
            fig2.tight_layout()
            fig2.savefig(plots_dir / f"{filename}_time_vs_voltage.png",
                         dpi=200, bbox_inches="tight")
            plt.close(fig2)

            self._log("Saved time-series plots (T and V vs time)")
        except Exception as exc:
            self._log(f"Warning: could not save time-series plots: {exc}")

    # ── Sigma iteration plot saving ──────────────────────────────────────

    def _save_sigma_iteration_plot(self, sigma_folder: Path,
                                    filename: str, results: dict):
        """Save a clean matplotlib plot of σ per iteration with median line."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np

            sigma_raw = results.get("sigma_raw")
            if sigma_raw is None:
                return
            sigma_raw = np.asarray(sigma_raw)
            iterations = np.arange(1, len(sigma_raw) + 1)
            valid_mask = sigma_raw > 0
            median_sigma = float(np.median(sigma_raw[valid_mask])) if valid_mask.any() else 0.0

            fig, ax = plt.subplots(figsize=(12, 7))
            ax.scatter(iterations, sigma_raw, s=100, c="#5B9BD5", zorder=5,
                       edgecolors="white", linewidths=1.2, label="σ per iteration")

            # Annotate each point with its value
            for i, s in zip(iterations, sigma_raw):
                if s > 0:
                    ax.annotate(f"{s:.2e}", (i, s), textcoords="offset points",
                                xytext=(8, 10), fontsize=9, color="#5B9BD5",
                                fontweight="bold")

            # Median reference line
            if median_sigma > 0:
                ax.axhline(median_sigma, color="#F0A500", linestyle="--",
                           linewidth=1.5,
                           label=f"Median σ = {median_sigma:.4e} S/cm")

            ax.set_xlabel("Iteration", fontsize=12, fontweight="bold")
            ax.set_ylabel("σ (S/cm)", fontsize=12, fontweight="bold")
            ax.set_title(f"{filename} — Conductivity per Iteration",
                         fontsize=14, fontweight="bold")
            ax.set_xticks(iterations)
            ax.legend(fontsize=11, loc="best")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()

            plots_dir = sigma_folder
            plots_dir.mkdir(parents=True, exist_ok=True)
            fig.savefig(plots_dir / f"{filename}_sigma_iterations.png",
                        dpi=200, bbox_inches="tight")
            plt.close(fig)
            self._log("Saved sigma iteration plot")
        except Exception as exc:
            self._log(f"Warning: could not save sigma iteration plot: {exc}")

    # ── Seebeck V₁ vs V₂ fit plot saving ─────────────────────────────────

    def _save_seebeck_fit_plot(self, seebeck_folder: Path,
                                filename: str, results: dict):
        """Save V1 vs V2 scatter + fit line via matplotlib."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np

            data_avg = results.get("data_avg")
            if data_avg is None or len(data_avg) == 0:
                return

            V1 = data_avg[:, 3]   # µV
            V2 = data_avg[:, 4]   # µV
            slope = results.get("slope", 0)
            intercept = results.get("offset", 0)
            adj_r2 = results.get("adj_r_square", 0)
            seebeck = results.get("Seebeck", 0)

            fig, ax = plt.subplots(figsize=(10, 7))
            ax.scatter(V1, V2, s=30, c="#5B9BD5", alpha=0.7, label="Data",
                       edgecolors="white", linewidths=0.5)
            # Fit line
            v1_sorted = np.sort(V1)
            fit_y = slope * v1_sorted + intercept
            ax.plot(v1_sorted, fit_y, "r-", linewidth=2, label="Fit")

            ax.set_xlabel("V₁ (µV)", fontsize=12, fontweight="bold")
            ax.set_ylabel("V₂ (µV)", fontsize=12, fontweight="bold")
            ax.set_title(f"{filename} — V₁ vs V₂ (Seebeck Fit)",
                         fontsize=14, fontweight="bold")
            ax.legend(fontsize=11, loc="best")
            ax.grid(True, alpha=0.3)

            # Fit annotation box
            fit_text = (f"S = {seebeck:.3f} µV/K\n"
                        f"adj R² = {adj_r2:.5f}\n"
                        f"slope = {slope:.5f}")
            ax.text(0.05, 0.95, fit_text, transform=ax.transAxes,
                    fontsize=10, verticalalignment="top",
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="#333333",
                              edgecolor="#666666", alpha=0.8),
                    color="white")

            fig.tight_layout()
            plots_dir = seebeck_folder / "plots"
            plots_dir.mkdir(parents=True, exist_ok=True)
            fig.savefig(plots_dir / f"{filename}_V1_vs_V2.png",
                        dpi=200, bbox_inches="tight")
            plt.close(fig)
            self._log("Saved V₁ vs V₂ fit plot")
        except Exception as exc:
            self._log(f"Warning: could not save V₁ vs V₂ fit plot: {exc}")

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
            cycle_mode         : bool   (optional, default False)
            temperatures       : list[float]  (cycle mode — list of target temps)
            rate               : float  (cycle mode — ramp rate °C/min)
            stability_time     : float  (seconds — wait time per temp, default 1200)
            heating_only       : bool   (cycle mode — heat only or heat+cool)
        """
        # Dispatch to cycle mode if requested
        if config.get("cycle_mode", False):
            return self._run_cycle(config)

        self.reset_abort()
        do_sigma   = config["measure_sigma"]
        do_seebeck = config["measure_seebeck"]

        global_logger: Optional[logging.Logger] = None
        temp_logger:   Optional[logging.Logger] = None

        _real_sleep = self._install_abortable_sleep()

        # Timing bookkeeping
        _t_run_start = time.time()
        _sigma_elapsed = 0.0
        _seebeck_elapsed = 0.0
        _current_temp = 0.0
        _data_path = ""

        try:
            # ── Read current temperature ──────────────────────────────────
            self._log("Reading current temperature …")
            self.status_message.emit("Reading temperature …")
            sources = [("DAQ thermocouple", read_current_temperature)]
            furnace = self._connected_furnace()
            if furnace is not None:
                sources.append(("Eurotherm", furnace.read_temperature))
            _current_temp, source = self._read_actual_temperature(sources)
            if _current_temp is None:
                _current_temp = 0.0   # keeps the summary dialog from showing one
                raise RuntimeError(
                    "Could not read the temperature from the DAQ thermocouple "
                    "or the Eurotherm — measurement NOT started (no data "
                    "would be recorded under a made-up temperature). Check "
                    "the instruments and try again."
                )
            self._log(f"Current temperature: {_current_temp:.1f} °C  (from {source})")

            # Guard against invalid temperature for folder name
            if _current_temp <= 0:
                self._log("⚠ Temperature ≤ 0 — using 'experiment_data' as folder name")

            self._check_abort("temperature read")

            # ── Create folder structure ───────────────────────────────────
            (global_logger, temp_folder, temp_logger,
             sigma_folder, seebeck_folder) = self._prepare_folders(
                config, _current_temp, do_sigma, do_seebeck)
            _data_path = str(temp_folder)

            # ── Run measurements ─────────────────────────────────────────
            sigma_results = None
            if do_sigma:
                _t0 = time.time()
                sigma_results = self._run_sigma(
                    config, _current_temp, sigma_folder,
                    temp_logger, global_logger)
                _sigma_elapsed = time.time() - _t0
                # Save sigma iteration plot (matplotlib)
                if sigma_results:
                    fname = f"{config['sample_name']}_{_current_temp:.1f}C"
                    self._save_sigma_iteration_plot(
                        sigma_folder, fname, sigma_results)
                self._check_abort("post-sigma")
                self._log("Holding 10s after \u03c3 measurement ...")
                self.status_message.emit("Holding 10s ...")
                self._interruptible_sleep(10.0, "post-sigma hold")

            if do_sigma and do_seebeck:
                self._check_abort("between measurements")

            seebeck_results = None
            if do_seebeck:
                _t0 = time.time()
                seebeck_results = self._run_seebeck(
                    config, _current_temp, seebeck_folder,
                    temp_logger, global_logger)
                _seebeck_elapsed = time.time() - _t0
                self._check_abort("post-seebeck")
                self._log("Holding 10s after Seebeck measurement ...")
                self.status_message.emit("Holding 10s ...")
                self._interruptible_sleep(10.0, "post-seebeck hold")

                # Save all 3 Seebeck plots (time-series + fit)
                if seebeck_results:
                    fname = f"{config['sample_name']}_{_current_temp:.1f}C"
                    self._save_seebeck_time_series_plots(
                        seebeck_folder, fname, seebeck_results)
                    self._save_seebeck_fit_plot(
                        seebeck_folder, fname, seebeck_results)

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

            self.phase_changed.emit("idle")
            _total = time.time() - _t_run_start
            metadata = {
                "temperature": _current_temp,
                "data_path": _data_path,
                "sigma_elapsed": _sigma_elapsed,
                "seebeck_elapsed": _seebeck_elapsed,
                "total_elapsed": _total,
            }
            self.measurement_finished.emit(True, summary, metadata)

        except MeasurementAborted:
            self._log("Measurement ABORTED by user")
            self.status_message.emit("Measurement aborted")
            self._finalize_loggers(global_logger, temp_logger, "User aborted")
            self._set_instruments("idle")
            self.phase_changed.emit("idle")
            self.measurement_finished.emit(False, "Aborted by user", {
                "temperature": _current_temp,
                "data_path": _data_path,
                "total_elapsed": time.time() - _t_run_start,
            })

        except Exception as exc:
            self._log(f"FATAL: {exc}")
            self.status_message.emit(f"Error: {exc}")
            self._finalize_loggers(global_logger, temp_logger, str(exc))
            self._set_instruments("idle")
            self.phase_changed.emit("idle")
            self.measurement_finished.emit(False, str(exc), {
                "temperature": _current_temp,
                "data_path": _data_path,
                "total_elapsed": time.time() - _t_run_start,
            })

        finally:
            time.sleep = _real_sleep

    # ── cycle measurement mode ───────────────────────────────────────────

    def _acquire_furnace(self, ramp_rate: float):
        """Return the shared furnace controller, ready for the cycle, or None.

        The cycle never opens its own serial connection: the GUI's
        ``EurothermService`` already holds the COM port (Windows allows one
        handle per port), so a second open fails with "Access is denied".
        We borrow that service's controller instead — its transactions are
        lock-serialised against the live-display polling.  If the furnace
        isn't connected yet (e.g. it was off at start-up) the service is
        asked to connect first.
        """
        if self._furnace is None:
            self._log("⚠ No Eurotherm service available — proceeding without temp control")
            return None
        try:
            if not self._furnace.connect_blocking():
                self._log("⚠ Could not connect to Eurotherm — proceeding without temp control")
                return None
            controller = self._furnace.controller
            try:
                controller.set_auto_mode()
            except Exception as exc:
                # Non-fatal: the furnace is normally already in Auto mode.
                self._log(f"⚠ Could not set Eurotherm to Auto mode: {exc}")
            controller.set_ramp_rate(ramp_rate)
            self._log("Eurotherm connected ✓ (shared with live display)")
            return controller
        except Exception as exc:
            self._log(f"⚠ Eurotherm connection error: {exc} — proceeding without")
            return None

    def _run_cycle(self, config: dict):
        """Run measurements across multiple temperatures.

        For each temperature point:
          1. Set Eurotherm setpoint
          2. Wait stability_time (default 20 min)
          3. Read actual temperature
          4. Create folder named after actual temperature
          5. Run σ and/or Seebeck measurements
        """
        self.reset_abort()
        _real_sleep = self._install_abortable_sleep()

        temperatures  = config.get("temperatures", [])
        ramp_rate     = config.get("rate", 10.0)
        stability_sec = config.get("stability_time", 1200.0)  # default 20 min
        do_sigma      = config["measure_sigma"]
        do_seebeck    = config["measure_seebeck"]
        sample_name   = config["sample_name"]

        global_logger: Optional[logging.Logger] = None
        _t_run_start = time.time()
        _data_path = ""

        eurotherm = None

        try:
            # ── Create sweep-level folder structure ───────────────────────
            sample_folder, global_logger = create_temp_sweep_structure(
                sample_name, config.get("base_dir")
            )
            self._make_logger(global_logger)
            _data_path = str(sample_folder)

            self._log(f"━━ Temperature Cycle: {len(temperatures)} points ━━")
            self._log(f"Points: {temperatures}")
            self._log(f"Ramp rate: {ramp_rate} °C/min  |  Stability wait: "
                      f"{stability_sec/60:g} min per point (none at the start point)")
            global_logger.info(f"Cycle: {temperatures}, rate={ramp_rate}, wait={stability_sec}s")

            # ── Borrow the shared Eurotherm connection ────────────────────
            eurotherm = self._acquire_furnace(ramp_rate)

            # ── Loop over temperature points ─────────────────────────────
            skipped_targets: list[float] = []   # temperature unreadable
            for idx, target_temp in enumerate(temperatures):
                self._check_abort("cycle loop")
                self.cycle_point_starting.emit(idx, target_temp)

                point_label = f"[{idx+1}/{len(temperatures)}]"
                self._log(f"\n{'━'*50}")
                self._log(f"{point_label} Target: {target_temp:.1f} °C")
                self._log(f"{'━'*50}")
                self.status_message.emit(
                    f"Cycle {point_label} — setting {target_temp:.1f} °C"
                )
                global_logger.info(f"{point_label} Target: {target_temp}°C")

                # 1. Set setpoint
                if eurotherm is not None:
                    try:
                        eurotherm.set_ramp_rate(ramp_rate)
                        eurotherm.set_temperature(target_temp)
                        self._log(f"Setpoint → {target_temp:.1f} °C  (ramp {ramp_rate} °C/min)")
                    except Exception as exc:
                        self._log(f"⚠ Failed to set temperature: {exc}")

                # 2. Wait.  The start point has no stabilisation hold — only
                #    the time to reach it; every later point waits
                #    stability_time after its set-point change.
                if idx == 0:
                    self._wait_for_start_temperature(
                        eurotherm, target_temp, ramp_rate, point_label)
                    remaining = 0.0
                else:
                    wait_min = stability_sec / 60.0
                    self._log(f"Waiting {wait_min:g} min for stabilisation …")
                    self.status_message.emit(
                        f"Cycle {point_label} — waiting {wait_min:g} min"
                    )
                    remaining = stability_sec

                # Countdown in 60-second chunks
                while remaining > 0:
                    self._check_abort("stability wait")
                    chunk = min(remaining, 60.0)
                    self._interruptible_sleep(chunk, "stability wait")
                    remaining -= chunk
                    mins_left = remaining / 60.0
                    if mins_left > 0:
                        # Read live temperature during wait if possible
                        live_t = "?"
                        if eurotherm is not None:
                            try:
                                t = eurotherm.read_temperature()
                                if t is not None:
                                    live_t = f"{t:.1f}"
                            except Exception:
                                pass
                        self._log(
                            f"  ⏳ {mins_left:g} min remaining  "
                            f"(current: {live_t} °C)"
                        )

                # 3. Read actual temperature — retry, but never substitute the
                #    target or any other made-up value.
                sources = []
                if eurotherm is not None:
                    sources.append(("Eurotherm", eurotherm.read_temperature))
                sources.append(("DAQ thermocouple", read_current_temperature))
                actual_temp, source = None, None
                for attempt in range(1, _TEMP_READ_ATTEMPTS + 1):
                    actual_temp, source = self._read_actual_temperature(sources)
                    if actual_temp is not None:
                        break
                    if attempt < _TEMP_READ_ATTEMPTS:
                        self._log(f"  Temperature unreadable — retrying in "
                                  f"{_TEMP_RETRY_DELAY_S:.0f} s "
                                  f"({attempt}/{_TEMP_READ_ATTEMPTS}) …")
                        self._interruptible_sleep(_TEMP_RETRY_DELAY_S,
                                                  "temperature retry")

                if actual_temp is None:
                    msg = (f"{point_label} ✗ SKIPPED — could not read the actual "
                           f"temperature (target {target_temp:.1f} °C); nothing "
                           f"measured or saved for this point")
                    global_logger.error(msg)   # also reaches the GUI log
                    skipped_targets.append(target_temp)
                    continue

                self._log(f"Actual temperature: {actual_temp:.1f} °C  "
                          f"(from {source}; target was {target_temp:.1f} °C)")
                global_logger.info(f"Actual temp: {actual_temp}°C")

                # 4. Create temperature folder with ACTUAL temperature
                if actual_temp > 0:
                    meas_types = []
                    if do_sigma:
                        meas_types.append("Sigma")
                    if do_seebeck:
                        meas_types.append("Seebeck")
                    temp_folder, temp_logger = create_temperature_folder(
                        sample_folder, actual_temp, meas_types
                    )
                else:
                    # Fallback folder name
                    self._log("⚠ Temperature ≤ 0 — using 'experiment_data' folder")
                    temp_folder = sample_folder / "experiment_data"
                    temp_folder.mkdir(parents=True, exist_ok=True)
                    from output_manager import setup_temperature_logger
                    temp_logger = setup_temperature_logger(temp_folder, actual_temp)
                    if do_sigma:
                        (temp_folder / "Sigma").mkdir(exist_ok=True)
                    if do_seebeck:
                        (temp_folder / "Seebeck").mkdir(exist_ok=True)

                self._make_logger(temp_logger)

                sigma_folder   = temp_folder / "Sigma"
                seebeck_folder = temp_folder / "Seebeck"

                # 5. Run measurements
                sigma_results = None
                if do_sigma:
                    self.graph_seebeck_clear_requested = True
                    sigma_results = self._run_sigma(
                        config, actual_temp, sigma_folder,
                        temp_logger, global_logger)
                    # Save sigma iteration plot (matplotlib)
                    if sigma_results:
                        fname = f"{sample_name}_{actual_temp:.1f}C"
                        self._save_sigma_iteration_plot(
                            sigma_folder, fname, sigma_results)
                    self._check_abort("post-sigma")
                    self._log("Holding 10s after \u03c3 measurement ...")
                    self.status_message.emit("Holding 10s ...")
                    self._interruptible_sleep(10.0, "post-sigma hold")

                if do_sigma and do_seebeck:
                    self._check_abort("between measurements")

                seebeck_results = None
                if do_seebeck:
                    seebeck_results = self._run_seebeck(
                        config, actual_temp, seebeck_folder,
                        temp_logger, global_logger)
                    self._check_abort("post-seebeck")
                    self._log("Holding 10s after Seebeck measurement ...")
                    self.status_message.emit("Holding 10s ...")
                    self._interruptible_sleep(10.0, "post-seebeck hold")

                    # Save all 3 Seebeck plots (time-series + fit)
                    if seebeck_results:
                        fname = f"{sample_name}_{actual_temp:.1f}C"
                        self._save_seebeck_time_series_plots(
                            seebeck_folder, fname, seebeck_results)
                        self._save_seebeck_fit_plot(
                            seebeck_folder, fname, seebeck_results)

                # Log point summary
                parts = []
                if sigma_results:
                    parts.append(f"σ={sigma_results['corr_sigma']:.2e}")
                if seebeck_results:
                    parts.append(f"S={seebeck_results['Seebeck']:.2f} µV/K")
                point_summary = ", ".join(parts) if parts else "no results"
                self._log(f"{point_label} Done: {point_summary}")
                global_logger.info(f"{point_label} Done: {point_summary}")

                self.cycle_point_completed.emit(actual_temp, sigma_results, seebeck_results, str(temp_folder))

                finalize_logging(temp_logger, success=True)

            # ── Cool down ─────────────────────────────────────────────────
            self._cool_down_furnace(eurotherm, _real_sleep)

            # ── Final summary ─────────────────────────────────────────────
            total = time.time() - _t_run_start
            n_measured = len(temperatures) - len(skipped_targets)
            summary = (
                f"Cycle complete — {n_measured} of {len(temperatures)} "
                f"temperature points in {total/60:.1f} min"
            )
            if skipped_targets:
                summary += (
                    f"\n⚠ {len(skipped_targets)} point(s) SKIPPED — temperature "
                    f"unreadable at target(s): "
                    + ", ".join(f"{t:.1f} °C" for t in skipped_targets)
                )
            # A cycle where every point was skipped recorded nothing.
            ok = n_measured > 0 or not temperatures
            self._log(summary)
            self.status_message.emit(summary.splitlines()[0])
            finalize_logging(global_logger, success=ok)
            self.phase_changed.emit("idle")
            self.measurement_finished.emit(ok, summary, {
                "data_path": _data_path,
                "total_elapsed": total,
                "n_points": n_measured,
                "skipped_targets": skipped_targets,
            })

        except MeasurementAborted:
            self._log("Cycle ABORTED by user")
            self._cool_down_furnace(eurotherm, _real_sleep)
            self.status_message.emit("Cycle aborted")
            if global_logger:
                finalize_logging(global_logger, success=False, error_msg="User aborted")
            self._set_instruments("idle")
            self.phase_changed.emit("idle")
            self.measurement_finished.emit(False, "Cycle aborted by user", {
                "data_path": _data_path,
                "total_elapsed": time.time() - _t_run_start,
            })

        except Exception as exc:
            self._log(f"FATAL: {exc}")
            self._cool_down_furnace(eurotherm, _real_sleep)
            self.status_message.emit(f"Error: {exc}")
            if global_logger:
                finalize_logging(global_logger, success=False, error_msg=str(exc))
            self._set_instruments("idle")
            self.phase_changed.emit("idle")
            self.measurement_finished.emit(False, str(exc), {
                "data_path": _data_path,
                "total_elapsed": time.time() - _t_run_start,
            })

        finally:
            time.sleep = _real_sleep
            # The Eurotherm connection is shared with the live display and
            # owned by EurothermService — deliberately left open.

    def _cool_down_furnace(self, eurotherm, real_sleep):
        """Set the furnace back to a safe set-point when a cycle ends.

        Runs on every exit — completed, aborted or failed — so the furnace is
        never left at a high set-point unattended.  The real ``time.sleep`` is
        restored first: after an abort the patched one raises, which would
        break the MODBUS write's inter-frame delay.
        """
        if eurotherm is None:
            return
        time.sleep = real_sleep
        try:
            # Local controller returns False on failure; remote one raises.
            if eurotherm.set_temperature(_COOL_DOWN_TEMP_C) is False:
                raise RuntimeError("controller did not accept the set-point")
            self._log(f"Cool-down: setpoint → {_COOL_DOWN_TEMP_C:.0f} °C")
        except Exception as exc:
            self._log(f"⚠ Could not set cool-down setpoint ({exc}) — "
                      "SET THE FURNACE MANUALLY")

    # ── temperature reading ──────────────────────────────────────────────

    def _connected_furnace(self):
        """The shared furnace controller if it is already connected, else None.

        Never opens a connection (that can mean a slow COM-port scan); it
        only borrows the one the live display already holds.
        """
        if self._furnace is None:
            return None
        try:
            controller = self._furnace.controller
            return controller if controller.is_connected() else None
        except Exception:
            return None

    def _read_actual_temperature(self, sources):
        """Read the temperature from the first source that gives a real value.

        Args:
            sources: ordered ``[(name, read_fn), ...]``.

        Returns:
            ``(temp_c, source_name)`` rounded to 0.1 °C, or ``(None, None)``
            if every source failed.  Failed, missing or implausible readings
            are logged and skipped — a substitute value is never returned.
        """
        for name, read in sources:
            try:
                t = read()
            except MeasurementAborted:
                raise
            except Exception as exc:
                self._log(f"  {name}: read failed ({exc})")
                continue
            if is_valid_temperature(t):
                return round(float(t), 1), name
            self._log(f"  {name}: no valid reading ({t!r})")
        return None, None

    def _wait_for_start_temperature(self, eurotherm, target: float,
                                    ramp_rate: float, point_label: str):
        """Wait until the furnace reaches the cycle's start temperature.

        The start point gets no stabilisation hold: it is measured as soon as
        the furnace is within ``_START_REACH_TOLERANCE_C`` of the set-point
        (immediately, if it is already there).  If that takes longer than the
        expected ramp time plus ``_START_REACH_MARGIN_S``, it measures anyway
        — the recorded temperature is always the actual reading, so nothing
        is mislabelled.
        """
        tol = _START_REACH_TOLERANCE_C
        if eurotherm is None:
            self._log("⚠ No furnace connection — cannot confirm the start "
                      "temperature; measuring now")
            return

        def read():
            try:
                t = eurotherm.read_temperature()
            except MeasurementAborted:
                raise
            except Exception:
                return None
            return float(t) if is_valid_temperature(t) else None

        t = read()
        distance = abs(target - t) if t is not None else 0.0
        timeout = distance / max(ramp_rate, 0.1) * 60.0 + _START_REACH_MARGIN_S
        self._log(f"Start point — no stabilisation wait; waiting to reach "
                  f"{target:.1f} °C (±{tol:g} °C) …")
        self.status_message.emit(
            f"Cycle {point_label} — reaching start temperature {target:.1f} °C"
        )

        waited, next_log = 0.0, 60.0
        while t is None or abs(t - target) > tol:
            if waited >= timeout:
                now = f"{t:.1f} °C" if t is not None else "unreadable"
                self._log(f"⚠ Start temperature not reached after "
                          f"{waited/60:.0f} min (current: {now}) — measuring "
                          f"anyway at the actual temperature")
                return
            self._interruptible_sleep(_START_POLL_S, "reaching start temperature")
            waited += _START_POLL_S
            t = read()
            if waited >= next_log:
                now = f"{t:.1f}" if t is not None else "?"
                self._log(f"  ⏳ reaching {target:.1f} °C — current: {now} °C")
                next_log += 60.0
        self._log(f"  Start temperature reached: {t:.1f} °C ✓")

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
    sigma_data_point     = Signal(dict)
    seebeck_fit_ready    = Signal(dict)
    phase_changed        = Signal(str)
    measurement_finished = Signal(bool, str, dict)
    
    # Cycle mode hooks
    cycle_point_starting = Signal(int, float)             # (index, target_temp)
    cycle_point_completed = Signal(float, object, object, str) # (actual_temp, sigma_res, seebeck_res, folder_path)

    # Private signal to invoke the worker's ``run`` slot across threads.
    _request_run = Signal(dict)

    def __init__(self, parent: QObject = None, furnace=None):
        """
        Args:
            furnace: The app's ``EurothermService``.  Temperature cycles use
                its (single, shared) furnace connection.  Without it, cycles
                run with no temperature control.
        """
        super().__init__(parent)
        self._thread = QThread()
        self._worker = _MeasurementWorker(furnace)
        self._worker.moveToThread(self._thread)

        # Forward worker signals → own signals.
        self._worker.log_message.connect(self.log_message)
        self._worker.status_message.connect(self.status_message)
        self._worker.instrument_status.connect(self.instrument_status)
        self._worker.sigma_completed.connect(self.sigma_completed)
        self._worker.seebeck_completed.connect(self.seebeck_completed)
        self._worker.seebeck_data_point.connect(self.seebeck_data_point)
        self._worker.sigma_data_point.connect(self.sigma_data_point)
        self._worker.seebeck_fit_ready.connect(self.seebeck_fit_ready)
        self._worker.phase_changed.connect(self.phase_changed)
        self._worker.measurement_finished.connect(self.measurement_finished)
        self._worker.cycle_point_starting.connect(self.cycle_point_starting)
        self._worker.cycle_point_completed.connect(self.cycle_point_completed)

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
