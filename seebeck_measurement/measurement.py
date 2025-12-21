"""Main Seebeck coefficient measurement module."""

import numpy as np
import time

from seebeck_measurement.config import DAQ_CHANNELS
from .instruments import DAQController, PowerSupplyController
from .temperature_conversion import temp_to_voltage, voltage_to_temp
from .data_processing import average_data, save_to_csv
from .curve_fitting import fit_v1_v2_and_calculate_seebeck
from .plotting import SeebeckPlotter


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
        self.daq = DAQController(daq_resource)
        self.ps = PowerSupplyController(ps_resource)
        self.plotter = SeebeckPlotter() if enable_plotting else None
        
        # Measurement parameters
        self.max_samples = 500
        self.dt_max = 8.0  # Maximum temperature difference (°C)
        
        # Data storage
        self.reset_data()
    
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
            
            if elapsed_time > 60:
                self.phase = 2
                self.ps.turn_off_all_channels()
        
        # Phase 2: Wait period (60s - half_time)
        elif self.phase == 2:
            if elapsed_time >= half_time:
                self.phase = 3
        
        # Phase 3: Turn on second heater (half_time - half_time+60s)
        elif self.phase == 3:
            if self.GH1_active:
                print('Phase 3: Turning Heater 2 on')
                self.ps.enable_heater(2)
                self.GH1_active = False
            elif self.GH2_active:
                print('Phase 3: Turning Heater 1 on')
                self.ps.enable_heater(1)
                self.GH2_active = False
            
            if elapsed_time > half_time + 60:
                self.phase = 4
                self.ps.turn_off_all_channels()
    
    def run_measurement(
        self,
        filename: str = "SN2517",
        measurement_time: float = 480.0,
        output_folder: str = None
    ) -> dict:
        """
        Run complete Seebeck measurement.
        
        Args:
            filename: Base filename for output files
            measurement_time: Total measurement duration (seconds)
            output_folder: Output directory for data files
            
        Returns:
            Dictionary with measurement results
        """
        print(f"\n{'='*60}")
        print(f"Starting Seebeck Measurement: {filename}")
        print(f"Measurement time: {measurement_time}s ({measurement_time/60:.1f} min)")
        print(f"{'='*60}\n")
        
        # Connect instruments
        self.connect_instruments()
        self.reset_data()
        
        start_time = time.time()
        
        try:
            while True:
                current_time = time.time() - start_time
                
                # Read measurements with individual timestamps
                readings = self.read_measurement_with_timestamps(start_time)
                
                # Print individual readings
                print(f"  Readings: T1_1={readings['T1']['values'][0]:.3f}°C, "
                      f"V1_1={readings['V1']['values'][0]:.6f}V, "
                      f"T2_1={readings['T2']['values'][0]:.3f}°C, "
                      f"V2={readings['V2']['values'][0]:.6f}V, "
                      f"T2_2={readings['T2']['values'][1]:.3f}°C, "
                      f"V1_2={readings['V1']['values'][1]:.6f}V, "
                      f"T1_2={readings['T1']['values'][1]:.3f}°C")
                
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
                print(f"Phase: {self.phase}, Time: {current_time:.1f}s, "
                      f"T1: {readings['T1_avg']:.2f}°C, T2: {readings['T2_avg']:.2f}°C, "
                      f"ΔT: {abs(readings['T1_avg'] - readings['T2_avg']):.2f}°C")
                
                self.control_heaters(current_time, measurement_time)
                
                # Check termination conditions
                dt = abs(readings['T1_avg'] - readings['T2_avg'])
                if dt > self.dt_max or current_time > measurement_time:
                    print(f"\nMeasurement complete (ΔT={dt:.2f}°C, t={current_time:.1f}s)")
                    break
                
                time.sleep(0.1)  # Small delay between readings
        
        finally:
            # Ensure heaters are off
            self.ps.turn_off_all_channels()
            self.disconnect_instruments()
            
            # Save real-time plot before closing
            if self.plotter:
                self.plotter.save_plot(filename, output_folder)
        
        # Process and save data
        results = self.process_and_save_data(filename, output_folder)
        
        return results
    
    def process_and_save_data(
        self,
        filename: str,
        output_folder: str = None
    ) -> dict:
        """
        Process measurements and save results to separate files.
        
        Creates:
            - {filename}_T1.csv: Temperature 1 with individual timestamps (2 readings per cycle)
            - {filename}_T2.csv: Temperature 2 with individual timestamps (2 readings per cycle)
            - {filename}_V1.csv: Voltage 1 with individual timestamps (2 readings per cycle)
            - {filename}_V2.csv: Voltage 2 with individual timestamps (1 reading per cycle)
            - {filename}_averaged.csv: All values averaged at V2 center time
            
        Args:
            filename: Base filename for output
            output_folder: Output directory
            
        Returns:
            Dictionary with analysis results
        """
        print("\nProcessing data...")
        
        # Save T1 data (2 readings per cycle with individual timestamps)
        t1_times = []
        t1_values = []
        for times, values in zip(self.T1_data['time'], self.T1_data['values']):
            for t, v in zip(times, values):
                t1_times.append(t)
                t1_values.append(v)
        data_T1 = np.column_stack([t1_times, t1_values])
        save_to_csv(f'{filename}_T1.csv', data_T1, ['t', 'T1'], output_folder)
        print(f"  Saved {filename}_T1.csv ({len(t1_times)} readings)")
        
        # Save T2 data (2 readings per cycle with individual timestamps)
        t2_times = []
        t2_values = []
        for times, values in zip(self.T2_data['time'], self.T2_data['values']):
            for t, v in zip(times, values):
                t2_times.append(t)
                t2_values.append(v)
        data_T2 = np.column_stack([t2_times, t2_values])
        save_to_csv(f'{filename}_T2.csv', data_T2, ['t', 'T2'], output_folder)
        print(f"  Saved {filename}_T2.csv ({len(t2_times)} readings)")
        
        # Save V1 data (2 readings per cycle with individual timestamps)
        v1_times = []
        v1_values = []
        for times, values in zip(self.V1_data['time'], self.V1_data['values']):
            for t, v in zip(times, values):
                v1_times.append(t)
                v1_values.append(v)
        data_V1 = np.column_stack([v1_times, v1_values])
        save_to_csv(f'{filename}_V1.csv', data_V1, ['t', 'V1'], output_folder)
        print(f"  Saved {filename}_V1.csv ({len(v1_times)} readings)")
        
        # Save V2 data (1 reading per cycle - center of scan)
        v2_times = []
        v2_values = []
        for times, values in zip(self.V2_data['time'], self.V2_data['values']):
            for t, v in zip(times, values):
                v2_times.append(t)
                v2_values.append(v)
        data_V2 = np.column_stack([v2_times, v2_values])
        save_to_csv(f'{filename}_V2.csv', data_V2, ['t', 'V2'], output_folder)
        print(f"  Saved {filename}_V2.csv ({len(v2_times)} readings)")
        
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
            V1_array[:min_len],
            V2_array[:min_len]
        ])
        
        headers_avg = ['t', 'T1_avg', 'T2_avg', 'V1_avg', 'V2']
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
            'slope': slope,
            'adj_r_square': adj_r2,
            'offset': offset,
            'rmse': rmse,
            'data_avg': data_avg
        }
        
        return results
