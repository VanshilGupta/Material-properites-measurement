"""
Run Seebeck Coefficient Measurement

Standalone script to measure Seebeck coefficient.
Supports both single measurement and temperature sweep with Eurotherm controller.

Output Structure:
- Single measurement: data/SampleX/RoomTemp/Seebeck/
- Temperature sweep: data/SampleX/100C/Seebeck/, data/SampleX/150C/Seebeck/, ...
"""

import traceback
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from seebeck_measurement import SeebeckMeasurement
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
from constants import (
    EUROTHERM_COM_PORT,
    EUROTHERM_STABILITY_TOLERANCE,
    EUROTHERM_STABILITY_TIME,
    EUROTHERM_STABILITY_TIMEOUT
)
from simulation import (
    simulate_seebeck_measurement,
    simulate_temperature_reading,
    simulate_eurotherm_ramp,
    SimulatedSeebeckMeasurement,
    set_simulation_mode,
    is_simulation_mode
)


def run_single_seebeck(sample_name: str, measurement_time: float = 480.0):
    """
    Run a single Seebeck measurement at current temperature.
    
    Args:
        sample_name: Name of the sample
        measurement_time: Measurement duration in seconds
    """
    # Read current temperature from DAQ before measurement
    if is_simulation_mode():
        current_temp = simulate_temperature_reading()
    else:
        try:
            import pyvisa
            from constants import DAQ_RESOURCE
            rm = pyvisa.ResourceManager()
            daq = rm.open_resource(DAQ_RESOURCE)
            daq.write('ROUT:SCAN (@111)')
            daq.write('SENS:FUNC "TEMP", (@111)')
            temp_reading = float(daq.query('READ?').strip())
            daq.close()
            current_temp = temp_reading
        except:
            # If temperature read fails, default to 25°C
            current_temp = 25.0
    
    # Create folder structure with actual temperature
    result = create_single_measurement_structure(sample_name, "seebeck", temperature=current_temp)
    sample_folder, global_logger, temp_folder, temp_logger, seebeck_folder = result
    
    # Create measurement instance after folder structure
    if is_simulation_mode():
        measurement = SimulatedSeebeckMeasurement(enable_plotting=True)
    else:
        measurement = SeebeckMeasurement(enable_plotting=True)
    
    print("\n" + "="*60)
    print("SEEBECK COEFFICIENT MEASUREMENT")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Current Temperature: {current_temp:.1f}°C")
    print(f"Output folder: {sample_folder}")
    print(f"Measurement time: {measurement_time/60:.1f} minutes")
    print("="*60 + "\n")
    
    global_logger.info(f"Starting single Seebeck measurement")
    global_logger.info(f"Current Temperature: {current_temp:.1f}°C")
    global_logger.info(f"Measurement time: {measurement_time}s")
    
    try:
        temp_logger.info("Starting Seebeck measurement...")
        
        results = measurement.run_measurement(
            filename=sample_name,
            measurement_time=measurement_time,
            output_folder=str(seebeck_folder),
            logger=temp_logger
        )
        
        print("\n" + "="*60)
        print("MEASUREMENT COMPLETE")
        print("="*60)
        print(f"Seebeck Coefficient: {results['Seebeck']:.2f} µV/K")
        print(f"Average Temperature: {results['T_avg']:.2f} °C")
        print(f"Fit Quality (R²): {results['adj_r_square']:.6f}")
        print(f"Data saved to: {seebeck_folder}")
        print("="*60)
        
        global_logger.info(f"COMPLETED: Seebeck = {results['Seebeck']:.2f} µV/K")
        temp_logger.info(f"Seebeck Coefficient: {results['Seebeck']:.2f} µV/K")
        
        finalize_logging(temp_logger, success=True)
        finalize_logging(global_logger, success=True)
        
        return results
        
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


