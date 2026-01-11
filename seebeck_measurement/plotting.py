"""Real-time plotting for Seebeck measurements."""

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
from typing import Optional


class SeebeckPlotter:
    """Real-time plotter for temperature and voltage data."""
    
    def __init__(self):
        """Initialize plotter with empty figure."""
        self.fig, (self.ax_temp, self.ax_volt) = plt.subplots(2, 1, figsize=(10, 8))
        self.fig.canvas.manager.set_window_title('Seebeck Measurement')
        
        # Data storage
        self.t1_data, self.T1_data = [], []
        self.t2_data, self.T2_data = [], []
        self.t3_data, self.V1_data = [], []
        self.t4_data, self.V2_data = [], []
        
        # Initialize plot lines
        self.line_T1, = self.ax_temp.plot([], [], 'ro-', markersize=3, label='T1')
        self.line_T2, = self.ax_temp.plot([], [], 'bo-', markersize=3, label='T2')
        self.line_V1, = self.ax_volt.plot([], [], 'ro-', markersize=3, label='V1')
        self.line_V2, = self.ax_volt.plot([], [], 'bo-', markersize=3, label='V2')
        
        # Setup axes
        self.ax_temp.set_xlabel('Time (minutes)')
        self.ax_temp.set_ylabel('Temperature (°C)')
        self.ax_temp.legend(loc='southwest')
        self.ax_temp.grid(True)
        
        self.ax_volt.set_xlabel('Time (minutes)')
        self.ax_volt.set_ylabel('Voltage (µV)')
        self.ax_volt.legend(loc='best')
        self.ax_volt.grid(True)
        
        plt.tight_layout()
        plt.ion()
        plt.show()
    
    def update(
        self,
        time: float,
        T1: float,
        T2: float,
        V1: float,
        V2: float
    ):
        """
        Update plot with new data point.
        
        Args:
            time: Time in seconds
            T1, T2: Temperatures in Celsius
            V1, V2: Voltages in Volts
        """
        time_min = time / 60.0
        
        # Append data
        self.t1_data.append(time_min)
        self.T1_data.append(T1)
        self.t2_data.append(time_min)
        self.T2_data.append(T2)
        self.t3_data.append(time_min)
        self.V1_data.append(V1 * 1e6)  # Convert to µV
        self.t4_data.append(time_min)
        self.V2_data.append(V2 * 1e6)  # Convert to µV
        
        # Update line data
        self.line_T1.set_data(self.t1_data, self.T1_data)
        self.line_T2.set_data(self.t2_data, self.T2_data)
        self.line_V1.set_data(self.t3_data, self.V1_data)
        self.line_V2.set_data(self.t4_data, self.V2_data)
        
        # Rescale axes
        self.ax_temp.relim()
        self.ax_temp.autoscale_view()
        self.ax_volt.relim()
        self.ax_volt.autoscale_view()
        
        # Redraw
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.pause(0.001)
    
    def save_plot(self, filename: str, output_folder: str = None):
        """
        Save the current plot to file.
        
        Args:
            filename: Base filename (without extension)
            output_folder: Output directory (the sample folder where all data goes)
        """
        
        
        # Hold the final plot for 5 seconds before saving and closing
        time.sleep(5)
        
        if output_folder is None:
            # Default to seebeck_data/plots/ folder next to the code files (legacy behavior)
            code_dir = Path(__file__).parent.parent
            output_folder = code_dir / 'seebeck_data' / 'plots'
        else:
            # Use the provided folder directly (sample folder)
            output_folder = Path(output_folder)
        
        output_folder.mkdir(parents=True, exist_ok=True)
        
        filepath = output_folder / f'{filename}_realtime.png'
        self.fig.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"💾 Real-time plot saved: {filepath}")
    
    def close(self):
        """Close the plot."""
        plt.close(self.fig)
