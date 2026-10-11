"""
Run Electrical Conductivity Measurement

Standalone script to measure electrical conductivity (sigma).
Supports both single measurement and temperature sweep with Eurotherm controller.

Output Structure:
- Single measurement: data/SampleX/RoomTemp/Sigma/
- Temperature sweep: data/SampleX/100C/Sigma/, data/SampleX/150C/Sigma/, ...
"""

import traceback
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from measure_sigma import measure_sigma, save_results_to_csv
from constants import (
    DEFAULT_SAMPLE_THICKNESS, 
    DEFAULT_SAMPLE_DIAMETER,
    EUROTHERM_COM_PORT,
    EUROTHERM_STABILITY_TOLERANCE,
    EUROTHERM_STABILITY_TIME,
    EUROTHERM_STABILITY_TIMEOUT,
    read_current_temperature
)
from output_manager import (
    create_single_measurement_structure,
    create_temp_sweep_structure,
    create_temperature_folder,
    finalize_logging
)
from eurotherm_control import (
    EurothermController,
    get_temperature_range_from_user,
    generate_temperature_list
)
from simulation import (
    simulate_sigma_measurement,
    simulate_temperature_reading,
    simulate_eurotherm_ramp,
    set_simulation_mode,
    is_simulation_mode
)


def run_single_sigma(sample_name: str, thickness: float, diameter: float):
    """
    Run a single sigma measurement at current temperature.
    
    Args:
        sample_name: Name of the sample
        thickness: Sample thickness in mm
        diameter: Sample diameter in mm
    """
    # Read current temperature
    if is_simulation_mode():
        current_temp = simulate_temperature_reading()
    else:
        current_temp = read_current_temperature()
        if current_temp is None:
            print("✗ ERROR: Could not read the temperature from the DAQ "
                  "thermocouple (channel 111) — measurement not started.")
            return None

    # Create folder structure with actual temperature
    result = create_single_measurement_structure(sample_name, "sigma", temperature=current_temp)
    sample_folder, global_logger, temp_folder, temp_logger, sigma_folder = result
    
    print("\n" + "="*60)
    print("ELECTRICAL CONDUCTIVITY MEASUREMENT")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Current Temperature: {current_temp:.1f}°C")
    print(f"Thickness: {thickness} mm, Diameter: {diameter} mm")
    print(f"Output folder: {sample_folder}")
    print("="*60 + "\n")
    
    global_logger.info(f"Starting single sigma measurement")
    global_logger.info(f"Current Temperature: {current_temp:.1f}°C")
    global_logger.info(f"Thickness: {thickness} mm, Diameter: {diameter} mm")
    
    try:
        temp_logger.info("Starting sigma measurement...")
        
        if is_simulation_mode():
            results = simulate_sigma_measurement(
                sample_t=thickness,
                sample_dia=diameter,
                temperature=current_temp,
                verbose=True,
                logger=temp_logger
            )
        else:
            results = measure_sigma(
                sample_t=thickness, 
                sample_dia=diameter, 
                verbose=True,
                logger=temp_logger
            )
        
        if results:
            print("\n" + "="*60)
            print("MEASUREMENT COMPLETE")
            print("="*60)
            print(f"Electrical Conductivity: {results['corr_sigma']:.2e} S/cm")
            print(f"Valid Measurements: {results['valid_count']}/5")
            print(f"Data saved to: {sigma_folder}")
            print("="*60)
            
            # Save results
            save_results_to_csv(results, sample_name, str(sigma_folder))
            
            global_logger.info(f"COMPLETED: Sigma = {results['corr_sigma']:.2e} S/cm")
            temp_logger.info(f"Electrical Conductivity: {results['corr_sigma']:.2e} S/cm")
            
            finalize_logging(temp_logger, success=True)
            finalize_logging(global_logger, success=True)
            
            return results
        else:
            global_logger.error("Measurement failed - no results")
            finalize_logging(temp_logger, success=False, error_msg="No results")
            finalize_logging(global_logger, success=False, error_msg="No results")
            return None
            
    except KeyboardInterrupt:
        global_logger.warning("Measurement interrupted by user")
        finalize_logging(temp_logger, success=False, error_msg="User interrupted")
        finalize_logging(global_logger, success=False, error_msg="User interrupted")
        print("\n\nMeasurement interrupted by user")
        return None
        
    except Exception as e:
        error_details = traceback.format_exc()
        global_logger.error(f"Measurement failed: {e}")
        temp_logger.error(f"Error: {e}\n{error_details}")
        finalize_logging(temp_logger, success=False, error_msg=str(e))
        finalize_logging(global_logger, success=False, error_msg=str(e))
        print(f"\nError: {e}")
        traceback.print_exc()
        return None


