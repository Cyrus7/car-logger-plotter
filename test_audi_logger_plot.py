import pytest
import time
from audi_logger_plot import faultword_to_flags, SerialReader, FIELDS

def test_faultword_to_flags_empty():
    assert faultword_to_flags(0) == []

def test_faultword_to_flags_single_bit():
    assert faultword_to_flags(1) == ["SENSOR_ERR"]
    assert faultword_to_flags(2) == ["OVERBOOST"]
    assert faultword_to_flags(4) == ["LOW_OIL"]
    assert faultword_to_flags(8) == ["HIGH_EGT"]
    assert faultword_to_flags(16) == ["LOW_FUEL_PRESS"]
    assert faultword_to_flags(32) == ["LOW_U12V"]
    assert faultword_to_flags(64) == ["LOW_U5V"]
    assert faultword_to_flags(128) == ["MAP_IMPLAUS"]

def test_faultword_to_flags_multiple_bits():
    # 1 + 128 = 129
    assert faultword_to_flags(129) == ["SENSOR_ERR", "MAP_IMPLAUS"]
    # 1 + 2 + 128 = 131
    assert faultword_to_flags(131) == ["SENSOR_ERR", "OVERBOOST", "MAP_IMPLAUS"]

def test_serial_reader_demo():
    reader = SerialReader(port=None, baud=115200, demo=True)
    assert reader.get_latest() is None

    reader.start()

    # Wait for the reader to generate some data
    # Polling instead of sleep to avoid flakiness
    start_time = time.time()
    latest = None
    while time.time() - start_time < 2.0:
        latest = reader.get_latest()
        if latest is not None:
            break
        time.sleep(0.01)

    assert latest is not None
    assert isinstance(latest, dict)

    for field in FIELDS:
        assert field in latest

    reader.stop()
    reader.join(timeout=1.0)
    assert not reader.is_alive()
