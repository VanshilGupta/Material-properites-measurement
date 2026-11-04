"""Simulated measurements must match the real result schema and the GUI worker."""

import csv
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from simulation import (
    nominal_seebeck,
    nominal_sigma,
    simulate_seebeck_measurement,
    simulate_sigma_measurement,
    solve_vdp_sigma,
    _geometry_error,
)


def test_method_panel_exposes_simulation_switch():
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from gui.widgets.method_config import MethodConfigPanel

    panel = MethodConfigPanel()
    assert panel.get_settings()["simulation"] is False
    assert panel._sim_note.isVisible() is False
    panel.chk_simulation.setChecked(True)
    assert panel.get_settings()["simulation"] is True
    assert panel._sim_note.isVisible() is True


def test_sigma_voltages_solve_back_to_the_reported_conductivity():
    thickness, diameter, temperature = 2.0, 12.7, 80.0
    results = simulate_sigma_measurement(
        thickness, diameter, temperature=temperature, verbose=False, seed=3,
    )

    assert results["valid_count"] == 5
    assert len(results["iterations"]) == 5
    assert abs(results["temperature"] - temperature) < 1.0
    assert results["temperature_readings"]

    for it in results["iterations"]:
        solved = solve_vdp_sigma(it["R1"], it["R2"], thickness)
        assert abs(solved - it["sigma"]) < 1e-6
        assert abs(abs(it["v1"] - it["v2"]) / 2.0 - it["delta_v1"]) < 1e-9
        assert abs(it["delta_v1"] / results["current"] - it["R1"]) < 1e-9
        assert it["temperature"] is not None

    median = float(np.median(results["sigma_raw"]))
    expected = median * (1.0 - _geometry_error(diameter))
    assert abs(results["corr_sigma"] - expected) < 1e-8
    # Iteration noise is 2%; the median stays near the temperature model.
    assert abs(median - nominal_sigma(temperature)) / nominal_sigma(temperature) < 0.08


def test_seebeck_fit_recovers_the_model_and_writes_real_csvs(tmp_path):
    temperature = 120.0
    seen = []

    class _Plotter:
        def update(self, t, t1, t2, v1, v2):
            seen.append((t, t1, t2, v1, v2))

    results = simulate_seebeck_measurement(
        "sample", 60.0, str(tmp_path), temperature=temperature,
        enable_plotting=False, seed=4, plotter=_Plotter(),
    )

    assert abs(results["T_avg"] - temperature) < 0.5
    assert abs(results["Seebeck"] - nominal_seebeck(temperature)) < 3.0
    assert results["data_avg"].shape[1] == 5
    # Averaged voltages are µV, live plotter voltages are volts.
    assert np.max(np.abs(results["data_avg"][:, 3])) > 20
    assert seen and max(abs(p[3]) for p in seen) < 0.01
    assert max(abs(p[1] - p[2]) for p in seen) > 1.0  # a real gradient, °C

    v1 = results["data_avg"][:, 3] * 1e-6
    v2 = results["data_avg"][:, 4] * 1e-6
    predicted = results["slope"] * v1 + results["offset"]
    rmse = float(np.sqrt(np.mean((predicted - v2) ** 2)))
    assert rmse < 2e-6

    data_dir = tmp_path / "data"
    assert (data_dir / "sample_averaged.csv").is_file()
    assert (data_dir / "sample_all.csv").is_file()
    header = (data_dir / "sample_averaged.csv").read_text(encoding="latin-1").splitlines()[0]
    assert header == "t(s),T1_avg(°C),T2_avg(°C),V1_avg(µV),V2(µV)"


def _forbid_instruments(monkeypatch):
    import gui.backend.measurement_service as ms

    def boom(*_a, **_k):
        raise AssertionError("real instrument path was used during simulation")

    monkeypatch.setattr(ms, "measure_sigma_with_sample_temperature", boom)
    monkeypatch.setattr(ms, "read_current_temperature", boom)
    monkeypatch.setattr(ms, "SeebeckMeasurement", boom)
    return ms


