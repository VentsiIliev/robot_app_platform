from __future__ import annotations

import logging
import math
import threading
from time import monotonic, perf_counter, sleep
from typing import Callable, Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.robot_systems.paint.processes.paint.execution_control import PaintExecutionControl
from src.robot_systems.paint.processes.paint.dashboard_live_view_events import (
    PaintDashboardLiveViewEvent,
    PaintDashboardLiveViewTopics,
)
from src.robot_systems.paint.processes.paint.execution_machine import (
    PaintExecutionContext,
    PaintExecutionMachineFactory,
)
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE
from src.robot_systems.paint.processes.paint.config import (
    scale_paint_process_accelerations,
)

_logger = logging.getLogger(__name__)


class PaintProductionService:
    """Own the end-to-end paint production flow outside the editor UI."""
    def __init__(
        self,
        *,
        workpiece_preparation_service,
        capture_snapshot_service,
        path_preparation_service,
        path_executor,
        vacuum_pump: Optional[IVacuumPumpController] = None,
        paint_process_config_service=None,
        magazine_load_service=None,
        navigation_service=None,
        vision_service=None,
        messaging_service=None,
    ) -> None:
        """Store the services needed to capture, prepare, plan, and execute one paint cycle."""
        self._workpiece_preparation = workpiece_preparation_service
        self._capture_snapshot_service = capture_snapshot_service
        self._path_preparation_service = path_preparation_service
        self._path_executor = path_executor
        self._vacuum_pump = vacuum_pump
        self._paint_process_config_service = paint_process_config_service
        self._magazine_load_service = magazine_load_service
        self._navigation_service = navigation_service
        self._vision_service = vision_service
        self._messaging_service = messaging_service
        self._brightness_locked = False
        self._paint_control = PaintExecutionControl()
        self._active_context_lock = threading.Lock()
        self._active_execution_context: PaintExecutionContext | None = None
        self._prepositioned_start_group: str | None = None

    def pause_current_phase(self) -> None:
        pause_load = getattr(self._magazine_load_service, "pause_current_load", None)
        if callable(pause_load):
            pause_load()
        with self._active_context_lock:
            context = self._active_execution_context
        if context is not None:
            context.run_allowed.clear()
        self._paint_control.request_pause()
        self._stop_active_magazine_navigation_motion()
        pause_execution = getattr(self._path_executor, "pause_current_execution", None)
        if callable(pause_execution):
            pause_execution()

    def resume_current_phase(self) -> None:
        self._clear_prepositioned_start_group()
        resume_load = getattr(self._magazine_load_service, "resume_current_load", None)
        if callable(resume_load):
            resume_load()
        with self._active_context_lock:
            context = self._active_execution_context
        if context is not None:
            context.run_allowed.set()
        self._paint_control.resume()

    def stop_current_phase(self) -> None:
        self._clear_prepositioned_start_group()
        stop_load = getattr(self._magazine_load_service, "stop_current_load", None)
        if callable(stop_load):
            stop_load()
        with self._active_context_lock:
            context = self._active_execution_context
        if context is not None:
            context.stop_event.set()
            context.run_allowed.set()
        self._paint_control.request_stop()

    def run_once(self, stop_requested: Optional[Callable[[], bool]] = None) -> tuple[bool, str]:
        """Run production once, or repeat from the active source until no workpiece is found."""
        self._clear_prepositioned_start_group()
        should_stop = stop_requested or (lambda: False)
        self._paint_control.reset()
        process_config_result = self._get_process_config()

        if not process_config_result[0]:
            return False, process_config_result[1]

        process_config = process_config_result[2]
        magazine_config = process_config.magazine_load if process_config is not None else None
        run_while_found = bool(getattr(process_config, "run_while_workpiece_found", False))

        if self._magazine_load_service is not None and magazine_config is not None and magazine_config.enabled:
            if run_while_found:
                return self._run_magazine_loop(magazine_config, process_config, should_stop)

            ok, msg = self._run_single_cycle(
                should_stop,
                process_config=process_config,
                magazine_config=magazine_config,
                cycle_index=1,
            )

            if not ok and msg == NO_WORKPIECE_AT_MAGAZINE:
                return True, NO_WORKPIECE_AT_MAGAZINE
            return ok, msg

        if run_while_found and magazine_config is not None:
            return self._run_manual_loop(magazine_config, process_config, should_stop)

        if magazine_config is not None:
            ok, msg = self._move_to_calibration_before_manual_cycle(magazine_config, should_stop)
            if not ok:
                return False, msg
        return self._run_single_cycle(
            should_stop,
            process_config=process_config,
            magazine_config=None,
            cycle_index=1,
        )

    def _run_manual_loop(self, magazine_config, process_config, should_stop: Callable[[], bool]) -> tuple[bool, str]:
        total_start = perf_counter()
        completed_cycles = 0
        while not should_stop():
            ok, msg = self._move_to_calibration_before_manual_cycle(magazine_config, should_stop)
            if not ok:
                self._log_phase_timing(
                    "manual_loop_total",
                    total_start,
                    success=False,
                    completed_cycles=completed_cycles,
                )
                return False, msg
            ok, msg = self._run_single_cycle(
                should_stop,
                process_config=process_config,
                magazine_config=None,
                cycle_index=completed_cycles + 1,
                repeats_after_success=True,
            )
            if not ok and msg == "No usable contour detected":
                self._log_phase_timing(
                    "manual_loop_total",
                    total_start,
                    success=True,
                    completed_cycles=completed_cycles,
                )
                if completed_cycles == 0:
                    return True, "No usable contour detected"
                return True, f"No workpiece detected after {completed_cycles} paint cycle(s)"
            if not ok and msg == "Drop-off plate is full":
                return True, msg
            if not ok:
                self._log_phase_timing(
                    "manual_loop_total",
                    total_start,
                    success=False,
                    completed_cycles=completed_cycles,
                )
                return False, msg
            completed_cycles += 1
            if msg == "Drop-off plate has no space for another workpiece of the same footprint":
                return True, msg
        self._log_phase_timing(
            "manual_loop_total",
            total_start,
            success=False,
            stopped=True,
            completed_cycles=completed_cycles,
        )
        return False, "Paint process stopped"

    def _run_magazine_loop(self, magazine_config, process_config, should_stop: Callable[[], bool]) -> tuple[bool, str]:
        total_start = perf_counter()
        completed_cycles = 0
        while not should_stop():
            ok, msg = self._run_single_cycle(
                should_stop,
                process_config=process_config,
                magazine_config=magazine_config,
                cycle_index=completed_cycles + 1,
                repeats_after_success=True,
            )

            if not ok and msg == NO_WORKPIECE_AT_MAGAZINE:
                self._log_phase_timing(
                    "magazine_loop_total",
                    total_start,
                    success=True,
                    completed_cycles=completed_cycles,
                )
                if completed_cycles == 0:
                    return True, NO_WORKPIECE_AT_MAGAZINE
                return True, f"Magazine empty after {completed_cycles} paint cycle(s)"
            if not ok and msg == "Drop-off plate is full":
                return True, msg
            if not ok:
                self._log_phase_timing(
                    "magazine_loop_total",
                    total_start,
                    success=False,
                    completed_cycles=completed_cycles,
                )
                return False, msg
            completed_cycles += 1
            if msg == "Drop-off plate has no space for another workpiece of the same footprint":
                return True, msg
        self._log_phase_timing(
            "magazine_loop_total",
            total_start,
            success=False,
            stopped=True,
            completed_cycles=completed_cycles,
        )
        return False, "Paint process stopped"

    def _run_single_cycle(
        self,
        should_stop: Callable[[], bool],
        *,
        process_config,
        magazine_config,
        cycle_index: int,
        repeats_after_success: bool = False,
    ) -> tuple[bool, str]:
        context = PaintExecutionContext(
            production_service=self,
            stop_requested=should_stop,
            control=self._paint_control,
            process_config=process_config,
            magazine_config=magazine_config,
            cycle_index=cycle_index,
            repeats_after_success=repeats_after_success,
            total_started_at=perf_counter(),
        )
        with self._active_context_lock:
            self._active_execution_context = context
        try:
            machine = PaintExecutionMachineFactory().build(context)
            machine.start_execution()
        finally:
            self._log_execution_state_timing(context)
            with self._active_context_lock:
                if self._active_execution_context is context:
                    self._active_execution_context = None

        snapshot = machine.get_snapshot()
        if snapshot.last_error is not None:
            self._clear_prepositioned_start_group()
            self._restore_brightness()
            self._set_dashboard_live_view_paused(False, reason="paint cycle finished")
            return False, snapshot.last_error

        return context.result_ok, context.result_message

    def _next_cycle_start_target(self, ctx: PaintExecutionContext) -> dict | None:
        if not ctx.repeats_after_success:
            return None
        magazine = ctx.magazine_config
        configured_magazine = magazine or getattr(ctx.process_config, "magazine_load", None)
        if magazine is not None and bool(getattr(magazine, "enabled", False)):
            mode = str(getattr(magazine, "pickup_mode", "") or "").strip().lower()
            group_id = (
                magazine.fixed_pickup_group_id
                if mode == "fixed_group_sensor_controlled_fast_lin"
                else magazine.magazine_group_id
            )
            velocity = float(magazine.move_to_magazine_vel_percent)
            acceleration = float(magazine.move_to_magazine_acc_percent)
            motion_type = str(magazine.move_to_magazine_motion_type)
        else:
            group_id = str(
                getattr(configured_magazine, "calibration_group_id", "CALIBRATION") or "CALIBRATION"
            )
            nav = ctx.process_config.navigation_return
            velocity = float(nav.calibration_move_vel_percent)
            acceleration = float(nav.calibration_move_acc_percent)
            motion_type = str(nav.calibration_move_motion_type)
        group_id = str(group_id or "").strip()
        navigation = getattr(self._magazine_load_service, "_navigation", None)
        if navigation is None:
            navigation = getattr(self._navigation_service, "_nav", None)
        getter = getattr(navigation, "get_group_position", None)
        pose = getter(group_id) if callable(getter) and group_id else None
        if pose is None or len(pose) < 6:
            _logger.error("[NEXT_CYCLE] Cannot resolve start movement group '%s'", group_id)
            return None
        return {
            "group_id": group_id,
            "position": [float(value) for value in pose[:6]],
            "vel": velocity,
            "acc": acceleration,
            "type": motion_type,
        }

    def _mark_prepositioned_start_group(self, group_id: str) -> None:
        self._prepositioned_start_group = str(group_id or "").strip() or None

    def _clear_prepositioned_start_group(self) -> None:
        self._prepositioned_start_group = None

    def _consume_verified_prepositioned_start_group(
        self,
        group_id: str,
        *,
        position_tolerance_mm: float = 2.0,
        orientation_tolerance_deg: float = 2.0,
    ) -> bool:
        expected_group = str(group_id or "").strip()
        if not expected_group or self._prepositioned_start_group != expected_group:
            return False
        self._prepositioned_start_group = None
        navigation = getattr(self._magazine_load_service, "_navigation", None)
        if navigation is None:
            navigation = getattr(self._navigation_service, "_nav", None)
        getter = getattr(navigation, "get_group_position", None)
        expected = getter(expected_group) if callable(getter) else None
        pose_getter = getattr(self._path_executor._robot_service, "get_current_position_fresh", None)
        if not callable(pose_getter):
            pose_getter = getattr(self._path_executor._robot_service, "get_current_position", None)
        actual = pose_getter() if callable(pose_getter) else None
        if expected is None or actual is None or len(expected) < 6 or len(actual) < 6:
            return False
        xyz_error = math.sqrt(sum((float(actual[i]) - float(expected[i])) ** 2 for i in range(3)))
        angle_error = max(
            abs((float(actual[i]) - float(expected[i]) + 180.0) % 360.0 - 180.0)
            for i in range(3, 6)
        )
        verified = xyz_error <= float(position_tolerance_mm) and angle_error <= float(orientation_tolerance_deg)
        _logger.info(
            "[NEXT_CYCLE] Preposition verification group='%s' verified=%s xyz_error_mm=%.3f angle_error_deg=%.3f",
            expected_group,
            verified,
            xyz_error,
            angle_error,
        )
        return verified

    def _stop_active_magazine_navigation_motion(self) -> None:
        with self._active_context_lock:
            context = self._active_execution_context
        state = getattr(context, "current_state", None)
        if state is None or not str(getattr(state, "name", "")).startswith("MAGAZINE_"):
            return
        navigation = getattr(self._magazine_load_service, "_navigation", None)
        stop_motion = getattr(navigation, "stop_motion", None)
        if callable(stop_motion):
            try:
                stop_motion()
            except Exception:
                _logger.exception("[MAGAZINE_LOAD] Failed to stop robot motion during pause")

    def _freeze_brightness_after_capture(self) -> None:
        """Freeze auto-brightness after the workpiece capture so exposure stays stable while painting.

        Mirrors the robot-calibration pattern (lock_auto_brightness_adjustment); the
        lock is restored by _restore_brightness() in the cycle's finally block.
        """
        vision = self._vision_service
        if vision is None:
            return
        try:
            if not vision.get_auto_brightness_enabled():
                return
            vision.lock_auto_brightness_adjustment()
            self._brightness_locked = True
            _logger.info("Freezing auto brightness adjustment after workpiece capture")
        except Exception:
            _logger.exception("Failed to freeze auto brightness adjustment after capture")

    def _restore_brightness(self) -> None:
        """Restore adaptive auto brightness after the paint cycle finishes."""
        if not self._brightness_locked:
            return
        self._brightness_locked = False
        vision = self._vision_service
        if vision is None:
            return
        try:
            vision.unlock_auto_brightness_adjustment()
            _logger.info("Restoring adaptive auto brightness adjustment after paint cycle")
        except Exception:
            _logger.exception("Failed to restore auto brightness adjustment after paint cycle")

    def _restore_brightness_for_capture(self, reason: str) -> None:
        """Resume auto-brightness before camera captures that need fresh correction."""
        if not self._brightness_locked:
            return
        _logger.info("Restoring adaptive auto brightness adjustment %s", reason)
        self._restore_brightness()

    def _restore_capture_view(self, reason: str) -> None:
        """Resume live vision only after the robot reaches a camera capture location."""
        self._set_dashboard_live_view_paused(False, reason=reason)
        self._restore_brightness_for_capture(reason)

    def _get_process_config(self) -> tuple[bool, str, object | None]:
        config_service = self._paint_process_config_service
        if config_service is None:
            return True, "", None
        try:
            config = scale_paint_process_accelerations(config_service.get_snapshot())
        except Exception:
            _logger.exception("Failed to read paint process settings")
            return False, "Failed to read paint process settings", None
        return True, "", config

    def _move_to_calibration_before_manual_cycle(
        self,
        magazine_config,
        should_stop: Callable[[], bool],
    ) -> tuple[bool, str]:
        navigation = self._navigation_service
        if navigation is None:
            return False, "Navigation service unavailable for calibration move"
        move_to_calibration = getattr(navigation, "move_to_calibration_position", None)
        if not callable(move_to_calibration):
            return False, "Navigation service does not support calibration move"

        group_id = str(getattr(magazine_config, "calibration_group_id", "CALIBRATION") or "CALIBRATION")
        if self._consume_verified_prepositioned_start_group(group_id):
            self._restore_capture_view("after verifying prepositioned calibration pickup")
            return True, ""

        phase_start = perf_counter()
        ok = bool(move_to_calibration(wait_cancelled=should_stop))
        self._log_phase_timing("move_to_calibration", phase_start, success=ok, cycle=1)
        if should_stop():
            return False, "Paint process stopped"
        if not ok:
            return False, f"Failed to move to calibration position '{group_id}'"
        self._restore_capture_view("after reaching calibration pickup")
        settle_s = float(getattr(magazine_config, "release_settle_s", 0.0) or 0.0)
        settle_start = perf_counter()
        if not self._wait_for_capture_settle(settle_s, should_stop):
            return False, "Paint process stopped"
        self._log_phase_timing(
            "calibration_camera_settle",
            settle_start,
            configured_s=settle_s,
            cycle=1,
        )
        return True, ""

    def _wait_for_capture_settle(
        self,
        seconds: float,
        should_stop: Callable[[], bool],
    ) -> bool:
        deadline = monotonic() + max(0.0, seconds)
        while monotonic() < deadline:
            if should_stop() or self._paint_control.should_stop():
                return False
            if not self._paint_control.wait_if_paused():
                return False
            sleep(min(0.05, max(0.0, deadline - monotonic())))
        return not should_stop() and not self._paint_control.should_stop()

    def _path_debug_plots_enabled(self) -> bool:
        config_service = self._paint_process_config_service
        if config_service is None:
            return False
        try:
            return bool(getattr(config_service.get_snapshot(), "enable_path_debug_plots", False))
        except Exception:
            _logger.debug("Failed to read path debug plot setting", exc_info=True)
            return False

    def _pause_dashboard_live_view_after_capture(self) -> bool:
        config_service = self._paint_process_config_service
        if config_service is None:
            return True
        try:
            return bool(getattr(config_service.get_snapshot(), "pause_dashboard_live_view_after_capture", True))
        except Exception:
            _logger.debug("Failed to read dashboard live-view setting", exc_info=True)
            return True

    def _set_dashboard_live_view_paused(
        self,
        paused: bool,
        *,
        image: object | None = None,
        reason: str = "",
    ) -> None:
        vision = self._vision_service
        lifecycle_method = (
            getattr(vision, "pause_processing", None)
            if paused
            else getattr(vision, "resume_processing", None)
        )
        if callable(lifecycle_method):
            try:
                lifecycle_method()
            except Exception:
                _logger.exception(
                    "Failed to %s vision processing: %s",
                    "pause" if paused else "resume",
                    reason,
                )
        messaging = self._messaging_service
        if messaging is None:
            return
        try:
            messaging.publish(
                PaintDashboardLiveViewTopics.STATE,
                PaintDashboardLiveViewEvent(
                    paused=bool(paused),
                    image=image,
                    reason=reason,
                ),
            )
        except Exception:
            _logger.exception("Failed to publish paint dashboard live-view state")

    @staticmethod
    def _log_execution_state_timing(context: PaintExecutionContext) -> None:
        recorder = context.state_timing_recorder
        if recorder is None:
            return
        try:
            recorder.log_state_summary(_logger)
        except Exception:
            _logger.exception("Failed to log paint execution state timing summary")

    @staticmethod
    def _log_phase_timing(label: str, started_at: float, **fields: object) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in fields.items())
        if suffix:
            suffix = f" {suffix}"
        _logger.info("[PRODUCTION_TIMING] phase=%s elapsed_s=%.3f%s", label, perf_counter() - started_at, suffix)
