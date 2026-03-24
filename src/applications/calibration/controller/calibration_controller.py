import logging
from typing import List, Tuple, Callable

from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt

from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.styled_message_box import ask_yes_no
from src.applications.calibration.model.calibration_model import CalibrationModel
from src.applications.calibration.view.calibration_view import CalibrationView
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.component_ids import ProcessID
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
    marker_height_btn_enabled = pyqtSignal(bool)
    area_grid_btn_enabled   = pyqtSignal(bool)
    test_finished           = pyqtSignal(bool, str)
    marker_height_finished  = pyqtSignal(bool, str)
    area_grid_finished      = pyqtSignal(bool, str)
    area_grid_verified      = pyqtSignal(bool, str, dict)
    area_grid_verify_progress = pyqtSignal(str, str, int, int)
    depth_map_btn_enabled   = pyqtSignal(bool)



class CalibrationController(IApplicationController):

    def __init__(self, model: CalibrationModel, view: CalibrationView,
                 messaging: IMessagingService):
        self._model    = model
        self._view     = view
        self._broker   = messaging
        self._bridge   = _Bridge()
        self._subs:    List[Tuple[str, Callable]] = []
        self._threads: List[Tuple[QThread, _Worker]] = []
        self._running               = False
        self._active                = False
        self._robot_process_running = False   # ← tracks robot calibration process state
        self._logger   = logging.getLogger(self.__class__.__name__)
        self._area_grid_verify_statuses: dict[str, str] = {}

    def load(self) -> None:
        self._running = True
        self._active = True
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.log_received.connect(self._on_log_received)
        self._bridge.stop_btn_enabled.connect(self._view.set_stop_calibration_enabled)
        self._bridge.test_btn_enabled.connect(self._view.set_test_calibration_enabled)
        self._bridge.camera_tcp_btn_enabled.connect(self._view.set_camera_tcp_offset_enabled)
        self._bridge.marker_height_btn_enabled.connect(self._view.set_measure_marker_heights_enabled)
        self._bridge.area_grid_btn_enabled.connect(self._view.set_measure_area_grid_enabled)
        self._bridge.test_finished.connect(self._on_test_finished)
        self._bridge.marker_height_finished.connect(self._on_marker_height_finished)
        self._bridge.area_grid_finished.connect(self._on_area_grid_finished)
        self._bridge.area_grid_verified.connect(self._on_area_grid_verified)
        self._bridge.area_grid_verify_progress.connect(self._on_area_grid_verify_progress)
        self._bridge.depth_map_btn_enabled.connect(self._view.set_depth_map_enabled)
        self._view.stop_calibration_requested.connect(self._on_stop_calibration)

        self._connect_signals()
        self._subscribe()
        self._view.destroyed.connect(self.stop)
        active_area_id = self._model.get_active_work_area_id()
        if active_area_id:
            self._view.set_current_work_area_id(active_area_id)
        self._refresh_calibration_dependent_actions()
        self._load_height_mapping_areas()
        self._view.set_depth_map_enabled(self._model.has_saved_height_model(self._view.current_work_area_id()))

    def stop(self) -> None:
        self._running = False
        self._active = False
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
        self._model.stop_marker_height_measurement()
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
        self._view.measure_marker_heights_requested.connect(self._on_measure_marker_heights)
        self._view.generate_area_grid_requested.connect(self._on_generate_area_grid)
        self._view.measure_area_grid_requested.connect(self._on_measure_area_grid)
        self._view.verify_area_grid_requested.connect(self._on_verify_area_grid)
        self._view.view_depth_map_requested.connect(self._on_view_depth_map)
        self._view.verify_saved_model_requested.connect(self._on_verify_saved_model)
        self._view.work_area_changed.connect(self._on_work_area_changed)
        self._view.measurement_area_changed.connect(self._on_measurement_area_changed)

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
            self._bridge.marker_height_btn_enabled.emit(False)
            self._bridge.area_grid_btn_enabled.emit(False)
        elif event.state in (ProcessState.STOPPED, ProcessState.ERROR, ProcessState.IDLE):
            self._robot_process_running = False
            self._bridge.stop_btn_enabled.emit(False)
            self._refresh_calibration_dependent_actions()

        if event.state == ProcessState.STOPPED:
            self._bridge.process_finished.emit(True, "Robot calibration complete")
            self._bridge.depth_map_btn_enabled.emit(
                self._model.has_saved_height_model(self._view.current_work_area_id())
            )
        elif event.state == ProcessState.ERROR:
            self._bridge.process_finished.emit(False, event.message or "Robot calibration failed")

    def _on_view_depth_map(self) -> None:
        from src.applications.calibration.view.depth_map_dialog import DepthMapDialog
        data = self._model.get_height_calibration_data(self._view.current_work_area_id())
        if data is None:
            self._view.append_log("✗ No height calibration data available")
            return
        dlg = DepthMapDialog(data, parent=self._view)
        dlg.exec()

    def _on_test_calibration(self) -> None:
        self._view.set_buttons_enabled(False)
        self._bridge.test_btn_enabled.emit(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        self._bridge.marker_height_btn_enabled.emit(False)
        self._bridge.area_grid_btn_enabled.emit(False)
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
        self._model.restore_pending_safety_walls()
        self._view.set_buttons_enabled(True)
        self._bridge.stop_btn_enabled.emit(False)
        self._refresh_calibration_dependent_actions()

    def _on_measure_marker_heights(self) -> None:
        self._view.set_buttons_enabled(False)
        self._bridge.test_btn_enabled.emit(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        self._bridge.marker_height_btn_enabled.emit(False)
        self._bridge.stop_btn_enabled.emit(True)
        thread = QThread()
        worker = _Worker(self._model.measure_marker_heights)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_marker_height_worker_done)
        worker.failed.connect(self._on_marker_height_worker_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append((thread, worker))
        thread.start()

    def _on_marker_height_worker_done(self, result) -> None:
        ok, msg = result
        self._bridge.marker_height_finished.emit(ok, msg)

    def _on_marker_height_worker_failed(self, error: str) -> None:
        self._bridge.marker_height_finished.emit(False, f"Marker height error: {error}")

    def _on_marker_height_finished(self, ok: bool, msg: str) -> None:
        if not self._running:
            return
        self._view.append_log(f"{'✓' if ok else '✗'} {msg}")
        self._view.set_buttons_enabled(True)
        self._bridge.stop_btn_enabled.emit(False)
        self._refresh_calibration_dependent_actions()

        if not ok:
            return

        self._bridge.depth_map_btn_enabled.emit(
            self._model.has_saved_height_model(self._view.current_work_area_id())
        )

        should_verify = ask_yes_no(
            self._view,
            "Verify Height Model",
            "Run 4-point verification against the saved piecewise triangle height model?",
        )
        if should_verify:
            self._start_height_model_verification(self._view.current_work_area_id())

    def _on_generate_area_grid(self) -> None:
        self._save_current_height_mapping_area()
        corners = self._view.get_measurement_area_corners()
        rows, cols = self._view.get_area_grid_shape()
        if len(corners) != 4:
            self._view.append_log("✗ Area grid needs exactly 4 corners. Click the preview to place them.")
            return
        points = self._model.generate_area_grid(corners, rows, cols)
        if not points:
            self._view.append_log("✗ Failed to generate area grid")
            return
        labels = [f"r{(i // cols) + 1}c{(i % cols) + 1}" for i in range(len(points))]
        self._view.set_generated_grid_points(points, point_labels=labels, point_statuses={})
        self._view.append_log(f"✓ Generated area grid: rows={rows} cols={cols} points={len(points)}")

    def _on_verify_area_grid(self) -> None:
        self._save_current_height_mapping_area()
        corners = self._view.get_measurement_area_corners()
        rows, cols = self._view.get_area_grid_shape()
        if len(corners) != 4:
            self._view.append_log("✗ Area grid verification needs exactly 4 corners")
            return
        points = self._model.generate_area_grid(corners, rows, cols)
        if not points:
            self._view.append_log("✗ Failed to generate area grid for verification")
            return
        labels = [f"r{(i // cols) + 1}c{(i % cols) + 1}" for i in range(len(points))]
        self._area_grid_verify_statuses = {}
        self._view.set_generated_grid_points(points, point_labels=labels, point_statuses={})
        self._view.set_substitute_regions({})
        self._view.append_log("▶ Verifying area grid reachability...")
        self._view.set_verify_area_grid_busy(True, 0, len(points))
        self._view.set_buttons_enabled(False)
        self._bridge.test_btn_enabled.emit(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        self._bridge.marker_height_btn_enabled.emit(False)
        self._bridge.area_grid_btn_enabled.emit(False)
        thread = QThread()
        worker = _Worker(
            lambda: self._model.verify_area_grid(
                corners,
                rows,
                cols,
                progress_callback=lambda label, status, current, total: (
                    self._bridge.area_grid_verify_progress.emit(label, status, current, total)
                ),
            )
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_area_grid_verify_done)
        worker.failed.connect(self._on_area_grid_verify_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append((thread, worker))
        thread.start()

    def _on_measure_area_grid(self) -> None:
        self._save_current_height_mapping_area()
        corners = self._view.get_measurement_area_corners()
        rows, cols = self._view.get_area_grid_shape()
        if len(corners) != 4:
            self._view.append_log("✗ Area grid measurement needs exactly 4 corners")
            return
        points = self._model.generate_area_grid(corners, rows, cols)
        if not points:
            self._view.append_log("✗ Failed to generate area grid for measurement")
            return
        self._view.set_generated_grid_points(points)
        self._view.set_buttons_enabled(False)
        self._bridge.test_btn_enabled.emit(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        self._bridge.marker_height_btn_enabled.emit(False)
        self._bridge.area_grid_btn_enabled.emit(False)
        self._bridge.stop_btn_enabled.emit(True)
        thread = QThread()
        area_id = self._view.current_work_area_id()
        worker = _Worker(lambda: self._model.measure_area_grid(area_id, corners, rows, cols))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_area_grid_worker_done)
        worker.failed.connect(self._on_area_grid_worker_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append((thread, worker))
        thread.start()

    def _on_area_grid_worker_done(self, result) -> None:
        ok, msg = result
        self._bridge.area_grid_finished.emit(ok, msg)

    def _on_area_grid_worker_failed(self, error: str) -> None:
        self._bridge.area_grid_finished.emit(False, f"Area grid error: {error}")

    def _on_area_grid_verify_done(self, result) -> None:
        ok, msg, details = result
        self._bridge.area_grid_verified.emit(ok, msg, details)

    def _on_area_grid_verify_failed(self, error: str) -> None:
        self._bridge.area_grid_verified.emit(False, f"Area grid verification error: {error}", {})

    def _on_area_grid_finished(self, ok: bool, msg: str) -> None:
        if not self._running:
            return
        self._view.append_log(f"{'✓' if ok else '✗'} {msg}")
        self._view.set_buttons_enabled(True)
        self._bridge.stop_btn_enabled.emit(False)
        self._refresh_calibration_dependent_actions()

        if not ok:
            self._model.restore_pending_safety_walls()
            return

        self._bridge.depth_map_btn_enabled.emit(
            self._model.has_saved_height_model(self._view.current_work_area_id())
        )

        should_verify = ask_yes_no(
            self._view,
            "Verify Height Model",
            "Run 4-point verification against the saved area-grid height model?",
        )
        if should_verify:
            self._start_height_model_verification(self._view.current_work_area_id())
        else:
            self._model.restore_pending_safety_walls()

    def _on_area_grid_verified(self, ok: bool, msg: str, details: dict) -> None:
        if not self._running:
            return
        self._view.append_log(f"{'✓' if ok else '✗'} {msg}")
        points = self._view.get_measurement_area_corners()
        rows, cols = self._view.get_area_grid_shape()
        generated = self._model.generate_area_grid(points, rows, cols) if len(points) == 4 else []
        labels = [f"r{(i // cols) + 1}c{(i % cols) + 1}" for i in range(len(generated))]
        # substitutes: dict[str, list[(xn, yn)]]  (one or more support points per unreachable)
        substitutes = details.get("substitutes", {}) if ok else {}
        all_points = list(generated)
        all_labels = list(labels)
        all_statuses = dict(self._area_grid_verify_statuses)
        for u_label, subs_norm in substitutes.items():
            for i, (xn, yn) in enumerate(subs_norm):
                sub_label = f"{u_label}_sub_{i}"
                all_points.append((xn, yn))
                all_labels.append(sub_label)
                all_statuses[sub_label] = "substitute"
        self._view.set_generated_grid_points(
            all_points,
            point_labels=all_labels,
            point_statuses=all_statuses,
        )
        self._view.set_substitute_regions(details.get("substitute_polygons", {}) if ok else {})
        if ok:
            reachable    = details.get("reachable_labels", [])
            unreachable  = details.get("unreachable_labels", [])
            via_anchor   = details.get("via_anchor_labels", [])
            xy           = details.get("point_robot_xy", {})
            # sub_xy: dict[str, list[(x, y)]]
            sub_xy       = details.get("substitute_robot_xy", {})
            total_pts    = len(reachable) + len(unreachable)

            def _log(line: str) -> None:
                self._view.append_log(line)
                self._logger.info(line)

            _log("─" * 48)
            _log("Grid Verification Report")
            _log("─" * 48)

            _log(f"Reachable  ({len(reachable)}/{total_pts}):")
            for lbl in reachable:
                x, y = xy.get(lbl, (float("nan"), float("nan")))
                _log(f"  {lbl:<8}  x={x:>8.1f} mm  y={y:>8.1f} mm")

            if unreachable:
                _log(f"Unreachable ({len(unreachable)}/{total_pts}):")
                for lbl in unreachable:
                    x, y = xy.get(lbl, (float("nan"), float("nan")))
                    _log(f"  {lbl:<8}  x={x:>8.1f} mm  y={y:>8.1f} mm")

            if substitutes:
                _log("Substitutions:")
                for lbl in unreachable:
                    pts = sub_xy.get(lbl, [])
                    if pts:
                        for i, (sx, sy) in enumerate(pts):
                            _log(f"  {lbl} → {lbl}_sub_{i}  x={sx:>8.1f} mm  y={sy:>8.1f} mm")
                    else:
                        _log(f"  {lbl} → no substitute found inside grid")

            if via_anchor:
                _log(f"Via-anchor: {', '.join(via_anchor)}")

            _log("─" * 48)
        self._view.set_verify_area_grid_busy(False)
        self._view.set_buttons_enabled(True)
        self._refresh_calibration_dependent_actions()

    def _on_area_grid_verify_progress(self, label: str, status: str, current: int, total: int) -> None:
        if not self._running:
            return
        self._area_grid_verify_statuses[str(label)] = str(status)
        corners = self._view.get_measurement_area_corners()
        rows, cols = self._view.get_area_grid_shape()
        generated = self._model.generate_area_grid(corners, rows, cols) if len(corners) == 4 else []
        labels = [f"r{(i // cols) + 1}c{(i % cols) + 1}" for i in range(len(generated))]
        self._view.set_generated_grid_points(
            generated,
            point_labels=labels,
            point_statuses=dict(self._area_grid_verify_statuses),
        )
        self._view.set_verify_area_grid_busy(True, current, total)

    def _start_height_model_verification(self, area_id: str) -> None:
        self._view.set_buttons_enabled(False)
        self._bridge.test_btn_enabled.emit(False)
        self._bridge.camera_tcp_btn_enabled.emit(False)
        self._bridge.marker_height_btn_enabled.emit(False)
        self._bridge.area_grid_btn_enabled.emit(False)
        self._bridge.stop_btn_enabled.emit(True)
        thread = QThread()
        worker = _Worker(lambda: self._model.verify_height_model(area_id))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_test_worker_done)
        worker.failed.connect(self._on_test_worker_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append((thread, worker))
        thread.start()

    def _on_verify_saved_model(self) -> None:
        area_id = self._view.current_work_area_id()
        if not self._model.has_saved_height_model(area_id):
            self._view.append_log("✗ No saved height model available")
            return
        self._start_height_model_verification(area_id)

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
        can_measure = self._model.can_measure_marker_heights() and not self.is_calibrating()
        self._bridge.marker_height_btn_enabled.emit(can_measure)
        self._bridge.area_grid_btn_enabled.emit(can_measure)

    def _load_height_mapping_areas(self) -> None:
        for definition in self._model.get_work_area_definitions():
            if not definition.supports_height_mapping:
                continue
            points = self._model.get_height_mapping_area(definition.id)
            if points:
                self._view.set_measurement_area_corners(definition.id, points)

    def _save_current_height_mapping_area(self) -> None:
        area_key = self._view.current_height_mapping_area_key()
        if not area_key:
            return
        corners = self._view.get_measurement_area_corners()
        if len(corners) != 4:
            return
        ok, msg = self._model.save_height_mapping_area(area_key, corners)
        if not ok:
            self._view.append_log(f"✗ {msg}")

    def _on_work_area_changed(self, area_id: str) -> None:
        self._model.set_active_work_area_id(area_id)
        self._bridge.depth_map_btn_enabled.emit(self._model.has_saved_height_model(area_id))

    def _on_measurement_area_changed(self) -> None:
        self._save_current_height_mapping_area()
