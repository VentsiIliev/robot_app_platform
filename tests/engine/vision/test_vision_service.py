import unittest
from enum import Enum
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
from src.engine.vision.vision_service import VisionService


class _ServiceState(Enum):
    IDLE = "idle"
    STARTED = "started"
    ERROR = "error"


def _make_camera_settings():
    settings = MagicMock()
    settings.get_camera_width.return_value = 1920
    settings.get_camera_height.return_value = 1080
    settings.get_chessboard_width.return_value = 11
    settings.get_chessboard_height.return_value = 8
    settings.get_square_size_mm.return_value = 25.0
    settings.get_brightness_auto.return_value = True
    settings.get_capture_pos_offset.return_value = -4.0
    return settings


def _make_vision_system():
    system = MagicMock()
    system.camera_settings = _make_camera_settings()
    system.state_manager = None
    system.correctedImage = None
    system.rawImage = None
    system.camera = MagicMock()
    system.camera.isOpened.return_value = True
    system.frame_grabber = MagicMock()
    system.frame_grabber.get_latest_snapshot.return_value = object()
    system._latest_contours = None
    system.camera_to_robot_matrix_path = "/tmp/camera_to_robot.npy"
    return system


class TestVisionServiceLifecycle(unittest.TestCase):

    def test_start_starts_system_and_sets_running(self):
        system = _make_vision_system()
        service = VisionService(system)

        service.start()

        system.start_system.assert_called_once_with()
        self.assertTrue(service._running)

    def test_stop_stops_system_and_clears_running(self):
        system = _make_vision_system()
        service = VisionService(system)
        service._running = True

        service.stop()

        system.stop_system.assert_called_once_with()
        self.assertFalse(service._running)


class TestVisionServiceHealth(unittest.TestCase):

    def test_not_healthy_when_not_running(self):
        service = VisionService(_make_vision_system())
        self.assertFalse(service.is_healthy())

    def test_running_without_state_manager_uses_running_camera_and_fresh_frame(self):
        service = VisionService(_make_vision_system())
        service._running = True
        self.assertTrue(service.is_healthy())

    def test_running_without_fresh_frame_is_unhealthy(self):
        system = _make_vision_system()
        system.frame_grabber.get_latest_snapshot.return_value = None
        service = VisionService(system)
        service._running = True

        self.assertFalse(service.is_healthy())
        self.assertEqual(service.get_health_details()["message"], "No fresh camera frame available")

    def test_running_without_open_camera_is_unhealthy(self):
        system = _make_vision_system()
        system.camera.isOpened.return_value = False
        service = VisionService(system)
        service._running = True

        self.assertFalse(service.is_healthy())
        self.assertEqual(service.get_health_details()["message"], "Camera is not open")

    def test_running_with_started_state_is_healthy(self):
        system = _make_vision_system()
        system.state_manager = MagicMock(state=_ServiceState.STARTED)
        service = VisionService(system)
        service._running = True

        with patch(
            "src.engine.vision.implementation.VisionSystem.core.external_communication.system_state_management.ServiceState",
            _ServiceState,
        ):
            self.assertTrue(service.is_healthy())

    def test_running_with_error_state_is_unhealthy(self):
        system = _make_vision_system()
        system.state_manager = MagicMock(state=_ServiceState.ERROR)
        service = VisionService(system)
        service._running = True

        with patch(
            "src.engine.vision.implementation.VisionSystem.core.external_communication.system_state_management.ServiceState",
            _ServiceState,
        ):
            self.assertFalse(service.is_healthy())


class TestVisionServiceFramesAndContours(unittest.TestCase):

    def test_get_latest_frame_prefers_corrected_frame(self):
        system = _make_vision_system()
        corrected = np.ones((2, 2, 3), dtype=np.uint8)
        raw = np.zeros((2, 2, 3), dtype=np.uint8)
        system.correctedImage = corrected
        system.rawImage = raw

        service = VisionService(system)

        self.assertIs(service.get_latest_frame(), corrected)

    def test_get_latest_frame_falls_back_to_raw_frame(self):
        system = _make_vision_system()
        raw = np.zeros((2, 2, 3), dtype=np.uint8)
        system.rawImage = raw

        service = VisionService(system)

        self.assertIs(service.get_latest_frame(), raw)

    def test_get_latest_contours_returns_copy(self):
        system = _make_vision_system()
        contour = np.array([[1, 2]], dtype=np.int32)
        system._latest_contours = [contour]
        service = VisionService(system)

        contours = service.get_latest_contours()
        contours.append(np.array([[3, 4]], dtype=np.int32))

        self.assertEqual(len(system._latest_contours), 1)
        self.assertIs(contours[0], contour)


