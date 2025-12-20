"""
Run Seebeck Coefficient Measurement

Simple standalone script to measure Seebeck coefficient.
"""

from seebeck_measurement import SeebeckMeasurement


def main():
    """Run Seebeck measurement."""
    
    # Configuration
    sample_name = input("Enter sample name (default: SN2517): ").strip() or "SN2517"
    
    print("\n" + "="*60)
    print("SEEBECK COEFFICIENT MEASUREMENT")
    print("="*60)
    print(f"Sample: {sample_name}")
    print(f"Measurement time: 8 minutes (480 seconds)")
    print("="*60 + "\n")
    
    # Create and run measurement
    measurement = SeebeckMeasurement(enable_plotting=True)
    
    try:
        results = measurement.run_measurement(
            filename=sample_name,
            measurement_time=480
        )
        
        print("\n" + "="*60)
        print("MEASUREMENT COMPLETE")
        print("="*60)
        print(f"Seebeck Coefficient: {results['S_slope']:.2f} µV/K")
        print(f"Average Temperature: {results['T_avg']:.2f} °C")
        print(f"Fit Quality (R²): {results['adj_r_square']:.6f}")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nMeasurement interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
