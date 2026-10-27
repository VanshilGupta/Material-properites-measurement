"""Electrical conductivity measurement using the Van der Pauw method.

Drives a Keithley DAQ6510 multimeter and a Keithley 2230-30-1 power supply
to measure 4 Van der Pauw voltage configurations, solves the transcendental
VdP equation with scipy.optimize.brentq, and reports the geometry-corrected
conductivity in S/cm.

In REMOTE_MODE the VISA resource manager is transparently replaced with an
HTTP proxy (see ``remote_instruments.py``) so the GUI can run on a separate
PC from the instruments.
"""

import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from constants import (
    DAQ_RESOURCE,
    DEFAULT_SAMPLE_DIAMETER,
    DEFAULT_SAMPLE_THICKNESS,
    KNOWN_RESISTOR,
    PS_RESOURCE,
    REMOTE_MODE,
)

# pyvisa is only available in local mode but VisaIOError is referenced in
# except-clauses below.  Import it lazily and fall back to a stand-in so the
# remote-mode code path never trips a NameError when a real exception fires.
try:
    import pyvisa
    _VisaIOError = pyvisa.VisaIOError
except ImportError:  # pragma: no cover - remote-mode environments
    pyvisa = None  # type: ignore[assignment]

    class _VisaIOError(Exception):  # type: ignore[no-redef]
        """Placeholder when pyvisa isn't installed (remote mode)."""
        error_code = None


class MeasurementAborted(Exception):
    """Raised when the user aborts (the GUI patches ``time.sleep`` to raise it).

    Defined here, not in the GUI, so the handlers below can let it through
    instead of swallowing it as an ordinary error.  The GUI's measurement
    service imports and raises this same class.
    """


def _output_off(ps):
    """Switch the power-supply output off.  Never raises.

    Called on every exit path once the output may be on, so an abort or an
    error can never leave current flowing through the sample.
    """
    try:
        ps.write(':OUTP:STAT OFF')
    except Exception as e:
        print(f"✗ WARNING: could not switch power supply output off: {e}")


def _make_resource_manager():
    """Return a resource manager appropriate for the active mode.

    Local mode → real ``pyvisa.ResourceManager``.
    Remote mode → ``RemoteResourceManager`` (HTTP proxy to the lab PC).
    """
    if REMOTE_MODE:
        from remote_instruments import RemoteResourceManager
        return RemoteResourceManager()
    if pyvisa is None:
        raise RuntimeError(
            "pyvisa is not installed but REMOTE_MODE is False. "
            "Install pyvisa or set REMOTE_MODE=True in constants.py."
        )
    return pyvisa.ResourceManager()


