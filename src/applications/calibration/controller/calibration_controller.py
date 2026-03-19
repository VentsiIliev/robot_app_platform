import logging
from typing import List, Tuple, Callable

from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt

from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.jog_controller import JogController
from src.applications.calibration.model.calibration_model import CalibrationModel
from src.applications.calibration.view.calibration_view import CalibrationView
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.process_ids import ProcessID
from src.shared_contracts.events.robot_events import RobotCalibrationTopics
from src.shared_contracts.events.vision_events import VisionTopics
from src.shared_contracts.events.process_events import ProcessTopics, ProcessState, ProcessStateEvent

_CALIBRATION_PROCESS_ID = ProcessID.ROBOT_CALIBRATION

class _Worker(QObject):
    finished = pyqtSignal(object)
    failed   = pyqtSignal(str)

    def __init__(self, fn: Callable):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception as exc:
            self.failed.emit(str(exc))


class _Bridge(QObject):
    camera_frame            = pyqtSignal(object)
    log_received            = pyqtSignal(str)
    process_finished        = pyqtSignal(bool, str)
    camera_process_finished = pyqtSignal(bool, str)
    stop_btn_enabled        = pyqtSignal(bool)
    test_btn_enabled        = pyqtSignal(bool)
    camera_tcp_btn_enabled  = pyqtSignal(bool)
    test_finished           = pyqtSignal(bool, str)
    depth_map_btn_enabled   = pyqtSignal(bool)



