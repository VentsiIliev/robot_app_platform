import logging
import unittest
from unittest.mock import MagicMock

from src.applications.device_control.controller.device_control_controller import (
    DeviceControlController,
)


class TestDeviceControlController(unittest.TestCase):
    def _controller(self) -> DeviceControlController:
        controller = DeviceControlController.__new__(DeviceControlController)
        controller._device_stopped = False
        controller._device_action_in_flight = False
        controller._pending_device_enabled = {}
        controller._view = MagicMock()
        controller._model = MagicMock()
        controller._device_executor = MagicMock()
        controller._logger = logging.getLogger("test.device_control")
        return controller

    def test_normal_action_does_not_access_lifecycle_enabled_value(self) -> None:
        controller = self._controller()

        controller._on_device_action("fan", "on")

        self.assertEqual(controller._pending_device_enabled, {})
        controller._device_executor.submit.assert_called_once_with(
            controller._model.execute_device_action,
            "fan",
            "on",
        )

    def test_lifecycle_request_records_requested_enabled_state(self) -> None:
        controller = self._controller()

        controller._on_device_enabled("fan", True)

        self.assertEqual(controller._pending_device_enabled, {"fan": True})
        controller._device_executor.submit.assert_called_once_with(
            controller._model.set_device_enabled,
            "fan",
            True,
        )


if __name__ == "__main__":
    unittest.main()
