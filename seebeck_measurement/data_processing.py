"""Data averaging and processing utilities."""

import numpy as np
from typing import Tuple


def average_data(
    time: np.ndarray,
    T1: np.ndarray,
    T2: np.ndarray,
    V1: np.ndarray,
    V2: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Average consecutive pairs of measurements.
    
    Args:
        time: Time array
        T1, T2: Temperature arrays
        V1, V2: Voltage arrays
        
    Returns:
        Tuple of (t_avg, T1_avg, T2_avg, V1_avg, V2_avg)
    """
    n = len(time)
    n_avg = n // 2
    
    t_avg = np.zeros(n_avg)
    T1_avg = np.zeros(n_avg)
    T2_avg = np.zeros(n_avg)
    V1_avg = np.zeros(n_avg)
    V2_avg = np.zeros(n_avg)
    
    j = 0
    for i in range(0, n - 1, 2):
        t_avg[j] = (time[i] + time[i + 1]) / 2
        T1_avg[j] = (T1[i] + T1[i + 1]) / 2
        T2_avg[j] = (T2[i] + T2[i + 1]) / 2
        V1_avg[j] = (V1[i] + V1[i + 1]) / 2
        V2_avg[j] = (V2[i] + V2[i + 1]) / 2
        j += 1
    
    return t_avg[:j], T1_avg[:j], T2_avg[:j], V1_avg[:j], V2_avg[:j]


def save_to_csv(
    filename: str,
    data: np.ndarray,
    headers: list,
    folder: str = None
) -> None:
    """
    Save data to CSV file with headers.
    
    Args:
        filename: Output filename
        data: 2D numpy array of data
        headers: List of column headers
        folder: Output folder (optional, defaults to seebeck_data/data/ next to code)
    """
    from pathlib import Path
    
    if folder is None:
        # Default to seebeck_data/data/ folder next to the code files
        code_dir = Path(__file__).parent.parent
        folder = code_dir / 'seebeck_data' / 'data'
    else:
        folder = Path(folder) / 'data'
    
    folder.mkdir(parents=True, exist_ok=True)
    
    filepath = folder / filename
    
    header_str = ','.join(headers)
    np.savetxt(filepath, data, delimiter=',', header=header_str, comments='')
    
    print(f'💾 Data saved to: {filepath}')
