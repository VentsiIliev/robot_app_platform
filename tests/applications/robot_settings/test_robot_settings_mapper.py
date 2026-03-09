import unittest
from copy import deepcopy

from src.engine.robot.configuration import (
    RobotSettings,
    RobotCalibrationSettings,
    SafetyLimits,
    GlobalMotionSettings,
    OffsetDirectionMap,
    MovementGroup,
)
from src.applications.robot_settings.model.mapper import (
    RobotCalibrationMapper,
    RobotSettingsMapper,
)


class TestRobotSettingsMapperToFlatDict(unittest.TestCase):

    def setUp(self):
        self.config = RobotSettings(
            robot_ip="10.0.0.1",
            robot_tool=2,
            robot_user=1,
            tcp_x_offset=1.5,
            tcp_y_offset=2.5,
            tcp_x_step_distance=60.0,
            tcp_x_step_offset=0.05,
            tcp_y_step_distance=70.0,
            tcp_y_step_offset=0.07,
            offset_direction_map=OffsetDirectionMap(pos_x=True, neg_x=False, pos_y=True, neg_y=False),
            safety_limits=SafetyLimits(x_min=-400, x_max=400, y_min=-300, y_max=300,
                                       z_min=50, z_max=700,
                                       rx_min=170, rx_max=190,
                                       ry_min=-5, ry_max=5,
                                       rz_min=-180, rz_max=180),
            global_motion_settings=GlobalMotionSettings(
                global_velocity=200, global_acceleration=200,
                emergency_decel=400, max_jog_step=30,
            ),
        )

    def test_robot_ip_present(self):
        flat = RobotSettingsMapper.to_flat_dict(self.config)
        self.assertEqual(flat["robot_ip"], "10.0.0.1")

    def test_robot_tool_present(self):
        flat = RobotSettingsMapper.to_flat_dict(self.config)
        self.assertEqual(flat["robot_tool"], 2)

    def test_tcp_offsets_present(self):
        flat = RobotSettingsMapper.to_flat_dict(self.config)
        self.assertEqual(flat["tcp_x_offset"], 1.5)
        self.assertEqual(flat["tcp_y_offset"], 2.5)

    def test_global_motion_present(self):
        flat = RobotSettingsMapper.to_flat_dict(self.config)
        self.assertEqual(flat["global_velocity"], 200)
        self.assertEqual(flat["global_acceleration"], 200)
        self.assertEqual(flat["emergency_decel"], 400)
        self.assertEqual(flat["max_jog_step"], 30)

    def test_safety_limits_present(self):
        flat = RobotSettingsMapper.to_flat_dict(self.config)
        self.assertEqual(flat["safety_x_min"], -400)
        self.assertEqual(flat["safety_x_max"], 400)
        self.assertEqual(flat["safety_z_min"], 50)
        self.assertEqual(flat["safety_z_max"], 700)

    def test_offset_direction_as_strings(self):
        flat = RobotSettingsMapper.to_flat_dict(self.config)
        self.assertEqual(flat["offset_pos_x"], "True")
        self.assertEqual(flat["offset_neg_x"], "False")

    def test_all_expected_keys_present(self):
        flat = RobotSettingsMapper.to_flat_dict(self.config)
        expected = {
            "robot_ip", "robot_tool", "robot_user",
            "tcp_x_offset", "tcp_y_offset",
            "tcp_x_step_distance", "tcp_x_step_offset",
            "tcp_y_step_distance", "tcp_y_step_offset",
            "offset_pos_x", "offset_neg_x", "offset_pos_y", "offset_neg_y",
            "global_velocity", "global_acceleration", "emergency_decel", "max_jog_step",
            "safety_x_min", "safety_x_max", "safety_y_min", "safety_y_max",
            "safety_z_min", "safety_z_max",
            "safety_rx_min", "safety_rx_max", "safety_ry_min", "safety_ry_max",
            "safety_rz_min", "safety_rz_max",
        }
        self.assertEqual(expected, set(flat.keys()))


