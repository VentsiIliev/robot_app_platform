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
from src.robot_systems.paint.processes.paint.magazine_load_result import (
    ALL_MAGAZINES_EMPTY,
    MAGAZINE_EMPTY,
    NO_WORKPIECE_AT_MAGAZINE,
)
from src.robot_systems.paint.processes.paint.motion.pose_sampling import (
    FreshPoseReadError,
    read_fresh_pose,
)
from src.robot_systems.paint.processes.paint.next_cycle_target import NextCycleTarget
from src.robot_systems.paint.processes.paint.config import (
    MAGAZINE_PROCESSING_STRATEGY_BATCH_NESTING,
    MAGAZINE_PICKUP_MODE_AUTO_DISCOVERY_SENSOR_CONTROLLED_FAST_LIN,
    MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN,
    DropoffStrategy,
    PAINT_PROCESS_CONFIG,
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
        self._last_execution_context: PaintExecutionContext | None = None
        self._prepositioned_start_group: str | None = None

    def pause_current_phase(self) -> None:
        with self._active_context_lock:
            context = self._active_execution_context
        if context is not None:
            context.run_allowed.clear()
        self._paint_control.request_pause()
        self._stop_active_magazine_navigation_motion()
        self._path_executor.pause_current_execution()

    def resume_current_phase(self) -> None:
        self._clear_prepositioned_start_group()
        with self._active_context_lock:
            context = self._active_execution_context
        if context is not None:
            context.run_allowed.set()
        self._paint_control.resume()

    def stop_current_phase(self) -> None:
        self._clear_prepositioned_start_group()
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
        run_while_found = bool(
            (process_config or PAINT_PROCESS_CONFIG).run_while_workpiece_found
        )

        if self._magazine_load_service is not None and magazine_config is not None and magazine_config.enabled:
            fixed_groups = self._fixed_magazine_groups(magazine_config)
            fixed_sources = self._fixed_magazine_sources(magazine_config)
            pickup_mode = magazine_config.pickup_mode
            if (
                magazine_config.processing_strategy == MAGAZINE_PROCESSING_STRATEGY_BATCH_NESTING
            ):
                if pickup_mode != MAGAZINE_PICKUP_MODE_AUTO_DISCOVERY_SENSOR_CONTROLLED_FAST_LIN:
                    return False, (
                        "Batch nesting currently requires the auto-discovery "
                        "sensor-controlled magazine pickup mode"
                    )
                return self._run_magazine_batch_loop(
                    magazine_config,
                    process_config,
                    should_stop,
                    fixed_sources=fixed_sources,
                )
            if pickup_mode == MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN and not fixed_sources:
                return False, "No fixed magazines are enabled"
            if (
                run_while_found
                or pickup_mode
                == MAGAZINE_PICKUP_MODE_AUTO_DISCOVERY_SENSOR_CONTROLLED_FAST_LIN
            ):
                return self._run_magazine_loop(
                    magazine_config,
                    process_config,
                    should_stop,
                    fixed_sources=fixed_sources,
                )

            ok, msg = self._run_single_cycle(
                should_stop,
                process_config=process_config,
                magazine_config=magazine_config,
                magazine_group=fixed_groups[0] if fixed_groups else None,
                magazine_source=fixed_sources[0] if fixed_sources else None,
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
            if process_config.stop_after_calibration_pickup:
                return True, msg
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

    def _run_magazine_loop(
        self,
        magazine_config,
        process_config,
        should_stop: Callable[[], bool],
        *,
        fixed_sources: tuple[dict, ...] | None = None,
    ) -> tuple[bool, str]:
        total_start = perf_counter()
        completed_cycles = 0
        sources = fixed_sources if fixed_sources is not None else self._fixed_magazine_sources(magazine_config)
        group_index = 0
        consecutive_empty_groups = 0
        discovery_contours: list = []
        discovery_active_contour = None
        discovery_snapshot = None
        pickup_mode = magazine_config.pickup_mode
        auto_discovery = (
            pickup_mode == MAGAZINE_PICKUP_MODE_AUTO_DISCOVERY_SENSOR_CONTROLLED_FAST_LIN
        )
        while not should_stop():
            active_source = sources[group_index] if sources else None
            active_group = (
                str(magazine_config.magazine_group_id).strip()
                if auto_discovery
                else self._magazine_source_group(active_source, magazine_config)
            )
            self._last_execution_context = None
            ok, msg = self._run_single_cycle(
                should_stop,
                process_config=process_config,
                magazine_config=magazine_config,
                magazine_group=active_group,
                magazine_source=active_source,
                magazine_index=group_index,
                cycle_index=completed_cycles + 1,
                repeats_after_success=True,
                magazine_discovery_contours=discovery_contours,
                magazine_discovery_active_contour=discovery_active_contour,
                magazine_discovery_snapshot=discovery_snapshot,
            )

            context = self._last_execution_context
            if auto_discovery and context is not None:
                discovery_contours = list(context.magazine_discovery_contours)
                discovery_active_contour = context.magazine_discovery_active_contour
                discovery_snapshot = context.magazine_snapshot

            if not ok and msg == NO_WORKPIECE_AT_MAGAZINE:
                if auto_discovery:
                    if context is not None and context.magazine_discovery_empty_capture:
                        self._log_phase_timing(
                            "magazine_loop_total",
                            total_start,
                            success=True,
                            completed_cycles=completed_cycles,
                        )
                        return True, MAGAZINE_EMPTY
                    discovery_active_contour = None
                    active_magazine_config = (
                        context.magazine_config
                        if context is not None
                        else magazine_config
                    )
                    if active_magazine_config.recapture_after_pile_done:
                        discovery_contours = []
                        discovery_snapshot = None
                        _logger.info(
                            "[MAGAZINE_LOAD] Active pile is empty; clearing cached "
                            "discovery so the magazine is recaptured"
                        )
                    self._clear_prepositioned_start_group()
                    continue
                consecutive_empty_groups += 1
                if sources and consecutive_empty_groups < len(sources):
                    next_index = (group_index + 1) % len(sources)
                    next_group = self._magazine_source_group(sources[next_index], magazine_config)
                    _logger.info(
                        "[MAGAZINE_LOAD] Magazine group '%s' is empty; advancing to '%s'",
                        active_group,
                        next_group,
                    )
                    group_index = next_index
                    self._clear_prepositioned_start_group()
                    continue
                self._log_phase_timing(
                    "magazine_loop_total",
                    total_start,
                    success=True,
                    completed_cycles=completed_cycles,
                )
                _logger.info(
                    "[MAGAZINE_LOAD] All %d configured magazine(s) are empty",
                    len(sources) or 1,
                )
                return True, ALL_MAGAZINES_EMPTY
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
            active_magazine_config = (
                context.magazine_config
                if context is not None
                else magazine_config
            )
            if auto_discovery and active_magazine_config.recapture_every_cycle:
                discovery_contours = []
                discovery_active_contour = None
                discovery_snapshot = None
                _logger.info(
                    "[MAGAZINE_LOAD] Cycle completed; clearing cached discovery "
                    "so the magazine is recaptured before the next pickup"
                )
            if process_config.stop_after_calibration_pickup:
                return True, msg
            consecutive_empty_groups = 0
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

    def _run_magazine_batch_loop(
        self,
        magazine_config,
        process_config,
        should_stop: Callable[[], bool],
        *,
        fixed_sources: tuple[dict, ...] | None = None,
    ) -> tuple[bool, str]:
        """Fill the paint work area, then process one cached capture as a batch."""
        completed = 0
        discovery_contours: list = []
        discovery_active = None
        discovery_snapshot = None
        sources = fixed_sources if fixed_sources is not None else self._fixed_magazine_sources(magazine_config)
        group_index = 0
        while not should_stop():
            self._magazine_load_service.clear_work_area_nesting()
            staged = 0
            while not should_stop():
                source = sources[group_index] if sources else None
                mode = magazine_config.pickup_mode
                group = (
                    str(magazine_config.magazine_group_id or "Magazine").strip()
                    if mode == MAGAZINE_PICKUP_MODE_AUTO_DISCOVERY_SENSOR_CONTROLLED_FAST_LIN
                    else self._magazine_source_group(source, magazine_config)
                )
                self._last_execution_context = None
                ok, message = self._run_single_cycle(
                    should_stop,
                    process_config=process_config,
                    magazine_config=magazine_config,
                    magazine_group=group,
                    magazine_source=source,
                    magazine_index=group_index,
                    cycle_index=completed + staged + 1,
                    magazine_discovery_contours=discovery_contours,
                    magazine_discovery_active_contour=discovery_active,
                    magazine_discovery_snapshot=discovery_snapshot,
                    magazine_stage_only=True,
                )
                context = self._last_execution_context
                if context is not None:
                    discovery_contours = list(context.magazine_discovery_contours)
                    discovery_active = context.magazine_discovery_active_contour
                    discovery_snapshot = context.magazine_snapshot
                if not ok:
                    if message == NO_WORKPIECE_AT_MAGAZINE:
                        discovery_active = None
                        active_magazine_config = (
                            context.magazine_config
                            if context is not None
                            else magazine_config
                        )
                        if active_magazine_config.recapture_after_pile_done:
                            discovery_contours = []
                            discovery_snapshot = None
                            _logger.info(
                                "[MAGAZINE_LOAD] Active pile is empty during batch "
                                "staging; clearing cached discovery so the magazine "
                                "is recaptured"
                            )
                        break
                    if "no space for another staged workpiece" in message.lower():
                        break
                    return False, message
                staged += 1
                active_magazine_config = (
                    context.magazine_config
                    if context is not None
                    else magazine_config
                )
                if active_magazine_config.recapture_every_cycle:
                    discovery_contours = []
                    discovery_active = None
                    discovery_snapshot = None
                    _logger.info(
                        "[MAGAZINE_LOAD] Batch staging pickup completed; clearing "
                        "cached discovery so the magazine is recaptured"
                    )
                if context is not None and not context.magazine_nesting_has_more:
                    break

            if should_stop():
                return False, "Paint process stopped"
            if staged == 0:
                if context is not None and context.magazine_discovery_empty_capture:
                    return True, MAGAZINE_EMPTY
                continue

            ok, message = self._move_to_calibration_before_manual_cycle(
                magazine_config, should_stop
            )
            if not ok:
                return False, message
            snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_batch_staging")
            contours = list(snapshot.contours or ())
            if not contours:
                return False, "Batch nesting staged workpieces but calibration capture found none"
            _logger.info("[BATCH_NESTING] captured staged batch workpieces=%d", len(contours))
            for index, contour in enumerate(contours):
                remaining = index + 1 < len(contours)
                ok, message = self._run_single_cycle(
                    should_stop,
                    process_config=process_config,
                    magazine_config=None,
                    cycle_index=completed + 1,
                    repeats_after_success=remaining,
                    cached_snapshot=snapshot,
                    cached_workpiece_contour=contour,
                    suppress_magazine_load=True,
                )
                if not ok:
                    return False, message
                completed += 1
            self._magazine_load_service.clear_work_area_nesting()
        return False, "Paint process stopped"

    @staticmethod
    def _fixed_magazine_groups(magazine_config) -> tuple[str, ...]:
        mode = magazine_config.pickup_mode
        if mode != MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN:
            return ()
        return magazine_config.effective_fixed_pickup_group_ids()

    @staticmethod
    def _fixed_magazine_sources(magazine_config) -> tuple[dict, ...]:
        mode = magazine_config.pickup_mode
        if mode != MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN:
            return ()
        return magazine_config.effective_fixed_pickup_sources()

    @staticmethod
    def _magazine_source_group(source: dict | None, magazine_config) -> str:
        if not isinstance(source, dict) or "movement_group_id" not in source:
            raise ValueError("Fixed magazine source requires movement_group_id")
        group_id = str(source["movement_group_id"] or "").strip()
        if not group_id:
            raise ValueError("Fixed magazine source movement_group_id cannot be empty")
        return group_id

    def _run_single_cycle(
        self,
        should_stop: Callable[[], bool],
        *,
        process_config,
        magazine_config,
        magazine_group: str | None = None,
        magazine_source: dict | None = None,
        magazine_index: int = 0,
        cycle_index: int,
        repeats_after_success: bool = False,
        magazine_discovery_contours: list | None = None,
        magazine_discovery_active_contour=None,
        magazine_discovery_snapshot=None,
        magazine_stage_only: bool = False,
        cached_snapshot=None,
        cached_workpiece_contour=None,
        suppress_magazine_load: bool = False,
    ) -> tuple[bool, str]:
        raw_process_config = process_config or PAINT_PROCESS_CONFIG
        process_config = scale_paint_process_accelerations(raw_process_config)
        if self._paint_process_config_service is not None:
            try:
                raw_process_config = self._paint_process_config_service.get_snapshot()
                process_config = scale_paint_process_accelerations(raw_process_config)
            except Exception:
                _logger.exception("Failed to capture settings for paint cycle %d", cycle_index)
                return False, "Failed to read paint process settings"
        latest_magazine_config = process_config.magazine_load
        if latest_magazine_config is not None and not suppress_magazine_load:
            magazine_config = latest_magazine_config
            pickup_mode = magazine_config.pickup_mode
            if pickup_mode != MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN:
                # Vision strategies always acquire from the camera observer.
                # Do not let a fixed-source choice made from an older settings
                # snapshot leak into this cycle.
                magazine_group = str(magazine_config.magazine_group_id).strip()
                magazine_source = None
        cycle_strategy = self._effective_dropoff_strategy(process_config, cycle_index)
        self._path_executor.set_cycle_dropoff_strategy(cycle_strategy)
        _logger.info(
            "[DRYING_MODE] cycle=%d effective_dropoff_strategy=%s alternating_demo=%s",
            cycle_index,
            cycle_strategy or "configured",
            process_config.dropoff.alternate_drying_demo,
        )
        context = PaintExecutionContext(
            production_service=self,
            stop_requested=should_stop,
            control=self._paint_control,
            process_config=process_config,
            raw_process_config=raw_process_config,
            magazine_config=magazine_config,
            magazine_group=str(magazine_group or "").strip(),
            magazine_index=int(magazine_index),
            cycle_index=cycle_index,
            repeats_after_success=repeats_after_success,
            total_started_at=perf_counter(),
            magazine_discovery_contours=list(magazine_discovery_contours or ()),
            magazine_discovery_active_contour=magazine_discovery_active_contour,
            magazine_snapshot=magazine_discovery_snapshot,
            magazine_stage_only=bool(magazine_stage_only),
            snapshot=cached_snapshot,
            cached_workpiece_contour=cached_workpiece_contour,
        )
        if isinstance(magazine_source, dict) and "position" in magazine_source:
            context.magazine_fixed_pickup_pose = [
                float(value) for value in list(magazine_source["position"])[:6]
            ]
        with self._active_context_lock:
            self._active_execution_context = context
        try:
            machine = PaintExecutionMachineFactory().build(context)
            machine.start_execution()
        finally:
            self._last_execution_context = context
            self._log_execution_state_timing(context)
            with self._active_context_lock:
                if self._active_execution_context is context:
                    self._active_execution_context = None
            self._path_executor.set_cycle_dropoff_strategy(None)

        snapshot = machine.get_snapshot()
        if snapshot.last_error is not None:
            self._clear_prepositioned_start_group()
            self._restore_brightness()
            self._set_dashboard_live_view_paused(False, reason="paint cycle finished")
            return False, snapshot.last_error

        return context.result_ok, context.result_message

    @staticmethod
    def _effective_dropoff_strategy(process_config, cycle_index: int) -> str | None:
        dropoff = process_config.dropoff
        if dropoff.alternate_drying_demo:
            return (
                DropoffStrategy.MOVEMENT_GROUP
                if int(cycle_index) % 2 == 1
                else DropoffStrategy.PLATE_LAYOUT
            )
        return dropoff.strategy

    def _next_cycle_start_target(self, ctx: PaintExecutionContext) -> NextCycleTarget | None:
        if not ctx.repeats_after_success:
            return None
        magazine = ctx.magazine_config
        configured_magazine = magazine or ctx.process_config.magazine_load
        if magazine is not None and magazine.enabled:
            group_id = ctx.magazine_group
            velocity = float(magazine.move_to_magazine_vel_percent)
            acceleration = float(magazine.move_to_magazine_acc_percent)
            motion_type = magazine.move_to_magazine_motion_type
        else:
            group_id = str(configured_magazine.calibration_group_id)
            nav = ctx.process_config.navigation_return
            velocity = float(nav.calibration_move_vel_percent)
            acceleration = float(nav.calibration_move_acc_percent)
            motion_type = nav.calibration_move_motion_type
        group_id = str(group_id or "").strip()
        navigation = self._magazine_load_service._navigation
        pose = ctx.magazine_fixed_pickup_pose
        if pose is None:
            pose = navigation.get_group_position(group_id) if group_id else None
        if pose is None or len(pose) < 6:
            _logger.error("[NEXT_CYCLE] Cannot resolve start movement group '%s'", group_id)
            return None
        return NextCycleTarget(
            group_id=group_id,
            position=tuple(float(value) for value in pose[:6]),
            velocity_percent=velocity,
            acceleration_percent=acceleration,
            motion_type=motion_type,
        )

    def _mark_prepositioned_start_group(self, group_id: str) -> None:
        self._prepositioned_start_group = str(group_id or "").strip() or None

    def _clear_prepositioned_start_group(self) -> None:
        self._prepositioned_start_group = None

    def _consume_verified_prepositioned_start_group(
        self,
        group_id: str,
        *,
        expected_position: list[float] | None = None,
        position_tolerance_mm: float = 2.0,
        orientation_tolerance_deg: float = 2.0,
    ) -> bool:
        expected_group = str(group_id or "").strip()
        if not expected_group or self._prepositioned_start_group != expected_group:
            return False
        self._prepositioned_start_group = None
        navigation = self._magazine_load_service._navigation
        expected = expected_position
        if expected is None:
            expected = navigation.get_group_position(expected_group)
        try:
            actual = read_fresh_pose(
                self._path_executor._robot_service,
                error_message=f"Failed to verify prepositioned group '{expected_group}'",
            )
        except FreshPoseReadError as exc:
            _logger.error("[NEXT_CYCLE] %s", exc)
            return False
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
        if context is None or context.current_state is None:
            return
        if not context.current_state.name.startswith("MAGAZINE_"):
            return
        try:
            self._magazine_load_service._navigation.stop_motion()
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

    def _restore_magazine_capture_view(self, reason: str) -> None:
        """Resume magazine vision while preserving a locked known-good correction."""
        self._set_dashboard_live_view_paused(False, reason=reason)
        if self._brightness_locked:
            _logger.info(
                "Keeping auto brightness adjustment locked while restoring the "
                "saved magazine correction"
            )
            return
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
        group_id = str(magazine_config.calibration_group_id)
        if self._consume_verified_prepositioned_start_group(group_id):
            self._restore_capture_view("after verifying prepositioned calibration pickup")
            return True, ""

        phase_start = perf_counter()
        ok = bool(navigation.move_to_calibration_position(wait_cancelled=should_stop))
        self._log_phase_timing("move_to_calibration", phase_start, success=ok, cycle=1)
        if should_stop():
            return False, "Paint process stopped"
        if not ok:
            return False, f"Failed to move to calibration position '{group_id}'"
        self._restore_capture_view("after reaching calibration pickup")
        settle_s = float(magazine_config.release_settle_s)
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

    def _wait_for_fresh_capture_frame(
        self,
        timeout_s: float,
        should_stop: Callable[[], bool],
    ) -> tuple[bool, str]:
        """Wait until resumed vision has published a genuinely fresh frame."""
        started = perf_counter()
        deadline = monotonic() + max(0.0, float(timeout_s))
        last_message = "No fresh camera frame available"
        while True:
            if should_stop() or self._paint_control.should_stop():
                return False, "Paint process stopped while waiting for a fresh camera frame"
            try:
                details = self._vision_service.get_health_details()
            except Exception as exc:
                return False, f"Failed to query camera frame readiness: {exc}"
            if bool(details.get("frame_fresh", False)):
                _logger.debug(
                    "[CAPTURE_TIMING] fresh_frame_ready elapsed_s=%.3f",
                    perf_counter() - started,
                )
                return True, ""
            last_message = str(details.get("message") or last_message)
            remaining_s = deadline - monotonic()
            if remaining_s <= 0.0:
                return False, f"Fresh camera frame unavailable after {timeout_s:.3f}s: {last_message}"
            sleep(min(0.02, remaining_s))

    def _path_debug_plots_enabled(self) -> bool:
        config_service = self._paint_process_config_service
        if config_service is None:
            return False
        return bool(config_service.get_snapshot().enable_path_debug_plots)

    def _pause_dashboard_live_view_after_capture(self) -> bool:
        config_service = self._paint_process_config_service
        if config_service is None:
            return True
        return bool(config_service.get_snapshot().pause_dashboard_live_view_after_capture)

    def _set_dashboard_live_view_paused(
        self,
        paused: bool,
        *,
        image: object | None = None,
        reason: str = "",
    ) -> None:
        vision = self._vision_service
        if vision is None:
            return
        lifecycle_method = vision.pause_processing if paused else vision.resume_processing
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
