# Thermoelectric Material Properties Measurement System

Complete Python system for measuring **Seebeck coefficient** and **electrical conductivity (σ)** of thermoelectric materials using the Van der Pauw method. Includes **Eurotherm temperature controller integration** for temperature-dependent measurements and a full **simulation mode** for testing without hardware.

---

## 📁 Project Structure

```
Material-properties-measurement/
├── constants.py                  # Shared instrument IDs, constants & helpers
├── measure_sigma.py              # Electrical conductivity (Van der Pauw)
├── run_seebeck.py                # Run Seebeck measurement (single / sweep)
├── run_sigma.py                  # Run conductivity measurement (single / sweep)
├── run_combined.py               # Run both Sigma + Seebeck vs temperature
├── eurotherm_control.py          # Eurotherm temperature controller (MODBUS RTU)
├── output_manager.py             # Folder structure & logging management
├── check_instruments.py          # Instrument diagnostics & health check
├── simulation.py                 # Simulated instruments for offline testing
├── test_eurotherm_temp.py        # Eurotherm standalone test script
├── requirements.txt              # Python dependencies
│
├── seebeck_measurement/          # Seebeck measurement package
│   ├── __init__.py               # Package exports
│   ├── config.py                 # Seebeck-specific configuration
│   ├── measurement.py            # Main measurement orchestration
│   ├── instruments.py            # DAQ & Power Supply hardware control
│   ├── temperature_conversion.py # ITS-90 thermocouple conversions
│   ├── data_processing.py        # Data averaging & CSV export
│   ├── curve_fitting.py          # Seebeck coefficient calculation
│   └── plotting.py               # Real-time visualization
│
├── logs/                         # Instrument check logs
│
└── data/                         # Output data (auto-created)
    └── SampleName/
        ├── global_log.log
        ├── SampleName_Sigma_vs_Temp.csv
        ├── SampleName_Seebeck_vs_Temp.csv
        ├── SampleName_Sigma_vs_Temp.png
        ├── SampleName_Seebeck_vs_Temp.png
        ├── 100C/
        │   ├── log.log
        │   ├── Sigma/
        │   │   └── SampleName_100C_sigma_results.csv
        │   └── Seebeck/
        │       ├── SampleName_100C_all.csv
        │       ├── SampleName_100C_averaged.csv
        │       └── plots/
        │           └── SampleName_100C_fit.png
        └── 150C/
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

Update `constants.py` with your instrument addresses.

### 5. Run Measurements

```bash
python run_seebeck.py        # Seebeck coefficient
python run_sigma.py          # Electrical conductivity
python run_combined.py       # Both at each temperature
python check_instruments.py  # Verify all instruments first
```

All scripts offer **simulation mode** — enter `y` when prompted to test without hardware.

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

### v2.1.0 (February 2025)
- **Refactored:** Debug prints in `eurotherm_control.py` → structured logger calls
- **Refactored:** Extracted `_measure_vdp_voltage()` helper in `measure_sigma.py` — eliminated 4× code duplication
- **Refactored:** Shared `read_current_temperature()` in `constants.py` — eliminated DAQ temp reading duplication across 3 scripts
- **Refactored:** `run_combined.py` imports save functions from `run_sigma`/`run_seebeck` instead of duplicating
- **Cleaned:** Duplicate entries in `requirements.txt`, `sys.path` hacks, log headers, inline imports

### v2.0.0 (January 2025)
- Eurotherm temperature controller integration
- Temperature sweep for all measurements
- `run_combined.py` for Sigma + Seebeck vs temperature
- Hierarchical folder structure with per-temperature logging
- Simulation mode, `check_instruments.py` diagnostic tool

### v1.0.0 (December 2024)
- Initial release: Seebeck + Van der Pauw conductivity

---

**Author:** VanshilGupta  
**Repository:** [Material-properites-measurement](https://github.com/VanshilGupta/Material-properites-measurement)  
**Version:** 2.1.0 | **Last Updated:** February 2025

For a detailed technical guide explaining every module, instrument, and SCPI command, see **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)**.
