import unittest

from src.applications.camera_settings.view import camera_settings_schema


class TestCameraSettingsSchema(unittest.TestCase):
    def test_camera_settings_does_not_expose_calibration_group(self):
        self.assertFalse(
            hasattr(camera_settings_schema, "CALIBRATION_GROUP"),
            "CameraSettings should not own calibration settings",
        )
