from __future__ import annotations

import logging
from contextlib import nullcontext
from time import monotonic, perf_counter, sleep

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.timing import timing_session

_logger = logging.getLogger(__name__)


def unwind_joint6_at_cycle_start(ctx: PaintExecutionContext) -> bool:
    """Recover J6 once per cycle before any production navigation starts."""
    if ctx.cycle_start_unwind_completed:
        return True
    executor = ctx.production_service._path_executor
    robot_service = executor._robot_service

    config = ctx.process_config
    if config is None:
        config = executor._paint_process_config()
    navigation = config.navigation_return
    _logger.info(
        "[CYCLE_START] Unwinding Joint 6 before production navigation "
        "vel=%.1f acc=%.1f queue_if_busy=%s",
        float(navigation.unwind_vel_percent),
        float(navigation.unwind_acc_percent),
        bool(navigation.unwind_queue_if_busy),
    )
    ok = bool(
        robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=bool(navigation.unwind_queue_if_busy),
            vel=float(navigation.unwind_vel_percent),
            acc=float(navigation.unwind_acc_percent),
        )
    )
    if ok:
        ok = _wait_for_unwind_motion_idle(robot_service)
    if ok:
        # Keep the plate-exit's preposition marker.  The stable-idle wait above
        # closes the unwind handoff race, and the magazine navigation handler
        # verifies the fresh Cartesian pose before it trusts this marker.  If
        # unwind changed the pose, verification fails and the normal correction
        # move still runs; a no-op unwind can reuse the already-reached pose.
        ctx.cycle_start_unwind_completed = True
    return ok


def _wait_for_unwind_motion_idle(robot_service, *, timeout_s: float = 2.0) -> bool:
    """Wait through the blocking-response/websocket-inactive handoff."""
    getter = getattr(robot_service, "get_execution_status", None)
    if not callable(getter):
        return True
    deadline = monotonic() + max(0.0, float(timeout_s))
    inactive_samples = 0
    while monotonic() < deadline:
        status = getter()
        if not isinstance(status, dict):
            return True
        if not bool(status.get("is_executing")):
            inactive_samples += 1
            if inactive_samples >= 2:
                return True
        else:
            inactive_samples = 0
        sleep(0.025)
    _logger.error("[CYCLE_START] Joint 6 unwind did not reach a stable idle state")
    return False


def start_paint_motion_if_needed(ctx: PaintExecutionContext) -> None:
    if ctx.paint_motion_active:
        return
    executor = ctx.production_service._path_executor
    session = timing_session("paint_process")
    ctx.paint_timing_session = session
    ctx.paint_timing_recorder = session.__enter__()
    ctx.paint_started_at = perf_counter()
    ctx.paint_previous_control = executor._active_execution_control
    ctx.paint_motion_active = True
    executor._active_execution_control = ctx.control
    executor._set_cycle_process_config_snapshot(ctx.raw_process_config or ctx.process_config)
    executor._apply_paint_process_contact_config()
    executor._dropoff_unwind_prepared = False
    executor._plate_entry_completed_in_paint_chain = False
    ctx.paint_total_waypoints = 0
    ctx.paint_contact_executed_in_ordered_chain = False


def wait_or_guard(ctx: PaintExecutionContext, state: PaintExecutionState) -> PaintExecutionState | None:
    guarded = guard_control(ctx, state)
    if guarded is not None:
        return guarded
    executor = ctx.production_service._path_executor
    if not executor._wait_for_paint_resume(ctx.control):
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED
    return None


def fail_paint_motion(ctx: PaintExecutionContext, message: str) -> None:
    set_paint_result(ctx, False, message)
    finish_paint_motion(ctx, success=False)


def motion_failure_message(robot_service, fallback: str) -> str:
    """Return the latest backend command error without hiding it behind a result code."""
    getter = getattr(robot_service, "get_last_trajectory_command_info", None)
    if callable(getter):
        try:
            info = getter() or {}
        except Exception:
            info = {}
        raw = info.get("raw") if isinstance(info, dict) else None
        if isinstance(raw, dict):
            detail = raw.get("error") or raw.get("message")
            if detail:
                return str(detail)

    details_getter = getattr(robot_service, "get_connection_details", None)
    if callable(details_getter):
        try:
            details = details_getter() or {}
        except Exception:
            details = {}
        if isinstance(details, dict):
            detail = details.get("last_command_error") or details.get("last_error")
            if detail:
                return str(detail)

    return str(fallback)


def set_paint_result(
    ctx: PaintExecutionContext,
    ok: bool,
    message: str,
    *,
    already_prefixed: bool = False,
) -> None:
    text = str(message or "")
    if not already_prefixed and ctx.workpiece_description:
        text = f"{ctx.workpiece_description}: {text}"
    ctx.set_result(ok, text)


def _post_return_failure_result(result_ok: bool, result_message: str) -> tuple[bool, str]:
    if result_ok:
        return False, "Paint process finished, but return-to-calibration failed"
    return False, f"{result_message}; additionally, return-to-calibration failed"


def post_return_failure_result(result_ok: bool, result_message: str) -> tuple[bool, str]:
    return _post_return_failure_result(result_ok, result_message)


def finish_paint_motion(ctx: PaintExecutionContext, *, success: bool) -> None:
    if not ctx.paint_motion_active:
        return
    executor = ctx.production_service._path_executor
    recorder = ctx.paint_timing_recorder
    started = ctx.paint_started_at or perf_counter()
    if recorder is not None:
        recorder.record(
            step="paint_process",
            label="",
            success=success,
            elapsed_s=elapsed_s(started),
            started_at=started,
            ended_at=perf_counter(),
        )
        csv_path = recorder.write_csv(executor._debug_dump_dir) if executor._diagnostics_artifacts_enabled() else None
        recorder.log_summary(_logger, csv_path=csv_path)
    session = ctx.paint_timing_session or nullcontext()
    session.__exit__(None, None, None)
    executor._active_execution_control = ctx.paint_previous_control
    ctx.paint_motion_active = False
