import logging
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea

from src.applications.device_control.controller.device_control_controller import (
    DeviceControlController,
)
from src.applications.device_control.view.device_control_view import DeviceControlView
from src.applications.device_control.dryer.view import DryerControlPanel
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from pl_gui.settings.settings_view.styles import TOUCH_SCROLL_AREA_STYLE


class TestDeviceControlController(unittest.TestCase):
    def _controller(self) -> DeviceControlController:
        controller = DeviceControlController.__new__(DeviceControlController)
        controller._device_stopped = False
        controller._device_action_in_flight = False
        controller._device_poll_in_flight = False
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
        controller._view.set_device_enabled.assert_called_once_with("fan", True)
        controller._device_executor.submit.assert_called_once_with(
            controller._model.set_device_enabled,
            "fan",
            True,
        )

    def test_failed_enable_rolls_optimistic_toggle_back_to_inactive(self) -> None:
        controller = self._controller()
        controller._pending_device_enabled = {"fan": True}

        with patch(
            "src.applications.device_control.controller.device_control_controller.QTimer.singleShot"
        ) as single_shot:
            controller._on_device_enabled_done("fan", False)

        delay, finish = single_shot.call_args.args
        self.assertEqual(delay, controller._FAILED_ENABLE_ROLLBACK_MS)
        controller._view.set_device_enabled.assert_not_called()

        finish()

        controller._view.set_device_enabled.assert_called_once_with("fan", False)
        controller._view.set_device_action_result.assert_called_once_with("fan", False)

    def test_completed_action_refreshes_only_the_acted_device(self) -> None:
        controller = self._controller()
        controller._model.get_devices.return_value = [
            MagicMock(key="vacuum_sensor"),
            MagicMock(key="dryer"),
        ]

        controller._on_device_action_done("dryer", True)

        controller._device_executor.submit.assert_called_once_with(
            controller._read_device_states,
            ["dryer"],
        )

    def test_load_attaches_and_loads_optional_dryer_panel(self) -> None:
        controller = self._controller()
        controller._dryer_view = MagicMock()
        controller._dryer_controller = MagicMock()
        controller._model.get_devices.return_value = []
        controller._model.get_motors.return_value = []
        controller._model.is_motor_available.return_value = False

        controller.load()

        controller._view.set_device_panel.assert_called_once_with(
            "dryer",
            controller._dryer_view,
        )
        controller._dryer_controller.load.assert_called_once_with()

    def test_stop_stops_optional_dryer_controller(self) -> None:
        controller = self._controller()
        controller._dryer_controller = MagicMock()
        controller._stop_threads = MagicMock()

        controller.stop()

        controller._dryer_controller.stop.assert_called_once_with()


class TestDeviceControlView(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_setup_does_not_emit_enable_request_for_enabled_device(self) -> None:
        device = MagicMock()
        device.key = "dryer"
        device.label = "Dryer"
        device.is_enabled.return_value = True
        device.actions.return_value = {"next_position": "Next Position"}
        view = DeviceControlView()
        requests = []

        def record_request(device_key: str, enabled: bool) -> None:
            requests.append((device_key, enabled))

        view.device_enabled_requested.connect(record_request)

        view.setup_devices([device])

        self.assertEqual([], requests)

    def test_device_tab_scrolls_as_one_complete_page(self) -> None:
        device = MagicMock()
        device.key = "dryer"
        device.label = "Dryer"
        device.is_enabled.return_value = True
        device.actions.return_value = {}
        view = DeviceControlView()

        view.setup_devices([device])
        panel = QLabel("Dryer configuration")
        view.set_device_panel("dryer", panel)

        page_scroll = view._tabs.widget(0)
        self.assertIsInstance(page_scroll, QScrollArea)
        self.assertIs(page_scroll.widget(), view._device_tabs["dryer"])
        self.assertEqual(page_scroll.styleSheet(), TOUCH_SCROLL_AREA_STYLE)
        self.assertEqual(
            page_scroll.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.assertEqual(panel.parentWidget(), view._device_tabs["dryer"])

    def test_dryer_settings_use_editable_parameter_tables(self) -> None:
        panel = DryerControlPanel()
        config = DryerConfig(pwm_open_vrytka=725, acceleration=0.4)

        panel.load_config(config)

        self.assertEqual(panel._register_table.columnCount(), 2)
        self.assertEqual(panel._timing_table.columnCount(), 2)
        self.assertEqual(panel._register_table.horizontalHeaderItem(0).text(), "Parameter")
        self.assertEqual(panel._register_table.horizontalHeaderItem(1).text(), "Value")
        self.assertEqual(panel.get_values()["pwm_open_vrytka"], 725)
        self.assertAlmostEqual(panel.get_values()["acceleration"], 0.4)


if __name__ == "__main__":
    unittest.main()
