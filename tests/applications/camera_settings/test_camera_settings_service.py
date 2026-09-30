"""
Tests for camera_settings service layer.

Covers:
- StubCameraSettingsService  — interface compliance + in-memory behaviour
- CameraSettingsApplicationService — delegation to settings_service and vision_service
"""
import unittest
from enum import Enum
from unittest.mock import MagicMock

from src.applications.camera_settings.camera_settings_data import CameraSettingsData
from src.applications.camera_settings.service.i_camera_settings_service import (
    CameraOrientation,
    ICameraSettingsService,
)
from src.applications.camera_settings.service.stub_camera_settings_service import StubCameraSettingsService
from src.applications.camera_settings.service.camera_settings_application_service import CameraSettingsApplicationService
from src.engine.vision.camera_device_settings import (
    CameraDeviceSpec,
    CameraDevicesConfig,
)


class _SettingsKey(str, Enum):
    CAMERAS = "cameras"


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

    def test_load_settings_returns_data(self):
        result = self._stub.load_settings()
        self.assertIsInstance(result, CameraSettingsData)

    def test_save_settings_updates_stored_data(self):
        new_data = CameraSettingsData(index=3)
        self._stub.save_settings(new_data)
        self.assertIs(self._stub.load_settings(), new_data)

    def test_set_raw_mode_does_not_change_saved_settings(self):
        before = self._stub.load_settings()
        self._stub.set_raw_mode(True)
        self._stub.set_raw_mode(False)
        self.assertIs(self._stub.load_settings(), before)

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
        self.assertEqual(points, [])


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

    def test_load_parses_hardware_auto_exposure(self):
        svc, _, _, _ = _make_app_service(
            data={"Brightness Control": {"Hardware auto exposure": True}}
        )

        result = svc.load_settings()

        self.assertTrue(result.hardware_auto_exposure)


# ══════════════════════════════════════════════════════════════════════════════
# CameraSettingsApplicationService — save
# ══════════════════════════════════════════════════════════════════════════════

class TestCameraSettingsApplicationServiceSave(unittest.TestCase):

    def test_save_applies_changed_hardware_auto_exposure(self):
        svc, _, vs, _ = _make_app_service(
            data={"Brightness Control": {"Hardware auto exposure": False}}
        )
        svc.load_settings()

        svc.save_settings(CameraSettingsData(hardware_auto_exposure=True))

        vs.set_auto_exposure.assert_called_once_with(True)

    def test_save_does_not_reapply_unchanged_hardware_auto_exposure(self):
        svc, _, vs, _ = _make_app_service(
            data={"Brightness Control": {"Hardware auto exposure": False}}
        )
        svc.load_settings()

        svc.save_settings(CameraSettingsData(hardware_auto_exposure=False))

        vs.set_auto_exposure.assert_not_called()

    def test_save_calls_settings_service_save(self):
        svc, ss, _, _ = _make_app_service()
        svc.save_settings(CameraSettingsData())
        ss.save.assert_called_once()

    def test_save_calls_vision_update_settings(self):
        svc, _, vs, _ = _make_app_service()
        svc.save_settings(CameraSettingsData())
        vs.update_settings.assert_called_once()

    def test_save_preserves_existing_calibration_section(self):
        svc, ss, vs, _ = _make_app_service(data={"Calibration": {"Enabled": True}})
        svc.save_settings(CameraSettingsData(index=4))

        saved_raw = ss.save.call_args[0][1]
        self.assertEqual(saved_raw.data["Calibration"], {"Enabled": True})
        self.assertEqual(saved_raw.data["Index"], 4)
        vs.update_settings.assert_called_once_with(saved_raw.data)


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

    def test_save_settings_requires_vision_service(self):
        ss = _make_settings_service()
        was = _make_work_area_service()
        svc = CameraSettingsApplicationService(settings_service=ss, vision_service=None, work_area_service=was)

        with self.assertRaises(AttributeError):
            svc.save_settings(CameraSettingsData())


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

    def test_save_work_area_fails_without_work_area_service(self):
        svc = CameraSettingsApplicationService(
            settings_service=_make_settings_service(),
            vision_service=_make_vision_service(),
            work_area_service=None,
        )
        ok, msg = svc.save_work_area("roi", [(0.1, 0.2)])
        self.assertFalse(ok)
        self.assertIn("No work area service", msg)

    def test_get_work_area_fails_without_work_area_service(self):
        svc = CameraSettingsApplicationService(
            settings_service=_make_settings_service(),
            vision_service=_make_vision_service(),
            work_area_service=None,
        )
        ok, msg, pts = svc.get_work_area("roi")
        self.assertFalse(ok)
        self.assertIn("No work area service", msg)
        self.assertEqual(pts, [])


