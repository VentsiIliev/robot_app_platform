import unittest
from unittest.mock import MagicMock

from src.engine.hardware.dryer.dryer_service import DryerService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig


class TestDryerService(unittest.TestCase):
    def test_failed_homing_keeps_service_disabled(self) -> None:
        controller = MagicMock()
        controller.initialize.return_value = False
        service = DryerService(lambda _config: controller, DryerConfig())

        self.assertFalse(service.enable())
        self.assertFalse(service.is_enabled())
        self.assertFalse(service.is_healthy())
        controller.shutdown.assert_called_once_with()

    def test_failed_enable_keeps_stable_service_disabled_and_reports_error(self) -> None:
        controller = MagicMock()
        controller.initialize.return_value = False
        service = DryerService(lambda _config: controller, DryerConfig())

        self.assertFalse(service.enable())
        self.assertFalse(service.is_enabled())
        self.assertIn("initialization", service.last_error.lower())
        controller.shutdown.assert_called_once_with()
        self.assertFalse(service.open_plate())

    def test_disable_releases_controller_and_commands_fail_safely(self) -> None:
        controller = MagicMock()
        controller.initialize.return_value = True
        service = DryerService(lambda _config: controller, DryerConfig())
        self.assertTrue(service.enable())

        service.disable()

        controller.shutdown.assert_called_once_with()
        self.assertFalse(service.is_enabled())
        self.assertFalse(service.move_servos())


if __name__ == "__main__":
    unittest.main()
