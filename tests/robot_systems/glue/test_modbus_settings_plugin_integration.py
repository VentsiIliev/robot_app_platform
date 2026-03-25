import unittest
from unittest.mock import MagicMock, patch

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.applications.base.widget_application import WidgetApplication
from src.applications.modbus_settings.service.modbus_settings_application_service import ModbusSettingsApplicationService
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem


def _make_robot_system(config=None):
    cfg = config or ModbusConfig()
    ss  = MagicMock()
    ss.get.side_effect = lambda key: cfg if key == "modbus_config" else None
    app                   = MagicMock()
    app._settings_service = ss
    return app


def _spec():
    return next(
        (s for s in GlueRobotSystem.shell.applications if s.name == "ModbusSettings"),
        None,
    )


# ---------------------------------------------------------------------------
# ApplicationSpec declaration
# ---------------------------------------------------------------------------

class TestModbusSettingsApplicationSpec(unittest.TestCase):

    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "ModbusSettings ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 2)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(_spec().icon)

    def test_spec_name(self):
        self.assertEqual(_spec().name, "ModbusSettings")


# ---------------------------------------------------------------------------
# Factory — WidgetApplication construction
# ---------------------------------------------------------------------------

class TestModbusSettingsApplicationFactory(unittest.TestCase):

    def test_factory_returns_widget_application(self):
        self.assertIsInstance(_spec().factory(_make_robot_system()), WidgetApplication)

    def test_factory_does_not_require_messaging_service(self):
        self.assertIsNotNone(_spec().factory(_make_robot_system()))

    def test_register_stores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        ms     = MagicMock()
        application.register(ms)
        self.assertIs(application._messaging_service, ms)

    def test_widget_factory_callable_ignores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        with patch(
            "src.applications.modbus_settings.modbus_settings_factory.ModbusSettingsFactory.build"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            application.register(MagicMock())
            application.create_widget()
            mock_build.assert_called_once()

    def test_factory_called_twice_returns_independent_applications(self):
        p1 = _spec().factory(_make_robot_system())
        p2 = _spec().factory(_make_robot_system())
        self.assertIsNot(p1, p2)


# ---------------------------------------------------------------------------
# ModbusSettingsApplicationService — settings only (no action methods)
# ---------------------------------------------------------------------------

class TestModbusSettingsApplicationServiceIntegration(unittest.TestCase):

    def _make_service(self, config=None):
        cfg = config or ModbusConfig(port="COM5", baudrate=115200, slave_address=10)
        ss  = MagicMock()
        ss.get.side_effect = lambda key: cfg if key == "modbus_config" else None
        return ModbusSettingsApplicationService(ss,config_key = CommonSettingsID.MODBUS_CONFIG), ss, cfg

    def test_load_config_returns_correct_instance(self):
        svc, _, cfg = self._make_service()
        self.assertIs(svc.load_config(), cfg)

    def test_load_config_reads_modbus_config_key(self):
        svc, ss, _ = self._make_service()
        svc.load_config()
        ss.get.assert_called_with("modbus_config")

    def test_save_config_delegates_to_settings_service(self):
        svc, ss, _ = self._make_service()
        new_cfg = ModbusConfig(port="COM3", baudrate=9600)
        svc.save_config(new_cfg)
        ss.save.assert_called_once_with("modbus_config", new_cfg)

    def test_load_config_port(self):
        svc, _, _ = self._make_service(ModbusConfig(port="COM9"))
        self.assertEqual(svc.load_config().port, "COM9")

    def test_load_config_baudrate(self):
        svc, _, _ = self._make_service(ModbusConfig(baudrate=19200))
        self.assertEqual(svc.load_config().baudrate, 19200)

    def test_load_config_slave_address(self):
        svc, _, _ = self._make_service(ModbusConfig(slave_address=22))
        self.assertEqual(svc.load_config().slave_address, 22)

    def test_load_config_parity(self):
        svc, _, _ = self._make_service(ModbusConfig(parity="E"))
        self.assertEqual(svc.load_config().parity, "E")

    def test_load_config_timeout(self):
        svc, _, _ = self._make_service(ModbusConfig(timeout=1.0))
        self.assertAlmostEqual(svc.load_config().timeout, 1.0)

    def test_save_config_correct_object_passed(self):
        svc, ss, _ = self._make_service()
        new_cfg = ModbusConfig(port="COM7", slave_address=5)
        svc.save_config(new_cfg)
        saved = ss.save.call_args[0][1]
        self.assertEqual(saved.port, "COM7")
        self.assertEqual(saved.slave_address, 5)

    def test_service_has_no_detect_ports(self):
        svc, _, _ = self._make_service()
        self.assertFalse(hasattr(svc, "detect_ports"))

    def test_service_has_no_test_connection(self):
        svc, _, _ = self._make_service()
        self.assertFalse(hasattr(svc, "test_connection"))


# ---------------------------------------------------------------------------
# IModbusActionService — core hardware, separate from settings
# ---------------------------------------------------------------------------

class TestModbusActionServiceIntegration(unittest.TestCase):

    def _make_action_service(self):
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        return ModbusActionService()

    def test_implements_i_modbus_action_service(self):
        from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
        self.assertIsInstance(self._make_action_service(), IModbusActionService)

    def test_detect_ports_returns_list(self):
        import unittest.mock as mock
        svc = self._make_action_service()
        with mock.patch.dict("sys.modules", {
            "serial": None, "serial.tools": None, "serial.tools.list_ports": None,
        }):
            result = svc.detect_ports()
        self.assertIsInstance(result, list)

    def test_test_connection_returns_bool(self):
        import unittest.mock as mock
        svc = self._make_action_service()
        with mock.patch.dict("sys.modules", {"serial": None}):
            result = svc.test_connection(ModbusConfig())
        self.assertIsInstance(result, bool)

    def test_action_service_independent_of_settings_service(self):
        """ModbusActionService must not import or depend on ISettingsService."""
        from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
        import inspect
        src = inspect.getsource(ModbusActionService)
        self.assertNotIn("ISettingsService", src)
        self.assertNotIn("settings_service", src)

    def test_factory_uses_modbus_action_service(self):
        """_build_modbus_settings_application must wire ModbusActionService — not a mock."""
        from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
        application = _spec().factory(_make_robot_system())
        # WidgetApplication.widget_factory is a callable — call it with mock broker
        ms     = MagicMock()
        application.register(ms)
        with patch(
            "src.applications.modbus_settings.modbus_settings_factory.ModbusSettingsFactory.build"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            application.create_widget()
            _, kwargs = mock_build.call_args
            args = mock_build.call_args[0]
            # second positional arg must be an IModbusActionService
            self.assertIsInstance(args[1], IModbusActionService)


# ---------------------------------------------------------------------------
# GlueRobotSystem settings_specs — modbus_config declared
# ---------------------------------------------------------------------------

class TestModbusSettingsSpecInGlueApp(unittest.TestCase):

    def _settings_spec(self):
        return next(
            (s for s in GlueRobotSystem.settings_specs if s.name == "modbus_config"),
            None,
        )

    def test_modbus_settings_spec_declared(self):
        self.assertIsNotNone(self._settings_spec())

    def test_modbus_settings_spec_path(self):
        self.assertEqual(self._settings_spec().storage_key, "hardware/modbus.json")

    def test_modbus_settings_spec_has_serializer(self):
        self.assertIsNotNone(self._settings_spec().serializer)

    def test_serializer_get_default_returns_modbus_config(self):
        self.assertIsInstance(self._settings_spec().serializer.get_default(), ModbusConfig)

    def test_serializer_roundtrip(self):
        spec = self._settings_spec()
        cfg  = ModbusConfig(port="COM3", baudrate=9600, parity="E",
                            slave_address=15, timeout=0.05)
        r    = spec.serializer.from_dict(spec.serializer.to_dict(cfg))
        self.assertEqual(r.port,          cfg.port)
        self.assertEqual(r.baudrate,      cfg.baudrate)
        self.assertEqual(r.parity,        cfg.parity)
        self.assertEqual(r.slave_address, cfg.slave_address)
        self.assertAlmostEqual(r.timeout, cfg.timeout)

    def test_serializer_settings_type(self):
        self.assertEqual(self._settings_spec().serializer.settings_type, "modbus_config")


# ---------------------------------------------------------------------------
# Application ordering
# ---------------------------------------------------------------------------

class TestModbusSettingsApplicationOrdering(unittest.TestCase):

    def test_modbus_settings_in_service_folder(self):
        self.assertIn("ModbusSettings", [
            s.name for s in GlueRobotSystem.shell.applications if s.folder_id == 2
        ])

    def test_service_folder_declared(self):
        self.assertIn(2, [f.folder_id for f in GlueRobotSystem.shell.folders])

    def test_all_service_applications_have_icons(self):
        for spec in GlueRobotSystem.shell.applications:
            if spec.folder_id == 2:
                self.assertIsNotNone(spec.icon, f"{spec.name} missing icon")

    def test_all_service_applications_have_factories(self):
        for spec in GlueRobotSystem.shell.applications:
            if spec.folder_id == 2:
                self.assertIsNotNone(spec.factory, f"{spec.name} missing factory")


if __name__ == "__main__":
    unittest.main()