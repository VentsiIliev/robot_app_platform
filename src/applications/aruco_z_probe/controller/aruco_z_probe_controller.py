from __future__ import annotations

import logging
import threading
from typing import Callable, List, Optional, Tuple

import numpy as np

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.aruco_z_probe.model.aruco_z_probe_model import ArucoZProbeModel
from src.applications.aruco_z_probe.service.i_aruco_z_probe_service import ArucoZSample
from src.applications.aruco_z_probe.view.aruco_z_probe_view import ArucoZProbeView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics

_logger = logging.getLogger(__name__)


class _Bridge(QObject):
    camera_frame  = pyqtSignal(object)
    log_message   = pyqtSignal(str)
    sweep_done    = pyqtSignal(bool, str, object)   # success, msg, results
    verify_done   = pyqtSignal(bool, str, object)   # success, msg, results


class _CalibWorker(QObject):
    log_message = pyqtSignal(str)
    finished    = pyqtSignal()

    def __init__(self, model: ArucoZProbeModel):
        super().__init__()
        self._model = model

    def run(self) -> None:
        try:
            ok = self._model.move_to_calibration_position()
            self.log_message.emit(
                "[CALIB] " + ("Reached calibration position." if ok else "Move failed.")
            )
        except Exception as exc:
            _logger.exception("CalibWorker error")
            self.log_message.emit(f"[ERROR] Calibration move failed: {exc}")
        finally:
            self.finished.emit()


class _SweepWorker(QObject):
    sweep_done  = pyqtSignal(bool, str, object)
    finished    = pyqtSignal()

    def __init__(
        self,
        model: ArucoZProbeModel,
        marker_id: int,
        min_z: float,
        sample_count: int,
        detection_attempts: int,
        bridge: _Bridge,
        stabilization_delay: float = 0.3,
    ):
        super().__init__()
        self._model               = model
        self._marker_id           = marker_id
        self._min_z               = min_z
        self._sample_count        = sample_count
        self._detection_attempts  = detection_attempts
        self._bridge              = bridge
        self._stabilization_delay = stabilization_delay
        self._stop_event          = threading.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            success, message, samples = self._model.run_sweep(
                marker_id=self._marker_id,
                min_z=self._min_z,
                sample_count=self._sample_count,
                detection_attempts=self._detection_attempts,
                stop_event=self._stop_event,
                progress_cb=self._on_progress,
                log_cb=self._bridge.log_message.emit,
                stabilization_delay=self._stabilization_delay,
            )
            self.sweep_done.emit(success, message, samples)
        except Exception as exc:
            _logger.exception("SweepWorker error")
            self.sweep_done.emit(False, f"Sweep error: {exc}", [])
        finally:
            self.finished.emit()

    def _on_progress(
        self,
        step_index: int,
        total_steps: int,
        z_mm: float,
        dx_px: Optional[float],
        dy_px: Optional[float],
    ) -> None:
        if dx_px is not None and dy_px is not None:
            msg = (
                f"[STEP {step_index:3d}/{total_steps}]"
                f"  z={z_mm:7.2f} mm"
                f"  dx={dx_px:+.2f} px"
                f"  dy={dy_px:+.2f} px"
            )
        else:
            msg = (
                f"[STEP {step_index:3d}/{total_steps}]"
                f"  z={z_mm:7.2f} mm  (marker not detected)"
            )
        self._bridge.log_message.emit(msg)


class _VerifyWorker(QObject):
    verify_done = pyqtSignal(bool, str, object)
    finished    = pyqtSignal()

    def __init__(
        self,
        model: ArucoZProbeModel,
        z_heights: List[float],
        marker_id: int,
        detection_attempts: int,
        bridge: _Bridge,
        stabilization_delay: float = 0.3,
    ):
        super().__init__()
        self._model               = model
        self._z_heights           = z_heights
        self._marker_id           = marker_id
        self._detection_attempts  = detection_attempts
        self._bridge              = bridge
        self._stabilization_delay = stabilization_delay
        self._stop_event          = threading.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            success, message, samples = self._model.run_verification(
                z_heights=self._z_heights,
                marker_id=self._marker_id,
                detection_attempts=self._detection_attempts,
                stop_event=self._stop_event,
                progress_cb=self._on_progress,
                log_cb=self._bridge.log_message.emit,
                stabilization_delay=self._stabilization_delay,
            )
            self.verify_done.emit(success, message, samples)
        except Exception as exc:
            _logger.exception("VerifyWorker error")
            self.verify_done.emit(False, f"Verification error: {exc}", [])
        finally:
            self.finished.emit()

    def _on_progress(
        self,
        step_index: int,
        total_steps: int,
        z_mm: float,
        dx_px: Optional[float],
        dy_px: Optional[float],
    ) -> None:
        if dx_px is not None and dy_px is not None:
            msg = (
                f"[VERIFY {step_index:3d}/{total_steps}]"
                f"  z={z_mm:7.2f} mm"
                f"  actual dx={dx_px:+.2f} px"
                f"  dy={dy_px:+.2f} px"
            )
        else:
            msg = (
                f"[VERIFY {step_index:3d}/{total_steps}]"
                f"  z={z_mm:7.2f} mm  (marker not detected)"
            )
        self._bridge.log_message.emit(msg)


