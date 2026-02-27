import unittest
from unittest.mock import MagicMock

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.applications.modbus_settings.model.mapper import ModbusSettingsMapper
from src.applications.modbus_settings.model.modbus_settings_model import ModbusSettingsModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings_service(config=None):
    svc = MagicMock()
    svc.load_config.return_value = config or ModbusConfig()
    return svc


def _make_action_service():
    svc = MagicMock()
    svc.detect_ports.return_value    = []
    svc.test_connection.return_value = False
    return svc


def _loaded(config=None):
    ss    = _make_settings_service(config)
    acts  = _make_action_service()
    model = ModbusSettingsModel(ss, acts)
    model.load()
    return model, ss, acts


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestModbusSettingsModelLoad(unittest.TestCase):

    def test_load_calls_settings_service(self):
        ss    = _make_settings_service()
        model = ModbusSettingsModel(ss, _make_action_service())
        model.load()
        ss.load_config.assert_called_once()

    def test_load_returns_config(self):
        cfg   = ModbusConfig(port="COM3")
        model = ModbusSettingsModel(_make_settings_service(cfg), _make_action_service())
        self.assertEqual(model.load().port, "COM3")

    def test_config_cached_after_load(self):
        cfg   = ModbusConfig(slave_address=7)
        model = ModbusSettingsModel(_make_settings_service(cfg), _make_action_service())
        model.load()
        self.assertEqual(model._config.slave_address, 7)


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

class TestModbusSettingsModelSave(unittest.TestCase):

    def test_save_calls_save_config(self):
        model, ss, _ = _loaded()
        model.save(ModbusSettingsMapper.to_flat_dict(ModbusConfig()))
        ss.save_config.assert_called_once()

    def test_save_updates_port(self):
        model, ss, _ = _loaded(ModbusConfig(port="COM1"))
        flat = dict(ModbusSettingsMapper.to_flat_dict(ModbusConfig(port="COM1")), port="COM9")
        model.save(flat)
        self.assertEqual(ss.save_config.call_args[0][0].port, "COM9")

    def test_save_updates_baudrate(self):
        model, ss, _ = _loaded()
        flat = dict(ModbusSettingsMapper.to_flat_dict(ModbusConfig()), baudrate="9600")
        model.save(flat)
        self.assertEqual(ss.save_config.call_args[0][0].baudrate, 9600)

    def test_save_updates_internal_cache(self):
        model, _, _ = _loaded()
        flat = dict(ModbusSettingsMapper.to_flat_dict(ModbusConfig()), slave_address="22")
        model.save(flat)
        self.assertEqual(model._config.slave_address, 22)

    def test_save_without_prior_load_uses_default(self):
        ss    = _make_settings_service()
        model = ModbusSettingsModel(ss, _make_action_service())
        model.save({"port": "COM7"})   # no load() first — must not raise
        ss.save_config.assert_called_once()

    def test_save_does_not_mutate_previous_config(self):
        original    = ModbusConfig(port="COM1")
        model, _, _ = _loaded(original)
        flat        = dict(ModbusSettingsMapper.to_flat_dict(original), port="COM99")
        model.save(flat)
        self.assertEqual(original.port, "COM1")


# ---------------------------------------------------------------------------
# detect_ports() — delegates to action service
# ---------------------------------------------------------------------------

class TestModbusSettingsModelDetectPorts(unittest.TestCase):

    def test_detect_ports_delegates_to_action_service(self):
        acts = _make_action_service()
        acts.detect_ports.return_value = ["COM1", "COM3"]
        model = ModbusSettingsModel(_make_settings_service(), acts)
        result = model.detect_ports()
        acts.detect_ports.assert_called_once()
        self.assertEqual(result, ["COM1", "COM3"])

    def test_detect_ports_does_not_call_settings_service(self):
        ss   = _make_settings_service()
        acts = _make_action_service()
        ModbusSettingsModel(ss, acts).detect_ports()
        ss.load_config.assert_not_called()
        ss.save_config.assert_not_called()

    def test_detect_ports_empty_list(self):
        model = ModbusSettingsModel(_make_settings_service(), _make_action_service())
        self.assertEqual(model.detect_ports(), [])


# ---------------------------------------------------------------------------
# test_connection() — delegates to action service
# ---------------------------------------------------------------------------

class TestModbusSettingsModelTestConnection(unittest.TestCase):

    def test_test_connection_delegates_to_action_service(self):
        acts = _make_action_service()
        acts.test_connection.return_value = True
        model = ModbusSettingsModel(_make_settings_service(), acts)
        self.assertTrue(model.test_connection(ModbusConfig()))
        acts.test_connection.assert_called_once()

    def test_test_connection_passes_config_to_action_service(self):
        acts = _make_action_service()
        cfg  = ModbusConfig(port="COM3")
        model = ModbusSettingsModel(_make_settings_service(), acts)
        model.test_connection(cfg)
        acts.test_connection.assert_called_once_with(cfg)

    def test_test_connection_does_not_call_settings_service(self):
        ss   = _make_settings_service()
        acts = _make_action_service()
        ModbusSettingsModel(ss, acts).test_connection(ModbusConfig())
        ss.load_config.assert_not_called()
        ss.save_config.assert_not_called()

    def test_test_connection_failure(self):
        model = ModbusSettingsModel(_make_settings_service(), _make_action_service())
        self.assertFalse(model.test_connection(ModbusConfig()))


