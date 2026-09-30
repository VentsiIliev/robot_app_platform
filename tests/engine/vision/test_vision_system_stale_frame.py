import unittest
import time
from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from src.engine.vision.i_vision_service import VisionFrameUnavailableError
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
from src.engine.vision.implementation.VisionSystem.core.camera.frame_grabber import (
    FrameGrabber,
    FrameSnapshot,
)


class TestVisionSystemStaleFrame(unittest.TestCase):
    def test_rotated_frame_dimensions_are_used_for_new_work_areas_and_rois(self):
        vision = VisionSystem.__new__(VisionSystem)
        vision.camera_settings = MagicMock()
        vision.camera_settings.get_camera_width.return_value = 1280
        vision.camera_settings.get_camera_height.return_value = 720
        vision.frame_grabber = MagicMock()
        vision.frame_grabber.is_transposed.return_value = True
        vision._work_area_service = MagicMock()
        vision._work_area_service.get_work_area.return_value = [(0.5, 0.5)]
        vision._work_area_service.get_active_area_id.return_value = "paint"

        vision.saveWorkAreaPoints({"area_type": "paint", "corners": [(360, 640)]})
        vision._work_area_service.save_work_area.assert_called_once_with(
            "paint", [(0.5, 0.5)]
        )
        _, _, points = vision.getWorkAreaPoints("paint")
        self.assertEqual(points, [(360.0, 640.0)])
        vision._get_area_points_by_region("paint")
        vision._work_area_service.get_detection_roi_pixels.assert_called_once_with(
            "paint", 720, 1280
        )
        vision._get_active_brightness_area_points()
        vision._work_area_service.get_brightness_roi_pixels.assert_called_once_with(
            "paint", 720, 1280
        )

    def test_frame_grabber_applies_updated_horizontal_flip_to_next_frame(self):
        frame = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        camera = MagicMock()

        def capture(*, timeout):
            time.sleep(0.01)
            return frame.copy()

        camera.capture.side_effect = capture
        grabber = FrameGrabber(camera)
        grabber.start()
        try:
            original = grabber.get_latest_snapshot_since(0, timeout_s=1.0)
            self.assertIsNotNone(original)
            np.testing.assert_array_equal(original.frame, frame)

            grabber.set_orientation(True, False)
            flipped = grabber.get_latest_snapshot_since(original.sequence, timeout_s=1.0)
            self.assertIsNotNone(flipped)
            np.testing.assert_array_equal(flipped.frame, np.array([[2, 1], [4, 3]], dtype=np.uint8))
        finally:
            grabber.stop()

    def test_frame_grabber_applies_updated_rotation_to_next_frame(self):
        frame = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        camera = MagicMock()

        def capture(*, timeout):
            time.sleep(0.01)
            return frame.copy()

        camera.capture.side_effect = capture
        grabber = FrameGrabber(camera)
        grabber.start()
        try:
            original = grabber.get_latest_snapshot_since(0, timeout_s=1.0)
            self.assertIsNotNone(original)

            grabber.set_orientation(False, False, 90)
            rotated = grabber.get_latest_snapshot_since(original.sequence, timeout_s=1.0)
            self.assertIsNotNone(rotated)
            np.testing.assert_array_equal(rotated.frame, np.array([[3, 1], [4, 2]], dtype=np.uint8))
        finally:
            grabber.stop()

    def test_frame_grabber_reports_transposition_for_quarter_turns(self):
        grabber = FrameGrabber(MagicMock())
        try:
            self.assertFalse(grabber.is_transposed())
            grabber.set_orientation(False, False, 180)
            self.assertFalse(grabber.is_transposed())
            grabber.set_orientation(False, False, 90)
            self.assertTrue(grabber.is_transposed())
            self.assertEqual(grabber.get_orientation(), (False, False, 90))
        finally:
            grabber.running = False

    def test_frame_grabber_rejects_unsupported_rotation(self):
        grabber = FrameGrabber(MagicMock())
        try:
            with self.assertRaisesRegex(ValueError, "rotation must be one of"):
                grabber.set_orientation(False, False, 45)
        finally:
            grabber.running = False

    def test_frame_grabber_pause_clears_frames_and_resume_keeps_camera_open(self):
        camera = MagicMock()
        grabber = FrameGrabber(camera)
        grabber.buffer = deque(
            [FrameSnapshot(frame="old", timestamp_s=time.time(), sequence=1)],
            maxlen=5,
        )
        grabber._last_frame_at = time.time()

        grabber.pause()

        self.assertFalse(grabber._resume_event.is_set())
        self.assertEqual(list(grabber.buffer), [])
        camera.stop_stream.assert_not_called()

        grabber.resume()

        self.assertTrue(grabber._resume_event.is_set())
        camera.start_stream.assert_not_called()

    def test_compute_contours_for_latest_frame_blocks_when_no_fresh_snapshot(self):
        vision = SimpleNamespace(
            frame_grabber=MagicMock(),
            _latest_contours=["cached-contour"],
            rawImage="cached-frame",
            correctedImage=None,
        )
        vision.frame_grabber.get_latest_snapshot.return_value = None

        with self.assertRaisesRegex(VisionFrameUnavailableError, "No fresh camera frame"):
            VisionSystem.compute_contours_for_latest_frame(vision)

    def test_compute_contours_recomputes_when_active_area_changes_on_same_frame_sequence(self):
        vision = VisionSystem.__new__(VisionSystem)
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        corrected = np.ones((8, 8, 3), dtype=np.uint8)

        vision.frame_grabber = MagicMock()
        vision.frame_grabber.get_latest_snapshot.return_value = SimpleNamespace(frame=frame, sequence=5)
        vision.camera_settings = MagicMock()
        vision.camera_settings.get_contour_detection.return_value = True
        vision.camera_settings.get_brightness_auto.return_value = False
        vision.camera_settings.get_threshold.return_value = 100
        vision.camera_settings.get_threshold_pickup_area.return_value = 100
        vision.camera_settings.get_camera_width.return_value = 8
        vision.camera_settings.get_camera_height.return_value = 8
        vision._work_area_service = MagicMock()
        vision._work_area_service.get_active_area_id.return_value = "paint"
        vision._work_area_service.get_area_definition.return_value = None
        vision._work_area_service.get_detection_roi_pixels.return_value = None
        vision._active_area_id = "paint"
        vision._latest_contours = ["magazine-contour"]
        vision._latest_contour_frame_sequence = 5
        vision._latest_contour_area_id = "magazine"
        vision._contour_service = MagicMock()
        vision._contour_service.detect.return_value = (["paint-contour"], corrected, None)
        vision._brightness_service = MagicMock()
        vision.cameraMatrix = None
        vision.correctImage = MagicMock()
        vision.rawImage = None
        vision.correctedImage = None

        returned_frame, contours = VisionSystem.compute_contours_for_latest_frame(vision)

        self.assertIs(returned_frame, corrected)
        self.assertEqual(contours, ["paint-contour"])
        self.assertEqual(vision._latest_contour_area_id, "paint")
        vision._contour_service.detect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
