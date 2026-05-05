import unittest
from unittest.mock import MagicMock

from src.engine.robot.calibration.robot_calibration.robot_controller import (
    CalibrationRobotController,
)


class _AdaptiveConfig:
    min_step_mm = 0.1
    max_step_mm = 25.0
    max_error_ref = 30.0
    k = 2.0
    derivative_scaling = 0.5
    iterative_gain = 0.7
    near_target_gain = 0.35
    axis_deadband_mm = 0.2
    axis_flip_scale_min = 0.2


class TestCalibrationRobotController(unittest.TestCase):

    def _make_controller(self) -> CalibrationRobotController:
        robot_service = MagicMock()
        robot_service.get_current_position.return_value = [100.0, 200.0, 300.0, 1.0, 2.0, 3.0]
        controller = CalibrationRobotController(
            robot_service=robot_service,
            navigation_service=None,
            tool=1,
            user=2,
            adaptive_movement_config=_AdaptiveConfig(),
        )
        controller._calibration_position = [100.0, 200.0, 300.0, 10.0, 20.0, 30.0]
        return controller

    def test_damps_axis_when_offset_sign_flips_near_target(self):
        controller = self._make_controller()

        first = controller.get_iterative_align_position(
            current_error_mm=1.0,
            offset_x_mm=1.0,
            offset_y_mm=0.0,
            alignment_threshold_mm=0.25,
        )
        second = controller.get_iterative_align_position(
            current_error_mm=0.8,
            offset_x_mm=-0.5,
            offset_y_mm=0.0,
            alignment_threshold_mm=0.25,
        )

        self.assertEqual(first[:2], [100.7, 200.0])
        self.assertEqual(second[:2], [99.8425, 200.0])

    def test_reset_derivative_state_clears_axis_history(self):
        controller = self._make_controller()
        controller.get_iterative_align_position(
            current_error_mm=1.0,
            offset_x_mm=1.0,
            offset_y_mm=-1.0,
            alignment_threshold_mm=0.25,
        )

        controller.reset_derivative_state()

        self.assertFalse(hasattr(controller, "previous_error_mm"))
        self.assertFalse(hasattr(controller, "previous_offset_x_mm"))
        self.assertFalse(hasattr(controller, "previous_offset_y_mm"))

    def test_zeroes_axis_inside_deadband(self):
        controller = self._make_controller()

        pose = controller.get_iterative_align_position(
            current_error_mm=0.3,
            offset_x_mm=0.1,
            offset_y_mm=0.5,
            alignment_threshold_mm=0.25,
        )

        self.assertEqual(pose[0], 100.0)
        self.assertLess(pose[1], 200.2)
