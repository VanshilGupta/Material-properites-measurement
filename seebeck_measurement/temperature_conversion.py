"""Temperature-voltage conversion utilities for Type K thermocouples."""

import numpy as np


def temp_to_voltage(temperature: float) -> float:
    """
    Convert temperature to voltage for Type K thermocouple.
    
    Valid for temperatures above 0°C using polynomial + exponential.
    
    Args:
        temperature: Temperature in Celsius
        
    Returns:
        Voltage in millivolts
    """
    c = np.array([
        0.389212049750E-01,
        0.185587700320E-04,
        -0.994575928740E-07,
        0.318409457190E-09,
        -0.560728448890E-12,
        0.560750590590E-15,
        -0.320207200030E-18,
        0.971511471520E-22,
        -0.121047212750E-25
    ])
    
    a0 = 0.118597600000E+00
    a1 = -0.118343200000E-03
    a2 = 0.126968600000E+03
    
    voltage = -0.176004136860E-01
    
    for i, coeff in enumerate(c, start=1):
        voltage += coeff * (temperature ** i)
    
    voltage += a0 * np.exp(a1 * (temperature - a2) ** 2)
    
    return voltage


def voltage_to_temp(voltage: float) -> float:
    """
    Convert voltage to temperature for Type K thermocouple.
    
    Args:
        voltage: Voltage in millivolts
        
    Returns:
        Temperature in Celsius
    """
    d = np.array([
        2.508355e1,
        7.860106e-2,
        -2.503131e-1,
        8.315270e-2,
        -1.228034e-2,
        9.804036e-4,
        -4.413030e-5,
        1.057734e-6,
        -1.052755e-8
    ])
    
    temperature = 0.0
    for i, coeff in enumerate(d, start=1):
        temperature += coeff * (voltage ** i)
    
    return temperature
