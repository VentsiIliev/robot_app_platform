import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.engine.robot.calibration.robot_calibration.config_helpers import RobotCalibrationConfig
from src.engine.robot.calibration.robot_calibration_service import RobotCalibrationService


class TestRobotCalibrationService(unittest.TestCase):

    def test_run_calibration_refreshes_live_settings_before_building_pipeline(self):
        settings_service = MagicMock()
        live_calibration = SimpleNamespace(
            required_ids=[4, 8],
            z_target=412,
            velocity=17,
            acceleration=9,
            run_height_measurement=False,
            camera_tcp_offset=SimpleNamespace(iterations=2),
            axis_mapping=SimpleNamespace(marker_id=8),
            adaptive_movement=SimpleNamespace(min_step_mm=0.5),
        )
        live_robot_config = SimpleNamespace(robot_tool=3, robot_user=7)
        settings_service.get.side_effect = lambda key: {
            "robot_calibration": live_calibration,
            "robot_config": live_robot_config,
        }[key]

        config = RobotCalibrationConfig(
            vision_service=MagicMock(),
            robot_service=MagicMock(),
            navigation_service=MagicMock(),
            height_measuring_service=MagicMock(),
            required_ids=[0, 1, 2],
            z_target=300,
            robot_tool=0,
            robot_user=0,
            velocity=30,
            acceleration=10,
            run_height_measurement=True,
            settings_service=settings_service,
            calibration_settings_key="robot_calibration",
            robot_config=SimpleNamespace(robot_tool=0, robot_user=0),
            robot_config_key="robot_config",
            camera_tcp_offset_config=SimpleNamespace(iterations=6),
            axis_mapping_config=SimpleNamespace(marker_id=4),
        )

        captured = {}

        class _FakePipeline:
            def __init__(self, cfg, adaptive_cfg, events_cfg):
                captured["config"] = cfg
                captured["adaptive"] = adaptive_cfg
                captured["events"] = events_cfg

            def run(self):
                return True, "ok"

        with patch(
            "src.engine.robot.calibration.robot_calibration_service.RefactoredRobotCalibrationPipeline",
            _FakePipeline,
        ):
            service = RobotCalibrationService(
                config=config,
                adaptive_config=SimpleNamespace(min_step_mm=0.1),
                events_config=None,
            )
            success, message = service.run_calibration()

        self.assertTrue(success)
        self.assertEqual(message, "ok")
        self.assertEqual(captured["config"].required_ids, [4, 8])
        self.assertEqual(captured["config"].z_target, 412)
        self.assertEqual(captured["config"].velocity, 17)
        self.assertEqual(captured["config"].acceleration, 9)
        self.assertFalse(captured["config"].run_height_measurement)
        self.assertEqual(captured["config"].camera_tcp_offset_config.iterations, 2)
        self.assertEqual(captured["config"].axis_mapping_config.marker_id, 8)
        self.assertEqual(captured["config"].robot_tool, 3)
        self.assertEqual(captured["config"].robot_user, 7)
        self.assertIs(captured["adaptive"], live_calibration.adaptive_movement)

    def test_run_calibration_refreshes_live_vision_board_settings_before_building_pipeline(self):
        settings_service = MagicMock()
        live_calibration = SimpleNamespace(
            required_ids=[4, 8],
            candidate_ids=[],
            min_target_separation_px=120.0,
            homography_target_count=16,
            residual_target_count=14,
            validation_target_count=6,
            test_target_count=10,
            auto_skip_known_unreachable_markers=True,
            unreachable_marker_failure_threshold=1,
            known_unreachable_marker_ids=[],
            unreachable_marker_failure_counts={},
            z_target=412,
            velocity=17,
            acceleration=9,
            travel_velocity=22,
            travel_acceleration=11,
            iterative_velocity=15,
            iterative_acceleration=8,
            run_height_measurement=False,
            camera_tcp_offset=SimpleNamespace(iterations=2),
            axis_mapping=SimpleNamespace(marker_id=8),
            adaptive_movement=SimpleNamespace(min_step_mm=0.5),
        )
        live_robot_config = SimpleNamespace(robot_tool=3, robot_user=7)
        live_vision_calibration = SimpleNamespace(
            reference_board_mode="charuco",
            charuco_board_width=33,
            charuco_board_height=21,
            charuco_square_size_mm=25.0,
            charuco_marker_size_mm=18.0,
        )
        settings_service.get.side_effect = lambda key: {
            "robot_calibration": live_calibration,
            "robot_config": live_robot_config,
            "calibration_vision_settings": live_vision_calibration,
        }[key]

        config = RobotCalibrationConfig(
            vision_service=MagicMock(),
            robot_service=MagicMock(),
            navigation_service=MagicMock(),
            height_measuring_service=MagicMock(),
            required_ids=[0, 1, 2],
            z_target=300,
            robot_tool=0,
            robot_user=0,
            velocity=30,
            acceleration=10,
            run_height_measurement=True,
            settings_service=settings_service,
            calibration_settings_key="robot_calibration",
            robot_config=SimpleNamespace(robot_tool=0, robot_user=0),
            robot_config_key="robot_config",
            camera_tcp_offset_config=SimpleNamespace(iterations=6),
            axis_mapping_config=SimpleNamespace(marker_id=4),
            reference_board_mode="auto",
            charuco_board_width=27,
            charuco_board_height=18,
            charuco_square_size_mm=15.0,
            charuco_marker_size_mm=11.0,
        )
        config.vision_calibration_settings_key = "calibration_vision_settings"

        captured = {}

        class _FakePipeline:
            def __init__(self, cfg, adaptive_cfg, events_cfg):
                captured["config"] = cfg

            def run(self):
                return True, "ok"

        with patch(
            "src.engine.robot.calibration.robot_calibration_service.RefactoredRobotCalibrationPipeline",
            _FakePipeline,
        ):
            service = RobotCalibrationService(
                config=config,
                adaptive_config=SimpleNamespace(min_step_mm=0.1),
                events_config=None,
            )
            success, message = service.run_calibration()

        self.assertTrue(success)
        self.assertEqual(message, "ok")
        self.assertEqual(captured["config"].reference_board_mode, "charuco")
        self.assertEqual(captured["config"].charuco_board_width, 33)
        self.assertEqual(captured["config"].charuco_board_height, 21)
        self.assertEqual(captured["config"].charuco_square_size_mm, 25.0)
        self.assertEqual(captured["config"].charuco_marker_size_mm, 18.0)


if __name__ == "__main__":
    unittest.main()
