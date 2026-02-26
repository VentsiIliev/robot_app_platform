import unittest
from unittest.mock import MagicMock

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.plugins.modbus_settings.controller.modbus_settings_controller import ModbusSettingsController
from src.plugins.modbus_settings.model.mapper import ModbusSettingsMapper
from src.plugins.modbus_settings.model.modbus_settings_model import ModbusSettingsModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_view():
    view = MagicMock()
    view.save_requested.connect            = MagicMock()
    view.detect_ports_requested.connect    = MagicMock()
    view.test_connection_requested.connect = MagicMock()
    view.destroyed.connect                 = MagicMock()
    return view


def _make_model(config=None):
    model = MagicMock(spec=ModbusSettingsModel)
    model.load.return_value             = config or ModbusConfig()
    model.detect_ports.return_value     = []
    model.test_connection.return_value  = False
    model.config_from_flat.return_value = config or ModbusConfig()
    return model


def _make_controller(config=None):
    model = _make_model(config)
    view  = _make_view()
    ctrl  = ModbusSettingsController(model, view)
    flat  = ModbusSettingsMapper.to_flat_dict(config or ModbusConfig())
    view.get_values.return_value = flat
    return ctrl, model, view


# ---------------------------------------------------------------------------
# Init — signal wiring
# ---------------------------------------------------------------------------

class TestModbusSettingsControllerInit(unittest.TestCase):

    def test_wires_save_requested(self):
        _, _, view = _make_controller()
        view.save_requested.connect.assert_called_once()

    def test_wires_detect_ports_requested(self):
        _, _, view = _make_controller()
        view.detect_ports_requested.connect.assert_called_once()

    def test_wires_test_connection_requested(self):
        _, _, view = _make_controller()
        view.test_connection_requested.connect.assert_called_once()

    def test_wires_destroyed(self):
        _, _, view = _make_controller()
        view.destroyed.connect.assert_called_once()


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestModbusSettingsControllerLoad(unittest.TestCase):

    def test_load_calls_model_load(self):
        ctrl, model, _ = _make_controller()
        ctrl.load()
        model.load.assert_called_once()

    def test_load_pushes_config_to_view(self):
        cfg  = ModbusConfig(port="COM3")
        ctrl, _, view = _make_controller(cfg)
        ctrl.load()
        view.load_config.assert_called_once_with(cfg)


# ---------------------------------------------------------------------------
# _on_save
# ---------------------------------------------------------------------------

class TestModbusSettingsControllerSave(unittest.TestCase):

    def test_on_save_calls_model_save(self):
        ctrl, model, _ = _make_controller()
        ctrl._on_save({})
        model.save.assert_called_once()

    def test_on_save_passes_view_values(self):
        cfg  = ModbusConfig(port="COM7")
        ctrl, model, view = _make_controller(cfg)
        flat = ModbusSettingsMapper.to_flat_dict(cfg)
        view.get_values.return_value = flat
        ctrl._on_save({})
        self.assertEqual(model.save.call_args[0][0]["port"], "COM7")

    def test_on_save_exception_does_not_propagate(self):
        ctrl, model, _ = _make_controller()
        model.save.side_effect = RuntimeError("disk error")
        ctrl._on_save({})   # must not raise


# ---------------------------------------------------------------------------
# _on_ports_detected / _on_detect_failed
# ---------------------------------------------------------------------------

class TestModbusSettingsControllerDetect(unittest.TestCase):

    def test_on_ports_detected_pushes_to_view(self):
        ctrl, _, view = _make_controller()
        ctrl._on_ports_detected(["COM1", "COM3"])
        view.set_detected_ports.assert_called_once_with(["COM1", "COM3"])

    def test_on_ports_detected_empty_list(self):
        ctrl, _, view = _make_controller()
        ctrl._on_ports_detected([])
        view.set_detected_ports.assert_called_once_with([])

    def test_on_detect_failed_pushes_empty_to_view(self):
        ctrl, _, view = _make_controller()
        ctrl._on_detect_failed("timeout")
        view.set_detected_ports.assert_called_once_with([])


# ---------------------------------------------------------------------------
# _on_test_done / _on_test_failed
# ---------------------------------------------------------------------------

class TestModbusSettingsControllerTestConnection(unittest.TestCase):

    def test_on_test_done_success_pushes_to_view(self):
        ctrl, _, view = _make_controller()
        ctrl._on_test_done(True, "COM3")
        view.set_connection_result.assert_called_once_with(True, "COM3")

    def test_on_test_done_failure_pushes_to_view(self):
        ctrl, _, view = _make_controller()
        ctrl._on_test_done(False, "COM3")
        view.set_connection_result.assert_called_once_with(False, "COM3")

    def test_on_test_failed_pushes_failure_to_view(self):
        ctrl, _, view = _make_controller()
        ctrl._on_test_failed("serial error")
        view.set_connection_result.assert_called_once_with(False, "")


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

class TestModbusSettingsControllerStop(unittest.TestCase):

    def test_stop_clears_active_list(self):
        ctrl, _, _ = _make_controller()
        ctrl.stop()
        self.assertEqual(ctrl._active, [])

    def test_stop_does_not_raise_when_empty(self):
        ctrl, _, _ = _make_controller()
        ctrl.stop()   # must not raise


# ---------------------------------------------------------------------------
# Integration — PluginSpec in GlueRobotApp
# ---------------------------------------------------------------------------

class TestModbusSettingsPluginSpec(unittest.TestCase):

    def _spec(self):
        from src.robot_apps.glue.glue_robot_app import GlueRobotApp
        return next(
            (s for s in GlueRobotApp.shell.plugins if s.name == "ModbusSettings"),
            None,
        )

    def test_spec_declared(self):
        self.assertIsNotNone(self._spec())

    def test_spec_folder_id(self):
        self.assertEqual(self._spec().folder_id, 2)

    def test_spec_has_factory(self):
        self.assertIsNotNone(self._spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(self._spec().icon)

    def test_factory_returns_widget_plugin(self):
        from src.plugins.base.widget_plugin import WidgetPlugin
        ss  = MagicMock()
        ss.get.return_value = ModbusConfig()
        app = MagicMock()
        app._settings_service = ss
        plugin = self._spec().factory(app)
        self.assertIsInstance(plugin, WidgetPlugin)

    def test_factory_registers_messaging_service(self):
        ss  = MagicMock()
        ss.get.return_value = ModbusConfig()
        app = MagicMock()
        app._settings_service = ss
        plugin = self._spec().factory(app)
        ms = MagicMock()
        plugin.register(ms)
        self.assertIs(plugin._messaging_service, ms)


if __name__ == "__main__":
    unittest.main()
