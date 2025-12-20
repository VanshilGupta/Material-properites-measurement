"""
Run Electrical Conductivity Measurement

Simple standalone script to measure electrical conductivity (sigma).
"""

from measure_sigma import measure_sigma
from constants import DEFAULT_SAMPLE_THICKNESS, DEFAULT_SAMPLE_DIAMETER


def main():
    """Run sigma measurement."""
    
    print("\n" + "="*60)
    print("ELECTRICAL CONDUCTIVITY MEASUREMENT")
    print("="*60)
    
    # Get sample parameters
    try:
        thickness = float(input(f"Enter sample thickness in mm (default: {DEFAULT_SAMPLE_THICKNESS}): ").strip() or DEFAULT_SAMPLE_THICKNESS)
        diameter = float(input(f"Enter sample diameter in mm (default: {DEFAULT_SAMPLE_DIAMETER}): ").strip() or DEFAULT_SAMPLE_DIAMETER)
    except ValueError:
        print("Invalid input, using default values")
        thickness = DEFAULT_SAMPLE_THICKNESS
        diameter = DEFAULT_SAMPLE_DIAMETER
    
    print(f"\nSample thickness: {thickness} mm")
    print(f"Sample diameter: {diameter} mm")
    print("="*60 + "\n")
    
    # Run measurement
    try:
        results = measure_sigma(sample_t=thickness, sample_dia=diameter, verbose=True)
        
        if results:
            print("\n" + "="*60)
            print("MEASUREMENT COMPLETE")
            print("="*60)
            print(f"Electrical Conductivity: {results['sigma']:.2e} S/m")
            print(f"Resistivity: {results['rho']:.2e} Ω·m")
            print("="*60)
        else:
            print("\nMeasurement failed. Check instrument connections.")
            
    except KeyboardInterrupt:
        print("\n\nMeasurement interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
