import unittest

from src.engine.hardware.communication.modbus.modbus import ModbusConfig, ModbusConfigSerializer


# ---------------------------------------------------------------------------
# ModbusConfig — defaults
# ---------------------------------------------------------------------------

class TestModbusConfigDefaults(unittest.TestCase):

    def setUp(self):
        self.config = ModbusConfig()

    def test_default_port(self):
        self.assertEqual(self.config.port, "COM5")

    def test_default_baudrate(self):
        self.assertEqual(self.config.baudrate, 115200)

    def test_default_bytesize(self):
        self.assertEqual(self.config.bytesize, 8)

    def test_default_stopbits(self):
        self.assertEqual(self.config.stopbits, 1)

    def test_default_parity(self):
        self.assertEqual(self.config.parity, "N")

    def test_default_timeout(self):
        self.assertAlmostEqual(self.config.timeout, 0.01)

    def test_default_slave_address(self):
        self.assertEqual(self.config.slave_address, 10)

    def test_default_max_retries(self):
        self.assertEqual(self.config.max_retries, 30)


# ---------------------------------------------------------------------------
# ModbusConfig — construction
# ---------------------------------------------------------------------------

class TestModbusConfigConstruction(unittest.TestCase):

    def test_custom_port(self):
        self.assertEqual(ModbusConfig(port="/dev/ttyUSB0").port, "/dev/ttyUSB0")

    def test_custom_baudrate(self):
        self.assertEqual(ModbusConfig(baudrate=9600).baudrate, 9600)

    def test_custom_bytesize(self):
        self.assertEqual(ModbusConfig(bytesize=7).bytesize, 7)

    def test_custom_stopbits(self):
        self.assertEqual(ModbusConfig(stopbits=2).stopbits, 2)

    def test_custom_parity(self):
        self.assertEqual(ModbusConfig(parity="E").parity, "E")

    def test_custom_timeout(self):
        self.assertAlmostEqual(ModbusConfig(timeout=1.5).timeout, 1.5)

    def test_custom_slave_address(self):
        self.assertEqual(ModbusConfig(slave_address=5).slave_address, 5)

    def test_custom_max_retries(self):
        self.assertEqual(ModbusConfig(max_retries=50).max_retries, 50)

    def test_two_configs_with_same_values_are_equal(self):
        self.assertEqual(ModbusConfig(port="COM3"), ModbusConfig(port="COM3"))

    def test_two_configs_with_different_values_are_not_equal(self):
        self.assertNotEqual(ModbusConfig(port="COM3"), ModbusConfig(port="COM5"))


# ---------------------------------------------------------------------------
# ModbusConfig.to_dict()
# ---------------------------------------------------------------------------

class TestModbusConfigToDict(unittest.TestCase):

    def setUp(self):
        self.cfg  = ModbusConfig(port="COM3", baudrate=9600, parity="E",
                                  slave_address=5, timeout=0.5)
        self.flat = self.cfg.to_dict()

    def test_all_keys_present(self):
        expected = {"port", "baudrate", "bytesize", "stopbits", "parity",
                    "timeout", "slave_address", "max_retries"}
        self.assertEqual(set(self.flat.keys()), expected)

    def test_port_value(self):
        self.assertEqual(self.flat["port"], "COM3")

    def test_baudrate_value(self):
        self.assertEqual(self.flat["baudrate"], 9600)

    def test_parity_value(self):
        self.assertEqual(self.flat["parity"], "E")

    def test_timeout_value(self):
        self.assertAlmostEqual(self.flat["timeout"], 0.5)

    def test_slave_address_value(self):
        self.assertEqual(self.flat["slave_address"], 5)

    def test_returns_new_dict_each_call(self):
        d1 = self.cfg.to_dict()
        d2 = self.cfg.to_dict()
        self.assertIsNot(d1, d2)


# ---------------------------------------------------------------------------
# ModbusConfig.from_dict()
# ---------------------------------------------------------------------------

