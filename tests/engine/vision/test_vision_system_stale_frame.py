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
