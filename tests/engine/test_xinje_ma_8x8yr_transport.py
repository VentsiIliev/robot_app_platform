import os
import unittest
from unittest.mock import MagicMock, patch

import serial

from src.engine.hardware.communication.modbus.xinje_ma_8x8yr_transport import (
    XinjeMA8X8YRTransport,
    _crc16,
    _write_fd_bounded,
)


class TestXinjeMA8X8YRTransport(unittest.TestCase):
    def test_bounded_fd_write_completes_without_blocking(self) -> None:
        read_fd, write_fd = os.pipe()
        try:
            _write_fd_bounded(write_fd, b"abc", 0.1)
            self.assertEqual(os.read(read_fd, 3), b"abc")
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_bounded_fd_write_times_out_when_fd_is_not_writable(self) -> None:
        read_fd, write_fd = os.pipe()
        try:
            with patch(
                "src.engine.hardware.communication.modbus.xinje_ma_8x8yr_transport.select.select",
                return_value=([], [], []),
            ):
                with self.assertRaises(serial.SerialTimeoutException):
                    _write_fd_bounded(write_fd, b"abc", 0.1)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_read_input_uses_fc1_for_x_points(self) -> None:
        transport = XinjeMA8X8YRTransport(port="/dev/null", slave_address=1)
        instrument = MagicMock()
        instrument.read_bit.return_value = True

        with patch.object(transport, "_session") as session:
            session.return_value.__enter__.return_value = instrument
            self.assertEqual(transport.read_input(0), 1)

        instrument.read_bit.assert_called_once_with(0, functioncode=1)

    def test_separate_transports_share_output_image(self) -> None:
        pump = XinjeMA8X8YRTransport(port="/dev/test-shared-image", slave_address=1)
        fan = XinjeMA8X8YRTransport(port="/dev/test-shared-image", slave_address=1)
        pump._raw_send = MagicMock(return_value=b"")
        fan._raw_send = MagicMock(return_value=b"")

        pump.write_register(130, 1)
        fan.write_register(131, 1)

        frame = bytes([1, 15, 0, 128, 0, 16, 2, 0b00001100, 0])
        expected = frame + _crc16(frame).to_bytes(2, "little")
        fan._raw_send.assert_called_once_with(expected)


if __name__ == "__main__":
    unittest.main()
