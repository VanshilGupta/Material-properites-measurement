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


def reference_temperature_c(response: str) -> Optional[float]:
    """Cold-junction temperature (°C) for channel 111 from a REFTEMP? reply.

    ``:CAL:PROT:CARD1:REFTEMP?`` returns the card's junction sensors.
    Seebeck uses the same reply: index 4 is the junction for channel 111
    (thermocouple 2), index 1 is the other junction.
    """
    try:
        values = [float(x) for x in str(response).strip().split(",") if x.strip()]
    except (TypeError, ValueError):
        return None
    for idx in (4, 1):
        if idx < len(values) and is_valid_temperature(values[idx]) and values[idx] > 0:
            return float(values[idx])
    return None


def sample_temperature_to_record(reading, reference) -> Optional[float]:
    """Temperature (°C) to store for a channel-111 reading, or None.

    A type-K result of 0 °C is 0 mV. With the cold junction left at a
    simulated 0 °C, that is what the DAQ reports when the sample is at room
    temperature — the same temperature as the terminals. The card's
    reference-junction sensor is that temperature, so it replaces a
    non-positive reading. A failed read (no number, or an overflow) is not
    replaced: the sample is not known to be at the terminal temperature.
    """
    if not is_valid_temperature(reading):
        return None
    reading = round(float(reading), 1)
    if reading > 0:
        return reading
    if is_valid_temperature(reference):
        reference = round(float(reference), 1)
        if reference > 0:
            return reference
    return None


def _configure_sample_thermocouple(daq) -> None:
    """Channel 111 as a type-K thermocouple with the internal cold junction.

    The unqualified transducer commands are the ones this instrument already
    measures with. The channel-qualified commands, including the internal
    reference junction, are sent as well: a simulated 0 °C junction makes a
    room-temperature sample read 0 °C.
    """
    daq.write("ROUT:SCAN (@111)")
    daq.write('SENS:FUNC "TEMP", (@111)')
    daq.write("SENS:TEMP:TRAN TC")
    daq.write("SENS:TEMP:TYPE K")
    for command in (
        "SENS:TEMP:TRAN TC, (@111)",
        "SENS:TEMP:TC:TYPE K, (@111)",
        "SENS:TEMP:TC:RJUN:RSEL INT, (@111)",
    ):
        try:
            daq.write(command)
        except Exception:
            pass


def read_thermocouple_temperature(daq) -> Optional[float]:
    """One channel-111 sample temperature (°C) from an open DAQ session."""
    _configure_sample_thermocouple(daq)
    reading = float(daq.query("READ?").strip())
    reference = None
    if sample_temperature_to_record(reading, None) is None:
        try:
            reference = reference_temperature_c(
                daq.query(":CAL:PROT:CARD1:REFTEMP?")
            )
        except Exception:
            reference = None
    return sample_temperature_to_record(reading, reference)


def read_current_temperature() -> Optional[float]:
    """Read the current sample temperature from the DAQ's type-K thermocouple.

    Local mode: opens the DAQ via pyvisa, configures channel 111 as a
    type-K thermocouple, and queries one reading.

    Remote mode: forwards the request to ``instrument_server.py`` over
    HTTP.

    Returns:
        Temperature in °C, or ``None`` if the read failed or the value is
        not a plausible temperature. A 0 °C reading is not returned: it is
        replaced with the card's reference-junction temperature when that
        sensor has a real value, and dropped otherwise. Callers must handle
        ``None``: a made-up value would end up in folder names and data
        files as if it had been measured.
    """
    t = _read_daq_temperature()
    return float(t) if is_valid_temperature(t) and float(t) > 0 else None


def _read_daq_temperature():
    """Sample temperature from channel 111, or ``None`` if the read failed."""
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
            return read_thermocouple_temperature(daq)
        finally:
            daq.close()
    except Exception:
        return None
