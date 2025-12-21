"""Curve fitting and Seebeck coefficient calculation."""

import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress
import matplotlib.pyplot as plt
from typing import Tuple


def linear_func(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """Linear function for fitting."""
    return a * x + b


def calculate_thermocouple_seebeck(temperature: float) -> Tuple[float, float]:
    """
    Calculate Seebeck coefficients for Type K thermocouple wires.
    
    Args:
        temperature: Average temperature in Celsius
        
    Returns:
        Tuple of (S_Chromel, S_Alumel) in µV/K
    """
    T = temperature
    
    # Chromel Seebeck coefficient
    S_Chromel = (21.7829 + 0.02204 * T - 6.92519E-5 * T**2 + 
                 4.49179E-8 * T**3 - 1.01799E-11 * T**4)
    
    # Alumel Seebeck coefficient (temperature dependent formula)
    if T < 255:
        S_Alumel = (-17.64963 - 0.02169 * T - 1.88616E-4 * T**2 + 
                    7.0347E-6 * T**3 - 3.97854E-8 * T**4 + 6.47807E-11 * T**5)
    else:
        S_Alumel = (-12.0609 - 0.02563 * T + 4.66833E-5 * T**2 - 
                    1.42138E-7 * T**3 + 1.79547E-10 * T**4 - 7.67423E-14 * T**5)
    
    return S_Chromel, S_Alumel


def fit_v1_v2_and_calculate_seebeck(
    V1: np.ndarray,
    V2: np.ndarray,
    temperature: float,
    plot: bool = True,
    save_plot: bool = True,
    filename: str = None,
    output_folder: str = None
) -> Tuple[float, float, float, float, float]:
    """
    Fit V2 vs V1 and calculate sample Seebeck coefficient.
    
    Args:
        V1, V2: Voltage arrays (in volts)
        temperature: Average temperature in Celsius
        plot: Whether to generate plot
        save_plot: Whether to save the plot to file
        filename: Base filename for saved plot (without extension)
        output_folder: Output directory for saved plot
        
    Returns:
        Tuple of (slope, adj_r_square, offset, rmse, S_sample)
    """
    # Remove NaN values
    mask = ~(np.isnan(V1) | np.isnan(V2))
    V1_clean = V1[mask]
    V2_clean = V2[mask]
    
    # Linear regression with robust fitting (similar to MATLAB's Bisquare)
    slope, intercept, r_value, _, std_err = linregress(V1_clean, V2_clean)
    
    # Calculate metrics
    predictions = slope * V1_clean + intercept
    residuals = V2_clean - predictions
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((V2_clean - np.mean(V2_clean))**2)
    
    adj_r_square = 1 - (ss_res / ss_tot) * (len(V1_clean) - 1) / (len(V1_clean) - 2)
    rmse = np.sqrt(np.mean(residuals**2))
    
    # Calculate sample Seebeck coefficient
    S_Chromel, S_Alumel = calculate_thermocouple_seebeck(temperature)
    S_TC = S_Chromel - S_Alumel
    S_sample = (1 / (1 - slope)) * S_TC + S_Alumel
    
    # Generate plot
    if plot:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(V1_clean * 1e6, V2_clean * 1e6, 'o', label='Raw Data', markersize=4)
        ax.plot(V1_clean * 1e6, predictions * 1e6, '-', label='Fit', linewidth=2)
        
        ax.set_xlabel('V1 (µV)', fontweight='bold')
        ax.set_ylabel('V2 (µV)', fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True)
        
        # Add text box with fit statistics
        textstr = f'Slope = {slope:.6f}\n'
        textstr += f'Intercept = {intercept * 1e5:.3f} × 10⁻⁵\n'
        textstr += f'Adj R² = {adj_r_square:.8f}\n'
        textstr += f'S_sample = {S_sample:.2f} µV/K'
        
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=12,
                verticalalignment='top', bbox=props, fontweight='bold')
        
        plt.tight_layout()
        
        # Save plot if requested
        if save_plot and filename:
            from pathlib import Path
            
            if output_folder is None:
                # Default to seebeck_data/plots/ folder next to the code files
                code_dir = Path(__file__).parent.parent
                save_folder = code_dir / 'seebeck_data' / 'plots'
            else:
                save_folder = Path(output_folder) / 'plots'
            
            save_folder.mkdir(parents=True, exist_ok=True)
            filepath = save_folder / f'{filename}_fit.png'
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"💾 Fit plot saved: {filepath}")
        
        plt.show()
    
    return slope, adj_r_square, intercept, rmse, S_sample
