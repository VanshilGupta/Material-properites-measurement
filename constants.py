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
# Instrument Vendor and Product IDs
# ============================================================================

# DAQ6510 Multimeter
DAQ_VENDOR_ID = 0x05E6
DAQ_PRODUCT_ID = 0x6510
DAQ_SERIAL = '04619482'

# Keithley 2230-30-1 Power Supply
PS_VENDOR_ID = 0x05E6
PS_PRODUCT_ID = 0x2230
PS_SERIAL = '805224014787570003'

# ============================================================================
# Sigma (Conductivity) Measurement - Van der Pauw
# ============================================================================

# Default sample dimensions
DEFAULT_SAMPLE_THICKNESS = 2.3  # mm
DEFAULT_SAMPLE_DIAMETER = 12.65  # mm

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
