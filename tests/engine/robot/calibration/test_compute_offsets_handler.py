import unittest
from unittest.mock import MagicMock

from src.engine.robot.calibration.robot_calibration.RobotCalibrationContext import (
    RobotCalibrationContext,
)
from src.engine.robot.calibration.robot_calibration.states.compute_offsets_handler import (
    handle_compute_offsets_state,
)
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates,
)


class TestComputeOffsetsHandler(unittest.TestCase):

    def test_offsets_are_scaled_for_target_height(self):
        ctx = RobotCalibrationContext()
        ctx.calibration_vision = MagicMock()
        ctx.calibration_vision.PPM = 2.0
        ctx.calibration_vision.marker_top_left_corners = {
            0: (300.0, 200.0),
        }
        ctx.calibration_vision.marker_top_left_corners_mm = {
            0: (-50.0, -50.0),
        }
        ctx.bottom_left_chessboard_corner_px = MagicMock()
        ctx.bottom_left_chessboard_corner_px.__getitem__.side_effect = [0.0, 0.0]
        ctx.vision_service = MagicMock()
        ctx.vision_service.get_camera_width.return_value = 800
        ctx.vision_service.get_camera_height.return_value = 600
        ctx.ppm_scale = 2.0

        result = handle_compute_offsets_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.ALIGN_ROBOT)
        self.assertEqual(ctx.markers_offsets_mm[0], (-25.0, -25.0))
