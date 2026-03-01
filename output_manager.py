"""
Output Folder and Logging Manager

Handles creation of sample-specific output folders with automatic versioning
and logging setup for measurement runs.

Features:
- Creates a folder with the sample name for all output data
- Auto-increments folder name if it already exists (e.g., SN2517, SN2517_2, SN2517_3)
- Sets up comprehensive logging to help debug any measurement issues
- Logs all measurement events, errors, and run information
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple


def get_unique_output_folder(sample_name: str, base_dir: str = None) -> Path:
    """
    Create a unique output folder for the sample.
    
    If a folder with the sample name already exists, creates a new one
    with an incremented suffix (e.g., SN2517_2, SN2517_3, etc.)
    
    Args:
        sample_name: Name of the sample (used as folder name)
        base_dir: Base directory for output folders. If None, uses 
                  'measurement_data' folder next to the code files.
    
    Returns:
        Path to the created output folder
    """
    if base_dir is None:
        # Default to 'data' folder next to the code files
        code_dir = Path(__file__).parent
        base_dir = code_dir / 'data'
    else:
        base_dir = Path(base_dir)
    
    # Ensure base directory exists
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to create folder with sample name
    output_folder = base_dir / sample_name
    
    if not output_folder.exists():
        output_folder.mkdir(parents=True, exist_ok=True)
        return output_folder
    
    # Folder exists, find next available suffix
    suffix = 2
    while True:
        output_folder = base_dir / f"{sample_name}_{suffix}"
        if not output_folder.exists():
            output_folder.mkdir(parents=True, exist_ok=True)
            return output_folder
        suffix += 1


def setup_logging(
    output_folder: Path,
    measurement_type: str,
    sample_name: str
) -> logging.Logger:
    """
    Set up logging for a measurement run.
    
    Creates a log file in the output folder that captures all measurement
    events, errors, and debug information to help identify issues if 
    the measurement stops abruptly or encounters errors.
    
    Args:
        output_folder: Path to the output folder
        measurement_type: Type of measurement ('seebeck' or 'sigma')
        sample_name: Name of the sample being measured
    
    Returns:
        Configured logger instance
    """
    # Create timestamp for the log filename (Indian format: DDMMYYYY_HHMMSS)
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    log_filename = f"{measurement_type}_run_{timestamp}.log"
    log_filepath = output_folder / log_filename
    
    # Create a unique logger name to avoid conflicts
    logger_name = f"{measurement_type}_{sample_name}_{timestamp}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # File handler - captures everything to file
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Console handler - shows INFO and above to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Log initial run information
    logger.info(f"--- {measurement_type.upper()} measurement started ---")
    logger.info(f"Sample: {sample_name}")
    logger.info(f"Output: {output_folder}")
    logger.info(f"Log: {log_filepath}")
    
    return logger


def finalize_logging(logger: logging.Logger, success: bool = True, error_msg: str = None):
    """
    Finalize the logging for a measurement run.
    
    Logs the end time and status, and properly closes all handlers.
    
    Args:
        logger: The logger instance to finalize
        success: Whether the measurement completed successfully
        error_msg: Error message if measurement failed
    """
    if success:
        logger.info("--- Measurement completed successfully ---")
    else:
        logger.error(f"--- Measurement FAILED{': ' + error_msg if error_msg else ''} ---")
    
    logger.info(f"End: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    
    # Close and remove all handlers
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def create_output_structure(
    sample_name: str,
    measurement_type: str,
    base_dir: str = None
) -> Tuple[Path, logging.Logger]:
    """
    Create complete output structure for a measurement run.
    
    This is a convenience function that creates the output folder
    and sets up logging in one call.
    
    Args:
        sample_name: Name of the sample
        measurement_type: Type of measurement ('seebeck' or 'sigma')
        base_dir: Base directory for output folders (optional)
    
    Returns:
        Tuple of (output_folder_path, logger)
    
    Example:
        >>> output_folder, logger = create_output_structure("SN2517", "seebeck")
        >>> logger.info("Starting measurement...")
        >>> # ... do measurement ...
        >>> finalize_logging(logger, success=True)
    """
    output_folder = get_unique_output_folder(sample_name, base_dir)
    logger = setup_logging(output_folder, measurement_type, sample_name)
    
    return output_folder, logger


# =============================================================================
# Temperature Sweep Output Structure
# =============================================================================

def create_temp_sweep_structure(
    sample_name: str,
    base_dir: str = None
) -> Tuple[Path, logging.Logger]:
    """
    Create output structure for temperature sweep measurements.
    
    Creates a hierarchical folder structure:
    data/
    └── SampleX/
        ├── global_log.log
        ├── SampleX_Sigma_vs_Temp.csv
        ├── SampleX_Seebeck_vs_Temp.csv
        ├── 100C/
        │   ├── log.log
        │   ├── Sigma/
        │   └── Seebeck/
        └── ...
    
    Args:
        sample_name: Name of the sample
        base_dir: Base directory (default: measurement_data/)
    
    Returns:
        Tuple of (sample_folder_path, global_logger)
    """
    sample_folder = get_unique_output_folder(sample_name, base_dir)
    global_logger = setup_global_logger(sample_folder, sample_name)
    
    return sample_folder, global_logger


def setup_global_logger(
    sample_folder: Path,
    sample_name: str
) -> logging.Logger:
    """
    Set up global logger for temperature sweep.
    
    This logger records high-level events across all temperatures.
    
    Args:
        sample_folder: Path to sample folder
        sample_name: Name of the sample
    
    Returns:
        Configured global logger
    """
    log_filepath = sample_folder / "global_log.log"
    
    # Create unique logger name
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    logger_name = f"global_{sample_name}_{timestamp}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Log header
    logger.info(f"--- Temperature sweep started ---")
    logger.info(f"Sample: {sample_name}")
    logger.info(f"Output: {sample_folder}")
    
    return logger


def create_temperature_folder(
    sample_folder: Path,
    temperature: float,
    measurement_types: list = None
) -> Tuple[Path, logging.Logger]:
    """
    Create folder structure for a specific temperature measurement.
    
    Args:
        sample_folder: Parent sample folder
        temperature: Temperature in °C
        measurement_types: List of measurement types ['Sigma', 'Seebeck']
    
    Returns:
        Tuple of (temp_folder_path, temp_logger)
    """
    # Create temperature folder (e.g., "100.0C" with 1 decimal)
    temp_folder_name = f"{temperature:.1f}C"
    temp_folder = sample_folder / temp_folder_name
    temp_folder.mkdir(parents=True, exist_ok=True)
    
    # Create subfolders for each measurement type
    if measurement_types is None:
        measurement_types = ['Sigma', 'Seebeck']
    
    for mtype in measurement_types:
        (temp_folder / mtype).mkdir(parents=True, exist_ok=True)
    
    # Setup local logger for this temperature
    temp_logger = setup_temperature_logger(temp_folder, temperature)
    
    return temp_folder, temp_logger


def setup_temperature_logger(
    temp_folder: Path,
    temperature: float
) -> logging.Logger:
    """
    Set up logger for a specific temperature measurement.
    
    Args:
        temp_folder: Temperature folder path
        temperature: Temperature in °C
    
    Returns:
        Configured logger for this temperature
    """
    log_filepath = temp_folder / "log.log"
    
    # Create unique logger name
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    logger_name = f"temp_{int(temperature)}C_{timestamp}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler only (console handled by global logger)
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Log header
    logger.info(f"--- Measurement at {temperature}°C ---")
    logger.info(f"Started: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    
    return logger


def create_single_measurement_structure(
    sample_name: str,
    measurement_type: str,
    base_dir: str = None,
    temperature: float = None
) -> Tuple[Path, logging.Logger, Path, logging.Logger, Path]:
    """
    Create folder structure for single measurement (no temperature sweep).
    
    Structure:
    data/
    └── SampleX/
        ├── global_log.log
        ├── 28C/ (or whatever the actual temperature is)
        │   ├── log.log
        │   └── Sigma/ or Seebeck/
    
    Args:
        sample_name: Name of the sample
        measurement_type: 'sigma' or 'seebeck'
        base_dir: Base directory
        temperature: Current temperature in Celsius (defaults to 25°C if None)
    
    Returns:
        Tuple of (sample_folder, global_logger, temp_folder, temp_logger, mtype_folder)
    """
    sample_folder = get_unique_output_folder(sample_name, base_dir)
    global_logger = setup_global_logger(sample_folder, sample_name)
    
    # Use actual temperature for folder name, default to 25°C if not provided
    if temperature is None:
        temperature = 25.0
    
    # Create temperature-specific folder (e.g., "28.5C" with 1 decimal)
    temp_folder = sample_folder / f"{temperature:.1f}C"
    temp_folder.mkdir(parents=True, exist_ok=True)
    
    # Create measurement subfolder
    mtype_folder = temp_folder / measurement_type.capitalize()
    mtype_folder.mkdir(parents=True, exist_ok=True)
    
    # Setup local logger
    temp_logger = setup_temperature_logger(temp_folder, temperature)
    
    return sample_folder, global_logger, temp_folder, temp_logger, mtype_folder

