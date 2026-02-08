"""
Simulation Module for Sigma and Seebeck Measurements

Provides simulated data for testing plotting and data saving
without being connected to actual instruments.
"""

import numpy as np
import time
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import matplotlib.pyplot as plt


# Simulation parameters (realistic ranges)
SIM_PARAMS = {
    # Sigma simulation
    'sigma_base': 1e2,  # Base conductivity in S/cm
    'sigma_noise': 0.05,  # 5% noise
    'sigma_temp_coeff': 0.02,  # Temperature coefficient
    
    # Seebeck simulation
    'seebeck_base': -150,  # Base Seebeck in µV/K (negative for n-type)
    'seebeck_noise': 0.03,  # 3% noise
    'seebeck_temp_coeff': 0.01,  # Temperature coefficient
    
    # Temperature simulation
    'room_temp': 25.0,
    'temp_noise': 0.5,  # ±0.5°C noise
}


def simulate_temperature_reading() -> float:
    """Simulate reading current temperature from DAQ."""
    base_temp = SIM_PARAMS['room_temp']
    noise = np.random.normal(0, SIM_PARAMS['temp_noise'])
    return base_temp + noise


def simulate_sigma_measurement(
    sample_t: float,
    sample_dia: float,
    temperature: float = 25.0,
    verbose: bool = True,
    logger: Optional[logging.Logger] = None
) -> Dict:
    """
    Simulate a sigma (electrical conductivity) measurement.
    
    Args:
        sample_t: Sample thickness in mm
        sample_dia: Sample diameter in mm
        temperature: Current temperature in °C
        verbose: Print progress
        logger: Optional logger
        
    Returns:
        Dictionary with simulated results
    """
    if verbose:
        print("\n[SIMULATION MODE] Sigma Measurement")
        print(f"Sample: {sample_t}mm thick, {sample_dia}mm diameter")
    
    if logger:
        logger.info("[SIMULATION] Starting simulated sigma measurement")
    
    # Calculate sample area
    area = np.pi * (sample_dia / 2) ** 2  # mm²
    area_cm2 = area / 100  # cm²
    thickness_cm = sample_t / 10  # cm
    
    # Simulate temperature-dependent conductivity
    temp_factor = 1 + SIM_PARAMS['sigma_temp_coeff'] * (temperature - 25)
    base_sigma = SIM_PARAMS['sigma_base'] * temp_factor
    
    # Simulate 5 measurement cycles with noise
    measurements = []
    resistances = []
    sigma_raw = np.zeros(5)  # Array to store raw sigma values
    currents = [0.001, 0.002, 0.005, 0.010, 0.020]  # Typical current values in A
    
    for i, current in enumerate(currents):
        if verbose:
            print(f"  Measurement {i+1}/5 at {current*1000:.1f} mA...")
        
        # Simulate resistance with noise
        base_resistance = thickness_cm / (base_sigma * area_cm2)
        noise = np.random.normal(1, SIM_PARAMS['sigma_noise'])
        resistance = base_resistance * noise
        
        # Calculate sigma for this measurement
        sigma_value = thickness_cm / (resistance * area_cm2)
        sigma_raw[i] = sigma_value
        
        resistances.append(resistance)
        measurements.append({
            'current': current,
            'voltage': current * resistance,
            'resistance': resistance,
            'sigma': sigma_value
        })
        
        time.sleep(0.2)  # Small delay for realism
    
    # Calculate results
    avg_resistance = np.mean(resistances)
    std_resistance = np.std(resistances)
    
    # Uncorrected sigma (median of raw values)
    uncorr_sigma = np.median(sigma_raw)
    std_dev = np.std(sigma_raw)
    
    # Apply geometric correction (simulated)
    D1 = sample_dia
    d1 = (D1 - 9.0) / 2.0
    error = 4 * ((d1**2) / (2 * D1**2 * np.log(2)))
    corr_sigma = uncorr_sigma * (1 - error)
    
    # Use median current value
    median_current = np.median(currents)
    
    results = {
        'corr_sigma': corr_sigma,
        'uncorr_sigma': uncorr_sigma,
        'sigma_raw': sigma_raw,
        'std_dev': std_dev,
        'current': median_current,
        'sample_thickness': sample_t,
        'sample_diameter': sample_dia,
        'valid_count': 5,
        'total_count': 5,
        'temperature': temperature,
        'avg_resistance': avg_resistance,
        'std_resistance': std_resistance,
        'measurements': measurements,
        'simulated': True
    }
    
    if verbose:
        print(f"\n  [SIM] Electrical Conductivity: {corr_sigma:.2e} S/cm")
        print(f"  [SIM] Average Resistance: {avg_resistance:.4f} Ω")
    
    if logger:
        logger.info(f"[SIMULATION] Sigma: {corr_sigma:.2e} S/cm")
    
    return results


