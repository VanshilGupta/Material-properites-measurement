"""
Run Seebeck Coefficient Measurement

Simple standalone script to measure Seebeck coefficient.

Output:
- Creates a folder with the sample name in measurement_data/
- All data files, plots, and logs are saved in this folder
- If folder exists, creates a new one with suffix (e.g., SN2517_2)
- Log file captures all events for debugging
"""

import traceback
from seebeck_measurement import SeebeckMeasurement
from output_manager import create_output_structure, finalize_logging


def main():
    """Run Seebeck measurement."""
    
    # Configuration
    sample_name = input("Enter sample name (default: SN2517): ").strip() or "SN2517"
    
    # Create output folder and setup logging
    output_folder, logger = create_output_structure(sample_name, "seebeck")
    
    print("\n" + "="*60)
    print("SEEBECK COEFFICIENT MEASUREMENT")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Output folder: {output_folder}")
    print(f"Measurement time: 8 minutes (480 seconds)")
    print("="*60 + "\n")
    
    logger.info(f"Sample parameters configured")
    logger.info(f"Measurement time: 480 seconds")
    
    # Create and run measurement
    measurement = SeebeckMeasurement(enable_plotting=True)
    
    try:
        logger.info("Starting Seebeck measurement...")
        
        results = measurement.run_measurement(
            filename=sample_name,
            measurement_time=480,
            output_folder=str(output_folder),
            logger=logger
        )
        
        print("\n" + "="*60)
        print("MEASUREMENT COMPLETE")
        print("="*60)
        print(f"Seebeck Coefficient: {results['Seebeck']:.2f} µV/K")
        print(f"Average Temperature: {results['T_avg']:.2f} °C")
        print(f"Fit Quality (R²): {results['adj_r_square']:.6f}")
        print(f"Data saved to: {output_folder}")
        print("="*60)
        
        logger.info("MEASUREMENT RESULTS:")
        logger.info(f"  Seebeck Coefficient: {results['Seebeck']:.2f} µV/K")
        logger.info(f"  Average Temperature: {results['T_avg']:.2f} °C")
        logger.info(f"  Fit Quality (R²): {results['adj_r_square']:.6f}")
        
        finalize_logging(logger, success=True)
        
    except KeyboardInterrupt:
        logger.warning("Measurement interrupted by user (KeyboardInterrupt)")
        finalize_logging(logger, success=False, error_msg="User interrupted measurement")
        print("\n\nMeasurement interrupted by user")
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Measurement failed with error: {e}")
        logger.error(f"Traceback:\n{error_details}")
        finalize_logging(logger, success=False, error_msg=str(e))
        print(f"\nError: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
