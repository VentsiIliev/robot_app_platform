import logging
import threading
from typing import List, Tuple

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QRunnable, QThread, QThreadPool, QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap

from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.jog_controller import JogController
from src.applications.base.robot_jog_service import RobotJogService
from src.applications.height_measuring.model.height_measuring_model import HeightMeasuringModel
from src.applications.height_measuring.model.mapper import HeightMeasuringSettingsMapper
from src.applications.height_measuring.view.height_measuring_view import HeightMeasuringView
from src.engine.core.i_messaging_service import IMessagingService

_logger = logging.getLogger(__name__)


class _Bridge(QObject):
    calibration_finished = pyqtSignal(object)
    detect_finished      = pyqtSignal(object)
    laser_on_finished    = pyqtSignal(object)
    laser_off_finished   = pyqtSignal(object)


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.finished.emit(self._fn())
        except Exception as e:
            _logger.error("Worker unhandled exception: %s", e, exc_info=True)
            self.finished.emit((False, str(e)))


class _FireAndForget(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        self._fn()


class HeightMeasuringController(IApplicationController):

    def __init__(self, model, view, messaging, jog_service):
        self._model           = model
        self._view            = view
        self._jog             = JogController(view, jog_service, messaging)
        self._bridge          = _Bridge()
        self._active: List[Tuple[QThread, _Worker]] = []
        self._stopped         = False                    # ← add
        self._frame_timer     = QTimer()
        self._frame_timer.setInterval(100)
        self._laser_on_state  = False
        self._calibrating = False

        self._detect_lock    = threading.Lock()
        self._is_detecting   = False
        self._detect_timer   = QTimer()
        self._detect_timer.setInterval(1000)


        self._frame_timer.timeout.connect(self._on_frame_tick)
        self._detect_timer.timeout.connect(self._on_detect_tick)
        self._bridge.calibration_finished.connect(self._on_calibration_done)
        self._bridge.detect_finished.connect(self._on_detect_done)
        self._bridge.laser_on_finished.connect(self._on_laser_on_done)
        self._bridge.laser_off_finished.connect(self._on_laser_off_done)

        self._view.calibrate_requested.connect(self._on_calibrate_requested)
        self._view.stop_requested.connect(self._on_stop_requested)
        self._view.save_settings_requested.connect(self._on_save_settings)
        self._view.laser_on_requested.connect(self._on_laser_on_requested)
        self._view.laser_off_requested.connect(self._on_laser_off_requested)
        self._view.detect_once_requested.connect(self._on_detect_once_requested)
        self._view.start_continuous_requested.connect(self._on_start_continuous_requested)
        self._view.stop_continuous_requested.connect(self._on_stop_continuous_requested)

    def is_calibrating(self) -> bool:
        return self._calibrating

    def load(self) -> None:
        settings = self._model.get_settings()
        self._view.set_settings(settings)
        self._view.load_settings(HeightMeasuringSettingsMapper.to_flat_dict(settings))
        is_cal = self._model.is_calibrated()
        info   = self._model.get_calibration_info() if is_cal else None
        self._view.set_calibration_status(is_cal, info)
        self._frame_timer.start()
        self._jog.start()

    def stop(self) -> None:
        self._stopped = True  # ← set first, before anything else
        self._detect_timer.stop()
        self._jog.stop()
        self._frame_timer.stop()
        self._model.cleanup()  # ← replaces the laser_off block
        for thread, _ in self._active:
            thread.quit()
            thread.wait(3000)
        self._active.clear()

    # ── Frame polling ─────────────────────────────────────────────────────────

    def _on_frame_tick(self):
        if self._stopped:  # ← guard
            return
        frame = self._model.get_latest_frame()
        if frame is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._view.set_frame(rgb)
            except Exception as e:
                _logger.debug("Frame conversion error: %s", e)

    # ── Calibration ───────────────────────────────────────────────────────────

    def _on_calibrate_requested(self):
        self._calibrating = True
        self._view.set_calibrating(True)
        self._view.append_log("Starting calibration…")
        self._run_blocking(self._model.run_calibration, self._bridge.calibration_finished)

    def _on_calibration_done(self, result):
        self._active = [(t, w) for t, w in self._active if t.isRunning()]
        ok, msg = result
        self._view.set_calibrating(False)
        self._view.show_message(msg, is_error=not ok)
        if ok:
            self._model.reload_calibration()
            info = self._model.get_calibration_info()
            self._view.set_calibration_status(True, info)
            self._view.append_log("Calibration saved.")
        else:
            self._view.append_log(f"Calibration failed: {msg}")
        self._calibrating = False

    def _on_stop_requested(self):
        self._calibrating = False
        self._model.cancel_calibration()  # ← signals the loop to exit
        for thread, _ in self._active:
            thread.quit()
        # _active self-removes via thread.finished when calibration returns
        self._view.set_calibrating(False)
        self._view.append_log("Calibration stopped by user.")

    # ── Laser control ─────────────────────────────────────────────────────────

    def _on_laser_on_requested(self):
        self._view.set_laser_state(True)
        self._run_blocking(self._model.laser_on, self._bridge.laser_on_finished)

    def _on_laser_off_requested(self):
        self._view.set_laser_state(False)
        self._run_blocking(self._model.laser_off, self._bridge.laser_off_finished)

    def _on_laser_on_done(self, result):
        self._active = [(t, w) for t, w in self._active if t.isRunning()]
        ok, msg = result
        if ok:
            self._laser_on_state = True
        else:
            self._view.set_laser_state(False)
            self._view.show_message(f"Laser error: {msg}", is_error=True)

    def _on_laser_off_done(self, result):
        self._active = [(t, w) for t, w in self._active if t.isRunning()]
        ok, msg = result
        if ok:
            self._laser_on_state = False
        else:
            self._view.set_laser_state(True)
            self._view.show_message(f"Laser error: {msg}", is_error=True)

    # ── Detection ─────────────────────────────────────────────────────────────

    def _on_detect_once_requested(self):
        with self._detect_lock:
            if self._is_detecting:
                return
            self._is_detecting = True
        QThreadPool.globalInstance().start(_FireAndForget(self._do_detect))

    def _on_start_continuous_requested(self):
        self._detect_timer.start()
        self._view.set_live_detecting(True)

    def _on_stop_continuous_requested(self):
        self._detect_timer.stop()
        self._view.set_live_detecting(False)
        self._view.set_laser_state(self._laser_on_state)

    def _on_detect_tick(self):
        with self._detect_lock:
            if self._is_detecting:
                return
            self._is_detecting = True
        QThreadPool.globalInstance().start(_FireAndForget(self._do_detect))

    def _do_detect(self):
        try:
            result = self._model.detect_once()
            self._bridge.detect_finished.emit(result)
        finally:
            with self._detect_lock:
                self._is_detecting = False

    def _on_detect_done(self, result):
        if self._stopped:  # ← guard
            return
        self._active = [(t, w) for t, w in self._active if t.isRunning()]
        self._view.set_detect_result(result)
        if result.debug_image is not None:
            rgb = cv2.cvtColor(result.debug_image, cv2.COLOR_BGR2RGB)
            self._view.set_mask_frame_rgb(rgb)
        elif result.mask is not None:
            self._view.set_mask_frame(result.mask)


    # ── Settings save ─────────────────────────────────────────────────────────

    def _on_save_settings(self):
        flat    = self._view.get_settings_values()
        base    = self._model.get_settings()
        updated = HeightMeasuringSettingsMapper.from_flat_dict(flat, base)
        updated.calibration.calibration_initial_position = self._view.get_initial_position()
        ok, msg = self._model.save_settings(updated)
        self._view.show_message(msg, is_error=not ok)

    # ── Thread helper ─────────────────────────────────────────────────────────

    def _run_blocking(self, fn, on_done: pyqtSignal) -> None:
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        thread.finished.connect(lambda: self._remove_thread(thread))  # ← keep ref alive until fully done
        self._active.append((thread, worker))
        thread.start()

    def _remove_thread(self, thread: QThread) -> None:
        self._active = [(t, w) for t, w in self._active if t is not thread]