def run_sigma_temperature_sweep(
    sample_name: str,
    thickness: float,
    diameter: float,
    temperatures: list,
    ramp_rate: float,
    stability_wait: float = 1200.0
):
    """
    Run sigma measurements across multiple temperatures.
    
    Args:
        sample_name: Name of the sample
        thickness: Sample thickness in mm
        diameter: Sample diameter in mm
        temperatures: List of target temperatures in °C
        ramp_rate: Temperature ramp rate in °C/min
    """
    # Create main folder structure
    sample_folder, global_logger = create_temp_sweep_structure(sample_name)
    
    print("\n" + "="*60)
    print("ELECTRICAL CONDUCTIVITY - TEMPERATURE SWEEP")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Thickness: {thickness} mm, Diameter: {diameter} mm")
    print(f"Temperatures: {temperatures[0]}°C → {temperatures[-1]}°C ({len(temperatures)} points)")
    print(f"Ramp rate: {ramp_rate}°C/min")
    print(f"Output folder: {sample_folder}")
    print("="*60 + "\n")
    
    global_logger.info(f"Temperature sweep: {temperatures}")
    global_logger.info(f"Ramp rate: {ramp_rate}°C/min")
    global_logger.info(f"Sample: {thickness}mm thick, {diameter}mm diameter")
    
    # Connect to Eurotherm (or simulate)
    eurotherm = None
    if not is_simulation_mode():
        eurotherm = EurothermController(com_port=EUROTHERM_COM_PORT)
        eurotherm.set_logger(global_logger)
        
        if not eurotherm.connect():
            global_logger.error("Failed to connect to Eurotherm!")
            finalize_logging(global_logger, success=False, error_msg="Eurotherm connection failed")
            return None
        
        # Set to auto mode and ramp rate
        eurotherm.set_auto_mode()
        eurotherm.set_ramp_rate(ramp_rate)
    else:
        global_logger.info("[SIMULATION] Eurotherm controller simulated")
    
    # Store results for all temperatures
    all_results = []
    
    try:
        for i, target_temp in enumerate(temperatures):
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(temperatures)}] TARGET TEMPERATURE: {target_temp}°C")
            print("="*60)
            
            global_logger.info(f"--- Starting measurement at {target_temp}°C ({i+1}/{len(temperatures)}) ---")
            
            # Set target temperature and wait for stabilization
            if is_simulation_mode():
                prev_temp = temperatures[i-1] if i > 0 else 25.0
                actual_temp, stable = simulate_eurotherm_ramp(prev_temp, target_temp, ramp_rate)
            else:
                # Set target temperature
                eurotherm.set_temperature(target_temp)
                
                # Wait for stabilization
                import time as _time
                print(f"  Waiting {stability_wait/60:.0f} min for stabilisation ...")
                _time.sleep(stability_wait)
                actual_temp = eurotherm.read_temperature()
            
            
            # Create temperature folder
            temp_folder, temp_logger = create_temperature_folder(
                sample_folder, target_temp, ['Sigma']
            )
            sigma_folder = temp_folder / "Sigma"
            
            global_logger.info(f"Measuring sigma at {actual_temp:.1f}°C (target: {target_temp}°C)")
            temp_logger.info(f"Actual temperature: {actual_temp:.1f}°C")
            temp_logger.info(f"Sample: {thickness}mm thick, {diameter}mm diameter")
            
            # Run sigma measurement
            try:
                if is_simulation_mode():
                    results = simulate_sigma_measurement(
                        sample_t=thickness,
                        sample_dia=diameter,
                        temperature=actual_temp,
                        verbose=True,
                        logger=temp_logger
                    )
                else:
                    results = measure_sigma(
                        sample_t=thickness,
                        sample_dia=diameter,
                        verbose=True,
                        logger=temp_logger
                    )
                
                if results:
                    results['target_temp'] = target_temp
                    results['actual_temp'] = actual_temp
                    all_results.append(results)
                    
                    # Save individual measurement
                    save_results_to_csv(results, f"{sample_name}_{int(target_temp)}C", str(sigma_folder))
                    
                    global_logger.info(f"COMPLETED {target_temp}°C: Sigma = {results['corr_sigma']:.2e} S/cm")
                    temp_logger.info(f"Electrical Conductivity: {results['corr_sigma']:.2e} S/cm")
                    finalize_logging(temp_logger, success=True)
                else:
                    global_logger.error(f"No results at {target_temp}°C")
                    temp_logger.error("Measurement returned no results")
                    finalize_logging(temp_logger, success=False, error_msg="No results")
                    all_results.append({
                        'target_temp': target_temp,
                        'actual_temp': actual_temp,
                        'corr_sigma': np.nan,
                        'uncorr_sigma': np.nan,
                        'error': 'No results'
                    })
                    
            except Exception as e:
                global_logger.error(f"Measurement failed at {target_temp}°C: {e}")
                temp_logger.error(f"Error: {e}")
                finalize_logging(temp_logger, success=False, error_msg=str(e))
                all_results.append({
                    'target_temp': target_temp,
                    'actual_temp': actual_temp,
                    'corr_sigma': np.nan,
                    'uncorr_sigma': np.nan,
                    'error': str(e)
                })
        
        # Save aggregated results
        save_sigma_vs_temp(sample_folder, sample_name, all_results)
        
        global_logger.info("="*60)
        global_logger.info("TEMPERATURE SWEEP COMPLETED")
        global_logger.info("="*60)
        finalize_logging(global_logger, success=True)
        
        return all_results
        
    except KeyboardInterrupt:
        global_logger.warning("Temperature sweep interrupted by user")
        # Save data collected so far
        if all_results:
            save_sigma_vs_temp(sample_folder, sample_name, all_results)
            global_logger.info("Partial data saved before exit")
        finalize_logging(global_logger, success=False, error_msg="User interrupted")
        print("\n\nMeasurement interrupted - partial data saved")
        return all_results
        
    finally:
        # Safety: cool down and disconnect (only if real Eurotherm)
        if eurotherm is not None:
            eurotherm.set_temperature(25.0)
            eurotherm.disconnect()