def simulate_seebeck_measurement(
    filename: str,
    measurement_time: float,
    output_folder: str,
    temperature: float = 25.0,
    logger: Optional[logging.Logger] = None
) -> Dict:
    """
    Simulate a Seebeck coefficient measurement with realistic data and plots.
    
    Args:
        filename: Base filename for outputs
        measurement_time: Measurement duration in seconds
        output_folder: Folder to save outputs
        temperature: Current temperature in °C
        logger: Optional logger
        
    Returns:
        Dictionary with simulated results
    """
    print("\n[SIMULATION MODE] Seebeck Measurement")
    print(f"Measurement time: {measurement_time/60:.1f} minutes")
    
    if logger:
        logger.info("[SIMULATION] Starting simulated Seebeck measurement")
    
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Simulate temperature-dependent Seebeck
    temp_factor = 1 + SIM_PARAMS['seebeck_temp_coeff'] * (temperature - 25)
    true_seebeck = SIM_PARAMS['seebeck_base'] * temp_factor  # µV/K
    
    # Generate time series data
    n_points = min(int(measurement_time / 2), 500)  # Sample every 2 seconds, max 500 points
    time_data = np.linspace(0, measurement_time, n_points)
    
    # Simulate heater cycles (heating and cooling)
    n_cycles = 4
    cycle_period = measurement_time / n_cycles
    
    # Generate temperature difference data (oscillating)
    delta_T_amplitude = 5.0  # ±5°C temperature difference
    delta_T = delta_T_amplitude * np.sin(2 * np.pi * time_data / cycle_period)
    delta_T += np.random.normal(0, 0.3, n_points)  # Add noise
    
    # Generate voltage response (Seebeck effect)
    delta_V = true_seebeck * delta_T  # µV
    delta_V += np.random.normal(0, abs(true_seebeck) * 0.05, n_points)  # Add noise
    
    # Hot and cold side temperatures
    T_avg = temperature + np.random.normal(0, 1, n_points)
    T_hot = T_avg + delta_T / 2
    T_cold = T_avg - delta_T / 2
    
    # Simulate progress
    print("  Collecting data", end="", flush=True)
    for i in range(10):
        time.sleep(0.1)
        print(".", end="", flush=True)
    print(" Done!")
    
    # Fit linear regression: ΔV = S * ΔT
    # Use points where |ΔT| > 1 for better fit
    mask = np.abs(delta_T) > 1.0
    if np.sum(mask) > 10:
        fit_dT = delta_T[mask]
        fit_dV = delta_V[mask]
    else:
        fit_dT = delta_T
        fit_dV = delta_V
    
    # Linear fit
    coeffs = np.polyfit(fit_dT, fit_dV, 1)
    seebeck_fit = coeffs[0]  # Slope is Seebeck coefficient
    intercept = coeffs[1]
    
    # Calculate R²
    y_pred = np.polyval(coeffs, fit_dT)
    ss_res = np.sum((fit_dV - y_pred) ** 2)
    ss_tot = np.sum((fit_dV - np.mean(fit_dV)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    # Adjusted R²
    n = len(fit_dT)
    p = 1  # Number of predictors
    adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - p - 1) if n > p + 1 else r_squared
    
    # Calculate RMSE
    rmse = np.sqrt(ss_res / n) if n > 0 else 0
    
    # Create plots
    _create_seebeck_plots(
        time_data, delta_T, delta_V, T_hot, T_cold,
        fit_dT, fit_dV, coeffs, seebeck_fit, adj_r_squared,
        filename, output_path
    )
    
    # Save data to CSV
    _save_seebeck_data(
        time_data, T_hot, T_cold, delta_T, delta_V,
        filename, output_path
    )
    
    # Prepare data_avg for compatibility (same format as real measurement)
    data_avg = np.column_stack([
        time_data,
        T_hot,
        T_cold,
        delta_V,  # V1_avg (already in µV)
        delta_V   # V2 (same for simulation)
    ])
    
    results = {
        'Seebeck': seebeck_fit,
        'S_slope': seebeck_fit,  # Alias for backward compatibility
        'T_avg': np.mean(T_avg),
        'T_hot_avg': np.mean(T_hot),
        'T_cold_avg': np.mean(T_cold),
        'slope': seebeck_fit,  # V1-V2 slope (same as Seebeck for simulation)
        'adj_r_square': adj_r_squared,
        'offset': intercept,
        'rmse': rmse,
        'n_points': n_points,
        'measurement_time': measurement_time,
        'data_avg': data_avg,
        'simulated': True
    }
    
    print(f"\n  [SIM] Seebeck Coefficient: {seebeck_fit:.2f} µV/K")
    print(f"  [SIM] Average Temperature: {np.mean(T_avg):.2f} °C")
    print(f"  [SIM] Fit Quality (R²): {adj_r_squared:.6f}")
    
    if logger:
        logger.info(f"[SIMULATION] Seebeck: {seebeck_fit:.2f} µV/K")
        logger.info(f"[SIMULATION] R²: {adj_r_squared:.6f}")
    
    return results


def _create_seebeck_plots(
    time_data, delta_T, delta_V, T_hot, T_cold,
    fit_dT, fit_dV, coeffs, seebeck_fit, r_squared,
    filename, output_path
):
    """Create and save Seebeck measurement plots."""
    
    # Plot 1: Time series
    fig1, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    
    # Temperature vs time
    axes[0].plot(time_data/60, T_hot, 'r-', label='T_hot', alpha=0.7)
    axes[0].plot(time_data/60, T_cold, 'b-', label='T_cold', alpha=0.7)
    axes[0].set_ylabel('Temperature (°C)', fontweight='bold')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f'{filename} - Temperature Profile [SIMULATED]', fontweight='bold')
    
    # ΔT vs time
    axes[1].plot(time_data/60, delta_T, 'g-', alpha=0.7)
    axes[1].set_ylabel('ΔT (°C)', fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].axhline(y=0, color='k', linestyle='--', alpha=0.3)
    
    # ΔV vs time
    axes[2].plot(time_data/60, delta_V, 'm-', alpha=0.7)
    axes[2].set_ylabel('ΔV (µV)', fontweight='bold')
    axes[2].set_xlabel('Time (minutes)', fontweight='bold')
    axes[2].grid(True, alpha=0.3)
    axes[2].axhline(y=0, color='k', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    fig1.savefig(output_path / f"{filename}_timeseries.png", dpi=300, bbox_inches='tight')
    plt.close(fig1)
    
    # Plot 2: ΔV vs ΔT with linear fit
    fig2, ax = plt.subplots(figsize=(10, 8))
    
    ax.scatter(fit_dT, fit_dV, alpha=0.5, s=20, label='Data points')
    
    # Fit line
    fit_x = np.linspace(min(fit_dT), max(fit_dT), 100)
    fit_y = np.polyval(coeffs, fit_x)
    ax.plot(fit_x, fit_y, 'r-', linewidth=2, 
            label=f'Linear fit: S = {seebeck_fit:.2f} µV/K')
    
    ax.set_xlabel('ΔT (°C)', fontsize=12, fontweight='bold')
    ax.set_ylabel('ΔV (µV)', fontsize=12, fontweight='bold')
    ax.set_title(f'{filename} - Seebeck Coefficient Determination [SIMULATED]', 
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Add R² annotation
    textstr = f'R² = {r_squared:.6f}\nS = {seebeck_fit:.2f} µV/K'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    fig2.savefig(output_path / f"{filename}_seebeck_fit.png", dpi=300, bbox_inches='tight')
    plt.close(fig2)
    
    print(f"  Saved plots to {output_path}")


def _save_seebeck_data(time_data, T_hot, T_cold, delta_T, delta_V, filename, output_path):
    """Save Seebeck measurement data to CSV."""
    import pandas as pd
    
    df = pd.DataFrame({
        'Time_s': time_data,
        'T_hot_C': T_hot,
        'T_cold_C': T_cold,
        'Delta_T_C': delta_T,
        'Delta_V_uV': delta_V
    })
    
    csv_path = output_path / f"{filename}_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"  Saved data to {csv_path}")


def simulate_eurotherm_ramp(
    start_temp: float,
    target_temp: float,
    ramp_rate: float,
    stability_time: float = 30.0
) -> Tuple[float, bool]:
    """
    Simulate Eurotherm temperature ramp and stabilization.
    
    Args:
        start_temp: Starting temperature in °C
        target_temp: Target temperature in °C
        ramp_rate: Ramp rate in °C/min
        stability_time: Time to wait after reaching target
        
    Returns:
        Tuple of (actual_temperature, is_stable)
    """
    print(f"\n[SIMULATION] Ramping from {start_temp:.1f}°C to {target_temp:.1f}°C at {ramp_rate}°C/min")
    
    # Calculate ramp time
    temp_diff = abs(target_temp - start_temp)
    ramp_time = temp_diff / ramp_rate * 60  # seconds
    
    # Simulate with accelerated time (max 5 seconds real time)
    sim_time = min(ramp_time / 60, 5.0)
    
    print(f"  [SIM] Ramp time would be {ramp_time/60:.1f} min (simulating in {sim_time:.1f}s)")
    
    # Animate progress
    steps = 10
    for i in range(steps):
        current = start_temp + (target_temp - start_temp) * (i + 1) / steps
        print(f"\r  [SIM] Temperature: {current:.1f}°C", end="", flush=True)
        time.sleep(sim_time / steps)
    
    print(f"\r  [SIM] Temperature: {target_temp:.1f}°C - STABLE")
    
    # Add small random deviation
    actual_temp = target_temp + np.random.normal(0, 0.5)
    
    return actual_temp, True


class SimulatedSeebeckMeasurement:
    """
    Simulated version of SeebeckMeasurement class for testing.
    """
    
    def __init__(self, enable_plotting: bool = True):
        self.enable_plotting = enable_plotting
        print("[SIMULATION] Initialized simulated Seebeck measurement system")
    
    def run_measurement(
        self,
        filename: str,
        measurement_time: float,
        output_folder: str,
        logger: Optional[logging.Logger] = None
    ) -> Dict:
        """Run simulated measurement."""
        return simulate_seebeck_measurement(
            filename=filename,
            measurement_time=measurement_time,
            output_folder=output_folder,
            temperature=simulate_temperature_reading(),
            logger=logger
        )


# Global simulation mode flag
SIMULATION_MODE = False


def set_simulation_mode(enabled: bool):
    """Enable or disable global simulation mode."""
    global SIMULATION_MODE
    SIMULATION_MODE = enabled
    if enabled:
        print("\n" + "="*60)
        print("⚠️  SIMULATION MODE ENABLED")
        print("All measurements will use simulated data.")
        print("="*60 + "\n")


def is_simulation_mode() -> bool:
    """Check if simulation mode is enabled."""
    return SIMULATION_MODE
