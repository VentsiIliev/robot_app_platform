"""
Tests for src/applications/camera_settings/model/camera_settings_model.y_pixels
"""
import unittest
from unittest.mock import MagicMock

from src.applications.camera_settings.camera_settings_data import CameraSettingsData
from src.applications.camera_settings.model.camera_settings_model import CameraSettingsModel
from src.applications.camera_settings.service.i_camera_settings_service import ICameraSettingsService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_service(settings=None):
    svc = MagicMock(spec=ICameraSettingsService)
    svc.load_settings.return_value = settings or CameraSettingsData()
    svc.save_work_area.return_value = (True, "saved")
    svc.get_work_area.return_value  = (True, "ok", [(100, 200)])
    return svc


# ══════════════════════════════════════════════════════════════════════════════
# load()
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsModelLoad(unittest.TestCase):

    def test_load_calls_service(self):
        svc = _make_service()
        model = CameraSettingsModel(svc)
        model.load()
        svc.load_settings.assert_called_once()

    def test_load_returns_camera_settings_data(self):
        data = CameraSettingsData(index=5)
        svc  = _make_service(data)
        model = CameraSettingsModel(svc)
        result = model.load()
        self.assertIs(result, data)

    def test_load_caches_settings(self):
        data = CameraSettingsData(threshold=99)
        svc  = _make_service(data)
        model = CameraSettingsModel(svc)
        model.load()
        self.assertEqual(model.current_settings.threshold, 99)


# ══════════════════════════════════════════════════════════════════════════════
# save()
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsModelSave(unittest.TestCase):

    def test_save_delegates_to_service(self):
        svc   = _make_service()
        model = CameraSettingsModel(svc)
        data  = CameraSettingsData(index=7)
        model.save(data)
        svc.save_settings.assert_called_once_with(data)

    def test_save_updates_cached_settings(self):
        svc   = _make_service()
        model = CameraSettingsModel(svc)
        data  = CameraSettingsData(index=3)
        model.save(data)
        self.assertIs(model.current_settings, data)


# ══════════════════════════════════════════════════════════════════════════════
# current_settings property
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsModelCurrentSettings(unittest.TestCase):

    def test_initial_current_settings_is_default(self):
        model = CameraSettingsModel(_make_service())
        self.assertIsInstance(model.current_settings, CameraSettingsData)

    def test_current_settings_reflects_loaded_data(self):
        data  = CameraSettingsData(width=640)
        svc   = _make_service(data)
        model = CameraSettingsModel(svc)
        model.load()
        self.assertEqual(model.current_settings.width, 640)


# ══════════════════════════════════════════════════════════════════════════════
# work_area helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsModelWorkArea(unittest.TestCase):

    def test_save_work_area_converts_normalized_to_pixel(self):
        svc   = _make_service(CameraSettingsData(width=1000, height=500))
        model = CameraSettingsModel(svc)
        model.load()
        model.save_work_area("roi_area", [(0.1, 0.2)])
        called_points = svc.save_work_area.call_args[0][1]
        self.assertEqual(called_points, [(100, 100)])

    def test_save_work_area_strips_area_suffix(self):
        svc   = _make_service()
        model = CameraSettingsModel(svc)
        model.load()
        model.save_work_area("roi_area", [])
        area_type = svc.save_work_area.call_args[0][0]
        self.assertEqual(area_type, "roi")

    def test_get_work_area_returns_empty_on_failure(self):
        svc   = _make_service()
        svc.get_work_area.return_value = (False, "none", None)
        model = CameraSettingsModel(svc)
        model.load()
        result = model.get_work_area("roi_area")
        self.assertEqual(result, [])

    def test_get_work_area_converts_pixel_to_normalized(self):
        svc   = _make_service(CameraSettingsData(width=1000, height=500))
        svc.get_work_area.return_value = (True, "ok", [(500, 250)])
        model = CameraSettingsModel(svc)
        model.load()
        result = model.get_work_area("roi_area")
        self.assertEqual(result, [(0.5, 0.5)])


if __name__ == "__main__":
    unittest.main()
