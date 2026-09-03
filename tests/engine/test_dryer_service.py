import unittest
import threading
import time
from unittest.mock import MagicMock

from src.engine.hardware.dryer.dryer_service import DryerService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig


class TestDryerService(unittest.TestCase):
    def test_async_enable_returns_before_initialization_completes(self) -> None:
        release = threading.Event()
        controller = MagicMock()
        controller.initialize.side_effect = lambda: release.wait(1.0) or True
        service = DryerService(lambda _config: controller, DryerConfig())

        self.assertTrue(service.enable_async())
        self.assertTrue(service.is_enabled())
        self.assertFalse(service.is_healthy())
        self.assertIn("progress", service.last_error.lower())

        release.set()
        deadline = time.monotonic() + 1.0
        while not service.is_healthy() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(service.is_healthy())
        self.assertIsNone(service.last_error)

    def test_disable_cancels_async_initialization_controller(self) -> None:
        started = threading.Event()
        release = threading.Event()
        controller = MagicMock()

        def initialize() -> bool:
            started.set()
            release.wait(1.0)
            return False

        controller.initialize.side_effect = initialize
        service = DryerService(lambda _config: controller, DryerConfig())
        self.assertTrue(service.enable_async())
        self.assertTrue(started.wait(1.0))

        service.disable()
        release.set()

        controller.shutdown.assert_called_once_with()
        self.assertFalse(service.is_enabled())
        self.assertFalse(service.is_healthy())

    def test_failed_next_position_verification_keeps_service_disabled(self) -> None:
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
