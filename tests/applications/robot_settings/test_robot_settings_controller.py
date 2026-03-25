import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings, MovementGroup
from src.applications.robot_settings.controller.robot_settings_controller import RobotSettingsController
from src.applications.robot_settings.model.robot_settings_model import RobotSettingsModel
from src.applications.robot_settings.model.mapper import RobotSettingsMapper, RobotCalibrationMapper


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
    model.load.return_value                         = (cfg, calib, None)
    model._config                                   = cfg
    model._calibration                              = calib
    model.get_slot_info.return_value                = []
    model.get_expected_movement_groups.return_value = cfg.movement_groups
    model.get_movement_group_definitions.return_value = []
    return model


def _make_messaging():
    return MagicMock()


def _make_jog():
    return MagicMock()


def _make_ctrl(model=None, view=None):
    return RobotSettingsController(model or _make_model(), view or _make_view(),
                                   _make_messaging())



class TestRobotSettingsControllerInit(unittest.TestCase):

    def test_wires_save_requested_signal(self):
        view  = _make_view()
        model = _make_model()
        RobotSettingsController(model, view, _make_messaging())
        view.save_requested.connect.assert_called_once()

    def test_wires_destroyed_signal(self):
        view  = _make_view()
        model = _make_model()
        RobotSettingsController(model, view, _make_messaging())
        view.destroyed.connect.assert_called_once()


class TestRobotSettingsControllerLoad(unittest.TestCase):

    def test_load_calls_model_load(self):
        view  = _make_view()
        model = _make_model(RobotSettings(robot_ip="1.2.3.4"))
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()
        model.load.assert_called_once()

    def test_load_pushes_config_to_view(self):
        cfg   = RobotSettings(robot_ip="5.5.5.5")
        view  = _make_view()
        model = _make_model(cfg)
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()
        view.load_config.assert_called_once()
        flat = view.load_config.call_args[0][0]
        self.assertIsInstance(flat, dict)
        self.assertEqual(flat.get("robot_ip"), "5.5.5.5")

    def test_load_pushes_movement_groups_to_view(self):
        cfg = RobotSettings()
        cfg.movement_groups = {"HOME_POS": MovementGroup(velocity=100)}
        view = _make_view()
        model = _make_model(cfg)
        ctrl = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()
        view.load_movement_groups.assert_called_once_with(cfg.movement_groups, definitions=[])


class TestRobotSettingsControllerSave(unittest.TestCase):

    def _make_controller(self, config=None, calibration=None):
        cfg   = config      or RobotSettings()
        calib = calibration or RobotCalibrationSettings()
        view  = _make_view()
        model = _make_model(cfg, calib)
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()

        flat    = RobotSettingsMapper.to_flat_dict(cfg)
        flat.update(RobotCalibrationMapper.to_flat_dict(calib))
        view.get_values.return_value               = flat
        view.get_movement_groups.return_value      = {}
        view.get_targeting_definitions.return_value = None
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
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.stop()   # should be a no-op, must not raise

class TestRobotSettingsControllerInitSignals(unittest.TestCase):

    def test_wires_remove_group_requested(self):
        view = _make_view()
        RobotSettingsController(_make_model(), view, _make_messaging())
        view.remove_group_requested.connect.assert_called_once()

    def test_wires_set_current_requested(self):
        view = _make_view()
        RobotSettingsController(_make_model(), view, _make_messaging())
        view.set_current_requested.connect.assert_called_once()

    def test_wires_move_to_requested(self):
        view = _make_view()
        RobotSettingsController(_make_model(), view, _make_messaging())
        view.move_to_requested.connect.assert_called_once()

    def test_wires_execute_requested(self):
        view = _make_view()
        RobotSettingsController(_make_model(), view, _make_messaging())
        view.execute_requested.connect.assert_called_once()