class TestVisionSystemRun(unittest.TestCase):

    def test_run_publishes_corrected_frame_when_contour_detection_is_off(self):
        system = VisionSystem.__new__(VisionSystem)
        raw = np.zeros((2, 2, 3), dtype=np.uint8)
        corrected = np.ones((2, 2, 3), dtype=np.uint8)
        system.frame_grabber = MagicMock()
        system.frame_grabber.get_latest_snapshot_since.return_value = SimpleNamespace(
            frame=raw,
            sequence=7,
            timestamp_s=12.0,
        )
        system._last_processed_frame_sequence = 0
        system._latest_frame_timestamp_s = 0.0
        system.current_skip_frames = 0
        system.camera_settings = MagicMock()
        system.camera_settings.get_skip_frames.return_value = 0
        system.camera_settings.get_brightness_auto.return_value = False
        system.camera_settings.get_contour_detection.return_value = False
        system.state_manager = MagicMock()
        system.rawMode = False
        system.message_publisher = MagicMock()
        system.cameraMatrix = np.eye(3)
        system.correctImage = MagicMock(return_value=corrected)
        system.image = None
        system.rawImage = None
        system.correctedImage = None
        system._latest_contours = [np.array([[1, 2]], dtype=np.int32)]

        contours, display_image, extra = system.run()

        self.assertIsNone(contours)
        self.assertIs(display_image, corrected)
        self.assertIsNone(extra)
        system.message_publisher.publish_latest_image.assert_called_once_with(corrected)
        self.assertEqual(system._latest_contours, [])


class TestVisionServiceDelegation(unittest.TestCase):

    def test_save_work_area_converts_points_to_float32_array(self):
        system = _make_vision_system()
        service = VisionService(system)

        service.save_work_area("main", [[1, 2], [3, 4]])

        payload = system.saveWorkAreaPoints.call_args.args[0]
        self.assertEqual(payload["area_type"], "main")
        self.assertEqual(payload["corners"].dtype, np.float32)
        self.assertEqual(payload["corners"].tolist(), [[1.0, 2.0], [3.0, 4.0]])

    def test_set_auto_exposure_updates_camera_and_brightness(self):
        system = _make_vision_system()
        system.camera = MagicMock()
        service = VisionService(system)

        service.set_auto_exposure(True)

        system.camera.set_auto_exposure.assert_called_once_with(True)
        system.camera_settings.set_brightness_auto.assert_called_once_with(True)

    def test_set_auto_exposure_without_camera_support_still_updates_brightness(self):
        system = _make_vision_system()
        system.camera = object()
        service = VisionService(system)

        service.set_auto_exposure(False)

        system.camera_settings.set_brightness_auto.assert_called_once_with(False)

    def test_set_active_work_area_publishes_region_even_on_invalid_area(self):
        system = _make_vision_system()
        work_area_service = MagicMock()
        work_area_service.set_active_area_id.side_effect = KeyError("bad area")
        service = VisionService(system, work_area_service)

        service.set_active_work_area("ghost")

        work_area_service.set_active_area_id.assert_called_once_with("ghost")
        system.on_threshold_update.assert_called_once_with({"region": "ghost"})

    def test_set_active_work_area_with_none_clears_threshold_region(self):
        system = _make_vision_system()
        work_area_service = MagicMock()
        service = VisionService(system, work_area_service)

        service.set_active_work_area(None)

        work_area_service.set_active_area_id.assert_called_once_with(None)
        system.on_threshold_update.assert_called_once_with({"region": ""})

    def test_run_matching_returns_result_counts_and_unwrapped_contours(self):
        system = _make_vision_system()
        service = VisionService(system)
        matched = MagicMock()
        matched.get.return_value = "matched-contour"
        unmatched = MagicMock()
        unmatched.get.return_value = "unmatched-contour"

        matching = MagicMock(return_value=({"workpieces": [1]}, [unmatched], [matched]))
        fake_module = SimpleNamespace(find_matching_workpieces=matching)
        module_name = (
            "src.engine.vision.implementation.VisionSystem.features."
            "contour_matching"
        )
        with patch.dict(sys.modules, {module_name: fake_module}):
            result = service.run_matching(["wp"], ["contour"])

        matching.assert_called_once_with(["wp"], ["contour"])
        self.assertEqual(
            result,
            ({"workpieces": [1]}, 1, ["matched-contour"], ["unmatched-contour"]),
        )