class TestCameraSettingsApplicationServiceDevices(unittest.TestCase):
    def _make_service(self):
        settings_service = MagicMock()
        config = CameraDevicesConfig(
            cameras={
                "primary_vision": CameraDeviceSpec("/dev/missing-primary", required=True),
                "auxiliary": CameraDeviceSpec("/dev/missing-auxiliary"),
            }
        )
        settings_service.get.return_value = config
        vision = _make_vision_service()
        service = CameraSettingsApplicationService(
            settings_service=settings_service,
            vision_service=vision,
            camera_devices_settings_key=_SettingsKey.CAMERAS,
        )
        return service, settings_service, vision

    def test_load_camera_devices_includes_missing_configured_devices(self):
        service, _, _ = self._make_service()

        state = service.load_camera_devices()

        self.assertEqual(state.assignments["primary_vision"], "/dev/missing-primary")
        configured = {option.device: option for option in state.options}
        self.assertFalse(configured["/dev/missing-primary"].connected)

    def test_save_camera_devices_preserves_role_metadata(self):
        service, settings_service, _ = self._make_service()

        service.save_camera_devices(
            {
                "primary_vision": "/dev/new-primary",
                "auxiliary": "/dev/new-auxiliary",
            },
            {
                "primary_vision": CameraOrientation(
                    flip_horizontal=True, rotate_degrees=90
                ),
                "auxiliary": CameraOrientation(
                    flip_vertical=True, rotate_degrees=180
                ),
            },
        )

        saved = settings_service.save.call_args.args[1]
        self.assertEqual(saved.get("primary_vision").device, "/dev/new-primary")
        self.assertTrue(saved.get("primary_vision").required)
        self.assertTrue(saved.get("primary_vision").flip_horizontal)
        self.assertEqual(saved.get("primary_vision").rotate_degrees, 90)
        self.assertTrue(saved.get("auxiliary").flip_vertical)
        self.assertEqual(saved.get("auxiliary").rotate_degrees, 180)

    def test_save_applies_orientation_to_running_camera_owners(self):
        service, settings_service, _ = self._make_service()
        apply_orientation_to_owners = MagicMock()
        service._camera_orientation_setter = apply_orientation_to_owners

        service.save_camera_devices(
            {"primary_vision": "/dev/missing-primary", "auxiliary": "/dev/missing-auxiliary"},
            {
                "primary_vision": CameraOrientation(
                    flip_horizontal=True, rotate_degrees=90
                ),
                "auxiliary": CameraOrientation(
                    flip_vertical=True, rotate_degrees=270
                ),
            },
        )

        self.assertEqual(settings_service.save.call_count, 1)
        self.assertEqual(
            apply_orientation_to_owners.call_args_list,
            [
                unittest.mock.call("primary_vision", True, False, 90),
                unittest.mock.call("auxiliary", False, True, 270),
            ],
        )

    def test_save_falls_back_to_persisted_orientation_for_unlisted_roles(self):
        service, settings_service, _ = self._make_service()

        service.save_camera_devices(
            {"primary_vision": "/dev/missing-primary"},
            {},
        )

        saved = settings_service.save.call_args.args[1]
        self.assertEqual(saved.get("primary_vision").rotate_degrees, 0)

    def test_save_rejects_unsupported_rotation(self):
        service, _, _ = self._make_service()

        with self.assertRaisesRegex(ValueError, "rotation must be one of 0, 90, 180 or 270"):
            service.save_camera_devices(
                {"primary_vision": "/dev/missing-primary"},
                {"primary_vision": CameraOrientation(rotate_degrees=45)},
            )

if __name__ == "__main__":
    unittest.main()
