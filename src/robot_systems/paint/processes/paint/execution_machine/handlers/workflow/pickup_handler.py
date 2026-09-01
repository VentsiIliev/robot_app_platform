from __future__ import annotations

import logging

import numpy as np

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    build_ordered_paint_contact_segments,
    build_ordered_pickup_segments,
)
from src.robot_systems.paint.processes.paint.config import (
    PICKUP_CONTACT_MODE_PLANNED,
    PICKUP_CONTACT_MODE_SENSOR_CONTROLLED_FAST_LIN,
)
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.motion_handlers import (
    fail_paint_motion,
    finish_paint_motion,
    motion_failure_message,
    start_paint_motion_if_needed,
    wait_or_guard,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    build_ordered_dropoff_preparation_segments,
    open_dropoff_passage_for_preparation,
    _resolve_dropoff_safe_travel_waypoints,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.magazine_load_result import (
    NO_WORKPIECE_AT_CALIBRATION,
)
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

    build_plan = getattr(executor._pickup, "build_plan", None)
    pickup_plan = build_plan(ctx.execution_plan) if callable(build_plan) else None
    if callable(build_plan) and pickup_plan is None:
        fail_paint_motion(ctx, "Could not compute pickup-to-pivot poses")
        return PaintExecutionState.ERROR

    if pickup_plan is not None and _dropoff_strategy(executor) == "plate_layout":
        ok, message = _reserve_plate_dropoff(ctx, executor, pickup_plan)
        if not ok:
            finish_paint_motion(ctx, success=False)
            ctx.set_result(False, message)
            return PaintExecutionState.COMPLETED if message == "Drop-off plate is full" else PaintExecutionState.ERROR

    ctx.paint_ordered_result = (
        try_execute_ordered_pickup_and_paint_contact(
            executor,
            ctx.execution_plan,
            pickup_plan=pickup_plan,
        )
        if pickup_plan is not None
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

    if pickup_plan is None:
        ok, msg = executor._pickup.execute(ctx.execution_plan)
    else:
        ok, msg = executor._pickup.execute(ctx.execution_plan, pickup_plan=pickup_plan)
    if not ok:
        _logger.info(
            "[TIMING] paint_process success=false stage=pickup total_elapsed_s=%.3f",
            elapsed_s(ctx.paint_started_at),
        )
        if msg == NO_WORKPIECE_AT_CALIBRATION:
            finish_paint_motion(ctx, success=False)
            ctx.set_result(False, msg)
            return PaintExecutionState.COMPLETED
        fail_paint_motion(ctx, msg)
        return PaintExecutionState.ERROR
    return PaintExecutionState.PAINT_CONTACT


def _dropoff_strategy(executor: object) -> str:
    return str(executor._paint_process_config().dropoff.strategy or "pickup_origin").strip().lower()


def _reserve_plate_dropoff(ctx, executor, pickup_plan) -> tuple[bool, str]:
    width_mm, height_mm = _workpiece_footprint_mm(ctx.execution_plan)
    motion_plan = getattr(pickup_plan, "motion_plan", pickup_plan)
    align_pose = getattr(motion_plan, "align_pose", None)
    if align_pose is None or len(align_pose) < 6:
        return False, "Plate-layout dropoff could not resolve workpiece orientation at calibration"

    magazine = ctx.magazine_config or getattr(ctx.process_config, "magazine_load", None)
    group_id = str(getattr(magazine, "calibration_group_id", "CALIBRATION") or "CALIBRATION")
    navigation = getattr(ctx.production_service._magazine_load_service, "_navigation", None)
    getter = getattr(navigation, "get_group_position", None)
    calibration_pose = getter(group_id) if callable(getter) else None
    if calibration_pose is None or len(calibration_pose) < 6:
        return False, f"Plate-layout dropoff requires calibration movement group '{group_id}'"

    reservation, message = executor._plate_layout_service.reserve(
        executor._paint_process_config().dropoff,
        width_mm=width_mm,
        height_mm=height_mm,
        calibration_pose=list(calibration_pose),
        workpiece_rz_at_calibration_deg=float(align_pose[5]),
        pose_calculator=calculate_workpiece_dropoff_pose,
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
    points = [
        pose[:2]
        for path in execution_plan.execution_paths()
        for pose in path
        if len(pose) >= 2
    ]
    if len(points) < 3:
        return 0.0, 0.0
    xy = np.asarray(points, dtype=np.float32)
    if not np.all(np.isfinite(xy)):
        return 0.0, 0.0
    import cv2
    _, size, _ = cv2.minAreaRect(np.ascontiguousarray(xy.reshape(-1, 1, 2)))
    return float(size[0]), float(size[1])


@timed_step(_logger, "ordered_pickup_paint_contact_chain")
def try_execute_ordered_pickup_and_paint_contact(
    executor: object,
    prepared_workpiece,
    *,
    pickup_plan=None,
) -> tuple[bool, str, int] | None:
    """Execute pickup/staging and primary paint contact as one preplanned ordered chain."""
    execute_chain = getattr(executor._robot_service, "execute_ordered_motion_chain", None)
    if not callable(execute_chain):
        return None

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
    paint_jobs: list[dict] = []
    ok, msg, total_waypoints = executor._paint_contact.execute(
        prepared_workpiece,
        execute_robot=False,
        collected_command_paths=paint_paths,
        collected_command_jobs=paint_jobs,
    )
    if not ok:
        executor._edge_cleanup.cancel_early_preplanning()
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
    second_pass_jobs: list[dict] = []
    config = executor._paint_process_config()
    workpiece = getattr(prepared_workpiece, "workpiece", {}) or {}
    is_unmatched = str(workpiece.get("workpieceId", "")).strip().lower() == "captured"
    pass_count = max(1, min(2, int(getattr(config, "unmatched_paint_pass_count", 1))))
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
            executor._edge_cleanup.cancel_early_preplanning()
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
    if _should_preplan_dropoff_in_ordered_chain(executor):
        config = executor._paint_process_config()
        if bool(config.dropoff_safe_travel.enabled) and not _resolve_dropoff_safe_travel_waypoints(executor):
            return (
                False,
                "Pivot paint finished, but paint-to-dropoff safe travel waypoints are not configured",
                total_waypoints,
            )
        dropoff_segments, dropoff_final_pose = build_ordered_dropoff_preparation_segments(executor)
        if not dropoff_segments:
            return (
                False,
                "Pivot paint finished, but no dropoff pose is available for safe pre-dropoff unwind alignment",
                total_waypoints,
            )
        post_pickup_segments.extend(dropoff_segments)
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
        return ok, msg, total_waypoints

    segments: list[dict] = build_ordered_pickup_segments(pickup_plan)
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
    return True, "", total_waypoints


def _should_preplan_dropoff_in_ordered_chain(executor: object) -> bool:
    """Keep plate travel/unwind in PREPARE_DROPOFF after paint completes."""
    return (
        _dropoff_strategy(executor) != "plate_layout"
        and not executor._edge_cleanup.should_run_after_xz_ry()
        and not executor._edge_cleanup.should_run_after_xy_rz()
    )


def build_ordered_second_pass_segments(
    paint_paths: list[list[list[float]]],
    paint_jobs: list[dict],
    config,
) -> list[dict]:
    """Build the guarded unwind, re-attach, and contact sequence for pass two."""
    return [
        {
            "type": "unwind_joint6",
            "label": "paint_pass_2_unwind",
            "vel": float(config.navigation_return.unwind_vel_percent),
            "acc": float(config.navigation_return.unwind_acc_percent),
            "protected": True,
        },
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
    workpiece = getattr(execution_plan, "workpiece", {}) or {}
    return (
        str(workpiece.get("workpieceId", "")).strip().lower() == "captured"
        and int(getattr(config, "unmatched_paint_pass_count", 1)) == 2
    )
