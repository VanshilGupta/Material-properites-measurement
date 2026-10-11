# Thermoelectric Material Properties Measurement System

Python system for measuring the **Seebeck coefficient (S)** and **electrical conductivity (σ)** of thermoelectric materials, with optional **Eurotherm furnace control** for temperature-dependent sweeps.

The same measurement code can be driven three ways:

| Mode | Entry point | Use when |
|------|-------------|----------|
| **GUI** | `python run_gui.py` | Day-to-day measurements — sample setup, real-time plots, abort button |
| **Terminal** | `python run_sigma.py` / `run_seebeck.py` / `run_combined.py` | Scripted runs, headless servers, or when the GUI isn't available |
| **Simulation** | Any of the above with simulation enabled | No hardware, just test the pipeline and output files |

Optional **Remote Mode** lets the GUI run on one PC while the instruments stay on the lab PC over HTTP (see [Remote Mode](#-remote-mode)).

---

## 📁 Project Structure

```
Seeback-sigma-measurement-app/
├── constants.py                  # Shared instrument IDs, constants & helpers
├── measure_sigma.py              # Electrical conductivity (Van der Pauw)
├── run_seebeck.py                # Run Seebeck measurement (single / sweep)
├── run_sigma.py                  # Run conductivity measurement (single / sweep)
├── run_combined.py               # Run both Sigma + Seebeck vs temperature
├── run_gui.py                    # Launch the PySide6 GUI
├── eurotherm_control.py          # Eurotherm temperature controller (MODBUS RTU)
├── output_manager.py             # Folder structure & logging management
├── check_instruments.py          # Instrument diagnostics & health check
├── simulation.py                 # Simulated instruments for offline testing
├── remote_instruments.py         # HTTP-proxy classes for Remote Mode
├── instrument_server.py          # Server-side companion for Remote Mode
├── generate_logo.py              # Builds the app icon
├── personalHelper.py             # Scratch / sanity-check script (safe to delete)
├── test_eurotherm_temp.py        # Eurotherm standalone test script
├── test_remote.py                # Remote-mode connectivity test
├── requirements.txt              # Python dependencies
│
├── seebeck_measurement/          # Seebeck measurement package
│   ├── __init__.py               # Package exports
│   ├── config.py                 # Seebeck-specific configuration
│   ├── measurement.py            # SeebeckMeasurement orchestrator
│   ├── instruments.py            # DAQ & Power Supply controllers + factories
│   ├── temperature_conversion.py # ITS-90 thermocouple conversions
│   ├── data_processing.py        # CSV export
│   ├── curve_fitting.py          # V1/V2 linear fit → Seebeck coefficient
│   └── plotting.py               # Real-time matplotlib visualization
│
├── gui/                          # PySide6 GUI layer
│   ├── app.py                    # Entry point — QApplication setup
│   ├── main_window.py            # Top-level QMainWindow + signal wiring
│   ├── styles.py                 # Dark-theme stylesheet
│   ├── assets/                   # logo.png, check.svg
│   ├── backend/
│   │   ├── eurotherm_service.py  # QThread wrapper for EurothermController
│   │   └── measurement_service.py# QThread wrapper for sigma / Seebeck runs
│   └── widgets/                  # SampleInfo / MethodConfig / Temperature /
│                                 # GraphPanel / LogPanel
│
├── eurotherm/                    # Reference MATLAB scripts & Excel test data
├── logs/                         # Instrument check logs
│
└── data/                         # Output data (auto-created, one folder per sample)
    └── SampleName/
        ├── global_log.log
        ├── SampleName_Sigma_vs_Temp.csv
        ├── SampleName_Seebeck_vs_Temp.csv
        ├── SampleName_Sigma_vs_Temp.png
        ├── SampleName_Seebeck_vs_Temp.png
        ├── 28.5C/                # Decimal temperature folders (since v2.2)
        │   ├── log.log
        │   ├── Sigma/
        │   │   ├── SampleName_28.5C_sigma_results.csv
        │   │   └── SampleName_28.5C_sigma_iterations.csv
        │   └── Seebeck/
        │       ├── SampleName_28.5C_all.csv
        │       ├── SampleName_28.5C_averaged.csv
        │       └── plots/
        │           └── SampleName_28.5C_fit.png
        └── 100.0C/
            └── ...
```

---

## 🚀 Quick Start

### 1. Install Python 3.8+

Download from <https://www.python.org/downloads/>  
**Important:** Check "Add Python to PATH" during installation.

### 2. Install Dependencies

```bash
cd Material-properties-measurement
pip install -r requirements.txt
```

### 3. Install VISA Backend

Install **one** of the following for instrument communication:

| Backend | Download |
|---------|----------|
| **NI-VISA** (recommended) | <https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html> |
| Keysight IO Libraries | <https://www.keysight.com/find/iolib> |

### 4. Configure Instruments

Find your VISA resource strings:

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

Copy `settings.example.ini` to `settings.ini` and put your instrument addresses
there (VISA strings, Eurotherm COM port, remote-PC host/token).  No code edits
needed.  The Eurotherm COM port is auto-detected if the configured one doesn't
answer (`[eurotherm] auto_detect`).

### 5. Run Measurements

```bash
python run_gui.py            # GUI (recommended)
python run_seebeck.py        # Terminal: Seebeck coefficient
python run_sigma.py          # Terminal: Electrical conductivity
python run_combined.py       # Terminal: Both at each temperature
python check_instruments.py  # Verify all instruments first
```

All terminal scripts offer a **simulation mode** prompt — enter `y` to test without hardware.

---

## 🖥️ GUI Quick Start

```bash
python run_gui.py
```

The window is split into three regions:

- **Left panel** — Sample info, method (Seebeck / σ / both), temperature profile, START / ABORT
- **Right panel** — Real-time graphs: σ per iteration, T₁/T₂ vs time, V₁/V₂ vs time, V₁-vs-V₂ Seebeck fit
- **Bottom** — Live log + status bar with instrument-connection dots

Key features:

- **Testing mode** — checkbox in the Method section exposes a 1–60 min slider for the Seebeck duration (default 8 min). Useful for quick sanity checks.
- **Confirm dialog** — shows the live current temperature and the data-output path before the run starts.
- **Instant abort** — the abort button breaks the run within 0.25 s (any `time.sleep()` inside the measurement is wrapped in an abort-aware shim).
- **Per-graph buttons** — ⇓ download PNG, ↺ reset view, ⛶ maximize, ▾ collapse.

Architecture details for the GUI live in [GUI_CONTEXT.md](GUI_CONTEXT.md); a hands-on "how to change things" guide is in [UI_TECHNICAL_REFERENCE.md](UI_TECHNICAL_REFERENCE.md).

---

## 🌐 Remote Mode

When the GUI must run on a *different* PC from the instruments (e.g. your laptop on the LAN, instruments in the lab):

1. On the **lab PC** (where USB instruments are connected):

   ```bash
   pip install -r requirements.txt
   python instrument_server.py
   ```

2. In `constants.py`, on **your PC**:

   ```python
   REMOTE_MODE = True
   INSTRUMENT_SERVER_HOST  = "192.168.x.x"   # lab PC LAN IP
   INSTRUMENT_SERVER_PORT  = 8765
   INSTRUMENT_SERVER_TOKEN = "vg@123"        # must match lab PC
   ```

3. Run `python run_gui.py` (or any terminal entry point) on your PC.

`remote_instruments.py` transparently swaps the local `pyvisa.ResourceManager` / `DAQController` / `EurothermController` for HTTP-proxy classes — the rest of the codebase doesn't know the difference.

Verify connectivity first with `python test_remote.py`.

---

## 🌡️ Temperature Sweep Mode

All run scripts support **Eurotherm temperature control** for measuring properties as a function of temperature.

### Usage Flow

1. Run any measurement script
2. When prompted "Enable Eurotherm Temperature Control?", enter `y`
3. Enter temperature range (start, end, step, ramp rate)
4. Confirm and start measurement

### Example Session

```
SEEBECK COEFFICIENT MEASUREMENT SYSTEM
============================================================
Enable SIMULATION mode? (y/n) [default: n]: n
Enter sample name (default: SN2517): MySample

Enable Eurotherm Temperature Control? (y/n) [default: n]: y

--- Temperature Sweep Configuration ---
Start temperature (°C) [default: 50]: 50
End temperature (°C) [default: 200]: 200
Temperature step (°C) [default: 25]: 50
Ramp rate (°C/min) [default: 10]: 5

Temperature points: [50.0, 100.0, 150.0, 200.0]
Proceed with temperature sweep? (y/n) [default: y]: y
```

---

## ⚙️ Configuration

### Shared Constants — `constants.py`

All instrument addresses and measurement parameters are centralized here:

```python
# VISA Addresses
DAQ_RESOURCE = 'USB0::0x05E6::0x6510::04619482::0::INSTR'
PS_RESOURCE  = 'USB0::0x05E6::0x2230::805224014787570003::0::INSTR'

# Eurotherm
EUROTHERM_COM_PORT = 5       # COM5
EUROTHERM_BAUD_RATE = 9600
EUROTHERM_DEVICE_ADDRESS = 1

# Sigma Measurement
DEFAULT_SAMPLE_THICKNESS = 2.1  # mm
DEFAULT_SAMPLE_DIAMETER  = 15   # mm
KNOWN_RESISTOR = 0.1029         # Ω
SIGMA_PS_VOLTAGE = 0.5          # V

# Temperature Stability
EUROTHERM_STABILITY_TOLERANCE = 1.0   # °C
EUROTHERM_STABILITY_TIME      = 60    # seconds
EUROTHERM_STABILITY_TIMEOUT   = 1800  # 30 min max
```

Also provides a shared `read_current_temperature()` helper that reads DAQ thermocouple channel 111.

### Seebeck-Specific — `seebeck_measurement/config.py`

```python
DEFAULT_MEASUREMENT_TIME = 480  # 8 minutes
HEATER_CURRENT = 0.3            # A
HEATER_VOLTAGE = 10.0           # V
DAQ_CHANNELS = [101, 106, 111, 116, 111, 106, 101]
```

---

## 📊 Measurements

### Seebeck Coefficient

Measures thermoelectric voltage response to a temperature gradient.

| Property | Value |
|----------|-------|
| **Instruments** | Keithley DAQ6510 + Keithley 2230-30-1 |
| **Method** | Dual gradient heater, V2-vs-V1 linear regression |
| **Duration** | ~8 min per temperature point |
| **Output** | Seebeck coefficient (µV/K), raw & averaged CSVs, fit plot |

### Electrical Conductivity (σ)

Measures electrical conductivity using the Van der Pauw four-point method.

| Property | Value |
|----------|-------|
| **Instruments** | Keithley DAQ6510 + Keithley 2230-30-1 |
| **Method** | Van der Pauw with matrix relay switching |
| **Duration** | ~80–90 seconds per temperature point |
| **Output** | σ (S/cm), resistivity (Ω·cm), CSV results |

**Safety:** Matrix relays are never switched while current is flowing.

### Combined Measurement (`run_combined.py`)

Runs both sigma and Seebeck at each temperature point:
1. Sigma measurement → 2. Safety pause → 3. Seebeck measurement

---

## 💻 Programmatic Usage

### Seebeck

```python
from seebeck_measurement import SeebeckMeasurement

measurement = SeebeckMeasurement(enable_plotting=True)
results = measurement.run_measurement(filename="MySample", measurement_time=480)
print(f"Seebeck: {results['S_slope']:.2f} µV/K")
```

### Conductivity

```python
from measure_sigma import measure_sigma

results = measure_sigma(sample_t=2.1, sample_dia=15, verbose=True)
if results:
    print(f"σ = {results['corr_sigma']:.2f} S/cm")
```

---

## 🔧 Simulation Mode

Every run script supports simulation mode for testing without physical instruments:

```
Enable SIMULATION mode? (y/n) [default: n]: y
```

Uses `simulation.py` to generate realistic noisy data, create plots, and save CSVs — identical workflow to real measurements.

---

## 🔌 Eurotherm Controller

Eurotherm 2000/3000 series via **MODBUS RTU** over RS-232.

| Setting | Value |
|---------|-------|
| Serial port | COM5 (configurable) |
| Baud rate | 9600, 8N1 |
| MODBUS address | 1 |

### MODBUS Registers

| Parameter | Register | Description |
|-----------|----------|-------------|
| PV | 1 | Process Value (current temp) |
| SP | 2 | Setpoint |
| Output | 3 | Heater output % |
| Ramp Rate | 35 | °C/min |
| Auto/Manual | 273 | 0 = Auto, 1 = Manual |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Cannot find instruments | Install NI-VISA, check USB, verify `constants.py` addresses |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `brentq failed` warning | Check sample contacts; code falls back to initial guess |
| Eurotherm not responding | Check COM port in Device Manager, verify baud rate |

---

## 📚 Technical Details

### Seebeck Coefficient

```
S_sample = (1 / (1 - m)) × S_TC + S_Alumel
```

Where `m` = V1–V2 slope, `S_TC = S_Chromel - S_Alumel` from temperature-dependent polynomials (ITS-90).

### Van der Pauw Equation

```
exp(-π·R₁·d/ρ) + exp(-π·R₂·d/ρ) = 1
```

Solved using `scipy.optimize.brentq`. Geometry correction applied for finite sample size.

---

## 📦 Dependencies

```
pyvisa>=1.14.0        # VISA communication
pyvisa-py>=0.7.1      # Pure-Python VISA backend
numpy>=1.24.0         # Numerical computing
scipy>=1.11.0         # Root-finding (brentq)
matplotlib>=3.7.0     # Plotting
pandas>=2.0.0         # Data export
openpyxl>=3.1.0       # Excel export
pyserial>=3.5         # Eurotherm serial
```

---

## 📋 Changelog

### v2.3.0 (May 2026)
- **Fixed:** `measure_sigma.py` referenced `pyvisa.VisaIOError` without importing pyvisa — would have raised `NameError` on VISA failures in remote mode. Now uses a safe alias that degrades to a placeholder when pyvisa isn't installed.
- **Fixed:** `seebeck_measurement/plotting.py::save_plot()` blocked the program for 5 seconds with no purpose. Removed.
- **Cleaned:** Unused imports (`VDP_TOLERANCE`, `average_data`, stray `time` in plotting, dead `MEASUREMENT_TIME` alias).
- **Cleaned:** Stray blank line inside the `DAQ_CHANNELS` list and inconsistent spacing on `HEATER_ON_DURATION`.
- **Polished:** Docstrings on `constants.py`, `measure_sigma.py`, `personalHelper.py`.

### v2.2.0 (March 2026)
- **GUI release** — PySide6 desktop app (`run_gui.py`) with real-time plots, abort button, testing mode, per-graph download/reset/collapse controls.
- **Remote Mode** — Run the GUI on one PC while instruments stay on the lab PC over HTTP (`instrument_server.py`, `remote_instruments.py`).
- **Decimal folder naming** — output folders now use `{temp:.1f}C` (e.g. `28.5C`) instead of integer rounding.
- **Per-iteration sigma CSV** — new `SampleName_{T}C_sigma_iterations.csv` with V1–V4, ΔV, R, σ per iteration.
- **All 3 Seebeck plots saved** — time-series T, time-series V, and V₁-vs-V₂ fit.

### v2.1.0 (February 2025)
- **Refactored:** Debug prints in `eurotherm_control.py` → structured logger calls.
- **Refactored:** Extracted `_measure_vdp_voltage()` helper in `measure_sigma.py` — eliminated 4× code duplication.
- **Refactored:** Shared `read_current_temperature()` in `constants.py`.
- **Refactored:** `run_combined.py` imports save functions from `run_sigma`/`run_seebeck` instead of duplicating.
- **Cleaned:** Duplicate `requirements.txt` entries, `sys.path` hacks, log headers, inline imports.

### v2.0.0 (January 2025)
- Eurotherm temperature controller integration.
- Temperature sweep for all measurements.
- `run_combined.py` for Sigma + Seebeck vs temperature.
- Hierarchical folder structure with per-temperature logging.
- Simulation mode and `check_instruments.py` diagnostic tool.

### v1.0.0 (December 2024)
- Initial release: Seebeck + Van der Pauw conductivity.

---

**Author:** VanshilGupta  
**Repository:** [Material-properites-measurement](https://github.com/VanshilGupta/Material-properites-measurement)  
**Version:** 2.3.0 | **Last Updated:** May 2026

For a detailed technical guide explaining every module, instrument, and SCPI command, see **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)**.  
For GUI architecture, see **[GUI_CONTEXT.md](GUI_CONTEXT.md)** and **[UI_TECHNICAL_REFERENCE.md](UI_TECHNICAL_REFERENCE.md)**.