def measure_sigma(sample_t=None, sample_dia=None, verbose=True, logger=None,
                  progress_callback=None):
    """
    Measure electrical conductivity using Van der Pauw method.
    
    Parameters:
    -----------
    sample_t : float, optional
        Sample thickness in mm (default from constants: 2.3 mm)
    sample_dia : float, optional
        Sample diameter in mm (default from constants: 12.65 mm)
    verbose : bool, optional
        Print detailed debug info (default: True)
    logger : logging.Logger, optional
        Logger instance for recording measurement events
    progress_callback : callable, optional
        Called after each VDP iteration with a dict of iteration data.
        Signature: ``progress_callback(iter_data: dict)``
    
    Returns:
    --------
    dict : Measurement results or None if failed
    """
    
    def _log(level: str, message: str):
        """Log a message if logger is available."""
        if logger:
            log_method = getattr(logger, level, logger.info)
            log_method(message)
    
    sigma_raw = np.zeros(5)  # Store 5 measurements
    iteration_results = []    # per-iteration V1–V4 + sigma
    
    # Use defaults from constants if not provided
    if sample_t is None:
        sample_t = DEFAULT_SAMPLE_THICKNESS
    if sample_dia is None:
        sample_dia = DEFAULT_SAMPLE_DIAMETER
    
    _log('info', f"Starting sigma measurement with thickness={sample_t}mm, diameter={sample_dia}mm")
    
    # Init resource manager (local pyvisa or HTTP proxy for remote mode)
    try:
        rm = _make_resource_manager()
        if verbose:
            mode_label = "Remote (HTTP proxy)" if REMOTE_MODE else "PyVISA"
            print(f"✓ ResourceManager initialized ({mode_label})")
            _log('info', f"ResourceManager initialized ({mode_label})")
            print(f"Available resources: {rm.list_resources()}")
            _log('debug', f"Available resources: {rm.list_resources()}")
    except Exception as e:
        print(f"✗ FATAL: Cannot initialize ResourceManager")
        print(f"  Error: {e}")
        if not REMOTE_MODE:
            print(f"  Solution: Install NI-VISA or pyvisa-py backend")
        _log('error', f"FATAL: Cannot initialize ResourceManager: {e}")
        return None
    
    if verbose:
        print("="*60)
        print("ELECTRICAL CONDUCTIVITY MEASUREMENT")
        print("="*60)
        print(f"Sample thickness: {sample_t} mm")
        print(f"Sample diameter: {sample_dia} mm\n")
    
    # =========================================================================
    # STEP 1: Measure current through known resistor (value from constants)
    # =========================================================================
    if verbose:
        print("Step 1: Measuring current through known resistor...")
    
    daq = None
    ps = None
    current = None
    
    try:
        # Connect to instruments
        daq = rm.open_resource(DAQ_RESOURCE)
        if verbose:
            print(f"  ✓ Connected to DAQ: {DAQ_RESOURCE}")
            _log('info', f"Connected to DAQ: {DAQ_RESOURCE}")
    except _VisaIOError as e:
        print(f"✗ ERROR: Cannot connect to DAQ6510 Multimeter")
        print(f"  Resource: {DAQ_RESOURCE}")
        print(f"  Error code: {e.error_code}")
        print(f"  Error: {e}")
        print(f"  Solution: Check USB connection, verify resource string")
        _log('error', f"Cannot connect to DAQ6510: {e}")
        return None
    except Exception as e:
        print(f"✗ ERROR: Unexpected error connecting to DAQ")
        print(f"  {type(e).__name__}: {e}")
        traceback.print_exc()
        _log('error', f"Unexpected error connecting to DAQ: {e}")
        return None
    
    try:
        ps = rm.open_resource(PS_RESOURCE)
        if verbose:
            print(f"  ✓ Connected to Power Supply: {PS_RESOURCE}")
            _log('info', f"Connected to Power Supply: {PS_RESOURCE}")
    except _VisaIOError as e:
        print(f"✗ ERROR: Cannot connect to Power Supply")
        print(f"  Resource: {PS_RESOURCE}")
        print(f"  Error code: {e.error_code}")
        print(f"  Error: {e}")
        print(f"  Solution: Check USB connection, verify resource string")
        _log('error', f"Cannot connect to Power Supply: {e}")
        if daq:
            daq.close()
        return None
    except Exception as e:
        print(f"✗ ERROR: Unexpected error connecting to Power Supply")
        print(f"  {type(e).__name__}: {e}")
        traceback.print_exc()
        _log('error', f"Unexpected error connecting to Power Supply: {e}")
        if daq:
            daq.close()
        return None
    
    try:
        # Configure DAQ for voltage on channel 103
        daq.write('*RST')  # Reset
        daq.write('ROUT:SCAN (@103)')  # Scan channel 103
        daq.write('SENS:FUNC "VOLT:DC", (@103)')  # DC voltage mode
        daq.write('VOLT:DC:RANG:AUTO ON,(@103)')  # Auto range
        daq.write('VOLT:DC:NPLC 5,(@103)')  # 5 power line cycles
        daq.write('ROUT:CLOS (@103)')  # Close channel 103
        daq.write('ROUT:CLOS (@229)')  # Close routing 229
        if verbose:
            print("  ✓ DAQ configured for channel 103")
        
    except _VisaIOError as e:
        print(f"✗ ERROR: Failed to configure DAQ")
        print(f"  Error: {e}")
        print(f"  Solution: Check SCPI command syntax, verify channel numbers")
        daq.close()
        ps.close()
        return None
    except Exception as e:
        print(f"✗ ERROR: Unexpected error configuring DAQ")
        print(f"  {type(e).__name__}: {e}")
        traceback.print_exc()
        daq.close()
        ps.close()
        return None
    
    try:
        # Configure Power Supply - All channels off first
        ps.write('*RST')  # Reset
        ps.write(':INST:SEL CH1')  # Select CH1
        ps.write(':SOUR:FUNC:CURR')  # Current mode
        ps.write(':SOUR:CURR 0.0')  # 0 A
        ps.write(':SOUR:VOLT 0')  # 0 V
        
        ps.write(':INST:SEL CH2')  # Select CH2
        ps.write(':SOUR:FUNC:CURR')
        ps.write(':SOUR:CURR 0.0')
        ps.write(':SOUR:VOLT 0')
        
        ps.write(':INST:SEL CH3')  # Select CH3
        ps.write(':SOUR:FUNC:CURR')
        ps.write(':SOUR:CURR 0.1')  # 100 mA
        ps.write(':SOUR:VOLT 5')  # 5V limit
        ps.write(':OUTP:STAT ON')  # Turn ON
        if verbose:
            print("  ✓ Power Supply configured, CH3 ON at 0.1A")
        
        time.sleep(2)  # Wait for stabilization

    except MeasurementAborted:
        _output_off(ps)
        daq.close()
        ps.close()
        raise
    except _VisaIOError as e:
        print(f"✗ ERROR: Failed to configure Power Supply")
        print(f"  Error: {e}")
        print(f"  Solution: Check if power supply supports these SCPI commands")
        _output_off(ps)
        daq.close()
        ps.close()
        return None
    except Exception as e:
        print(f"✗ ERROR: Unexpected error configuring Power Supply")
        print(f"  {type(e).__name__}: {e}")
        traceback.print_exc()
        _output_off(ps)
        daq.close()
        ps.close()
        return None
    
    try:
        # Read voltage from DAQ
        result_str = daq.query('READ?')
        ps.write(':OUTP:STAT OFF')  # Turn off immediately
        
        voltage = float(result_str.strip())
        current = voltage / KNOWN_RESISTOR  # Known resistance from constants
        
        if verbose:
            print(f"  ✓ Voltage measured: {voltage:.6f} V")
            print(f"  ✓ Current calculated: {current:.6f} A\n")
        
    except ValueError as e:
        print(f"✗ ERROR: Cannot parse voltage reading")
        print(f"  Received: '{result_str}'")
        print(f"  Error: {e}")
        print(f"  Solution: Check DAQ output format")
        ps.write(':OUTP:STAT OFF')
        daq.close()
        ps.close()
        return None
    except Exception as e:
        print(f"✗ ERROR: Failed to read voltage")
        print(f"  {type(e).__name__}: {e}")
        traceback.print_exc()
        ps.write(':OUTP:STAT OFF')
        daq.close()
        ps.close()
        return None
    
    # Close after Step 1
    daq.close()
    ps.close()
    if verbose:
        print("  ✓ Instruments closed after current measurement\n")
    
    if current is None or current <= 0:
        print(f"✗ ERROR: Invalid current measured: {current}")
        return None
    
    # =========================================================================
    # STEP 2: Van der Pauw measurements (5 iterations)
    # =========================================================================
    
    # Van der Pauw channel/route configurations:
    #   (DAQ channel, route, label)
    VDP_CONFIGS = [
        (204, 227, "V1"),
        (204, 235, "V2"),
        (206, 229, "V3"),
        (206, 237, "V4"),
    ]
    
    def _measure_vdp_voltage(rm, channel, route, label, iteration, verbose):
        """Take a single Van der Pauw voltage reading."""
        daq_inst = None
        ps_inst = None
        try:
            daq_inst = rm.open_resource(DAQ_RESOURCE)
            ps_inst = rm.open_resource(PS_RESOURCE)
            
            # Configure DAQ
            daq_inst.write('*RST')
            daq_inst.write('ROUT:OPEN:ALL')
            daq_inst.write(f'ROUT:SCAN (@{channel})')
            daq_inst.write(f'SENS:FUNC "VOLT:DC", (@{channel})')
            daq_inst.write(f'VOLT:DC:RANG:AUTO ON,(@{channel})')
            daq_inst.write(f'VOLT:DC:NPLC 5,(@{channel})')
            daq_inst.write(f'ROUT:CLOS (@{channel})')
            daq_inst.write(f'ROUT:CLOS (@{route})')
            
            # Configure PS: CH1/CH2 off, CH3 at 0.1A/5V
            ps_inst.write('*RST')
            ps_inst.write(':INST:SEL CH1')
            ps_inst.write(':SOUR:FUNC:CURR')
            ps_inst.write(':SOUR:CURR 0.0')
            ps_inst.write(':SOUR:VOLT 0')
            ps_inst.write(':INST:SEL CH2')
            ps_inst.write(':SOUR:FUNC:CURR')
            ps_inst.write(':SOUR:CURR 0.0')
            ps_inst.write(':SOUR:VOLT 0')
            ps_inst.write(':INST:SEL CH3')
            ps_inst.write(':SOUR:FUNC:CURR')
            ps_inst.write(':SOUR:CURR 0.1')
            ps_inst.write(':SOUR:VOLT 5')
            ps_inst.write(':OUTP:STAT ON')
            
            time.sleep(2)
            
            result_str = daq_inst.query('READ?')
            ps_inst.write(':OUTP:STAT OFF')
            voltage = float(result_str.strip())
            
            if verbose:
                print(f"  {label} ({channel}-{route}): {voltage:.6f} V")
            
            return voltage

        except MeasurementAborted:
            raise
        except Exception as e:
            print(f"✗ ERROR in {label} (iteration {iteration}): {type(e).__name__}: {e}")
            return None
        finally:
            if daq_inst:
                daq_inst.close()
            if ps_inst:
                # Abort or error during the 2 s wait skips the OFF above.
                _output_off(ps_inst)
                ps_inst.close()
    
    if verbose:
        print("Step 2: Van der Pauw measurements (4 voltages × 5 iterations)")
        print("-" * 60)
    
    for j in range(5):
        if verbose:
            print(f"\nIteration {j+1}/5:")
        _log('info', f"Van der Pauw iteration {j+1}/5 starting")
        
        # Take all 4 voltage measurements
        voltages = []
        for channel, route, label in VDP_CONFIGS:
            v = _measure_vdp_voltage(rm, channel, route, label, j+1, verbose)
            voltages.append(v)
            _log('info', f"  {label} = {v:.6f} V" if v is not None else f"  {label} = FAILED")
        
        volt1, volt2, volt3, volt4 = voltages
        _log('info',
             f"  Voltages: V1={volt1}, V2={volt2}, V3={volt3}, V4={volt4}")
        
        # Skip iteration if any measurement failed
        if None in voltages:
            print(f"✗ Iteration {j+1} incomplete, skipping")
            _log('warning', f"Iteration {j+1} incomplete — skipping")
            sigma_raw[j] = 0
            iter_data = {
                'iteration': j + 1,
                'v1': volt1, 'v2': volt2, 'v3': volt3, 'v4': volt4,
                'delta_v1': None, 'delta_v2': None,
                'R1': None, 'R2': None, 'sigma': 0,
            }
            iteration_results.append(iter_data)
            if progress_callback:
                progress_callback(iter_data)
            continue
        
        # --- Calculate resistivity using Van der Pauw ---
        try:
            V1 = abs(volt1 - volt2) / 2.0  # Average voltage 1
            V2 = abs(volt3 - volt4) / 2.0  # Average voltage 2
            
            R1 = V1 / current  # Resistance 1
            R2 = V2 / current  # Resistance 2
            
            _log('info',
                 f"  ΔV1={V1:.6f} V, ΔV2={V2:.6f} V  →  "
                 f"R1={R1:.6f} Ω, R2={R2:.6f} Ω")
            
            if verbose:
                print(f"  R1 = {R1:.6f} Ω, R2 = {R2:.6f} Ω")
            
            d = sample_t / 10.0  # Thickness in cm
            
            # Van der Pauw equation
            def vdp_equation(rho):
                return (np.exp(-np.pi * R1 * d / rho) + 
                        np.exp(-np.pi * R2 * d / rho)) - 1
            
            # Find initial guess for bracketing
            Rho1 = np.arange(5e-5, 100, 10e-5)
            F = np.abs(vdp_equation(Rho1))
            id_min = np.nanargmin(F)
            Rho_min = Rho1[id_min]
            
            # Solve for resistivity using Brent's method (robust bracketed root finding)
            try:
                # Find a bracket around Rho_min where function changes sign
                bracket_found = False
                for scale in [10, 100, 1000, 10000]:
                    a, b = Rho_min / scale, Rho_min * scale
                    fa, fb = vdp_equation(a), vdp_equation(b)
                    if fa * fb < 0:  # Opposite signs, valid bracket
                        bracket_found = True
                        if verbose:
                            print(f"    Bracket found: [{a:.6e}, {b:.6e}]")
                        break
                
                if bracket_found:
                    Rho = brentq(vdp_equation, a, b, xtol=1e-12, rtol=1e-10)
                else:
                    # Fallback: try wide bracket, but check sign change first
                    fa_wide, fb_wide = vdp_equation(1e-8), vdp_equation(1e3)
                    if fa_wide * fb_wide < 0:
                        if verbose:
                            print(f"    Using wide bracket [1e-8, 1e3]")
                        Rho = brentq(vdp_equation, 1e-8, 1e3, xtol=1e-12, rtol=1e-10)
                    else:
                        # No valid bracket found, use initial guess
                        if verbose:
                            print(f"    No valid bracket found, failed to find resistivity")
                        Rho = 0
                
                if Rho <= 0:
                    raise ValueError(f"Non-physical resistivity: {Rho}")
                
                sigma_raw[j] = 1.0 / Rho  # Conductivity
                
            except (ValueError, RuntimeError) as solve_error:
                print(f"    ⚠ brentq failed: {solve_error}, using initial guess")
                _log('warning', f"  brentq solver failed: {solve_error}")
                sigma_raw[j] = 0  # failed to find valid sigma
            
            _log('info', f"  Iteration {j+1} result: σ = {sigma_raw[j]:.2f} S/cm")
            if verbose:
                print(f"  ✓ σ = {sigma_raw[j]:.2f} S/cm")

            # Collect iteration-level data
            iter_data = {
                'iteration': j + 1,
                'v1': volt1, 'v2': volt2, 'v3': volt3, 'v4': volt4,
                'delta_v1': V1, 'delta_v2': V2,
                'R1': R1, 'R2': R2, 'sigma': sigma_raw[j],
            }
            iteration_results.append(iter_data)
            if progress_callback:
                progress_callback(iter_data)

        except MeasurementAborted:
            raise
        except Exception as e:
            print(f"✗ ERROR calculating resistivity (iteration {j+1})")
            print(f"  {type(e).__name__}: {e}")
            traceback.print_exc()
            sigma_raw[j] = 0
            iter_data = {
                'iteration': j + 1,
                'v1': volt1, 'v2': volt2, 'v3': volt3, 'v4': volt4,
                'delta_v1': None, 'delta_v2': None,
                'R1': None, 'R2': None, 'sigma': 0,
            }
            iteration_results.append(iter_data)
            if progress_callback:
                progress_callback(iter_data)
            continue
    
    # =========================================================================
    # STEP 3: Statistical analysis and correction
    # =========================================================================
    if verbose:
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(f"Raw sigma values: {sigma_raw}")
    
    _log('info', "Processing measurement results...")
    _log('debug', f"Raw sigma values: {sigma_raw}")
    
    valid_sigma = sigma_raw[sigma_raw > 0]  # Filter valid measurements
    
    if len(valid_sigma) == 0:
        print("✗ FATAL: No valid measurements obtained")
        print("  Check instrument connections and channel configurations")
        _log('error', "FATAL: No valid measurements obtained")
        return None
    
    sigma_avg = np.median(valid_sigma)  # Median (robust to outliers)
    std_dev = np.std(sigma_raw)
    uncorr_sigma = sigma_avg
    
    # Geometry correction
    D1 = sample_dia
    d1 = (D1 - 9.0) / 2.0
    error = 4 * ((d1**2) / (2 * D1**2 * np.log(2)))
    corr_sigma = sigma_avg * (1 - error)
    
    if verbose:
        print(f"Valid measurements: {len(valid_sigma)}/5")
        print(f"Median sigma: {sigma_avg:.2f} S/cm")
        print(f"Standard deviation: {std_dev:.4f}")
        print(f"Geometry correction: {error:.6f}")
        print(f"✓ CORRECTED SIGMA: {corr_sigma:.2f} S/cm")
        print("="*60)
    
    _log('info', f"Valid measurements: {len(valid_sigma)}/5")
    _log('info', f"Corrected sigma: {corr_sigma:.2f} S/cm")
    _log('debug', f"Median sigma: {sigma_avg:.2f}, Std dev: {std_dev:.4f}, Geometry correction: {error:.6f}")
    
    results = {
        'corr_sigma': corr_sigma,
        'uncorr_sigma': uncorr_sigma,
        'sigma_raw': sigma_raw,
        'std_dev': std_dev,
        'current': current,
        'sample_thickness': sample_t,
        'sample_diameter': sample_dia,
        'valid_count': len(valid_sigma),
        'iterations': iteration_results,
    }
    
    return results


