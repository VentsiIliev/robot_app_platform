import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.applications.intrinsic_calibration_capture.service.intrinsic_capture_service import (
    IntrinsicCaptureService,
)
from src.engine.vision.i_vision_service import VisionFrameSnapshot
from src.shared_contracts.events.vision_events import VisionTopics


class _FreshVision:
    def __init__(self, snapshots):
        self._snapshots = iter(snapshots)
        self.calls = []

    def get_fresh_frame(self, *, after_sequence, timeout_s, raw=False):
        self.calls.append((after_sequence, timeout_s, raw))
        return next(self._snapshots)


class TestIntrinsicCaptureFreshFrames(unittest.TestCase):

    def test_capture_requires_distinct_raw_frame_sequences(self):
        frame_1 = object()
        frame_2 = object()
        vision = _FreshVision([
            VisionFrameSnapshot(frame_1, 1.0, 5),
            VisionFrameSnapshot(frame_2, 2.0, 6),
        ])
        service = IntrinsicCaptureService(
            robot_service=MagicMock(),
            vision_service=vision,
            robot_config=MagicMock(),
        )

        self.assertIs(service._get_capture_frame(), frame_1)
        self.assertIs(service._get_capture_frame(), frame_2)
        self.assertEqual(vision.calls, [(0, 2.0, True), (5, 2.0, True)])

    def test_capture_timeout_aborts_and_stops_robot(self):
        robot = MagicMock()
        service = IntrinsicCaptureService(
            robot_service=robot,
            vision_service=_FreshVision([None]),
            robot_config=MagicMock(),
        )

        with self.assertRaisesRegex(RuntimeError, "Camera frame timeout"):
            service._get_capture_frame()

        self.assertTrue(service._stop_event.is_set())
        robot.stop_motion.assert_called_once_with()

    def test_vision_error_during_capture_stops_robot(self):
        robot = MagicMock()
        messaging = MagicMock()
        service = IntrinsicCaptureService(
            robot_service=robot,
            vision_service=_FreshVision([]),
            robot_config=MagicMock(),
            messaging=messaging,
        )
        service._thread = SimpleNamespace(is_alive=lambda: True)
        service._subscribe_to_vision_state()

        service._on_vision_state({"state": "ERROR"})

        self.assertTrue(service._stop_event.is_set())
        robot.stop_motion.assert_called_once_with()
        messaging.unsubscribe.assert_called_once_with(
            VisionTopics.SERVICE_STATE,
            service._on_vision_state,
        )


if __name__ == "__main__":
    unittest.main()
