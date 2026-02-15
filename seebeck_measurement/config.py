"""
Configuration file for Seebeck measurements.

Seebeck-specific measurement parameters and configurations.
Shared instrument constants are imported from the root constants.py file.

Modify parameters here to customize measurement behavior.
"""

# Import shared instrument constants from root
import sys
from pathlib import Path

# Ensure root project directory is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from constants import (
    DAQ_RESOURCE, 
    PS_RESOURCE, 
    DAQ_TIMEOUT,
    DAQ_NPLC,
    DAQ_VOLTAGE_RANGE
)

# ============================================================================
# Measurement Parameters - Seebeck Specific
# ============================================================================

# Total measurement duration (seconds)
DEFAULT_MEASUREMENT_TIME = 480  # 8 minutes
MEASUREMENT_TIME = DEFAULT_MEASUREMENT_TIME  # Backwards compatibility

# Maximum temperature difference threshold (°C)
MAX_TEMP_DIFFERENCE = 8.0

# Maximum number of data points
MAX_SAMPLES = 500

# ============================================================================
# Heater Control Parameters
# ============================================================================

# Gradient heater current (Amps)
HEATER_CURRENT = 0.3

# Gradient heater voltage limit (Volts)
HEATER_VOLTAGE = 10.0

# Heater ON duration at start (seconds)
HEATER_ON_DURATION= 60


# ============================================================================
# DAQ Configuration - Seebeck Specific
# ============================================================================

# Channel mapping for voltage readings
# Order: [U1_1, V1_1, U2_1, V2_1, U2_2, V1_2, U1_2]
DAQ_CHANNELS = [101, 106, 

111, 116, 111, 106, 101]

# Note: DAQ_NPLC, DAQ_VOLTAGE_RANGE, and DAQ_TIMEOUT are imported from root constants.py

# ============================================================================
# Data Storage
# ============================================================================

# Default output folder (None = ~/seebeck_data/)
OUTPUT_FOLDER = None

# ============================================================================
# Plotting Configuration
# ============================================================================

# Enable real-time plotting
ENABLE_PLOTTING = True

# Plot update interval (seconds)
PLOT_UPDATE_INTERVAL = 0.1

# Figure size (width, height in inches)
FIGURE_SIZE = (10, 8)

# ============================================================================
# Analysis Configuration
# ============================================================================

# Curve fit method ('bisquare' for robust fitting)
FIT_METHOD = 'bisquare'

