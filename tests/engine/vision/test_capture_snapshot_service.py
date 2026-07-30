import unittest
from unittest.mock import MagicMock

from src.engine.vision.capture_snapshot_service import CaptureSnapshotService


class TestCaptureSnapshotService(unittest.TestCase):

    def test_capture_snapshot_collects_frame_contours_and_robot_pose(self):
        vision = MagicMock()
        vision.get_latest_frame.return_value = "frame"
        vision.get_latest_contours.return_value = ["c1", "c2"]
        robot = MagicMock()
        robot.get_current_position.return_value = (1, 2, 3, 4, 5, 6)
        service = CaptureSnapshotService(vision, robot)

        snapshot = service.capture_snapshot(source="manual")

        self.assertEqual(snapshot.frame, "frame")
        self.assertEqual(snapshot.contours, ["c1", "c2"])
        self.assertEqual(snapshot.robot_pose, [1, 2, 3, 4, 5, 6])
        self.assertEqual(snapshot.source, "manual")
        self.assertIsInstance(snapshot.timestamp_s, float)

    def test_capture_snapshot_without_services_returns_empty_snapshot(self):
        service = CaptureSnapshotService(None, None)

        snapshot = service.capture_snapshot()

        self.assertIsNone(snapshot.frame)
        self.assertEqual(snapshot.contours, [])
        self.assertIsNone(snapshot.robot_pose)
        self.assertEqual(snapshot.source, "")

    def test_capture_snapshot_tolerates_vision_failures(self):
        vision = MagicMock()
        vision.get_latest_frame.side_effect = RuntimeError("camera down")
        vision.get_latest_contours.side_effect = RuntimeError("no contours")
        service = CaptureSnapshotService(vision, None)

        snapshot = service.capture_snapshot(source="auto")

        self.assertIsNone(snapshot.frame)
        self.assertEqual(snapshot.contours, [])
        self.assertEqual(snapshot.source, "auto")

    def test_capture_snapshot_tolerates_robot_pose_failure(self):
        robot = MagicMock()
        robot.get_current_position.side_effect = RuntimeError("robot offline")
        service = CaptureSnapshotService(None, robot)

        snapshot = service.capture_snapshot()

        self.assertIsNone(snapshot.robot_pose)