# Written in the temperature cell when the sample temperature couldn't be read.
TEMPERATURE_FAILED_TEXT = "Failed to record"


def measure_sigma_with_sample_temperature(read_temperature, readings=None,
                                          progress_callback=None, **kwargs):
    """Run ``measure_sigma`` and record the SAMPLE's mean temperature.

    The sample thermocouple is read before σ starts and again after every
    VDP iteration — ``measure_sigma`` closes the DAQ after each reading, so
    it is free then.  Each of those reads is a single try.

    Parameters
    ----------
    read_temperature : callable
        Returns the sample temperature in °C, or ``None`` if the read failed
        (e.g. ``constants.read_current_temperature``).
    readings : list[float] | None
        Sample temperatures already taken just before σ.  If ``None``, one
        reading is taken here.
    progress_callback : callable | None
        Passed on to ``measure_sigma``; called after the iteration's
        temperature has been read.
    **kwargs
        Passed on to ``measure_sigma``.

    Returns
    -------
    dict | None
        ``measure_sigma``'s results plus ``'temperature'`` (mean of all
        readings, or ``None`` with a ``'temperature_note'`` if none could be
        read) and ``'temperature_readings'``.  Every iteration dict also gets
        its own ``'temperature'``.
    """
    def _read():
        try:
            return read_temperature()
        except MeasurementAborted:
            raise
        except Exception:
            return None

    if readings is None:
        t = _read()
        readings = [t] if t is not None else []
    else:
        readings = list(readings)

    def _callback(iter_data):
        t = _read()
        iter_data['temperature'] = round(t, 1) if t is not None else None
        if t is not None:
            readings.append(t)
        if progress_callback:
            progress_callback(iter_data)

    results = measure_sigma(progress_callback=_callback, **kwargs)
    if results:
        results['temperature_readings'] = readings
        if readings:
            results['temperature'] = round(sum(readings) / len(readings), 2)
        else:
            results['temperature'] = None
            results['temperature_note'] = TEMPERATURE_FAILED_TEXT
    return results


