import unittest
from unittest.mock import MagicMock

import cv2
import numpy as np

from src.engine.robot.calibration.robot_calibration.CalibrationVision import (
    CalibrationVision,
)


class TestCalibrationVision(unittest.TestCase):

    def _make_vision(self) -> CalibrationVision:
        service = MagicMock()
        return CalibrationVision(
            vision_service=service,
            chessboard_size=(32, 20),
            square_size_mm=25.0,
            required_ids={0, 1, 2},
            debug=False,
            charuco_board_size=(19, 12),
        )

    def test_uses_4x4_250_as_calibration_fallback_dictionary(self):
        vision = self._make_vision()
        self.assertEqual(vision._get_charuco_dictionary_id(), cv2.aruco.DICT_4X4_1000)

    def test_detect_specific_marker_returns_detected_marker(self):
        vision = self._make_vision()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        vision.vision_service.detect_aruco_markers.return_value = (
            [np.array([[[10.0, 10.0], [20.0, 10.0], [20.0, 20.0], [10.0, 20.0]]], dtype=np.float32)],
            np.array([[0]], dtype=np.int32),
            None,
        )

        result = vision.detect_specific_marker(frame, 0)

        self.assertTrue(result.found)
        self.assertEqual(result.aruco_ids.flatten().tolist(), [0])
