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


def test_sigma_temperature_adds_the_cold_junction_like_seebeck():
    from seebeck_measurement.temperature_conversion import (
        temp_to_voltage, voltage_to_temp,
    )
    from constants import sigma_temperature_from_voltages

    def converted(volts, reference):
        return voltage_to_temp(volts * 1e3 + temp_to_voltage(reference))

    # 0 V is a room-temperature thermocouple. Adding each cold junction
    # makes the saved temperature the mean of the two junctions, not 0 °C.
    room = sigma_temperature_from_voltages(0.0, 0.0, 23.0, 25.0)
    assert room == round((converted(0.0, 23.0) + converted(0.0, 25.0)) / 2, 2)
    assert abs(room - 24.0) < 0.2

    # A sample at 100 °C: the DAQ voltage is the difference from the junction.
    hot_volts = (temp_to_voltage(100.0) - temp_to_voltage(25.0)) / 1e3
    assert sigma_temperature_from_voltages(
        hot_volts, hot_volts, 25.0, 25.0) == round(converted(hot_volts, 25.0), 2)
    assert abs(sigma_temperature_from_voltages(
        hot_volts, hot_volts, 25.0, 25.0) - 100.0) < 0.05

    # The two channels are averaged. One missing channel is left out.
    assert sigma_temperature_from_voltages(0.0, None, 25.0, 25.0) == round(
        converted(0.0, 25.0), 2)
    # No cold junction: the voltage alone is not a sample temperature.
    assert sigma_temperature_from_voltages(0.0, 0.0, None, None) is None


def test_sigma_temperature_is_the_mean_of_both_thermocouples():
    from constants import mean_sigma_temperature

    assert mean_sigma_temperature(100.0, 110.0) == 105.0
    # One channel dead at 0 °C while the other is hot: keep the hot one.
    assert mean_sigma_temperature(0.0, 200.0, ref101=25.0, ref111=25.0) == 200.0
    # Both at 0 mV: the sample is at the cold junctions, so average those.
    assert mean_sigma_temperature(0.0, 0.0, ref101=23.0, ref111=25.0) == 24.0
    # Neither channel read: no temperature.
    assert mean_sigma_temperature(None, None, ref101=25.0, ref111=25.0) is None


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
