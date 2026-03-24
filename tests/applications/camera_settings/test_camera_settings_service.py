"""
Tests for camera_settings service layer.

Covers:
- StubCameraSettingsService  — interface compliance + in-memory behaviour
- CameraSettingsApplicationService — delegation to settings_service and vision_service
"""
import unittest
from unittest.mock import MagicMock

from src.applications.camera_settings.camera_settings_data import CameraSettingsData
from src.applications.camera_settings.service.i_camera_settings_service import ICameraSettingsService
from src.applications.camera_settings.service.stub_camera_settings_service import StubCameraSettingsService
from src.applications.camera_settings.service.camera_settings_application_service import CameraSettingsApplicationService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_settings_service(data: dict = None):
    ss = MagicMock()
    raw = MagicMock()
    raw.data = data or {}
    ss.get.return_value = raw
    return ss


def _make_vision_service():
    vs = MagicMock()
    vs.update_settings.return_value = (True, "ok")
    return vs


def _make_work_area_service():
    service = MagicMock()
    service.save_work_area.return_value = (True, "saved")
    service.get_work_area.return_value = [(0.1, 0.2)]
    return service


def _make_app_service(data=None, vision=None, work_area_service=None):
    ss  = _make_settings_service(data)
    vs  = vision if vision is not None else _make_vision_service()
    was = work_area_service if work_area_service is not None else _make_work_area_service()
    svc = CameraSettingsApplicationService(settings_service=ss, vision_service=vs, work_area_service=was)
    return svc, ss, vs, was


# ══════════════════════════════════════════════════════════════════════════════
# StubCameraSettingsService
# ══════════════════════════════════════════════════════════════════════════════

class TestStubCameraSettingsService(unittest.TestCase):

    def setUp(self):
        self._stub = StubCameraSettingsService()

    def test_implements_interface(self):
        self.assertIsInstance(self._stub, ICameraSettingsService)

    def test_load_settings_returns_data(self):
        result = self._stub.load_settings()
        self.assertIsInstance(result, CameraSettingsData)

    def test_save_settings_updates_stored_data(self):
        new_data = CameraSettingsData(index=3)
        self._stub.save_settings(new_data)
        self.assertIs(self._stub.load_settings(), new_data)

    def test_set_raw_mode_does_not_raise(self):
        self._stub.set_raw_mode(True)
        self._stub.set_raw_mode(False)

    def test_update_settings_returns_true_tuple(self):
        ok, msg = self._stub.update_settings({"threshold": 100})
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_save_work_area_returns_true_tuple(self):
        ok, msg = self._stub.save_work_area("roi", [(0.0, 0.0), (0.5, 0.5)])
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_get_work_area_returns_tuple(self):
        ok, msg, points = self._stub.get_work_area("roi")
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)


# ══════════════════════════════════════════════════════════════════════════════
# CameraSettingsApplicationService — load
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsApplicationServiceLoad(unittest.TestCase):

    def test_load_calls_settings_service_get(self):
        svc, ss, _, _ = _make_app_service()
        svc.load_settings()
        ss.get.assert_called_once()

    def test_load_returns_camera_settings_data(self):
        svc, _, _, _ = _make_app_service()
        result = svc.load_settings()
        self.assertIsInstance(result, CameraSettingsData)

    def test_load_parses_index_from_raw(self):
        svc, _, _, _ = _make_app_service(data={"Index": 2})
        result = svc.load_settings()
        self.assertEqual(result.index, 2)


# ══════════════════════════════════════════════════════════════════════════════
# CameraSettingsApplicationService — save
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsApplicationServiceSave(unittest.TestCase):

    def test_save_calls_settings_service_save(self):
        svc, ss, _, _ = _make_app_service()
        svc.save_settings(CameraSettingsData())
        ss.save.assert_called_once()

    def test_save_calls_vision_update_settings(self):
        svc, _, vs, _ = _make_app_service()
        svc.save_settings(CameraSettingsData())
        vs.update_settings.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# CameraSettingsApplicationService — update_settings
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsApplicationServiceUpdateSettings(unittest.TestCase):

    def test_update_delegates_to_vision(self):
        svc, _, vs, _ = _make_app_service()
        vs.update_settings.return_value = (True, "updated")
        ok, msg = svc.update_settings({"threshold": 100})
        vs.update_settings.assert_called_once_with({"threshold": 100})
        self.assertTrue(ok)

    def test_update_passes_through_failure(self):
        svc, _, vs, _ = _make_app_service()
        vs.update_settings.return_value = (False, "bad param")
        ok, msg = svc.update_settings({})
        self.assertFalse(ok)


# ══════════════════════════════════════════════════════════════════════════════
# CameraSettingsApplicationService — constructor with no vision
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsApplicationServiceVisionOptional(unittest.TestCase):

    def test_constructed_without_vision_does_not_raise(self):
        ss = _make_settings_service()
        was = _make_work_area_service()
        CameraSettingsApplicationService(settings_service=ss, vision_service=None, work_area_service=was)


# ══════════════════════════════════════════════════════════════════════════════
# CameraSettingsApplicationService — work area
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsApplicationServiceWorkArea(unittest.TestCase):

    def test_save_work_area_delegates_to_work_area_service(self):
        svc, _, _, was = _make_app_service()
        svc.save_work_area("roi", [(0.1, 0.2)])
        was.save_work_area.assert_called_once_with("roi", [(0.1, 0.2)])

    def test_get_work_area_delegates_to_work_area_service(self):
        svc, _, _, was = _make_app_service()
        was.get_work_area.return_value = [(0.1, 0.2)]
        ok, msg, pts = svc.get_work_area("roi")
        was.get_work_area.assert_called_once_with("roi")
        self.assertTrue(ok)
        self.assertEqual(pts, [(0.1, 0.2)])

    def test_set_raw_mode_delegates_to_vision(self):
        svc, _, vs, _ = _make_app_service()
        svc.set_raw_mode(True)
        vs.set_raw_mode.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