def save_sigma_vs_temp(sample_folder: Path, sample_name: str, results: list):
    """Save aggregated Sigma vs Temperature data."""
    if not results:
        print("No results to save.")
        return
    
    # Prepare data
    data = {
        'Target_Temp_C': [r.get('target_temp', np.nan) for r in results],
        'Actual_Temp_C': [r.get('actual_temp', np.nan) for r in results],
        'Sigma_S_cm': [r.get('corr_sigma', np.nan) for r in results],
        'Sigma_uncorr_S_cm': [r.get('uncorr_sigma', np.nan) for r in results],
        'Valid_Count': [r.get('valid_count', np.nan) for r in results]
    }
    
    df = pd.DataFrame(data)
    
    # Save to CSV
    csv_path = sample_folder / f"{sample_name}_Sigma_vs_Temp.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved: {csv_path}")
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    valid = ~np.isnan(data['Sigma_S_cm'])
    
    if any(valid):
        temps = np.array(data['Target_Temp_C'])[valid]
        sigma = np.array(data['Sigma_S_cm'])[valid]
        ax.semilogy(temps, sigma, 'o-', markersize=8, linewidth=2)
    ax.set_xlabel('Temperature (°C)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Electrical Conductivity (S/cm)', fontsize=12, fontweight='bold')
    ax.set_title(f'{sample_name} - Sigma vs Temperature', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, which='both')
    
    plt.tight_layout()
    plot_path = sample_folder / f"{sample_name}_Sigma_vs_Temp.png"
    fig.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {plot_path}")


def main():
    """Main entry point for sigma measurement."""
    
    print("\n" + "="*60)
    print("ELECTRICAL CONDUCTIVITY MEASUREMENT SYSTEM")
    print("="*60)
    
    # Ask for simulation mode
    sim_mode = input("\nEnable SIMULATION mode? (y/n) [default: n]: ").strip().lower()
    if sim_mode == 'y':
        set_simulation_mode(True)
    
    # Get sample name
    sample_name = input("Enter sample name (default: Sample1): ").strip() or "Sample1"
    
    # Get sample parameters
    try:
        thickness = float(input(f"Enter sample thickness in mm (default: {DEFAULT_SAMPLE_THICKNESS}): ").strip() or DEFAULT_SAMPLE_THICKNESS)
        diameter = float(input(f"Enter sample diameter in mm (default: {DEFAULT_SAMPLE_DIAMETER}): ").strip() or DEFAULT_SAMPLE_DIAMETER)
    except ValueError:
        print("Invalid input, using default values")
        thickness = DEFAULT_SAMPLE_THICKNESS
        diameter = DEFAULT_SAMPLE_DIAMETER
    
    # Ask about Eurotherm
    use_eurotherm = input("\nEnable Eurotherm Temperature Control? (y/n) [default: n]: ").strip().lower()
    
    if use_eurotherm == 'y':
        # Get temperature sweep parameters
        start_temp, end_temp, step_temp, ramp_rate = get_temperature_range_from_user()
        temperatures = generate_temperature_list(start_temp, end_temp, step_temp)
        
        print(f"\nTemperature points: {temperatures}")
        confirm = input("Proceed with temperature sweep? (y/n) [default: y]: ").strip().lower()
        
        if confirm != 'n':
            # Ask for stability wait time
            try:
                stability_input = input(
                    "Enter stability wait time in minutes (default: 20): "
                ).strip() or "20"
                stability_wait = float(stability_input) * 60.0
            except ValueError:
                stability_wait = 1200.0
            run_sigma_temperature_sweep(
                sample_name, thickness, diameter,
                temperatures, ramp_rate,
                stability_wait=stability_wait,
            )
        else:
            print("Cancelled.")
    else:
        # Single measurement at room temperature
        run_single_sigma(sample_name, thickness, diameter)


if __name__ == "__main__":
    main()
