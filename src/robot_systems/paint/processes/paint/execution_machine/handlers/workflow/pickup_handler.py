from __future__ import annotations

import logging

import numpy as np

from src.engine.robot.motion_sequence import (
    OrderedMotionCommand,
    OrderedUnwindJoint6Command,
)
from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    build_ordered_paint_contact_segments,
    build_ordered_pickup_segments,
)
from src.robot_systems.paint.processes.paint.config import (
    PICKUP_CONTACT_MODE_PLANNED,
    PICKUP_CONTACT_MODE_SENSOR_CONTROLLED_FAST_LIN,
    DropoffStrategy,
)
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.motion_handlers import (
    fail_paint_motion,
    finish_paint_motion,
    motion_failure_message,
    start_paint_motion_if_needed,
    unwind_joint6_at_cycle_start,
    wait_or_guard,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    build_plate_entry_segments_for_paint_chain,
    build_ordered_dropoff_preparation_segments,
    open_dropoff_passage_for_preparation,
    _resolve_dropoff_safe_travel_waypoints,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.magazine_load_result import (
    NO_WORKPIECE_AT_CALIBRATION,
)
from src.robot_systems.paint.processes.paint.paint_contact_job import PaintContactCommandJob
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_execute_pickup_release_handler import (
    calculate_workpiece_dropoff_pose,
)
from src.robot_systems.paint.timing import timed_block, timed_step

_logger = logging.getLogger(__name__)


def handle_pickup(ctx: PaintExecutionContext) -> PaintExecutionState:
    executor = ctx.production_service._path_executor
    start_paint_motion_if_needed(ctx)

    guarded = wait_or_guard(ctx, PaintExecutionState.PICKUP)
    if guarded is not None:
        finish_paint_motion(ctx, success=False)
        return guarded

    if not unwind_joint6_at_cycle_start(ctx):
        fail_paint_motion(ctx, "Cycle-start Joint 6 unwind failed before pickup")
        return PaintExecutionState.ERROR

    pickup_plan = executor._pickup.build_plan(ctx.execution_plan)
    if pickup_plan is None:
        fail_paint_motion(ctx, "Could not compute pickup-to-pivot poses")
        return PaintExecutionState.ERROR

    if pickup_plan is not None and _dropoff_strategy(executor) is DropoffStrategy.PLATE_LAYOUT:
        ok, message = _reserve_plate_dropoff(ctx, executor, pickup_plan)
        if not ok:
            finish_paint_motion(ctx, success=False)
            ctx.set_result(False, message)
            return PaintExecutionState.COMPLETED if message == "Drop-off plate is full" else PaintExecutionState.ERROR

    stop_after_pickup = bool(ctx.process_config.stop_after_calibration_pickup)
    ctx.paint_ordered_result = (
        try_execute_ordered_pickup_and_paint_contact(
            executor,
            ctx.execution_plan,
            pickup_plan=pickup_plan,
        )
        if pickup_plan is not None and not stop_after_pickup
        else None
    )
    if ctx.paint_ordered_result is not None:
        ok, msg, total_waypoints = ctx.paint_ordered_result
        ctx.paint_total_waypoints = int(total_waypoints)
        if not ok:
            if msg == NO_WORKPIECE_AT_CALIBRATION:
                finish_paint_motion(ctx, success=False)
                ctx.set_result(False, msg)
                return PaintExecutionState.COMPLETED
            fail_paint_motion(ctx, msg)
            return PaintExecutionState.ERROR
        ctx.paint_contact_executed_in_ordered_chain = True
        return PaintExecutionState.PAINT_CONTACT

    if _unmatched_second_pass_requested(executor, ctx.execution_plan):
        fail_paint_motion(ctx, "Two-pass painting requires ordered motion-chain support")
        return PaintExecutionState.ERROR

    if stop_after_pickup:
        ok, msg = executor._pickup.execute(
            ctx.execution_plan,
            pickup_plan=pickup_plan,
            stop_after_retract=stop_after_pickup,
        )
    elif pickup_plan is None:
        ok, msg = executor._pickup.execute(ctx.execution_plan)
    else:
        ok, msg = executor._pickup.execute(
            ctx.execution_plan,
            pickup_plan=pickup_plan,
        )
    if not ok:
        _logger.debug(
            "[TIMING] paint_process success=false stage=pickup total_elapsed_s=%.3f",
            elapsed_s(ctx.paint_started_at),
        )
        if msg == NO_WORKPIECE_AT_CALIBRATION:
            finish_paint_motion(ctx, success=False)
            ctx.set_result(False, msg)
            return PaintExecutionState.COMPLETED
        fail_paint_motion(ctx, msg)
        return PaintExecutionState.ERROR
    if stop_after_pickup:
        finish_paint_motion(ctx, success=True)
        ctx.set_result(True, "Calibration pickup test completed")
        return PaintExecutionState.COMPLETED
    return PaintExecutionState.PAINT_CONTACT


def _dropoff_strategy(executor: object) -> DropoffStrategy:
    return executor._paint_process_config().dropoff.strategy


def _reserve_plate_dropoff(ctx, executor, pickup_plan) -> tuple[bool, str]:
    motion_plan = pickup_plan.motion_plan
    align_pose = motion_plan.align_pose
    if align_pose is None or len(align_pose) < 6:
        return False, "Plate-layout dropoff could not resolve workpiece orientation at calibration"
    width_mm, height_mm, outlines_mm = _workpiece_layout_geometry(ctx.execution_plan)
    paint_passes = _paint_pass_metadata(
        ctx.execution_plan,
        executor._paint_process_config(),
        executor,
    )

    magazine = ctx.magazine_config or ctx.process_config.magazine_load
    group_id = str(magazine.calibration_group_id)
    navigation = ctx.production_service._magazine_load_service._navigation
    calibration_pose = navigation.get_group_position(group_id)
    if calibration_pose is None or len(calibration_pose) < 6:
        return False, f"Plate-layout dropoff requires calibration movement group '{group_id}'"

    reservation, message = executor._plate_layout_service.reserve(
        executor._paint_process_config().dropoff,
        width_mm=width_mm,
        height_mm=height_mm,
        calibration_pose=list(calibration_pose),
        workpiece_rz_at_calibration_deg=float(align_pose[5]),
        pose_calculator=calculate_workpiece_dropoff_pose,
        outlines_mm=outlines_mm,
        paint_passes=paint_passes,
    )
    if reservation is None:
        return False, message
    _logger.info(
        "[PLATE_LAYOUT] reserved release_pose=%s footprint=(%.3f, %.3f) has_space_for_same_footprint=%s",
        [round(value, 3) for value in reservation.release_pose],
        width_mm,
        height_mm,
        reservation.has_space_for_same_footprint,
    )
    return True, ""


def _workpiece_footprint_mm(execution_plan) -> tuple[float, float]:
    """Return canonical min-rectangle sides as long-side width and short-side height."""
    width, height, _outlines = _workpiece_layout_geometry(execution_plan)
    return width, height


def _paint_pass_metadata(execution_plan, config, executor) -> tuple[dict, ...]:
    """Capture the configured paint controls used by each production pass."""
    jobs = list(execution_plan.execution_jobs)
    first_job = jobs[0] if jobs else {}
    try:
        first_offset = float(
            executor._resolve_pivot_offset_mm(first_job or None, execution_plan)
        )
    except (AttributeError, TypeError, ValueError):
        first_offset = float(config.default_paint_offset_mm)
    first_pass = {
        "pass_number": 1,
        "velocity_percent": float(
            first_job.get("vel", config.default_paint_velocity_percent)
        ),
        "acceleration_percent": float(
            first_job.get("acc", config.default_paint_acceleration_percent)
        ),
        "press_offset_mm": first_offset,
    }
    passes = [first_pass]
    workpiece = execution_plan.workpiece
    is_unmatched = str(workpiece.get("workpieceId", "")).strip().lower() == "captured"
    pass_count = max(1, min(2, int(config.unmatched_paint_pass_count)))
    if is_unmatched and pass_count == 2:
        second = config.unmatched_second_pass
        if bool(second.use_pass_1_settings):
            second_pass = {**first_pass, "pass_number": 2}
        else:
            second_pass = {
                "pass_number": 2,
                "velocity_percent": float(second.velocity_percent),
                "acceleration_percent": float(second.acceleration_percent),
                "press_offset_mm": float(second.offset_mm),
            }
        passes.append(second_pass)
    return tuple(passes)


def _workpiece_layout_geometry(
    execution_plan,
) -> tuple[float, float, tuple[tuple[tuple[float, float], ...], ...]]:
    """Return footprint and execution paths projected into its local rectangle."""
    paths = [
        [pose[:2] for pose in path if len(pose) >= 2]
        for path in execution_plan.execution_paths()
    ]
    paths = [path for path in paths if path]
    points = [point for path in paths for point in path]
    if len(points) < 3:
        return 0.0, 0.0, ()
    xy = np.asarray(points, dtype=np.float32)
    if not np.all(np.isfinite(xy)):
        return 0.0, 0.0, ()
    import cv2
    rectangle = cv2.boxPoints(cv2.minAreaRect(np.ascontiguousarray(xy.reshape(-1, 1, 2))))
    edges = [rectangle[(index + 1) % 4] - rectangle[index] for index in range(4)]
    long_axis = max(edges, key=lambda edge: float(np.linalg.norm(edge)))
    long_axis = long_axis / np.linalg.norm(long_axis)
    # A rectangle axis has no inherent direction: OpenCV may return either v
    # or -v for otherwise identically oriented contours. Choose one stable
    # direction in robot coordinates so asymmetric workpieces are never shown
    # rotated by 180 degrees from their physical orientation.
    dominant_index = int(np.argmax(np.abs(long_axis)))
    if long_axis[dominant_index] > 0.0:
        long_axis = -long_axis
    short_axis = np.asarray([-long_axis[1], long_axis[0]], dtype=np.float32)
    projected = np.column_stack((xy @ long_axis, xy @ short_axis))
    minimum = projected.min(axis=0)
    projected -= minimum
    width, height = projected.max(axis=0)
    outlines = []
    offset = 0
    for path in paths:
        count = len(path)
        outlines.append(tuple(
            (float(x), float(y)) for x, y in projected[offset:offset + count]
        ))
        offset += count
    return float(width), float(height), tuple(outlines)


@timed_step(_logger, "ordered_pickup_paint_contact_chain")
def try_execute_ordered_pickup_and_paint_contact(
    executor: object,
    prepared_workpiece,
    *,
    pickup_plan=None,
) -> tuple[bool, str, int] | None:
    """Execute pickup/staging and primary paint contact as one preplanned ordered chain."""
    execute_chain = executor._robot_service.execute_ordered_motion_chain

    if pickup_plan is None:
        pickup_plan = executor._pickup.build_plan(prepared_workpiece)
    if pickup_plan is None:
        return False, "Could not compute pickup-to-pivot poses", 0
    if pickup_plan.contact_mode not in {
        PICKUP_CONTACT_MODE_PLANNED,
        PICKUP_CONTACT_MODE_SENSOR_CONTROLLED_FAST_LIN,
    }:
        _logger.info(
            "[ORDERED_CHAIN] pickup plus paint contact chain skipped: pickup contact mode=%s",
            pickup_plan.contact_mode,
        )
        return None
    executor._last_pickup_plan = pickup_plan.motion_plan

    if pickup_plan.change_plane_combined_with_first_contact:
        with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
            _logger.info(
                "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
            )

    paint_paths: list[list[list[float]]] = []
    paint_jobs: list[PaintContactCommandJob] = []
    ok, msg, total_waypoints = executor._paint_contact.execute(
        prepared_workpiece,
        execute_robot=False,
        collected_command_paths=paint_paths,
        collected_command_jobs=paint_jobs,
    )
    if not ok:
        return False, msg, total_waypoints
    if not paint_paths:
        return False, "Pickup succeeded, but no paint contact path was generated", total_waypoints

    paint_segments = build_ordered_paint_contact_segments(
            paint_paths,
            paint_jobs,
            executor._paint_process_config().contact_staging,
            acceleration_scale=(
                executor._paint_process_config().paint_process_acceleration_scale_percent
                / 100.0
            ),
    )
    post_pickup_segments = list(paint_segments)

    second_pass_paths: list[list[list[float]]] = []
    second_pass_jobs: list[PaintContactCommandJob] = []
    config = executor._paint_process_config()
    workpiece = prepared_workpiece.workpiece
    is_unmatched = str(workpiece.get("workpieceId", "")).strip().lower() == "captured"
    pass_count = max(1, min(2, int(config.unmatched_paint_pass_count)))
    if is_unmatched and pass_count == 2:
        pass_2 = config.unmatched_second_pass
        use_first = bool(pass_2.use_pass_1_settings)
        velocity = None if use_first else float(pass_2.velocity_percent)
        acceleration = (
            None
            if use_first
            else executor._scale_process_acceleration(pass_2.acceleration_percent)
        )
        offset = (
            executor._resolve_pivot_offset_mm(None, prepared_workpiece)
            if use_first
            else float(pass_2.offset_mm)
        )
        ok, msg, second_waypoints = executor._paint_contact.execute(
            prepared_workpiece,
            vel_override=velocity,
            acc_override=acceleration,
            execute_robot=False,
            collected_command_paths=second_pass_paths,
            collected_command_jobs=second_pass_jobs,
            pivot_offset_override_mm=offset,
        )
        if not ok or not second_pass_paths:
            return False, msg or "Second paint pass could not be planned", total_waypoints
        total_waypoints += int(second_waypoints)
        post_pickup_segments.extend(
            build_ordered_second_pass_segments(
                second_pass_paths, second_pass_jobs, config
            )
        )
    dropoff_prepared_in_chain = False
    final_pose: list[float] | None = (
        list(second_pass_paths[-1][-1])
        if second_pass_paths
        else list(paint_paths[-1][-1])
    )
    plate_entry_in_chain = False
    if (
        _dropoff_strategy(executor) is DropoffStrategy.PLATE_LAYOUT
        and bool(config.dropoff.plate_use_entry_gate_as_detach_pose)
    ):
        plate_segments, plate_release_pose, error = build_plate_entry_segments_for_paint_chain(
            executor
        )
        if error:
            return False, error, total_waypoints
        post_pickup_segments.extend(plate_segments)
        plate_entry_in_chain = bool(plate_segments)
        final_pose = plate_release_pose or final_pose
    if _should_preplan_dropoff_in_ordered_chain(executor):
        config = executor._paint_process_config()
        if bool(config.dropoff_safe_travel.enabled) and not _resolve_dropoff_safe_travel_waypoints(executor):
            return (
                False,
                "Pivot paint finished, but paint-to-dropoff safe travel waypoints are not configured",
                total_waypoints,
            )
        dropoff_commands, dropoff_final_pose = build_ordered_dropoff_preparation_segments(executor)
        if not dropoff_commands:
            return (
                False,
                "Pivot paint finished, but no dropoff pose is available for safe pre-dropoff unwind alignment",
                total_waypoints,
            )
        post_pickup_segments.extend(dropoff_commands)
        dropoff_prepared_in_chain = True
        final_pose = dropoff_final_pose or final_pose

    if dropoff_prepared_in_chain:
        opened, message = open_dropoff_passage_for_preparation(executor)
        if not opened:
            return False, message, total_waypoints

    if pickup_plan.contact_mode == PICKUP_CONTACT_MODE_SENSOR_CONTROLLED_FAST_LIN:
        _logger.info(
            "[ORDERED_CHAIN] preparing complete post-retract servo chain: "
            "segments=%d paint_paths=%d dropoff_prep=%s",
            len(post_pickup_segments),
            len(paint_paths),
            dropoff_prepared_in_chain,
        )
        ok, msg = executor._pickup.execute(
            prepared_workpiece,
            pickup_plan=pickup_plan,
            prepared_continuation_segments=post_pickup_segments,
        )
        if ok and dropoff_prepared_in_chain:
            executor._dropoff_unwind_prepared = True
        if ok and final_pose is not None:
            executor._last_process_end_pose = list(final_pose)
        if ok and plate_entry_in_chain:
            executor._plate_entry_completed_in_paint_chain = True
        return ok, msg, total_waypoints

    segments: list[OrderedMotionCommand] = build_ordered_pickup_segments(pickup_plan)
    segments.extend(post_pickup_segments)

    if pickup_plan.vacuum_on_before_moves:
        ok, msg = executor._motion.turn_vacuum_on()
        if not ok:
            return False, msg, total_waypoints

    if not executor._motion.move_ordered_pickup_sequence(
        "Ordered pickup plus paint contact chain",
        segments,
    ):
        return False, motion_failure_message(
            executor._robot_service,
            "Ordered pickup and paint contact chain failed",
        ), total_waypoints

    if dropoff_prepared_in_chain:
        executor._dropoff_unwind_prepared = True
    if final_pose is not None:
        executor._last_process_end_pose = list(final_pose)
    if plate_entry_in_chain:
        executor._plate_entry_completed_in_paint_chain = True
    return True, "", total_waypoints


def _should_preplan_dropoff_in_ordered_chain(executor: object) -> bool:
    """Keep plate travel/unwind in PREPARE_DROPOFF after paint completes."""
    return (
        _dropoff_strategy(executor) is not DropoffStrategy.PLATE_LAYOUT
        and not executor._edge_cleanup.should_run_after_xz_ry()
        and not executor._edge_cleanup.should_run_after_xy_rz()
    )


def build_ordered_second_pass_segments(
    paint_paths: list[list[list[float]]],
    paint_jobs: list[PaintContactCommandJob],
    config,
) -> list[OrderedMotionCommand]:
    """Build the guarded unwind, re-attach, and contact sequence for pass two."""
    return [
        OrderedUnwindJoint6Command(
            label="paint_pass_2_unwind",
            velocity_percent=float(config.navigation_return.unwind_vel_percent),
            acceleration_percent=float(config.navigation_return.unwind_acc_percent),
            protected=True,
        ),
        *build_ordered_paint_contact_segments(
                paint_paths,
                paint_jobs,
                config.contact_staging,
                label_prefix="paint_pass_2",
                acceleration_scale=(
                    1.0
                    if not bool(config.unmatched_second_pass.use_pass_1_settings)
                    else config.paint_process_acceleration_scale_percent / 100.0
                ),
        ),
    ]


def _unmatched_second_pass_requested(executor: object, execution_plan: object) -> bool:
    config = executor._paint_process_config()
    workpiece = execution_plan.workpiece
    return (
        str(workpiece.get("workpieceId", "")).strip().lower() == "captured"
        and int(config.unmatched_paint_pass_count) == 2
    )
