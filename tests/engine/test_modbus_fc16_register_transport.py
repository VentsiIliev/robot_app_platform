import unittest
from unittest.mock import MagicMock, patch

from src.engine.hardware.communication.modbus.modbus_fc16_register_transport import (
    ModbusFc16RegisterTransport,
)
from src.engine.hardware.communication.transport_registry import (
    DEFAULT_TRANSPORT_REGISTRY,
)


class TestModbusFc16RegisterTransport(unittest.TestCase):
    def test_single_register_write_uses_fc16_batch_operation(self) -> None:
        transport = ModbusFc16RegisterTransport(
            port="/dev/null",
            slave_address=10,
        )
        instrument = MagicMock()

        with patch.object(transport, "_session") as session:
            session.return_value.__enter__.return_value = instrument
            transport.write_register(1, 1)

        instrument.write_registers.assert_called_once_with(1, [1])
        instrument.write_register.assert_not_called()

    def test_transport_is_registered(self) -> None:
        self.assertIn("modbus_register_fc16", DEFAULT_TRANSPORT_REGISTRY.keys())


if __name__ == "__main__":
    unittest.main()
