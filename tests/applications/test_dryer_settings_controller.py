import logging
import unittest
from unittest.mock import MagicMock

from src.applications.dryer_settings.controller.dryer_settings_controller import (
    DryerSettingsController,
)


class TestDryerSettingsController(unittest.TestCase):
    def test_enable_failure_immediately_turns_toggle_off(self) -> None:
        controller = DryerSettingsController.__new__(DryerSettingsController)
        controller._model = MagicMock()
        controller._view = MagicMock()
        controller._logger = logging.getLogger("test.dryer_settings")
        controller._model.is_enabled.return_value = False

        controller._on_enable_failed("Dryer initialization write failed")

        controller._view.set_busy.assert_called_once_with(False)
        controller._view.set_enabled.assert_called_once_with(False)
        controller._view.set_error.assert_called_once_with(
            "Dryer enable failed: Dryer initialization write failed"
        )

    def test_failed_enable_reconciles_toggle_with_actual_service_state(self) -> None:
        controller = DryerSettingsController.__new__(DryerSettingsController)
        controller._model = MagicMock()
        controller._view = MagicMock()
        controller._logger = logging.getLogger("test.dryer_settings")
        controller._model.save.side_effect = RuntimeError("Dryer initialization failed")
        controller._model.is_enabled.return_value = False

        controller._on_save({"enabled": True})

        controller._view.set_enabled.assert_called_once_with(False)
        controller._view.set_status.assert_called_once_with("Dryer initialization failed")

    def test_successful_enable_reconciles_toggle_with_actual_service_state(self) -> None:
        controller = DryerSettingsController.__new__(DryerSettingsController)
        controller._model = MagicMock()
        controller._view = MagicMock()
        controller._logger = logging.getLogger("test.dryer_settings")
        controller._model.is_enabled.return_value = True

        controller._on_save({"enabled": True})

        controller._view.set_enabled.assert_called_once_with(True)
        controller._view.set_status.assert_called_once_with("Saved")


if __name__ == "__main__":
    unittest.main()