class TestModbusConfigFromDict(unittest.TestCase):

    def test_port_parsed(self):
        self.assertEqual(ModbusConfig.from_dict({"port": "COM7"}).port, "COM7")

    def test_baudrate_parsed(self):
        self.assertEqual(ModbusConfig.from_dict({"baudrate": 19200}).baudrate, 19200)

    def test_bytesize_parsed(self):
        self.assertEqual(ModbusConfig.from_dict({"bytesize": 7}).bytesize, 7)

    def test_stopbits_parsed(self):
        self.assertEqual(ModbusConfig.from_dict({"stopbits": 2}).stopbits, 2)

    def test_parity_parsed(self):
        self.assertEqual(ModbusConfig.from_dict({"parity": "O"}).parity, "O")

    def test_timeout_parsed(self):
        self.assertAlmostEqual(ModbusConfig.from_dict({"timeout": 2.0}).timeout, 2.0)

    def test_slave_address_parsed(self):
        self.assertEqual(ModbusConfig.from_dict({"slave_address": 22}).slave_address, 22)

    def test_max_retries_parsed(self):
        self.assertEqual(ModbusConfig.from_dict({"max_retries": 5}).max_retries, 5)

    def test_missing_keys_use_defaults(self):
        cfg = ModbusConfig.from_dict({})
        self.assertEqual(cfg.port,          "COM5")
        self.assertEqual(cfg.baudrate,      115200)
        self.assertEqual(cfg.slave_address, 10)

    def test_partial_dict_keeps_unspecified_defaults(self):
        cfg = ModbusConfig.from_dict({"port": "COM3"})
        self.assertEqual(cfg.baudrate, 115200)
        self.assertEqual(cfg.parity,   "N")

    def test_full_roundtrip(self):
        original = ModbusConfig(port="COM3", baudrate=9600, bytesize=7,
                                stopbits=2, parity="E", timeout=1.0,
                                slave_address=15, max_retries=5)
        restored = ModbusConfig.from_dict(original.to_dict())
        self.assertEqual(original, restored)


# ---------------------------------------------------------------------------
# ModbusConfig.update_field()
# ---------------------------------------------------------------------------

class TestModbusConfigUpdateField(unittest.TestCase):

    def test_update_port(self):
        cfg = ModbusConfig()
        cfg.update_field("port", "COM9")
        self.assertEqual(cfg.port, "COM9")

    def test_update_baudrate(self):
        cfg = ModbusConfig()
        cfg.update_field("baudrate", 9600)
        self.assertEqual(cfg.baudrate, 9600)

    def test_update_slave_address(self):
        cfg = ModbusConfig()
        cfg.update_field("slave_address", 20)
        self.assertEqual(cfg.slave_address, 20)

    def test_update_timeout(self):
        cfg = ModbusConfig()
        cfg.update_field("timeout", 2.5)
        self.assertAlmostEqual(cfg.timeout, 2.5)

    def test_update_invalid_field_raises_value_error(self):
        cfg = ModbusConfig()
        with self.assertRaises(ValueError):
            cfg.update_field("nonexistent_field", "x")

    def test_update_does_not_affect_other_fields(self):
        cfg = ModbusConfig(baudrate=9600)
        cfg.update_field("port", "COM3")
        self.assertEqual(cfg.baudrate, 9600)


# ---------------------------------------------------------------------------
# ModbusConfigSerializer
# ---------------------------------------------------------------------------

class TestModbusConfigSerializer(unittest.TestCase):

    def setUp(self):
        self.serializer = ModbusConfigSerializer()

    def test_settings_type(self):
        self.assertEqual(self.serializer.settings_type, "modbus_config")

    def test_get_default_returns_modbus_config(self):
        self.assertIsInstance(self.serializer.get_default(), ModbusConfig)

    def test_get_default_has_correct_port(self):
        self.assertEqual(self.serializer.get_default().port, "COM5")

    def test_get_default_returns_new_instance_each_call(self):
        d1 = self.serializer.get_default()
        d2 = self.serializer.get_default()
        self.assertIsNot(d1, d2)

    def test_to_dict_returns_dict(self):
        result = self.serializer.to_dict(ModbusConfig())
        self.assertIsInstance(result, dict)

    def test_to_dict_contains_all_keys(self):
        d = self.serializer.to_dict(ModbusConfig())
        for key in ("port", "baudrate", "bytesize", "stopbits",
                    "parity", "timeout", "slave_address", "max_retries"):
            self.assertIn(key, d)

    def test_from_dict_returns_modbus_config(self):
        result = self.serializer.from_dict({"port": "COM3"})
        self.assertIsInstance(result, ModbusConfig)

    def test_from_dict_parses_port(self):
        self.assertEqual(self.serializer.from_dict({"port": "COM3"}).port, "COM3")

    def test_serializer_roundtrip(self):
        cfg = ModbusConfig(port="COM3", baudrate=9600, parity="E",
                           slave_address=15, timeout=0.05)
        restored = self.serializer.from_dict(self.serializer.to_dict(cfg))
        self.assertEqual(restored.port,          cfg.port)
        self.assertEqual(restored.baudrate,      cfg.baudrate)
        self.assertEqual(restored.parity,        cfg.parity)
        self.assertEqual(restored.slave_address, cfg.slave_address)
        self.assertAlmostEqual(restored.timeout, cfg.timeout)

    def test_serializer_roundtrip_all_fields(self):
        cfg = ModbusConfig(port="/dev/ttyUSB0", baudrate=38400, bytesize=7,
                           stopbits=2, parity="O", timeout=2.0,
                           slave_address=22, max_retries=5)
        restored = self.serializer.from_dict(self.serializer.to_dict(cfg))
        self.assertEqual(restored, cfg)


if __name__ == "__main__":
    unittest.main()