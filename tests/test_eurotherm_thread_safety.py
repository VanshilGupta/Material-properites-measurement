"""One shared EurothermController used from several threads at once.

Regression guard for the temperature-cycle bug: the GUI polls the furnace on
one thread while the cycle sets set-points from another, through the SAME
controller.  Their MODBUS request/response exchanges must never interleave.
"""

import struct
import threading
import time

import eurotherm_control as ec


class OverlapDetectingSerial:
    """Fake port that answers float reads/writes and flags interleaving.

    A transaction is "write request → read reply".  If a second request is
    written before the first reply was read, two threads were talking on the
    wire at the same time — exactly what the controller's lock must prevent.
    """

    is_open = True

    def __init__(self):
        self.in_flight = False
        self.overlaps = 0
        self.transactions = 0
        self._request = b""

    def reset_input_buffer(self):
        pass

    def write(self, data):
        if self.in_flight:
            self.overlaps += 1
        self.in_flight = True
        self._request = bytes(data)

    def read(self, size):
        time.sleep(0.002)                      # give other threads a chance to cut in
        addr, func = self._request[0], self._request[1]
        if func == 16:                         # write-multiple echo
            reply = ec.append_crc16(self._request[:6])
        else:                                  # float read
            reply = ec.append_crc16(bytes([addr, 3, 4]) + struct.pack(">f", 25.0))
        self.in_flight = False
        self.transactions += 1
        return reply[:size]

    def close(self):
        self.is_open = False


def _connected_controller():
    ctrl = ec.EurothermController(com_port=5, auto_detect=False)
    ctrl.MODBUS_INTER_FRAME_DELAY = 0          # keep the test fast
    ctrl.serial = OverlapDetectingSerial()
    ctrl._connected = True
    return ctrl


def test_concurrent_polling_and_setpoints_never_interleave():
    ctrl = _connected_controller()

    def poll():                                # the GUI's live display
        for _ in range(40):
            assert ctrl.read_temperature() == 25.0

    def cycle():                               # the temperature cycle
        for i in range(40):
            assert ctrl.set_temperature(100.0 + i) is True

    threads = [threading.Thread(target=poll), threading.Thread(target=cycle)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert ctrl.serial.overlaps == 0
    assert ctrl.serial.transactions == 80
