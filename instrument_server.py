"""
Instrument Server — Lab PC side
================================
Runs on the machine that has the physical instruments attached.

Exposes a lightweight HTTP API so that a remote PC running the GUI
can read/write instruments without UltraViewer or NI-VISA-Server.

Usage (on the lab PC):
    python instrument_server.py

Then on your PC set in settings.ini (see settings.example.ini):
    [mode]    remote = true
    [remote]  host = <lab-PC-LAN-IP>
              port = 8765
              token = <shared secret>   # must match the token this server expects

The VISA strings and the Eurotherm COM port are read from the settings.ini on
THIS (lab) PC; with [eurotherm] auto_detect = true the server scans for the
Eurotherm if the configured COM port does not answer.

Security
--------
A static shared token in the ``X-Token`` header is checked on every
request.  Change TOKEN to a long random string before using on a
shared network.  For additional security, tunnel through SSH:
    ssh -L 8765:localhost:8765 user@lab-pc   (on your PC)
then set INSTRUMENT_SERVER_HOST = "localhost".

Dependencies (install on lab PC):
    pip install fastapi uvicorn
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── project imports ──────────────────────────────────────────────────────────
import pathlib
_root = str(pathlib.Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from constants import (
    DAQ_RESOURCE, PS_RESOURCE, DAQ_TIMEOUT,
    EUROTHERM_COM_PORT, EUROTHERM_DEVICE_ADDRESS,
    EUROTHERM_BAUD_RATE, EUROTHERM_TIMEOUT,
    INSTRUMENT_SERVER_PORT, INSTRUMENT_SERVER_TOKEN,
)
from seebeck_measurement.instruments import DAQController, PowerSupplyController
from eurotherm_control import EurothermController

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("instrument_server")

# ── shared token ─────────────────────────────────────────────────────────────
TOKEN = INSTRUMENT_SERVER_TOKEN   # set [remote] token in settings.ini


# ─── Global instrument state ─────────────────────────────────────────────────

class _State:
    """Singleton that holds live instrument connections."""
    daq:        DAQController | None       = None
    ps:         PowerSupplyController | None = None
    eurotherm:  EurothermController | None = None

state = _State()


# ─── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Instrument Server starting — waiting for /connect calls.")
    log.info("=" * 60)
    yield
    # Cleanup on shutdown
    for name, inst in [("DAQ", state.daq), ("PS", state.ps), ("Eurotherm", state.eurotherm)]:
        if inst is not None:
            try:
                inst.disconnect()
                log.info(f"{name} disconnected on shutdown.")
            except Exception as exc:
                log.warning(f"{name} disconnect on shutdown failed: {exc}")


app = FastAPI(
    title="Instrument Server",
    description="Remote VISA/Serial proxy for lab instruments.",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Auth dependency ──────────────────────────────────────────────────────────

def verify_token(x_token: str = Header(...)):
    if x_token != TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token.")


# ─── Pydantic models ──────────────────────────────────────────────────────────

class WriteCmd(BaseModel):
    command: str

class QueryCmd(BaseModel):
    command: str

class ConfigureHeaterCmd(BaseModel):
    channel:    int
    current:    float
    voltage:    float

class EnableHeaterCmd(BaseModel):
    heater_num: int

class SetTemperatureCmd(BaseModel):
    temperature: float

class SetRampRateCmd(BaseModel):
    rate: float


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ok(data: Dict[str, Any] = None) -> JSONResponse:
    return JSONResponse({"status": "ok", **(data or {})})

def _require_daq():
    if state.daq is None or not state.daq._is_connected:
        raise HTTPException(400, "DAQ not connected. Call POST /daq/connect first.")
    return state.daq

def _require_ps():
    if state.ps is None or not state.ps._is_connected:
        raise HTTPException(400, "Power Supply not connected. Call POST /ps/connect first.")
    return state.ps

def _require_eurotherm():
    if state.eurotherm is None or not state.eurotherm.is_connected():
        raise HTTPException(400, "Eurotherm not connected. Call POST /eurotherm/connect first.")
    return state.eurotherm


# ═══════════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", dependencies=[Depends(verify_token)])
def health():
    return {
        "status": "ok",
        "daq_connected":       state.daq is not None and state.daq._is_connected,
        "ps_connected":        state.ps  is not None and state.ps._is_connected,
        "eurotherm_connected": state.eurotherm is not None and state.eurotherm.is_connected(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Quick temperature read (no persistent connection needed)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/temperature", dependencies=[Depends(verify_token)])
def get_temperature():
    """Read current thermocouple temperature from DAQ channel 111."""
    # Use persistent DAQ if connected, else open fresh connection
    try:
        if state.daq and state.daq._is_connected:
            daq = state.daq
            daq.write('ROUT:SCAN (@111)')
            daq.write('SENS:FUNC "TEMP", (@111)')
            daq.write('SENS:TEMP:TRAN TC')
            daq.write('SENS:TEMP:TYPE K')
            temp = float(daq.query('READ?').strip())
        else:
            import pyvisa
            rm = pyvisa.ResourceManager()
            inst = rm.open_resource(DAQ_RESOURCE)
            inst.timeout = DAQ_TIMEOUT
            inst.write('ROUT:SCAN (@111)')
            inst.write('SENS:FUNC "TEMP", (@111)')
            inst.write('SENS:TEMP:TRAN TC')
            inst.write('SENS:TEMP:TYPE K')
            temp = float(inst.query('READ?').strip())
            inst.close()
        return {"temperature": temp}
    except Exception as exc:
        raise HTTPException(500, f"Temperature read failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# DAQ (Data Acquisition — Keithley DAQ6510)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/daq/connect", dependencies=[Depends(verify_token)])
def daq_connect():
    if state.daq is None:
        state.daq = DAQController()
    if not state.daq._is_connected:
        state.daq.connect()
    return _ok({"resource": state.daq.resource_string})


@app.post("/daq/disconnect", dependencies=[Depends(verify_token)])
def daq_disconnect():
    if state.daq and state.daq._is_connected:
        state.daq.disconnect()
    return _ok()


@app.post("/daq/write", dependencies=[Depends(verify_token)])
def daq_write(body: WriteCmd):
    _require_daq().write(body.command)
    return _ok()


@app.post("/daq/query", dependencies=[Depends(verify_token)])
def daq_query(body: QueryCmd):
    response = _require_daq().query(body.command)
    return _ok({"response": response})


@app.get("/daq/reference_temperatures", dependencies=[Depends(verify_token)])
def daq_ref_temps():
    t_ref1, t_ref2 = _require_daq().get_reference_temperatures()
    return _ok({"t_ref1": t_ref1, "t_ref2": t_ref2})


@app.post("/daq/read_voltages", dependencies=[Depends(verify_token)])
def daq_read_voltages(body: Dict[str, Any] = None):
    """Read voltages from DAQ. Optional JSON body: {"channels": [101, 106, ...]}"""
    from seebeck_measurement.config import DAQ_CHANNELS
    channels = (body or {}).get("channels", DAQ_CHANNELS)
    result = _require_daq().read_voltages(channels)
    return _ok({"voltages": result.tolist()})


@app.post("/daq/read_voltages_with_timestamps", dependencies=[Depends(verify_token)])
def daq_read_voltages_ts(body: Dict[str, Any] = None):
    """Read voltages + relative timestamps. Optional body: {"channels": [...]}"""
    from seebeck_measurement.config import DAQ_CHANNELS
    channels = (body or {}).get("channels", DAQ_CHANNELS)
    result = _require_daq().read_voltages_with_timestamps(channels)
    return _ok({
        "voltages":   result["voltages"].tolist(),
        "rel_times":  result["rel_times"].tolist(),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Power Supply (Keithley 2230-30-1)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/ps/connect", dependencies=[Depends(verify_token)])
def ps_connect():
    if state.ps is None:
        state.ps = PowerSupplyController()
    if not state.ps._is_connected:
        state.ps.connect()
    return _ok({"resource": state.ps.resource_string})


@app.post("/ps/disconnect", dependencies=[Depends(verify_token)])
def ps_disconnect():
    if state.ps and state.ps._is_connected:
        state.ps.disconnect()
    return _ok()


@app.post("/ps/write", dependencies=[Depends(verify_token)])
def ps_write(body: WriteCmd):
    _require_ps().write(body.command)
    return _ok()


@app.post("/ps/query", dependencies=[Depends(verify_token)])
def ps_query(body: QueryCmd):
    response = _require_ps().query(body.command)
    return _ok({"response": response})


@app.post("/ps/turn_off_all", dependencies=[Depends(verify_token)])
def ps_turn_off_all():
    _require_ps().turn_off_all_channels()
    return _ok()


@app.post("/ps/configure_heater", dependencies=[Depends(verify_token)])
def ps_configure_heater(body: ConfigureHeaterCmd):
    _require_ps().configure_heater(body.channel, body.current, body.voltage)
    return _ok()


@app.post("/ps/enable_heater", dependencies=[Depends(verify_token)])
def ps_enable_heater(body: EnableHeaterCmd):
    _require_ps().enable_heater(body.heater_num)
    return _ok()


# ═══════════════════════════════════════════════════════════════════════════════
# Eurotherm Temperature Controller
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/eurotherm/connect", dependencies=[Depends(verify_token)])
def eurotherm_connect():
    if state.eurotherm is None:
        state.eurotherm = EurothermController(
            com_port=EUROTHERM_COM_PORT,
            device_address=EUROTHERM_DEVICE_ADDRESS,
            baud_rate=EUROTHERM_BAUD_RATE,
            timeout=EUROTHERM_TIMEOUT,
        )
    if not state.eurotherm.is_connected():
        ok = state.eurotherm.connect()
        if not ok:
            raise HTTPException(
                500,
                f"Eurotherm failed to connect (configured COM{EUROTHERM_COM_PORT}, "
                f"auto-detect {'on' if state.eurotherm.auto_detect else 'off'}). "
                "Check cable/port and the server log.",
            )
    # Report the port actually in use — auto-detect may have moved it.
    return _ok({"com_port": state.eurotherm.com_port})


@app.post("/eurotherm/disconnect", dependencies=[Depends(verify_token)])
def eurotherm_disconnect():
    if state.eurotherm and state.eurotherm.is_connected():
        state.eurotherm.disconnect()
    return _ok()


@app.get("/eurotherm/temperature", dependencies=[Depends(verify_token)])
def eurotherm_temperature():
    temp = _require_eurotherm().read_temperature()
    if temp is None:
        raise HTTPException(500, "Eurotherm returned no temperature value.")
    return _ok({"temperature": temp})


@app.post("/eurotherm/set_temperature", dependencies=[Depends(verify_token)])
def eurotherm_set_temperature(body: SetTemperatureCmd):
    _require_eurotherm().set_temperature(body.temperature)
    return _ok()


@app.post("/eurotherm/set_ramp_rate", dependencies=[Depends(verify_token)])
def eurotherm_set_ramp_rate(body: SetRampRateCmd):
    _require_eurotherm().set_ramp_rate(body.rate)
    return _ok()


@app.post("/eurotherm/set_auto_mode", dependencies=[Depends(verify_token)])
def eurotherm_set_auto_mode():
    _require_eurotherm().set_auto_mode()
    return _ok()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Instrument Server for remote instrument control.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0 = all interfaces)")
    parser.add_argument("--port", type=int, default=INSTRUMENT_SERVER_PORT, help=f"Port (default: {INSTRUMENT_SERVER_PORT})")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  Instrument Server")
    print(f"  Listening on  http://{args.host}:{args.port}")
    print(f"  Token         {TOKEN[:8]}... (set [remote] token in settings.ini)")
    print(f"{'=' * 60}\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
