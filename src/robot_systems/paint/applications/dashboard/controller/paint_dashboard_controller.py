from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from src.applications.base.dashboard_camera_feed_mixin import DashboardCameraFeedMixin
from src.applications.base.dashboard_process_state_mixin import DashboardProcessStateMixin
from src.applications.base.broker_subscription_mixin import BrokerSubscriptionMixin
from src.applications.base.i_application_controller import IApplicationController
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.paint.applications.dashboard.model.paint_dashboard_model import (
    PaintDashboardModel,
)
from src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view import (
    PaintDashboardView,
)
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardCardState
from src.shared_contracts.events.robot_events import RobotTopics


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        self.finished.emit(self._fn())


class PaintDashboardController(
    IApplicationController,
    BrokerSubscriptionMixin,
    DashboardCameraFeedMixin,
    DashboardProcessStateMixin,
):
    def __init__(self, model: PaintDashboardModel, view: PaintDashboardView, broker: IMessagingService):
        BrokerSubscriptionMixin.__init__(self)
        self._model = model
        self._view = view
        self._broker = broker
        self._active = False
        self._workers: list[tuple[QThread, _Worker]] = []
        timer_parent = self._view if isinstance(self._view, QObject) else None
        self._status_timer = QTimer(timer_parent)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._refresh_dashboard_status)
        self._init_dashboard_camera_feed()
        self._init_dashboard_process_state()
        self._view.start_requested.connect(self._on_start)
        self._view.stop_requested.connect(self._on_stop)
        self._view.pause_requested.connect(self._on_pause)
        self._view.reset_requested.connect(self._on_reset)
        self._view.action_requested.connect(self._on_action)

    def load(self) -> None:
        self._active = True
        self._subscribe_dashboard_camera_feed()
        self._subscribe_dashboard_process_state()
        self._subscribe_dashboard_robot_state()
        self._view.apply_dashboard_state(self._model.load())
        if self._status_timer.parent() is not None or QThread.currentThread().eventDispatcher() is not None:
            self._status_timer.start()
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        self._status_timer.stop()
        self._unsubscribe_all()
        for thread, _worker in list(self._workers):
            thread.quit()
            thread.wait(1000)
        self._workers.clear()

    def _on_start(self) -> None:
        self._view.apply_dashboard_state(self._model.start())

    def _on_stop(self) -> None:
        self._view.apply_dashboard_state(self._model.stop_process())

    def _on_pause(self) -> None:
        self._view.apply_dashboard_state(self._model.toggle_pause())

    def _on_reset(self) -> None:
        self._view.apply_dashboard_state(self._model.reset_errors())

    def _subscribe_dashboard_robot_state(self) -> None:
        self._subscribe(RobotTopics.STATE, self._on_dashboard_robot_state_raw)

    def _on_dashboard_robot_state_raw(self, _event: object) -> None:
        if not self._active:
            return
        state = self._model.load()
        event_state = str(getattr(_event, "state", "") or "").lower()
        if event_state == "disconnected":
            extra = getattr(_event, "extra", {}) or {}
            last_error = extra.get("last_error") if isinstance(extra, dict) else None
            state.card_states[1] = DashboardCardState(
                "Robot Status",
                "DISCONNECTED",
                self._robot_connection_note(last_error),
            )
        elif event_state == "starting":
            extra = getattr(_event, "extra", {}) or {}
            startup = extra.get("startup") if isinstance(extra, dict) else {}
            state.card_states[1] = DashboardCardState(
                "Robot Status",
                "STARTING",
                self._robot_startup_note(startup if isinstance(startup, dict) else {}),
            )
        elif event_state in {"error", "fault"}:
            extra = getattr(_event, "extra", {}) or {}
            last_error = extra.get("last_error") if isinstance(extra, dict) else None
            state.card_states[1] = DashboardCardState(
                "Robot Status",
                "ERROR",
                self._robot_connection_note(last_error),
            )
        self._dashboard_process_bridge.state_ready.emit(state)

    @staticmethod
    def _robot_connection_note(last_error: object) -> str:
        message = str(last_error or "").strip()
        if not message:
            return "Robot bridge is disconnected"
        lowered = message.lower()
        if "connection refused" in lowered or "failed to establish a new connection" in lowered:
            return "ROS2 bridge is not reachable"
        if "timed out" in lowered or "timeout" in lowered:
            return "ROS2 bridge health check timed out"
        if "max retries exceeded" in lowered:
            return "ROS2 bridge is not responding"
        return "Robot bridge is disconnected"

    @staticmethod
    def _robot_startup_note(startup: dict) -> str:
        message = str(startup.get("message") or "").strip()
        if message:
            return message
        phase = str(startup.get("phase") or "").strip()
        if phase:
            return f"Runtime startup phase: {phase}"
        return "Robot runtime is starting"

    def _refresh_dashboard_status(self) -> None:
        if not self._active:
            return
        try:
            self._view.apply_dashboard_state(self._model.load())
        except RuntimeError:
            self.stop()

    def _on_action(self, action_id: str) -> None:
        if action_id != "debug_contour_transform":
            return
        self._view.set_action_enabled("debug_contour_transform", False)
        self._view.set_notes(["Capturing latest contour and building pixel-to-mm debug plot..."])
        self._run_background(
            self._model.capture_latest_contour_transform_debug,
            self._on_contour_transform_debug_finished,
        )

    def _run_background(self, fn, on_done) -> None:
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_finished_workers)
        self._workers.append((thread, worker))
        thread.start()

    def _cleanup_finished_workers(self) -> None:
        self._workers = [pair for pair in self._workers if pair[0].isRunning()]

    def _on_contour_transform_debug_finished(self, result) -> None:
        if not self._view_ok():
            return
        self._view.set_action_enabled("debug_contour_transform", True)
        self._view.apply_dashboard_state(self._model.load())
        if getattr(result, "success", False) and getattr(result, "image_path", None):
            self._view.show_debug_plot(
                "Latest Contour Pixel-to-MM Transform",
                result.image_path,
                result.message,
            )
        else:
            self._view.show_warning(
                "Latest Contour Pixel-to-MM Transform",
                getattr(result, "message", "Failed to create contour transform plot."),
            )

    def _view_ok(self) -> bool:
        if not self._active:
            return False
        try:
            _ = self._view.isVisible()
            return True
        except RuntimeError:
            return False
