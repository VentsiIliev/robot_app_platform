import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.applications.base.robot_jog_service import RobotJogService
from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.configuration.movement_group_settings import MovementGroupSettings
from src.engine.robot.configuration.robot_settings import MovementGroup


class TestRobotJogService(unittest.TestCase):
    def test_jog_moves_configured_tool_from_current_pose(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = True
        robot.get_current_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        service = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: 1,
            user_getter=lambda: 2,
            move_velocity=20.0,
            move_acceleration=10.0,
        )

        service.jog("X", "PLUS", 5.0)

        robot.set_active_tool.assert_called_once_with(1)
        robot.move_fast_linear.assert_called_once_with(
            position=[15.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            tool=1,
            user=2,
            vel=20.0,
            acc=10.0,
            trajectory_optimizer="TOTG",
        )

    def test_jog_uses_live_motion_settings_getters(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = True
        robot.get_current_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        service = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: 1,
            user_getter=lambda: 2,
            move_velocity=10.0,
            move_acceleration=10.0,
            move_velocity_getter=lambda: 35.0,
            move_acceleration_getter=lambda: 25.0,
        )

        service.jog("X", "PLUS", 5.0)

        robot.move_fast_linear.assert_called_once_with(
            position=[15.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            tool=1,
            user=2,
            vel=35.0,
            acc=25.0,
            trajectory_optimizer="TOTG",
        )

    def test_rotation_jog_uses_linear_pose_move(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = True
        robot.get_current_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        service = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: 1,
            user_getter=lambda: 2,
            move_velocity=10.0,
            move_acceleration=10.0,
            move_velocity_getter=lambda: 35.0,
            move_acceleration_getter=lambda: 25.0,
        )

        service.jog("RZ", "PLUS", 5.0)

        robot.start_jog.assert_not_called()
        robot.move_fast_linear.assert_called_once_with(
            position=[10.0, 20.0, 30.0, 0.0, 0.0, 5.0],
            tool=1,
            user=2,
            vel=35.0,
            acc=25.0,
            trajectory_optimizer="TOTG",
        )

    def test_builder_uses_ten_when_saved_jog_velocity_or_acceleration_is_zero(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = True
        robot.get_current_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        settings_service = MagicMock()
        settings_service.get.side_effect = lambda key: (
            SimpleNamespace(robot_tool=1, robot_user=2)
            if key == CommonSettingsID.ROBOT_CONFIG
            else MovementGroupSettings(
                movement_groups={"JOG": MovementGroup(velocity=0, acceleration=0)}
            )
        )
        robot_system = MagicMock()
        robot_system._robot = robot
        robot_system._settings_service = settings_service
        robot_system._robot_config = MagicMock(robot_tool=1, robot_user=2)
        service = build_robot_system_jog_service(robot_system)

        service.jog("X", "PLUS", 5.0)

        settings_service.get.assert_called_with(CommonSettingsID.MOVEMENT_GROUPS)
        robot.move_fast_linear.assert_called_once_with(
            position=[15.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            tool=1,
            user=2,
            vel=10.0,
            acc=10.0,
            trajectory_optimizer="TOTG",
        )

    def test_builder_reads_current_tool_and_workobject_from_settings(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.get_current_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        settings_service = MagicMock()
        settings_service.get.side_effect = lambda key: (
            SimpleNamespace(robot_tool=0, robot_user=0)
            if key == CommonSettingsID.ROBOT_CONFIG
            else MovementGroupSettings(
                movement_groups={"JOG": MovementGroup(velocity=10, acceleration=10)}
            )
        )
        robot_system = SimpleNamespace(
            _robot=robot,
            _settings_service=settings_service,
            _robot_config=SimpleNamespace(robot_tool=1, robot_user=1),
        )
        service = build_robot_system_jog_service(robot_system)

        service.jog("X", "PLUS", 5.0)

        robot.set_active_tool.assert_called_once_with(0)
        self.assertEqual(robot.move_fast_linear.call_args.kwargs["tool"], 0)
        self.assertEqual(robot.move_fast_linear.call_args.kwargs["user"], 0)

    def test_jog_activates_tool_before_reading_current_position(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = True
        robot.get_current_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        calls = []
        robot.set_active_tool.side_effect = lambda tool: calls.append(("set_active_tool", tool)) or True
        robot.set_active_workobject.side_effect = lambda user: calls.append(("set_active_workobject", user)) or True
        robot.get_current_position.side_effect = lambda: calls.append(("get_current_position", None)) or [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        service = RobotJogService(robot_service=robot, tool_getter=lambda: 1, user_getter=lambda: 0)

        service.jog("X", "PLUS", 1.0)

        self.assertEqual(
            calls[:3],
            [("set_active_tool", 1), ("set_active_workobject", 0), ("get_current_position", None)],
        )

    def test_jog_aborts_when_configured_tool_cannot_be_activated(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = False
        service = RobotJogService(robot_service=robot, tool_getter=lambda: 1, user_getter=lambda: 0)

        service.jog("X", "PLUS", 1.0)

        robot.get_current_position.assert_not_called()
        robot.move_linear.assert_not_called()

    def test_step_jog_applies_delta_in_configured_user_frame(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = True
        robot.get_current_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 90.0]
        service = RobotJogService(robot_service=robot, tool_getter=lambda: 1, user_getter=lambda: 0)

        service.jog("X", "PLUS", 5.0)

        target = robot.move_fast_linear.call_args.kwargs["position"]
        self.assertAlmostEqual(target[0], 15.0, places=6)
        self.assertAlmostEqual(target[1], 20.0, places=6)
        self.assertAlmostEqual(target[2], 30.0, places=6)
        self.assertEqual(target[3:], [0.0, 0.0, 90.0])

    def test_servo_jog_uses_same_tool_user_frame_and_direction_as_step(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = True
        robot.start_servo_jog.return_value = 0
        service = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: 1,
            user_getter=lambda: 2,
        )

        service.jog("SERVO_JOG", "Y", "PLUS", 8.0)

        robot.set_active_tool.assert_called_once_with(1)
        robot.set_active_workobject.assert_called_once_with(2)
        robot.start_servo_jog.assert_called_once()
        args = robot.start_servo_jog.call_args.args
        kwargs = robot.start_servo_jog.call_args.kwargs
        self.assertEqual(args[0].name, "Y")
        self.assertEqual(args[1].name, "PLUS")
        self.assertEqual(kwargs["frame"], "user")
        self.assertEqual(kwargs["tool"], 1)
        self.assertEqual(kwargs["user"], 2)
        self.assertFalse(kwargs["disable_collision_checking"])

    def test_recovery_mode_scopes_collision_override_to_servo_z_plus(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = True
        robot.start_servo_jog.return_value = 0
        service = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: 1,
            user_getter=lambda: 1,
        )
        service.set_recovery_mode(True)

        service.jog("SERVO_JOG", "Z", "PLUS", 5.0)

        self.assertTrue(
            robot.start_servo_jog.call_args.kwargs["disable_collision_checking"]
        )

    def test_recovery_mode_disables_collision_for_operator_selected_servo_axis(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = True
        robot.start_servo_jog.return_value = 0
        service = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: 1,
            user_getter=lambda: 1,
        )
        service.set_recovery_mode(True)

        service.jog("SERVO_JOG", "Z", "MINUS", 5.0)

        self.assertTrue(
            robot.start_servo_jog.call_args.kwargs["disable_collision_checking"]
        )

    def test_recovery_servo_uses_configured_recovery_speed_limit(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = True
        robot.start_servo_jog.return_value = 0
        service = RobotJogService(
            robot_service=robot,
            servo_linear_speed_mm_s=250.0,
            recovery_servo_linear_speed_getter=lambda: 40.0,
        )
        service.set_recovery_mode(True)

        service.jog("SERVO_JOG", "X", "PLUS", 150.0)

        self.assertEqual(
            40.0, robot.start_servo_jog.call_args.kwargs["linear_mm_s"]
        )

    def test_recovery_step_above_zero_requests_collision_recovery_without_floor_bypass(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = True
        robot.get_current_position.return_value = [10, 20, 30, 0, 0, 0]
        service = RobotJogService(robot_service=robot, tool_getter=lambda: 1, user_getter=lambda: 1)
        service.set_recovery_mode(True)

        service.jog("JOG_ROBOT", "X", "PLUS", 1.0)

        kwargs = robot.move_linear.call_args.kwargs
        self.assertTrue(kwargs["allow_collision_recovery"])
        self.assertTrue(kwargs["bypass_safety_limits"])
        self.assertNotIn("allow_subzero_step_recovery", kwargs)

    def test_servo_jog_caps_slider_speed_to_configured_maximum(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = True
        robot.start_servo_jog.return_value = 0
        service = RobotJogService(
            robot_service=robot,
            tool_getter=lambda: 1,
            user_getter=lambda: 2,
            servo_linear_speed_getter=lambda: 10.0,
        )

        service.jog("SERVO_JOG", "Z", "PLUS", 100.0)

        self.assertEqual(robot.start_servo_jog.call_args.kwargs["linear_mm_s"], 10.0)

    def test_jog_aborts_when_configured_workobject_cannot_be_activated(self):
        robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot.set_active_workobject.return_value = False
        service = RobotJogService(robot_service=robot, tool_getter=lambda: 1, user_getter=lambda: 2)

        service.jog("X", "PLUS", 1.0)

        robot.get_current_position.assert_not_called()
        robot.move_linear.assert_not_called()

    def test_jog_ignores_frame_options_and_pose_resolver_offsets(self):
        robot = MagicMock()
        robot._robot = None
        robot.set_active_tool.return_value = True
        robot.get_current_position.return_value = [1.0, 2.0, 3.0, 0.0, 0.0, 0.0]
        resolver = MagicMock()
        resolver.available_frames.return_value = ["camera", "tool"]
        resolver.resolve.return_value = [999.0, 999.0, 999.0, 0.0, 0.0, 0.0]
        service = RobotJogService(
            robot_service=robot,
            pose_resolver=resolver,
            frame_options_getter=lambda: ["camera", "tool"],
            default_frame_getter=lambda: "camera",
            tool_getter=lambda: 1,
        )

        service.set_frame("camera")
        service.jog("Z", "MINUS", 2.0)

        self.assertEqual(service.get_available_frames(), [])
        self.assertEqual(service.get_default_frame(), "")
        resolver.resolve.assert_not_called()
        robot.move_fast_linear.assert_called_once()
        self.assertEqual(
            robot.move_fast_linear.call_args.kwargs["position"],
            [1.0, 2.0, 1.0, 0.0, 0.0, 0.0],
        )

    def test_jog_does_not_use_native_incremental_jog_when_driver_prefers_it(self):
        robot = MagicMock()
        robot._robot = MagicMock()
        robot.set_active_tool.return_value = True
        robot._robot.prefers_incremental_jog.return_value = True
        robot.get_current_position.return_value = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        service = RobotJogService(robot_service=robot, tool_getter=lambda: 1, user_getter=lambda: 0)

        service.jog("Y", "PLUS", 4.0)

        robot.start_jog.assert_not_called()
        robot.move_fast_linear.assert_called_once()
        self.assertEqual(
            robot.move_fast_linear.call_args.kwargs["position"],
            [0.0, 4.0, 0.0, 0.0, 0.0, 0.0],
        )


if __name__ == "__main__":
    unittest.main()
