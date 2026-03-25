import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.engine.robot.calibration.camera_tcp_offset_calibration_service import (
    CameraTcpOffsetCalibrationService,
)
from src.engine.robot.configuration import RobotCalibrationSettings, RobotSettings


class _FakeVisionService:
    def __init__(self, matrix_path: str, detections: list[tuple[float, float]]):
        self.camera_to_robot_matrix_path = matrix_path
        self._detections = list(detections)

    def get_latest_frame(self):
        return object()

    def detect_aruco_markers(self, image):
        if not self._detections:
            return [], None, image
        x, y = self._detections.pop(0)
        corners = [
            np.array(
                [[[x - 1.0, y - 1.0], [x + 1.0, y - 1.0], [x + 1.0, y + 1.0], [x - 1.0, y + 1.0]]],
                dtype=np.float32,
            )
        ]
        ids = np.array([[4]], dtype=np.int32)
        return corners, ids, image

    def get_camera_width(self) -> int:
        return 640

    def get_camera_height(self) -> int:
        return 480


class _FakeRobotService:
    def __init__(self):
        self.current_position = [0.0, 0.0, 0.0, 180.0, 0.0, 0.0]
        self.moves = []

    def get_current_position(self) -> list:
        return list(self.current_position)

    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool:
        self.current_position = list(position)
        self.moves.append((list(position), tool, user, velocity, acceleration, wait_to_reach))
        return True

    def stop_motion(self) -> bool:
        return True


class _FakeNavigationService:
    def __init__(self):
        self.called = 0

    def move_to_calibration_position(self, wait_cancelled=None) -> bool:
        self.called += 1
        return True


class _FakeSettingsService:
    def __init__(self):
        self.saved = []

    def save(self, name, settings) -> None:
        self.saved.append((name, settings))


class TestCameraTcpOffsetCalibrationService(unittest.TestCase):

    def test_calibrate_solves_and_saves_rotating_local_offset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            matrix_path = str(Path(tmp_dir) / "cameraToRobotMatrix_camera_center.npy")
            np.save(matrix_path, np.eye(3, dtype=np.float32))

            expected_local_x = 12.0
            expected_local_y = -5.0

            def world_shift(sample_deg: float) -> tuple[float, float]:
                theta = np.deg2rad(sample_deg)
                cos_theta = float(np.cos(theta))
                sin_theta = float(np.sin(theta))
                return (
                    (1.0 - cos_theta) * expected_local_x + sin_theta * expected_local_y,
                    -sin_theta * expected_local_x + (1.0 - cos_theta) * expected_local_y,
                )

            target_x = 100.0
            target_y = 200.0
            sample_1_dx, sample_1_dy = world_shift(15.0)
            sample_2_dx, sample_2_dy = world_shift(30.0)
            sample_3_dx, sample_3_dy = world_shift(45.0)
            detections = [
                (target_x, target_y),  # initial target acquisition
                (target_x + sample_1_dx, target_y + sample_1_dy),
                (target_x + sample_2_dx, target_y + sample_2_dy),
                (target_x + sample_3_dx, target_y + sample_3_dy),
            ]
            vision = _FakeVisionService(matrix_path=matrix_path, detections=detections)
            robot = _FakeRobotService()
            navigation = _FakeNavigationService()
            settings = _FakeSettingsService()
            robot_config = RobotSettings()
            calibration_settings = RobotCalibrationSettings()
            cfg = calibration_settings.camera_tcp_offset
            cfg.marker_id = 4
            cfg.iterations = 3
            cfg.rotation_step_deg = 15.0
            cfg.approach_z = 300.0
            cfg.approach_rx = 180.0
            cfg.approach_ry = 0.0
            cfg.approach_rz = 0.0
            cfg.velocity = 20
            cfg.acceleration = 10
            cfg.settle_time_s = 0.0
            cfg.detection_attempts = 1
            cfg.retry_delay_s = 0.0

            service = CameraTcpOffsetCalibrationService(
                vision_service=vision,
                robot_service=robot,
                navigation_service=navigation,
                settings_service=settings,
                robot_config_key="robot_config",
                robot_config=robot_config,
                calibration_settings=calibration_settings,
                robot_tool=0,
                robot_user=0,
            )

            ok, msg = service.calibrate()

            self.assertTrue(ok)
            self.assertIn("Camera-to-TCP offset calibrated", msg)
            self.assertAlmostEqual(robot_config.camera_to_tcp_x_offset, expected_local_x, places=3)
            self.assertAlmostEqual(robot_config.camera_to_tcp_y_offset, expected_local_y, places=3)
            self.assertEqual(navigation.called, 1)
            self.assertEqual(len(settings.saved), 1)
            saved_key, saved_config = settings.saved[0]
            self.assertEqual(saved_key, "robot_config")
            self.assertIs(saved_config, robot_config)


if __name__ == "__main__":
    unittest.main()
