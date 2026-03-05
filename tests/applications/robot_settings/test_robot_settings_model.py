import unittest
from unittest.mock import MagicMock, call

from src.robot_systems.glue.settings_ids import SettingsID
from src.engine.robot.configuration import (
    RobotSettings,
    RobotCalibrationSettings,
    MovementGroup,
)
from src.applications.robot_settings.model.mapper import RobotSettingsMapper, RobotCalibrationMapper
from src.applications.robot_settings.model.robot_settings_model import RobotSettingsModel


def _make_service(config=None, calibration=None):
    service = MagicMock()
    service.load_config.return_value      = config      or RobotSettings()
    service.load_calibration.return_value = calibration or RobotCalibrationSettings()
    return service


class TestRobotSettingsModelLoad(unittest.TestCase):

    def test_load_calls_service(self):
        service = _make_service()
        model   = RobotSettingsModel(service)
        model.load()
        service.load_config.assert_called_once()
        service.load_calibration.assert_called_once()

    def test_load_returns_config_and_calibration(self):
        cfg   = RobotSettings(robot_ip="1.2.3.4")
        calib = RobotCalibrationSettings(z_target=500)
        model = RobotSettingsModel(_make_service(cfg, calib))
        returned_cfg, returned_calib = model.load()
        self.assertEqual(returned_cfg.robot_ip, "1.2.3.4")
        self.assertEqual(returned_calib.z_target, 500)

    def test_config_accessible_after_load(self):
        cfg   = RobotSettings(robot_ip="5.5.5.5")
        model = RobotSettingsModel(_make_service(cfg))
        model.load()
        self.assertEqual(model._config.robot_ip, "5.5.5.5")


class TestRobotSettingsModelSave(unittest.TestCase):

    def _loaded_model(self, config=None, calibration=None):
        service = _make_service(config, calibration)
        model   = RobotSettingsModel(service)
        model.load()
        return model, service

    def test_save_calls_save_config(self):
        model, service = self._loaded_model()
        flat = RobotSettingsMapper.to_flat_dict(RobotSettings())
        model.save(flat, {})
        service.save_config.assert_called_once()

    def test_save_calls_save_calibration(self):
        model, service = self._loaded_model()
        flat = RobotSettingsMapper.to_flat_dict(RobotSettings())
        model.save(flat, {})
        service.save_calibration.assert_called_once()

    def test_save_updates_robot_ip(self):
        model, service = self._loaded_model(RobotSettings(robot_ip="1.1.1.1"))
        flat = RobotSettingsMapper.to_flat_dict(RobotSettings(robot_ip="1.1.1.1"))
        flat["robot_ip"] = "9.9.9.9"
        model.save(flat, {})
        saved_config = service.save_config.call_args[0][0]
        self.assertEqual(saved_config.robot_ip, "9.9.9.9")

    def test_save_persists_movement_groups(self):
        model, service = self._loaded_model()
        flat   = RobotSettingsMapper.to_flat_dict(RobotSettings())
        groups = {"HOME_POS": MovementGroup(velocity=100, acceleration=50)}
        model.save(flat, groups)
        saved_config = service.save_config.call_args[0][0]
        self.assertIn("HOME_POS", saved_config.movement_groups)

    def test_save_updates_internal_config(self):
        model, service = self._loaded_model(RobotSettings(robot_ip="1.1.1.1"))
        flat = RobotSettingsMapper.to_flat_dict(RobotSettings())
        flat["robot_ip"] = "2.2.2.2"
        model.save(flat, {})
        self.assertEqual(model._config.robot_ip, "2.2.2.2")

    def test_save_updates_calibration_z_target(self):
        model, service = self._loaded_model(calibration=RobotCalibrationSettings(z_target=300))
        flat = RobotSettingsMapper.to_flat_dict(RobotSettings())
        calib_flat = RobotCalibrationMapper.to_flat_dict(RobotCalibrationSettings(z_target=300))
        flat.update(calib_flat)
        flat["calib_z_target"] = 600
        model.save(flat, {})
        saved_calib = service.save_calibration.call_args[0][0]
        self.assertEqual(saved_calib.z_target, 600)

    def test_save_without_load_raises(self):
        service = _make_service()
        model   = RobotSettingsModel(service)
        with self.assertRaises(Exception):
            model.save({}, {})


