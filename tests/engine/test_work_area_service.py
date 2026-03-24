import unittest
from unittest.mock import MagicMock

from src.engine.common_settings_ids import CommonSettingsID
from src.shared_contracts.declarations import WorkAreaDefinition
from src.engine.work_areas.work_area_service import WorkAreaService
from src.engine.work_areas.work_area_settings import WorkAreaSettings


class TestWorkAreaService(unittest.TestCase):
    def _make_settings(self, settings=None):
        service = MagicMock()
        current = settings if settings is not None else WorkAreaSettings()

        def get_side_effect(key):
            self.assertEqual(key, CommonSettingsID.WORK_AREA_SETTINGS)
            return current

        def save_side_effect(key, value):
            nonlocal current
            self.assertEqual(key, CommonSettingsID.WORK_AREA_SETTINGS)
            current = value

        service.get.side_effect = get_side_effect
        service.save.side_effect = save_side_effect
        return service

    def test_defaults_active_area_from_robot_system_default(self):
        service = WorkAreaService(
            settings_service=self._make_settings(),
            definitions=[WorkAreaDefinition(id="spray", label="Spray", color="#f80")],
            default_active_area_id="spray",
        )
        self.assertEqual(service.get_active_area_id(), "spray")

    def test_set_invalid_active_area_raises(self):
        service = WorkAreaService(
            settings_service=self._make_settings(),
            definitions=[WorkAreaDefinition(id="spray", label="Spray", color="#f80")],
        )
        with self.assertRaises(KeyError):
            service.set_active_area_id("missing")

    def test_save_and_get_detection_roi(self):
        service = WorkAreaService(
            settings_service=self._make_settings(),
            definitions=[WorkAreaDefinition(id="spray", label="Spray", color="#f80")],
        )
        ok, _ = service.save_work_area("spray", [[0.1, 0.2], [0.3, 0.4]])
        self.assertTrue(ok)
        self.assertEqual(service.get_work_area("spray"), [[0.1, 0.2], [0.3, 0.4]])

    def test_get_brightness_roi_falls_back_to_detection(self):
        service = WorkAreaService(
            settings_service=self._make_settings(),
            definitions=[WorkAreaDefinition(id="spray", label="Spray", color="#f80")],
        )
        service.save_work_area("spray", [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8]])
        points = service.get_brightness_roi_pixels("spray", 100, 200)
        self.assertEqual(points.tolist(), [[10.0, 40.0], [30.0, 80.0], [50.0, 120.0], [70.0, 160.0]])

    def test_get_area_definition_returns_declared_definition(self):
        definition = WorkAreaDefinition(id="pickup", label="Pickup", color="#0f0", threshold_profile="pickup")
        service = WorkAreaService(
            settings_service=self._make_settings(),
            definitions=[definition],
        )
        self.assertEqual(service.get_area_definition("pickup"), definition)


if __name__ == "__main__":
    unittest.main()
