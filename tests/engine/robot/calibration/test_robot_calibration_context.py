"""
Tests for src/engine/robot/calibration/robot_calibration/RobotCalibrationContext.y_pixels

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

    def test_legacy_properties_proxy_to_grouped_views(self):
        ctx = RobotCalibrationContext()
        ctx.current_marker_id = 3
        ctx.iteration_count = 7
        ctx.target_marker_ids = [11, 22]
        ctx.failed_target_ids.add(22)
        ctx.camera_points_for_homography = {11: (100.0, 200.0)}

        self.assertEqual(ctx.progress.current_marker_id, 3)
        self.assertEqual(ctx.progress.iteration_count, 7)
        self.assertEqual(ctx.target_plan.target_marker_ids, [11, 22])
        self.assertEqual(ctx.artifacts.failed_target_ids, {22})
        self.assertEqual(ctx.artifacts.camera_points_for_homography, {11: (100.0, 200.0)})

    def test_grouped_views_are_initialized_with_mutable_containers(self):
        ctx = RobotCalibrationContext()

        ctx.failed_target_ids.add(1)
        ctx.skipped_target_ids.add(2)
        ctx.camera_tcp_offset_captured_markers.add(3)
        ctx.camera_tcp_offset_samples.append("sample")

        self.assertEqual(ctx.artifacts.failed_target_ids, {1})
        self.assertEqual(ctx.artifacts.skipped_target_ids, {2})
        self.assertEqual(ctx.artifacts.camera_tcp_offset_captured_markers, {3})
        self.assertEqual(ctx.artifacts.camera_tcp_offset_samples, ["sample"])


if __name__ == "__main__":
    unittest.main()
