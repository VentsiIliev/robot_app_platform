import unittest
from unittest.mock import MagicMock

from src.engine.vision.capture_snapshot_service import CaptureSnapshotService
from src.engine.vision.i_vision_service import VisionFrameUnavailableError


class TestCaptureSnapshotService(unittest.TestCase):

    def test_capture_snapshot_collects_frame_contours_and_robot_pose(self):
        vision = MagicMock()
        vision.compute_contours_for_latest_frame.return_value = ("frame", ["c1", "c2"])
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
        vision.compute_contours_for_latest_frame.side_effect = RuntimeError("processor down")
        vision.get_latest_frame.side_effect = RuntimeError("camera down")
        vision.get_latest_contours.side_effect = RuntimeError("no contours")
        service = CaptureSnapshotService(vision, None)

        snapshot = service.capture_snapshot(source="auto")

        self.assertIsNone(snapshot.frame)
        self.assertEqual(snapshot.contours, [])
        self.assertEqual(snapshot.source, "auto")

    def test_capture_snapshot_blocks_stale_vision_frames_without_fallback(self):
        vision = MagicMock()
        vision.compute_contours_for_latest_frame.side_effect = VisionFrameUnavailableError("stale frame")
        vision.get_latest_frame.return_value = "cached-frame"
        vision.get_latest_contours.return_value = ["cached-contour"]
        service = CaptureSnapshotService(vision, None)

        with self.assertRaisesRegex(VisionFrameUnavailableError, "stale frame"):
            service.capture_snapshot(source="paint")

        vision.get_latest_frame.assert_not_called()
        vision.get_latest_contours.assert_not_called()

    def test_capture_snapshot_tolerates_robot_pose_failure(self):
        robot = MagicMock()
        robot.get_current_position.side_effect = RuntimeError("robot offline")
        service = CaptureSnapshotService(None, robot)

        snapshot = service.capture_snapshot()

        self.assertIsNone(snapshot.robot_pose)

    def test_capture_snapshot_blocks_when_active_work_area_unknown(self):
        work_areas = MagicMock()
        work_areas.get_active_area_id.return_value = None
        service = CaptureSnapshotService(
            MagicMock(),
            None,
            work_area_service=work_areas,
            active_work_area_validator=lambda _area, _pose: (True, ""),
        )

        with self.assertRaisesRegex(RuntimeError, "Active work area is unknown"):
            service.capture_snapshot(source="paint")

    def test_capture_snapshot_blocks_when_active_work_area_validator_fails(self):
        work_areas = MagicMock()
        work_areas.get_active_area_id.return_value = "magazine"
        work_areas.is_active_area_verified.return_value = True
        robot = MagicMock()
        robot.get_current_position.return_value = [1, 2, 3, 4, 5, 6]
        service = CaptureSnapshotService(
            MagicMock(),
            robot,
            work_area_service=work_areas,
            active_work_area_validator=lambda area, pose: (
                False,
                f"{area} invalid at {pose[0]}",
            ),
        )

        with self.assertRaisesRegex(RuntimeError, "magazine invalid"):
            service.capture_snapshot(source="pick_target")

    def test_capture_snapshot_retries_active_work_area_validation_with_fresh_pose(self):
        work_areas = MagicMock()
        work_areas.get_active_area_id.return_value = "paint"
        work_areas.is_active_area_verified.return_value = True
        robot = MagicMock()
        robot.get_current_position.side_effect = [
            [100, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
        ]
        vision = MagicMock()
        vision.compute_contours_for_latest_frame.return_value = ("frame", [])

        def validate(_area, pose):
            return (pose == [0, 0, 0, 0, 0, 0], "stale pose")

        service = CaptureSnapshotService(
            vision,
            robot,
            work_area_service=work_areas,
            active_work_area_validator=validate,
            active_work_area_retry_timeout_s=0.2,
            active_work_area_retry_interval_s=0.01,
        )

        snapshot = service.capture_snapshot(source="paint")

        self.assertEqual(snapshot.robot_pose, [0, 0, 0, 0, 0, 0])
        self.assertEqual(robot.get_current_position.call_count, 2)

    def test_capture_snapshot_blocks_when_active_work_area_not_verified(self):
        work_areas = MagicMock()
        work_areas.get_active_area_id.return_value = "magazine"
        work_areas.is_active_area_verified.return_value = False
        service = CaptureSnapshotService(
            MagicMock(),
            None,
            work_area_service=work_areas,
            active_work_area_validator=lambda _area, _pose: (True, ""),
        )

        with self.assertRaisesRegex(RuntimeError, "not verified"):
            service.capture_snapshot(source="paint")
