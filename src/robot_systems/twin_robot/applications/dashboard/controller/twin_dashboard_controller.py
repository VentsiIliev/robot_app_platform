from __future__ import annotations

import logging
from functools import partial

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.robot_systems.twin_robot.applications.dashboard.model.twin_dashboard_model import (
    TwinDashboardModel,
)
from src.robot_systems.twin_robot.applications.dashboard.view.twin_dashboard_view import (
    TwinDashboardView,
)


class TwinDashboardController(IApplicationController, BackgroundWorker):
    def __init__(self, model: TwinDashboardModel, view: TwinDashboardView):
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)
        self._active = False

    def load(self) -> None:
        self._active = True
        self._view.choreography_selected.connect(self._on_choreography_selected)
        self._view.plan_requested.connect(self._on_plan_requested)
        self._view.start_requested.connect(self._on_start_requested)
        self._view.stop_requested.connect(self._on_stop_requested)

        try:
            choreographies = self._model.load()
            self._view.set_choreographies(choreographies)
            self._view.select_first_choreography()
            if not choreographies:
                self._view.set_message("No saved choreographies. Create one in Choreography Setup.")
        except Exception as exc:
            self._logger.exception("Failed to load choreographies")
            self._view.set_message(str(exc))

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        self._stop_threads()
        try:
            self._view.choreography_selected.disconnect(self._on_choreography_selected)
            self._view.plan_requested.disconnect(self._on_plan_requested)
            self._view.start_requested.disconnect(self._on_start_requested)
            self._view.stop_requested.disconnect(self._on_stop_requested)
        except RuntimeError:
            pass

    def _on_choreography_selected(self, choreography_id: str) -> None:
        if not self._active:
            return
        try:
            selected = self._model.select(choreography_id)
            self._view.set_loop_count(int(selected.get("loop_count", 1)))
            self._view.set_plan_status(False, False, "Selected. Press PLAN BOTH.")
        except Exception as exc:
            self._view.set_plan_status(False, False, str(exc))

    def _on_plan_requested(self) -> None:
        if not self._active:
            return
        self._view.set_busy(True, "Planning Robot 1 and Robot 2...")
        self._run_in_thread(
            fn=self._model.plan,
            on_done=self._on_plan_done,
            on_error=self._on_background_error,
        )

    def _on_plan_done(self, result) -> None:
        if not self._active:
            return
        result = result if isinstance(result, dict) else {}
        robot1_ready = bool(result.get("robot1_ready", False))
        robot2_ready = bool(result.get("robot2_ready", False))
        message = str(
            result.get("error", "")
            or ("Both trajectories prepared" if robot1_ready and robot2_ready else "Planning failed")
        )
        self._view.set_plan_status(robot1_ready, robot2_ready, message)

    def _on_start_requested(self, loop_count: int) -> None:
        if not self._active:
            return
        self._view.set_busy(True, "Moving to exact start anchors and starting synchronized execution...")
        self._run_in_thread(
            fn=partial(self._model.start, loop_count),
            on_done=self._on_start_done,
            on_error=self._on_background_error,
        )

    def _on_start_done(self, result) -> None:
        if not self._active:
            return
        result = result if isinstance(result, dict) else {}
        message = str(
            result.get("error", "")
            or ("Choreography execution completed" if result.get("success") else "Start failed")
        )
        status = self._model.prepared_status()
        self._view.set_plan_status(
            bool(status.get("robot1_ready", False)),
            bool(status.get("robot2_ready", False)),
            message,
        )

    def _on_stop_requested(self) -> None:
        if not self._active:
            return
        self._run_in_thread(
            fn=self._model.stop_motion,
            on_done=self._on_stop_done,
            on_error=self._on_background_error,
        )

    def _on_stop_done(self, result) -> None:
        if not self._active:
            return
        result = result if isinstance(result, dict) else {}
        self._view.set_message(str(result.get("error", "") or "Stop requested for both robots"))

    def _on_background_error(self, message: str) -> None:
        if not self._active:
            return
        self._logger.error("Twin dashboard background operation failed: %s", message)
        self._view.set_plan_status(False, False, message)
