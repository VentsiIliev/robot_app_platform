from __future__ import annotations

import logging
import time
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.pick_target.model.pick_target_model import PickTargetModel
from src.applications.pick_target.view.pick_target_view import PickTargetView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics

_logger = logging.getLogger(__name__)


class _Bridge(QObject):
    """Routes broker callbacks (background thread) safely to the main thread."""
    camera_frame = pyqtSignal(object)


class _MoveWorker(QObject):
    """Iterates captured robot coords and moves to each one."""
    log_message = pyqtSignal(str)
    finished    = pyqtSignal()

    def __init__(
        self,
        model: PickTargetModel,
        coords: List[Tuple[float, float, float, float, float, float]],
        delay: float = 0.0,
        use_base_z: bool = False,
        use_live_height: bool = False,
    ):
        super().__init__()
        self._model          = model
        self._coords         = coords
        self._delay          = delay
        self._use_base_z     = use_base_z
        self._use_live_height = use_live_height
        self._stop           = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        if self._use_live_height:
            tag = "[LIVE]"
        elif self._use_base_z:
            tag = "[BASE]"
        else:
            tag = "[MOVE]"
        try:
            for i, (x, y, z, rx, ry, rz) in enumerate(self._coords):
                if self._stop:
                    self.log_message.emit("[STOP] Aborted by user.")
                    break
                self.log_message.emit(
                    f"{tag} {i + 1}/{len(self._coords)}: robot=({x:.1f}, {y:.1f}, {z:.1f})"
                )
                if self._use_live_height:
                    ok = self._model.move_to_with_live_height(x, y, rx, ry, rz)
                elif self._use_base_z:
                    ok = self._model.move_to_base(x, y, rx, ry, rz)
                else:
                    ok = self._model.move_to(x, y, z, rx, ry, rz)
                status = "[OK]  " if ok else "[FAIL]"
                self.log_message.emit(f"{status} ({x:.1f}, {y:.1f}, {z:.1f})")
                if self._delay > 0 and i < len(self._coords) - 1 and not self._stop:
                    self.log_message.emit(f"[WAIT] {self._delay:.1f}s...")
                    time.sleep(self._delay)
            else:
                self.log_message.emit("[DONE] Sequence complete.")
        except Exception as exc:
            _logger.exception("MoveWorker error")
            self.log_message.emit(f"[ERROR] {exc}")
        finally:
            self.finished.emit()


class _CalibWorker(QObject):
    """Moves robot to the mode-appropriate start position."""
    log_message = pyqtSignal(str)
    finished    = pyqtSignal()

    def __init__(self, model: PickTargetModel):
        super().__init__()
        self._model = model

    def run(self) -> None:
        try:
            ok = self._model.move_to_calibration_position()
            self.log_message.emit("[START] " + ("Reached start position." if ok else "Move failed."))
        except Exception as exc:
            self.log_message.emit(f"[ERROR] Start move failed: {exc}")
        finally:
            self.finished.emit()


class _TrajectoryWorker(QObject):
    """Executes a contour trajectory on the robot."""
    log_message = pyqtSignal(str)
    finished    = pyqtSignal()

    def __init__(self, model: PickTargetModel, contour_robot_pts, z: float, vel: float, acc: float):
        super().__init__()
        self._model = model
        self._pts   = contour_robot_pts
        self._z     = z
        self._vel   = vel
        self._acc   = acc

    def run(self) -> None:
        try:
            ok, msg = self._model.execute_contour_trajectory(self._pts, self._z, self._vel, self._acc)
            self.log_message.emit(f"[TRAJ] {'✓' if ok else '✗'} {msg}")
        except Exception as exc:
            self.log_message.emit(f"[ERROR] Trajectory failed: {exc}")
        finally:
            self.finished.emit()


