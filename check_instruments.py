"""
Instrument Health Check and Diagnostic Tool

Verifies all instruments are:
1. Connected and identifiable
2. Responding correctly to commands
3. Capable of sustained operation

Instruments tested:
- Keithley DAQ6510 Multimeter (VISA USB)
- Keithley 2230-30-1 Power Supply (VISA USB)
- Eurotherm 2000/3000 Temperature Controller (Serial RS-232)

Run this before starting any measurement to ensure system readiness.
"""

import time
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Try imports and track what's available
PYVISA_AVAILABLE = False
SERIAL_AVAILABLE = False

try:
    import pyvisa
    PYVISA_AVAILABLE = True
except ImportError:
    pass

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    pass

from constants import (
    DAQ_RESOURCE,
    PS_RESOURCE,
    DAQ_TIMEOUT,
    EUROTHERM_COM_PORT,
    EUROTHERM_DEVICE_ADDRESS,
    EUROTHERM_BAUD_RATE
)


class InstrumentChecker:
    """Comprehensive instrument diagnostics."""
    
    def __init__(self):
        self.results: Dict[str, dict] = {}
        self.rm = None
        self.logger = None
        self.log_file = None
    
    def setup_logging(self):
        """Setup file logging for instrument checks."""
        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%d-%m-%Y_%H%M%S")
        self.log_file = log_dir / f"instrument_check_{timestamp}.log"
        
        # Setup logger
        self.logger = logging.getLogger('InstrumentChecker')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # File handler (replaces file each time)
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
        # Log header
        self.logger.info("="*60)
        self.logger.info("INSTRUMENT HEALTH CHECK & DIAGNOSTICS")
        self.logger.info(f"Started: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
        self.logger.info("="*60)
        
        return self.log_file
        
    def print_header(self, title: str):
        """Print section header."""
        header = "\n" + "=" * 60 + f"\n {title}\n" + "=" * 60
        print(header)
        if self.logger:
            self.logger.info(f"\n{title}")
    
    def print_status(self, item: str, status: bool, details: str = ""):
        """Print status line with checkmark or X."""
        mark = "✓" if status else "✗"
        status_text = "OK" if status else "FAIL"
        detail_str = f" - {details}" if details else ""
        message = f"  {mark} {item}: {status_text}{detail_str}"
        print(message)
        
        # Log to file
        if self.logger:
            log_message = f"{item}: {status_text}{detail_str}"
            if status:
                self.logger.info(log_message)
            else:
                self.logger.error(log_message)
    
    def check_dependencies(self) -> bool:
        """Check if required Python packages are installed."""
        self.print_header("DEPENDENCY CHECK")
        
        all_ok = True
        
        # PyVISA
        self.print_status("pyvisa", PYVISA_AVAILABLE, 
                         "Required for DAQ and Power Supply")
        if not PYVISA_AVAILABLE:
            msg = "    → Install: pip install pyvisa pyvisa-py"
            print(msg)
            if self.logger:
                self.logger.warning(msg)
            all_ok = False
        
        # PySerial
        self.print_status("pyserial", SERIAL_AVAILABLE,
                         "Required for Eurotherm controller")
        if not SERIAL_AVAILABLE:
            msg = "    → Install: pip install pyserial"
            print(msg)
            if self.logger:
                self.logger.warning(msg)
            all_ok = False
        
        # NumPy (for measurements)
        try:
            import numpy
            self.print_status("numpy", True, f"v{numpy.__version__}")
        except ImportError:
            self.print_status("numpy", False, "Required for measurements")
            msg = "    → Install: pip install numpy"
            print(msg)
            if self.logger:
                self.logger.warning(msg)
            all_ok = False
        
        # SciPy (for Van der Pauw)
        try:
            import scipy
            self.print_status("scipy", True, f"v{scipy.__version__}")
        except ImportError:
            self.print_status("scipy", False, "Required for sigma calculation")
            msg = "    → Install: pip install scipy"
            print(msg)
            if self.logger:
                self.logger.warning(msg)
            all_ok = False
        
        # Matplotlib (for plotting)
        try:
            import matplotlib
            self.print_status("matplotlib", True, f"v{matplotlib.__version__}")
        except ImportError:
            self.print_status("matplotlib", False, "Required for plotting")
            msg = "    → Install: pip install matplotlib"
            print(msg)
            if self.logger:
                self.logger.warning(msg)
            all_ok = False
        
        # Pandas (for data export)
        try:
            import pandas
            self.print_status("pandas", True, f"v{pandas.__version__}")
        except ImportError:
            self.print_status("pandas", False, "Required for data export")
            msg = "    → Install: pip install pandas"
            print(msg)
            if self.logger:
                self.logger.warning(msg)
            all_ok = False
        
        self.results['dependencies'] = {'ok': all_ok}
        return all_ok
    
    def check_visa_backend(self) -> bool:
        """Check VISA backend availability."""
        self.print_header("VISA BACKEND CHECK")
        
        if not PYVISA_AVAILABLE:
            print("  ✗ PyVISA not installed, skipping...")
            self.results['visa_backend'] = {'ok': False, 'error': 'pyvisa not installed'}
            return False
        
        try:
            self.rm = pyvisa.ResourceManager()
            backend = self.rm.visalib
            self.print_status("VISA Library", True, str(backend))
            
            # List available resources
            resources = self.rm.list_resources()
            msg = f"\n  Available VISA resources ({len(resources)}):"
            print(msg)
            if self.logger:
                self.logger.info(f"Found {len(resources)} VISA resources")
            if resources:
                for res in resources:
                    print(f"    • {res}")
                    if self.logger:
                        self.logger.info(f"  Resource: {res}")
            else:
                print("    (none found)")
                if self.logger:
                    self.logger.warning("No VISA resources found")
            
            self.results['visa_backend'] = {'ok': True, 'resources': resources}
            return True
            
        except Exception as e:
            self.print_status("VISA Library", False, str(e))
            solutions = [
                "\n  Possible solutions:",
                "    1. Install NI-VISA: https://www.ni.com/visa",
                "    2. Install pyvisa-py: pip install pyvisa-py"
            ]
            for sol in solutions:
                print(sol)
                if self.logger:
                    self.logger.warning(sol)
            self.results['visa_backend'] = {'ok': False, 'error': str(e)}
            return False
    
    def check_daq6510(self) -> Tuple[bool, dict]:
        """
        Comprehensive check of Keithley DAQ6510.
        
        Tests:
        1. Connection
        2. Identity query (*IDN?)
        3. Self-test (*TST?)
        4. Error queue check
        5. Channel scan capability
        6. Response time
        """
        self.print_header("KEITHLEY DAQ6510 MULTIMETER")
        print(f"  Resource: {DAQ_RESOURCE}")
        
        result = {
            'ok': False,
            'connected': False,
            'identity': None,
            'self_test': None,
            'errors': [],
            'response_time_ms': None
        }
        
        if self.rm is None:
            print("  ✗ VISA not available")
            return False, result
        
        daq = None
        try:
            # Test 1: Connection
            print("\n  [1/6] Testing connection...")
            start = time.time()
            daq = self.rm.open_resource(DAQ_RESOURCE)
            daq.timeout = DAQ_TIMEOUT
            connect_time = (time.time() - start) * 1000
            self.print_status("Connection", True, f"{connect_time:.0f}ms")
            result['connected'] = True
            
            # Test 2: Identity
            print("  [2/6] Querying identity...")
            start = time.time()
            idn = daq.query('*IDN?').strip()
            response_time = (time.time() - start) * 1000
            result['identity'] = idn
            result['response_time_ms'] = response_time
            
            # Parse identity
            parts = idn.split(',')
            if len(parts) >= 4:
                manufacturer, model, serial, firmware = parts[0], parts[1], parts[2], parts[3]
                self.print_status("Identity", True)
                print(f"      Manufacturer: {manufacturer}")
                print(f"      Model: {model}")
                print(f"      Serial: {serial}")
                print(f"      Firmware: {firmware}")
                if self.logger:
                    self.logger.info(f"  Manufacturer: {manufacturer}, Model: {model}, Serial: {serial}, Firmware: {firmware}")
            else:
                self.print_status("Identity", True, idn)
                if self.logger:
                    self.logger.info(f"  Identity: {idn}")
            
            # Test 3: Self-test
            print("  [3/6] Running self-test (may take a moment)...")
            try:
                tst_result = daq.query('*TST?').strip()
                tst_ok = tst_result == '0'
                result['self_test'] = tst_ok
                self.print_status("Self-test", tst_ok, 
                                 "PASSED" if tst_ok else f"FAILED (code: {tst_result})")
            except Exception as e:
                self.print_status("Self-test", False, f"Timeout/Error: {e}")
                result['self_test'] = False
            
            # Test 4: Error queue
            print("  [4/6] Checking error queue...")
            errors = []
            for _ in range(10):  # Max 10 errors
                err = daq.query('SYST:ERR?').strip()
                if err.startswith('0,') or err.startswith('+0,'):
                    break
                errors.append(err)
            
            result['errors'] = errors
            if errors:
                self.print_status("Error queue", False, f"{len(errors)} error(s)")
                for err in errors:
                    msg = f"      → {err}"
                    print(msg)
                    if self.logger:
                        self.logger.error(f"  {err}")
            else:
                self.print_status("Error queue", True, "No errors")
            
            # Test 5: Channel scan test
            print("  [5/6] Testing channel scan capability...")
            try:
                daq.write('*RST')
                daq.write('ROUT:SCAN (@101)')
                daq.write('SENS:FUNC "VOLT:DC", (@101)')
                self.print_status("Channel scan", True, "Channel 101 configured")
            except Exception as e:
                self.print_status("Channel scan", False, str(e))
            
            # Test 6: Response time consistency
            print("  [6/6] Testing response consistency (5 queries)...")
            times = []
            for i in range(5):
                start = time.time()
                daq.query('*IDN?')
                times.append((time.time() - start) * 1000)
                time.sleep(0.1)
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)
            
            # Good if consistent (max < 2x min) and fast (avg < 500ms)
            consistent = max_time < (min_time * 2) and avg_time < 500
            self.print_status("Response time", consistent,
                            f"avg={avg_time:.0f}ms, min={min_time:.0f}ms, max={max_time:.0f}ms")
            
            # Overall result
            result['ok'] = result['connected'] and result['self_test'] and len(result['errors']) == 0
            
        except pyvisa.VisaIOError as e:
            self.print_status("Connection", False, f"VISA Error: {e.error_code}")
            msg = f"      {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"DAQ6510 VISA Error {e.error_code}: {e}")
        except Exception as e:
            self.print_status("Connection", False, str(e))
            if self.logger:
                self.logger.error(f"DAQ6510 Connection Error: {e}")
        finally:
            if daq:
                try:
                    daq.write('*RST')  # Reset to safe state
                    daq.close()
                except:
                    pass
        
        self.results['daq6510'] = result
        return result['ok'], result
    
    def check_power_supply(self) -> Tuple[bool, dict]:
        """
        Comprehensive check of Keithley 2230-30-1 Power Supply.
        
        Tests:
        1. Connection
        2. Identity query
        3. All channels controllable
        4. Output enable/disable
        5. Current/voltage readback
        """
        self.print_header("KEITHLEY 2230-30-1 POWER SUPPLY")
        print(f"  Resource: {PS_RESOURCE}")
        
        result = {
            'ok': False,
            'connected': False,
            'identity': None,
            'channels': {},
            'errors': []
        }
        
        if self.rm is None:
            print("  ✗ VISA not available")
            return False, result
        
        ps = None
        try:
            # Test 1: Connection
            print("\n  [1/5] Testing connection...")
            start = time.time()
            ps = self.rm.open_resource(PS_RESOURCE)
            ps.timeout = 5000
            connect_time = (time.time() - start) * 1000
            self.print_status("Connection", True, f"{connect_time:.0f}ms")
            result['connected'] = True
            
            # Test 2: Identity
            print("  [2/5] Querying identity...")
            idn = ps.query('*IDN?').strip()
            result['identity'] = idn
            parts = idn.split(',')
            if len(parts) >= 4:
                self.print_status("Identity", True)
                print(f"      Manufacturer: {parts[0]}")
                print(f"      Model: {parts[1]}")
                print(f"      Serial: {parts[2]}")
                print(f"      Firmware: {parts[3]}")
            else:
                self.print_status("Identity", True, idn)
            
            # Test 3: Reset to safe state
            print("  [3/5] Resetting to safe state...")
            ps.write('*RST')
            time.sleep(0.5)
            self.print_status("Reset", True)
            
            # Test 4: Check all channels
            print("  [4/5] Testing channel control...")
            channels_ok = True
            for ch in ['CH1', 'CH2', 'CH3']:
                try:
                    ps.write(f':INST:SEL {ch}')
                    ps.write(':SOUR:VOLT 0')
                    ps.write(':SOUR:CURR 0')
                    
                    # Read back
                    volt = ps.query(':SOUR:VOLT?').strip()
                    curr = ps.query(':SOUR:CURR?').strip()
                    
                    result['channels'][ch] = {
                        'voltage_setpoint': float(volt),
                        'current_setpoint': float(curr)
                    }
                    self.print_status(f"{ch}", True, f"V={volt}V, I={curr}A")
                except Exception as e:
                    self.print_status(f"{ch}", False, str(e))
                    channels_ok = False
            
            # Test 5: Output control
            print("  [5/5] Testing output control...")
            try:
                ps.write(':INST:SEL CH3')
                ps.write(':OUTP:STAT ON')
                time.sleep(0.2)
                state_on = ps.query(':OUTP:STAT?').strip()
                
                ps.write(':OUTP:STAT OFF')
                time.sleep(0.2)
                state_off = ps.query(':OUTP:STAT?').strip()
                
                output_ok = ('1' in state_on or 'ON' in state_on.upper()) and \
                           ('0' in state_off or 'OFF' in state_off.upper())
                self.print_status("Output control", output_ok, 
                                 f"ON→{state_on}, OFF→{state_off}")
            except Exception as e:
                self.print_status("Output control", False, str(e))
                output_ok = False
            
            result['ok'] = result['connected'] and channels_ok and output_ok
            
        except pyvisa.VisaIOError as e:
            self.print_status("Connection", False, f"VISA Error: {e.error_code}")
            msg = f"      {e}"
            print(msg)
            if self.logger:
                self.logger.error(f"Power Supply VISA Error {e.error_code}: {e}")
        except Exception as e:
            self.print_status("Connection", False, str(e))
            if self.logger:
                self.logger.error(f"Power Supply Connection Error: {e}")
        finally:
            if ps:
                try:
                    # Ensure outputs are OFF
                    ps.write('*RST')
                    ps.close()
                except:
                    pass
        
        self.results['power_supply'] = result
        return result['ok'], result
    
    def check_eurotherm(self) -> Tuple[bool, dict]:
        """
        Check Eurotherm temperature controller via MODBUS.
        
        Tests:
        1. Serial port available
        2. MODBUS communication
        3. Read process value (temperature)
        4. Read setpoint
        5. Response consistency
        """
        self.print_header("EUROTHERM TEMPERATURE CONTROLLER")
        print(f"  Port: COM{EUROTHERM_COM_PORT}")
        print(f"  MODBUS Address: {EUROTHERM_DEVICE_ADDRESS}")
        print(f"  Baud Rate: {EUROTHERM_BAUD_RATE}")
        
        result = {
            'ok': False,
            'connected': False,
            'temperature': None,
            'setpoint': None,
            'response_time_ms': None
        }
        
        if not SERIAL_AVAILABLE:
            print("\n  ✗ pyserial not installed")
            return False, result
        
        # Import CRC function from eurotherm module
        try:
            from eurotherm_control import calculate_crc16, append_crc16, verify_crc16
        except ImportError:
            print("\n  ✗ eurotherm_control.py not found")
            return False, result
        
        ser = None
        try:
            # Test 1: Open serial port
            print("\n  [1/5] Opening serial port...")
            port_name = f'COM{EUROTHERM_COM_PORT}'
            ser = serial.Serial(
                port=port_name,
                baudrate=EUROTHERM_BAUD_RATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0
            )
            self.print_status("Serial port", True, port_name)
            result['connected'] = True
            
            # Helper to read MODBUS register
            def read_register(register: int) -> Optional[float]:
                """Read a 32-bit float from Eurotherm using full-resolution addressing."""
                addr = EUROTHERM_DEVICE_ADDRESS
                full_addr = (register * 2) + 0x8000  # Eurotherm full-resolution
                
                # Build MODBUS read request (function code 3)
                request = bytes([
                    addr,           # Device address
                    0x03,           # Function code: read holding registers
                    (full_addr >> 8) & 0xFF,
                    full_addr & 0xFF,
                    0x00, 0x02      # Read 2 registers (32-bit float)
                ])
                request = append_crc16(request)
                
                ser.reset_input_buffer()
                ser.write(request)
                time.sleep(0.1)
                
                response = ser.read(9)  # addr + func + byte_count + 4 data + 2 CRC
                if len(response) < 9:
                    return None
                
                if not verify_crc16(response):
                    return None
                
                # Extract 32-bit float (big-endian)
                import struct
                raw_bytes = response[3:7]
                value = struct.unpack('>f', raw_bytes)[0]
                return value
            
            # Test 2: Read process value (temperature)
            print("  [2/5] Reading process value (temperature)...")
            start = time.time()
            pv = read_register(1)  # Register 1 = PV
            response_time = (time.time() - start) * 1000
            
            if pv is not None:
                result['temperature'] = pv
                result['response_time_ms'] = response_time
                self.print_status("Process Value", True, f"{pv:.1f}°C ({response_time:.0f}ms)")
            else:
                self.print_status("Process Value", False, "No valid response")
            
            # Test 3: Read setpoint
            print("  [3/5] Reading setpoint...")
            sp = read_register(2)  # Register 2 = SP
            if sp is not None:
                result['setpoint'] = sp
                self.print_status("Setpoint", True, f"{sp:.1f}°C")
            else:
                self.print_status("Setpoint", False, "No valid response")
            
            # Test 4: Read output power
            print("  [4/5] Reading heater output...")
            output = read_register(3)  # Register 3 = Output
            if output is not None:
                self.print_status("Heater Output", True, f"{output:.1f}%")
            else:
                self.print_status("Heater Output", False, "No valid response")
            
            # Test 5: Response consistency
            print("  [5/5] Testing response consistency (5 reads)...")
            times = []
            temps = []
            for _ in range(5):
                start = time.time()
                t = read_register(1)
                times.append((time.time() - start) * 1000)
                if t is not None:
                    temps.append(t)
                time.sleep(0.2)
            
            if temps:
                avg_time = sum(times) / len(times)
                temp_spread = max(temps) - min(temps)
                consistent = temp_spread < 1.0 and avg_time < 500
                self.print_status("Consistency", consistent,
                                f"avg={avg_time:.0f}ms, temp spread={temp_spread:.2f}°C")
            else:
                self.print_status("Consistency", False, "No valid readings")
            
            result['ok'] = result['temperature'] is not None and result['setpoint'] is not None
            
        except serial.SerialException as e:
            self.print_status("Serial port", False, str(e))
            causes = [
                f"\n  Possible causes:",
                f"    • COM{EUROTHERM_COM_PORT} not available",
                f"    • Port in use by another program",
                f"    • Wrong port number (check Device Manager)"
            ]
            for cause in causes:
                print(cause)
                if self.logger:
                    self.logger.warning(cause)
        except Exception as e:
            self.print_status("Communication", False, str(e))
            if self.logger:
                self.logger.error(f"Eurotherm Error: {e}")
        finally:
            if ser and ser.is_open:
                ser.close()
        
        self.results['eurotherm'] = result
        return result['ok'], result
    
    def run_stress_test(self, duration_seconds: int = 30) -> bool:
        """
        Run a brief stress test to check instrument stability.
        
        Rapidly queries all instruments to check for:
        - Communication timeouts
        - Response degradation
        - Connection drops
        """
        self.print_header(f"STRESS TEST ({duration_seconds} seconds)")
        
        if not all([
            self.results.get('daq6510', {}).get('ok'),
            self.results.get('power_supply', {}).get('ok')
        ]):
            print("  ⚠ Skipping stress test - not all VISA instruments passed basic tests")
            return False
        
        print("  Rapidly querying instruments to test stability...")
        print("  Press Ctrl+C to stop early\n")
        
        daq = None
        ps = None
        
        try:
            daq = self.rm.open_resource(DAQ_RESOURCE)
            ps = self.rm.open_resource(PS_RESOURCE)
            daq.timeout = DAQ_TIMEOUT
            ps.timeout = 5000
            
            start_time = time.time()
            daq_queries = 0
            ps_queries = 0
            daq_errors = 0
            ps_errors = 0
            
            while (time.time() - start_time) < duration_seconds:
                # Query DAQ
                try:
                    daq.query('*IDN?')
                    daq_queries += 1
                except:
                    daq_errors += 1
                
                # Query PS
                try:
                    ps.query('*IDN?')
                    ps_queries += 1
                except:
                    ps_errors += 1
                
                # Progress update
                elapsed = time.time() - start_time
                sys.stdout.write(f"\r  Progress: {elapsed:.0f}s | DAQ: {daq_queries} ok, {daq_errors} err | PS: {ps_queries} ok, {ps_errors} err")
                sys.stdout.flush()
                
                time.sleep(0.1)
            
            print("\n")
            
            # Results
            total_time = time.time() - start_time
            daq_rate = daq_queries / total_time
            ps_rate = ps_queries / total_time
            
            daq_ok = daq_errors == 0
            ps_ok = ps_errors == 0
            
            self.print_status("DAQ6510", daq_ok, 
                            f"{daq_queries} queries, {daq_errors} errors, {daq_rate:.1f} q/s")
            self.print_status("Power Supply", ps_ok,
                            f"{ps_queries} queries, {ps_errors} errors, {ps_rate:.1f} q/s")
            
            return daq_ok and ps_ok
            
        except KeyboardInterrupt:
            print("\n\n  Stress test interrupted by user")
            return False
        except Exception as e:
            print(f"\n  Stress test error: {e}")
            return False
        finally:
            if daq:
                try:
                    daq.close()
                except:
                    pass
            if ps:
                try:
                    ps.close()
                except:
                    pass
    
    def print_summary(self):
        """Print overall summary of all checks."""
        self.print_header("SUMMARY")
        
        all_ok = True
        
        # Dependencies
        dep_ok = self.results.get('dependencies', {}).get('ok', False)
        self.print_status("Dependencies", dep_ok)
        all_ok = all_ok and dep_ok
        
        # VISA
        visa_ok = self.results.get('visa_backend', {}).get('ok', False)
        self.print_status("VISA Backend", visa_ok)
        all_ok = all_ok and visa_ok
        
        # DAQ
        daq_ok = self.results.get('daq6510', {}).get('ok', False)
        self.print_status("DAQ6510 Multimeter", daq_ok)
        all_ok = all_ok and daq_ok
        
        # Power Supply
        ps_ok = self.results.get('power_supply', {}).get('ok', False)
        self.print_status("Power Supply", ps_ok)
        all_ok = all_ok and ps_ok
        
        eurotherm_ok = self.results.get('eurotherm', {}).get('ok', False)
        eurotherm_tested = 'eurotherm' in self.results
        if eurotherm_tested:
            self.print_status("Eurotherm Controller", eurotherm_ok, 
                            "")
        
        print("\n" + "=" * 60)
        if all_ok:
            print(" ✓ ALL CORE INSTRUMENTS READY")
            if eurotherm_tested and eurotherm_ok:
                print(" ✓ TEMPERATURE SWEEP CAPABLE")
            elif eurotherm_tested and not eurotherm_ok:
                print(" ⚠ Temperature sweep NOT available (Eurotherm issue)")
        else:
            print(" ✗ SOME INSTRUMENTS HAVE ISSUES - CHECK ABOVE")
        print("=" * 60)
        
        return all_ok


