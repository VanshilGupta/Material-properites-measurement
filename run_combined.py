"""
Run Combined Sigma + Seebeck Measurements

At each temperature:
1. Run Sigma (Electrical Conductivity) measurement first
2. Turn off power supply (safety)
3. Run Seebeck coefficient measurement

Output Structure:
- Temperature sweep: data/SampleX/100C/{Sigma/, Seebeck/}, ...
- Aggregated: SampleX_Sigma_vs_Temp.csv, SampleX_Seebeck_vs_Temp.csv
"""

import traceback
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from measure_sigma import measure_sigma, save_results_to_csv
from seebeck_measurement import SeebeckMeasurement
from run_sigma import save_sigma_vs_temp
from run_seebeck import save_seebeck_vs_temp
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
    create_temp_sweep_structure,
    create_temperature_folder,
    create_single_measurement_structure,
    finalize_logging
)
from eurotherm_control import (
    EurothermController,
    get_temperature_range_from_user,
    generate_temperature_list
)
from simulation import (
    simulate_sigma_measurement,
    simulate_seebeck_measurement,
    simulate_temperature_reading,
    simulate_eurotherm_ramp,
    SimulatedSeebeckMeasurement,
    set_simulation_mode,
    is_simulation_mode
)


def run_single_combined(
    sample_name: str,
    thickness: float,
    diameter: float,
    seebeck_time: float = 480.0
):
    """
    Run both Sigma and Seebeck measurements at current temperature (no Eurotherm).
    
    Args:
        sample_name: Name of the sample
        thickness: Sample thickness in mm
        diameter: Sample diameter in mm
        seebeck_time: Seebeck measurement duration in seconds
    """
    # Read current temperature
    if is_simulation_mode():
        current_temp = simulate_temperature_reading()
    else:
        current_temp = read_current_temperature()
    
    # Create folder structure with actual temperature (for Sigma first, we'll add Seebeck subfolder)
    result = create_single_measurement_structure(sample_name, "sigma", temperature=current_temp)
    sample_folder, global_logger, temp_folder, temp_logger, sigma_folder = result
    
    # Create Seebeck subfolder in the same temperature folder
    seebeck_folder = temp_folder / "Seebeck"
    seebeck_folder.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*60)
    print("COMBINED SIGMA + SEEBECK MEASUREMENT (Single Temperature)")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Current Temperature: {current_temp:.1f}°C")
    print(f"Thickness: {thickness} mm, Diameter: {diameter} mm")
    print(f"Seebeck time: {seebeck_time/60:.1f} minutes")
    print(f"Output folder: {sample_folder}")
    print("="*60 + "\n")
    
    global_logger.info(f"Starting combined Sigma + Seebeck measurement (single temperature)")
    global_logger.info(f"Current Temperature: {current_temp:.1f}°C")
    global_logger.info(f"Sample: {thickness}mm thick, {diameter}mm diameter")
    
    sigma_results = None
    seebeck_results = None
    
    try:
        # =============================================
        # STEP 1: SIGMA MEASUREMENT
        # =============================================
        print(f"\n--- SIGMA MEASUREMENT at {current_temp:.1f}°C ---")
        global_logger.info(f"Starting SIGMA measurement")
        temp_logger.info("Starting SIGMA measurement...")
        
        try:
            if is_simulation_mode():
                sigma_results = simulate_sigma_measurement(
                    sample_t=thickness,
                    sample_dia=diameter,
                    temperature=current_temp,
                    verbose=True,
                    logger=temp_logger
                )
            else:
                sigma_results = measure_sigma(
                    sample_t=thickness,
                    sample_dia=diameter,
                    verbose=True,
                    logger=temp_logger
                )
            
            if sigma_results:
                sigma_results['temperature'] = current_temp
                
                # Save individual measurement
                save_results_to_csv(sigma_results, f"{sample_name}_{int(current_temp)}C", str(sigma_folder))
                
                print(f"\n✅ SIGMA: {sigma_results['corr_sigma']:.2e} S/cm")
                global_logger.info(f"SIGMA: {sigma_results['corr_sigma']:.2e} S/cm")
                temp_logger.info(f"Sigma: {sigma_results['corr_sigma']:.2e} S/cm")
            else:
                print("\n❌ SIGMA measurement failed - no results")
                global_logger.error("Sigma measurement failed - no results")
                temp_logger.error("Sigma: No results")
                
        except Exception as e:
            print(f"\n❌ SIGMA measurement error: {e}")
            global_logger.error(f"Sigma failed: {e}")
            temp_logger.error(f"Sigma error: {e}")
        
        # SAFETY: Brief pause between measurements
        print("\n⏳ Switching to Seebeck measurement (2s pause for safety)...")
        time.sleep(2)
        
        # =============================================
        # STEP 2: SEEBECK MEASUREMENT
        # =============================================
        print(f"\n--- SEEBECK MEASUREMENT at {current_temp:.1f}°C ---")
        global_logger.info(f"Starting SEEBECK measurement")
        temp_logger.info("Starting SEEBECK measurement...")
        
        try:
            if is_simulation_mode():
                measurement = SimulatedSeebeckMeasurement(enable_plotting=True)
            else:
                measurement = SeebeckMeasurement(enable_plotting=True)
            filename = f"{sample_name}_{int(current_temp)}C"
            
            seebeck_results = measurement.run_measurement(
                filename=filename,
                measurement_time=seebeck_time,
                output_folder=str(seebeck_folder),
                logger=temp_logger
            )
            
            seebeck_results['temperature'] = current_temp
            
            print(f"\n✅ SEEBECK: {seebeck_results['Seebeck']:.2f} µV/K")
            global_logger.info(f"SEEBECK: {seebeck_results['Seebeck']:.2f} µV/K")
            temp_logger.info(f"Seebeck: {seebeck_results['Seebeck']:.2f} µV/K")
            
        except Exception as e:
            print(f"\n❌ SEEBECK measurement error: {e}")
            global_logger.error(f"Seebeck failed: {e}")
            temp_logger.error(f"Seebeck error: {e}")
        
        # Print summary
        print("\n" + "="*60)
        print("MEASUREMENT COMPLETE")
        print("="*60)
        print(f"Temperature: {current_temp:.1f}°C")
        if sigma_results:
            print(f"Electrical Conductivity: {sigma_results['corr_sigma']:.2e} S/cm")
        else:
            print("Electrical Conductivity: FAILED")
        if seebeck_results:
            print(f"Seebeck Coefficient: {seebeck_results['Seebeck']:.2f} µV/K")
        else:
            print("Seebeck Coefficient: FAILED")
        print(f"Data saved to: {temp_folder}")
        print("="*60)
        
        global_logger.info("Combined measurement completed")
        finalize_logging(temp_logger, success=True)
        finalize_logging(global_logger, success=True)
        
        return sigma_results, seebeck_results
        
    except KeyboardInterrupt:
        global_logger.warning("Measurement interrupted by user")
        finalize_logging(temp_logger, success=False, error_msg="User interrupted")
        finalize_logging(global_logger, success=False, error_msg="User interrupted")
        print("\n\nMeasurement interrupted")
        return sigma_results, seebeck_results
        
    except Exception as e:
        global_logger.error(f"Unexpected error: {e}")
        global_logger.error(traceback.format_exc())
        finalize_logging(temp_logger, success=False, error_msg=str(e))
        finalize_logging(global_logger, success=False, error_msg=str(e))
        raise


