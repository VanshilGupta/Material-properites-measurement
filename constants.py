"""Shared constants and a small temperature-reading helper.

Holds VISA resource strings, Eurotherm serial settings, sample defaults,
and the parameters used by ``measure_sigma.py``.  Seebeck-specific
parameters live in ``seebeck_measurement/config.py``.

Settings come from ``settings.ini``
-----------------------------------
Every machine-specific value below (remote mode, host/token, VISA strings,
Eurotherm COM port, sample defaults) is read from ``settings.ini`` via
``app_config`` — edit that file, not this one.  The constant *names* are
unchanged, so ``from constants import ...`` works as always.  See
``settings.example.ini`` for the documented template.

Remote Mode
-----------
``[mode] remote = true`` runs the GUI on a separate PC while the instruments
stay on the lab PC.  The lab PC must be running ``instrument_server.py``.
Point ``[remote] host`` at its LAN IP (or ``localhost`` for testing) and set
``[remote] token`` to the same value used by the server.
"""

import math
from typing import Optional

from app_config import settings as _settings

# ============================================================================
# Remote Instrument Mode
# ============================================================================

# Set True on your PC when instruments live on a remote lab PC.
REMOTE_MODE = _settings.remote_mode

# IP address (or hostname) of the lab PC running instrument_server.py.
INSTRUMENT_SERVER_HOST = _settings.remote_host

# Port the instrument server listens on.
INSTRUMENT_SERVER_PORT = _settings.remote_port

# Shared secret token — must match instrument_server.py on the lab PC.
INSTRUMENT_SERVER_TOKEN = _settings.remote_token

# ============================================================================
# Instrument Resource Strings (VISA Addresses)
# ============================================================================

# DAQ (Data Acquisition) - Keithley DAQ6510 Multimeter
DAQ_RESOURCE = _settings.daq_resource

# Power Supply - Keithley 2230-30-1 Power Supply
PS_RESOURCE = _settings.ps_resource

# ============================================================================
# Eurotherm Temperature Controller Configuration
# ============================================================================

# COM port number for Eurotherm (e.g., 5 for COM5) — tried first on connect
EUROTHERM_COM_PORT = _settings.eurotherm_com_port

# MODBUS device address (default: 1)
EUROTHERM_DEVICE_ADDRESS = _settings.eurotherm_device_address

# Serial communication settings
EUROTHERM_BAUD_RATE = _settings.eurotherm_baud_rate
EUROTHERM_TIMEOUT = _settings.eurotherm_timeout  # seconds

# Port auto-detection: if the configured COM port doesn't answer, scan every
# serial port on the PC and probe each for a Eurotherm (see eurotherm_control).
EUROTHERM_AUTO_DETECT = _settings.eurotherm_auto_detect
EUROTHERM_PROBE_TIMEOUT = _settings.eurotherm_probe_timeout  # seconds per probe

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
DEFAULT_SAMPLE_THICKNESS = _settings.default_sample_thickness_mm  # mm
DEFAULT_SAMPLE_DIAMETER = _settings.default_sample_diameter_mm  # mm

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

# Plausible range for a real furnace/thermocouple reading (°C).  Anything
# outside it is an instrument fault, e.g. an open thermocouple, for which the
# DAQ reports an overflow of 9.9e37.
TEMP_VALID_MIN_C = -50.0
TEMP_VALID_MAX_C = 1400.0


def is_valid_temperature(value) -> bool:
    """True if ``value`` is a finite reading inside the plausible range."""
    try:
        t = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(t) and TEMP_VALID_MIN_C <= t <= TEMP_VALID_MAX_C


def read_current_temperature() -> Optional[float]:
    """Read the current furnace temperature from the DAQ's type-K thermocouple.

    Local mode: opens the DAQ via pyvisa, configures channel 111 as a
    type-K thermocouple, and queries one reading.

    Remote mode: forwards the request to ``instrument_server.py`` over
    HTTP.

    Returns:
        Temperature in °C, or ``None`` if the read failed or the value is
        not a plausible temperature.  Callers must handle ``None``: a
        substitute value would end up in folder names and data files as if
        it had been measured.
    """
    t = _read_daq_temperature()
    return float(t) if is_valid_temperature(t) else None


def _read_daq_temperature():
    """Raw DAQ thermocouple reading, or ``None`` if the read failed."""
    if REMOTE_MODE:
        try:
            import requests
            url = f"http://{INSTRUMENT_SERVER_HOST}:{INSTRUMENT_SERVER_PORT}/temperature"
            resp = requests.get(
                url,
                headers={"X-Token": INSTRUMENT_SERVER_TOKEN},
                timeout=10,
            )
            resp.raise_for_status()
            return float(resp.json()["temperature"])
        except Exception:
            return None

    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        daq = rm.open_resource(DAQ_RESOURCE)
        try:
            daq.write('ROUT:SCAN (@111)')
            daq.write('SENS:FUNC "TEMP", (@111)')
            daq.write('SENS:TEMP:TRAN TC')
            daq.write('SENS:TEMP:TYPE K')
            return float(daq.query('READ?').strip())
        finally:
            daq.close()
    except Exception:
        return None