class PickTargetController(IApplicationController):

    def __init__(
        self,
        model:       PickTargetModel,
        view:        PickTargetView,
        messaging:   Optional[IMessagingService] = None,
    ):
        self._model   = model
        self._view    = view
        self._broker  = messaging
        self._bridge  = _Bridge()
        self._subs:   List[Tuple[str, Callable]] = []
        self._active: List[Tuple[QThread, QObject]] = []  # keeps workers alive
        self._current_worker: Optional[QObject] = None
        self._alive   = False
        self._captured_coords:          List[Tuple[float, float, float, float, float, float]] = []
        self._captured_trajectory:      List = []          # robot-space contour arrays
        self._two_step_mode:             bool = False
        self._measure_height_mode:       bool = False
        self._pending_correction_coords: List[Tuple[float, float, float, float, float, float]] = []

        self._bridge.camera_frame.connect(self._on_camera_frame)

        self._view.capture_requested.connect(self._on_capture)
        self._view.move_requested.connect(self._on_move)
        self._view.calibration_pos_requested.connect(self._on_go_to_calibration)
        self._view.target_changed.connect(self._model.set_target)
        self._view.pickup_plane_toggled.connect(self._model.set_use_pickup_plane)
        self._view.pickup_plane_rz_changed.connect(self._model.set_pickup_plane_rz)
        self._view.execute_trajectory_requested.connect(self._on_execute_trajectory)
        self._view.z_mode_toggled.connect(self._on_z_mode_toggled)
        self._view.apply_correction_requested.connect(self._on_apply_correction)
        self._view.measure_height_toggled.connect(self._on_measure_height_toggled)
        self._view.destroyed.connect(self.stop)
        self._model.set_target(self._view.get_target())
        self._model.set_pickup_plane_rz(self._view.get_pickup_plane_rz())

    def load(self) -> None:
        self._alive = True
        if self._broker:
            self._subscribe()

    def stop(self) -> None:
        self._alive = False
        if self._current_worker and hasattr(self._current_worker, "request_stop"):
            self._current_worker.request_stop()
        for thread, _ in self._active:
            thread.quit()
            thread.wait(3000)
        self._active.clear()
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                pass
        self._subs.clear()

    # ── Broker subscriptions ──────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_camera_frame_raw)

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    def _on_camera_frame_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    # ── Main-thread slots ─────────────────────────────────────────────

    def _on_camera_frame(self, frame) -> None:
        if frame is not None and self._alive:
            try:
                self._view.update_camera_frame(frame)
            except Exception:
                pass

    def _on_log_message(self, text: str) -> None:
        if self._alive:
            self._view.append_log(text)

    def _on_move_done(self) -> None:
        self._view.set_busy(False)
        self._view.set_move_enabled(bool(self._captured_coords))
        self._view.set_trajectory_enabled(bool(self._captured_trajectory))
        self._view.set_correction_available(bool(self._pending_correction_coords))
        self._current_worker = None

    def _on_measure_height_toggled(self, enabled: bool) -> None:
        self._measure_height_mode = enabled

    def _on_z_mode_toggled(self, two_step: bool) -> None:
        self._two_step_mode = two_step
        if not two_step:
            self._pending_correction_coords = []
            self._view.set_correction_available(False)

    def _on_calib_done(self) -> None:
        self._view.set_busy(False)
        self._view.set_move_enabled(bool(self._captured_coords))
        self._view.set_trajectory_enabled(bool(self._captured_trajectory))
        self._view.set_correction_available(bool(self._pending_correction_coords))
        self._current_worker = None

    def _on_trajectory_done(self) -> None:
        self._view.set_busy(False)
        self._view.set_move_enabled(bool(self._captured_coords))
        self._view.set_trajectory_enabled(bool(self._captured_trajectory))
        self._view.set_correction_available(bool(self._pending_correction_coords))
        self._current_worker = None

    def _on_thread_finished(self) -> None:
        self._active = [(t, w) for t, w in self._active if t.isRunning()]

    # ── Capture (main thread) ─────────────────────────────────────────

    def _on_capture(self) -> None:
        try:
            frame, pixel_centroids, robot_coords = self._model.capture()
        except Exception as exc:
            self._view.append_log(f"[ERROR] Capture failed: {exc}")
            return

        self._captured_coords = robot_coords

        # Also capture full contour trajectories (all contour points in robot space)
        try:
            self._captured_trajectory = self._model.capture_contour_trajectory()
        except Exception as exc:
            self._captured_trajectory = []
            self._view.append_log(f"[WARN] Trajectory capture failed: {exc}")

        if frame is not None and len(frame.shape) == 3:
            self._view.update_captured_frame(self._annotate(frame, pixel_centroids))

        n = len(robot_coords)
        self._view.append_log(f"[CAPTURE] {n} target(s) found.")
        for i, (x, y, z, rx, ry, rz) in enumerate(robot_coords):
            self._view.append_log(f"  [{i + 1}] robot=({x:.1f}, {y:.1f}, z={z:.1f}, rz={rz:.1f})")

        traj_pts = sum(len(c) for c in self._captured_trajectory)
        if self._captured_trajectory:
            self._view.append_log(
                f"[TRAJ]   {len(self._captured_trajectory)} contour(s), {traj_pts} waypoints ready."
            )

        self._view.set_move_enabled(n > 0)
        self._view.set_trajectory_enabled(bool(self._captured_trajectory))
        if n == 0:
            self._view.append_log("[WARN] No contours detected — check camera and lighting.")

    # ── Execute Trajectory ────────────────────────────────────────────

    def _on_execute_trajectory(self) -> None:
        if not self._captured_trajectory:
            self._view.append_log("[WARN] No trajectory captured — press Capture first.")
            return
        if self._current_worker is not None:
            return
        self._view.set_busy(True)
        total = sum(len(c) for c in self._captured_trajectory)
        self._view.append_log(
            f"[TRAJ] Executing {len(self._captured_trajectory)} contour(s), {total} waypoints..."
        )
        worker = _TrajectoryWorker(
            self._model,
            list(self._captured_trajectory),
            z=self._view.get_trajectory_z(),
            vel=self._view.get_trajectory_vel(),
            acc=self._view.get_trajectory_acc(),
        )
        self._launch(worker, on_done=self._on_trajectory_done)

    # ── Move ──────────────────────────────────────────────────────────

    def _on_move(self) -> None:
        if not self._captured_coords:
            self._view.append_log("[WARN] No captured targets — press Capture first.")
            return
        if self._current_worker is not None:
            return
        self._view.set_busy(True)
        coords = list(self._captured_coords)
        delay = self._view.get_move_delay()
        if self._measure_height_mode:
            self._pending_correction_coords = []
            self._view.append_log(
                f"[LIVE] Moving to {len(coords)} target(s) with live height measurement..."
            )
            worker = _MoveWorker(self._model, coords, delay, use_live_height=True)
        elif self._two_step_mode:
            self._pending_correction_coords = coords
            self._view.set_correction_available(False)
            self._view.append_log(
                f"[BASE] Moving to {len(coords)} target(s) at base Z (no correction)..."
            )
            worker = _MoveWorker(self._model, coords, delay, use_base_z=True)
        else:
            self._pending_correction_coords = []
            self._view.append_log(
                f"[MOVE] Starting sequence for {len(coords)} target(s)..."
            )
            worker = _MoveWorker(self._model, coords, delay)
        self._launch(worker, on_done=self._on_move_done)

    def _on_apply_correction(self) -> None:
        if not self._pending_correction_coords:
            self._view.append_log("[WARN] No pending targets — press Move first (two-step mode).")
            return
        if self._current_worker is not None:
            return
        self._view.set_busy(True)
        coords = list(self._pending_correction_coords)
        self._view.append_log(
            f"[CORR] Applying height correction for {len(coords)} target(s)..."
        )
        worker = _MoveWorker(self._model, coords, self._view.get_move_delay(), use_base_z=False)
        self._launch(worker, on_done=self._on_move_done)

    # ── Start position ────────────────────────────────────────────────

    def _on_go_to_calibration(self) -> None:
        if self._current_worker is not None:
            return
        self._view.set_busy(True)
        self._view.append_log("[MOVE] Moving to start position...")
        worker = _CalibWorker(self._model)
        self._launch(worker, on_done=self._on_calib_done)

    # ── Thread helper (mirrors ModbusSettingsController pattern) ──────

    def _launch(self, worker: QObject, on_done: Callable) -> None:
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log_message.connect(self._on_log_message)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        self._active.append((thread, worker))
        self._current_worker = worker
        thread.start()

    # ── Annotation ────────────────────────────────────────────────────

    @staticmethod
    def _annotate(frame: np.ndarray, pixel_centroids: List[Tuple[float, float]]) -> np.ndarray:
        out = frame.copy()
        for px, py in pixel_centroids:
            x, y = int(round(px)), int(round(py))
            cv2.line(out, (x - 14, y), (x + 14, y), (0, 255, 0), 1)
            cv2.line(out, (x, y - 14), (x, y + 14), (0, 255, 0), 1)
        return out