class TestRobotSettingsApplicationService(unittest.TestCase):

    def _make_settings_service(self, config=None, calibration=None):
        ss = MagicMock()
        ss.get.side_effect = lambda key: (
            config      if key == "robot_config"      else
            calibration if key == "robot_calibration" else None
        )
        return ss

    def test_load_config_delegates_to_settings_service(self):
        from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
        cfg = RobotSettings(robot_ip="7.7.7.7")
        ss  = self._make_settings_service(config=cfg)
        svc = RobotSettingsApplicationService(ss,config_key=SettingsID.ROBOT_CONFIG,calibration_key=SettingsID.ROBOT_CALIBRATION)
        self.assertEqual(svc.load_config().robot_ip, "7.7.7.7")

    def test_load_calibration_delegates_to_settings_service(self):
        from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
        calib = RobotCalibrationSettings(z_target=999)
        ss    = self._make_settings_service(calibration=calib)
        svc   = RobotSettingsApplicationService(ss,config_key=SettingsID.ROBOT_CONFIG,calibration_key=SettingsID.ROBOT_CALIBRATION)
        self.assertEqual(svc.load_calibration().z_target, 999)

    def test_save_config_delegates_to_settings_service(self):
        from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
        ss  = MagicMock()
        svc = RobotSettingsApplicationService(ss,config_key=SettingsID.ROBOT_CONFIG,calibration_key=SettingsID.ROBOT_CALIBRATION)
        cfg = RobotSettings()
        svc.save_config(cfg)
        ss.save.assert_called_once_with("robot_config", cfg)

    def test_save_calibration_delegates_to_settings_service(self):
        from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
        ss    = MagicMock()
        svc   = RobotSettingsApplicationService(ss,config_key=SettingsID.ROBOT_CONFIG,calibration_key=SettingsID.ROBOT_CALIBRATION)
        calib = RobotCalibrationSettings()
        svc.save_calibration(calib)
        ss.save.assert_called_once_with("robot_calibration", calib)


class TestRobotSettingsModelMotionDelegation(unittest.TestCase):

    def _loaded(self):
        service = _make_service()
        model   = RobotSettingsModel(service)
        model.load()
        return model, service

    def test_get_current_position_delegates(self):
        model, service = self._loaded()
        service.get_current_position.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        self.assertEqual(model.get_current_position(), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        service.get_current_position.assert_called_once()

    def test_get_slot_info_delegates(self):
        model, service = self._loaded()
        service.get_slot_info.return_value = [(1, "Grip"), (2, None)]
        self.assertEqual(model.get_slot_info(), [(1, "Grip"), (2, None)])

    def test_move_to_group_delegates(self):
        model, service = self._loaded()
        service.move_to_group.return_value = True
        self.assertTrue(model.move_to_group("HOME"))
        service.move_to_group.assert_called_once_with("HOME")

    def test_execute_group_delegates(self):
        model, service = self._loaded()
        service.execute_group.return_value = True
        self.assertTrue(model.execute_group("TRAJ"))
        service.execute_group.assert_called_once_with("TRAJ")

    def test_move_to_point_delegates(self):
        model, service = self._loaded()
        service.move_to_point.return_value = True
        self.assertTrue(model.move_to_point("HOME", "[0,0,0,0,0,0]"))
        service.move_to_point.assert_called_once_with("HOME", "[0,0,0,0,0,0]")


class TestRobotSettingsModelExpectedMovementGroups(unittest.TestCase):

    def _loaded(self, config=None):
        cfg     = config or RobotSettings()
        service = _make_service(config=cfg)
        service.get_slot_info.return_value = []
        model   = RobotSettingsModel(service)
        model.load()
        return model, service

    def test_returns_existing_groups(self):
        cfg = RobotSettings()
        cfg.movement_groups = {"HOME": MovementGroup(velocity=50)}
        model, _ = self._loaded(cfg)
        self.assertIn("HOME", model.get_expected_movement_groups())

    def test_adds_pickup_and_dropoff_for_assigned_tool(self):
        model, service = self._loaded()
        service.get_slot_info.return_value = [(1, "Gripper")]
        result = model.get_expected_movement_groups()
        self.assertIn("SLOT 1 PICKUP",  result)
        self.assertIn("SLOT 1 DROPOFF", result)

    def test_skips_slot_with_no_tool(self):
        model, service = self._loaded()
        service.get_slot_info.return_value = [(1, None)]
        result = model.get_expected_movement_groups()
        self.assertNotIn("SLOT 1 PICKUP", result)

    def test_does_not_overwrite_existing_slot_group(self):
        cfg = RobotSettings()
        cfg.movement_groups["SLOT 1 PICKUP"] = MovementGroup(velocity=99)
        model, service = self._loaded(cfg)
        service.get_slot_info.return_value = [(1, "Gripper")]
        result = model.get_expected_movement_groups()
        self.assertEqual(result["SLOT 1 PICKUP"].velocity, 99)

if __name__ == "__main__":
    unittest.main()