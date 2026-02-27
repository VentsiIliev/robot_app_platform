import unittest
from unittest.mock import MagicMock, patch

from src.robot_systems.glue.glue_settings.controller.glue_settings_controller import GlueSettingsController
from src.robot_systems.glue.glue_settings.model.glue_settings_model import GlueSettingsModel
from src.robot_systems.glue.glue_settings.model.mapper import GlueSettingsMapper
from src.robot_systems.glue.settings.glue import GlueSettings
from src.robot_systems.glue.settings.glue_types import Glue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_view():
    view = MagicMock()
    view.save_requested.connect        = MagicMock()
    view.spray_on_changed.connect      = MagicMock()
    view.add_type_requested.connect    = MagicMock()
    view.update_type_requested.connect = MagicMock()
    view.remove_type_requested.connect = MagicMock()
    view.destroyed.connect             = MagicMock()
    return view


def _make_model(settings=None, types=None):
    model = MagicMock(spec=GlueSettingsModel)
    model.load.return_value            = settings or GlueSettings()
    model.load_glue_types.return_value = types    or []
    return model


def _make_controller(settings=None, types=None):
    model = _make_model(settings, types)
    view  = _make_view()
    ctrl  = GlueSettingsController(model, view)
    flat  = GlueSettingsMapper.to_flat_dict(settings or GlueSettings())
    view.get_values.return_value = flat
    return ctrl, model, view


# ---------------------------------------------------------------------------
# Init — signal wiring
# ---------------------------------------------------------------------------

class TestGlueSettingsControllerInit(unittest.TestCase):

    def test_wires_save_requested(self):
        _, _, view = _make_controller()
        view.save_requested.connect.assert_called_once()

    def test_wires_spray_on_changed(self):
        _, _, view = _make_controller()
        view.spray_on_changed.connect.assert_called_once()

    def test_wires_add_type_requested(self):
        _, _, view = _make_controller()
        view.add_type_requested.connect.assert_called_once()

    def test_wires_update_type_requested(self):
        _, _, view = _make_controller()
        view.update_type_requested.connect.assert_called_once()

    def test_wires_remove_type_requested(self):
        _, _, view = _make_controller()
        view.remove_type_requested.connect.assert_called_once()

    def test_wires_destroyed(self):
        _, _, view = _make_controller()
        view.destroyed.connect.assert_called_once()


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestGlueSettingsControllerLoad(unittest.TestCase):

    def test_load_calls_model_load(self):
        ctrl, model, _ = _make_controller()
        ctrl.load()
        model.load.assert_called_once()

    def test_load_pushes_settings_to_view(self):
        cfg  = GlueSettings(spray_width=4.4)
        ctrl, _, view = _make_controller(cfg)
        ctrl.load()
        view.load_settings.assert_called_once_with(cfg)

    def test_load_pushes_glue_types_to_view(self):
        types = [Glue(name="Type A"), Glue(name="Type B")]
        ctrl, model, view = _make_controller(types=types)
        model.load_glue_types.return_value = types
        ctrl.load()
        view.load_glue_types.assert_called_once_with(types)


# ---------------------------------------------------------------------------
# _on_save
# ---------------------------------------------------------------------------

class TestGlueSettingsControllerSave(unittest.TestCase):

    def test_on_save_calls_model_save(self):
        ctrl, model, _ = _make_controller()
        ctrl._on_save({})
        model.save.assert_called_once()

    def test_on_save_passes_view_values(self):
        cfg  = GlueSettings(spray_width=2.2)
        ctrl, model, view = _make_controller(cfg)
        flat = GlueSettingsMapper.to_flat_dict(cfg)
        view.get_values.return_value = flat
        ctrl._on_save({})
        actual_flat = model.save.call_args[0][0]
        self.assertEqual(actual_flat["spray_width"], 2.2)

    def test_on_save_exception_does_not_propagate(self):
        ctrl, model, _ = _make_controller()
        model.save.side_effect = RuntimeError("disk full")
        ctrl._on_save({})   # must not raise


# ---------------------------------------------------------------------------
# _on_spray_on_changed  — auto-save
# ---------------------------------------------------------------------------

