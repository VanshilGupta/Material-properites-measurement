"""Eurotherm COM-port auto-detection, against fake serial ports."""

import struct
from types import SimpleNamespace

import pytest
import serial

import eurotherm_control as ec


class FakeBus:
    """Pretends to be the PC's serial ports.

    ``behaviour`` maps a COM number to one of:
        "eurotherm"  – answers MODBUS reads correctly
        "wrong_addr" – answers, but from a different device address
        "garbage"    – answers with bytes that fail the CRC
        "silent"     – opens fine, never replies
        "busy"       – refuses to open (e.g. held by another program)
    ``listed`` is what the OS reports; a port may work without being listed.
    """

    def __init__(self, behaviour, listed=None):
        self.behaviour = behaviour
        self.listed = list(behaviour) if listed is None else listed
        self.opened = []                    # COM numbers, in open order

    def comports(self):
        return [SimpleNamespace(device=f"COM{n}") for n in self.listed]

    def serial_factory(self):
        bus = self

        class FakeSerial:
            is_open = True

            def __init__(self, port, **_kwargs):
                self.com = int(port[3:])
                mode = bus.behaviour.get(self.com, "busy")
                bus.opened.append(self.com)
                if mode == "busy":
                    raise serial.SerialException(f"could not open {port}")
                self.mode = mode
                self._request = b""

            def reset_input_buffer(self):
                pass

            def write(self, data):
                self._request = bytes(data)

            def read(self, size):
                if self.mode == "silent":
                    return b""
                addr = self._request[0]
                count = struct.unpack(">H", self._request[4:6])[0]
                if self.mode == "wrong_addr":
                    addr += 1
                payload = (struct.pack(">BBH", addr, 3, 300)[:2] + b"\x02\x01\x2c"
                           if count == 1 else
                           bytes([addr, 3, 4]) + struct.pack(">f", 25.0))
                frame = ec.append_crc16(payload)
                if self.mode == "garbage":
                    frame = frame[:-1] + bytes([frame[-1] ^ 0xFF])
                return frame[:size]

            def close(self):
                self.is_open = False

        return FakeSerial


@pytest.fixture
def install(monkeypatch):
    def _install(behaviour, listed=None):
        bus = FakeBus(behaviour, listed)
        monkeypatch.setattr(ec.serial.tools.list_ports, "comports", bus.comports)
        monkeypatch.setattr(ec.serial, "Serial", bus.serial_factory())
        return bus
    return _install


def test_configured_port_is_tried_first_and_stops_the_scan(install):
    bus = install({3: "silent", 5: "eurotherm", 7: "eurotherm"})
    result = ec.find_eurotherm_port(preferred=5, probe_timeout=0.01)
    assert result.com_port == 5
    assert bus.opened == [5]                # nothing else was touched


def test_falls_back_to_scanning_every_other_port_in_order(install):
    bus = install({3: "busy", 4: "silent", 5: "silent", 7: "eurotherm", 9: "eurotherm"})
    result = ec.find_eurotherm_port(preferred=5, probe_timeout=0.01)
    assert result.com_port == 7
    # configured first, then the rest ascending; stops at the first hit
    assert [a.com_port for a in result.attempts] == [5, 3, 4, 7]
    assert result.ports_seen == [3, 4, 5, 7, 9]


def test_unlisted_configured_port_is_still_tried_then_scan_continues(install):
    bus = install({6: "eurotherm"}, listed=[6])        # COM5 not present at all
    result = ec.find_eurotherm_port(preferred=5, probe_timeout=0.01)
    assert result.com_port == 6
    assert result.attempts[0].com_port == 5 and not result.attempts[0].found
    assert "cannot open" in result.attempts[0].detail


def test_nothing_answers_reports_every_port(install):
    install({3: "silent", 4: "busy", 5: "garbage", 6: "wrong_addr"})
    result = ec.find_eurotherm_port(preferred=5, probe_timeout=0.01)
    assert result.com_port is None
    assert sorted(a.com_port for a in result.attempts) == [3, 4, 5, 6]
    summary = result.summary()
    for needle in ("COM3: no reply", "COM4: cannot open", "COM5: invalid reply"):
        assert needle in summary


def test_reply_from_wrong_device_address_is_rejected(install):
    install({5: "wrong_addr"})
    assert ec.probe_port(5, device_address=1, timeout=0.01).found is False


def test_connect_adopts_the_detected_port(install):
    install({4: "silent", 7: "eurotherm"})
    ctrl = ec.EurothermController(com_port=4, auto_detect=True, probe_timeout=0.01)
    assert ctrl.connect() is True
    assert ctrl.com_port == 7
    ctrl.disconnect()


def test_connect_fails_when_no_port_answers(install):
    install({4: "silent", 7: "silent"})
    ctrl = ec.EurothermController(com_port=4, auto_detect=True, probe_timeout=0.01)
    assert ctrl.connect() is False
    assert not ctrl.is_connected()


def test_auto_detect_off_only_uses_the_configured_port(install):
    bus = install({4: "busy", 7: "eurotherm"})
    ctrl = ec.EurothermController(com_port=4, auto_detect=False)
    assert ctrl.connect() is False
    assert bus.opened == [4]                # never scanned COM7