def run_seebeck_temperature_sweep(
    sample_name: str,
    temperatures: list,
    ramp_rate: float,
    measurement_time: float = 480.0
):
    """
    Run Seebeck measurements across multiple temperatures.
    
    Args:
        sample_name: Name of the sample
        temperatures: List of target temperatures in °C
        ramp_rate: Temperature ramp rate in °C/min
        measurement_time: Measurement duration per temperature
    """
    # Create main folder structure
    sample_folder, global_logger = create_temp_sweep_structure(sample_name)
    
    print("\n" + "="*60)
    print("SEEBECK COEFFICIENT - TEMPERATURE SWEEP")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Temperatures: {temperatures[0]}°C → {temperatures[-1]}°C ({len(temperatures)} points)")
    print(f"Ramp rate: {ramp_rate}°C/min")
    print(f"Output folder: {sample_folder}")
    print("="*60 + "\n")
    
    global_logger.info(f"Temperature sweep: {temperatures}")
    global_logger.info(f"Ramp rate: {ramp_rate}°C/min")
    
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
                stable = eurotherm.wait_for_stability(
                    target=target_temp,
                    tolerance=EUROTHERM_STABILITY_TOLERANCE,
                    stable_time=EUROTHERM_STABILITY_TIME,
                    timeout=EUROTHERM_STABILITY_TIMEOUT
                )
                actual_temp = eurotherm.read_temperature()
            
            if not stable:
                global_logger.warning(f"Temperature did not stabilize at {target_temp}°C, proceeding anyway")
            
            # Create temperature folder
            temp_folder, temp_logger = create_temperature_folder(
                sample_folder, target_temp, ['Seebeck']
            )
            seebeck_folder = temp_folder / "Seebeck"
            
            global_logger.info(f"Measuring Seebeck at {actual_temp:.1f}°C (target: {target_temp}°C)")
            temp_logger.info(f"Actual temperature: {actual_temp:.1f}°C")
            
            # Run Seebeck measurement
            if is_simulation_mode():
                measurement = SimulatedSeebeckMeasurement(enable_plotting=True)
            else:
                measurement = SeebeckMeasurement(enable_plotting=True)
            filename = f"{sample_name}_{int(target_temp)}C"
            
            try:
                results = measurement.run_measurement(
                    filename=filename,
                    measurement_time=measurement_time,
                    output_folder=str(seebeck_folder),
                    logger=temp_logger
                )
                
                results['target_temp'] = target_temp
                results['actual_temp'] = actual_temp
                all_results.append(results)
                
                global_logger.info(f"COMPLETED {target_temp}°C: Seebeck = {results['Seebeck']:.2f} µV/K")
                temp_logger.info(f"Seebeck Coefficient: {results['Seebeck']:.2f} µV/K")
                finalize_logging(temp_logger, success=True)
                
            except Exception as e:
                global_logger.error(f"Measurement failed at {target_temp}°C: {e}")
                temp_logger.error(f"Error: {e}")
                finalize_logging(temp_logger, success=False, error_msg=str(e))
                all_results.append({
                    'target_temp': target_temp,
                    'actual_temp': actual_temp,
                    'Seebeck': np.nan,
                    'T_avg': np.nan,
                    'adj_r_square': np.nan,
                    'error': str(e)
                })
        
        # Save aggregated results
        save_seebeck_vs_temp(sample_folder, sample_name, all_results)
        
        global_logger.info("="*60)
        global_logger.info("TEMPERATURE SWEEP COMPLETED")
        global_logger.info("="*60)
        finalize_logging(global_logger, success=True)
        
        return all_results
        
    except KeyboardInterrupt:
        global_logger.warning("Temperature sweep interrupted by user")
        # Save data collected so far
        if all_results:
            save_seebeck_vs_temp(sample_folder, sample_name, all_results)
            global_logger.info("Partial data saved before exit")
        finalize_logging(global_logger, success=False, error_msg="User interrupted")
        print("\n\nMeasurement interrupted - partial data saved")
        return all_results
        
    finally:
        # Safety: cool down and disconnect (only if real Eurotherm)
        if eurotherm is not None:
            eurotherm.set_temperature(25.0)
            eurotherm.disconnect()


def save_seebeck_vs_temp(sample_folder: Path, sample_name: str, results: list):
    """Save aggregated Seebeck vs Temperature data."""
    if not results:
        print("No results to save.")
        return
    
    # Prepare data
    data = {
        'Target_Temp_C': [r.get('target_temp', np.nan) for r in results],
        'Actual_Temp_C': [r.get('actual_temp', np.nan) for r in results],
        'Seebeck_uV_K': [r.get('Seebeck', np.nan) for r in results],
        'T_avg_C': [r.get('T_avg', np.nan) for r in results],
        'R_squared': [r.get('adj_r_square', np.nan) for r in results]
    }
    
    df = pd.DataFrame(data)
    
    # Save to CSV
    csv_path = sample_folder / f"{sample_name}_Seebeck_vs_Temp.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved: {csv_path}")
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    valid = ~np.isnan(data['Seebeck_uV_K'])
    
    if any(valid):
        temps = np.array(data['Target_Temp_C'])[valid]
        seebeck = np.array(data['Seebeck_uV_K'])[valid]
        ax.plot(temps, seebeck, 'o-', markersize=8, linewidth=2)
    ax.set_xlabel('Temperature (°C)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Seebeck Coefficient (µV/K)', fontsize=12, fontweight='bold')
    ax.set_title(f'{sample_name} - Seebeck vs Temperature', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot_path = sample_folder / f"{sample_name}_Seebeck_vs_Temp.png"
    fig.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {plot_path}")


def main():
    """Main entry point for Seebeck measurement."""
    
    print("\n" + "="*60)
    print("SEEBECK COEFFICIENT MEASUREMENT SYSTEM")
    print("="*60)
    
    # Ask for simulation mode
    sim_mode = input("\nEnable SIMULATION mode? (y/n) [default: n]: ").strip().lower()
    if sim_mode == 'y':
        set_simulation_mode(True)
    
    # Get sample name
    sample_name = input("Enter sample name (default: SN2517): ").strip() or "SN2517"
    
    # Ask about Eurotherm
    use_eurotherm = input("\nEnable Eurotherm Temperature Control? (y/n) [default: n]: ").strip().lower()
    
    if use_eurotherm == 'y':
        # Get temperature sweep parameters
        start_temp, end_temp, step_temp, ramp_rate = get_temperature_range_from_user()
        temperatures = generate_temperature_list(start_temp, end_temp, step_temp)
        
        print(f"\nTemperature points: {temperatures}")
        confirm = input("Proceed with temperature sweep? (y/n) [default: y]: ").strip().lower()
        
        if confirm != 'n':
            run_seebeck_temperature_sweep(sample_name, temperatures, ramp_rate)
        else:
            print("Cancelled.")
    else:
        # Single measurement at room temperature
        run_single_seebeck(sample_name)


if __name__ == "__main__":
    main()