class TestGlueSettingsControllerSprayOn(unittest.TestCase):

    def test_spray_on_true_saves(self):
        ctrl, model, view = _make_controller()
        flat = GlueSettingsMapper.to_flat_dict(GlueSettings(spray_on=False))
        view.get_values.return_value = flat
        ctrl._on_spray_on_changed(True)
        model.save.assert_called_once()

    def test_spray_on_value_overridden_in_flat(self):
        ctrl, model, view = _make_controller()
        flat = dict(GlueSettingsMapper.to_flat_dict(GlueSettings()), spray_on=False)
        view.get_values.return_value = flat
        ctrl._on_spray_on_changed(True)
        saved_flat = model.save.call_args[0][0]
        self.assertTrue(saved_flat["spray_on"])

    def test_spray_on_false_saves_false(self):
        ctrl, model, view = _make_controller()
        flat = dict(GlueSettingsMapper.to_flat_dict(GlueSettings()), spray_on=True)
        view.get_values.return_value = flat
        ctrl._on_spray_on_changed(False)
        saved_flat = model.save.call_args[0][0]
        self.assertFalse(saved_flat["spray_on"])

    def test_spray_on_exception_does_not_propagate(self):
        ctrl, model, _ = _make_controller()
        model.save.side_effect = RuntimeError("boom")
        ctrl._on_spray_on_changed(True)   # must not raise


# ---------------------------------------------------------------------------
# Glue type CRUD
# ---------------------------------------------------------------------------

class TestGlueSettingsControllerGlueTypes(unittest.TestCase):

    def test_add_type_calls_model(self):
        ctrl, model, _ = _make_controller()
        model.add_glue_type.return_value = Glue(name="New")
        ctrl._on_add_type("New", "desc")
        model.add_glue_type.assert_called_once_with("New", "desc")

    def test_add_type_reloads_view(self):
        ctrl, model, view = _make_controller()
        model.add_glue_type.return_value  = Glue(name="New")
        model.load_glue_types.return_value = [Glue(name="New")]
        ctrl._on_add_type("New", "desc")
        view.load_glue_types.assert_called()

    def test_add_type_exception_does_not_propagate(self):
        ctrl, model, _ = _make_controller()
        model.add_glue_type.side_effect = RuntimeError("db error")
        ctrl._on_add_type("X", "")   # must not raise

    def test_update_type_calls_model(self):
        ctrl, model, _ = _make_controller()
        model.update_glue_type.return_value = Glue(name="Updated")
        ctrl._on_update_type("some-id", "Updated", "new desc")
        model.update_glue_type.assert_called_once_with("some-id", "Updated", "new desc")

    def test_update_type_reloads_view(self):
        ctrl, model, view = _make_controller()
        model.update_glue_type.return_value  = Glue(name="Updated")
        model.load_glue_types.return_value   = [Glue(name="Updated")]
        ctrl._on_update_type("id", "Updated", "")
        view.load_glue_types.assert_called()

    def test_update_type_exception_does_not_propagate(self):
        ctrl, model, _ = _make_controller()
        model.update_glue_type.side_effect = KeyError("bad-id")
        ctrl._on_update_type("bad-id", "X", "")   # must not raise

    def test_remove_type_calls_model(self):
        ctrl, model, _ = _make_controller()
        ctrl._on_remove_type("del-id")
        model.remove_glue_type.assert_called_once_with("del-id")

    def test_remove_type_reloads_view(self):
        ctrl, model, view = _make_controller()
        ctrl._on_remove_type("del-id")
        view.load_glue_types.assert_called()

    def test_remove_type_exception_does_not_propagate(self):
        ctrl, model, _ = _make_controller()
        model.remove_glue_type.side_effect = KeyError("bad-id")
        ctrl._on_remove_type("bad-id")   # must not raise

    def test_stop_does_not_raise(self):
        ctrl, _, _ = _make_controller()
        ctrl.stop()


# ---------------------------------------------------------------------------
# Integration — PluginSpec declared in GlueRobotApp
# ---------------------------------------------------------------------------

class TestGlueSettingsPluginSpec(unittest.TestCase):

    def _spec(self):
        from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
        return next(
            (s for s in GlueRobotSystem.shell.plugins if s.name == "GlueSettings"),
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
        from unittest.mock import MagicMock
        from src.plugins.base.widget_plugin import WidgetPlugin
        from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
        ss  = MagicMock()
        ss.get.side_effect = lambda k: MagicMock()
        app = MagicMock()
        app._settings_service = ss
        plugin = self._spec().factory(app)
        self.assertIsInstance(plugin, WidgetPlugin)

    def test_factory_registers_messaging_service(self):
        from unittest.mock import MagicMock
        from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
        ss  = MagicMock()
        ss.get.side_effect = lambda k: MagicMock()
        app = MagicMock()
        app._settings_service = ss
        plugin = self._spec().factory(app)
        ms = MagicMock()
        plugin.register(ms)
        self.assertIs(plugin._messaging_service, ms)


if __name__ == "__main__":
    unittest.main()