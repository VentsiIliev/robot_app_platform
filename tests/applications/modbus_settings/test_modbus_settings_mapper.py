import unittest

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.applications.modbus_settings.model.mapper import ModbusSettingsMapper


class TestModbusSettingsMapperToFlatDict(unittest.TestCase):

    def setUp(self):
        self.config = ModbusConfig()
        self.flat   = ModbusSettingsMapper.to_flat_dict(self.config)

    def test_all_expected_keys_present(self):
        expected = {"port", "baudrate", "bytesize", "stopbits", "parity",
                    "timeout", "slave_address", "max_retries"}
        self.assertEqual(expected, set(self.flat.keys()))

    def test_port_value(self):
        c = ModbusConfig(port="COM3")
        self.assertEqual(ModbusSettingsMapper.to_flat_dict(c)["port"], "COM3")

    def test_baudrate_value(self):
        c = ModbusConfig(baudrate=9600)
        self.assertEqual(ModbusSettingsMapper.to_flat_dict(c)["baudrate"], 9600)

    def test_parity_value(self):
        c = ModbusConfig(parity="E")
        self.assertEqual(ModbusSettingsMapper.to_flat_dict(c)["parity"], "E")

    def test_timeout_value(self):
        c = ModbusConfig(timeout=1.5)
        self.assertAlmostEqual(ModbusSettingsMapper.to_flat_dict(c)["timeout"], 1.5)

    def test_slave_address_value(self):
        c = ModbusConfig(slave_address=5)
        self.assertEqual(ModbusSettingsMapper.to_flat_dict(c)["slave_address"], 5)


class TestModbusSettingsMapperFromFlatDict(unittest.TestCase):

    def setUp(self):
        self.base = ModbusConfig()
        self.flat = ModbusSettingsMapper.to_flat_dict(self.base)

    def test_port_updated(self):
        flat = dict(self.flat, port="/dev/ttyUSB0")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(r.port, "/dev/ttyUSB0")

    def test_baudrate_cast_to_int(self):
        flat = dict(self.flat, baudrate="9600")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertIsInstance(r.baudrate, int)
        self.assertEqual(r.baudrate, 9600)

    def test_bytesize_cast_to_int(self):
        flat = dict(self.flat, bytesize="7")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertIsInstance(r.bytesize, int)
        self.assertEqual(r.bytesize, 7)

    def test_stopbits_cast_to_int(self):
        flat = dict(self.flat, stopbits="2")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertIsInstance(r.stopbits, int)
        self.assertEqual(r.stopbits, 2)

    def test_parity_updated(self):
        flat = dict(self.flat, parity="O")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(r.parity, "O")

    def test_timeout_cast_to_float(self):
        flat = dict(self.flat, timeout="0.5")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertIsInstance(r.timeout, float)
        self.assertAlmostEqual(r.timeout, 0.5)

    def test_slave_address_cast_to_int(self):
        flat = dict(self.flat, slave_address="20")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertIsInstance(r.slave_address, int)
        self.assertEqual(r.slave_address, 20)

    def test_max_retries_cast_to_int(self):
        flat = dict(self.flat, max_retries="50")
        r = ModbusSettingsMapper.from_flat_dict(flat, self.base)
        self.assertIsInstance(r.max_retries, int)
        self.assertEqual(r.max_retries, 50)

    def test_missing_keys_fall_back_to_base(self):
        r = ModbusSettingsMapper.from_flat_dict({}, self.base)
        self.assertEqual(r.port,          self.base.port)
        self.assertEqual(r.baudrate,      self.base.baudrate)
        self.assertEqual(r.slave_address, self.base.slave_address)

    def test_does_not_mutate_base(self):
        original_port = self.base.port
        ModbusSettingsMapper.from_flat_dict({"port": "COM99"}, self.base)
        self.assertEqual(self.base.port, original_port)

    def test_full_roundtrip(self):
        c    = ModbusConfig(port="COM3", baudrate=19200, parity="E",
                            slave_address=15, timeout=0.05)
        flat = ModbusSettingsMapper.to_flat_dict(c)
        r    = ModbusSettingsMapper.from_flat_dict(flat, c)
        self.assertEqual(r.port,          c.port)
        self.assertEqual(r.baudrate,      c.baudrate)
        self.assertEqual(r.parity,        c.parity)
        self.assertEqual(r.slave_address, c.slave_address)
        self.assertAlmostEqual(r.timeout, c.timeout)


if __name__ == "__main__":
    unittest.main()