"""Shared Constants for Both Seebeck and Sigma Measurements.

Instrument IDs and resource strings that are common to both measurement types.
Each measurement type has its own specific constants in their respective files:
- Sigma-specific: This file (constants.py)
- Seebeck-specific: seebeck_measurement/config.py
"""

# ============================================================================
# Instrument Resource Strings (VISA Addresses)
# ============================================================================

# DAQ (Data Acquisition) - Keithley DAQ6510 Multimeter
DAQ_RESOURCE = 'USB0::0x05E6::0x6510::04619482::0::INSTR'

# Power Supply - Keithley 2230-30-1 Power Supply
PS_RESOURCE = 'USB0::0x05E6::0x2230::805224014787570003::0::INSTR'

# ============================================================================
# Eurotherm Temperature Controller Configuration
# ============================================================================

# COM port number for Eurotherm (e.g., 5 for COM5)
EUROTHERM_COM_PORT = 5

# MODBUS device address (default: 1)
EUROTHERM_DEVICE_ADDRESS = 1

# Serial communication settings
EUROTHERM_BAUD_RATE = 9600
EUROTHERM_TIMEOUT = 2.0  # seconds

# Temperature stabilization parameters
EUROTHERM_STABILITY_TOLERANCE = 1.0    # °C deviation allowed
EUROTHERM_STABILITY_TIME = 60.0        # seconds to hold within tolerance
EUROTHERM_STABILITY_TIMEOUT = 1800.0   # 30 min max wait time
EUROTHERM_CHECK_INTERVAL = 5.0         # seconds between temperature checks

# Default temperature sweep parameters
DEFAULT_START_TEMP = 50.0    # °C
DEFAULT_END_TEMP = 200.0     # °C
DEFAULT_TEMP_STEP = 25.0     # °C
DEFAULT_RAMP_RATE = 10.0     # °C/min

# ============================================================================
# Instrument Vendor and Product IDs
# ============================================================================


# ============================================================================
# Sigma (Conductivity) Measurement - Van der Pauw
# ============================================================================

# Default sample dimensions
DEFAULT_SAMPLE_THICKNESS = 2.1  # mm
DEFAULT_SAMPLE_DIAMETER = 15  # mm

# Known resistor value for current measurement (Ohms)
KNOWN_RESISTOR = 0.1029

# Power supply voltage for sigma measurement (Volts)
SIGMA_PS_VOLTAGE = 0.5

# Van der Pauw iteration parameters
VDP_MAX_ITERATIONS = 100
VDP_TOLERANCE = 1e-6

# Measurement current (Amps)
MEASUREMENT_CURRENT = 0.1

# Current measurement voltage limit (Volts)
CURRENT_MEASUREMENT_VOLTAGE = 5.0

# ============================================================================
# DAQ Configuration for Sigma Measurement
# ============================================================================

# DAQ timeout (milliseconds)
DAQ_TIMEOUT = 20000

# Integration time (number of power line cycles)
DAQ_NPLC = 5

# Voltage range (Volts)
DAQ_VOLTAGE_RANGE = 1.0
