from __future__ import annotations

from functools import partial
from threading import Lock

from PyQt6.QtCore import QCoreApplication, QObject, QThread, QTimer, pyqtSignal

from src.applications.base.dashboard_camera_feed_mixin import DashboardCameraFeedMixin
from src.applications.base.dashboard_process_state_mixin import DashboardProcessStateMixin
from src.applications.base.broker_subscription_mixin import BrokerSubscriptionMixin
from src.applications.base.i_application_controller import IApplicationController
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.paint.applications.dashboard.model.paint_dashboard_model import (
    PaintDashboardModel,
)
from src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view import (
    PaintDashboardView,
)
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardCardState
from src.robot_systems.paint.processes.paint.dashboard_live_view_events import (
    PaintDashboardLiveViewTopics,
    PaintDashboardMessageTopics,
)
from src.shared_contracts.events.robot_events import RobotTopics
from src.shared_contracts.events.shell_events import ShellTopics
from src.shared_contracts.events.vision_events import CameraTopics


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        self.finished.emit(self._fn())


class _DashboardNoticeBridge(QObject):
    info_ready = pyqtSignal(str, str)
    warning_ready = pyqtSignal(str, str)
    unknown_workpiece_ready = pyqtSignal(str, str)


class PaintDashboardController(
    IApplicationController,
    BrokerSubscriptionMixin,
    DashboardCameraFeedMixin,
    DashboardProcessStateMixin,
):
    def _dashboard_warning_for_event(
        self,
        event_state: str,
        message: str,
    ) -> tuple[str, str] | None:
        if (
            event_state == "stopped"
            and str(message or "").strip().lower() == "all magazines are empty"
        ):
            return (
                self._t("All Magazines Empty"),
                self._t(
                    "No workpieces were found in any configured magazine. Refill the magazines and start again."
                ),
            )
        return super()._dashboard_warning_for_event(event_state, message)

    def __init__(self, model: PaintDashboardModel, view: PaintDashboardView, broker: IMessagingService):
        BrokerSubscriptionMixin.__init__(self)
        self._model = model
        self._view = view
        self._broker = broker
        self._active = False
        self._dashboard_live_view_paused = False
        self._workers: list[tuple[QThread, _Worker]] = []
        self._pending_auxiliary: dict[str, bool] = {}
        self._paint_head_pending = False
        self._paint_head_held_direction: str | None = None
        self._paint_head_held_units = 0
        self._production_start_pending = False
        timer_parent = self._view if isinstance(self._view, QObject) else None
        self._paint_head_hold_timer = QTimer(timer_parent)
        self._paint_head_hold_timer.timeout.connect(self._repeat_held_paint_head_adjust)
        self._status_timer = QTimer(timer_parent)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._refresh_dashboard_status)
        self._selected_camera = "primary_vision"
        self._camera_feed_visible = False
        self._auxiliary_camera_topic: str | None = None
        self._camera_frame_lock = Lock()
        self._latest_camera_frame = None
        self._camera_display_timer = QTimer(timer_parent)
        self._camera_display_timer.setInterval(100)
        self._camera_display_timer.timeout.connect(self._show_selected_camera_frame)
        self._init_dashboard_camera_feed()
        self._init_dashboard_process_state()
        self._dashboard_notice_bridge = _DashboardNoticeBridge()
        self._dashboard_notice_bridge.info_ready.connect(self._view.show_info)
        self._dashboard_notice_bridge.warning_ready.connect(self._view.show_warning_dialog)
        self._dashboard_notice_bridge.unknown_workpiece_ready.connect(
            self._view.show_unknown_workpiece_dialog
        )
        self._view.start_requested.connect(self._on_start)
        self._view.scan_again_requested.connect(self._on_scan_again)
        self._view.stop_requested.connect(self._on_stop)
        self._view.pause_requested.connect(self._on_pause)
        self._view.reset_requested.connect(self._on_reset)
        self._view.action_requested.connect(self._on_action)
        self._view.dashboard_shown.connect(self._refresh_workpiece_selection_indicator)
        self._view.language_changed.connect(self._retranslate)
        self._view.cable_relief_requested.connect(self._on_cable_relief)
        self._view.auxiliary_toggle_requested.connect(self._on_auxiliary_toggle)
        self._view.application_shortcut_requested.connect(self._on_application_shortcut)
        self._view.unmatched_paint_settings_requested.connect(
            self._on_unmatched_paint_settings
        )
        self._view.paint_head_adjust_requested.connect(self._on_paint_head_adjust)
        self._view.paint_head_adjust_released.connect(self._stop_held_paint_head_adjust)
        self._view.acceleration_scale_requested.connect(self._on_acceleration_scale)
        self._view.drying_mode_requested.connect(self._on_drying_mode)
        self._view.new_tray_requested.connect(self._on_new_tray)
        self._view.remove_plate_placement_requested.connect(self._on_remove_plate_placement)
        self._view.camera_selected.connect(self._on_camera_selected)
        self._view.camera_feed_visible.connect(self._on_camera_feed_visible)

    def load(self) -> None:
        self._active = True
        self._subscribe_dashboard_camera_feed()
        self._update_camera_feed_subscription()
        self._subscribe_dashboard_process_state()
        self._subscribe_dashboard_robot_state()
        self._subscribe_dashboard_live_view_state()
        self._subscribe_dashboard_messages()
        self._view.apply_dashboard_state(self._model.load())
        self._view.set_unmatched_paint_settings(
            self._model.get_unmatched_paint_settings()
        )
        self._view.set_acceleration_scale(self._model.get_acceleration_scale())
        self._view.set_paint_head_available(self._model.is_paint_head_available())
        self._run_background(self._model.get_auxiliary_states, self._on_auxiliary_states_loaded)
        self._view.set_drying_mode(self._model.get_drying_mode())
        self._refresh_plate_layout()
        self._load_application_shortcuts()
        self._retranslate()
        if self._status_timer.parent() is not None or QThread.currentThread().eventDispatcher() is not None:
            self._status_timer.start()
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        # The current pause is dashboard-local. Never carry a frozen preview
        # state across dashboard exit/re-entry. When acquisition leases are
        # introduced, this exit path must release the dashboard's lease too.
        self._dashboard_live_view_paused = False
        self._model.resume_vision_for_dashboard_exit()
        self._status_timer.stop()
        self._stop_held_paint_head_adjust()
        self._camera_display_timer.stop()
        self._unsubscribe_auxiliary_camera()
        self._unsubscribe_all()
        for thread, _worker in list(self._workers):
            thread.quit()
            thread.wait(1000)
        self._workers.clear()

    def _on_start(self) -> None:
        drying_mode = self._model.get_drying_mode()
        if drying_mode in {"auto", "demo"}:
            state = self._model.get_production_start_guard_state(drying_mode)
            if not bool(state.get("required", False)):
                self._view.apply_dashboard_state(self._model.start())
                return
            if not bool(state.get("available", False)):
                if self._confirm_start_guard_bypass(state):
                    self._view.apply_dashboard_state(self._model.start())
                    return
                self._view.show_warning(
                    str(state.get("title") or self._t("Production Start")),
                    str(state.get("message") or self._t("Production destination is unavailable.")),
                )
                return
            if bool(state.get("enabled", False)) and not bool(state.get("ready", False)):
                message = str(state.get("message") or self._t("Production destination is not ready."))
                self._view.show_warning(str(state.get("title") or self._t("Production Start")), message)
                return
            if not bool(state.get("ready", False)):
                confirmed = self._view.ask_production_start_confirmation(
                    str(state.get("title") or self._t("Production Start")),
                    str(state.get("prepare_prompt") or self._t("Prepare the production destination now?")),
                )
                if not confirmed:
                    if self._confirm_start_guard_bypass(state):
                        self._view.apply_dashboard_state(self._model.start())
                    return
                if self._production_start_pending:
                    return
                self._production_start_pending = True
                self._view.set_action_enabled("start", False)
                self._run_background(
                    partial(self._model.prepare_production_start, drying_mode),
                    self._on_production_start_prepared,
                )
                return
        self._view.apply_dashboard_state(self._model.start())

    def _on_production_start_prepared(self, result: object) -> None:
        self._production_start_pending = False
        if not self._view_ok():
            return
        if bool(getattr(result, "success", False)):
            self._view.apply_dashboard_state(self._model.start())
            return
        self._view.apply_dashboard_state(self._model.load())
        self._show_command_result(self._t("Drying Mode"), result)

    def _on_stop(self) -> None:
        self._view.apply_dashboard_state(self._model.stop_process())

    def _on_pause(self) -> None:
        self._view.apply_dashboard_state(self._model.toggle_pause())

    def _on_reset(self) -> None:
        self._view.apply_dashboard_state(self._model.reset_errors())

    def _on_scan_again(self) -> None:
        if self._model.retry_unmatched_workpiece():
            self._view.apply_dashboard_state(self._model.load())
        else:
            self._view.show_warning_dialog(
                self._t("Scan again unavailable"),
                self._t("The workpiece is no longer ready for recapture."),
            )

    def _on_unmatched_paint_settings(
        self,
        settings: dict | float,
        acceleration_percent: float | None = None,
        offset_mm: float | None = None,
    ) -> None:
        result = self._model.save_unmatched_paint_settings(
            settings,
            acceleration_percent,
            offset_mm,
        )
        if bool(getattr(result, "success", False)):
            # Re-read the config-service snapshot after persistence so the controls
            # reflect the same in-memory values consumed by the paint process.
            self._view.set_unmatched_paint_settings(
                self._model.get_unmatched_paint_settings()
            )
        self._show_command_result(self._t("Painting"), result)

    def _on_paint_head_adjust(self, direction: str, units: int) -> None:
        if direction not in {"more", "less"}:
            return
        self._paint_head_held_direction = direction
        self._paint_head_held_units = units
        self._paint_head_hold_timer.start(400)
        self._send_paint_head_adjust(direction, units)

    def _repeat_held_paint_head_adjust(self) -> None:
        direction = self._paint_head_held_direction
        if direction is None:
            return
        if not self._view_ok():
            self._stop_held_paint_head_adjust()
            return
        if self._paint_head_hold_timer.interval() != 150:
            self._paint_head_hold_timer.setInterval(150)
        self._send_paint_head_adjust(direction, self._paint_head_held_units)

    def _stop_held_paint_head_adjust(self) -> None:
        self._paint_head_hold_timer.stop()
        self._paint_head_held_direction = None
        self._paint_head_held_units = 0

    def _send_paint_head_adjust(self, direction: str, units: int) -> None:
        if self._paint_head_pending:
            return
        self._paint_head_pending = True
        self._view.set_paint_head_busy(True)
        self._run_background(
            partial(self._model.adjust_paint_head, direction, units),
            self._on_paint_head_adjusted,
        )

    def _on_paint_head_adjusted(self, result: object) -> None:
        self._paint_head_pending = False
        if not bool(getattr(result, "success", False)):
            self._stop_held_paint_head_adjust()
        if not self._view_ok():
            self._stop_held_paint_head_adjust()
            return
        self._view.set_paint_head_busy(False)
        self._view.set_paint_head_status(
            self._t(str(getattr(result, "message", "") or "Command failed.")),
            bool(getattr(result, "success", False)),
        )

    def _on_cable_relief(self) -> None:
        self._view.set_cable_relief_busy(True)
        self._run_background(self._model.relieve_cable, self._on_cable_relief_finished)

    def _on_acceleration_scale(self, scale_percent: float) -> None:
        result = self._model.save_acceleration_scale(scale_percent)
        if bool(getattr(result, "success", False)):
            self._view.set_acceleration_scale(self._model.get_acceleration_scale())
        self._show_command_result(self._t("Process Scaling"), result)

    def _on_auxiliary_toggle(self, device_id: str, enabled: bool) -> None:
        self._pending_auxiliary[device_id] = enabled
        self._view.set_auxiliary_busy(device_id, True)
        self._run_background(
            partial(self._model.set_auxiliary_enabled, device_id, enabled),
            self._on_auxiliary_finished,
        )

    def _on_auxiliary_states_loaded(self, states: object) -> None:
        if not self._view_ok() or not isinstance(states, dict):
            return
        for device_id, enabled in states.items():
            self._view.set_auxiliary_state(device_id, bool(enabled))

    def _on_drying_mode(self, mode: str) -> None:
        normalized_mode = str(mode).strip().lower()
        self._start_drying_mode_change(normalized_mode)

    def _start_drying_mode_change(self, mode: str) -> None:
        self._view.set_drying_mode_busy(True)
        self._run_background(
            partial(self._model.set_drying_mode, mode),
            self._on_drying_mode_finished,
        )

    def _confirm_start_guard_bypass(self, state: dict[str, object]) -> bool:
        if not bool(state.get("bypass_allowed", False)):
            return False
        return self._view.ask_production_start_confirmation(
            self._t("Development Mode"),
            str(state.get("bypass_prompt") or self._t("Continue without the production destination?")),
        )

    def _on_drying_mode_finished(self, result: object) -> None:
        if not self._view_ok():
            return
        self._view.set_drying_mode_busy(False)
        if bool(getattr(result, "success", False)):
            self._view.set_drying_mode(self._model.get_drying_mode())
            self._run_background(
                self._model.get_auxiliary_states,
                self._on_auxiliary_states_loaded,
            )
            self._refresh_plate_layout()
        self._show_command_result(self._t("Drying Mode"), result)

    def _on_new_tray(self) -> None:
        result = self._model.clear_plate_layout()
        self._refresh_plate_layout()
        self._show_command_result(self._t("New Tray"), result)

    def _on_remove_plate_placement(self, placement_id: int) -> None:
        result = self._model.remove_plate_placement(placement_id)
        self._view.clear_plate_selection()
        self._refresh_plate_layout()
        self._show_command_result(self._t("Remove Workpiece"), result)

    def _refresh_plate_layout(self) -> None:
        self._view.set_plate_layout_state(self._model.get_plate_layout_state())

    def _on_cable_relief_finished(self, result: object) -> None:
        if not self._view_ok():
            return
        self._view.set_cable_relief_busy(False)
        self._show_command_result(self._t("Cable Relief"), result)

    def _on_auxiliary_finished(self, result: object) -> None:
        if not self._view_ok():
            return
        device_id = str(getattr(result, "device_id", "") or "")
        desired = self._pending_auxiliary.pop(device_id, False)
        success = bool(getattr(result, "success", False))
        self._view.set_auxiliary_state(device_id, desired if success else not desired)
        self._view.set_auxiliary_busy(device_id, False)
        self._show_command_result(self._t("Manual Control"), result)

    def _show_command_result(self, title: str, result: object) -> None:
        message = str(getattr(result, "message", "") or self._t("Command failed."))
        if bool(getattr(result, "success", False)):
            self._view.show_info(title, message)
        else:
            self._view.show_warning(title, message)

    def _load_application_shortcuts(self) -> None:
        if not self._view.application_shortcuts_enabled:
            return
        shortcuts = self._broker.request(
            ShellTopics.VISIBLE_APPLICATIONS,
            {"exclude": ["PaintDashboard"]},
        )
        if not isinstance(shortcuts, (list, tuple)):
            return
        selected_names = set(self._view.shortcut_application_names)
        if selected_names:
            shortcuts = [item for item in shortcuts if item.app_name in selected_names]
        self._view.set_application_shortcuts(list(shortcuts))

    def _on_application_shortcut(self, app_name: str) -> None:
        self._broker.publish(ShellTopics.NAVIGATE, {"app": app_name})

    def _subscribe_dashboard_robot_state(self) -> None:
        self._subscribe(RobotTopics.STATE, self._on_dashboard_robot_state_raw)

    def _subscribe_dashboard_live_view_state(self) -> None:
        self._subscribe(PaintDashboardLiveViewTopics.STATE, self._on_dashboard_live_view_state_raw)

    def _subscribe_dashboard_messages(self) -> None:
        self._subscribe(PaintDashboardMessageTopics.MESSAGE, self._on_dashboard_message_raw)

    def _on_dashboard_message_raw(self, event: object) -> None:
        source_title = str(getattr(event, "title", "") or "")
        title = self._t(source_title)
        message = self._t(str(getattr(event, "message", "") or ""))
        if str(getattr(event, "level", "info")).lower() == "warning":
            if source_title == "Unknown Workpiece":
                self._dashboard_notice_bridge.unknown_workpiece_ready.emit(title, message)
            else:
                self._dashboard_notice_bridge.warning_ready.emit(title, message)
        else:
            self._dashboard_notice_bridge.info_ready.emit(title, message)

    def _on_dashboard_live_view_state_raw(self, event: object) -> None:
        self._dashboard_live_view_paused = bool(getattr(event, "paused", False))
        if not self._dashboard_live_view_paused:
            return
        image = getattr(event, "image", None)
        if image is None or not self._view_ok() or self._selected_camera != "primary_vision":
            return
        self._dashboard_camera_bridge.frame_ready.emit({"image": image})

    def _dashboard_camera_feed_updates_enabled(self) -> bool:
        return not self._dashboard_live_view_paused and self._selected_camera == "primary_vision"

    def _on_dashboard_camera_frame(self, image: object) -> None:
        if self._selected_camera == "primary_vision":
            super()._on_dashboard_camera_frame(image)

    def _on_camera_selected(self, role: str) -> None:
        self._selected_camera = str(role)
        self._update_camera_feed_subscription()

    def _on_camera_feed_visible(self, _visible: bool) -> None:
        self._camera_feed_visible = bool(_visible)
        self._update_camera_feed_subscription()

    def _update_camera_feed_subscription(self) -> None:
        self._unsubscribe_auxiliary_camera()
        with self._camera_frame_lock:
            self._latest_camera_frame = None
        if (
            self._active
            and self._selected_camera != "primary_vision"
            and self._camera_feed_visible
        ):
            self._auxiliary_camera_topic = CameraTopics.frame(self._selected_camera)
            self._broker.subscribe(self._auxiliary_camera_topic, self._on_auxiliary_camera_frame)
            self._camera_display_timer.start()
        else:
            self._camera_display_timer.stop()

    def _unsubscribe_auxiliary_camera(self) -> None:
        if self._auxiliary_camera_topic is not None:
            self._broker.unsubscribe(
                self._auxiliary_camera_topic,
                self._on_auxiliary_camera_frame,
            )
            self._auxiliary_camera_topic = None

    def _on_auxiliary_camera_frame(self, message: object) -> None:
        if isinstance(message, dict):
            frame = message.get("image")
            if frame is not None:
                with self._camera_frame_lock:
                    self._latest_camera_frame = frame

    def _show_selected_camera_frame(self) -> None:
        with self._camera_frame_lock:
            frame = self._latest_camera_frame
            self._latest_camera_frame = None
        if frame is not None and self._view_ok() and self._camera_feed_visible:
            self._view.set_trajectory_image({"image": frame})

    def _on_dashboard_robot_state_raw(self, _event: object) -> None:
        if not self._active:
            return
        state = self._model.load()
        event_state = str(getattr(_event, "state", "") or "").lower()
        if event_state == "disconnected":
            extra = getattr(_event, "extra", {}) or {}
            last_error = extra.get("last_error") if isinstance(extra, dict) else None
            state.card_states[1] = DashboardCardState(
                "Robot Status",
                "DISCONNECTED",
                self._robot_connection_note(last_error),
            )
        elif event_state == "starting":
            extra = getattr(_event, "extra", {}) or {}
            startup = extra.get("startup") if isinstance(extra, dict) else {}
            state.card_states[1] = DashboardCardState(
                "Robot Status",
                "STARTING",
                self._robot_startup_note(startup if isinstance(startup, dict) else {}),
            )
        elif event_state in {"error", "fault"}:
            extra = getattr(_event, "extra", {}) or {}
            last_error = extra.get("last_error") if isinstance(extra, dict) else None
            state.card_states[1] = DashboardCardState(
                "Robot Status",
                "ERROR",
                self._robot_connection_note(last_error),
            )
        self._dashboard_process_bridge.state_ready.emit(state)

    @staticmethod
    def _robot_connection_note(last_error: object) -> str:
        message = str(last_error or "").strip()
        if not message:
            return "Robot bridge is disconnected"
        lowered = message.lower()
        if "connection refused" in lowered or "failed to establish a new connection" in lowered:
            return "ROS2 bridge is not reachable"
        if "timed out" in lowered or "timeout" in lowered:
            return "ROS2 bridge health check timed out"
        if "max retries exceeded" in lowered:
            return "ROS2 bridge is not responding"
        return "Robot bridge is disconnected"

    @staticmethod
    def _robot_startup_note(startup: dict) -> str:
        message = str(startup.get("message") or "").strip()
        if message:
            return message
        phase = str(startup.get("phase") or "").strip()
        if phase:
            return f"Runtime startup phase: {phase}"
        return "Robot runtime is starting"

    def _refresh_dashboard_status(self) -> None:
        if not self._active:
            return
        try:
            self._view.apply_dashboard_state(self._model.load())
            self._refresh_workpiece_selection_indicator()
            if self._model.get_drying_mode() == "manual":
                self._refresh_plate_layout()
        except RuntimeError:
            self.stop()

    def _refresh_workpiece_selection_indicator(self) -> None:
        settings = self._model.get_unmatched_paint_settings()
        self._view.set_workpiece_selection_indicator(
            bool(settings.get("matching_enabled", False)),
            settings.get("selected_workpiece_count"),
        )

    def _on_action(self, action_id: str) -> None:
        if action_id == "select_workpieces":
            self._broker.publish(ShellTopics.NAVIGATE, {"app": "WorkpieceLibrary"})
            return
        if action_id != "debug_contour_transform":
            return
        self._view.set_action_enabled("debug_contour_transform", False)
        self._view.set_notes([self._t("Capturing latest contour and building pixel-to-mm debug plot...")])
        self._run_background(
            self._model.capture_latest_contour_transform_debug,
            self._on_contour_transform_debug_finished,
        )

    def _run_background(self, fn, on_done) -> None:
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(partial(self._cleanup_finished_worker, thread))
        thread.finished.connect(thread.deleteLater)
        self._workers.append((thread, worker))
        thread.start()

    def _cleanup_finished_worker(self, finished_thread: QThread) -> None:
        self._workers = [pair for pair in self._workers if pair[0] is not finished_thread]

    def _on_contour_transform_debug_finished(self, result) -> None:
        if not self._view_ok():
            return
        self._view.set_action_enabled("debug_contour_transform", True)
        self._view.apply_dashboard_state(self._model.load())
        if getattr(result, "success", False) and getattr(result, "image_path", None):
            self._view.show_debug_plot(
                self._t("Latest Contour Pixel-to-MM Transform"),
                result.image_path,
                result.message,
            )
        else:
            self._view.show_warning(
                self._t("Latest Contour Pixel-to-MM Transform"),
                getattr(result, "message", self._t("Failed to create contour transform plot.")),
            )

    def _retranslate(self) -> None:
        if not self._view_ok():
            return
        for action in getattr(self._view, "action_button_configs", []):
            self._view.set_action_button_text(action.action_id, self._t(action.label))
        try:
            state = self._model.load()
        except Exception:
            return
        self._view.set_pause_label(self._t(state.pause_label))

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("PaintDashboard", text)
        return translated or text

    def _view_ok(self) -> bool:
        if not self._active:
            return False
        try:
            _ = self._view.isVisible()
            return True
        except RuntimeError:
            return False
