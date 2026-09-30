import logging
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from threading import Lock

import cv2
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap

from src.applications.base.i_application_controller import IApplicationController
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.paint.component_ids import ProcessID
from src.shared_contracts.events.process_events import ProcessStateEvent, ProcessTopics
from src.shared_contracts.events.vision_events import CameraTopics
from ..model.paint_adjustment_model import PaintAdjustmentModel
from ..service.i_paint_adjustment_service import PaintAdjustmentOptions
from ..view.paint_adjustment_view import PaintAdjustmentView


class _AdjustmentRelay(QObject):
    finished = pyqtSignal(object)

    def __init__(self, on_finished) -> None:
        super().__init__()
        self._on_finished = on_finished
        self.finished.connect(self._dispatch)

    @pyqtSlot(object)
    def _dispatch(self, result: object) -> None:
        self._on_finished(result)


class PaintAdjustmentController(IApplicationController):
    """Display the auxiliary stream and dispatch serial I/O off the UI thread."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        model: PaintAdjustmentModel,
        view: PaintAdjustmentView,
        messaging: IMessagingService,
    ) -> None:
        self._model = model
        self._view = view
        self._messaging = messaging
        self._topic: str | None = None
        self._frame_lock = Lock()
        self._latest_frame = None
        self._ticks_without_frame = 0
        self._stopped = False
        self._action_pending = False
        self._configuration_available: bool | None = None
        self._dial_config = None
        self._position_read_pending = False
        self._cycle_start_pending = False
        self._process_topic = ProcessTopics.state(ProcessID.MAIN_PROCESS)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="PaintHeadIO")
        self._relay = _AdjustmentRelay(self._on_adjustment_finished)
        self._position_relay = _AdjustmentRelay(self._on_position_read_finished)
        self._cycle_relay = _AdjustmentRelay(self._on_cycle_start_finished)
        self._process_relay = _AdjustmentRelay(self._apply_process_state)
        self._timer = QTimer(view)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._display_latest_frame)
        self._settings_timer = QTimer(view)
        self._settings_timer.setInterval(250)
        self._settings_timer.timeout.connect(self._refresh_preset_configuration)
        self._settings_timer.timeout.connect(self._refresh_adjustment_status)
        self._hold_timer = QTimer(view)
        self._hold_timer.timeout.connect(self._repeat_held_adjustment)
        self._held_direction: str | None = None
        self._held_units = 0
        self._drag_active = False
        self._drag_target: int | None = None
        self._last_drag_sent: int | None = None
        self._view.more_paint_requested.connect(self._on_more_paint)
        self._view.less_paint_requested.connect(self._on_less_paint)
        self._view.adjustment_released.connect(self._stop_held_adjustment)
        self._view.dial_drag_started.connect(self._on_dial_drag_started)
        self._view.position_dragged.connect(self._on_drag_position)
        self._view.position_requested.connect(self._on_position)
        self._view.refresh_position_requested.connect(self._request_position_read)
        self._view.single_cycle_requested.connect(self._request_single_cycle)
        self._view.next_section_requested.connect(self._request_next_section)
        self._view.finish_dropoff_requested.connect(self._request_finish_dropoff)

    def load(self) -> None:
        self._topic = CameraTopics.frame(self._model.load())
        self._messaging.subscribe(self._topic, self._on_frame)
        self._messaging.subscribe(self._process_topic, self._on_process_state)
        self._view.set_cycle_state(self._model.get_paint_cycle_state())
        options = self._model.get_adjustment_options()
        self._view.set_adjustment_options(
            options.length_mm, options.paint_axis_offset_mm, options.perpendicular_axis_offset_mm
        )
        self._refresh_adjustment_status()
        self._refresh_preset_configuration()
        self._request_position_read()
        self._timer.start()
        self._settings_timer.start()

    def stop(self) -> None:
        self._stopped = True
        self._timer.stop()
        self._settings_timer.stop()
        self._stop_held_adjustment()
        self._drag_active = False
        self._drag_target = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        if self._topic is not None:
            self._messaging.unsubscribe(self._topic, self._on_frame)
            self._topic = None
        self._messaging.unsubscribe(self._process_topic, self._on_process_state)
        with self._frame_lock:
            self._latest_frame = None

    def _on_frame(self, message: object) -> None:
        if not isinstance(message, dict):
            return
        frame = message.get("image")
        if frame is not None:
            with self._frame_lock:
                self._latest_frame = frame

    def _on_process_state(self, event: object) -> None:
        if not self._stopped and isinstance(event, ProcessStateEvent):
            self._process_relay.finished.emit(event)

    def _apply_process_state(self, event: object) -> None:
        if not self._stopped:
            self._view.set_cycle_state(event.state.value, event.message)

    def _refresh_adjustment_status(self) -> None:
        phase, travelled, total = self._model.get_adjustment_status()
        self._view.set_adjustment_status(phase, travelled, total)

    def _request_single_cycle(self, length: float, axis: float, perpendicular: float) -> None:
        if self._stopped or self._cycle_start_pending:
            return
        if self._model.get_paint_cycle_state() not in {"idle", "stopped"}:
            self._view.set_cycle_state(self._model.get_paint_cycle_state())
            return
        options = PaintAdjustmentOptions(length, axis, perpendicular)
        self._submit_cycle_command("start", self._model.start_adjustment_cycle, options)

    def _request_next_section(self, length: float, axis: float, perpendicular: float) -> None:
        options = PaintAdjustmentOptions(length, axis, perpendicular)
        self._submit_cycle_command("next", self._model.paint_next_section, options)

    def _request_finish_dropoff(self) -> None:
        self._submit_cycle_command("finish", self._model.finish_adjustment_cycle)

    def _submit_cycle_command(self, label: str, command, *args) -> None:
        if self._stopped or self._cycle_start_pending:
            return
        self._cycle_start_pending = True
        self._view.set_cycle_start_pending()
        future = self._executor.submit(command, *args)
        future.add_done_callback(partial(self._emit_cycle_start_result, label))

    def _emit_cycle_start_result(self, label: str, future: Future) -> None:
        if self._stopped:
            return
        try:
            result = (label, bool(future.result()), None)
        except Exception as error:
            self._logger.exception("Paint adjustment %s command failed", label)
            result = (label, False, str(error))
        self._cycle_relay.finished.emit(result)

    def _on_cycle_start_finished(self, result: object) -> None:
        if self._stopped:
            return
        self._cycle_start_pending = False
        label, started, error = result
        if error is not None:
            self._view.set_cycle_state(self._model.get_paint_cycle_state(), error)
        elif started:
            self._view.set_cycle_state(self._model.get_paint_cycle_state())
            self._refresh_adjustment_status()
        else:
            self._view.set_cycle_state(
                self._model.get_paint_cycle_state(),
                f"{label} is not available in the current phase",
            )

    def _refresh_preset_configuration(self) -> None:
        try:
            config = self._model.get_dial_config()
        except (KeyError, TypeError, ValueError):
            config = None
        available = config is not None
        if not available:
            self._stop_held_adjustment()
        if available != self._configuration_available:
            self._view.set_paint_head_available(available)
            self._configuration_available = available
        if config != self._dial_config:
            self._drag_active = False
            self._drag_target = None
            self._last_drag_sent = None
            should_read = (
                config is not None and config.enabled
                and self._dial_config is not None and not self._dial_config.enabled
            )
            if config is None:
                self._view.set_dial_config(0, 1, 0, False)
            else:
                self._view.set_dial_config(
                    config.minimum, config.spacing, config.count, config.enabled
                )
            self._dial_config = config
            if should_read:
                self._request_position_read()

    def _request_position_read(self) -> None:
        if (
            self._stopped or self._position_read_pending or self._action_pending
            or self._dial_config is None or not self._dial_config.enabled
        ):
            return
        self._position_read_pending = True
        self._view.set_position_pending()
        future = self._executor.submit(self._model.read_current_position)
        future.add_done_callback(self._emit_position_read_result)

    def _emit_position_read_result(self, future: Future) -> None:
        if self._stopped:
            return
        try:
            result = (future.result(), None)
        except Exception as error:
            self._logger.exception("Paint-head position read failed")
            result = (None, str(error))
        self._position_relay.finished.emit(result)

    def _on_position_read_finished(self, result: object) -> None:
        if self._stopped:
            return
        self._position_read_pending = False
        value, error = result
        if error is None:
            self._view.set_confirmed_position(value)
        else:
            self._view.set_position_error(error)

    def _display_latest_frame(self) -> None:
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
        if frame is None:
            self._ticks_without_frame += 1
            if self._ticks_without_frame == 20:
                self._view.set_waiting_for_camera()
            return
        self._ticks_without_frame = 0
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
        self._view.set_frame(QPixmap.fromImage(image))

    def _on_more_paint(self, units: int) -> None:
        self._start_held_adjustment("more", units)

    def _on_less_paint(self, units: int) -> None:
        self._start_held_adjustment("less", units)

    def _start_held_adjustment(self, direction: str, units: int) -> None:
        if self._stopped or self._action_pending or self._dial_config is None:
            return
        self._held_direction = direction
        self._held_units = units
        self._hold_timer.start(400)
        self._request_command(direction, self._model.adjust_paint_by_register_units, direction, units)

    def _repeat_held_adjustment(self) -> None:
        if self._held_direction is None:
            return
        if self._hold_timer.interval() != 150:
            self._hold_timer.setInterval(150)
        if not self._action_pending:
            direction = self._held_direction
            self._request_command(
                direction, self._model.adjust_paint_by_register_units,
                direction, self._held_units,
            )

    def _stop_held_adjustment(self) -> None:
        self._hold_timer.stop()
        self._held_direction = None
        self._held_units = 0
        if self._action_pending:
            self._view.set_action_pending()

    def _on_position(self, position: int) -> None:
        self._drag_active = False
        self._drag_target = position
        self._send_latest_drag_target()

    def _on_dial_drag_started(self) -> None:
        self._drag_active = True
        self._drag_target = None
        self._last_drag_sent = None

    def _on_drag_position(self, position: int) -> None:
        if self._stopped or self._dial_config is None:
            return
        self._drag_active = True
        self._drag_target = position
        self._send_latest_drag_target()

    def _send_latest_drag_target(self) -> None:
        if self._stopped or self._action_pending or self._drag_target is None:
            return
        position = self._drag_target
        self._drag_target = None
        if position == self._last_drag_sent:
            return
        self._last_drag_sent = position
        self._request_command(f"position {position}", self._model.go_to_position, position)

    def _request_command(self, label: str, command, *args) -> None:
        if self._stopped or self._action_pending:
            return
        self._action_pending = True
        self._view.set_action_pending(
            self._held_direction, keep_dial_enabled=self._drag_active
        )
        self._logger.info("Paint-head command requested: %s, args=%s", label, args)
        future = self._executor.submit(command, *args)
        future.add_done_callback(partial(self._emit_adjustment_result, label))

    def _emit_adjustment_result(self, label: str, future: Future) -> None:
        if self._stopped:
            return
        try:
            result = (label, future.result(), None)
        except Exception as error:
            self._logger.exception("Paint-head command failed: %s", label)
            result = (label, None, str(error))
        self._relay.finished.emit(result)

    def _on_adjustment_finished(self, result: object) -> None:
        if self._stopped:
            return
        label, value, error = result
        self._action_pending = False
        if error is None:
            self._logger.info(
                "Paint-head command complete: %s, value=%d, wrote=%s",
                label, value.value, value.wrote,
            )
            self._view.set_action_result(
                value.value, value.register, wrote=value.wrote, relative=value.relative
            )
            self._send_latest_drag_target()
        else:
            self._stop_held_adjustment()
            self._drag_active = False
            self._drag_target = None
            self._view.set_action_error(error)