class TestRobotSettingsControllerAutoSave(unittest.TestCase):

    def _make_loaded(self):
        view  = _make_view()
        model = _make_model()
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()
        view.get_values.return_value               = {}
        view.get_movement_groups.return_value      = {}
        view.get_targeting_definitions.return_value = None
        return ctrl, model, view

    def test_auto_save_calls_model_save(self):
        ctrl, model, _ = self._make_loaded()
        ctrl._auto_save()
        model.save.assert_called_once()

    def test_auto_save_passes_values_from_view(self):
        ctrl, model, view = self._make_loaded()
        flat = {"robot_ip": "9.9.9.9"}
        view.get_values.return_value = flat
        ctrl._auto_save()
        self.assertEqual(model.save.call_args[0][0], flat)

    def test_auto_save_passes_movement_groups_from_view(self):
        ctrl, model, view = self._make_loaded()
        groups = {"HOME": MovementGroup(velocity=50)}
        view.get_movement_groups.return_value = groups
        ctrl._auto_save()
        self.assertEqual(model.save.call_args[0][1], groups)

    def test_auto_save_swallows_exception(self):
        ctrl, model, _ = self._make_loaded()
        model.save.side_effect = RuntimeError("disk full")
        ctrl._auto_save()   # must not propagate


class TestRobotSettingsControllerSetCurrent(unittest.TestCase):

    def _make_loaded(self):
        view  = _make_view()
        model = _make_model()
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()
        view.get_values.return_value          = {}
        view.get_movement_groups.return_value = {}
        return ctrl, model, view

    @patch("src.applications.robot_settings.controller.robot_settings_controller.show_warning")
    def test_shows_warning_when_position_is_none(self, mock_warn):
        ctrl, model, _ = self._make_loaded()
        model.get_current_position.return_value = None
        ctrl._on_set_current("HOME")
        mock_warn.assert_called_once()

    def test_does_nothing_when_widget_not_found(self):
        ctrl, model, view = self._make_loaded()
        model.get_current_position.return_value = [0.0] * 6
        view.get_group_widget.return_value = None
        ctrl._on_set_current("MISSING")   # must not raise

    def test_calls_set_position_for_single_position_group(self):
        from src.shared_contracts.declarations import MovementGroupDefinition as MovementGroupDef, MovementGroupType
        ctrl, model, view = self._make_loaded()
        model.get_current_position.return_value = [100.0, 0.0, 300.0, 180.0, 0.0, 0.0]
        widget = MagicMock()
        widget._def = MovementGroupDef("HOME", MovementGroupType.SINGLE_POSITION)
        view.get_group_widget.return_value = widget
        ctrl._on_set_current("HOME")
        widget.set_position.assert_called_once_with("[100.000, 0.000, 300.000, 180.000, 0.000, 0.000]")

    def test_calls_add_point_for_multi_position_group(self):
        from src.shared_contracts.declarations import MovementGroupDefinition as MovementGroupDef, MovementGroupType
        ctrl, model, view = self._make_loaded()
        model.get_current_position.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        widget = MagicMock()
        widget._def = MovementGroupDef("TRAJ", MovementGroupType.MULTI_POSITION)
        view.get_group_widget.return_value = widget
        ctrl._on_set_current("TRAJ")
        widget.add_point.assert_called_once()
        widget.set_position.assert_not_called()


class TestRobotSettingsControllerMotionDone(unittest.TestCase):

    @patch("src.applications.robot_settings.controller.robot_settings_controller.show_warning")
    def test_shows_warning_on_failure(self, mock_warn):
        ctrl = RobotSettingsController(_make_model(), _make_view(), _make_messaging())
        ctrl._on_motion_done(False, "HOME")
        mock_warn.assert_called_once()

    @patch("src.applications.robot_settings.controller.robot_settings_controller.show_warning")
    def test_no_warning_on_success(self, mock_warn):
        ctrl = RobotSettingsController(_make_model(), _make_view(), _make_messaging())
        ctrl._on_motion_done(True, "HOME")
        mock_warn.assert_not_called()


class TestRobotSettingsControllerRemoveGroup(unittest.TestCase):

    @patch("src.applications.robot_settings.controller.robot_settings_controller.ask_yes_no")
    def test_calls_remove_on_confirm(self, mock_ask):
        view = _make_view()
        ctrl = RobotSettingsController(_make_model(), view, _make_messaging())
        mock_ask.return_value = True
        ctrl._on_remove_group("HOME")
        view.remove_movement_group.assert_called_once_with("HOME")

    @patch("src.applications.robot_settings.controller.robot_settings_controller.ask_yes_no")
    def test_does_nothing_on_cancel(self, mock_ask):
        view = _make_view()
        ctrl = RobotSettingsController(_make_model(), view, _make_messaging())
        mock_ask.return_value = False
        ctrl._on_remove_group("HOME")
        view.remove_movement_group.assert_not_called()

