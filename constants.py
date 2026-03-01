"""Shared Constants for Both Seebeck and Sigma Measurements.

Instrument IDs and resource strings that are common to both measurement types.
Each measurement type has its own specific constants in their respective files:
- Sigma-specific: This file (constants.py)
- Seebeck-specific: seebeck_measurement/config.py

Remote Mode
-----------
Set REMOTE_MODE = True when running the GUI on *your PC* while the
instruments are physically connected to the *lab PC*.

The lab PC must be running ``instrument_server.py``.
Point INSTRUMENT_SERVER_HOST at its LAN IP (or "localhost" for testing).
Set INSTRUMENT_SERVER_TOKEN to the same value as on the server.
"""

# ============================================================================
# Remote Instrument Mode
# ============================================================================

# Set True on your PC when instruments live on a remote lab PC.
REMOTE_MODE = False

# IP address (or hostname) of the lab PC running instrument_server.py.
INSTRUMENT_SERVER_HOST = "192.168.1.100"

# Port the instrument server listens on.
INSTRUMENT_SERVER_PORT = 8765

# Shared secret token — must match instrument_server.py on the lab PC.
INSTRUMENT_SERVER_TOKEN = "seebeck-lab-token-change-me"

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


# ============================================================================
# Shared Helpers
# ============================================================================

def read_current_temperature() -> float:
    """
    Read the current temperature from the DAQ thermocouple channel.

    In REMOTE_MODE the request is forwarded to the instrument server
    running on the lab PC.  In local mode the DAQ is queried directly
    via pyvisa.

    Returns:
        Temperature in °C (defaults to 25.0 if reading fails).
    """
    if REMOTE_MODE:
        try:
            import requests
            url = f"http://{INSTRUMENT_SERVER_HOST}:{INSTRUMENT_SERVER_PORT}/temperature"
            resp = requests.get(url, headers={"X-Token": INSTRUMENT_SERVER_TOKEN}, timeout=10)
            resp.raise_for_status()
            return float(resp.json()["temperature"])
        except Exception:
            return 25.0
    else:
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            daq = rm.open_resource(DAQ_RESOURCE)
            daq.write('ROUT:SCAN (@111)')
            daq.write('SENS:FUNC "TEMP", (@111)')
            daq.write('SENS:TEMP:TRAN TC')
            daq.write('SENS:TEMP:TYPE K')
            temp = float(daq.query('READ?').strip())
            daq.close()
            return temp
        except Exception:
            return 25.0
