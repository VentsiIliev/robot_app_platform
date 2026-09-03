import unittest
from enum import Enum
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.applications.base.dashboard_process_state_mixin import DashboardProcessStateMixin


class _ProcessID(str, Enum):
    MAIN_PROCESS = "main_process"


class _Controller(DashboardProcessStateMixin):
    def __init__(self):
        self._view = MagicMock()
        self._model = MagicMock()
        self._model._service.get_process_id.return_value = "paint_process"
        self._model.load.return_value = "state"
        self._init_dashboard_process_state()


class TestDashboardProcessStateMixin(unittest.TestCase):
    def test_error_event_message_is_shown_once(self):
        controller = _Controller()
        event = SimpleNamespace(
            process_id="paint_process",
            state=SimpleNamespace(value="error"),
            message="Move the robot to Calibration or Magazine before starting.",
        )

        controller._on_dashboard_process_state_raw(event)
        controller._on_dashboard_process_state_raw(event)

        controller._view.apply_dashboard_state.assert_called_with("state")
        controller._view.show_warning.assert_called_once_with(
            "Process Blocked",
            "Move the robot to Calibration or Magazine before starting.",
        )

    def test_no_workpiece_text_in_error_preserves_failure_message(self):
        controller = _Controller()
        event = SimpleNamespace(
            process_id="paint_process",
            state=SimpleNamespace(value="error"),
            message="No usable contour detected",
        )

        controller._on_dashboard_process_state_raw(event)

        controller._view.show_warning.assert_called_once_with(
            "Process Blocked",
            "No usable contour detected",
        )

    def test_magazine_servo_failure_with_no_workpiece_text_is_not_downgraded(self):
        controller = _Controller()
        message = "Magazine servo contact pickup failed: no workpiece detected after retract"
        event = SimpleNamespace(
            process_id="paint_process",
            state=SimpleNamespace(value="error"),
            message=message,
        )

        controller._on_dashboard_process_state_raw(event)

        controller._view.show_warning.assert_called_once_with("Process Blocked", message)

    def test_no_workpiece_stopped_message_is_shown_as_operator_warning(self):
        controller = _Controller()
        event = SimpleNamespace(
            process_id="paint_process",
            state=SimpleNamespace(value="stopped"),
            message="No workpiece detected after 2 paint cycle(s)",
        )

        controller._on_dashboard_process_state_raw(event)

        controller._view.show_warning.assert_called_once_with(
            "No Workpiece Found",
            "No workpiece was found in the camera view. Place a workpiece in the active area and start again.",
        )

    def test_non_matching_process_event_is_ignored(self):
        controller = _Controller()
        event = SimpleNamespace(
            process_id="other",
            state=SimpleNamespace(value="error"),
            message="hidden",
        )

        controller._on_dashboard_process_state_raw(event)

        controller._view.apply_dashboard_state.assert_not_called()
        controller._view.show_warning.assert_not_called()

    def test_enum_process_id_event_matches_service_string_process_id(self):
        controller = _Controller()
        controller._model._service.get_process_id.return_value = "main_process"
        controller._model.load.return_value = SimpleNamespace(
            process_state="error",
            can_start=False,
            can_stop=False,
            can_pause=False,
        )
        event = SimpleNamespace(
            process_id=_ProcessID.MAIN_PROCESS,
            state=SimpleNamespace(value="error"),
            message="Ordered paint motion chain failed with code -14",
        )

        controller._on_dashboard_process_state_raw(event)

        state = controller._view.apply_dashboard_state.call_args.args[0]
        self.assertEqual("error", state.process_state)
        self.assertFalse(state.can_stop)
        self.assertFalse(state.can_pause)
        controller._view.show_warning.assert_called_once_with(
            "Process Blocked",
            "Ordered paint motion chain failed with code -14",
        )


if __name__ == "__main__":
    unittest.main()
