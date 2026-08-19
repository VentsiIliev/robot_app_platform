import unittest
from unittest.mock import MagicMock, patch

from src.engine.hardware.communication.modbus.xinje_ma_8x8yr_transport import (
    XinjeMA8X8YRTransport,
)


class TestXinjeMA8X8YRTransport(unittest.TestCase):
    def test_read_input_uses_fc1_for_x_points(self) -> None:
        transport = XinjeMA8X8YRTransport(port="/dev/null", slave_address=1)
        instrument = MagicMock()
        instrument.read_bit.return_value = True

        with patch.object(transport, "_session") as session:
            session.return_value.__enter__.return_value = instrument
            self.assertEqual(transport.read_input(0), 1)

        instrument.read_bit.assert_called_once_with(0, functioncode=1)


if __name__ == "__main__":
    unittest.main()
