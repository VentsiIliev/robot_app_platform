import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.vision.camera_stream_publisher import CameraStreamPublisher
from src.engine.vision.implementation.VisionSystem.core.external_communication.system_state_management import (
    MessagePublisher,
)
from src.shared_contracts.events.vision_events import CameraTopics


class CameraStreamPublisherTests(unittest.TestCase):
    @patch("src.engine.vision.camera_stream_publisher.cv2.VideoCapture")
    def test_stop_cancels_retry_wait(self, video_capture) -> None:
        missing = MagicMock()
        missing.isOpened.return_value = False
        video_capture.return_value = missing
        publisher = CameraStreamPublisher("auxiliary", "/dev/video2", MagicMock())
        publisher._RECONNECT_DELAY_S = 1.0

        publisher.start()
        deadline = time.monotonic() + 1.0
        while video_capture.call_count == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        publisher.stop()
        calls_after_stop = video_capture.call_count
        time.sleep(0.05)

        self.assertEqual(calls_after_stop, 1)
        self.assertEqual(video_capture.call_count, calls_after_stop)
        self.assertFalse(publisher._thread is not None and publisher._thread.is_alive())

    @patch("src.engine.vision.camera_stream_publisher.cv2.VideoCapture")
    def test_retries_initially_missing_camera_until_it_appears(self, video_capture) -> None:
        missing = MagicMock()
        missing.isOpened.return_value = False
        recovered = MagicMock()
        recovered.isOpened.return_value = True
        recovered.read.return_value = (True, "reconnected-frame")
        video_capture.side_effect = [missing, recovered]
        received = threading.Event()
        messaging = MagicMock()
        messaging.publish.side_effect = self._signal_on_publish(received)
        publisher = CameraStreamPublisher("auxiliary", "/dev/video2", messaging)
        publisher._RECONNECT_DELAY_S = 0.01

        publisher.start()
        try:
            self.assertTrue(received.wait(timeout=1.0))
        finally:
            publisher.stop()

        self.assertEqual(video_capture.call_count, 2)
        missing.release.assert_called_once_with()
        messaging.publish.assert_any_call(
            CameraTopics.frame("auxiliary"),
            {"image": "reconnected-frame", "camera": "auxiliary"},
        )

    @patch("src.engine.vision.camera_stream_publisher.cv2.VideoCapture")
    def test_reopens_after_lost_frames(self, video_capture) -> None:
        first = MagicMock()
        first.isOpened.return_value = True
        first.read.side_effect = [
            (True, "before-unplug"),
            (False, None),
            (False, None),
            (False, None),
        ]
        second = MagicMock()
        second.isOpened.return_value = True
        second.read.return_value = (True, "after-replug")
        video_capture.side_effect = [first, second]
        received = threading.Event()
        messaging = MagicMock()

        def record_frame(_topic, message):
            if message["image"] == "after-replug":
                received.set()

        messaging.publish.side_effect = record_frame
        publisher = CameraStreamPublisher("auxiliary", "/dev/video2", messaging)
        publisher._RECONNECT_DELAY_S = 0.01

        publisher.start()
        try:
            self.assertTrue(received.wait(timeout=2.0))
        finally:
            publisher.stop()

        self.assertEqual(video_capture.call_count, 2)
        first.release.assert_called_once_with()
        messaging.publish.assert_any_call(
            CameraTopics.frame("auxiliary"),
            {"image": "after-replug", "camera": "auxiliary"},
        )

    @staticmethod
    def _signal_on_publish(event):
        def record_frame(_topic, _message):
            event.set()

        return record_frame

    @patch("src.engine.vision.camera_stream_publisher.cv2.VideoCapture")
    def test_live_flip_update_changes_published_auxiliary_frames(self, video_capture) -> None:
        frame = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.read.side_effect = lambda: (True, frame.copy())
        video_capture.return_value = capture
        published = []
        first_frame = threading.Event()
        second_frame = threading.Event()
        messaging = MagicMock()

        def record_frame(_topic, message):
            published.append(message["image"].copy())
            (first_frame if len(published) == 1 else second_frame).set()

        messaging.publish.side_effect = record_frame
        publisher = CameraStreamPublisher("auxiliary", "/dev/video2", messaging)

        publisher.start()
        try:
            self.assertTrue(first_frame.wait(timeout=1.0))
            publisher.set_orientation(False, True)
            self.assertTrue(second_frame.wait(timeout=1.0))
        finally:
            publisher.stop()

        np.testing.assert_array_equal(published[0], frame)
        np.testing.assert_array_equal(published[1], np.array([[3, 4], [1, 2]], dtype=np.uint8))

    @patch("src.engine.vision.camera_stream_publisher.cv2.VideoCapture")
    def test_live_rotation_update_changes_published_auxiliary_frames(self, video_capture) -> None:
        frame = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.read.side_effect = lambda: (True, frame.copy())
        video_capture.return_value = capture
        published = []
        first_frame = threading.Event()
        second_frame = threading.Event()
        messaging = MagicMock()

        def record_frame(_topic, message):
            published.append(message["image"].copy())
            (first_frame if len(published) == 1 else second_frame).set()

        messaging.publish.side_effect = record_frame
        publisher = CameraStreamPublisher("auxiliary", "/dev/video2", messaging)

        publisher.start()
        try:
            self.assertTrue(first_frame.wait(timeout=1.0))
            publisher.set_orientation(False, False, 90)
            self.assertTrue(second_frame.wait(timeout=1.0))
        finally:
            publisher.stop()

        np.testing.assert_array_equal(published[0], frame)
        # 90 degrees clockwise maps a 2x2 grid onto a 2x2 transposed grid.
        np.testing.assert_array_equal(published[1], np.array([[3, 1], [4, 2]], dtype=np.uint8))
        self.assertEqual(published[1].shape, frame.shape)

    def test_primary_vision_publishes_named_camera_topic(self) -> None:
        messaging = MagicMock()
        publisher = MessagePublisher(messaging)

        publisher.publish_camera_frame("primary-frame")

        message = {"image": "primary-frame", "camera": "primary_vision"}
        messaging.publish.assert_any_call(
            CameraTopics.frame("primary_vision"),
            message,
        )

    @patch("src.engine.vision.camera_stream_publisher.cv2.VideoCapture")
    def test_opens_once_and_publishes_named_camera_frames(self, video_capture) -> None:
        capture = MagicMock()
        capture.isOpened.return_value = True
        frame_published = threading.Event()
        messaging = MagicMock()

        def read_frame():
            if frame_published.is_set():
                return False, None
            frame_published.set()
            return True, "aux-frame"

        capture.read.side_effect = read_frame
        video_capture.return_value = capture
        publisher = CameraStreamPublisher(
            role="auxiliary",
            device="/dev/video2",
            messaging=messaging,
            width=1280,
            height=720,
        )

        publisher.start()
        self.assertTrue(frame_published.wait(timeout=1.0))
        publisher.stop()

        video_capture.assert_called_once()
        messaging.publish.assert_any_call(
            CameraTopics.frame("auxiliary"),
            {"image": "aux-frame", "camera": "auxiliary"},
        )
        capture.release.assert_called()


if __name__ == "__main__":
    unittest.main()
