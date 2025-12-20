# Thermoelectric Material Properties Measurement System

Complete Python system for measuring **Seebeck coefficient** and **electrical conductivity (σ)** of thermoelectric materials using Van der Pauw method.

## 📁 Project Structure

```
Material-properties-measurement/
├── constants.py                  # Shared instrument IDs & sigma constants
├── measure_sigma.py              # Electrical conductivity measurement
├── run_seebeck.py                # Run Seebeck measurement
├── run_sigma.py                  # Run conductivity measurement
├── requirements.txt              # Dependencies
│
└── seebeck_measurement/          # Seebeck measurement package
    ├── __init__.py               # Package exports
    ├── config.py                 # Seebeck-specific configuration
    ├── measurement.py            # Main orchestration
    ├── instruments.py            # Hardware control (DAQ, PS)
    ├── temperature_conversion.py # Thermocouple conversions (ITS-90)
    ├── data_processing.py        # Data averaging & CSV export
    ├── curve_fitting.py          # Seebeck coefficient calculation
    └── plotting.py               # Real-time visualization
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

**Seebeck Coefficient:**
```bash
python run_seebeck.py
```

**Electrical Conductivity:**
```bash
python run_sigma.py
```

---

## ⚙️ Configuration

### Constants File (Shared)

All instrument IDs and shared constants are in **[constants.py](constants.py)**:

```python
# Instrument Resource Strings (VISA Addresses)
DAQ_RESOURCE = 'USB0::0x05E6::0x6510::04619482::0::INSTR'
PS_RESOURCE = 'USB0::0x05E6::0x2230::805224014787570003::0::INSTR'

# Instrument IDs
DAQ_VENDOR_ID = 0x05E6
DAQ_PRODUCT_ID = 0x6510
DAQ_SERIAL = '04619482'

PS_VENDOR_ID = 0x05E6
PS_PRODUCT_ID = 0x2230
PS_SERIAL = '805224014787570003'

# Sigma Measurement Constants
DEFAULT_SAMPLE_THICKNESS = 2.3   # mm
DEFAULT_SAMPLE_DIAMETER = 12.65  # mm
KNOWN_RESISTOR = 0.1029          # Ohms
DAQ_TIMEOUT = 20000              # ms
```

### Seebeck-Specific Config

Additional Seebeck parameters in **[seebeck_measurement/config.py](seebeck_measurement/config.py)**:

```python
# Imports shared constants from root constants.py
from constants import DAQ_RESOURCE, PS_RESOURCE, DAQ_TIMEOUT, ...

# Seebeck-specific settings
DEFAULT_MEASUREMENT_TIME = 480   # seconds (8 minutes)
MAX_TEMP_DIFFERENCE = 8.0        # °C
HEATER_CURRENT = 0.3             # Amps
HEATER_VOLTAGE = 10.0            # Volts
DAQ_CHANNELS = [101, 106, 111, 116, 111, 106, 101]
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

**Method:**
1. Creates temperature gradient using gradient heaters
2. Measures temperatures (T1, T2) and voltages (V1, V2)
3. Reverses gradient to eliminate systematic errors
4. Fits V2 vs V1 linear regression
5. Calculates Seebeck coefficient from slope

**Duration:** ~8 minutes (configurable)

**Output:**
- Raw data CSV file
- Averaged data CSV file
- Seebeck coefficient (µV/K)
- Real-time plots

### Electrical Conductivity Measurement

Measures electrical conductivity using Van der Pauw method.

**Instruments:**
- Keithley DAQ6510 Data Acquisition System
- Keithley 2230-30-1 Triple Output Power Supply

**Method:**
1. Measures current through known resistor (0.1029 Ω)
2. Performs 5 iterations of 4-point measurements
3. Applies current to sample corners via matrix switching
4. Measures voltages in perpendicular directions
5. Solves Van der Pauw equation using Brent's method
6. Computes conductivity with geometry correction

**Duration:** ~80-90 seconds

**Output:**
- Electrical conductivity (S/cm)
- Resistivity (Ω·cm)
- Excel file with results

**Safety:** Matrix relays are never switched while current is flowing.

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
```

Install all:
```bash
pip install -r requirements.txt
```

---

## 🎯 Best Practices

1. **Update constants.py** with your instrument addresses before first use
2. **Calibrate instruments** before measurements
3. **Stabilize temperature** before Seebeck measurement
4. **Check connections** to avoid contact resistance
5. **Use consistent sample dimensions** for comparisons
6. **Run multiple measurements** for statistical accuracy

---

## 📋 Changelog

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
**Version:** 1.0.0  
**Last Updated:** December 2025
