"""Room-temperature sigma must not be stored as 0 °C.

A type-K reading of 0 °C is 0 mV. That is what channel 111 reports at room
temperature when the cold junction is simulated as 0 °C. The master file
takes its sigma temperature from this reading, so 0 has to be replaced
before it is written.
"""

from constants import reference_temperature_c, sample_temperature_to_record


def test_room_temperature_zero_uses_reference_junction():
    # REFTEMP? layout used by Seebeck: index 4 is channel 111's junction.
    reference = reference_temperature_c("0,23.1,0,0,25.4,0")
    assert reference == 25.4
    assert sample_temperature_to_record(0.0, reference) == 25.4


def test_real_sample_temperature_is_kept():
    assert sample_temperature_to_record(180.2, 25.4) == 180.2


def test_failed_read_is_not_replaced_with_the_terminal_temperature():
    assert sample_temperature_to_record(None, 25.4) is None
    assert sample_temperature_to_record(9.9e37, 25.4) is None


def test_zero_without_a_reference_is_not_recorded():
    assert sample_temperature_to_record(0.0, None) is None
    assert reference_temperature_c("not a reading") is None


def test_sigma_iterations_csv_writes_the_measured_temperature(tmp_path):
    from measure_sigma import record_sample_temperature, save_iteration_data_to_csv

    results = {
        "iterations": [
            {"iteration": i, "temperature": 0.0, "v1": 0.1, "v2": 0.1,
             "v3": 0.1, "v4": 0.1, "delta_v1": 0.01, "delta_v2": 0.01,
             "R1": 1.0, "R2": 1.0, "sigma": 100.0}
            for i in range(1, 6)
        ],
    }
    record_sample_temperature(results, [0.0, 0.0], fallback=24.8)
    save_iteration_data_to_csv(results, "Room", str(tmp_path))
    text = (tmp_path / "Room_sigma_iterations.csv").read_text(encoding="utf-8-sig")
    temps = [line.split(",")[1] for line in text.strip().splitlines()[1:]]
    assert temps == ["24.80"] * 5
    assert results["temperature"] == 24.8
