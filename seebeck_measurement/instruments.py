"""Instrument communication interface for DAQ and Power Supply."""

from abc import ABC, abstractmethod
from typing import List
import numpy as np

from seebeck_measurement.config import DAQ_CHANNELS, HEATER_CURRENT, HEATER_VOLTAGE
from constants import DAQ_RESOURCE, PS_RESOURCE, DAQ_TIMEOUT, REMOTE_MODE


class InstrumentInterface(ABC):
    """Base interface for instrument communication."""
    
    @abstractmethod
    def connect(self):
        """Establish connection to instrument."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close connection to instrument."""
        pass
    
    @abstractmethod
    def write(self, command: str):
        """Send command to instrument."""
        pass
    
    @abstractmethod
    def query(self, command: str) -> str:
        """Send query and return response."""
        pass


class DAQController(InstrumentInterface):
    """
    Data Acquisition controller for reading voltages.
    
    Supports Keysight/Agilent DAQ6510 or similar VISA instruments.
    """
    
    def __init__(self, resource_string: str = None):
        """
        Initialize DAQ controller.
        
        Args:
            resource_string: VISA resource string for the instrument
        """
        self.resource_string = resource_string or DAQ_RESOURCE
        self.instrument = None
        self._is_connected = False
    
    def connect(self):
        """Connect to DAQ instrument."""
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(self.resource_string)
            self.instrument.timeout = DAQ_TIMEOUT
            self._is_connected = True
            print(f"Connected to DAQ: {self.resource_string}")
        except Exception as e:
            print(f"Failed to connect to DAQ: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from DAQ instrument."""
        if self.instrument:
            self.instrument.close()
            self._is_connected = False
            print("Disconnected from DAQ")
    
    def write(self, command: str):
        """Send command to DAQ."""
        if not self._is_connected:
            raise RuntimeError("DAQ not connected")
        self.instrument.write(command)
    
    def query(self, command: str) -> str:
        """Send query to DAQ and return response."""
        if not self._is_connected:
            raise RuntimeError("DAQ not connected")
        return self.instrument.query(command)
    
    def get_reference_temperatures(self) -> tuple:
        """
        Read reference junction temperatures.
        
        Returns:
            Tuple of (T_ref1, T_ref2) in Celsius
        """
        response = self.query(':CAL:PROT:CARD1:REFTEMP?')
        values = [float(x) for x in response.strip().split(',')]
        return values[1], values[4]  # T_ref1, T_ref2
    
    def read_voltages_with_timestamps(self, channels: List[int] = DAQ_CHANNELS) -> dict:
        """
        Read voltages from specified channels with individual timestamps.
        
        Args:
            channels: List of channel numbers (default: [101, 106, 111, 116, 111, 106, 101])
                      Order: [U1_1, V1_1, U2_1, V2, U2_2, V1_2, U1_2]
            
        Returns:
            Dictionary with 'voltages' array and 'timestamps' array
        """
        import time
        
        # Configure scan
        self.write('*RST')
        
        # Setup scan list
        channel_str = ','.join([str(ch) for ch in channels])
        self.write(f'ROUT:SCAN (@{channel_str})')
        self.write(f'SENS:FUNC "VOLT:DC", (@{channel_str})')
        self.write(f'VOLT:RANG 1, (@{channel_str})')
        self.write(f'VOLT:NPLC 5, (@{channel_str})')
        
        # Trigger measurement
        self.write('INIT')
        self.query('*OPC?')  # Wait for completion
        
        # Read data with relative timestamps from buffer
        num_readings = len(channels)
        
        # Get readings with relative time
        raw_data = self.query(f'TRAC:DATA? 1,{num_readings},"defbuffer1", READ, REL')
        values = raw_data.strip().split(',')
        voltages = []
        rel_times = []
        for i in range(0, len(values), 2):
            voltages.append(float(values[i]))
            rel_times.append(float(values[i + 1]))
        
        return {
            'voltages': np.array(voltages),
            'rel_times': np.array(rel_times)  # Relative times within this scan
        }
    
    def read_voltages(self, channels: List[int]=DAQ_CHANNELS) -> np.ndarray:
        """
        Read voltages from specified channels (legacy method).
        
        Args:
            channels: List of channel numbers (default: [101, 106, 111, 116, 111, 106, 101])
            
        Returns:
            Array of voltage readings in volts
        """
        
        # Configure scan
        self.write('*RST')
        
        # Setup scan list
        channel_str = ','.join([str(ch) for ch in channels])
        self.write(f'ROUT:SCAN (@{channel_str})')
        self.write(f'SENS:FUNC "VOLT:DC", (@{channel_str})')
        self.write(f'VOLT:RANG 1, (@{channel_str})')
        self.write(f'VOLT:NPLC 5, (@{channel_str})')
        
        # Trigger measurement
        self.write('INIT')
        self.query('*OPC?')  # Wait for completion
        
        # Read data
        num_readings = len(channels)
        raw_data = self.query(f'TRAC:DATA? 1,{num_readings},"defbuffer1", READ')
        voltages = np.array([float(x) for x in raw_data.strip().split(',')])
        
        return voltages


class PowerSupplyController(InstrumentInterface):
    """
    Power Supply controller for gradient heaters.
    
    Supports Keysight/Agilent multi-channel power supplies.
    """
    
    def __init__(self, resource_string: str = None):
        """
        Initialize power supply controller.
        
        Args:
            resource_string: VISA resource string for the instrument
        """
        self.resource_string = resource_string or PS_RESOURCE
        self.instrument = None
        self._is_connected = False
    
    def connect(self):
        """Connect to power supply."""
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(self.resource_string)
            self._is_connected = True
            print(f"Connected to Power Supply: {self.resource_string}")
        except Exception as e:
            print(f"Failed to connect to Power Supply: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from power supply."""
        if self.instrument:
            self.instrument.close()
            self._is_connected = False
            print("Disconnected from Power Supply")
    
    def write(self, command: str):
        """Send command to power supply."""
        if not self._is_connected:
            raise RuntimeError("Power supply not connected")
        self.instrument.write(command)
    
    def query(self, command: str) -> str:
        """Send query to power supply and return response."""
        if not self._is_connected:
            raise RuntimeError("Power supply not connected")
        return self.instrument.query(command)
    
    def turn_off_all_channels(self):
        """Turn off all power supply outputs."""
        self.write(':OUTP:STAT OFF')
    
    def configure_heater(self, channel: int, current: float = HEATER_CURRENT, voltage: float = 10.0):
        """
        Configure and enable a heater channel.
        
        Args:
            channel: Channel number (1, 2, or 3)
            current: Current limit in Amps
            voltage: Voltage limit in Volts
        """
        self.write(f':INST:SEL CH{channel}')
        self.write(':SOUR:FUNC:CURR')
        self.write(f':SOUR:CURR {current}')
        self.write(f':SOUR:VOLT {voltage}')
    
    def enable_heater(self, heater_num: int):
        """
        Enable specific heater (turns off others).
        
        Args:
            heater_num: Heater number (1 or 2)
        """
        self.write('*RST')
        
        if heater_num == 1:
            self.configure_heater(1, current=HEATER_CURRENT, voltage=HEATER_VOLTAGE)
            self.configure_heater(2, current=0.0, voltage=0.0)
        elif heater_num == 2:
            self.configure_heater(1, current=0.0, voltage=0.0)
            self.configure_heater(2, current=HEATER_CURRENT, voltage=HEATER_VOLTAGE)
        
        self.configure_heater(3, current=0.0, voltage=0.0)
        self.write(':OUTP:STAT ON')


# ─── Instrument Factories ────────────────────────────────────────────────────
#
# Use these functions everywhere instead of directly instantiating
# DAQController / PowerSupplyController.  When REMOTE_MODE is True in
# constants.py, the factory transparently returns the HTTP-proxy class
# (RemoteDAQController / RemotePowerSupplyController) from
# remote_instruments.py — no other code needs to change.
#
#   from seebeck_measurement.instruments import get_daq, get_power_supply
#   daq = get_daq()
#   ps  = get_power_supply()
# ─────────────────────────────────────────────────────────────────────────────

def get_daq() -> DAQController:
    """
    Return a DAQ controller appropriate for the current mode.

    - REMOTE_MODE = False → local ``DAQController`` (pyvisa, USB)
    - REMOTE_MODE = True  → ``RemoteDAQController`` (HTTP proxy)
    """
    if REMOTE_MODE:
        from remote_instruments import RemoteDAQController
        return RemoteDAQController()
    return DAQController()


def get_power_supply() -> PowerSupplyController:
    """
    Return a Power Supply controller appropriate for the current mode.

    - REMOTE_MODE = False → local ``PowerSupplyController`` (pyvisa, USB)
    - REMOTE_MODE = True  → ``RemotePowerSupplyController`` (HTTP proxy)
    """
    if REMOTE_MODE:
        from remote_instruments import RemotePowerSupplyController
        return RemotePowerSupplyController()
    return PowerSupplyController()


def get_eurotherm():
    """
    Return an Eurotherm controller appropriate for the current mode.

    - REMOTE_MODE = False → local ``EurothermController`` (serial RS-232)
    - REMOTE_MODE = True  → ``RemoteEurothermController`` (HTTP proxy)
    """
    if REMOTE_MODE:
        from remote_instruments import RemoteEurothermController
        return RemoteEurothermController()
    from eurotherm_control import EurothermController
    from constants import (
        EUROTHERM_COM_PORT, EUROTHERM_DEVICE_ADDRESS,
        EUROTHERM_BAUD_RATE, EUROTHERM_TIMEOUT,
    )
    return EurothermController(
        com_port=EUROTHERM_COM_PORT,
        device_address=EUROTHERM_DEVICE_ADDRESS,
        baud_rate=EUROTHERM_BAUD_RATE,
        timeout=EUROTHERM_TIMEOUT,
    )
