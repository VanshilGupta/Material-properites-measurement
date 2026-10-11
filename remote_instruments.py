"""
Remote Instrument Client
========================
Drop-in replacements for ``DAQController`` and ``PowerSupplyController``
(and Eurotherm) that forward every call as an HTTP request to the
``instrument_server.py`` running on the lab PC.

These classes implement *exactly* the same public API as their local
counterparts so the rest of the codebase needs no changes — only the
factory in ``seebeck_measurement/instruments.py`` decides which class
to instantiate based on ``constants.REMOTE_MODE``.

Also provides ``RemoteResourceManager`` — a pyvisa-API-compatible mock
so that ``measure_sigma.py`` (which uses raw pyvisa objects) can work in
remote mode with *zero changes* to its internal logic.

No pyvisa / serial is needed on this (remote) machine.

Dependencies:
    pip install requests
"""

from __future__ import annotations

import numpy as np
import requests
from typing import List

from constants import (
    INSTRUMENT_SERVER_HOST,
    INSTRUMENT_SERVER_PORT,
    INSTRUMENT_SERVER_TOKEN,
    DAQ_RESOURCE,
    PS_RESOURCE,
    DAQ_TIMEOUT,
)
from seebeck_measurement.config import DAQ_CHANNELS


# ── HTTP helper ───────────────────────────────────────────────────────────────

class _RemoteBase:
    """
    Shared HTTP transport for all remote instrument proxies.

    Every call goes to:
        http://<host>:<port>/<prefix>/<action>

    The shared secret token is sent in the ``X-Token`` header so the
    server can verify the caller is authorised.
    """

    def __init__(self, prefix: str):
        self._base = f"http://{INSTRUMENT_SERVER_HOST}:{INSTRUMENT_SERVER_PORT}/{prefix}"
        self._headers = {"X-Token": INSTRUMENT_SERVER_TOKEN}
        # Convert DAQ timeout from ms -> seconds for the requests library
        self._req_timeout = max(DAQ_TIMEOUT / 1000 + 5, 30)

    def _get(self, path: str) -> dict:
        url = f"{self._base}/{path}"
        resp = requests.get(url, headers=self._headers, timeout=self._req_timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict = None) -> dict:
        url = f"{self._base}/{path}"
        resp = requests.post(url, headers=self._headers, json=body or {}, timeout=self._req_timeout)
        resp.raise_for_status()
        return resp.json()


# ── pyvisa-compatible mock ────────────────────────────────────────────────────
#
# measure_sigma.py uses raw pyvisa objects:
#   rm  = pyvisa.ResourceManager()
#   daq = rm.open_resource(DAQ_RESOURCE)   -> daq.write() / daq.query() / daq.close()
#   ps  = rm.open_resource(PS_RESOURCE)    -> ps.write()  / ps.query()  / ps.close()
#
# By swapping pyvisa.ResourceManager() for RemoteResourceManager() the entire
# measure_sigma.py works in remote mode without any other edits.
# ─────────────────────────────────────────────────────────────────────────────

class _RemoteResource(_RemoteBase):
    """
    Mimics a pyvisa Resource (instrument handle) but routes calls via HTTP.
    prefix is either "daq" or "ps".
    """

    def __init__(self, prefix: str, resource_string: str):
        super().__init__(prefix)
        self._resource_string = resource_string
        self._post("connect")   # ensure server-side connection is live

    # pyvisa-compatible API ---------------------------------------------------

    def write(self, command: str):
        self._post("write", {"command": command})

    def query(self, command: str) -> str:
        data = self._post("query", {"command": command})
        return data["response"]

    def close(self):
        # Intentionally no-op: keep server-side connection alive for reuse.
        # measure_sigma.py opens/closes the same instrument many times in a
        # loop; persistent connections on the server are more efficient.
        pass

    @property
    def timeout(self) -> int:
        return int(self._req_timeout * 1000)

    @timeout.setter
    def timeout(self, value: int):
        self._req_timeout = max(value / 1000 + 5, 30)


