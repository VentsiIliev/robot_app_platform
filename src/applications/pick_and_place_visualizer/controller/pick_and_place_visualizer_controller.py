from __future__ import annotations
import logging
import logging.handlers
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.pick_and_place_visualizer.model.pick_and_place_visualizer_model import (
    PickAndPlaceVisualizerModel,
)
from src.applications.pick_and_place_visualizer.view.pick_and_place_visualizer_view import (
    PickAndPlaceVisualizerView,
)
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.process_ids import ProcessID
from src.shared_contracts.events.process_events import ProcessTopics
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(QObject):
    camera_frame     = pyqtSignal(object)
    process_state    = pyqtSignal(str)
    log_record       = pyqtSignal(str)
    workpiece_placed = pyqtSignal(object)
    plane_reset      = pyqtSignal()
    match_result     = pyqtSignal(object)
    diagnostics      = pyqtSignal(object)


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
        self._log_handler = _BridgeLogHandler(self._bridge)
        self._logger  = logging.getLogger(self.__class__.__name__)

        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.process_state.connect(self._on_process_state)
        self._bridge.log_record.connect(self._on_log_record)
        self._bridge.workpiece_placed.connect(self._on_workpiece_placed)
        self._bridge.plane_reset.connect(self._on_plane_reset)
        self._bridge.match_result.connect(self._on_match_result)
        self._bridge.diagnostics.connect(self._on_diagnostics)

        self._view.simulation_toggled.connect(self._on_simulation_toggled)
        self._view.step_mode_toggled.connect(self._on_step_mode_toggled)
        self._view.step_process_requested.connect(self._on_step_process)
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
        self._view.set_step_mode(self._model.is_step_mode_enabled())

        if self._broker:
            self._subscribe()

        self._view.set_process_state(self._model.get_process_state())

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

    def _on_match_result(self, items) -> None:
        if not self._active:
            return
        from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import MatchedItem
        matched = [
            MatchedItem(
                workpiece_name=info.workpiece_name,
                workpiece_id=info.workpiece_id,
                gripper_id=info.gripper_id,
                orientation=info.orientation,
            )
            for info in items
        ]
        self._view.set_matched_items(matched)

    def _on_plane_reset(self) -> None:
        if self._active:
            self._view.reset_plane()
            self._view.set_matched_items([])
            self._view.append_log("[PLANE] Reset — new run started")

    def _on_start_process(self) -> None:
        self._model.start_process()

    def _on_stop_process(self) -> None:
        self._model.stop_process()

    def _on_pause_process(self) -> None:
        self._model.pause_process()

    def _on_reset_process(self) -> None:
        self._model.reset_process()

    def _on_step_mode_toggled(self, value: bool) -> None:
        self._model.set_step_mode(value)
        self._view.append_log(f"[STEP] Step mode {'ON' if value else 'OFF'}")

    def _on_step_process(self) -> None:
        try:
            self._model.step_process()
        except Exception as exc:
            self._view.append_log(f"[STEP] {exc}")

    def stop(self) -> None:
        self._active = False
        logging.getLogger().removeHandler(self._log_handler)
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                import traceback
                traceback.print_exc()
        self._subs.clear()

    # ── Broker subscriptions ──────────────────────────────────────────

    def _subscribe(self) -> None:
        from src.shared_contracts.events.pick_and_place_events import PickAndPlaceTopics
        self._sub(VisionTopics.LATEST_IMAGE, self._handle_latest_image)
        self._sub(ProcessTopics.state(ProcessID.PICK_AND_PLACE), self._handle_process_state_event)
        self._sub(PickAndPlaceTopics.WORKPIECE_PLACED, self._handle_workpiece_placed)
        self._sub(PickAndPlaceTopics.PLANE_RESET, self._handle_plane_reset)
        self._sub(PickAndPlaceTopics.MATCH_RESULT, self._handle_match_result)
        self._sub(PickAndPlaceTopics.DIAGNOSTICS, self._handle_diagnostics)


    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    def _handle_latest_image(self, msg) -> None:
        if isinstance(msg, dict):
            self._bridge.camera_frame.emit(msg.get("image"))

    def _handle_process_state_event(self, event) -> None:
        self._bridge.process_state.emit(event.state.value)

    def _handle_workpiece_placed(self, event) -> None:
        self._bridge.workpiece_placed.emit(event)

    def _handle_plane_reset(self, _event) -> None:
        self._bridge.plane_reset.emit()

    def _handle_match_result(self, items) -> None:
        self._bridge.match_result.emit(items)

    def _handle_diagnostics(self, event) -> None:
        snapshot = getattr(event, "snapshot", event)
        self._bridge.diagnostics.emit(snapshot)

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

    def _on_simulation_toggled(self, value: bool) -> None:
        self._model.set_simulation(value)
        self._view.append_log(f"[SIM] Simulation mode {'ON' if value else 'OFF'}")

    def _on_diagnostics(self, snapshot: dict) -> None:
        if not self._active or not isinstance(snapshot, dict):
            return
        self._view.set_step_mode(bool(snapshot.get("step_mode", False)))
        self._view.set_step_status(
            checkpoint=snapshot.get("current_checkpoint"),
            waiting=bool(snapshot.get("waiting_for_step", False)),
            step_budget=int(snapshot.get("step_budget", 0) or 0),
            current_workpiece=snapshot.get("current_workpiece_name"),
        )
