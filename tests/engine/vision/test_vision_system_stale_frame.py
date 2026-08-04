import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.engine.vision.i_vision_service import VisionFrameUnavailableError
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem


class TestVisionSystemStaleFrame(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
