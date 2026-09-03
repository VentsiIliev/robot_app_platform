from __future__ import annotations

import logging
from functools import partial

from PyQt6.QtCore import QTimer

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.robot_systems.twin_robot.applications.choreography_setup.model.choreography_setup_model import (
    ChoreographySetupModel,
)
from src.robot_systems.twin_robot.applications.choreography_setup.view.choreography_setup_view import (
    ChoreographySetupView,
)


class ChoreographySetupController(IApplicationController, BackgroundWorker):
    def __init__(self, model: ChoreographySetupModel, view: ChoreographySetupView):
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)
        self._active = False
        self._state_poll_pending = False
        self._motion_pending = {"robot1": False, "robot2": False}
        self._state_timer = QTimer()
        self._state_timer.setInterval(250)
        self._state_timer.timeout.connect(self._poll_robot_states)

    def load(self) -> None:
        self._active = True
        self._connect_signals()
        try:
            library = self._model.load()
            if library:
                definition = self._model.load_choreography(str(library[0].get("id", "")))
                self._render(definition, message=f"Loaded {definition.get('name', '')}")
            else:
                definition = self._model.new_choreography(
                    "new_choreography",
                    "New Choreography",
                )
                self._render(
                    definition,
                    message="Jog both robots to the start pose, then press Capture Both.",
                )
        except Exception as exc:
            self._logger.exception("Failed to initialize choreography setup")
            self._view.set_message(str(exc))
        self._state_timer.start()
        self._poll_robot_states()

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        self._state_timer.stop()
        self._stop_threads()
        self._disconnect_signals()

    def _connect_signals(self) -> None:
        self._view.new_requested.connect(self._on_new_requested)
        self._view.load_requested.connect(self._on_load_requested)
        self._view.save_requested.connect(self._on_save_requested)
        self._view.add_step_requested.connect(self._on_add_step_requested)
        self._view.delete_step_requested.connect(self._on_delete_step_requested)
        self._view.capture_robot_requested.connect(self._on_capture_robot_requested)
        self._view.capture_both_requested.connect(self._on_capture_both_requested)
        self._view.robot_jog_requested.connect(self._on_robot_jog_requested)
        self._view.robot_jog_stopped.connect(self._on_robot_jog_stopped)
        self._view.robot_joint_jog_requested.connect(self._on_robot_joint_jog_requested)

    def _disconnect_signals(self) -> None:
        try:
            self._view.new_requested.disconnect(self._on_new_requested)
            self._view.load_requested.disconnect(self._on_load_requested)
            self._view.save_requested.disconnect(self._on_save_requested)
            self._view.add_step_requested.disconnect(self._on_add_step_requested)
            self._view.delete_step_requested.disconnect(self._on_delete_step_requested)
            self._view.capture_robot_requested.disconnect(self._on_capture_robot_requested)
            self._view.capture_both_requested.disconnect(self._on_capture_both_requested)
            self._view.robot_jog_requested.disconnect(self._on_robot_jog_requested)
            self._view.robot_jog_stopped.disconnect(self._on_robot_jog_stopped)
            self._view.robot_joint_jog_requested.disconnect(self._on_robot_joint_jog_requested)
        except RuntimeError:
            pass

    def _apply_editor(self) -> None:
        snapshot = self._view.editor_snapshot()
        self._model.apply_editor(
            name=str(snapshot.get("name", "")),
            loop_count=int(snapshot.get("loop_count", 1)),
            steps=list(snapshot.get("steps", [])),
        )

    def _render(
        self,
        definition=None,
        *,
        selected_row: int | None = None,
        message: str = "",
    ) -> None:
        if not self._active:
            return
        payload = definition if isinstance(definition, dict) else self._model.current()
        row = self._view.selected_row() if selected_row is None else int(selected_row)
        self._view.set_definition(payload, selected_row=row)
        self._view.set_library(
            self._model.load(),
            selected_id=str(payload.get("id", "")),
        )
        if message:
            self._view.set_message(message)

    def _on_new_requested(self, choreography_id: str, name: str) -> None:
        if not self._active:
            return
        if not choreography_id.strip() or not name.strip():
            self._view.set_message("ID and name are required")
            return
        try:
            definition = self._model.new_choreography(choreography_id, name)
            self._render(definition, selected_row=0, message="New choreography created")
        except Exception as exc:
            self._view.set_message(str(exc))

    def _on_load_requested(self, choreography_id: str) -> None:
        if not self._active:
            return
        try:
            definition = self._model.load_choreography(choreography_id)
            self._render(
                definition,
                selected_row=0,
                message=f"Loaded {definition.get('name', choreography_id)}",
            )
        except Exception as exc:
            self._view.set_message(str(exc))

    def _on_save_requested(self) -> None:
        if not self._active:
            return
        try:
            self._apply_editor()
        except Exception as exc:
            self._view.set_message(str(exc))
            return
        self._run_in_thread(
            fn=self._model.save,
            on_done=self._on_save_done,
            on_error=self._on_background_error,
        )

    def _on_save_done(self, result) -> None:
        if not self._active:
            return
        result = result if isinstance(result, dict) else {}
        warnings = list(result.get("warnings", []) or [])
        message = "Saved"
        if warnings:
            message += " with validation warnings: " + "; ".join(str(item) for item in warnings)
        self._render(message=message)

    def _on_add_step_requested(self) -> None:
        if not self._active:
            return
        try:
            self._apply_editor()
            definition = self._model.add_step()
            row = max(0, len(definition.get("steps", [])) - 1)
            self._render(definition, selected_row=row)
        except Exception as exc:
            self._view.set_message(str(exc))

    def _on_delete_step_requested(self, row: int) -> None:
        if not self._active:
            return
        try:
            self._apply_editor()
            definition = self._model.delete_step(row)
            self._render(definition, selected_row=max(0, row - 1))
        except Exception as exc:
            self._view.set_message(str(exc))

    def _on_capture_robot_requested(self, robot_name: str, row: int) -> None:
        if not self._active:
            return
        try:
            self._apply_editor()
        except Exception as exc:
            self._view.set_message(str(exc))
            return
        self._run_in_thread(
            fn=partial(self._model.capture_robot, row, robot_name),
            on_done=partial(self._on_capture_done, row, robot_name),
            on_error=self._on_background_error,
        )

    def _on_capture_both_requested(self, row: int) -> None:
        if not self._active:
            return
        try:
            self._apply_editor()
        except Exception as exc:
            self._view.set_message(str(exc))
            return
        self._run_in_thread(
            fn=partial(self._model.capture_both, row),
            on_done=partial(self._on_capture_done, row, "both robots"),
            on_error=self._on_background_error,
        )

    def _on_capture_done(self, row: int, label: str, definition) -> None:
        if not self._active:
            return
        self._render(
            definition,
            selected_row=row,
            message=f"Captured {label} into step {row + 1}",
        )

    def _on_robot_jog_requested(
        self,
        robot_name: str,
        command: str,
        axis: str,
        direction: str,
        step: float,
    ) -> None:
        if not self._active or self._motion_pending.get(robot_name, False):
            return
        self._motion_pending[robot_name] = True
        self._run_in_thread(
            fn=partial(self._model.jog, robot_name, command, axis, direction, step),
            on_done=partial(self._on_motion_done, robot_name),
            on_error=partial(self._on_motion_error, robot_name),
        )

    def _on_robot_joint_jog_requested(
        self,
        robot_name: str,
        command: str,
        joint: str,
        direction: str,
        step: float,
    ) -> None:
        if not self._active or self._motion_pending.get(robot_name, False):
            return
        self._motion_pending[robot_name] = True
        self._run_in_thread(
            fn=partial(self._model.joint_jog, robot_name, command, joint, direction, step),
            on_done=partial(self._on_motion_done, robot_name),
            on_error=partial(self._on_motion_error, robot_name),
        )

    def _on_robot_jog_stopped(self, robot_name: str) -> None:
        if not self._active:
            return
        self._run_in_thread(
            fn=partial(self._model.stop_servo_jog, robot_name),
            on_done=self._ignore_result,
            on_error=self._on_background_error,
        )

    def _on_motion_done(self, robot_name: str, result) -> None:
        self._motion_pending[robot_name] = False
        try:
            code = int(result)
        except (TypeError, ValueError):
            code = -1
        if code != 0 and self._active:
            self._view.set_message(f"{robot_name} jog returned {code}")

    def _on_motion_error(self, robot_name: str, message: str) -> None:
        self._motion_pending[robot_name] = False
        self._on_background_error(message)

    def _poll_robot_states(self) -> None:
        if not self._active or self._state_poll_pending:
            return
        self._state_poll_pending = True
        self._run_in_thread(
            fn=self._model.robot_states,
            on_done=self._on_robot_states,
            on_error=self._on_state_poll_error,
        )

    def _on_robot_states(self, states) -> None:
        self._state_poll_pending = False
        if not self._active or not isinstance(states, dict):
            return
        for robot_name in ("robot1", "robot2"):
            state = states.get(robot_name, {}) or {}
            self._view.set_robot_state(
                robot_name,
                list(state.get("pose", []) or []),
                list(state.get("joints", []) or []),
            )

    def _on_state_poll_error(self, _message: str) -> None:
        self._state_poll_pending = False
        if not self._active:
            return
        self._view.set_robot_state("robot1", [], [])
        self._view.set_robot_state("robot2", [], [])

    def _on_background_error(self, message: str) -> None:
        if self._active:
            self._logger.error("Choreography setup operation failed: %s", message)
            self._view.set_message(message)

    @staticmethod
    def _ignore_result(_result) -> None:
        pass
