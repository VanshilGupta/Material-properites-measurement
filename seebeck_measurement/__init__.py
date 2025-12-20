"""
Seebeck Coefficient Measurement Package

A Python implementation for measuring Seebeck coefficient using 
thermocouple-based differential temperature and voltage measurements.
"""

__version__ = "1.0.0"

from .measurement import SeebeckMeasurement
from .instruments import DAQController, PowerSupplyController
from .temperature_conversion import temp_to_voltage, voltage_to_temp
from .data_processing import average_data, save_to_csv
from .curve_fitting import fit_v1_v2_and_calculate_seebeck
from . import config

__all__ = [
    'SeebeckMeasurement',
    'DAQController',
    'PowerSupplyController',
    'temp_to_voltage',
    'voltage_to_temp',
    'average_data',
    'save_to_csv',
    'fit_v1_v2_and_calculate_seebeck',
    'config',
]
