from __future__ import annotations
import logging
import logging.handlers
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.pick_and_place_visualizer.model.pick_and_place_visualizer_model import (
    PickAndPlaceVisualizerModel,
)
from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import SimResult
from src.applications.pick_and_place_visualizer.view.pick_and_place_visualizer_view import (
    PickAndPlaceVisualizerView,
)
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.process_ids import ProcessID
from src.shared_contracts.events.process_events import ProcessTopics
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(QObject):
    camera_frame   = pyqtSignal(object)
    process_state  = pyqtSignal(str)
    log_record     = pyqtSignal(str)
    sim_result     = pyqtSignal(object)
    workpiece_placed  = pyqtSignal(object)
    plane_reset       = pyqtSignal()


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        self.finished.emit(self._fn())


class _BridgeLogHandler(logging.Handler):
    """Captures pick-and-place + matching log records and forwards via Qt signal."""

    _PREFIXES = (
        "src.robot_systems.glue.processes.pick_and_place",
        "src.robot_systems.glue.domain.matching",
        "PickAndPlaceVisualizerService",
        "PickAndPlaceVisualizerController",
    )

    def __init__(self, bridge: _Bridge):
        super().__init__()
        self._bridge = bridge
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
                                            datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        if any(record.name.startswith(p) for p in self._PREFIXES):
            try:
                self._bridge.log_record.emit(self.format(record))
            except Exception:
                pass


class PickAndPlaceVisualizerController(IApplicationController):

    def __init__(
        self,
        model:     PickAndPlaceVisualizerModel,
        view:      PickAndPlaceVisualizerView,
        messaging: Optional[IMessagingService] = None,
    ):
        self._model   = model
        self._view    = view
        self._broker  = messaging
        self._bridge  = _Bridge()
        self._subs:   List[Tuple[str, Callable]] = []
        self._active  = False
        self._threads: List[Tuple[QThread, _Worker]] = []
        self._log_handler = _BridgeLogHandler(self._bridge)
        self._logger  = logging.getLogger(self.__class__.__name__)

        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.process_state.connect(self._on_process_state)
        self._bridge.log_record.connect(self._on_log_record)
        self._bridge.sim_result.connect(self._on_sim_result)
        self._bridge.workpiece_placed.connect(self._on_workpiece_placed)
        self._bridge.plane_reset.connect(self._on_plane_reset)

        self._view.run_simulation_requested.connect(self._on_run_simulation)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        self._active = True
        bounds = self._model.get_plane_bounds()
        self._view.set_plane_bounds(*bounds)
        logging.getLogger().addHandler(self._log_handler)

        # wire live process buttons
        self._view.start_process_requested.connect(self._on_start_process)
        self._view.stop_process_requested.connect(self._on_stop_process)
        self._view.pause_process_requested.connect(self._on_pause_process)
        self._view.reset_process_requested.connect(self._on_reset_process)

        if self._broker:
            self._subscribe()

    def _on_workpiece_placed(self, event) -> None:
        from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import PlacedItem
        if self._active:
            item = PlacedItem(
                workpiece_name=event.workpiece_name,
                gripper_id=event.gripper_id,
                plane_x=event.plane_x,
                plane_y=event.plane_y,
                width=event.width,
                height=event.height,
            )
            self._view.add_placed_item(item)
            self._view.append_log(
                f"[PLACED] {event.workpiece_name} gripper=G{event.gripper_id} "
                f"@ ({event.plane_x:.1f}, {event.plane_y:.1f})"
            )

    def _on_plane_reset(self) -> None:
        if self._active:
            self._view.reset_plane()
            self._view.append_log("[PLANE] Reset — new run started")

    def _on_start_process(self) -> None:
        self._model.start_process()

    def _on_stop_process(self) -> None:
        self._model.stop_process()

    def _on_pause_process(self) -> None:
        self._model.pause_process()

    def _on_reset_process(self) -> None:
        self._model.reset_process()


    def stop(self) -> None:
        self._active = False
        logging.getLogger().removeHandler(self._log_handler)
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                pass
        self._subs.clear()
        for thread, _ in self._threads:
            thread.quit()
            thread.wait()
        self._threads.clear()

    # ── Broker subscriptions ──────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE,
                  lambda msg: self._bridge.camera_frame.emit(msg.get("image")) if isinstance(msg, dict) else None)
        self._sub(ProcessTopics.state(ProcessID.PICK_AND_PLACE),
                  lambda e: self._bridge.process_state.emit(e.state.value))
        from src.shared_contracts.events.pick_and_place_events import PickAndPlaceTopics
        self._sub(PickAndPlaceTopics.WORKPIECE_PLACED,
                  lambda e: self._bridge.workpiece_placed.emit(e))
        self._sub(PickAndPlaceTopics.PLANE_RESET,
                  lambda _: self._bridge.plane_reset.emit())


    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    # ── Bridge slots (main thread) ─────────────────────────────────────

    def _on_camera_frame(self, frame) -> None:
        if frame is not None and self._active:
            try:
                self._view.update_camera_frame(frame)
            except Exception:
                pass

    def _on_process_state(self, state: str) -> None:
        if self._active:
            self._view.set_process_state(state)
            self._view.append_log(f"[PROCESS] State → {state.upper()}")

    def _on_log_record(self, text: str) -> None:
        if self._active:
            self._view.append_log(text)

    def _on_sim_result(self, result: SimResult) -> None:
        self._view.set_busy(False)
        self._view.set_simulation_result(result)
        if result.error:
            self._view.append_log(f"[SIM] ERROR: {result.error}")
        else:
            self._view.append_log(
                f"[SIM] Done — {len(result.matched)} matched, "
                f"{result.unmatched_count} unmatched, "
                f"{len(result.placements)} placed"
            )

    # ── Worker ────────────────────────────────────────────────────────

    def _on_run_simulation(self) -> None:
        if not self._active:
            return
        self._view.set_busy(True)
        self._view.append_log("[SIM] Running simulation…")

        thread = QThread()
        worker = _Worker(self._model.run_simulation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda r: self._bridge.sim_result.emit(r))
        worker.finished.connect(thread.quit)
        self._threads.append((thread, worker))
        thread.finished.connect(lambda: self._threads.remove(
            next((t for t in self._threads if t[0] is thread), (thread, worker))
        ) if (thread, worker) in self._threads else None)
        thread.start()