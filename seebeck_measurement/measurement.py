"""Main Seebeck coefficient measurement module."""

import logging
import numpy as np
import time

from .config import (
    DAQ_CHANNELS,
    HEATER_ON_DURATION,
    MAX_SAMPLES,
    MAX_TEMP_DIFFERENCE,
    PLOT_UPDATE_INTERVAL,
)
from .curve_fitting import fit_v1_v2_and_calculate_seebeck
from .data_processing import save_to_csv
from .instruments import DAQController, PowerSupplyController, get_daq, get_power_supply
from .plotting import SeebeckPlotter
from .temperature_conversion import temp_to_voltage, voltage_to_temp


class SeebeckMeasurement:
    """
    Main class for Seebeck coefficient measurements.
    
    Orchestrates instrument control, data acquisition, and analysis.
    """
    
    def __init__(
        self,
        daq_resource: str = None,
        ps_resource: str = None,
        enable_plotting: bool = True
    ):
        """
        Initialize measurement system.
        
        Args:
            daq_resource: DAQ VISA resource string
            ps_resource: Power supply VISA resource string
            enable_plotting: Enable real-time plotting
        """
        self.daq = get_daq() if daq_resource is None else DAQController(daq_resource)
        self.ps = get_power_supply() if ps_resource is None else PowerSupplyController(ps_resource)
        self.plotter = SeebeckPlotter() if enable_plotting else None
        
        # Measurement parameters
        self.max_samples = MAX_SAMPLES
        self.dt_max = MAX_TEMP_DIFFERENCE # Maximum temperature difference (°C)
        
        # Data storage
        self.reset_data()
        
        # Logger (will be set in run_measurement if provided)
        self.logger = None
    
    def _log(self, level: str, message: str):
        """
        Log a message if logger is available.
        
        Args:
            level: Log level ('debug', 'info', 'warning', 'error')
            message: Message to log
        """
        if self.logger:
            log_method = getattr(self.logger, level, self.logger.info)
            log_method(message)
    
    def reset_data(self):
        """Reset all data arrays."""
        # Individual measurement data with timestamps
        # T1 has 2 readings per cycle (forward and backward)
        self.T1_data = {'time': [], 'values': []}  # Each entry is [t1, t2] and [val1, val2]
        # T2 has 2 readings per cycle (forward and backward)
        self.T2_data = {'time': [], 'values': []}
        # V1 has 2 readings per cycle (forward and backward)
        self.V1_data = {'time': [], 'values': []}
        # V2 has 1 reading per cycle (center)
        self.V2_data = {'time': [], 'values': []}
        
        # Legacy format for compatibility
        self.time_data = []
        self.T1 = []
        self.T2 = []
        self.V1 = []
        self.V2 = []
        
        self.phase = 1
        self.GH1_active = False
        self.GH2_active = False
    
    def connect_instruments(self):
        """Connect to all instruments."""
        print("Connecting to instruments...")
        self.daq.connect()
        time.sleep(1)
        self.ps.connect()
        time.sleep(1)
        print("All instruments connected")
    
    def disconnect_instruments(self):
        """Disconnect from all instruments."""
        print("Disconnecting instruments...")
        self.ps.turn_off_all_channels()
        self.ps.disconnect()
        self.daq.disconnect()
        print("All instruments disconnected")
    
    def read_measurement_with_timestamps(self, start_time: float) -> dict:
        """
        Read one complete measurement cycle with individual timestamps.
        
        Args:
            start_time: Reference start time for relative timestamps
        
        Returns:
            Dictionary with temperature and voltage readings plus timestamps
        """
        # Get reference temperatures
        T_ref1, T_ref2 = self.daq.get_reference_temperatures()
        V_ref1 = temp_to_voltage(T_ref1)  # mV
        V_ref2 = temp_to_voltage(T_ref2)  # mV
        
        # Read voltages from DAQ with timestamps
        result = self.daq.read_voltages_with_timestamps(DAQ_CHANNELS)
        voltages = result['voltages']
        rel_times = result['rel_times']  # Relative times within scan
        
        # Capture current time for this scan
        scan_time = time.time() - start_time
        
        # Process readings
        # voltages order: [101, 106, 111, 116, 111, 106, 101]
        # Corresponds to: [U1_1, V1_1, U2_1, V2, U2_2, V1_2, U1_2]
        # rel_times[i] is relative time of each reading within the scan
        
        U1_1 = voltages[0] * 1e3  # Convert to mV
        V1_1 = voltages[1]
        U2_1 = voltages[2] * 1e3
        V2_1 = voltages[3]
        U2_2 = voltages[4] * 1e3
        V1_2 = voltages[5]
        U1_2 = voltages[6] * 1e3
        
        # Calculate absolute timestamps for each measurement
        # rel_times are relative to start of scan, scan_time is when scan started
        t_U1_1 = scan_time + rel_times[0]
        t_V1_1 = scan_time + rel_times[1]
        t_U2_1 = scan_time + rel_times[2]
        t_V2 = scan_time + rel_times[3]   # V2 center time
        t_U2_2 = scan_time + rel_times[4]
        t_V1_2 = scan_time + rel_times[5]
        t_U1_2 = scan_time + rel_times[6]
        
        # Convert to temperatures
        T1_1 = voltage_to_temp(U1_1 + V_ref1)
        T2_1 = voltage_to_temp(U2_1 + V_ref2)
        T1_2 = voltage_to_temp(U1_2 + V_ref1)
        T2_2 = voltage_to_temp(U2_2 + V_ref2)
        
        return {
            # Temperature 1: two readings with their timestamps
            'T1': {'times': [t_U1_1, t_U1_2], 'values': [T1_1, T1_2]},
            # Temperature 2: two readings with their timestamps
            'T2': {'times': [t_U2_1, t_U2_2], 'values': [T2_1, T2_2]},
            # Voltage 1: two readings with their timestamps
            'V1': {'times': [t_V1_1, t_V1_2], 'values': [V1_1, V1_2]},
            # Voltage 2: single reading (duplicated for averaging)
            'V2': {'times': [t_V2], 'values': [V2_1]},
            # V2 center time for averaged data
            'center_time': t_V2,
            # Averaged values at center time
            'T1_avg': (T1_1 + T1_2) / 2,
            'T2_avg': (T2_1 + T2_2) / 2,
            'V1_avg': (V1_1 + V1_2) / 2,
            'V2_avg': V2_1,
        }
    
    def read_measurement(self) -> dict:
        """
        Read one complete measurement cycle (legacy method).
        
        Returns:
            Dictionary with temperature and voltage readings
        """
        # Get reference temperatures
        T_ref1, T_ref2 = self.daq.get_reference_temperatures()
        V_ref1 = temp_to_voltage(T_ref1)  # mV
        V_ref2 = temp_to_voltage(T_ref2)  # mV
        
        # Read voltages from DAQ
        voltages = self.daq.read_voltages(DAQ_CHANNELS)
        
        # Process readings
        # voltages order: [101, 106, 111, 116, 111, 106, 101]
        # Corresponds to: [U1_1, V1_1, U2_1, V2_1, U2_2, V1_2, U1_2]
        
        U1_1 = voltages[0] * 1e3  # Convert to mV
        V1_1 = voltages[1]
        U2_1 = voltages[2] * 1e3
        V2_1 = voltages[3]
        U2_2 = voltages[4] * 1e3
        V1_2 = voltages[5]
        U1_2 = voltages[6] * 1e3
        
        # Convert to temperatures
        T1_1 = voltage_to_temp(U1_1 + V_ref1)
        T2_1 = voltage_to_temp(U2_1 + V_ref2)
        T1_2 = voltage_to_temp(U1_2 + V_ref1)
        T2_2 = voltage_to_temp(U2_2 + V_ref2)
        
        return {
            'T1': [T1_1, T1_2],
            'T2': [T2_1, T2_2],
            'V1': [V1_1, V1_2],
            'V2': [V2_1, V2_1],
        }
    
    def control_heaters(self, elapsed_time: float, seebeck_meas_time: float):
        """
        Control heater states based on measurement phase.
        
        Args:
            elapsed_time: Time elapsed since measurement start (seconds)
            seebeck_meas_time: Total measurement time (seconds)
        """
        half_time = seebeck_meas_time / 2
        
        # Phase 1: Turn on first heater (0-60s)
        if self.phase == 1:
            if len(self.T1) > 0 and len(self.T2) > 0:
                if self.T1[0] > self.T2[0]:
                    print('Phase 1: Turning Heater 1 on')
                    self.ps.enable_heater(1)
                    self.GH1_active = True
                else:
                    print('Phase 1: Turning Heater 2 on')
                    self.ps.enable_heater(2)
                    self.GH2_active = True
            
            if elapsed_time > HEATER_ON_DURATION:
                self.phase = 2
                self.ps.turn_off_all_channels()
        
        # Phase 2: Wait period (half_time - 60s)
        elif self.phase == 2:
            if elapsed_time >= half_time:
                self.phase = 3
        
        # Phase 3: Turn on second heater (half_time)
        elif self.phase == 3:
            if self.GH1_active:
                print('Phase 3: Turning Heater 2 on')
                self.ps.enable_heater(2)
                self.GH1_active = False
            elif self.GH2_active:
                print('Phase 3: Turning Heater 1 on')
                self.ps.enable_heater(1)
                self.GH2_active = False
            
            if elapsed_time > half_time + HEATER_ON_DURATION:
                self.phase = 4
                self.ps.turn_off_all_channels()
    
    def run_measurement(
        self,
        filename: str = "SN2517",
        measurement_time: float = 480.0,
        output_folder: str = None,
        logger: logging.Logger = None
    ) -> dict:
        """
        Run complete Seebeck measurement.
        
        Args:
            filename: Base filename for output files
            measurement_time: Total measurement duration (seconds)
            output_folder: Output directory for data files (sample folder)
            logger: Logger instance for recording measurement events
            
        Returns:
            Dictionary with measurement results
        """
        # Set the logger for this measurement run
        self.logger = logger
        
        print(f"\n{'='*60}")
        print(f"Starting Seebeck Measurement: {filename}")
        print(f"Measurement time: {measurement_time}s ({measurement_time/60:.1f} min)")
        print(f"{'='*60}\n")
        
        self._log('info', f"Measurement parameters: filename={filename}, time={measurement_time}s")
        
        # Connect instruments
        self._log('info', "Connecting to instruments...")
        self.connect_instruments()
        self._log('info', "Instruments connected successfully")
        self.reset_data()
        
        start_time = time.time()
        
        try:
            while True:
                current_time = time.time() - start_time
                
                # Read measurements with individual timestamps
                readings = self.read_measurement_with_timestamps(start_time)
                
                # Print individual readings
                reading_str = (f"  Readings: T1_1={readings['T1']['values'][0]:.3f}°C, "
                      f"V1_1={readings['V1']['values'][0]:.6f}V, "
                      f"T2_1={readings['T2']['values'][0]:.3f}°C, "
                      f"V2={readings['V2']['values'][0]:.6f}V, "
                      f"T2_2={readings['T2']['values'][1]:.3f}°C, "
                      f"V1_2={readings['V1']['values'][1]:.6f}V, "
                      f"T1_2={readings['T1']['values'][1]:.3f}°C")
                print(reading_str)
                self._log('debug', reading_str)
                
                # Store individual measurement data
                self.T1_data['time'].append(readings['T1']['times'])
                self.T1_data['values'].append(readings['T1']['values'])
                
                self.T2_data['time'].append(readings['T2']['times'])
                self.T2_data['values'].append(readings['T2']['values'])
                
                self.V1_data['time'].append(readings['V1']['times'])
                self.V1_data['values'].append(readings['V1']['values'])
                
                self.V2_data['time'].append(readings['V2']['times'])
                self.V2_data['values'].append(readings['V2']['values'])
                
                # Store averaged data at center time
                self.time_data.append(readings['center_time'])
                self.T1.append(readings['T1_avg'])
                self.T2.append(readings['T2_avg'])
                self.V1.append(readings['V1_avg'])
                self.V2.append(readings['V2_avg'])
                
                # Update plot with averaged values
                if self.plotter:
                    self.plotter.update(
                        readings['center_time'],
                        readings['T1_avg'],
                        readings['T2_avg'],
                        readings['V1_avg'],
                        readings['V2_avg']
                    )
                
                # Control heaters
                phase_str = (f"Phase: {self.phase}, Time: {current_time:.1f}s, "
                      f"T1: {readings['T1_avg']:.2f}°C, T2: {readings['T2_avg']:.2f}°C, "
                      f"ΔT: {abs(readings['T1_avg'] - readings['T2_avg']):.2f}°C")
                print(phase_str)
                self._log('debug', phase_str)
                
                self.control_heaters(current_time, measurement_time)
                
                # Check termination conditions
                dt = abs(readings['T1_avg'] - readings['T2_avg'])
                if dt > self.dt_max or current_time > measurement_time:
                    complete_msg = f"Measurement complete (ΔT={dt:.2f}°C, t={current_time:.1f}s)"
                    print(f"\n{complete_msg}")
                    self._log('info', complete_msg)
                    break
                
                # Small delay between readings
                time.sleep(PLOT_UPDATE_INTERVAL)
        
        except Exception as e:
            self._log('error', f"Error during measurement loop: {e}")
            raise
        
        finally:
            # Ensure heaters are off
            self._log('info', "Turning off heaters and disconnecting instruments...")
            self.ps.turn_off_all_channels()
            self.disconnect_instruments()
            self._log('info', "Instruments disconnected")
            
            # Save real-time plot before closing
            if self.plotter:
                self._log('info', "Saving real-time plot...")
                self.plotter.save_plot(filename, output_folder)

            # Always attempt to save collected data, even if the loop
            # terminated due to an error.  Guard against empty datasets.
            if self.time_data:
                self._log('info', "Processing and saving data...")
                try:
                    results = self.process_and_save_data(filename, output_folder)
                except Exception as save_err:
                    self._log('error', f"Failed to save data: {save_err}")
                    results = {}
            else:
                self._log('info', "No data to save (measurement did not collect readings).")
                results = {}
        
        return results
    
    def process_and_save_data(
        self,
        filename: str,
        output_folder: str = None
    ) -> dict:
        """
        Process measurements and save results to files.
        
        Creates:
            - {filename}_all.csv: All 7 readings with individual timestamps per cycle
            - {filename}_averaged.csv: All values averaged at V2 center time
            
        Args:
            filename: Base filename for output
            output_folder: Output directory
            
        Returns:
            Dictionary with analysis results
        """
        print("\nProcessing data...")
        
        # Create single file with all 7 readings per cycle
        num_cycles = len(self.T1_data['time'])
        all_data = []
        
        for i in range(num_cycles):
            # Extract times and values for this cycle
            t_T1_1, t_T1_2 = self.T1_data['time'][i]
            T1_1, T1_2 = self.T1_data['values'][i]
            
            t_V1_1, t_V1_2 = self.V1_data['time'][i]
            V1_1, V1_2 = self.V1_data['values'][i]
            
            t_T2_1, t_T2_2 = self.T2_data['time'][i]
            T2_1, T2_2 = self.T2_data['values'][i]
            
            t_V2 = self.V2_data['time'][i][0]
            V2 = self.V2_data['values'][i][0]
            
            # Create row: t_T1_1, T1_1, _, t_V1_1, V1_1, _, t_T2_1, T2_1, _, t_V2, V2, _, t_T2_2, T2_2, _, t_V1_2, V1_2, _, t_T1_2, T1_2
            row = [
                t_T1_1, T1_1, np.nan,        # T1_1 with space
                t_V1_1, V1_1*1e6, np.nan,    # V1_1 in µV with space
                t_T2_1, T2_1, np.nan,        # T2_1 with space
                t_V2, V2*1e6, np.nan,        # V2 in µV with space
                t_T2_2, T2_2, np.nan,        # T2_2 with space
                t_V1_2, V1_2*1e6, np.nan,    # V1_2 in µV with space
                t_T1_2, T1_2                 # T1_2 (no trailing space)
            ]
            all_data.append(row)
        
        data_all = np.array(all_data)
        headers_all = [
            't_T1_1(s)', 'T1_1(°C)', '',
            't_V1_1(s)', 'V1_1(µV)', '',
            't_T2_1(s)', 'T2_1(°C)', '',
            't_V2(s)', 'V2(µV)', '',
            't_T2_2(s)', 'T2_2(°C)', '',
            't_V1_2(s)', 'V1_2(µV)', '',
            't_T1_2(s)', 'T1_2(°C)'
        ]
        save_to_csv(f'{filename}_all.csv', data_all, headers_all, output_folder)
        print(f"  Saved {filename}_all.csv ({num_cycles} cycles with 7 readings each)")
        
        # Convert averaged data to numpy arrays
        time_array = np.array(self.time_data)
        T1_array = np.array(self.T1)
        T2_array = np.array(self.T2)
        V1_array = np.array(self.V1)
        V2_array = np.array(self.V2)
        
        # Save averaged data (values at V2 center time)
        min_len = min(len(T1_array), len(T2_array), 
                     len(V1_array), len(V2_array), len(time_array))
        
        data_avg = np.column_stack([
            time_array[:min_len],
            T1_array[:min_len],
            T2_array[:min_len],
            V1_array[:min_len]*1e6,
            V2_array[:min_len]*1e6
        ])
        
        headers_avg = ['t(s)', 'T1_avg(°C)', 'T2_avg(°C)', 'V1_avg(µV)', 'V2(µV)']
        save_to_csv(f'{filename}_averaged.csv', data_avg, headers_avg, output_folder)
        print(f"  Saved {filename}_averaged.csv ({min_len} averaged readings)")
        
        # Calculate Seebeck coefficient using averaged data
        T_avg = np.mean([np.mean(T1_array), np.mean(T2_array)])
        
        slope, adj_r2, offset, rmse, S_slope = fit_v1_v2_and_calculate_seebeck(
            V1_array, V2_array, T_avg, plot=True, save_plot=True, 
            filename=filename, output_folder=output_folder
        )
        
        print(f"\n{'='*60}")
        print("MEASUREMENT RESULTS")
        print(f"{'='*60}")
        print(f"Average Temperature: {T_avg:.2f} °C")
        print(f"Seebeck Coefficient: {S_slope:.2f} µV/K")
        print(f"V1-V2 Slope: {slope:.6f}")
        print(f"Adjusted R²: {adj_r2:.8f}")
        print(f"RMSE: {rmse:.6e}")
        print(f"{'='*60}\n")
        
        results = {
            'T_avg': T_avg,
            'Seebeck': S_slope,
            'S_slope': S_slope,  # Alias for backward compatibility
            'slope': slope,
            'adj_r_square': adj_r2,
            'offset': offset,
            'rmse': rmse,
            'data_avg': data_avg
        }
        
        return results