def _result_temperature(results):
    """Return the measurement temperature (°C) as a CSV cell string.

    The GUI stores the sample temperature as ``'temperature'`` (``None`` plus
    a ``'temperature_note'`` if it couldn't be read); run_sigma.py /
    run_combined.py store ``'actual_temp'``.  Empty if nothing is present.
    """
    temp = results.get('temperature', results.get('actual_temp'))
    if temp is None:
        return results.get('temperature_note', "")
    return f"{temp:.2f}"


def save_results_to_csv(results, sample_name, output_folder=None):
    """
    Save measurement results to CSV file in the output folder.
    
    Parameters:
    -----------
    results : dict
        Results from measure_sigma()
    sample_name : str
        Name of the sample
    output_folder : str
        Output folder path (sample folder)
    """
    try:
        if output_folder is None:
            output_folder = Path.cwd()
        else:
            output_folder = Path(output_folder)
        
        output_folder.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        filepath = output_folder / f"{sample_name}_sigma_results.csv"
        
        # Prepare data
        headers = [
            'Sample Name',
            'Timestamp',
            'Temperature (°C)',
            'Corrected Sigma (S/cm)',
            'Uncorrected Sigma (S/cm)',
            'Standard Deviation',
            'Current (A)',
            'Sample Thickness (mm)',
            'Sample Diameter (mm)',
            'Valid Measurements',
            'Raw Sigma Values'
        ]
        
        raw_sigma_str = ';'.join([f"{s:.4f}" for s in results['sigma_raw']])
        
        data = [
            sample_name,
            timestamp,
            _result_temperature(results),
            f"{results['corr_sigma']:.6f}",
            f"{results['uncorr_sigma']:.6f}",
            f"{results['std_dev']:.6f}",
            f"{results['current']:.6f}",
            f"{results['sample_thickness']:.2f}",
            f"{results['sample_diameter']:.2f}",
            f"{results['valid_count']}",
            raw_sigma_str
        ]
        
        # Write to CSV
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(','.join(headers) + '\n')
            f.write(','.join(data) + '\n')
        
        print(f"💾 Results saved to: {filepath}")
        
    except Exception as e:
        print(f"✗ ERROR saving results to CSV: {type(e).__name__}: {e}")
        traceback.print_exc()


