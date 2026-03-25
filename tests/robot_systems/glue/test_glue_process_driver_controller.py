import unittest
from unittest.mock import MagicMock

from src.robot_systems.glue.applications.glue_process_driver.controller.glue_process_driver_controller import (
    GlueProcessDriverController,
)
from src.robot_systems.glue.component_ids import ProcessID
from src.shared_contracts.events.glue_process_events import GlueProcessTopics
from src.shared_contracts.events.process_events import ProcessState, ProcessStateEvent, ProcessTopics


def _make_view():
    view = MagicMock()
    view.capture_match_requested.connect = MagicMock()
    view.build_job_requested.connect = MagicMock()
    view.load_job_requested.connect = MagicMock()
    view.manual_mode_toggled.connect = MagicMock()
    view.step_requested.connect = MagicMock()
    view.start_requested.connect = MagicMock()
    view.pause_requested.connect = MagicMock()
    view.resume_requested.connect = MagicMock()
    view.stop_requested.connect = MagicMock()
    view.reset_errors_requested.connect = MagicMock()
    view.refresh_requested.connect = MagicMock()
    view.destroyed.connect = MagicMock()
    view.get_selected_match_indexes.return_value = [0]
    return view


class TestGlueProcessDriverController(unittest.TestCase):
    def _make(self):
        model = MagicMock()
        model.load.return_value = {"process_state": "idle", "manual_mode": False, "dispensing": None}
        model.refresh_process_snapshot.return_value = {"process_state": "running", "manual_mode": False, "dispensing": None}
        model.get_match_summary.return_value = {"matched_workpiece_count": 0}
        model.get_latest_job.return_value = None
        model.get_latest_job_summary.return_value = None
        view = _make_view()
        broker = MagicMock()
        ctrl = GlueProcessDriverController(model, view, broker)
        return ctrl, model, view, broker

    def test_init_wires_view_signals(self):
        _, _, view, _ = self._make()
        view.capture_match_requested.connect.assert_called_once()
        view.build_job_requested.connect.assert_called_once()
        view.load_job_requested.connect.assert_called_once()
        view.manual_mode_toggled.connect.assert_called_once()
        view.step_requested.connect.assert_called_once()
        view.start_requested.connect.assert_called_once()
        view.pause_requested.connect.assert_called_once()
        view.resume_requested.connect.assert_called_once()
        view.stop_requested.connect.assert_called_once()
        view.reset_errors_requested.connect.assert_called_once()
        view.refresh_requested.connect.assert_called_once()
        view.destroyed.connect.assert_called_once()

    def test_load_pushes_initial_snapshot_to_view(self):
        ctrl, model, view, broker = self._make()

        ctrl.load()

        model.load.assert_called_once_with()
        view.set_process_snapshot.assert_called_once_with({"process_state": "idle", "manual_mode": False, "dispensing": None})
        view.set_manual_mode_enabled.assert_called_once_with(False)
        broker.subscribe.assert_any_call(ProcessTopics.state(ProcessID.GLUE), ctrl._on_process_state_event)
        broker.subscribe.assert_any_call(GlueProcessTopics.DIAGNOSTICS, ctrl._on_diagnostics)

    def test_capture_and_match_updates_view(self):
        ctrl, model, view, _ = self._make()
        model.capture_and_match.return_value = {"result": {"workpieces": []}}
        model.get_match_summary.return_value = {"matched_workpiece_count": 2, "matched_ids": ["a", "b"]}
        model.get_latest_matched_workpieces.return_value = [{"workpieceId": "a"}, {"workpieceId": "b"}]

        ctrl._on_capture_and_match()

        model.capture_and_match.assert_called_once_with()
        view.set_match_summary.assert_called_once_with({"matched_workpiece_count": 2, "matched_ids": ["a", "b"]})
        view.set_matched_workpieces.assert_called_once_with([{"workpieceId": "a"}, {"workpieceId": "b"}])

    def test_build_job_updates_view(self):
        ctrl, model, view, _ = self._make()
        model.build_job.return_value = "job-object"
        model.get_latest_job_summary.return_value = {"segment_count": 3}

        ctrl._on_build_job()

        model.build_job.assert_called_once_with(selected_indexes=[0])
        view.set_job_summary.assert_called_once_with({"segment_count": 3})

    def test_load_job_delegates_to_model(self):
        ctrl, model, _, _ = self._make()

        ctrl._on_load_job(True)

        model.load_job.assert_called_once_with(spray_on=True)

    def test_process_commands_delegate_to_model(self):
        ctrl, model, _, _ = self._make()

        ctrl._on_manual_mode_toggled(True)
        ctrl._on_step()
        ctrl._on_start()
        ctrl._on_pause()
        ctrl._on_resume()
        ctrl._on_stop()
        ctrl._on_reset_errors()

        model.set_manual_mode.assert_called_once_with(True)
        model.step_once.assert_called_once_with()
        model.start.assert_called_once_with()
        model.pause.assert_called_once_with()
        model.resume.assert_called_once_with()
        model.stop.assert_called_once_with()
        model.reset_errors.assert_called_once_with()

    def test_refresh_updates_process_snapshot(self):
        ctrl, model, view, _ = self._make()
        model.refresh_process_snapshot.return_value = {"process_state": "running", "dispensing": {"current_path_index": 1}}

        ctrl._on_refresh()

        view.set_process_snapshot.assert_called_once_with(
            {"process_state": "running", "dispensing": {"current_path_index": 1}}
        )

    def test_stop_does_not_raise(self):
        ctrl, _, _, _ = self._make()
        ctrl.stop()
        ctrl.stop()

    def test_view_destroyed_stops_controller(self):
        ctrl, _, _, broker = self._make()
        ctrl.load()

        ctrl._on_view_destroyed()

        broker.unsubscribe.assert_any_call(ProcessTopics.state(ProcessID.GLUE), ctrl._on_process_state_event)
        broker.unsubscribe.assert_any_call(GlueProcessTopics.DIAGNOSTICS, ctrl._on_diagnostics)

    def test_process_state_event_refreshes_snapshot_through_broker_path(self):
        ctrl, model, view, _ = self._make()
        ctrl.load()
        view.set_process_snapshot.reset_mock()

        ctrl._on_process_state_event(
            ProcessStateEvent(
                process_id=ProcessID.GLUE,
                state=ProcessState.RUNNING,
                previous=ProcessState.IDLE,
            )
        )

        model.refresh_process_snapshot.assert_called()
        view.set_process_snapshot.assert_called_once_with({"process_state": "running", "manual_mode": False, "dispensing": None})

    def test_diagnostics_event_pushes_snapshot_directly(self):
        ctrl, _, view, _ = self._make()
        ctrl.load()
        view.set_process_snapshot.reset_mock()

        ctrl._on_diagnostics({"process_state": "running", "machine": {"current_state": "STARTING"}})

        view.set_process_snapshot.assert_called_once_with(
            {"process_state": "running", "machine": {"current_state": "STARTING"}}
        )


if __name__ == "__main__":
    unittest.main()