class TestRobotSettingsMapperFromFlatDict(unittest.TestCase):

    def setUp(self):
        self.base = RobotSettings()
        self.flat = RobotSettingsMapper.to_flat_dict(self.base)

    def test_roundtrip_robot_ip(self):
        flat = dict(self.flat, robot_ip="192.168.1.99")
        result = RobotSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(result.robot_ip, "192.168.1.99")

    def test_roundtrip_robot_tool(self):
        flat = dict(self.flat, robot_tool=3)
        result = RobotSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(result.robot_tool, 3)

    def test_roundtrip_safety_limits(self):
        flat = dict(self.flat, safety_x_min=-999, safety_x_max=999)
        result = RobotSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(result.safety_limits.x_min, -999)
        self.assertEqual(result.safety_limits.x_max, 999)

    def test_roundtrip_global_motion(self):
        flat = dict(self.flat, global_velocity=500, emergency_decel=800)
        result = RobotSettingsMapper.from_flat_dict(flat, self.base)
        self.assertEqual(result.global_motion_settings.global_velocity, 500)
        self.assertEqual(result.global_motion_settings.emergency_decel, 800)

    def test_offset_direction_true_string(self):
        flat = dict(self.flat, offset_neg_x="True")
        result = RobotSettingsMapper.from_flat_dict(flat, self.base)
        self.assertTrue(result.offset_direction_map.neg_x)

    def test_offset_direction_false_string(self):
        flat = dict(self.flat, offset_pos_y="False")
        result = RobotSettingsMapper.from_flat_dict(flat, self.base)
        self.assertFalse(result.offset_direction_map.pos_y)

    def test_missing_keys_fall_back_to_base(self):
        result = RobotSettingsMapper.from_flat_dict({}, self.base)
        self.assertEqual(result.robot_ip, self.base.robot_ip)
        self.assertEqual(result.robot_tool, self.base.robot_tool)

    def test_does_not_mutate_base(self):
        original_ip = self.base.robot_ip
        RobotSettingsMapper.from_flat_dict({"robot_ip": "9.9.9.9"}, self.base)
        self.assertEqual(self.base.robot_ip, original_ip)

    def test_full_roundtrip(self):
        config = RobotSettings(robot_ip="1.2.3.4", robot_tool=5, robot_user=2,
                               tcp_x_offset=3.14, tcp_y_offset=2.71)
        flat   = RobotSettingsMapper.to_flat_dict(config)
        result = RobotSettingsMapper.from_flat_dict(flat, config)
        self.assertEqual(result.robot_ip,     config.robot_ip)
        self.assertEqual(result.robot_tool,   config.robot_tool)
        self.assertEqual(result.tcp_x_offset, config.tcp_x_offset)


class TestRobotCalibrationMapperToFlatDict(unittest.TestCase):

    def setUp(self):
        self.settings = RobotCalibrationSettings()

    def test_all_expected_keys_present(self):
        flat = RobotCalibrationMapper.to_flat_dict(self.settings)
        expected = {
            "calib_min_step_mm", "calib_max_step_mm", "calib_target_error_mm",
            "calib_max_error_ref", "calib_k", "calib_derivative_scaling",
            "calib_z_target", "calib_required_ids",
            "calib_axis_marker_id", "calib_axis_move_mm",
            "calib_axis_max_attempts", "calib_axis_delay_after_move",
        }
        self.assertEqual(expected, set(flat.keys()))

    def test_defaults_correct(self):
        flat = RobotCalibrationMapper.to_flat_dict(self.settings)
        self.assertEqual(flat["calib_min_step_mm"],   0.1)
        self.assertEqual(flat["calib_max_step_mm"],   25.0)
        self.assertEqual(flat["calib_z_target"],      300)
        self.assertEqual(flat["calib_required_ids"],  [0, 1, 2, 3, 4, 5, 6, 8])


class TestRobotCalibrationMapperFromFlatDict(unittest.TestCase):

    def setUp(self):
        self.base = RobotCalibrationSettings()

    def test_roundtrip_z_target(self):
        flat = RobotCalibrationMapper.to_flat_dict(self.base)
        flat["calib_z_target"] = 500
        result = RobotCalibrationMapper.from_flat_dict(flat, self.base)
        self.assertEqual(result.z_target, 500)

    def test_roundtrip_adaptive_movement(self):
        flat = RobotCalibrationMapper.to_flat_dict(self.base)
        flat["calib_min_step_mm"]  = 0.5
        flat["calib_max_step_mm"]  = 50.0
        flat["calib_k"]            = 3.0
        result = RobotCalibrationMapper.from_flat_dict(flat, self.base)
        self.assertEqual(result.adaptive_movement.min_step_mm, 0.5)
        self.assertEqual(result.adaptive_movement.max_step_mm, 50.0)
        self.assertEqual(result.adaptive_movement.k,           3.0)

    def test_missing_keys_fall_back_to_base(self):
        result = RobotCalibrationMapper.from_flat_dict({}, self.base)
        self.assertEqual(result.z_target, self.base.z_target)

    def test_does_not_mutate_base(self):
        original_z = self.base.z_target
        RobotCalibrationMapper.from_flat_dict({"calib_z_target": 999}, self.base)
        self.assertEqual(self.base.z_target, original_z)

    def test_full_roundtrip(self):
        flat   = RobotCalibrationMapper.to_flat_dict(self.base)
        result = RobotCalibrationMapper.from_flat_dict(flat, self.base)
        self.assertEqual(result.z_target,                      self.base.z_target)
        self.assertEqual(result.adaptive_movement.min_step_mm, self.base.adaptive_movement.min_step_mm)
        self.assertEqual(result.required_ids,                  self.base.required_ids)


if __name__ == "__main__":
    unittest.main()