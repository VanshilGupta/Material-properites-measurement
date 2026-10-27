"""
Master Results File

One CSV per sample folder holding every σ and Seebeck result of the run —
one row per temperature point, instead of separate Sigma / Seebeck files.

A row is appended as soon as a point finishes, so an abort or crash part-way
through a cycle still leaves every completed point on disk.  Each run gets a
unique sample folder (see ``output_manager.get_unique_output_folder``), so a
master file never mixes runs.  Raw data (σ iterations, Seebeck time series)
stays in the per-temperature Sigma/ and Seebeck/ subfolders.

Temperatures are the SAMPLE's, and σ and Seebeck each have their own since
they are measured at different times:
  - σ:       mean of the DAQ ch 111 readings taken during the σ measurement
  - Seebeck: mean of every T₁ and T₂ reading of the Seebeck run
The furnace set-point is kept only to tell the cycle's points apart.

Cells for a measurement that was not run, or that failed, are left blank.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from measure_sigma import _result_temperature

MASTER_COLUMNS = [
    "Timestamp",
    "Sample Name",
    "Furnace Set-point (°C)",
    "Sigma Sample Temperature (°C)",
    "Corrected Sigma (S/cm)",
    "Uncorrected Sigma (S/cm)",
    "Sigma Std Dev",
    "Current (A)",
    "Valid σ Iterations",
    "Seebeck Sample Temperature (°C)",
    "Seebeck Coefficient (µV/K)",
    "Adj. R²",
    "Fit RMSE",
    "Sample Thickness (mm)",
    "Sample Diameter (mm)",
]


def master_file_path(sample_folder, sample_name: str) -> Path:
    """Return ``<sample_folder>/<sample_name>_master.csv``."""
    return Path(sample_folder) / f"{sample_name}_master.csv"


def _fmt(value, spec: str) -> str:
    """Format *value* with *spec*, or '' if it is missing."""
    return "" if value is None else format(value, spec)


def append_master_row(
    path,
    sample_name: str,
    sigma_results: Optional[dict],
    seebeck_results: Optional[dict],
    setpoint: Optional[float] = None,
    thickness: Optional[float] = None,
    diameter: Optional[float] = None,
) -> None:
    """Append one temperature point to the master CSV.

    The σ temperature is ``sigma_results['temperature']`` (the GUI's mean
    sample temperature); the Seebeck one is ``seebeck_results['T_avg']``.

    The header is written first if the file is new.  Raises ``OSError``
    (e.g. ``PermissionError`` when the file is open in Excel) — the caller
    decides whether that is fatal.
    """
    sigma = sigma_results or {}
    seebeck = seebeck_results or {}

    row = [
        datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        sample_name,
        _fmt(setpoint, ".2f"),
        _result_temperature(sigma) if sigma else "",
        _fmt(sigma.get("corr_sigma"), ".6e"),
        _fmt(sigma.get("uncorr_sigma"), ".6e"),
        _fmt(sigma.get("std_dev"), ".6e"),
        _fmt(sigma.get("current"), ".6f"),
        _fmt(sigma.get("valid_count"), "d"),
        _fmt(seebeck.get("T_avg"), ".2f"),
        _fmt(seebeck.get("Seebeck"), ".6f"),
        _fmt(seebeck.get("adj_r_square"), ".6f"),
        _fmt(seebeck.get("rmse"), ".6e"),
        _fmt(thickness, ".3f"),
        _fmt(diameter, ".3f"),
    ]

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    # utf-8-sig only writes the BOM at the start of an empty file, so
    # appending keeps a single BOM and Excel shows °C / µ correctly.
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(MASTER_COLUMNS)
        writer.writerow(row)
