# Thermoelectric Material Properties Measurement System

Complete Python system for measuring **Seebeck coefficient** and **electrical conductivity (σ)** of thermoelectric materials using Van der Pauw method. Now with **Eurotherm temperature controller integration** for temperature-dependent measurements.

## 📁 Project Structure

```
Material-properties-measurement/
├── constants.py                  # Shared instrument IDs & all constants
├── measure_sigma.py              # Electrical conductivity measurement
├── run_seebeck.py                # Run Seebeck measurement (single or sweep)
├── run_sigma.py                  # Run conductivity measurement (single or sweep)
├── run_combined.py               # Run both Sigma + Seebeck vs temperature
├── eurotherm_control.py          # Eurotherm temperature controller module
├── output_manager.py             # Folder structure & logging management
├── requirements.txt              # Dependencies
│
├── seebeck_measurement/          # Seebeck measurement package
│   ├── __init__.py               # Package exports
│   ├── config.py                 # Seebeck-specific configuration
│   ├── measurement.py            # Main orchestration
│   ├── instruments.py            # Hardware control (DAQ, PS)
│   ├── temperature_conversion.py # Thermocouple conversions (ITS-90)
│   ├── data_processing.py        # Data averaging & CSV export
│   ├── curve_fitting.py          # Seebeck coefficient calculation
│   └── plotting.py               # Real-time visualization
│
└── data/                         # Output data folder
    └── SampleName/               # Sample-specific folder
        ├── global_log.log        # Master log for entire sweep
        ├── SampleName_Sigma_vs_Temp.csv
        ├── SampleName_Seebeck_vs_Temp.csv
        ├── 100C/                  # Temperature-specific subfolder
        │   ├── log.log
        │   ├── Sigma/
        │   └── Seebeck/
        └── 150C/
            └── ...
```

---

## 🚀 Quick Start

### 1. Install Python

Download Python 3.8+ from https://www.python.org/downloads/

**Important:** Check "Add Python to PATH" during installation

Verify:
```bash
python --version
```

### 2. Install Dependencies

```bash
cd Material-properties-measurement
pip install -r requirements.txt
```

### 3. Install VISA Backend

Install ONE of the following for instrument communication:

**Option A: NI-VISA (Recommended)**
- Download from: https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html

**Option B: Keysight IO Libraries**
- Download from: https://www.keysight.com/find/iolib

### 4. Run Measurements

**Seebeck Coefficient (with optional temperature sweep):**
```bash
python run_seebeck.py
```

**Electrical Conductivity (with optional temperature sweep):**
```bash
python run_sigma.py
```

**Combined Sigma + Seebeck vs Temperature:**
```bash
python run_combined.py
```

---

## 🌡️ Temperature Sweep Mode

All run scripts now support **Eurotherm temperature control** for measuring properties as a function of temperature.

### Usage Flow

1. Run any measurement script
2. When prompted "Enable Eurotherm Temperature Control? (y/n)", enter `y`
3. Enter temperature range (start, end, step, ramp rate)
4. Confirm and start measurement

### Example Session
```
SEEBECK COEFFICIENT MEASUREMENT SYSTEM
============================================================
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

### Output Structure
```
data/MySample/
├── global_log.log                    # Master log
├── MySample_Seebeck_vs_Temp.csv      # Aggregated results
├── MySample_Seebeck_vs_Temp.png      # Temperature plot
├── 50C/
│   ├── log.log
│   └── Seebeck/
│       ├── MySample_50C-orig.csv
│       └── MySample_50C-avg.csv
├── 100C/
│   └── ...
└── 200C/
    └── ...
```

---

## ⚙️ Configuration

### Constants File (Shared)

All instrument IDs and shared constants are in **[constants.py](constants.py)**:

```python
# Instrument Resource Strings (VISA Addresses)
DAQ_RESOURCE = 'USB0::0x05E6::0x6510::04619482::0::INSTR'
PS_RESOURCE = 'USB0::0x05E6::0x2230::805224014787570003::0::INSTR'

# Sigma Measurement Constants
DEFAULT_SAMPLE_THICKNESS = 2.3   # mm
DEFAULT_SAMPLE_DIAMETER = 12.65  # mm
KNOWN_RESISTOR = 0.1029          # Ohms
DAQ_TIMEOUT = 20000              # ms

