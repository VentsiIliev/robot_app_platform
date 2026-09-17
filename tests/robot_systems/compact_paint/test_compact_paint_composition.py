import unittest

from src.robot_systems.compact_paint import CompactPaintRobotSystem
from src.robot_systems.paint.component_ids import ServiceID, SettingsID


class TestCompactPaintComposition(unittest.TestCase):
    def test_has_independent_storage_root(self):
        self.assertEqual("CompactPaintSystem", CompactPaintRobotSystem.metadata.name)
        self.assertEqual("storage/settings", CompactPaintRobotSystem.metadata.settings_root)

    def test_declares_no_automatic_dryer_components(self):
        setting_ids = {spec.name for spec in CompactPaintRobotSystem.settings_specs}
        service_ids = {spec.name for spec in CompactPaintRobotSystem.services}

        self.assertNotIn(SettingsID.DRYER_CONFIG, setting_ids)
        self.assertNotIn(ServiceID.DRYER, service_ids)
        self.assertNotIn(ServiceID.TRAY_FAN, service_ids)

    def test_uses_no_production_start_guard(self):
        system = CompactPaintRobotSystem()

        self.assertIsNone(system.build_production_start_guard())


if __name__ == "__main__":
    unittest.main()