class RemoteResourceManager:
    """
    Drop-in replacement for ``pyvisa.ResourceManager`` over HTTP.

    Usage (in measure_sigma.py):
        from constants import REMOTE_MODE
        if REMOTE_MODE:
            from remote_instruments import RemoteResourceManager
            rm = RemoteResourceManager()
        else:
            import pyvisa
            rm = pyvisa.ResourceManager()
    """

    _RESOURCE_MAP = {
        DAQ_RESOURCE: "daq",
        PS_RESOURCE:  "ps",
    }

    def list_resources(self) -> tuple:
        return tuple(self._RESOURCE_MAP.keys())

    def open_resource(self, resource_string: str) -> _RemoteResource:
        prefix = self._RESOURCE_MAP.get(resource_string)
        if prefix is None:
            raise ValueError(
                f"RemoteResourceManager: unknown resource '{resource_string}'. "
                f"Known: {list(self._RESOURCE_MAP.keys())}"
            )
        return _RemoteResource(prefix, resource_string)


# ── DAQ proxy ─────────────────────────────────────────────────────────────────

class RemoteDAQController(_RemoteBase):
    """
    Remote proxy for Keithley DAQ6510.
    Same public interface as local DAQController.
    """

    def __init__(self):
        super().__init__("daq")
        self._is_connected = False

    def connect(self):
        self._post("connect")
        self._is_connected = True
        print("RemoteDAQ: connected via instrument server.")

    def disconnect(self):
        self._post("disconnect")
        self._is_connected = False
        print("RemoteDAQ: disconnected.")

    def write(self, command: str):
        self._post("write", {"command": command})

    def query(self, command: str) -> str:
        return self._post("query", {"command": command})["response"]

    def get_reference_temperatures(self) -> tuple:
        data = self._get("reference_temperatures")
        return data["t_ref1"], data["t_ref2"]

    def read_voltages(self, channels: List[int] = None) -> np.ndarray:
        data = self._post("read_voltages", {"channels": channels or DAQ_CHANNELS})
        return np.array(data["voltages"])

    def read_voltages_with_timestamps(self, channels: List[int] = None) -> dict:
        data = self._post("read_voltages_with_timestamps", {"channels": channels or DAQ_CHANNELS})
        return {
            "voltages":  np.array(data["voltages"]),
            "rel_times": np.array(data["rel_times"]),
        }


# ── Power Supply proxy ────────────────────────────────────────────────────────

class RemotePowerSupplyController(_RemoteBase):
    """
    Remote proxy for Keithley 2230-30-1 Power Supply.
    Same public interface as local PowerSupplyController.
    """

    def __init__(self):
        super().__init__("ps")
        self._is_connected = False

    def connect(self):
        self._post("connect")
        self._is_connected = True
        print("RemotePS: connected via instrument server.")

    def disconnect(self):
        self._post("disconnect")
        self._is_connected = False
        print("RemotePS: disconnected.")

    def write(self, command: str):
        self._post("write", {"command": command})

    def query(self, command: str) -> str:
        return self._post("query", {"command": command})["response"]

    def turn_off_all_channels(self):
        self._post("turn_off_all")

    def configure_heater(self, channel: int, current: float, voltage: float):
        self._post("configure_heater", {"channel": channel, "current": current, "voltage": voltage})

    def enable_heater(self, heater_num: int):
        self._post("enable_heater", {"heater_num": heater_num})


# ── Eurotherm proxy ───────────────────────────────────────────────────────────

class RemoteEurothermController(_RemoteBase):
    """
    Remote proxy for Eurotherm 2000/3000 Series temperature controller.
    Mirrors the public API of EurothermController.
    """

    def __init__(self):
        super().__init__("eurotherm")
        self._connected = False

    def connect(self) -> bool:
        self._post("connect")
        self._connected = True
        print("RemoteEurotherm: connected via instrument server.")
        return True

    def disconnect(self):
        self._post("disconnect")
        self._connected = False
        print("RemoteEurotherm: disconnected.")

    def is_connected(self) -> bool:
        """Match EurothermController.is_connected() method signature."""
        return self._connected

    def read_temperature(self) -> float | None:
        """Return current furnace temperature in Celsius, or None on failure."""
        try:
            return self._get("temperature")["temperature"]
        except Exception:
            return None

    def set_temperature(self, temperature: float):
        self._post("set_temperature", {"temperature": temperature})

    def set_ramp_rate(self, rate: float):
        self._post("set_ramp_rate", {"rate": rate})

    def set_auto_mode(self):
        self._post("set_auto_mode")
