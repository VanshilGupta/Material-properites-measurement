# Thermoelectric Measurement System

Complete Python system for measuring **Seebeck coefficient** and **electrical conductivity (σ)** of thermoelectric materials.

## 📁 Project Structure

```
Seeback-sigma-measurement-app/
├── seebeck_measurement/          # Seebeck measurement package
│   ├── measurement.py            # Main orchestration
│   ├── instruments.py            # Hardware control
│   ├── temperature_conversion.py # Thermocouple conversions
│   ├── data_processing.py        # Data averaging & export
│   ├── curve_fitting.py          # Seebeck calculation
│   ├── plotting.py               # Real-time visualization
│   └── config.py                 # Configuration
│
├── measure_sigma.py              # Conductivity measurement
├── run_seebeck.py                # Run Seebeck measurement
├── run_sigma.py                  # Run conductivity measurement
└── requirements.txt              # Dependencies
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
cd Seeback-sigma-measurement-app
pip install -r requirements.txt
```

### 3. Run Measurements

**Seebeck Coefficient:**
```bash
python run_seebeck.py
```

**Electrical Conductivity:**
```bash
python run_sigma.py
```

---

## 📊 Measurements

### Seebeck Coefficient Measurement

Measures thermoelectric voltage response to temperature gradient.

**Instruments:**
- Keysight DAQ6510 Data Acquisition System
- Keysight 2230-30-1 Triple Output Power Supply
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
- Keysight DAQ6510 Data Acquisition System
- Keysight 2230-30-1 Triple Output Power Supply

**Method:**
1. Measures current through known resistor
2. Applies current to sample corners
3. Measures voltages in perpendicular directions
4. Calculates resistivity using Van der Pauw equations
5. Computes conductivity (σ = 1/ρ)

**Duration:** ~1-2 minutes

**Output:**
- Electrical conductivity (S/m)
- Resistivity (Ω·m)

---

## ⚙️ Configuration

### Update Instrument Addresses

Edit [seebeck_measurement/config.py](seebeck_measurement/config.py) for Seebeck:
```python
DAQ_RESOURCE = 'USB0::0x05E6::0x6510::04619482::0::INSTR'
PS_RESOURCE = 'USB0::0x05E6::0x2230::805224014787570003::0::INSTR'
```

Edit [measure_sigma.py](measure_sigma.py) for Conductivity (lines 36-37):
```python
DAQ_RESOURCE = 'USB0::0x05E6::0x6510::04619482::0::INSTR'
PS_RESOURCE = 'USB0::0x05E6::0x2230::805224014787570003::0::INSTR'
```

**Find your instruments:**
```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

### Measurement Parameters

**Seebeck:** Edit [seebeck_measurement/config.py](seebeck_measurement/config.py)
- Measurement time
- Temperature thresholds
- Heater parameters
- DAQ channels

**Conductivity:** Edit sample dimensions when prompted or in code

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

# Run measurement
results = measure_sigma(
    sample_t=2.3,      # thickness in mm
    sample_dia=12.65,  # diameter in mm
    verbose=True
)

# Get results
if results:
    print(f"Conductivity: {results['sigma']:.2e} S/m")
    print(f"Resistivity: {results['rho']:.2e} Ω·m")
```

---

## 📁 Output Files

### Seebeck Measurement
Files saved to `~/seebeck_data/`:
- `{sample_name}-orig.csv` - Raw measurements
- `{sample_name}-avg.csv` - Averaged data

Columns: `DT, T1, T2, V1, V2, time`

### Conductivity Measurement
Results printed to console (can be logged to file)

---

## 🔧 Troubleshooting

### VISA Connection Errors

**Problem:** Cannot find instruments

**Solution:**
1. Install NI-VISA or Keysight IO Libraries
2. Verify USB connections
3. Check resource strings match your instruments
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

### Plot Not Showing

**Problem:** Seebeck plot doesn't appear

**Solution:**
- Install matplotlib: `pip install matplotlib`
- Use `enable_plotting=True` when creating SeebeckMeasurement
- Check if running in headless environment

### Permission Errors

**Windows:** Run as Administrator
**Linux:** Check USB device permissions

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
ρ = (π × t / ln(2)) × f × (R_A + R_B) / 2
σ = 1 / ρ
```

Where:
- `t` = sample thickness
- `f` = geometric factor (solved numerically)
- `R_A`, `R_B` = resistances in perpendicular directions

---

## 🎯 Best Practices

1. **Calibrate instruments** before measurements
2. **Stabilize temperature** before Seebeck measurement
3. **Check connections** to avoid contact resistance
4. **Use consistent sample dimensions** for comparisons
5. **Run multiple measurements** for statistical accuracy
6. **Save data immediately** after each measurement

---

## 📦 Dependencies

- `numpy` - Numerical computations
- `scipy` - Curve fitting and optimization
- `matplotlib` - Plotting
- `pyvisa` - Instrument communication
- `pyvisa-py` - Pure Python VISA backend

Install all:
```bash
pip install -r requirements.txt
```


## 🙋 Support

For issues or questions:
1. Check the troubleshooting section
2. Verify instrument connections
3. Review configuration files
4. Check Python version compatibility (3.8+)

---

**Version:** 1.0.0  
**Last Updated:** December 2025

Save this as `requirements.txt` in your project folder:
```
pyvisa>=1.14.0
pyvisa-py>=0.7.1
numpy>=1.24.0
scipy>=1.11.0
pandas>=2.0.0
openpyxl>=3.1.0
```

Install all libraries:
```
pip install -r requirements.txt
```

---

## Step 4: Install VISA Backend

You need to install ONE of the following (this allows Python to communicate with instruments):

**Option A: NI-VISA (Recommended)**
- Download from: https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html
- Install the software
- Restart your computer

**Option B: Keysight IO Libraries**
- Download from: https://www.keysight.com/find/iolib
- Install the software
- Restart your computer

---

## Step 5: Connect Instruments

1. Connect Keithley DAQ6510 to computer via USB cable
2. Connect Keithley 2230-30-1 Power Supply to computer via USB cable
3. Turn ON both instruments
4. Wait 10-20 seconds for Windows to install drivers

---

## Step 6: Verify Connected Devices

Make sure your virtual environment is activated.

Run this command:
```
python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"
```

**Expected Output:**
You should see something like:
```
('USB0::0x05E6::0x6510::04619482::0::INSTR',
 'USB0::0x05E6::0x2230::805224014787570003::0::INSTR')
```

The first line is your DAQ6510 Multimeter.
The second line is your Power Supply.

**If you see your instruments listed, setup is complete!**

**If you don't see any instruments:**
- Check USB connections
- Make sure instruments are turned ON
- Verify VISA backend (NI-VISA or Keysight IO) is installed
- Try unplugging and replugging USB cables
- Restart your computer

**If your instrument addresses are different from the ones above:**
You will need to update the addresses in `measure_sigma.py`:
```python
DAQ_RESOURCE = 'YOUR_DAQ_ADDRESS_HERE'
PS_RESOURCE = 'YOUR_POWER_SUPPLY_ADDRESS_HERE'
```

---

## Setup Complete

Your system is now ready to run measurements.