def run_combined_temperature_sweep(
    sample_name: str,
    thickness: float,
    diameter: float,
    temperatures: list,
    ramp_rate: float,
    seebeck_time: float = 480.0,
    stability_wait: float = 1200.0
):
    """
    Run both Sigma and Seebeck measurements across multiple temperatures.
    
    At each temperature:
    - Run sigma first (uses power supply current)
    - Turn off power supply for safety
    - Run Seebeck (uses heater, no high current)
    
    Args:
        sample_name: Name of the sample
        thickness: Sample thickness in mm
        diameter: Sample diameter in mm
        temperatures: List of target temperatures in °C
        ramp_rate: Temperature ramp rate in °C/min
        seebeck_time: Seebeck measurement duration in seconds
    """
    # Create main folder structure
    sample_folder, global_logger = create_temp_sweep_structure(sample_name)
    
    print("\n" + "="*60)
    print("COMBINED SIGMA + SEEBECK TEMPERATURE SWEEP")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Thickness: {thickness} mm, Diameter: {diameter} mm")
    print(f"Temperatures: {temperatures[0]}°C → {temperatures[-1]}°C ({len(temperatures)} points)")
    print(f"Ramp rate: {ramp_rate}°C/min")
    print(f"Seebeck time per point: {seebeck_time/60:.1f} minutes")
    print(f"Output folder: {sample_folder}")
    print("="*60 + "\n")
    
    global_logger.info(f"Combined Sigma + Seebeck measurement")
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
            return None, None
        
        # Set to auto mode and ramp rate
        eurotherm.set_auto_mode()
        eurotherm.set_ramp_rate(ramp_rate)
    else:
        global_logger.info("[SIMULATION] Eurotherm controller simulated")
    
    # Store results for all temperatures
    all_sigma_results = []
    all_seebeck_results = []
    
    try:
        for i, target_temp in enumerate(temperatures):
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(temperatures)}] TARGET TEMPERATURE: {target_temp}°C")
            print("="*60)
            
            global_logger.info(f"--- Temperature {target_temp}°C ({i+1}/{len(temperatures)}) ---")
            
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
            
            # Create temperature folder with both subfolders
            temp_folder, temp_logger = create_temperature_folder(
                sample_folder, target_temp, ['Sigma', 'Seebeck']
            )
            sigma_folder = temp_folder / "Sigma"
            seebeck_folder = temp_folder / "Seebeck"
            
            global_logger.info(f"Actual temperature: {actual_temp:.1f}°C")
            temp_logger.info(f"Actual temperature: {actual_temp:.1f}°C")
            
            # =============================================
            # STEP 1: SIGMA MEASUREMENT
            # =============================================
            print(f"\n--- SIGMA MEASUREMENT at {target_temp}°C ---")
            global_logger.info(f"Starting SIGMA measurement at {target_temp}°C")
            temp_logger.info("Starting SIGMA measurement...")
            
            try:
                if is_simulation_mode():
                    sigma_results = simulate_sigma_measurement(
                        sample_t=thickness,
                        sample_dia=diameter,
                        temperature=actual_temp,
                        verbose=True,
                        logger=temp_logger
                    )
                else:
                    sigma_results = measure_sigma(
                        sample_t=thickness,
                        sample_dia=diameter,
                        verbose=True,
                        logger=temp_logger
                    )
                
                if sigma_results:
                    sigma_results['target_temp'] = target_temp
                    sigma_results['actual_temp'] = actual_temp
                    all_sigma_results.append(sigma_results)
                    
                    # Save individual measurement
                    save_results_to_csv(sigma_results, f"{sample_name}_{int(target_temp)}C", str(sigma_folder))
                    
                    global_logger.info(f"SIGMA at {target_temp}°C: {sigma_results['corr_sigma']:.2e} S/cm")
                    temp_logger.info(f"Sigma: {sigma_results['corr_sigma']:.2e} S/cm")
                else:
                    global_logger.error(f"Sigma measurement failed at {target_temp}°C")
                    temp_logger.error("Sigma: No results")
                    all_sigma_results.append({
                        'target_temp': target_temp,
                        'actual_temp': actual_temp,
                        'corr_sigma': np.nan,
                        'error': 'No results'
                    })
                    
            except Exception as e:
                global_logger.error(f"Sigma failed at {target_temp}°C: {e}")
                temp_logger.error(f"Sigma error: {e}")
                all_sigma_results.append({
                    'target_temp': target_temp,
                    'actual_temp': actual_temp,
                    'corr_sigma': np.nan,
                    'error': str(e)
                })
            
            # SAFETY: Brief pause between measurements
            print("\n⏳ Switching to Seebeck measurement (2s pause for safety)...")
            time.sleep(2)
            
            # =============================================
            # STEP 2: SEEBECK MEASUREMENT
            # =============================================
            print(f"\n--- SEEBECK MEASUREMENT at {target_temp}°C ---")
            global_logger.info(f"Starting SEEBECK measurement at {target_temp}°C")
            temp_logger.info("Starting SEEBECK measurement...")
            
            try:
                if is_simulation_mode():
                    measurement = SimulatedSeebeckMeasurement(enable_plotting=True)
                else:
                    measurement = SeebeckMeasurement(enable_plotting=True)
                filename = f"{sample_name}_{int(target_temp)}C"
                
                seebeck_results = measurement.run_measurement(
                    filename=filename,
                    measurement_time=seebeck_time,
                    output_folder=str(seebeck_folder),
                    logger=temp_logger
                )
                
                seebeck_results['target_temp'] = target_temp
                seebeck_results['actual_temp'] = actual_temp
                all_seebeck_results.append(seebeck_results)
                
                global_logger.info(f"SEEBECK at {target_temp}°C: {seebeck_results['Seebeck']:.2f} µV/K")
                temp_logger.info(f"Seebeck: {seebeck_results['Seebeck']:.2f} µV/K")
                
            except Exception as e:
                global_logger.error(f"Seebeck failed at {target_temp}°C: {e}")
                temp_logger.error(f"Seebeck error: {e}")
                all_seebeck_results.append({
                    'target_temp': target_temp,
                    'actual_temp': actual_temp,
                    'Seebeck': np.nan,
                    'error': str(e)
                })
            
            # Finalize this temperature
            finalize_logging(temp_logger, success=True)
            
            print(f"\n✅ Completed measurements at {target_temp}°C")
        
        # Save aggregated results
        save_sigma_vs_temp(sample_folder, sample_name, all_sigma_results)
        save_seebeck_vs_temp(sample_folder, sample_name, all_seebeck_results)
        
        # Print summary
        print_summary(sample_name, all_sigma_results, all_seebeck_results)
        
        global_logger.info("="*60)
        global_logger.info("COMBINED TEMPERATURE SWEEP COMPLETED")
        global_logger.info("="*60)
        finalize_logging(global_logger, success=True)
        
        return all_sigma_results, all_seebeck_results
        
    except KeyboardInterrupt:
        global_logger.warning("Temperature sweep interrupted by user")
        # Save data collected so far
        if all_sigma_results:
            save_sigma_vs_temp(sample_folder, sample_name, all_sigma_results)
        if all_seebeck_results:
            save_seebeck_vs_temp(sample_folder, sample_name, all_seebeck_results)
        global_logger.info("Partial data saved before exit")
        finalize_logging(global_logger, success=False, error_msg="User interrupted")
        print("\n\nMeasurement interrupted - partial data saved")
        return all_sigma_results, all_seebeck_results
        
    finally:
        # Safety: cool down and disconnect (only if real Eurotherm)
        if eurotherm is not None:
            eurotherm.set_temperature(25.0)
            eurotherm.disconnect()


