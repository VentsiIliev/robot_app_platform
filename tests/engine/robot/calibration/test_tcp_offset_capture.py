import unittest
from dataclasses import replace
from unittest.mock import MagicMock

from src.engine.robot.calibration.robot_calibration.tcp_offset_capture import (
    CameraTcpOffsetSample,
    capture_tcp_offset_for_current_marker,
    finalize_tcp_offset_calibration,
    _solve_local_offset,
)


class TestFinalizeTcpOffsetCalibration(unittest.TestCase):

    def test_saves_mean_offset_when_sample_spread_is_acceptable(self):
        ctx = MagicMock()
        ctx.camera_tcp_offset_config = MagicMock(
            min_samples=2,
            max_acceptance_std_mm=5.0,
        )
        ctx.camera_tcp_offset_samples = [
            CameraTcpOffsetSample(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            CameraTcpOffsetSample(0, 1, 0.0, 15.0, 11.0, -19.5, 11.0, -19.5),
            CameraTcpOffsetSample(1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            CameraTcpOffsetSample(1, 1, 0.0, 15.0, 9.5, -20.5, 9.5, -20.5),
        ]
        ctx.robot_config = MagicMock()
        ctx.settings_service = MagicMock()
        ctx.robot_config_key = "robot_config"

        ok, message = finalize_tcp_offset_calibration(ctx)

        self.assertTrue(ok)
        self.assertIn("tcp_x_offset", message)
        self.assertAlmostEqual(ctx.robot_config.camera_to_tcp_x_offset, 10.25, places=3)
        self.assertAlmostEqual(ctx.robot_config.camera_to_tcp_y_offset, -20.0, places=3)
        ctx.settings_service.save.assert_called_once_with("robot_config", ctx.robot_config)

    def test_rejects_result_when_sample_spread_is_too_high(self):
        ctx = MagicMock()
        ctx.camera_tcp_offset_config = MagicMock(
            min_samples=2,
            max_acceptance_std_mm=5.0,
        )
        ctx.camera_tcp_offset_samples = [
            CameraTcpOffsetSample(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            CameraTcpOffsetSample(0, 1, 0.0, 15.0, 50.0, -80.0, 50.0, -80.0),
            CameraTcpOffsetSample(1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            CameraTcpOffsetSample(1, 1, 0.0, 15.0, -30.0, 25.0, -30.0, 25.0),
        ]
        ctx.robot_config = MagicMock()
        ctx.settings_service = MagicMock()
        ctx.robot_config_key = "robot_config"

        ok, message = finalize_tcp_offset_calibration(ctx)

        self.assertFalse(ok)
        self.assertIn("spread", message)
        ctx.settings_service.save.assert_not_called()

    def test_rejects_result_when_not_enough_samples_exist(self):
        ctx = MagicMock()
        ctx.camera_tcp_offset_config = MagicMock(
            min_samples=2,
            max_acceptance_std_mm=5.0,
        )
        ctx.camera_tcp_offset_samples = [
            CameraTcpOffsetSample(0, 0, 0.0, 0.0, 10.0, -20.0, 10.0, -20.0),
        ]
        ctx.robot_config = MagicMock()
        ctx.settings_service = MagicMock()
        ctx.robot_config_key = "robot_config"

        ok, message = finalize_tcp_offset_calibration(ctx)

        self.assertFalse(ok)
        self.assertIn("Not enough", message)
        ctx.settings_service.save.assert_not_called()

    def test_ignores_reference_samples_when_checking_sample_count(self):
        ctx = MagicMock()
        ctx.camera_tcp_offset_config = MagicMock(
            min_samples=2,
            max_acceptance_std_mm=5.0,
        )
        ctx.camera_tcp_offset_samples = [
            CameraTcpOffsetSample(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            CameraTcpOffsetSample(1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        ]
        ctx.robot_config = MagicMock()
        ctx.settings_service = MagicMock()
        ctx.robot_config_key = "robot_config"

        ok, message = finalize_tcp_offset_calibration(ctx)

        self.assertFalse(ok)
        self.assertIn("Not enough", message)
        ctx.settings_service.save.assert_not_called()


class TestCaptureTcpOffsetForCurrentMarker(unittest.TestCase):

    def test_solves_consistent_local_offset_from_multiple_rotation_angles(self):
        local_dx, local_dy = _solve_local_offset(
            21.049147,
            4.032374,
            reference_rz_deg=0.0,
            sample_rz_deg=15.0,
        )
        self.assertAlmostEqual(local_dx, -4.789887, places=3)
        self.assertAlmostEqual(local_dy, 81.958259, places=3)

        local_dx, local_dy = _solve_local_offset(
            40.940664,
            13.833188,
            reference_rz_deg=0.0,
            sample_rz_deg=30.0,
        )
        self.assertAlmostEqual(local_dx, -5.342748, places=3)
        self.assertAlmostEqual(local_dy, 83.312913, places=3)

    def test_iterations_count_rotated_samples_after_reference_pose(self):
        from unittest.mock import patch

        ctx = MagicMock()
        ctx.required_ids = {0}
        ctx.current_marker_id = 0
        ctx.stop_event.is_set.return_value = False
        ctx.camera_tcp_offset_config = MagicMock(
            run_during_robot_calibration=True,
            approach_rz=0.0,
            iterations=2,
            rotation_step_deg=15.0,
        )
        ctx.calibration_robot_controller.get_current_position.return_value = [1.0, 2.0, 3.0, 180.0, 0.0, 0.0]
        ctx.robot_positions_for_calibration = {}
        ctx.camera_tcp_offset_samples = []
        ctx.camera_tcp_offset_captured_markers = set()

        reference_pose = [10.0, 20.0, 300.0, 180.0, 0.0, 0.0]
        sample_pose_1 = [31.0, 18.5, 300.0, 180.0, 0.0, 15.0]
        sample_pose_2 = [32.0, 19.0, 300.0, 180.0, 0.0, 30.0]

        with patch(
            "src.engine.robot.calibration.robot_calibration.tcp_offset_capture._move_and_realign_marker",
            side_effect=[reference_pose, sample_pose_1, sample_pose_2],
        ) as move_and_realign_mock, patch(
            "src.engine.robot.calibration.robot_calibration.tcp_offset_capture._move_to_pose",
            return_value=reference_pose,
        ):
            ok = capture_tcp_offset_for_current_marker(ctx)

        self.assertTrue(ok)
        self.assertEqual(move_and_realign_mock.call_count, 3)
        self.assertEqual(move_and_realign_mock.call_args_list[0].args[2], 0.0)
        self.assertEqual(move_and_realign_mock.call_args_list[1].args[2], 15.0)
        self.assertEqual(move_and_realign_mock.call_args_list[2].args[2], 30.0)
        self.assertEqual(len(ctx.camera_tcp_offset_samples), 2)
        self.assertEqual(ctx.camera_tcp_offset_samples[0].sample_rz, 15.0)
        self.assertEqual(ctx.camera_tcp_offset_samples[1].sample_rz, 30.0)
        self.assertEqual(ctx.camera_tcp_offset_samples[0].sample_index, 0)
        self.assertEqual(ctx.camera_tcp_offset_samples[1].sample_index, 1)

    def test_restores_reference_pose_when_sampling_fails_after_reference_alignment(self):
        from unittest.mock import patch

        ctx = MagicMock()
        ctx.required_ids = {0}
        ctx.current_marker_id = 0
        ctx.stop_event.is_set.return_value = False
        ctx.camera_tcp_offset_config = MagicMock(
            run_during_robot_calibration=True,
            approach_rz=0.0,
            iterations=2,
            rotation_step_deg=15.0,
        )
        ctx.calibration_robot_controller.get_current_position.return_value = [1.0, 2.0, 3.0, 180.0, 0.0, 0.0]
        ctx.robot_positions_for_calibration = {}
        ctx.camera_tcp_offset_samples = []
        ctx.camera_tcp_offset_captured_markers = set()

        reference_pose = [10.0, 20.0, 300.0, 180.0, 0.0, 0.0]
        sample_pose = None

        with patch(
            "src.engine.robot.calibration.robot_calibration.tcp_offset_capture._move_and_realign_marker",
            side_effect=[reference_pose, reference_pose, None],
        ), patch(
            "src.engine.robot.calibration.robot_calibration.tcp_offset_capture._move_to_pose",
            return_value=reference_pose,
        ) as restore_mock:
            ok = capture_tcp_offset_for_current_marker(ctx)

        self.assertFalse(ok)
        restore_mock.assert_called_with(ctx, reference_pose, "restore tcp-offset reference pose after failure")
        self.assertEqual(ctx.robot_positions_for_calibration[0], reference_pose)


if __name__ == "__main__":
    unittest.main()
