import os
import unittest
from unittest.mock import MagicMock

from src.robot_systems.paint_auto_dry.bootstrap_provider import (
    create_bootstrap_provider as create_auto_dry_provider,
)
from src.robot_systems.paint.paint_robot_system import (
    AutomaticDryerPaintRobotSystem,
    TrayDryerPaintRobotSystem,
)
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_schema import (
    build_process_groups,
)
from src.robot_systems.paint.processes.paint.config import (
    PaintDropoffConfig,
    PaintProcessConfig,
)
from src.robot_systems.paint.processes.paint.paint_process_config_service import (
    PaintProcessConfigService,
)
from src.robot_systems.paint_tray_dry.bootstrap_provider import (
    create_bootstrap_provider as create_tray_dry_provider,
)


class TestPaintProfiles(unittest.TestCase):
    def test_selects_automatic_dryer_profile(self):
        provider = create_auto_dry_provider()

        self.assertIs(provider.system_class, AutomaticDryerPaintRobotSystem)

    def test_selects_tray_dryer_profile(self):
        provider = create_tray_dry_provider()

        self.assertIs(provider.system_class, TrayDryerPaintRobotSystem)
        self.assertFalse(provider.system_class.ui_config.show_drying_mode_control)

    def test_automatic_dryer_keeps_mode_selection(self):
        provider = create_auto_dry_provider()

        self.assertTrue(provider.system_class.ui_config.show_drying_mode_control)

    def test_tray_dryer_only_allows_plate_layout_dropoff(self):
        self.assertEqual(
            TrayDryerPaintRobotSystem.allowed_dropoff_strategies,
            ("plate_layout",),
        )

        strategy_field = next(
            field
            for group in build_process_groups(
                TrayDryerPaintRobotSystem.allowed_dropoff_strategies
            )
            for field in group.fields
            if field.key == "dropoff_strategy"
        )
        self.assertEqual(strategy_field.choices, ["plate_layout"])
        self.assertEqual(strategy_field.default, "plate_layout")

    def test_height_measuring_is_disabled_only_for_tray_dryer(self):
        self.assertFalse(TrayDryerPaintRobotSystem.height_measuring_enabled)
        self.assertTrue(AutomaticDryerPaintRobotSystem.height_measuring_enabled)

    def test_tray_dryer_rejects_movement_group_dropoff_at_runtime(self):
        settings = MagicMock()
        settings.get.return_value = PaintProcessConfig(
            dropoff=PaintDropoffConfig(strategy="plate_layout")
        )
        service = PaintProcessConfigService(
            settings,
            allowed_dropoff_strategies=("plate_layout",),
        )

        with self.assertRaisesRegex(ValueError, "not available"):
            service.save(
                PaintProcessConfig(
                    dropoff=PaintDropoffConfig(strategy="movement_group")
                )
            )

        settings.save.assert_not_called()

    def test_profile_storage_is_isolated(self):
        automatic_root = AutomaticDryerPaintRobotSystem.storage_path()
        tray_root = TrayDryerPaintRobotSystem.storage_path()

        self.assertNotEqual(automatic_root, tray_root)
        self.assertTrue(automatic_root.endswith(os.path.join("automatic_dryer", "storage")))
        self.assertTrue(tray_root.endswith(os.path.join("tray_dryer", "storage")))
        self.assertTrue(
            AutomaticDryerPaintRobotSystem.users_storage_path().startswith(automatic_root)
        )
        self.assertTrue(
            TrayDryerPaintRobotSystem.permissions_storage_path().startswith(tray_root)
        )

if __name__ == "__main__":
    unittest.main()
