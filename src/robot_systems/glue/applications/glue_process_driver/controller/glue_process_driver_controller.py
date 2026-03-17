import logging

from PyQt6.QtCore import QObject, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.process_ids import ProcessID
from src.robot_systems.glue.applications.glue_process_driver.model.glue_process_driver_model import (
    GlueProcessDriverModel,
)
from src.robot_systems.glue.applications.glue_process_driver.view.glue_process_driver_view import (
    GlueProcessDriverView,
)
from src.shared_contracts.events.glue_process_events import GlueProcessTopics
from src.shared_contracts.events.process_events import ProcessTopics


class _DriverBridge(QObject):
    process_snapshot_updated = pyqtSignal(object)


class GlueProcessDriverController(IApplicationController):
    def __init__(self, model: GlueProcessDriverModel, view: GlueProcessDriverView, broker: IMessagingService | None = None):
        self._model = model
        self._view = view
        self._broker = broker
        self._subs = []
        self._logger = logging.getLogger(self.__class__.__name__)
        self._bridge = _DriverBridge()

        view.capture_match_requested.connect(self._on_capture_and_match)
        view.build_job_requested.connect(self._on_build_job)
        view.load_job_requested.connect(self._on_load_job)
        view.manual_mode_toggled.connect(self._on_manual_mode_toggled)
        view.step_requested.connect(self._on_step)
        view.start_requested.connect(self._on_start)
        view.pause_requested.connect(self._on_pause)
        view.resume_requested.connect(self._on_resume)
        view.stop_requested.connect(self._on_stop)
        view.reset_errors_requested.connect(self._on_reset_errors)
        view.refresh_requested.connect(self._on_refresh)
        view.destroyed.connect(self.stop)
        self._bridge.process_snapshot_updated.connect(self._view.set_process_snapshot)

    def load(self) -> None:
        snapshot = self._model.load()
        self._view.set_process_snapshot(snapshot)
        self._view.set_manual_mode_enabled(bool(snapshot.get("manual_mode")))
        self._subscribe()

    def stop(self) -> None:
        for topic, callback in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, callback)
            except Exception:
                pass
        self._subs.clear()

    def _on_capture_and_match(self) -> None:
        self._model.capture_and_match()
        self._view.set_match_summary(self._model.get_match_summary())
        self._view.set_matched_workpieces(self._model.get_latest_matched_workpieces())

    def _on_build_job(self) -> None:
        self._model.build_job(selected_indexes=self._view.get_selected_match_indexes())
        self._view.set_job_summary(self._model.get_latest_job_summary())

    def _on_load_job(self, spray_on: bool) -> None:
        self._model.load_job(spray_on=spray_on)

    def _on_manual_mode_toggled(self, enabled: bool) -> None:
        self._model.set_manual_mode(enabled)
        self._view.set_process_snapshot(self._model.get_process_snapshot())

    def _on_step(self) -> None:
        self._view.set_process_snapshot(self._model.step_once())

    def _on_start(self) -> None:
        self._model.start()

    def _on_pause(self) -> None:
        self._model.pause()

    def _on_resume(self) -> None:
        self._model.resume()

    def _on_stop(self) -> None:
        self._model.stop()

    def _on_reset_errors(self) -> None:
        self._model.reset_errors()

    def _on_refresh(self) -> None:
        self._view.set_process_snapshot(self._model.refresh_process_snapshot())

    def _subscribe(self) -> None:
        if self._broker is None:
            return
        self._sub(ProcessTopics.state(ProcessID.GLUE), self._on_process_state_event)
        self._sub(GlueProcessTopics.DIAGNOSTICS, self._on_diagnostics)

    def _sub(self, topic: str, callback) -> None:
        if self._broker is None:
            return
        self._broker.subscribe(topic, callback)
        self._subs.append((topic, callback))

    def _on_process_state_event(self, _event) -> None:
        self._bridge.process_snapshot_updated.emit(self._model.refresh_process_snapshot())

    def _on_diagnostics(self, snapshot: dict) -> None:
        self._bridge.process_snapshot_updated.emit(snapshot)
