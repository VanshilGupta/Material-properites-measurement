"""
Eurotherm Temperature Controller Interface

Python module for controlling Eurotherm Series 2000/3000 temperature controllers
via RS-232 serial communication using MODBUS protocol.

Converted from MATLAB reference code for integration with the 
Thermoelectric Material Properties Measurement System.

Key Features:
- Connect/disconnect to Eurotherm via COM port
- Read current temperature
- Set target temperature
- Set ramp rate (°C/min)
- Wait for temperature stabilization
- Auto/Manual mode control
"""

import serial
import struct
import time
import logging
from typing import Optional, Tuple, List


# =============================================================================
# CRC-16 MODBUS Calculation
# =============================================================================

def calculate_crc16(data: bytes) -> int:
    """
    Calculate CRC-16 MODBUS checksum.
    
    Args:
        data: Bytes to calculate CRC for
        
    Returns:
        CRC-16 value as integer
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def append_crc16(data: bytes) -> bytes:
    """Append CRC-16 checksum to data."""
    crc = calculate_crc16(data)
    return data + struct.pack('<H', crc)  # Little-endian CRC


def verify_crc16(data: bytes) -> bool:
    """Verify CRC-16 checksum of received data."""
    if len(data) < 3:
        return False
    message = data[:-2]
    received_crc = struct.unpack('<H', data[-2:])[0]
    calculated_crc = calculate_crc16(message)
    return received_crc == calculated_crc


# =============================================================================
# Eurotherm Controller Class
# =============================================================================

class EurothermController:
    """
    Controller class for Eurotherm temperature controllers.
    
    Communicates via MODBUS RTU protocol over RS-232 serial port.
    
    Example Usage:
        controller = EurothermController(com_port=5)
        controller.connect()
        
        # Read current temperature
        temp = controller.read_temperature()
        print(f"Current: {temp}°C")
        
        # Set target and wait
        controller.set_temperature(100.0)
        controller.set_ramp_rate(10.0)  # 10°C/min
        controller.wait_for_stability(target=100.0, tolerance=1.0)
        
        controller.disconnect()
    """
    
    # MODBUS Register Addresses (Eurotherm specific)
    REG_PROCESS_VALUE = 1      # Current temperature (PV)
    REG_SETPOINT = 2           # Target temperature (SP)
    REG_OUTPUT_POWER = 3       # Output power %
    REG_RAMP_RATE = 35         # Setpoint ramp rate (°C/min)
    REG_AUTO_MANUAL = 273      # Auto/Manual mode (0=Auto, 1=Manual)
    
    # MODBUS RTU inter-frame delay — 50 ms provides a safe margin above the
    # 3.5-character-time minimum (~3.6 ms at 9600 baud) and matches the
    # effective pause in the MATLAB reference code once interpreter overhead
    # is accounted for.
    MODBUS_INTER_FRAME_DELAY = 0.05  # seconds
    
    # Retry settings for MODBUS read operations
    MAX_READ_RETRIES = 3
    RETRY_DELAY = 0.1  # seconds between retries
    
    def __init__(
        self,
        com_port: int = 5,
        device_address: int = 1,
        baud_rate: int = 9600,
        timeout: float = 2.0
    ):
        """
        Initialize Eurotherm controller.
        
        Args:
            com_port: COM port number (e.g., 5 for COM5)
            device_address: MODBUS device address (default: 1)
            baud_rate: Serial baud rate (default: 9600)
            timeout: Serial timeout in seconds (default: 2.0)
        """
        self.com_port = com_port
        self.device_address = device_address
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None
        self.logger: Optional[logging.Logger] = None
        self._connected = False
    
    def set_logger(self, logger: logging.Logger):
        """Set logger for this controller."""
        self.logger = logger
    
    def _log(self, level: str, message: str):
        """Log message if logger available."""
        if self.logger:
            getattr(self.logger, level, self.logger.info)(message)
    
    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------
    
    def connect(self) -> bool:
        """
        Connect to the Eurotherm controller.
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            port_name = f"COM{self.com_port}"
            self.serial = serial.Serial(
                port=port_name,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self._connected = True
            self._log('info', f"Connected to Eurotherm on {port_name}")
            
            # Verify connection by reading temperature
            temp = self.read_temperature()
            if temp is not None:
                self._log('info', f"Current temperature: {temp:.1f}°C")
                return True
            else:
                self._log('warning', "Connected but could not read temperature")
                return True
                
        except serial.SerialException as e:
            self._log('error', f"Failed to connect to COM{self.com_port}: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the Eurotherm controller."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            self._log('info', "Disconnected from Eurotherm")
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if controller is connected."""
        return self._connected and self.serial and self.serial.is_open
    
    # -------------------------------------------------------------------------
    # Low-Level MODBUS Communication
    # -------------------------------------------------------------------------
    
    def _flush(self):
        """Flush serial input buffer before a new transaction.
        
        Only the *input* buffer is cleared so that stale response bytes
        from a previous transaction do not corrupt the next read.  The
        output buffer is intentionally left alone — purging it on Windows
        can discard bytes that the OS has accepted but not yet
        transmitted, causing the Eurotherm to receive a truncated frame.
        """
        if self.serial:
            self.serial.reset_input_buffer()
    
    def _read_registers(self, register: int, count: int = 1) -> Optional[list]:
        """
        Read holding registers using MODBUS function code 3.
        
        Automatically retries up to ``MAX_READ_RETRIES`` times on failure.
        
        Args:
            register: Starting register address
            count: Number of registers to read
            
        Returns:
            List of register values or None if failed
        """
        if not self.is_connected():
            return None
        
        # Build MODBUS request: [addr, func(3), reg_hi, reg_lo, count_hi, count_lo]
        # Eurotherm parameter addresses are sent as-is (no subtraction)
        # per the MATLAB tempobjcomm reference implementation
        request = struct.pack('>BBHH', 
                              self.device_address, 
                              3,  # Function code: Read Holding Registers
                              register,
                              count)
        request = append_crc16(request)
        
        # Response: [addr, func, byte_count, data..., crc_lo, crc_hi]
        # Expected length: 3 + (count * 2) + 2 = 5 + count*2
        response_len = 5 + count * 2
        
        for attempt in range(self.MAX_READ_RETRIES):
            try:
                self._flush()
                self.serial.write(request)
                
                response = self.serial.read(response_len)
                
                if len(response) < response_len:
                    self._log('warning',
                              f"Register read incomplete: got {len(response)}/{response_len} bytes "
                              f"(reg={register}, attempt {attempt + 1}/{self.MAX_READ_RETRIES})")
                    time.sleep(self.RETRY_DELAY)
                    continue
                
                if not verify_crc16(response):
                    self._log('warning',
                              f"CRC mismatch on register read "
                              f"(reg={register}, attempt {attempt + 1}/{self.MAX_READ_RETRIES})")
                    time.sleep(self.RETRY_DELAY)
                    continue
                
                # Check for Eurotherm error response (function code + 0x80)
                if response[1] == (3 + 0x80):
                    error_code = response[2] if len(response) > 2 else -1
                    self._log('warning',
                              f"Eurotherm error response code {error_code} for register {register}")
                    return None  # No point retrying a device-level error
                
                # Parse values (big-endian 16-bit integers)
                values = []
                for i in range(count):
                    offset = 3 + i * 2
                    value = struct.unpack('>H', response[offset:offset+2])[0]
                    values.append(value)
                
                return values
                
            except Exception as e:
                self._log('warning', f"Register read exception (attempt {attempt + 1}): {e}")
                time.sleep(self.RETRY_DELAY)
            finally:
                time.sleep(self.MODBUS_INTER_FRAME_DELAY)
        
        self._log('warning', f"Register read failed after {self.MAX_READ_RETRIES} attempts (reg={register})")
        return None
    
    def _read_float(self, register: int) -> Optional[float]:
        """
        Read a full-resolution floating point value.
        
        Uses the Eurotherm full-resolution addressing (register*2 + 0x8000).
        Automatically retries up to ``MAX_READ_RETRIES`` times on failure.
        
        Args:
            register: Register address
            
        Returns:
            Float value or None if failed
        """
        if not self.is_connected():
            return None
        
        # Full resolution address calculation (from MATLAB code)
        # Address = parameterAddress * 2 + 0x8000 (sent as-is, no subtraction)
        full_res_addr = register * 2 + 0x8000
        
        # Build request for 2 registers (4 bytes = 1 float)
        request = struct.pack('>BBHH',
                              self.device_address,
                              3,  # Read Holding Registers
                              full_res_addr,
                              2)  # Read 2 registers for float
        request = append_crc16(request)
        
        for attempt in range(self.MAX_READ_RETRIES):
            try:
                self._flush()
                self.serial.write(request)
                
                # Response: addr(1) + func(1) + count(1) + data(4) + crc(2) = 9 bytes
                response = self.serial.read(9)
                
                if len(response) < 9:
                    self._log('warning',
                              f"Float read incomplete: got {len(response)}/9 bytes "
                              f"(reg={register}, attempt {attempt + 1}/{self.MAX_READ_RETRIES})")
                    time.sleep(self.RETRY_DELAY)
                    continue
                
                if not verify_crc16(response):
                    self._log('warning',
                              f"CRC mismatch on float read "
                              f"(reg={register}, attempt {attempt + 1}/{self.MAX_READ_RETRIES})")
                    time.sleep(self.RETRY_DELAY)
                    continue
                
                # Check for Eurotherm error response (function code + 0x80)
                if response[1] == (3 + 0x80):
                    error_code = response[2] if len(response) > 2 else -1
                    self._log('warning',
                              f"Eurotherm error response code {error_code} for register {register}")
                    return None  # No point retrying a device-level error
                
                # Validate response header: device address and function code
                if response[0] != self.device_address or response[1] != 3:
                    self._log('warning',
                              f"Unexpected response header: addr={response[0]}, func={response[1]} "
                              f"(expected addr={self.device_address}, func=3)")
                    time.sleep(self.RETRY_DELAY)
                    continue
                
                # Extract 4 bytes and convert to float (big-endian)
                float_bytes = response[3:7]
                value = struct.unpack('>f', float_bytes)[0]
                
                return value
                
            except Exception as e:
                self._log('warning', f"Float read exception (attempt {attempt + 1}): {e}")
                time.sleep(self.RETRY_DELAY)
            finally:
                time.sleep(self.MODBUS_INTER_FRAME_DELAY)
        
        self._log('warning', f"Float read failed after {self.MAX_READ_RETRIES} attempts (reg={register})")
        return None
    
    def _write_float(self, register: int, value: float) -> bool:
        """
        Write a full-resolution floating point value.
        
        Args:
            register: Register address
            value: Float value to write
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        # Full resolution address calculation
        # Address = parameterAddress * 2 + 0x8000 (sent as-is, no subtraction)
        full_res_addr = register * 2 + 0x8000
        
        # Convert float to bytes (big-endian)
        float_bytes = struct.pack('>f', value)
        
        # Build MODBUS write multiple registers request (function code 16)
        # [addr, func(16), reg_hi, reg_lo, count_hi, count_lo, byte_count, data...]
        request = struct.pack('>BBHHB',
                              self.device_address,
                              16,  # Write Multiple Registers
                              full_res_addr,
                              2,   # 2 registers
                              4)   # 4 bytes
        request += float_bytes
        request = append_crc16(request)
        
        try:
            self._flush()
            self.serial.write(request)
            
            # Response: addr(1) + func(1) + reg(2) + count(2) + crc(2) = 8 bytes
            response = self.serial.read(8)
            
            if len(response) < 8:
                self._log('warning', f"Write float incomplete response: got {len(response)}/8 bytes (reg={register})")
                return False
            
            if not verify_crc16(response):
                self._log('warning', f"Write float CRC mismatch (reg={register})")
                return False
            
            return True
            
        except Exception as e:
            self._log('warning', f"Write float error: {e}")
            return False
        finally:
            time.sleep(self.MODBUS_INTER_FRAME_DELAY)
    
    def _write_register(self, register: int, value: int) -> bool:
        """
        Write a single 16-bit register using MODBUS function code 16.
        
        Eurotherm recommends FC 16 (Write Multiple Registers) for all
        write operations, matching the MATLAB tempobjcomm reference.
        
        Args:
            register: Register address
            value: Integer value to write (0-65535)
            
        Returns:
            True if successful
        """
        if not self.is_connected():
            return False
        
        # FC 16: [addr, 16, reg_hi, reg_lo, count_hi, count_lo, byte_count, val_hi, val_lo]
        # Address sent as-is (no subtraction), per MATLAB tempobjcomm
        request = struct.pack('>BBHHBH',
                              self.device_address,
                              16,  # Write Multiple Registers (Eurotherm recommended)
                              register,
                              1,   # 1 register
                              2,   # 2 bytes
                              value)
        request = append_crc16(request)
        
        try:
            self._flush()
            self.serial.write(request)
            response = self.serial.read(8)
            
            if len(response) < 8:
                self._log('warning', f"Write register incomplete response: got {len(response)}/8 bytes (reg={register})")
                return False
            if not verify_crc16(response):
                self._log('warning', f"Write register CRC mismatch (reg={register})")
                return False
            return True
        except Exception as e:
            self._log('warning', f"Write register error: {e}")
            return False
        finally:
            time.sleep(self.MODBUS_INTER_FRAME_DELAY)
    
    # -------------------------------------------------------------------------
    # High-Level Temperature Control Functions
    # -------------------------------------------------------------------------
    
    def read_temperature(self) -> Optional[float]:
        """
        Read current process temperature.
        
        Returns:
            Current temperature in °C or None if failed
        """
        return self._read_float(self.REG_PROCESS_VALUE)
    
    def read_setpoint(self) -> Optional[float]:
        """
        Read current setpoint temperature.
        
        Returns:
            Setpoint temperature in °C or None if failed
        """
        return self._read_float(self.REG_SETPOINT)
    
    def set_temperature(self, temperature: float) -> bool:
        """
        Set target temperature.
        
        Args:
            temperature: Target temperature in °C
            
        Returns:
            True if successful
        """
        success = self._write_float(self.REG_SETPOINT, temperature)
        if success:
            self._log('info', f"Set target temperature: {temperature}°C")
        else:
            self._log('error', f"Failed to set temperature to {temperature}°C")
        return success
    
    def read_ramp_rate(self) -> Optional[float]:
        """
        Read current ramp rate.
        
        Returns:
            Ramp rate in °C/min or None if failed
        """
        return self._read_float(self.REG_RAMP_RATE)
    
    def set_ramp_rate(self, rate: float) -> bool:
        """
        Set temperature ramp rate.
        
        Args:
            rate: Ramp rate in °C/min (0 = instant, max typically 99.9)
            
        Returns:
            True if successful
        """
        success = self._write_float(self.REG_RAMP_RATE, rate)
        if success:
            self._log('info', f"Set ramp rate: {rate}°C/min")
        return success
    
    def read_output_power(self) -> Optional[float]:
        """
        Read current output power percentage.
        
        Returns:
            Output power in % or None if failed
        """
        return self._read_float(self.REG_OUTPUT_POWER)
    
    def set_auto_mode(self) -> bool:
        """Set controller to automatic (PID) mode."""
        success = self._write_register(self.REG_AUTO_MANUAL, 0)
        if success:
            self._log('info', "Set to AUTO mode")
        return success
    
    def set_manual_mode(self) -> bool:
        """Set controller to manual mode."""
        success = self._write_register(self.REG_AUTO_MANUAL, 1)
        if success:
            self._log('info', "Set to MANUAL mode")
        return success
    
    def is_auto_mode(self) -> bool:
        """Check if controller is in auto mode."""
        result = self._read_registers(self.REG_AUTO_MANUAL, 1)
        return result is not None and result[0] == 0
    
    # -------------------------------------------------------------------------
    # Temperature Stabilization
    # -------------------------------------------------------------------------
    
    def wait_for_stability(
        self,
        target: float,
        tolerance: float = 1.0,
        stable_time: float = 60.0,
        timeout: float = 1800.0,
        check_interval: float = 5.0
    ) -> bool:
        """
        Wait for temperature to stabilize at target.
        
        Args:
            target: Target temperature in °C
            tolerance: Acceptable deviation from target (°C)
            stable_time: Time temperature must stay within tolerance (seconds)
            timeout: Maximum wait time (seconds)
            check_interval: Time between temperature checks (seconds)
            
        Returns:
            True if temperature stabilized, False if timeout
        """
        self._log('info', f"Waiting for temperature to stabilize at {target}°C (±{tolerance}°C)...")
        
        start_time = time.time()
        stable_start = None
        
        while (time.time() - start_time) < timeout:
            current_temp = self.read_temperature()
            
            if current_temp is None:
                self._log('warning', "Failed to read temperature, retrying...")
                time.sleep(check_interval)
                continue
            
            deviation = abs(current_temp - target)
            
            if deviation <= tolerance:
                if stable_start is None:
                    stable_start = time.time()
                    self._log('info', f"Temperature within tolerance: {current_temp:.1f}°C")
                
                stable_duration = time.time() - stable_start
                
                if stable_duration >= stable_time:
                    self._log('info', f"Temperature STABLE at {current_temp:.1f}°C for {stable_duration:.0f}s")
                    return True
            else:
                stable_start = None
            
            time.sleep(check_interval)
        
        self._log('error', f"Timeout waiting for temperature stabilization")
        return False
    
    def get_status(self) -> dict:
        """
        Get comprehensive controller status.
        
        Returns:
            Dictionary with current state
        """
        return {
            'temperature': self.read_temperature(),
            'setpoint': self.read_setpoint(),
            'output_power': self.read_output_power(),
            'ramp_rate': self.read_ramp_rate(),
            'auto_mode': self.is_auto_mode(),
            'connected': self.is_connected()
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def get_temperature_range_from_user() -> Tuple[float, float, float, float]:
    """
    Prompt user for temperature sweep parameters.
    
    Returns:
        Tuple of (start_temp, end_temp, step_temp, ramp_rate)
    """
    print("\n" + "="*60)
    print("TEMPERATURE SWEEP CONFIGURATION")
    print("="*60)
    
    try:
        start_temp = float(input("Enter START temperature (°C) [default: 50]: ").strip() or "50")
        end_temp = float(input("Enter END temperature (°C) [default: 200]: ").strip() or "200")
        step_temp = float(input("Enter STEP size (°C) [default: 25]: ").strip() or "25")
        ramp_rate = float(input("Enter RAMP rate (°C/min) [default: 10]: ").strip() or "10")
    except ValueError:
        print("Invalid input, using defaults")
        start_temp, end_temp, step_temp, ramp_rate = 50.0, 200.0, 25.0, 10.0
    
    print(f"\nTemperature sweep: {start_temp}°C → {end_temp}°C (step: {step_temp}°C)")
    print(f"Ramp rate: {ramp_rate}°C/min")
    print("="*60)
    
    return start_temp, end_temp, step_temp, ramp_rate


def generate_temperature_list(start: float, end: float, step: float) -> list:
    """
    Generate list of temperatures for sweep.
    
    Args:
        start: Starting temperature
        end: Ending temperature
        step: Step size
        
    Returns:
        List of temperatures
    """
    temperatures = []
    current = start
    
    if start <= end:
        while current <= end + 0.001:  # Small tolerance for float comparison
            temperatures.append(round(current, 1))
            current += step
    else:
        while current >= end - 0.001:
            temperatures.append(round(current, 1))
            current -= step
    
    return temperatures


# =============================================================================
# Test Function
# =============================================================================

if __name__ == "__main__":
    # Simple test
    print("Eurotherm Controller Test")
    print("="*40)
    
    com_port = int(input("Enter COM port number [default: 5]: ").strip() or "5")
    
    controller = EurothermController(com_port=com_port)
    
    if controller.connect():
        print("\n--- Status ---")
        status = controller.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        print("\n--- Test Commands ---")
        test_temp = input("Enter test setpoint (or Enter to skip): ").strip()
        if test_temp:
            controller.set_temperature(float(test_temp))
            time.sleep(2)
            print(f"New setpoint: {controller.read_setpoint()}°C")
        
        controller.disconnect()
    else:
        print("Failed to connect!")