# ---------------------------------------------------------------------------
# config_from_flat()
# ---------------------------------------------------------------------------

class TestModbusSettingsModelConfigFromFlat(unittest.TestCase):

    def test_config_from_flat_uses_cached_base(self):
        model, _, _ = _loaded(ModbusConfig(port="COM5", baudrate=115200))
        result = model.config_from_flat({"port": "COM3", "baudrate": "9600"})
        self.assertEqual(result.port,     "COM3")
        self.assertEqual(result.baudrate, 9600)

    def test_config_from_flat_no_load_uses_default(self):
        model = ModbusSettingsModel(_make_settings_service(), _make_action_service())
        self.assertEqual(model.config_from_flat({"port": "COM1"}).port, "COM1")

    def test_config_from_flat_does_not_mutate_cache(self):
        model, _, _ = _loaded(ModbusConfig(port="COM5"))
        model.config_from_flat({"port": "COM99"})
        self.assertEqual(model._config.port, "COM5")


# ---------------------------------------------------------------------------
# ModbusSettingsApplicationService — settings only (load/save)
# ---------------------------------------------------------------------------

class TestModbusSettingsApplicationService(unittest.TestCase):

    def _make_ss(self, config=None):
        cfg = config or ModbusConfig()
        ss  = MagicMock()
        ss.get.side_effect = lambda key: cfg if key == "modbus_config" else None
        return ss, cfg

    def test_load_config_reads_correct_key(self):
        from src.applications.modbus_settings.service.modbus_settings_application_service import ModbusSettingsApplicationService
        ss, cfg = self._make_ss()
        self.assertIs(ModbusSettingsApplicationService(ss).load_config(), cfg)
        ss.get.assert_called_with("modbus_config")

    def test_save_config_writes_correct_key(self):
        from src.applications.modbus_settings.service.modbus_settings_application_service import ModbusSettingsApplicationService
        ss, _ = self._make_ss()
        new   = ModbusConfig(port="COM7")
        ModbusSettingsApplicationService(ss).save_config(new)
        ss.save.assert_called_once_with("modbus_config", new)

    def test_service_has_no_detect_ports_method(self):
        """detect_ports belongs to IModbusActionService — not to the settings service."""
        from src.applications.modbus_settings.service.modbus_settings_application_service import ModbusSettingsApplicationService
        ss, _ = self._make_ss()
        svc   = ModbusSettingsApplicationService(ss)
        self.assertFalse(hasattr(svc, "detect_ports"))

    def test_service_has_no_test_connection_method(self):
        """test_connection belongs to IModbusActionService — not to the settings service."""
        from src.applications.modbus_settings.service.modbus_settings_application_service import ModbusSettingsApplicationService
        ss, _ = self._make_ss()
        svc   = ModbusSettingsApplicationService(ss)
        self.assertFalse(hasattr(svc, "test_connection"))


# ---------------------------------------------------------------------------
# ModbusActionService — core hardware utility
# ---------------------------------------------------------------------------

class TestModbusActionService(unittest.TestCase):

    def test_detect_ports_returns_list_on_import_error(self):
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        import unittest.mock as mock
        svc = ModbusActionService()
        with mock.patch.dict("sys.modules", {
            "serial": None, "serial.tools": None, "serial.tools.list_ports": None,
        }):
            result = svc.detect_ports()
        self.assertIsInstance(result, list)

    def test_detect_ports_returns_empty_on_import_error(self):
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        import unittest.mock as mock
        svc = ModbusActionService()
        with mock.patch.dict("sys.modules", {
            "serial": None, "serial.tools": None, "serial.tools.list_ports": None,
        }):
            result = svc.detect_ports()
        self.assertEqual(result, [])

    def test_test_connection_returns_false_on_import_error(self):
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        import unittest.mock as mock
        svc = ModbusActionService()
        with mock.patch.dict("sys.modules", {"serial": None}):
            result = svc.test_connection(ModbusConfig())
        self.assertFalse(result)

    def test_test_connection_returns_false_on_serial_error(self):
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        import unittest.mock as mock
        svc    = ModbusActionService()
        serial = mock.MagicMock()
        serial.Serial.side_effect = OSError("port not found")
        with mock.patch.dict("sys.modules", {"serial": serial}):
            result = svc.test_connection(ModbusConfig(port="INVALID"))
        self.assertFalse(result)

    def test_test_connection_returns_true_on_success(self):
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        import unittest.mock as mock
        svc    = ModbusActionService()
        serial = mock.MagicMock()
        serial.Serial.return_value.__enter__ = mock.MagicMock(return_value=mock.MagicMock())
        serial.Serial.return_value.__exit__  = mock.MagicMock(return_value=False)
        with mock.patch.dict("sys.modules", {"serial": serial}):
            result = svc.test_connection(ModbusConfig(port="COM3"))
        self.assertTrue(result)

    def test_implements_interface(self):
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
        self.assertIsInstance(ModbusActionService(), IModbusActionService)


if __name__ == "__main__":
    unittest.main()
