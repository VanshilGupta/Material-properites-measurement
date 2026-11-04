"""
Simulation Module for Sigma and Seebeck Measurements

Generates data with the same keys, units, and files as a real run, without
contacting the furnace, power supply, or multimeter.

Sigma voltages are a noisy Van der Pauw measurement of a temperature-dependent
conductivity, solved with the same equation the instrument code uses.
Seebeck time series follow the real heater phases; V1 and V2 (volts) are built
so the thermocouple-corrected fit recovers the model Seebeck coefficient.
Saved CSVs use the real layouts (sigma iterations, ``*_all.csv``,
``*_averaged.csv``).
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional, Tuple

import numpy as np
from scipy.optimize import brentq

from constants import MEASUREMENT_CURRENT
from seebeck_measurement.curve_fitting import (
    calculate_thermocouple_seebeck,
    fit_v1_v2_and_calculate_seebeck,
)
from seebeck_measurement.data_processing import save_to_csv


# Simulation parameters (realistic ranges)
SIM_PARAMS = {
    # Sigma simulation — about 100 S/cm at 25 °C, rising gently with temperature
    'sigma_base': 1e2,          # S/cm
    'sigma_noise': 0.02,        # fractional noise on each iteration
    'sigma_temp_coeff': 0.004,  # per °C

    # Seebeck simulation — n-type, µV/K
    'seebeck_base': -150.0,
    'seebeck_noise_v': 0.4e-6,  # volts, on V1 and V2
    'seebeck_temp_coeff': 0.001,

    # Temperature simulation
    'room_temp': 25.0,
    'temp_noise': 0.15,         # °C, sample-temperature scatter
}

# Wall-clock pauses so a GUI can paint live points. Real durations are
# written into the data; these only pace the simulation.
_SIGMA_PAUSE_S = 0.08
_SEEBECK_PAUSE_S = 0.015
_RAMP_PAUSE_S = 0.4


def nominal_sigma(temperature: float) -> float:
    """Conductivity (S/cm) the sigma simulator is built around."""
    factor = 1.0 + SIM_PARAMS['sigma_temp_coeff'] * (temperature - 25.0)
    return SIM_PARAMS['sigma_base'] * max(factor, 0.2)


def nominal_seebeck(temperature: float) -> float:
    """Seebeck coefficient (µV/K) the seebeck simulator is built around."""
    factor = 1.0 + SIM_PARAMS['seebeck_temp_coeff'] * (temperature - 25.0)
    return SIM_PARAMS['seebeck_base'] * factor


def _rng(seed: Optional[int]) -> np.random.Generator:
    return np.random.default_rng(seed)


def _geometry_error(diameter_mm: float) -> float:
    """Same geometry correction ``measure_sigma`` applies."""
    d1 = (diameter_mm - 9.0) / 2.0
    return 4.0 * ((d1 ** 2) / (2.0 * diameter_mm ** 2 * np.log(2.0)))


def solve_vdp_sigma(r1: float, r2: float, thickness_mm: float) -> float:
    """Conductivity (S/cm) from the Van der Pauw equation, or 0 if unsolvable.

    ``r1`` and ``r2`` are ohms, ``thickness_mm`` is millimetres.  This is the
    same transcendental equation ``measure_sigma`` solves with Brent's method.
    """
    d_cm = thickness_mm / 10.0
    if d_cm <= 0 or r1 <= 0 or r2 <= 0:
        return 0.0

    def vdp_equation(rho: float) -> float:
        return (np.exp(-np.pi * r1 * d_cm / rho)
                + np.exp(-np.pi * r2 * d_cm / rho)) - 1.0

    rho_guess = np.pi * 0.5 * (r1 + r2) * d_cm / np.log(2.0)
    bracket = None
    for scale in (10, 100, 1000, 10000):
        a, b = rho_guess / scale, rho_guess * scale
        if vdp_equation(a) * vdp_equation(b) < 0:
            bracket = (a, b)
            break
    if bracket is None:
        a, b = 1e-8, 1e3
        if vdp_equation(a) * vdp_equation(b) >= 0:
            return 0.0
        bracket = (a, b)
    try:
        rho = brentq(vdp_equation, bracket[0], bracket[1], xtol=1e-12, rtol=1e-10)
    except ValueError:
        return 0.0
    if rho <= 0:
        return 0.0
    return float(1.0 / rho)


def _vdp_slope(sample_seebeck_uV_K: float, temperature: float) -> float:
    """V2-vs-V1 slope that the real fit turns back into ``sample_seebeck_uV_K``.

    The instrument fit is::

        S = S_TC / (1 - slope) + S_Alumel
    """
    s_chromel, s_alumel = calculate_thermocouple_seebeck(temperature)
    s_tc = s_chromel - s_alumel
    return 1.0 - s_tc / (sample_seebeck_uV_K - s_alumel)


def simulate_temperature_reading(base: Optional[float] = None,
                                 seed: Optional[int] = None) -> float:
    """Simulate one sample-thermocouple reading (°C)."""
    rng = _rng(seed)
    center = SIM_PARAMS['room_temp'] if base is None else float(base)
    return float(center + rng.normal(0, SIM_PARAMS['temp_noise']))


def simulate_sigma_measurement(
    sample_t: float,
    sample_dia: float,
    temperature: float = 25.0,
    verbose: bool = True,
    logger: Optional[logging.Logger] = None,
    progress_callback: Optional[Callable[[dict], None]] = None,
    seed: Optional[int] = None,
) -> Dict:
    """Simulate a sigma measurement and return the real result schema.

    The dict matches ``measure_sigma_with_sample_temperature``: per-iteration
    V1–V4, resistances, solved conductivity, sample-temperature readings, and
    the geometry-corrected median.  ``progress_callback`` is invoked once per
    iteration with the same keys the GUI graphs consume.
    """
    rng = _rng(seed)
    if verbose:
        print("\n[SIMULATION MODE] Sigma Measurement")
        print(f"Sample: {sample_t} mm thick, {sample_dia} mm diameter")
    if logger:
        logger.info("[SIMULATION] Starting simulated sigma measurement")

    current = float(MEASUREMENT_CURRENT)
    # Resistances that a uniform sample of ``nominal_sigma`` would show,
    # with a little iteration-to-iteration scatter and a slight R1/R2 mismatch.
    d_cm = sample_t / 10.0
    readings = [round(simulate_temperature_reading(temperature, seed=None if seed is None else seed + 1), 2)]

    sigma_raw = np.zeros(5)
    iteration_results = []

    for j in range(5):
        self_check = nominal_sigma(temperature)
        noisy = self_check * float(rng.normal(1.0, SIM_PARAMS['sigma_noise']))
        noisy = max(noisy, 1e-3)
        rho = 1.0 / noisy
        r_match = rho * np.log(2.0) / (np.pi * d_cm)
        r1 = r_match * float(rng.normal(1.0, 0.005))
        r2 = r_match * float(rng.normal(1.0, 0.005))
        r1 = max(r1, 1e-9)
        r2 = max(r2, 1e-9)

        # abs(v1 - v2) / 2 = R * I, same definition as measure_sigma.
        half_1 = r1 * current
        half_2 = r2 * current
        volt1, volt2 = half_1, -half_1
        volt3, volt4 = half_2, -half_2
        delta_v1 = abs(volt1 - volt2) / 2.0
        delta_v2 = abs(volt3 - volt4) / 2.0

        sigma_value = solve_vdp_sigma(r1, r2, sample_t)
        sigma_raw[j] = sigma_value
        sample_temp = round(
            float(temperature + rng.normal(0, SIM_PARAMS['temp_noise'])), 1
        )
        readings.append(sample_temp)

        iter_data = {
            'iteration': j + 1,
            'v1': float(volt1), 'v2': float(volt2),
            'v3': float(volt3), 'v4': float(volt4),
            'delta_v1': float(delta_v1), 'delta_v2': float(delta_v2),
            'R1': float(r1), 'R2': float(r2),
            'sigma': float(sigma_value),
            'temperature': sample_temp,
        }
        iteration_results.append(iter_data)
        if logger:
            logger.info(
                f"Iteration {j + 1}/5: V1={volt1:.6f} V, V2={volt2:.6f} V, "
                f"V3={volt3:.6f} V, V4={volt4:.6f} V"
            )
            logger.info(f"  R1={r1:.6f} Ω, R2={r2:.6f} Ω → σ={sigma_value:.2f} S/cm")
        if progress_callback:
            progress_callback(iter_data)
        time.sleep(_SIGMA_PAUSE_S)

    valid = sigma_raw[sigma_raw > 0]
    if len(valid) == 0:
        if logger:
            logger.error("[SIMULATION] No valid sigma iterations")
        return None

    uncorr = float(np.median(valid))
    error = _geometry_error(sample_dia)
    corr = uncorr * (1.0 - error)
    mean_temp = round(float(sum(readings) / len(readings)), 2)

    results = {
        'corr_sigma': float(corr),
        'uncorr_sigma': uncorr,
        'sigma_raw': sigma_raw,
        'std_dev': float(np.std(sigma_raw)),
        'current': current,
        'sample_thickness': float(sample_t),
        'sample_diameter': float(sample_dia),
        'valid_count': int(len(valid)),
        'iterations': iteration_results,
        'temperature': mean_temp,
        'temperature_readings': readings,
        'simulated': True,
    }

    if verbose:
        print(f"  [SIM] Electrical Conductivity: {corr:.2e} S/cm")
        print(f"  [SIM] Sample temperature: {mean_temp:.2f} °C")
    if logger:
        logger.info(f"[SIMULATION] Sigma: {corr:.2e} S/cm at {mean_temp:.2f} °C")
    return results


def _heater_delta(t: float, measurement_time: float, amplitude: float = 4.5) -> float:
    """T1 − T2 (°C) for one timestamp, following the real heater phases.

    Side 1 is heated at the start, side 2 after the halfway point, each for
    up to 60 s (shorter when the run itself is short).  The difference swings
    positive, decays, then swings negative — the shape a real Seebeck trace has.
    """
    half = max(measurement_time / 2.0, 1.0)
    on = min(60.0, half * 0.35)
    tau_rise = max(on / 3.0, 1.0)
    tau_decay = max(half / 4.0, 1.0)

    def pulse(t0: float) -> float:
        t1 = t0 + on
        if t < t0:
            return 0.0
        if t < t1:
            return amplitude * (1.0 - np.exp(-(t - t0) / tau_rise))
        peak = amplitude * (1.0 - np.exp(-(t1 - t0) / tau_rise))
        return peak * np.exp(-(t - t1) / tau_decay)

    return pulse(0.0) - pulse(half)


def simulate_seebeck_measurement(
    filename: str,
    measurement_time: float,
    output_folder: str,
    temperature: float = 25.0,
    logger: Optional[logging.Logger] = None,
    plotter=None,
    enable_plotting: bool = False,
    seed: Optional[int] = None,
) -> Dict:
    """Simulate a Seebeck run and return the real result schema.

    ``data_avg`` columns are ``[t(s), T1(°C), T2(°C), V1(µV), V2(µV)]``,
    matching ``SeebeckMeasurement.process_and_save_data``.  ``V1`` and ``V2``
    passed to ``plotter.update`` are in volts, as the live GUI expects.
    CSVs are written with ``save_to_csv`` into ``<output_folder>/data``.
    """
    rng = _rng(seed)
    measurement_time = max(float(measurement_time), 2.0)
    if logger:
        logger.info("[SIMULATION] Starting simulated Seebeck measurement")

    n_points = int(np.clip(round(measurement_time / 2.0), 40, 200))
    time_data = np.linspace(0.0, measurement_time, n_points)

    target_s = nominal_seebeck(temperature)
    slope_true = _vdp_slope(target_s, temperature)
    offset_v = 2.0e-6  # volts

    T1 = np.empty(n_points)
    T2 = np.empty(n_points)
    V1 = np.empty(n_points)
    V2 = np.empty(n_points)
    # Forward/backward pairs for *_all.csv, mirroring the 7-reading scan.
    pairs = []

    for i, t in enumerate(time_data):
        delta = _heater_delta(float(t), measurement_time)
        common = float(rng.normal(0, 0.03))
        t1 = float(temperature + delta / 2.0 + common)
        t2 = float(temperature - delta / 2.0 + common)
        v1 = float(delta * 40e-6 + rng.normal(0, SIM_PARAMS['seebeck_noise_v']))
        v2 = float(slope_true * v1 + offset_v
                   + rng.normal(0, SIM_PARAMS['seebeck_noise_v']))
        T1[i], T2[i], V1[i], V2[i] = t1, t2, v1, v2

        # Tiny forward/backward differences, as the DAQ's two passes would show.
        def _pair(value, scale):
            a = value + float(rng.normal(0, scale))
            b = value + float(rng.normal(0, scale))
            return a, b

        t1a, t1b = _pair(t1, 0.01)
        t2a, t2b = _pair(t2, 0.01)
        v1a, v1b = _pair(v1, 0.2e-6)
        pairs.append((float(t), t1a, t1b, t2a, t2b, v1a, v1b, v2))

        if plotter is not None:
            plotter.update(float(t), t1, t2, v1, v2)
        time.sleep(_SEEBECK_PAUSE_S)

    T_avg = float(np.mean([np.mean(T1), np.mean(T2)]))
    data_avg = np.column_stack([
        time_data, T1, T2, V1 * 1e6, V2 * 1e6,
    ])

    _save_seebeck_csvs(filename, output_folder, pairs, data_avg)

    slope, adj_r2, offset, rmse, seebeck = fit_v1_v2_and_calculate_seebeck(
        V1, V2, T_avg,
        plot=enable_plotting, save_plot=enable_plotting,
        filename=filename, output_folder=output_folder,
    )

    results = {
        'T_avg': T_avg,
        'Seebeck': float(seebeck),
        'S_slope': float(seebeck),
        'slope': float(slope),
        'adj_r_square': float(adj_r2),
        'offset': float(offset),
        'rmse': float(rmse),
        'data_avg': data_avg,
        'n_points': n_points,
        'measurement_time': measurement_time,
        'simulated': True,
    }
    if logger:
        logger.info(f"[SIMULATION] Seebeck: {seebeck:.2f} µV/K")
        logger.info(f"[SIMULATION] R²: {adj_r2:.6f}  T_avg: {T_avg:.2f} °C")
    if enable_plotting:
        print(f"  [SIM] Seebeck Coefficient: {seebeck:.2f} µV/K")
        print(f"  [SIM] Average Temperature: {T_avg:.2f} °C")
        print(f"  [SIM] Fit Quality (R²): {adj_r2:.6f}")
    return results


def _save_seebeck_csvs(filename, output_folder, pairs, data_avg) -> None:
    """Write the same two CSVs a real Seebeck run writes."""
    all_rows = []
    for t, t1a, t1b, t2a, t2b, v1a, v1b, v2 in pairs:
        all_rows.append([
            t - 0.06, t1a, np.nan,
            t - 0.04, v1a * 1e6, np.nan,
            t - 0.02, t2a, np.nan,
            t, v2 * 1e6, np.nan,
            t + 0.02, t2b, np.nan,
            t + 0.04, v1b * 1e6, np.nan,
            t + 0.06, t1b,
        ])
    headers_all = [
        't_T1_1(s)', 'T1_1(°C)', '',
        't_V1_1(s)', 'V1_1(µV)', '',
        't_T2_1(s)', 'T2_1(°C)', '',
        't_V2(s)', 'V2(µV)', '',
        't_T2_2(s)', 'T2_2(°C)', '',
        't_V1_2(s)', 'V1_2(µV)', '',
        't_T1_2(s)', 'T1_2(°C)',
    ]
    save_to_csv(f'{filename}_all.csv', np.array(all_rows), headers_all, output_folder)
    headers_avg = ['t(s)', 'T1_avg(°C)', 'T2_avg(°C)', 'V1_avg(µV)', 'V2(µV)']
    save_to_csv(f'{filename}_averaged.csv', data_avg, headers_avg, output_folder)


def simulate_eurotherm_ramp(
    start_temp: float,
    target_temp: float,
    ramp_rate: float,
    stability_time: float = 30.0,
) -> Tuple[float, bool]:
    """Simulate a furnace ramp. Returns ``(actual_temperature_C, is_stable)``.

    Wall-clock time is a fraction of a second. The reading sits within a few
    tenths of a degree of the target, as a stabilised furnace would.
    """
    temp_diff = abs(target_temp - start_temp)
    ramp_minutes = temp_diff / max(ramp_rate, 0.1)
    print(
        f"\n[SIMULATION] Ramping {start_temp:.1f}°C → {target_temp:.1f}°C "
        f"at {ramp_rate}°C/min ({ramp_minutes:.1f} min on real hardware)"
    )
    steps = 4
    sim_time = 0.0 if temp_diff < 0.05 else _RAMP_PAUSE_S
    for i in range(steps):
        current = start_temp + (target_temp - start_temp) * (i + 1) / steps
        print(f"\r  [SIM] Temperature: {current:.1f}°C", end="", flush=True)
        if sim_time:
            time.sleep(sim_time / steps)
    actual = float(target_temp + np.random.normal(0, 0.2))
    print(f"\r  [SIM] Temperature: {actual:.1f}°C - STABLE")
    return actual, True


class SimulatedSeebeckMeasurement:
    """Drop-in stand-in for ``SeebeckMeasurement`` that never opens instruments.

    Assign ``plotter`` (anything with ``update(t, t1, t2, v1, v2)``) before
    ``run_measurement`` to stream live points. Voltages on that callback are
    in volts.
    """

    def __init__(self, enable_plotting: bool = True):
        self.enable_plotting = enable_plotting
        self.plotter = None

    def run_measurement(
        self,
        filename: str,
        measurement_time: float,
        output_folder: str,
        logger: Optional[logging.Logger] = None,
        temperature: Optional[float] = None,
    ) -> Dict:
        """Run a simulated measurement at ``temperature`` (°C).

        When ``temperature`` is omitted a room-temperature reading is used.
        Pass the furnace temperature for a sweep so the saved trace matches
        the folder it is written into.
        """
        if temperature is None:
            temperature = simulate_temperature_reading()
        return simulate_seebeck_measurement(
            filename=filename,
            measurement_time=measurement_time,
            output_folder=output_folder,
            temperature=temperature,
            logger=logger,
            plotter=self.plotter,
            enable_plotting=self.enable_plotting,
        )


# Global simulation mode flag (command-line scripts)
SIMULATION_MODE = False


def set_simulation_mode(enabled: bool):
    """Enable or disable global simulation mode."""
    global SIMULATION_MODE
    SIMULATION_MODE = enabled
    if enabled:
        print("\n" + "=" * 60)
        print("SIMULATION MODE ENABLED")
        print("All measurements will use simulated data.")
        print("=" * 60 + "\n")


def is_simulation_mode() -> bool:
    """Check if simulation mode is enabled."""
    return SIMULATION_MODE
