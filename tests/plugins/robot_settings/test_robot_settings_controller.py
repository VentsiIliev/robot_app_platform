import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings, MovementGroup
from src.plugins.robot_settings.controller.robot_settings_controller import RobotSettingsController
from src.plugins.robot_settings.model.robot_settings_model import RobotSettingsModel
from src.plugins.robot_settings.model.mapper import RobotSettingsMapper, RobotCalibrationMapper


def _make_view():
    view = MagicMock()
    view.save_requested  = MagicMock()
    view.destroyed       = MagicMock()
    view.save_requested.connect  = MagicMock()
    view.destroyed.connect       = MagicMock()
    return view


def _make_model(config=None, calibration=None):
    model = MagicMock(spec=RobotSettingsModel)
    cfg   = config      or RobotSettings()
    calib = calibration or RobotCalibrationSettings()
    model.load.return_value = (cfg, calib)
    model._config           = cfg
    model._calibration      = calib
    return model


class TestRobotSettingsControllerInit(unittest.TestCase):

    def test_wires_save_requested_signal(self):
        view  = _make_view()
        model = _make_model()
        RobotSettingsController(model, view)
        view.save_requested.connect.assert_called_once()

    def test_wires_destroyed_signal(self):
        view  = _make_view()
        model = _make_model()
        RobotSettingsController(model, view)
        view.destroyed.connect.assert_called_once()


class TestRobotSettingsControllerLoad(unittest.TestCase):

    def test_load_calls_model_load(self):
        view  = _make_view()
        model = _make_model(RobotSettings(robot_ip="1.2.3.4"))
        ctrl  = RobotSettingsController(model, view)
        ctrl.load()
        model.load.assert_called_once()

    def test_load_pushes_config_to_view(self):
        cfg   = RobotSettings(robot_ip="5.5.5.5")
        view  = _make_view()
        model = _make_model(cfg)
        ctrl  = RobotSettingsController(model, view)
        ctrl.load()
        view.load_config.assert_called_once_with(cfg)

    def test_load_pushes_movement_groups_to_view(self):
        cfg            = RobotSettings()
        cfg.movement_groups = {"HOME_POS": MovementGroup(velocity=100)}
        view  = _make_view()
        model = _make_model(cfg)
        ctrl  = RobotSettingsController(model, view)
        ctrl.load()
        view.load_movement_groups.assert_called_once_with(cfg.movement_groups)


class TestRobotSettingsControllerSave(unittest.TestCase):

    def _make_controller(self, config=None, calibration=None):
        cfg   = config      or RobotSettings()
        calib = calibration or RobotCalibrationSettings()
        view  = _make_view()
        model = _make_model(cfg, calib)
        ctrl  = RobotSettingsController(model, view)
        ctrl.load()

        flat    = RobotSettingsMapper.to_flat_dict(cfg)
        flat.update(RobotCalibrationMapper.to_flat_dict(calib))
        view.get_values.return_value         = flat
        view.get_movement_groups.return_value = {}
        return ctrl, model, view

    def test_on_save_calls_model_save(self):
        ctrl, model, view = self._make_controller()
        ctrl._on_save({})
        model.save.assert_called_once()

    def test_on_save_passes_flat_dict_from_view(self):
        cfg  = RobotSettings(robot_ip="4.4.4.4")
        ctrl, model, view = self._make_controller(cfg)
        flat = RobotSettingsMapper.to_flat_dict(cfg)
        view.get_values.return_value = flat
        ctrl._on_save({})
        actual_flat = model.save.call_args[0][0]
        self.assertEqual(actual_flat["robot_ip"], "4.4.4.4")

    def test_on_save_passes_movement_groups_from_view(self):
        ctrl, model, view = self._make_controller()
        groups = {"JOG": MovementGroup(velocity=50)}
        view.get_movement_groups.return_value = groups
        ctrl._on_save({})
        actual_groups = model.save.call_args[0][1]
        self.assertEqual(actual_groups, groups)

    def test_stop_does_not_raise(self):
        view  = _make_view()
        model = _make_model()
        ctrl  = RobotSettingsController(model, view)
        ctrl.stop()   # should be a no-op, must not raise


if __name__ == "__main__":
    unittest.main()