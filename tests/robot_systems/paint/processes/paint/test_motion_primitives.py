import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.engine.robot.motion_sequence import OrderedPathCommand, OrderedPositionCommand
from src.robot_systems.paint.processes.paint.motion import (
    FreshPoseReadError,
    poses_close,
    read_fresh_pose,
    shift_path_rotation,
    wait_for_stable_pose,
)
from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    build_ordered_paint_contact_segments,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, duration: float) -> None:
        self.now += duration


class TestShiftPathRotation(unittest.TestCase):
    def test_returns_a_copy_when_shift_is_zero(self):
        source = [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]]

        shifted = shift_path_rotation(source, rotation_index=5, shift_degrees=0.0)

        self.assertEqual(source, shifted)
        self.assertIsNot(source, shifted)
        self.assertIsNot(source[0], shifted[0])

    def test_shifts_only_existing_rotation_components(self):
        source = [[1.0, 2.0], [1.0, 2.0, 3.0]]

        shifted = shift_path_rotation(source, rotation_index=2, shift_degrees=10.0)

        self.assertEqual([[1.0, 2.0], [1.0, 2.0, 13.0]], shifted)
        self.assertEqual([[1.0, 2.0], [1.0, 2.0, 3.0]], source)


class TestPosesClose(unittest.TestCase):
    def test_rejects_missing_or_incomplete_poses(self):
        self.assertFalse(poses_close(None, [0.0] * 6))
        self.assertFalse(poses_close([0.0] * 5, [0.0] * 6))

    def test_uses_tolerance_for_linear_axes(self):
        reference = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]

        self.assertTrue(poses_close(reference, [10.0005, 20.0, 30.0, 40.0, 50.0, 60.0]))
        self.assertFalse(poses_close(reference, [10.002, 20.0, 30.0, 40.0, 50.0, 60.0]))

    def test_treats_wrapped_rz_as_equivalent(self):
        self.assertTrue(
            poses_close(
                [10.0, 20.0, 30.0, 40.0, 50.0, 0.0],
                [10.0, 20.0, 30.0, 40.0, 50.0, 360.0],
            )
        )


class TestPoseSampling(unittest.TestCase):
    def test_fresh_read_is_preferred_and_normalized(self):
        robot = MagicMock()
        robot.get_current_position_fresh.return_value = (1, 2, 3, 4, 5, 6, 7)

        pose = read_fresh_pose(robot, error_message="read failed")

        self.assertEqual([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], pose)
        robot.get_current_position.assert_not_called()

    def test_missing_fresh_api_fails_loudly_without_legacy_fallback(self):
        class LegacyRobot:
            def get_current_position(self):
                return [1, 2, 3, 4, 5, 6]

        with self.assertRaisesRegex(FreshPoseReadError, "get_current_position_fresh"):
            read_fresh_pose(LegacyRobot(), error_message="read failed")

    def test_fresh_read_exception_is_propagated_as_explicit_pose_error(self):
        robot = MagicMock()
        robot.get_current_position_fresh.side_effect = OSError("transport failed")

        with self.assertRaisesRegex(FreshPoseReadError, "read failed") as raised:
            read_fresh_pose(robot, error_message="read failed")

        self.assertIsInstance(raised.exception.__cause__, OSError)

    def test_invalid_fresh_pose_fails_loudly(self):
        robot = MagicMock()
        robot.get_current_position_fresh.return_value = [1, 2, 3]

        with self.assertRaisesRegex(FreshPoseReadError, "six finite axis values"):
            read_fresh_pose(robot, error_message="read failed")

    def test_stability_requires_consecutive_samples_with_wrapped_angles(self):
        robot = MagicMock()
        settled_pose = [10.0, 20.0, 30.0, 0.0, 0.0, 360.0]
        robot.get_current_position_fresh.side_effect = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [10.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            [10.0, 20.0, 30.0, 0.0, 0.0, 360.0],
            settled_pose,
        ]
        clock = _FakeClock()

        pose = wait_for_stable_pose(
            robot,
            logger=MagicMock(),
            read_error_message="read failed",
            timeout_message="timeout",
            timeout_s=1.0,
            sample_interval_s=0.05,
            required_stable_samples=2,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertEqual(settled_pose, pose)
        self.assertEqual(4, robot.get_current_position_fresh.call_count)

    def test_unstable_samples_time_out(self):
        robot = MagicMock()
        robot.get_current_position_fresh.side_effect = (
            [float(index), 0.0, 0.0, 0.0, 0.0, 0.0]
            for index in range(20)
        )
        clock = _FakeClock()
        logger = MagicMock()

        pose = wait_for_stable_pose(
            robot,
            logger=logger,
            read_error_message="read failed",
            timeout_message="timeout",
            timeout_s=0.2,
            sample_interval_s=0.05,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertIsNone(pose)
        logger.error.assert_called_once_with("timeout")


class TestOrderedPaintContactCommands(unittest.TestCase):
    def test_builder_returns_typed_position_and_path_commands(self):
        commands = build_ordered_paint_contact_segments(
            paint_paths=[[
                [1.0, 2.0, 3.0, 180.0, 0.0, 10.0],
                [2.0, 2.0, 3.0, 180.0, 0.0, 20.0],
            ]],
            paint_jobs=[{"pattern_type": "Contour", "vel": 12.0, "acc": 40.0}],
            contact_staging=SimpleNamespace(
                attach_vel_percent=20.0,
                attach_acc_percent=30.0,
            ),
            acceleration_scale=0.5,
        )

        self.assertEqual(2, len(commands))
        self.assertIsInstance(commands[0], OrderedPositionCommand)
        self.assertIsInstance(commands[1], OrderedPathCommand)
        self.assertEqual(20.0, commands[1].profile.acceleration_percent)


if __name__ == "__main__":
    unittest.main()