def save_iteration_data_to_csv(results, sample_name, output_folder=None):
    """Save per-iteration V1–V4 and σ data to a separate CSV.

    Parameters
    ----------
    results : dict
        Results from ``measure_sigma()`` — must contain ``'iterations'``.
    sample_name : str
        Name of the sample (used in the filename).
    output_folder : str | Path | None
        Destination folder.  Defaults to the current directory.
    """
    iterations = results.get("iterations")
    if not iterations:
        return

    try:
        folder = Path(output_folder) if output_folder else Path.cwd()
        folder.mkdir(parents=True, exist_ok=True)
        filepath = folder / f"{sample_name}_sigma_iterations.csv"

        headers = [
            "Iteration", "Temperature (°C)",
            "V1 (V)", "V2 (V)", "V3 (V)", "V4 (V)",
            "Delta_V1 (V)", "Delta_V2 (V)", "R1 (Ohm)", "R2 (Ohm)",
            "Sigma (S/cm)",
        ]

        def _fmt(v):
            return f"{v:.6f}" if v is not None else ""

        temp_str = _result_temperature(results)

        def _iter_temp(it):
            # The GUI reads the sample temperature after every iteration;
            # otherwise every row gets the measurement's temperature.
            if "temperature" not in it:
                return temp_str
            t = it["temperature"]
            return f"{t:.2f}" if t is not None else TEMPERATURE_FAILED_TEXT

        with open(filepath, "w", encoding="utf-8-sig") as f:
            f.write(",".join(headers) + "\n")
            for it in iterations:
                row = [
                    str(it["iteration"]),
                    _iter_temp(it),
                    _fmt(it["v1"]), _fmt(it["v2"]),
                    _fmt(it["v3"]), _fmt(it["v4"]),
                    _fmt(it["delta_v1"]), _fmt(it["delta_v2"]),
                    _fmt(it["R1"]), _fmt(it["R2"]),
                    f"{it['sigma']:.6f}",
                ]
                f.write(",".join(row) + "\n")

        print(f"💾 Iteration data saved to: {filepath}")
    except Exception as e:
        print(f"✗ ERROR saving iteration CSV: {type(e).__name__}: {e}")
        traceback.print_exc()


def save_to_excel(results, temperature, filename='conductivity_results.xlsx'):
    """
    Save measurement results to Excel.
    
    Parameters:
    -----------
    results : dict
        Results from measure_sigma()
    temperature : float
        Temperature in Kelvin
    filename : str
        Output filename
    """
    try:
        import pandas as pd
        
        data = {
            'Temperature (K)': [temperature],
            'Uncorrected Sigma (S/cm)': [results['uncorr_sigma']],
            'Corrected Sigma (S/cm)': [results['corr_sigma']],
            'Standard Deviation': [results['std_dev']],
            'Current (A)': [results['current']],
            'Sample Thickness (mm)': [results['sample_thickness']],
            'Sample Diameter (mm)': [results['sample_diameter']],
            'Valid Measurements': [results['valid_count']]
        }
        
        df = pd.DataFrame(data)
        df.to_excel(filename, index=False)
        print(f"\n✓ Results saved to {filename}")
        
    except ImportError:
        print("✗ ERROR: pandas or openpyxl not installed")
        print("  Install: pip install pandas openpyxl")
    except Exception as e:
        print(f"✗ ERROR saving to Excel: {type(e).__name__}: {e}")
        traceback.print_exc()