def print_summary(sample_name: str, sigma_results: list, seebeck_results: list):
    """Print a summary table of all results."""
    
    print("\n" + "="*80)
    print(f"MEASUREMENT SUMMARY - {sample_name}")
    print("="*80)
    print(f"{'Temp (°C)':<12} {'Sigma (S/cm)':<18} {'Seebeck (µV/K)':<18}")
    print("-"*80)
    
    for i, (sig, see) in enumerate(zip(sigma_results, seebeck_results)):
        temp = sig.get('target_temp', np.nan)
        sigma_val = sig.get('corr_sigma', np.nan)
        seebeck_val = see.get('Seebeck', np.nan)
        
        sigma_str = f"{sigma_val:.2e}" if not np.isnan(sigma_val) else "FAILED"
        seebeck_str = f"{seebeck_val:.2f}" if not np.isnan(seebeck_val) else "FAILED"
        
        print(f"{temp:<12.0f} {sigma_str:<18} {seebeck_str:<18}")
    
    print("="*80)


def main():
    """Main entry point for combined measurement."""
    
    print("\n" + "="*60)
    print("COMBINED SIGMA + SEEBECK MEASUREMENT SYSTEM")
    print("="*60)
    print("At each temperature:")
    print("  1. Sigma (electrical conductivity)")
    print("  2. Seebeck coefficient")
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
    
    # Get Seebeck measurement time
    try:
        seebeck_time = float(input("Enter Seebeck measurement time in minutes (default: 8): ").strip() or 8) * 60
    except ValueError:
        seebeck_time = 480.0
    
    # Ask for measurement mode
    print("\n--- Measurement Mode ---")
    print("1. Single measurement (current temperature, no Eurotherm)")
    print("2. Temperature sweep (with Eurotherm control)")
    mode = input("Select mode [1/2] (default: 1): ").strip() or "1"
    
    if mode == "2":
        # Temperature sweep mode
        print("\n--- Temperature Sweep Configuration ---")
        start_temp, end_temp, step_temp, ramp_rate = get_temperature_range_from_user()
        temperatures = generate_temperature_list(start_temp, end_temp, step_temp)
        
        print(f"\n{'='*60}")
        print("CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Mode: Temperature Sweep (with Eurotherm)")
        print(f"Sample: {sample_name}")
        print(f"Thickness: {thickness} mm, Diameter: {diameter} mm")
        print(f"Temperature points: {temperatures}")
        print(f"Ramp rate: {ramp_rate}°C/min")
        print(f"Seebeck time: {seebeck_time/60:.1f} minutes per point")
        print("="*60)
        
        confirm = input("\nProceed with temperature sweep? (y/n) [default: y]: ").strip().lower()
        
        if confirm != 'n':
            # Ask for stability wait time
            try:
                stability_input = input(
                    "Enter stability wait time in minutes (default: 20): "
                ).strip() or "20"
                stability_wait = float(stability_input) * 60.0
            except ValueError:
                stability_wait = 1200.0
            run_combined_temperature_sweep(
                sample_name, thickness, diameter,
                temperatures, ramp_rate, seebeck_time,
                stability_wait=stability_wait,
            )
        else:
            print("Cancelled.")
    else:
        # Single measurement mode
        print(f"\n{'='*60}")
        print("CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Mode: Single Measurement (current temperature)")
        print(f"Sample: {sample_name}")
        print(f"Thickness: {thickness} mm, Diameter: {diameter} mm")
        print(f"Seebeck time: {seebeck_time/60:.1f} minutes")
        print("="*60)
        
        confirm = input("\nProceed with single measurement? (y/n) [default: y]: ").strip().lower()
        
        if confirm != 'n':
            run_single_combined(sample_name, thickness, diameter, seebeck_time)
        else:
            print("Cancelled.")


if __name__ == "__main__":
    main()