class TestRobotSettingsControllerMoveTo(unittest.TestCase):

    def _make_loaded(self):
        view  = _make_view()
        model = _make_model()
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()
        view.get_values.return_value          = {}
        view.get_movement_groups.return_value = {}
        return ctrl, model, view

    def test_move_to_calls_auto_save(self):
        ctrl, model, view = self._make_loaded()
        view.get_group_widget.return_value = None
        with patch.object(ctrl, '_run_blocking'):
            ctrl._on_move_to("HOME", None)
        model.save.assert_called_once()

    def test_move_to_single_pos_calls_run_blocking(self):
        ctrl, _, view = self._make_loaded()
        view.get_group_widget.return_value = None
        with patch.object(ctrl, '_run_blocking') as mock_block:
            ctrl._on_move_to("HOME", None)
        mock_block.assert_called_once()

    @patch("src.applications.robot_settings.controller.robot_settings_controller.show_warning")
    def test_move_to_multi_pos_no_point_shows_warning(self, mock_warn):
        from src.shared_contracts.declarations import MovementGroupDefinition as MovementGroupDef, MovementGroupType
        ctrl, _, view = self._make_loaded()
        widget = MagicMock()
        widget._def = MovementGroupDef("TRAJ", MovementGroupType.MULTI_POSITION)
        view.get_group_widget.return_value = widget
        with patch.object(ctrl, '_run_blocking') as mock_block:
            ctrl._on_move_to("TRAJ", None)
        mock_warn.assert_called_once()
        mock_block.assert_not_called()

    def test_move_to_explicit_point_calls_run_blocking(self):
        ctrl, _, _ = self._make_loaded()
        with patch.object(ctrl, '_run_blocking') as mock_block:
            ctrl._on_move_to("TRAJ", "[1,2,3,4,5,6]")
        mock_block.assert_called_once()

    def test_move_to_single_pos_fn_delegates_to_move_to_group(self):
        ctrl, model, view = self._make_loaded()
        view.get_group_widget.return_value = None
        captured = {}
        with patch.object(ctrl, '_run_blocking', side_effect=lambda **kw: captured.update(kw)):
            ctrl._on_move_to("HOME", None)
        captured['fn']()
        model.move_to_group.assert_called_once_with("HOME")

    def test_move_to_explicit_point_fn_delegates_to_move_to_point(self):
        ctrl, model, _ = self._make_loaded()
        captured = {}
        with patch.object(ctrl, '_run_blocking', side_effect=lambda **kw: captured.update(kw)):
            ctrl._on_move_to("TRAJ", "[1,2,3,4,5,6]")
        captured['fn']()
        model.move_to_point.assert_called_once_with("TRAJ", "[1,2,3,4,5,6]")


class TestRobotSettingsControllerExecute(unittest.TestCase):

    def _make_loaded(self):
        view  = _make_view()
        model = _make_model()
        ctrl  = RobotSettingsController(model, view, _make_messaging())
        ctrl.load()
        view.get_values.return_value          = {}
        view.get_movement_groups.return_value = {}
        return ctrl, model, view

    def test_execute_calls_auto_save(self):
        ctrl, model, _ = self._make_loaded()
        with patch.object(ctrl, '_run_blocking'):
            ctrl._on_execute("TRAJ")
        model.save.assert_called_once()

    def test_execute_calls_run_blocking(self):
        ctrl, _, _ = self._make_loaded()
        with patch.object(ctrl, '_run_blocking') as mock_block:
            ctrl._on_execute("TRAJ")
        mock_block.assert_called_once()

    def test_execute_fn_delegates_to_execute_group(self):
        ctrl, model, _ = self._make_loaded()
        captured = {}
        with patch.object(ctrl, '_run_blocking', side_effect=lambda **kw: captured.update(kw)):
            ctrl._on_execute("TRAJ")
        captured['fn']()
        model.execute_group.assert_called_once_with("TRAJ")

if __name__ == "__main__":
    unittest.main()