# Eurotherm Temperature Controller
EUROTHERM_COM_PORT = 5           # COM5
EUROTHERM_DEVICE_ADDRESS = 1     # MODBUS address
EUROTHERM_BAUD_RATE = 9600

# Stability Parameters
EUROTHERM_STABILITY_TOLERANCE = 1.0   # °C
EUROTHERM_STABILITY_TIME = 60         # seconds
EUROTHERM_STABILITY_TIMEOUT = 1800    # seconds (30 min max)

# Default Temperature Sweep
DEFAULT_TEMP_START = 50.0    # °C
DEFAULT_TEMP_END = 200.0     # °C
DEFAULT_TEMP_STEP = 25.0     # °C
DEFAULT_RAMP_RATE = 10.0     # °C/min
```

### Find Your Instruments

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

Update `constants.py` with your instrument addresses.

---

## 📊 Measurements

### Seebeck Coefficient Measurement

Measures thermoelectric voltage response to temperature gradient.

**Instruments:**
- Keithley DAQ6510 Data Acquisition System
- Keithley 2230-30-1 Triple Output Power Supply
- Type K thermocouples
- Eurotherm 2000/3000 Series (optional, for temperature sweep)

**Method:**
1. Creates temperature gradient using gradient heaters
2. Measures temperatures (T1, T2) and voltages (V1, V2)
3. Reverses gradient to eliminate systematic errors
4. Fits V2 vs V1 linear regression
5. Calculates Seebeck coefficient from slope

**Duration:** ~8 minutes per temperature point (configurable)

**Output:**
- Raw data CSV file
- Averaged data CSV file
- Seebeck coefficient (µV/K)
- Real-time plots
- Temperature-dependent data (when using Eurotherm)

### Electrical Conductivity Measurement

Measures electrical conductivity using Van der Pauw method.

**Instruments:**
- Keithley DAQ6510 Data Acquisition System
- Keithley 2230-30-1 Triple Output Power Supply
- Eurotherm 2000/3000 Series (optional, for temperature sweep)

**Method:**
1. Measures current through known resistor (0.1029 Ω)
2. Performs 5 iterations of 4-point measurements
3. Applies current to sample corners via matrix switching
4. Measures voltages in perpendicular directions
5. Solves Van der Pauw equation using Brent's method
6. Computes conductivity with geometry correction

**Duration:** ~80-90 seconds per temperature point

**Output:**
- Electrical conductivity (S/cm)
- Resistivity (Ω·cm)
- CSV file with results
- Temperature-dependent data (when using Eurotherm)

**Safety:** Matrix relays are never switched while current is flowing.

### Combined Measurement (run_combined.py)

Runs both sigma and Seebeck at each temperature point.

**Order at each temperature:**
1. Sigma measurement (uses power supply current)
2. 2-second safety pause
3. Seebeck measurement (uses gradient heater)

**Output:**
- `SampleName_Sigma_vs_Temp.csv` with plot
- `SampleName_Seebeck_vs_Temp.csv` with plot
- Per-temperature folders with individual results

---

## 💻 Usage Examples

### Seebeck Measurement (Programmatic)

```python
from seebeck_measurement import SeebeckMeasurement

# Create measurement instance
measurement = SeebeckMeasurement(enable_plotting=True)

# Run measurement
results = measurement.run_measurement(
    filename="MySample_001",
    measurement_time=480  # seconds
)

# Get results
print(f"Seebeck Coefficient: {results['S_slope']:.2f} µV/K")
print(f"Temperature: {results['T_avg']:.2f} °C")
```

### Conductivity Measurement (Programmatic)

```python
from measure_sigma import measure_sigma

# Run measurement (uses defaults from constants.py)
results = measure_sigma(
    sample_t=2.3,      # thickness in mm (optional)
    sample_dia=12.65,  # diameter in mm (optional)
    verbose=True
)

# Get results
if results:
    print(f"Conductivity: {results['corr_sigma']:.2f} S/cm")
    print(f"Current: {results['current']:.6f} A")
