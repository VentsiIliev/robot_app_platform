from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    build_ordered_paint_contact_segments,
    build_ordered_pickup_segments,
)
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.motion_handlers import (
    fail_paint_motion,
    finish_paint_motion,
    start_paint_motion_if_needed,
    wait_or_guard,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    build_ordered_dropoff_preparation_segments,
    _resolve_dropoff_safe_travel_waypoints,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.timing import timed_block, timed_step

_logger = logging.getLogger(__name__)


def handle_pickup(ctx: PaintExecutionContext) -> PaintExecutionState:
    executor = ctx.production_service._path_executor
    start_paint_motion_if_needed(ctx)

    guarded = wait_or_guard(ctx, PaintExecutionState.PICKUP)
    if guarded is not None:
        finish_paint_motion(ctx, success=False)
        return guarded

    ctx.paint_ordered_result = try_execute_ordered_pickup_and_paint_contact(executor, ctx.execution_plan)
    if ctx.paint_ordered_result is not None:
        ok, msg, total_waypoints = ctx.paint_ordered_result
        ctx.paint_total_waypoints = int(total_waypoints)
        if not ok:
            fail_paint_motion(ctx, msg)
            return PaintExecutionState.ERROR
        ctx.paint_contact_executed_in_ordered_chain = True
        return PaintExecutionState.PAINT_CONTACT

    ok, msg = executor._pickup.execute(ctx.execution_plan)
    if not ok:
        _logger.info(
            "[TIMING] paint_process success=false stage=pickup total_elapsed_s=%.3f",
            elapsed_s(ctx.paint_started_at),
        )
        fail_paint_motion(ctx, msg)
        return PaintExecutionState.ERROR
    return PaintExecutionState.PAINT_CONTACT


@timed_step(_logger, "ordered_pickup_paint_contact_chain")
def try_execute_ordered_pickup_and_paint_contact(
    executor: object,
    prepared_workpiece,
) -> tuple[bool, str, int] | None:
    """Execute pickup/staging and primary paint contact as one preplanned ordered chain."""
    execute_chain = getattr(executor._robot_service, "execute_ordered_motion_chain", None)
    if not callable(execute_chain):
        return None

    pickup_plan = executor._pickup.build_plan(prepared_workpiece)
    if pickup_plan is None:
        return False, "Could not compute pickup-to-pivot poses", 0
    if pickup_plan.servo_contact_enabled:
        _logger.info("[ORDERED_CHAIN] pickup plus paint contact chain skipped: servo contact pickup enabled")
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

    segments: list[dict] = build_ordered_pickup_segments(pickup_plan)
    segments.extend(build_ordered_paint_contact_segments(paint_paths, paint_jobs))

    dropoff_prepared_in_chain = False
    final_pose: list[float] | None = list(paint_paths[-1][-1])
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
        segments.extend(dropoff_segments)
        dropoff_prepared_in_chain = True
        final_pose = dropoff_final_pose or final_pose

    if pickup_plan.vacuum_on_before_moves:
        ok, msg = executor._motion.turn_vacuum_on()
        if not ok:
            return False, msg, total_waypoints

    active_segments = list(segments)
    chain_completed = False
    while active_segments:
        _logger.info(
            "[ORDERED_CHAIN] executing pickup plus paint contact chain: segments=%d paint_paths=%d dropoff_prep=%s",
            len(active_segments),
            len(paint_paths),
            dropoff_prepared_in_chain,
        )
        executor._motion.mark_ordered_chain_interrupted_by_pause(False)
        result = execute_chain(
            active_segments,
            tool=executor._pickup_tool,
            user=executor._pickup_user,
            blocking=True,
        )
        if result in (0, True, None):
            chain_completed = True
            break
        if not executor._motion.resume_after_interrupted_non_contact_motion("Ordered pickup plus paint contact chain"):
            return False, f"Ordered pickup and paint contact chain failed with code {result}", total_waypoints
        start_index = executor._motion.consume_ordered_chain_resume_start_index()
        if start_index is None:
            start_index = executor._motion.ordered_motion_chain_resume_index(
                executor._motion.read_ordered_motion_chain_status()
            )
        executor._motion.mark_ordered_chain_interrupted_by_pause(False)
        active_segments = active_segments[max(0, min(start_index, len(active_segments))):]
    if not chain_completed:
        return True, "", total_waypoints

    if dropoff_prepared_in_chain:
        executor._dropoff_unwind_prepared = True
    if final_pose is not None:
        executor._last_process_end_pose = list(final_pose)
    return True, "", total_waypoints