class CalibrationController(IApplicationController):

    def __init__(self, model: CalibrationModel, view: CalibrationView,
                 messaging: IMessagingService,jog_service):
        self._model    = model
        self._view     = view
        self._jog = JogController(view, jog_service, messaging)
        self._broker   = messaging
        self._bridge   = _Bridge()
        self._subs:    List[Tuple[str, Callable]] = []
        self._threads: List[Tuple[QThread, _Worker]] = []
        self._running               = False
        self._active                = False
        self._robot_process_running = False   # ← tracks robot calibration process state
        self._logger   = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        self._running = True
        self._active = True
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.log_received.connect(self._on_log_received)
        self._bridge.stop_btn_enabled.connect(self._view.set_stop_calibration_enabled)
        self._bridge.test_btn_enabled.connect(self._view.set_test_calibration_enabled)
        self._bridge.camera_tcp_btn_enabled.connect(self._view.set_camera_tcp_offset_enabled)
        self._bridge.test_finished.connect(self._on_test_finished)
        self._bridge.depth_map_btn_enabled.connect(self._view.set_depth_map_enabled)
        self._view.stop_calibration_requested.connect(self._on_stop_calibration)

        self._connect_signals()
        self._subscribe()
        self._jog.start()
        self._view.destroyed.connect(self.stop)
        self._refresh_calibration_dependent_actions()
        self._view.set_depth_map_enabled(self._model.get_height_calibration_data() is not None)

    def stop(self) -> None:
        self._running = False
        self._active = False
        self._jog.stop()
        self._model.stop_calibration()
        self._model.stop_test_calibration()
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                pass
        self._subs.clear()
        for thread, _ in self._threads:
            thread.quit()
            thread.wait(3000)  # ← timeout, don't block forever
        self._threads.clear()

    # ── Broker → Bridge ───────────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)
        self._sub(RobotCalibrationTopics.ROBOT_CALIBRATION_LOG, self._on_calibration_log_raw)
        self._sub(ProcessTopics.state(_CALIBRATION_PROCESS_ID), self._on_calibration_process_state)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    def _on_calibration_log_raw(self, msg) -> None:
        self._bridge.log_received.emit(str(msg))

    # ── Bridge → View (main thread) ───────────────────────────────────
    def _on_stop_calibration(self) -> None:
        self._model.stop_calibration()
        self._model.stop_test_calibration()
        self._bridge.stop_btn_enabled.emit(False)

    def _on_camera_frame(self, frame) -> None:
        if self._active and frame is not None:
            self._view.update_camera_view(frame)

    def _on_log_received(self, msg: str) -> None:
        if self._running:
            self._view.append_log(msg)

    # ── View → Model ──────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._view.capture_requested.connect(self._on_capture)
        self._view.calibrate_camera_requested.connect(self._on_calibrate_camera)
        self._view.calibrate_robot_requested.connect(self._on_calibrate_robot)
        self._view.calibrate_sequence_requested.connect(self._on_calibrate_sequence)
        self._view.calibrate_camera_tcp_offset_requested.connect(self._on_calibrate_camera_tcp_offset)
        self._view.test_calibration_requested.connect(self._on_test_calibration)
        self._view.view_depth_map_requested.connect(self._on_view_depth_map)

    def _log(self, ok: bool, msg: str) -> None:
        self._view.append_log(f"{'✓' if ok else '✗'} {msg}")

    def _on_capture(self) -> None:
        ok, msg = self._model.capture_calibration_image()
        self._log(ok, msg)

    def _on_calibrate_camera(self) -> None:
        self._run_in_thread(self._model.calibrate_camera)

    def _on_calibrate_robot(self) -> None:
        self._view.set_buttons_enabled(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        _, msg = self._model.calibrate_robot()
        self._view.append_log(f"▶ {msg}")

    def _on_calibrate_sequence(self) -> None:
        self._run_in_thread(self._model.calibrate_camera_and_robot)

    def _on_calibrate_camera_tcp_offset(self) -> None:
        self._view.set_buttons_enabled(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        self._run_in_thread(self._model.calibrate_camera_tcp_offset, manage_buttons=False)

    def _on_task_done(self, result) -> None:
        if not self._running:
            return
        ok, msg = result
        self._view.append_log(f"{'✓' if ok else '✗'} {msg}")
        self._view.set_buttons_enabled(True)
        self._refresh_calibration_dependent_actions()

    def _on_task_failed(self, error: str) -> None:
        if not self._running:
            return
        self._logger.error("Calibration task failed: %s", error)
        self._view.append_log(f"✗ {error}")
        self._view.set_buttons_enabled(True)
        self._refresh_calibration_dependent_actions()

    # main-thread bridge slot:
    def _on_process_finished(self, ok: bool, msg: str) -> None:
        if self._running:
            self._view.append_log(f"{'✓' if ok else '✗'} {msg}")
            self._view.set_buttons_enabled(True)

    def is_calibrating(self) -> bool:
        threads_active = any(t.isRunning() for t, _ in self._threads)
        return threads_active or self._robot_process_running

    def _on_calibration_process_state(self, event: ProcessStateEvent) -> None:
        if event.state == ProcessState.RUNNING:
            self._robot_process_running = True
            self._bridge.stop_btn_enabled.emit(True)
            self._bridge.test_btn_enabled.emit(False)
            self._bridge.camera_tcp_btn_enabled.emit(False)
        elif event.state in (ProcessState.STOPPED, ProcessState.ERROR, ProcessState.IDLE):
            self._robot_process_running = False
            self._bridge.stop_btn_enabled.emit(False)
            self._refresh_calibration_dependent_actions()

        if event.state == ProcessState.STOPPED:
            self._bridge.process_finished.emit(True, "Robot calibration complete")
            self._bridge.depth_map_btn_enabled.emit(
                self._model.get_height_calibration_data() is not None
            )
        elif event.state == ProcessState.ERROR:
            self._bridge.process_finished.emit(False, event.message or "Robot calibration failed")

    def _on_view_depth_map(self) -> None:
        from src.applications.calibration.view.depth_map_dialog import DepthMapDialog
        data = self._model.get_height_calibration_data()
        if data is None:
            self._view.append_log("✗ No height calibration data available")
            return
        dlg = DepthMapDialog(data, parent=self._view)
        dlg.exec()

    def _on_test_calibration(self) -> None:
        self._view.set_buttons_enabled(False)
        self._bridge.test_btn_enabled.emit(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        self._bridge.stop_btn_enabled.emit(True)
        thread = QThread()
        worker = _Worker(self._model.test_calibration)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_test_worker_done)
        worker.failed.connect(self._on_test_worker_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append((thread, worker))
        thread.start()

    def _on_test_worker_done(self, result) -> None:
        ok, msg = result
        self._bridge.test_finished.emit(ok, msg)

    def _on_test_worker_failed(self, error: str) -> None:
        self._bridge.test_finished.emit(False, f"Test error: {error}")

    def _on_test_finished(self, ok: bool, msg: str) -> None:
        if not self._running:
            return
        self._view.append_log(f"{'✓' if ok else '✗'} {msg}")
        self._view.set_buttons_enabled(True)
        self._bridge.stop_btn_enabled.emit(False)
        self._refresh_calibration_dependent_actions()

    # ── Thread helper ─────────────────────────────────────────────────

    def _run_in_thread(self, fn: Callable, manage_buttons: bool = True) -> None:
        if manage_buttons:
            self._view.set_buttons_enabled(False)
            self._bridge.camera_tcp_btn_enabled.emit(False)
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_task_done)
        worker.failed.connect(self._on_task_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append((thread, worker))
        thread.start()

    def _on_thread_finished(self) -> None:
        self._threads = [(t, w) for t, w in self._threads if t.isRunning()]

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    def _refresh_calibration_dependent_actions(self) -> None:
        calibrated = self._model.is_calibrated()
        self._bridge.test_btn_enabled.emit(calibrated)
        self._bridge.camera_tcp_btn_enabled.emit(calibrated and not self.is_calibrating())