def main():
    """Run comprehensive instrument diagnostics."""
    
    print("\n" + "=" * 60)
    print(" INSTRUMENT HEALTH CHECK & DIAGNOSTICS")
    print(" " + datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
    print("=" * 60)
    
    checker = InstrumentChecker()
    
    # Setup logging
    log_file = checker.setup_logging()
    print(f"\n📝 Logging to: {log_file}\n")
    
    # Run all checks
    checker.check_dependencies()
    checker.check_visa_backend()
    checker.check_daq6510()
    checker.check_power_supply()
    
    # Ask about Eurotherm
    print("\n")
    check_eurotherm = input("Check Eurotherm temperature controller? (y/n) [default: y]: ").strip().lower()
    if check_eurotherm != 'n':
        checker.check_eurotherm()
    
    # Ask about stress test
    print("\n")
    run_stress = input("Run stress test (30 seconds)? (y/n) [default: n]: ").strip().lower()
    if run_stress == 'y':
        checker.run_stress_test(30)
    
    # Print summary
    all_ok = checker.print_summary()
    
    # Finalize log
    if checker.logger:
        checker.logger.info("="*60)
        checker.logger.info(f"Check completed: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
        checker.logger.info(f"Overall result: {'PASSED' if all_ok else 'FAILED'}")
        checker.logger.info("="*60)
        
        # Close handlers
        for handler in checker.logger.handlers:
            handler.close()
            checker.logger.removeHandler(handler)
    
    print(f"\n📝 Full log saved to: {checker.log_file}")
    
    # Return exit code
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
