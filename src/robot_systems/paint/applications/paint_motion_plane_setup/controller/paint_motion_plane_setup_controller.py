from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.robot_systems.paint.applications.paint_motion_plane_setup.domain.plane_inference import Pose6D
from src.robot_systems.paint.applications.paint_motion_plane_setup.model.paint_motion_plane_setup_model import (
    PaintMotionPlaneSetupModel,
)
from src.robot_systems.paint.applications.paint_motion_plane_setup.view.paint_motion_plane_setup_view import (
    PaintMotionPlaneSetupView,
)

_logger = logging.getLogger(__name__)


class _Worker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception as exc:
            _logger.exception("Paint motion plane setup worker failed")
            self.failed.emit(str(exc))


class PaintMotionPlaneSetupController(IApplicationController):
    def __init__(self, model: PaintMotionPlaneSetupModel, view: PaintMotionPlaneSetupView) -> None:
        self._model = model
        self._view = view
        self._active: list[tuple[QThread, _Worker]] = []
        self._pending_capture: str | None = None

        view.move_to_paint_pose_requested.connect(self._on_move_to_paint_pose)
        view.capture_reference_requested.connect(self._on_capture_reference)
        view.capture_translation_requested.connect(self._on_capture_translation)
        view.capture_rotation_requested.connect(self._on_capture_rotation)
        view.fixed_axis_selected.connect(self._on_fixed_axis_selected)

    def load(self) -> None:
        try:
            self._model.load()
            self._view.set_paint_pose(self._model.paint_pose)
            self._view.set_result(None)
        except Exception as exc:
            self._view.show_error("Paint setup unavailable", str(exc))

    def stop(self) -> None:
        for thread, worker in self._active:
            try:
                worker.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            try:
                worker.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            thread.quit()
            thread.wait(1000)
        self._active.clear()
        try:
            self._view.move_to_paint_pose_requested.disconnect(self._on_move_to_paint_pose)
            self._view.capture_reference_requested.disconnect(self._on_capture_reference)
            self._view.capture_translation_requested.disconnect(self._on_capture_translation)
            self._view.capture_rotation_requested.disconnect(self._on_capture_rotation)
            self._view.fixed_axis_selected.disconnect(self._on_fixed_axis_selected)
        except (RuntimeError, TypeError):
            pass

    def _on_move_to_paint_pose(self) -> None:
        if not self._view.confirm_move_to_paint_pose():
            return
        self._view.set_busy(True, "Moving to paint position...")
        self._run_worker(self._model.move_to_paint_pose, self._on_move_finished)

    def _on_capture_reference(self) -> None:
        self._capture_current("reference")

    def _on_capture_translation(self) -> None:
        self._capture_current("translation")

    def _on_capture_rotation(self) -> None:
        self._capture_current("rotation")

    def _on_fixed_axis_selected(self, axis: str) -> None:
        self._model.fixed_axis = axis
        self._refresh_result()

    def _capture_current(self, slot: str) -> None:
        self._pending_capture = slot
        self._view.set_busy(True, f"Capturing {slot} pose...")
        self._run_worker(self._model.get_current_pose, self._on_capture_finished)

    def _on_move_finished(self, ok_obj) -> None:
        self._view.set_busy(False, "Ready")
        ok = bool(ok_obj)
        self._view.set_paint_move_complete(ok)
        if not ok:
            self._view.show_error("Move failed", "The robot did not report a successful move to the paint position.")

    def _on_capture_finished(self, pose_obj) -> None:
        self._view.set_busy(False, "Ready")
        slot = self._pending_capture
        self._pending_capture = None
        if not isinstance(pose_obj, Pose6D) or slot is None:
            return
        if slot == "reference":
            self._model.reference_pose = pose_obj
            self._view.set_reference_pose(pose_obj)
        elif slot == "translation":
            self._model.translation_pose = pose_obj
            self._view.set_translation_pose(pose_obj)
        elif slot == "rotation":
            self._model.rotation_pose = pose_obj
            self._view.set_rotation_pose(pose_obj)
        self._view.set_current_pose(pose_obj)
        self._refresh_result()

    def _on_worker_failed(self, message: str) -> None:
        self._view.set_busy(False, "Ready")
        self._pending_capture = None
        self._view.show_error("Operation failed", message)

    def _refresh_result(self) -> None:
        try:
            inference = self._model.update_inference()
        except Exception as exc:
            self._view.set_result(None)
            self._view.show_error("Inference failed", str(exc))
            return
        if inference is None:
            self._view.set_result(None)
            return
        self._view.set_result(inference.as_runtime_config(), inference.warnings)

    def _run_worker(self, fn, on_finished) -> None:
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(self._on_worker_failed)
        worker.failed.connect(thread.quit)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._active.append((thread, worker))
        thread.start()

    def _on_thread_finished(self) -> None:
        self._active = [
            (thread, worker)
            for thread, worker in self._active
            if thread.isRunning()
        ]