class _Furnace:
    def connect_blocking(self):
        raise AssertionError("furnace was contacted during simulation")

    @property
    def controller(self):
        raise AssertionError("furnace was contacted during simulation")


def _run(ms, config):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    worker = ms._MeasurementWorker(furnace=_Furnace())
    done = {}
    worker.measurement_finished.connect(
        lambda ok, summary, meta: done.update(ok=ok, summary=summary, meta=meta)
    )
    worker.sigma_data_point.connect(lambda d: done.setdefault("sigma", []).append(d))
    worker.seebeck_data_point.connect(lambda d: done.setdefault("seebeck", []).append(d))
    worker.run(config)
    return done


def test_gui_worker_simulation_saves_the_real_files(tmp_path, monkeypatch):
    ms = _forbid_instruments(monkeypatch)
    done = _run(ms, {
        "sample_name": "SimTest",
        "diameter": 12.7,
        "thickness": 2.0,
        "measure_sigma": True,
        "measure_seebeck": True,
        "seebeck_time": 40.0,
        "base_dir": str(tmp_path),
        "simulation": True,
    })

    assert done["ok"], done.get("summary")
    assert done["meta"]["simulation"] is True
    assert len(done["sigma"]) == 5
    assert all(p["sigma"] > 0 for p in done["sigma"])
    assert len(done["seebeck"]) >= 40
    # Live Seebeck voltages are volts; the window scales them to µV.
    assert max(abs(p["V1"]) for p in done["seebeck"]) < 0.01

    master = next(tmp_path.rglob("*_master.csv"))
    with master.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    row = rows[0]
    temp = done["meta"]["temperature"]
    assert abs(float(row["Sigma Sample Temperature (°C)"]) - temp) < 1.5
    assert abs(float(row["Seebeck Sample Temperature (°C)"]) - temp) < 1.0
    assert abs(float(row["Seebeck Coefficient (µV/K)"]) - nominal_seebeck(temp)) < 5
    assert float(row["Corrected Sigma (S/cm)"]) > 0
    assert "Failed to record" not in master.read_text(encoding="utf-8-sig")

    iterations = next(tmp_path.rglob("*_sigma_iterations.csv"))
    text = iterations.read_text(encoding="utf-8-sig")
    assert text.startswith("Iteration,Temperature")
    assert len(text.strip().splitlines()) == 6  # header + 5 iterations
    assert next(tmp_path.rglob("*_averaged.csv"))


def test_gui_worker_simulation_cycle_does_not_touch_the_furnace(tmp_path, monkeypatch):
    ms = _forbid_instruments(monkeypatch)
    done = _run(ms, {
        "sample_name": "SimCycle",
        "diameter": 12.7,
        "thickness": 2.0,
        "measure_sigma": True,
        "measure_seebeck": True,
        "seebeck_time": 30.0,
        "base_dir": str(tmp_path),
        "simulation": True,
        "cycle_mode": True,
        "temperatures": [50.0, 100.0],
        "rate": 10.0,
        "stability_time": 1200.0,
        "heating_only": True,
    })

    assert done["ok"], done.get("summary")
    assert done["meta"]["n_points"] == 2
    master = next(tmp_path.rglob("*_master.csv"))
    with master.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    sigma_temps = [float(r["Sigma Sample Temperature (°C)"]) for r in rows]
    seebeck_vals = [float(r["Seebeck Coefficient (µV/K)"]) for r in rows]
    assert abs(sigma_temps[0] - 50) < 1.5
    assert abs(sigma_temps[1] - 100) < 1.5
    # Conductivity and Seebeck both move with the set-point, not one flat value.
    assert float(rows[1]["Corrected Sigma (S/cm)"]) > float(rows[0]["Corrected Sigma (S/cm)"])
    assert seebeck_vals[1] < seebeck_vals[0]