```

---

## 📁 Output Files

### Seebeck Measurement
Files saved to `~/seebeck_data/`:
- `{sample_name}-orig.csv` - Raw measurements
- `{sample_name}-avg.csv` - Averaged data

Columns: `DT, T1, T2, V1, V2, time`

### Conductivity Measurement
- Console output with detailed measurement progress
- Optional Excel export: `sigma_measurement.xlsx`

---

## 🔧 Troubleshooting

### VISA Connection Errors

**Problem:** Cannot find instruments

**Solution:**
1. Install NI-VISA or Keysight IO Libraries
2. Verify USB connections
3. Check resource strings in `constants.py`
4. List available resources:
   ```python
   import pyvisa
   print(pyvisa.ResourceManager().list_resources())
   ```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'pyvisa'`

**Solution:**
```bash
pip install -r requirements.txt
```

### Van der Pauw Solver Fails

**Problem:** `brentq failed` warning

**Solution:** The code automatically falls back to initial guess. If results seem wrong:
- Check sample dimensions
- Verify current is flowing (check voltage readings)
- Ensure good electrical contact

### Plot Not Showing

**Problem:** Seebeck plot doesn't appear

**Solution:**
- Install matplotlib: `pip install matplotlib`
- Use `enable_plotting=True`
- Check if running in headless environment

---

## 📚 Technical Details

### Seebeck Coefficient Theory

The Seebeck coefficient is calculated from V1-V2 slope:

```
S_sample = (1 / (1 - m)) × S_TC + S_Alumel
```

Where:
- `m` = V1-V2 slope from linear regression
- `S_TC` = Type K thermocouple Seebeck coefficient
- `S_Alumel` = Alumel wire Seebeck coefficient

Type K thermocouple conversions use ITS-90 polynomials.

### Van der Pauw Method

Four-point probe measurement eliminating contact resistance:

```
exp(-π·R₁·d/ρ) + exp(-π·R₂·d/ρ) = 1
```

Solved using `scipy.optimize.brentq` (Brent's bracketed root-finding method) for robust convergence.

Geometry correction applied for finite sample size:
```
σ_corrected = σ × (1 - error)
error = 4 × (d₁² / (2 × D₁² × ln(2)))
```

---

## 📦 Dependencies

```
pyvisa>=1.14.0
pyvisa-py>=0.7.1
numpy>=1.24.0
scipy>=1.11.0
matplotlib>=3.7.0
pandas>=2.0.0
openpyxl>=3.1.0
pyserial>=3.5
```

Install all:
```bash
pip install -r requirements.txt
```

---

## 🔌 Eurotherm Controller Setup

The Eurotherm 2000/3000 series temperature controller communicates via **MODBUS RTU** over RS-232.

### Connection
- Serial port: COM5 (configurable in constants.py)
- Baud rate: 9600
- MODBUS address: 1

### Supported Functions
- Read process value (PV)
- Set setpoint (SP)
- Set ramp rate
- Auto/Manual mode control

### MODBUS Registers
| Parameter | Register | Description |
|-----------|----------|-------------|
| PV | 1 | Process Value (current temp) |
| SP | 2 | Setpoint |
| Output | 3 | Heater output % |
| Ramp Rate | 35 | °C/min |
| Auto/Manual | 273 | 0=Auto, 1=Manual |

---

## 🎯 Best Practices

1. **Update constants.py** with your instrument addresses before first use
2. **Calibrate instruments** before measurements
3. **Stabilize temperature** before measurements (automatic with Eurotherm)
4. **Check connections** to avoid contact resistance
5. **Use consistent sample dimensions** for comparisons
6. **Run multiple measurements** for statistical accuracy
7. **Allow cooldown** - Scripts automatically set 25°C after temperature sweeps

---

## 📋 Changelog

### v2.0.0 (January 2025)
- **NEW:** Eurotherm temperature controller integration
- **NEW:** Temperature sweep capability for all measurements
- **NEW:** `run_combined.py` for Sigma + Seebeck vs temperature
- **NEW:** Hierarchical data folder structure
- **NEW:** Global and local logging per temperature
- **NEW:** Aggregated CSV files and temperature plots
- Improved output organization
- Indian date format (DD-MM-YYYY)

### v1.0.0 (December 2025)
- Initial release
- Seebeck coefficient measurement with real-time plotting
- Van der Pauw electrical conductivity measurement
- Centralized constants file for easy configuration
- Robust root-finding using Brent's method
- Matrix switching safety (no hot-switching)

---

**Author:** VanshilGupta  
**Repository:** [Material-properites-measurement](https://github.com/VanshilGupta/Material-properites-measurement)  
**Version:** 2.0.0  
**Last Updated:** January 2025
