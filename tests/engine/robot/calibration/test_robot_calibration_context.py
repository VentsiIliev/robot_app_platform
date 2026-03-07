"""
Tests for src/engine/robot/calibration/robot_calibration/RobotCalibrationContext.py

Covers stop_event lifecycle, reset behaviour, and flush_camera_buffer.
"""
import threading
import unittest
from unittest.mock import MagicMock

from src.engine.robot.calibration.robot_calibration.RobotCalibrationContext import RobotCalibrationContext


class TestRobotCalibrationContextStopEvent(unittest.TestCase):

    def test_stop_event_initially_clear(self):
        ctx = RobotCalibrationContext()
        self.assertFalse(ctx.stop_event.is_set())

    def test_stop_event_is_threading_event(self):
        ctx = RobotCalibrationContext()
        self.assertIsInstance(ctx.stop_event, threading.Event)

    def test_reset_creates_fresh_stop_event(self):
        ctx = RobotCalibrationContext()
        first = ctx.stop_event
        first.set()
        ctx.reset()
        self.assertIsNot(ctx.stop_event, first)

    def test_reset_clears_stop_event(self):
        ctx = RobotCalibrationContext()
        ctx.stop_event.set()
        ctx.reset()
        self.assertFalse(ctx.stop_event.is_set())


class TestRobotCalibrationContextFlushCamera(unittest.TestCase):

    def test_flush_camera_buffer_calls_get_frame_min_flush_times(self):
        ctx = RobotCalibrationContext()
        ctx.vision_service = MagicMock()
        ctx.min_camera_flush = 5
        ctx.flush_camera_buffer()
        self.assertEqual(ctx.vision_service.get_latest_frame.call_count, 5)

    def test_flush_camera_buffer_with_no_vision_service_does_not_raise(self):
        ctx = RobotCalibrationContext()
        ctx.vision_service = None
        ctx.flush_camera_buffer()   # must not raise

    def test_flush_uses_min_camera_flush_value(self):
        ctx = RobotCalibrationContext()
        ctx.vision_service = MagicMock()
        ctx.min_camera_flush = 3
        ctx.flush_camera_buffer()
        self.assertEqual(ctx.vision_service.get_latest_frame.call_count, 3)


class TestRobotCalibrationContextReset(unittest.TestCase):

    def test_reset_clears_robot_positions(self):
        ctx = RobotCalibrationContext()
        ctx.robot_positions_for_calibration = {1: [0, 0, 0, 0, 0, 0]}
        ctx.reset()
        self.assertEqual(ctx.robot_positions_for_calibration, {})

    def test_reset_clears_iteration_count(self):
        ctx = RobotCalibrationContext()
        ctx.iteration_count = 42
        ctx.reset()
        self.assertEqual(ctx.iteration_count, 0)

    def test_reset_clears_error_message(self):
        ctx = RobotCalibrationContext()
        ctx.calibration_error_message = "something broke"
        ctx.reset()
        self.assertIsNone(ctx.calibration_error_message)


if __name__ == "__main__":
    unittest.main()
