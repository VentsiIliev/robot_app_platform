from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    build_ordered_paint_contact_segments,
    build_ordered_pickup_segments,
)
from src.robot_systems.paint.processes.paint.config import (
    PICKUP_CONTACT_MODE_PLANNED,
    PICKUP_CONTACT_MODE_SERVO_CONTACT,
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
        PICKUP_CONTACT_MODE_SERVO_CONTACT,
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
        acceleration = None if use_first else float(pass_2.acceleration_percent)
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
    if not executor._edge_cleanup.should_run_after_xz_ry() and not executor._edge_cleanup.should_run_after_xy_rz():
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

    if pickup_plan.contact_mode == PICKUP_CONTACT_MODE_SERVO_CONTACT:
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
        ),
    ]


def _unmatched_second_pass_requested(executor: object, execution_plan: object) -> bool:
    config = executor._paint_process_config()
    workpiece = getattr(execution_plan, "workpiece", {}) or {}
    return (
        str(workpiece.get("workpieceId", "")).strip().lower() == "captured"
        and int(getattr(config, "unmatched_paint_pass_count", 1)) == 2
    )
