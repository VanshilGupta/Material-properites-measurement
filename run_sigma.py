"""
Run Electrical Conductivity Measurement

Simple standalone script to measure electrical conductivity (sigma).

Output:
- Creates a folder with the sample name in measurement_data/
- All data files and logs are saved in this folder
- If folder exists, creates a new one with suffix (e.g., Sample1_2)
- Log file captures all events for debugging
"""

import traceback
from measure_sigma import measure_sigma, save_results_to_csv
from constants import DEFAULT_SAMPLE_THICKNESS, DEFAULT_SAMPLE_DIAMETER
from output_manager import create_output_structure, finalize_logging


def main():
    """Run sigma measurement."""
    
    print("\n" + "="*60)
    print("ELECTRICAL CONDUCTIVITY MEASUREMENT")
    print("="*60)
    
    # Get sample name
    sample_name = input("Enter sample name (default: Sample1): ").strip() or "Sample1"
    
    # Create output folder and setup logging
    output_folder, logger = create_output_structure(sample_name, "sigma")
    
    # Get sample parameters
    try:
        thickness = float(input(f"Enter sample thickness in mm (default: {DEFAULT_SAMPLE_THICKNESS}): ").strip() or DEFAULT_SAMPLE_THICKNESS)
        diameter = float(input(f"Enter sample diameter in mm (default: {DEFAULT_SAMPLE_DIAMETER}): ").strip() or DEFAULT_SAMPLE_DIAMETER)
    except ValueError:
        print("Invalid input, using default values")
        thickness = DEFAULT_SAMPLE_THICKNESS
        diameter = DEFAULT_SAMPLE_DIAMETER
    
    print(f"\nSample name: {sample_name}")
    print(f"Sample thickness: {thickness} mm")
    print(f"Sample diameter: {diameter} mm")
    print(f"Output folder: {output_folder}")
    print("="*60 + "\n")
    
    logger.info(f"Sample thickness: {thickness} mm")
    logger.info(f"Sample diameter: {diameter} mm")
    
    # Run measurement
    try:
        logger.info("Starting sigma measurement...")
        
        results = measure_sigma(
            sample_t=thickness, 
            sample_dia=diameter, 
            verbose=True,
            logger=logger
        )
        
        if results:
            print("\n" + "="*60)
            print("MEASUREMENT COMPLETE")
            print("="*60)
            print(f"Electrical Conductivity: {results['corr_sigma']:.2e} S/cm")
            print(f"Uncorrected Sigma: {results['uncorr_sigma']:.2e} S/cm")
            print(f"Valid Measurements: {results['valid_count']}/5")
            print(f"Data saved to: {output_folder}")
            print("="*60)
            
            # Save results to CSV in output folder
            save_results_to_csv(results, sample_name, str(output_folder))
            
            logger.info("MEASUREMENT RESULTS:")
            logger.info(f"  Electrical Conductivity: {results['corr_sigma']:.2e} S/cm")
            logger.info(f"  Uncorrected Sigma: {results['uncorr_sigma']:.2e} S/cm")
            logger.info(f"  Valid Measurements: {results['valid_count']}/5")
            
            finalize_logging(logger, success=True)
        else:
            logger.error("Measurement failed - no results returned")
            finalize_logging(logger, success=False, error_msg="Measurement returned no results. Check instrument connections.")
            print("\nMeasurement failed. Check instrument connections.")
            
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
