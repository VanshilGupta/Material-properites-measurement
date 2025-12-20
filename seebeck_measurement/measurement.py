"""Main Seebeck coefficient measurement module."""

import numpy as np
import time
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
    
    def read_measurement(self) -> dict:
        """
        Read one complete measurement cycle.
        
        Returns:
            Dictionary with temperature and voltage readings
        """
        # Get reference temperatures
        T_ref1, T_ref2 = self.daq.get_reference_temperatures()
        V_ref1 = temp_to_voltage(T_ref1)  # mV
        V_ref2 = temp_to_voltage(T_ref2)  # mV
        
        # Read voltages from DAQ
        voltages = self.daq.read_voltages()
        
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
            'V2': [V2_1, V2_2]
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
                
                # Read measurements
                readings = self.read_measurement()
                
                # Store data (both readings per cycle)
                for i in range(2):
                    self.time_data.append(current_time)
                    self.T1.append(readings['T1'][i])
                    self.T2.append(readings['T2'][i])
                    self.V1.append(readings['V1'][i])
                    self.V2.append(readings['V2'][i])
                
                # Update plot with first reading of the pair
                if self.plotter:
                    self.plotter.update(
                        current_time,
                        readings['T1'][0],
                        readings['T2'][0],
                        readings['V1'][0],
                        readings['V2'][0]
                    )
                
                # Control heaters
                print(f"Phase: {self.phase}, Time: {current_time:.1f}s, "
                      f"T1: {readings['T1'][0]:.2f}°C, T2: {readings['T2'][0]:.2f}°C, "
                      f"ΔT: {abs(readings['T1'][0] - readings['T2'][0]):.2f}°C")
                
                self.control_heaters(current_time, measurement_time)
                
                # Check termination conditions
                dt = abs(readings['T1'][0] - readings['T2'][0])
                if dt > self.dt_max or current_time > measurement_time:
                    print(f"\nMeasurement complete (ΔT={dt:.2f}°C, t={current_time:.1f}s)")
                    break
                
                time.sleep(0.1)  # Small delay between readings
        
        finally:
            # Ensure heaters are off
            self.ps.turn_off_all_channels()
            self.disconnect_instruments()
        
        # Process and save data
        results = self.process_and_save_data(filename, output_folder)
        
        return results
    
    def process_and_save_data(
        self,
        filename: str,
        output_folder: str = None
    ) -> dict:
        """
        Process measurements and save results.
        
        Args:
            filename: Base filename for output
            output_folder: Output directory
            
        Returns:
            Dictionary with analysis results
        """
        print("\nProcessing data...")
        
        # Convert to numpy arrays
        time_array = np.array(self.time_data)
        T1_array = np.array(self.T1)
        T2_array = np.array(self.T2)
        V1_array = np.array(self.V1)
        V2_array = np.array(self.V2)
        
        # Calculate temperature differences
        DT = T1_array - T2_array
        
        # Save original data
        min_len = min(len(DT), len(T1_array), len(T2_array), 
                     len(V1_array), len(V2_array), len(time_array))
        
        data_orig = np.column_stack([
            DT[:min_len],
            T1_array[:min_len],
            T2_array[:min_len],
            V1_array[:min_len],
            V2_array[:min_len],
            time_array[:min_len]
        ])
        
        headers_orig = ['DT_Bottom', 'T1', 'T2', 'V1', 'V2', 't']
        save_to_csv(f'{filename}-orig.csv', data_orig, headers_orig, output_folder)
        
        # Average data
        t_avg, T1_avg, T2_avg, V1_avg, V2_avg = average_data(
            time_array, T1_array, T2_array, V1_array, V2_array
        )
        
        DT_avg = T1_avg - T2_avg
        
        # Save averaged data
        data_avg = np.column_stack([DT_avg, T1_avg, T2_avg, V1_avg, V2_avg, t_avg])
        headers_avg = ['DT_Bttm_av', 'T1_av', 'T2_av', 'V1_av', 'V2_av', 't_av']
        save_to_csv(f'{filename}-avg.csv', data_avg, headers_avg, output_folder)
        
        # Calculate Seebeck coefficient
        T_avg = np.mean([np.mean(T1_avg), np.mean(T2_avg)])
        
        slope, adj_r2, offset, rmse, S_slope = fit_v1_v2_and_calculate_seebeck(
            V1_avg, V2_avg, T_avg, plot=True
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
            'S_slope': S_slope,
            'slope': slope,
            'adj_r_square': adj_r2,
            'offset': offset,
            'rmse': rmse,
            'data_orig': data_orig,
            'data_avg': data_avg
        }
        
        return results
