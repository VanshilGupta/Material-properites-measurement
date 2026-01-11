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
        # Default to measurement_data folder next to the code files
        code_dir = Path(__file__).parent
        base_dir = code_dir / 'measurement_data'
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
    logger.info("=" * 60)
    logger.info(f"MEASUREMENT LOG STARTED")
    logger.info("=" * 60)
    logger.info(f"Measurement Type: {measurement_type.upper()}")
    logger.info(f"Sample Name: {sample_name}")
    logger.info(f"Output Folder: {output_folder}")
    logger.info(f"Log File: {log_filepath}")
    logger.info(f"Start Time: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    logger.info("=" * 60)
    
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
    logger.info("=" * 60)
    logger.info("MEASUREMENT LOG ENDED")
    logger.info("=" * 60)
    logger.info(f"End Time: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    
    if success:
        logger.info("Status: COMPLETED SUCCESSFULLY")
    else:
        logger.error(f"Status: FAILED")
        if error_msg:
            logger.error(f"Error: {error_msg}")
    
    logger.info("=" * 60)
    
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