class ArucoZProbeController(IApplicationController):

    def __init__(
        self,
        model:     ArucoZProbeModel,
        view:      ArucoZProbeView,
        messaging: Optional[IMessagingService] = None,
    ):
        self._model   = model
        self._view    = view
        self._broker  = messaging
        self._bridge  = _Bridge()
        self._subs:   List[Tuple[str, Callable]] = []
        self._active: List[Tuple[QThread, QObject]] = []
        self._current_worker: Optional[QObject] = None
        self._alive   = False
        self._interp_zs:  Optional[np.ndarray] = None   # sorted ascending
        self._interp_dxs: Optional[np.ndarray] = None
        self._interp_dys: Optional[np.ndarray] = None
        self._sweep_baseline_z: Optional[float] = None
        self._sweep_step: Optional[float] = None
        self._sweep_min_z: Optional[float] = None
        self._sweep_sample_count: int = 0

        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.log_message.connect(self._on_log_message)
        self._bridge.sweep_done.connect(self._on_sweep_done)
        self._bridge.verify_done.connect(self._on_verify_done)

        self._view.calibration_pos_requested.connect(self._on_go_to_calibration)
        self._view.sweep_requested.connect(self._on_sweep)
        self._view.stop_requested.connect(self._on_stop)
        self._view.predict_requested.connect(self._on_predict)
        self._view.verify_requested.connect(self._on_verify)

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

    # ── Broker subscriptions ─────────────────────────────────────────────

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

    # ── Main-thread slots ─────────────────────────────────────────────────

    def _on_camera_frame(self, frame) -> None:
        if frame is not None and self._alive:
            try:
                self._view.update_camera_frame(frame)
            except Exception:
                pass

    def _on_log_message(self, text: str) -> None:
        if self._alive:
            self._view.append_log(text)

    def _on_sweep_done(self, success: bool, message: str, results) -> None:
        if not self._alive:
            return
        samples: List[ArucoZSample] = list(results) if results else []
        if samples:
            self._view.append_log("[RESULT] (baseline — step 0)")
            for z, dx, dy in samples:
                if dx is not None and dy is not None:
                    self._view.append_log(
                        f"[RESULT] z={z:7.2f} mm  dx={dx:+.2f} px  dy={dy:+.2f} px"
                    )
                else:
                    self._view.append_log(
                        f"[RESULT] z={z:7.2f} mm  (marker not detected)"
                    )
        status = "[DONE]" if success else "[FAIL]"
        self._view.append_log(f"{status} {message}")

        if success and samples:
            self._fit_model(samples)

        self._view.set_busy(False)
        self._current_worker = None

    def _fit_model(self, samples: List[ArucoZSample]) -> None:
        valid = [(z, dx, dy) for z, dx, dy in samples if dx is not None and dy is not None]
        if len(valid) < 2:
            self._view.append_log("[MODEL] Not enough valid samples to build model.")
            self._interp_zs  = None
            self._interp_dxs = None
            self._interp_dys = None
            self._view.set_model_ready(False)
            return

        zs  = np.array([v[0] for v in valid])
        dxs = np.array([v[1] for v in valid])
        dys = np.array([v[2] for v in valid])

        # Recover baseline Z and step from sample positions
        step = float((zs[0] - zs[-1]) / (len(zs) - 1))
        self._sweep_baseline_z = float(zs[0]) + step
        self._sweep_step = step

        # Sort ascending — required by np.interp
        order = np.argsort(zs)
        self._interp_zs  = zs[order]
        self._interp_dxs = dxs[order]
        self._interp_dys = dys[order]

        z_min = float(self._interp_zs[0])
        z_max = float(self._interp_zs[-1])
        self._view.append_log(
            f"[MODEL] Interpolation model ready: {len(valid)} points"
            f"  z=[{z_min:.2f} … {z_max:.2f}] mm"
        )
        self._view.append_log(
            "[MODEL]   Exact at sample points · linear between · clamped outside range"
        )
        self._view.set_model_ready(True)

    def _interpolate(self, z: float) -> tuple[float, float]:
        """Return (dx, dy) for the given z using linear interpolation."""
        dx = float(np.interp(z, self._interp_zs, self._interp_dxs))
        dy = float(np.interp(z, self._interp_zs, self._interp_dys))
        return dx, dy

    def _on_predict(self) -> None:
        if self._interp_zs is None:
            return
        z  = self._view.get_query_z()
        dx, dy = self._interpolate(z)
        z_min = float(self._interp_zs[0])
        z_max = float(self._interp_zs[-1])
        extra = " [EXTRAPOLATED]" if z < z_min or z > z_max else ""
        self._view.show_prediction(z, dx, dy)
        self._view.append_log(
            f"[PREDICT] z={z:.1f} mm  →  dx={dx:+.2f} px   dy={dy:+.2f} px{extra}"
        )

    def _on_thread_finished(self) -> None:
        self._active = [(t, w) for t, w in self._active if t.isRunning()]

    # ── Button handlers ───────────────────────────────────────────────────

    def _on_go_to_calibration(self) -> None:
        if self._current_worker is not None:
            return
        self._view.set_busy(True)
        self._view.append_log("[MOVE] Moving to calibration position...")
        worker = _CalibWorker(self._model)
        self._launch(worker, on_done=self._on_calib_done)

    def _on_calib_done(self) -> None:
        self._view.set_busy(False)
        self._current_worker = None

    def _on_sweep(self) -> None:
        if self._current_worker is not None:
            return
        self._interp_zs  = None
        self._interp_dxs = None
        self._interp_dys = None
        self._sweep_baseline_z = None
        self._sweep_step = None
        self._view.set_model_ready(False)
        marker_id            = self._view.get_marker_id()
        min_z                = self._view.get_min_z()
        sample_count         = self._view.get_sample_count()
        detection_attempts   = self._view.get_detection_attempts()
        stabilization_delay  = self._view.get_stabilization_delay()
        self._sweep_min_z        = min_z
        self._sweep_sample_count = sample_count
        self._view.set_busy(True)
        self._view.append_log(
            f"[SWEEP] marker={marker_id}  min_z={min_z:.1f} mm"
            f"  steps={sample_count}  attempts={detection_attempts}"
            f"  stabilization={stabilization_delay:.2f}s"
        )
        worker = _SweepWorker(
            model=self._model,
            marker_id=marker_id,
            min_z=min_z,
            sample_count=sample_count,
            detection_attempts=detection_attempts,
            bridge=self._bridge,
            stabilization_delay=stabilization_delay,
        )
        worker.sweep_done.connect(self._bridge.sweep_done)
        self._launch(worker, on_done=self._on_sweep_worker_finished)

    def _on_sweep_worker_finished(self) -> None:
        # sweep_done signal handles the UI update; just clean up thread list
        self._active = [(t, w) for t, w in self._active if t.isRunning()]

    def _on_verify(self) -> None:
        if self._current_worker is not None:
            return
        if self._interp_zs is None or self._sweep_baseline_z is None or self._sweep_step is None:
            self._view.append_log("[VERIFY] No sweep model available — run a sweep first.")
            return

        min_z        = self._sweep_min_z if self._sweep_min_z is not None else 0.0
        baseline_z   = self._sweep_baseline_z
        step         = self._sweep_step
        n            = self._sweep_sample_count

        # Midpoint of each sweep segment: baseline_z - (i - 0.5)*step  for i=1..n
        z_heights = [baseline_z - (i - 0.5) * step for i in range(1, n + 1)]
        # Safety clamp: never go below min_z
        z_heights = [max(z, min_z) for z in z_heights]
        # Drop duplicates that collapsed to min_z
        seen: set = set()
        unique: List[float] = []
        for z in z_heights:
            key = round(z, 3)
            if key not in seen:
                seen.add(key)
                unique.append(z)
        z_heights = unique

        marker_id           = self._view.get_marker_id()
        detection_attempts  = self._view.get_detection_attempts()
        stabilization_delay = self._view.get_stabilization_delay()

        self._view.set_busy(True)
        self._view.append_log(
            f"[VERIFY] Starting verification: {len(z_heights)} points"
            f"  marker={marker_id}  min_z={min_z:.1f} mm"
            f"  stabilization={stabilization_delay:.2f}s"
        )

        worker = _VerifyWorker(
            model=self._model,
            z_heights=z_heights,
            marker_id=marker_id,
            detection_attempts=detection_attempts,
            bridge=self._bridge,
            stabilization_delay=stabilization_delay,
        )
        worker.verify_done.connect(self._bridge.verify_done)
        self._launch(worker, on_done=self._on_verify_worker_finished)

    def _on_verify_worker_finished(self) -> None:
        self._active = [(t, w) for t, w in self._active if t.isRunning()]

    def _on_verify_done(self, success: bool, message: str, results) -> None:
        if not self._alive:
            return

        samples: List[ArucoZSample] = list(results) if results else []
        valid = [(z, dx, dy) for z, dx, dy in samples if dx is not None and dy is not None]

        if not success or not valid:
            self._view.append_log(f"[VERIFY] {message}")
            self._view.set_busy(False)
            self._current_worker = None
            return

        # Compute predicted vs actual
        pred_dxs = [self._interpolate(z)[0] for z, _, _ in valid]
        pred_dys = [self._interpolate(z)[1] for z, _, _ in valid]
        act_dxs  = [dx for _, dx, _ in valid]
        act_dys  = [dy for _, _, dy in valid]
        err_dxs  = [a - p for a, p in zip(act_dxs, pred_dxs)]
        err_dys  = [a - p for a, p in zip(act_dys, pred_dys)]

        # ── Detailed report ────────────────────────────────────────────
        sep  = "═" * 72
        dash = "─" * 72
        hdr  = (
            f"{'#':>3}  {'Z (mm)':>8}  "
            f"{'pred_dx':>8}  {'pred_dy':>8}  "
            f"{'act_dx':>8}  {'act_dy':>8}  "
            f"{'err_dx':>8}  {'err_dy':>8}"
        )

        self._view.append_log(f"[VERIFY] {sep}")
        self._view.append_log(f"[VERIFY] {hdr}")
        self._view.append_log(f"[VERIFY] {dash}")

        max_abs_err = 0.0
        max_err_z   = 0.0
        for idx, ((z, _, _), pdx, pdy, adx, ady, edx, edy) in enumerate(
            zip(valid, pred_dxs, pred_dys, act_dxs, act_dys, err_dxs, err_dys), start=1
        ):
            abs_err = max(abs(edx), abs(edy))
            if abs_err > max_abs_err:
                max_abs_err = abs_err
                max_err_z   = z
            self._view.append_log(
                f"[VERIFY] {idx:>3}  {z:>8.2f}  "
                f"{pdx:>+8.2f}  {pdy:>+8.2f}  "
                f"{adx:>+8.2f}  {ady:>+8.2f}  "
                f"{edx:>+8.2f}  {edy:>+8.2f}"
            )

        self._view.append_log(f"[VERIFY] {dash}")

        mae_dx  = float(np.mean(np.abs(err_dxs)))
        mae_dy  = float(np.mean(np.abs(err_dys)))
        rms_dx  = float(np.sqrt(np.mean(np.array(err_dxs) ** 2)))
        rms_dy  = float(np.sqrt(np.mean(np.array(err_dys) ** 2)))
        max_dx  = float(np.max(np.abs(err_dxs)))
        max_dy  = float(np.max(np.abs(err_dys)))

        self._view.append_log(
            f"[VERIFY] MAE   dx={mae_dx:.3f} px   dy={mae_dy:.3f} px"
        )
        self._view.append_log(
            f"[VERIFY] RMS   dx={rms_dx:.3f} px   dy={rms_dy:.3f} px"
        )
        self._view.append_log(
            f"[VERIFY] Max   dx={max_dx:.3f} px   dy={max_dy:.3f} px"
            f"   (worst z={max_err_z:.2f} mm)"
        )
        self._view.append_log(f"[VERIFY] {sep}")
        self._view.append_log(f"[VERIFY] {message}")

        self._view.set_busy(False)
        self._current_worker = None

    def _on_stop(self) -> None:
        if self._current_worker and hasattr(self._current_worker, "request_stop"):
            self._view.append_log("[STOP] Stop requested...")
            self._current_worker.request_stop()

    # ── Thread helper ─────────────────────────────────────────────────────

    def _launch(self, worker: QObject, on_done: Callable) -> None:
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        if hasattr(worker, "log_message"):
            worker.log_message.connect(self._on_log_message)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        self._active.append((thread, worker))
        self._current_worker = worker
        thread.start()
