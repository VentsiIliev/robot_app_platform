from __future__ import annotations

import logging
from time import perf_counter

from src.robot_systems.paint.processes.paint.magazine_load.context import MagazineLoadContext
from src.robot_systems.paint.processes.paint.magazine_load.state import MagazineLoadState
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE
from src.robot_systems.paint.processes.paint.plan import pick_largest_contour

_logger = logging.getLogger(__name__)


def guard_control(ctx: MagazineLoadContext, state: MagazineLoadState) -> MagazineLoadState | None:
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return MagazineLoadState.STOPPED
    if not ctx.run_allowed.is_set():
        ctx.pause_from(state)
        return MagazineLoadState.PAUSED
    return None


def handle_starting(ctx: MagazineLoadContext) -> MagazineLoadState:
    S = MagazineLoadState
    if ctx.is_resuming and ctx.resume_state is not None:
        resume_state = ctx.resume_state
        ctx.is_resuming = False
        _logger.info("[MAGAZINE_LOAD] Resuming from state %s", resume_state.name)
        return resume_state

    config = ctx.config
    magazine_group = str(config.magazine_group_id or "Magazine").strip()
    calibration_group = str(config.calibration_group_id or "CALIBRATION").strip()
    if not magazine_group:
        ctx.set_result(False, "Magazine movement group is not configured")
        return S.ERROR
    if not calibration_group:
        ctx.set_result(False, "Calibration movement group is not configured")
        return S.ERROR

    ctx.magazine_group = magazine_group
    ctx.calibration_group = calibration_group
    return S.MOVE_TO_MAGAZINE


def handle_move_to_magazine(ctx: MagazineLoadContext) -> MagazineLoadState:
    S = MagazineLoadState
    config = ctx.config
    service = ctx.service
    ok = service._move_to_group_with_pause_resume_recovery(
        ctx,
        S.MOVE_TO_MAGAZINE,
        ctx.magazine_group,
        velocity=float(config.move_to_magazine_vel_percent),
        acceleration=float(config.move_to_magazine_acc_percent),
    )
    if not ok:
        return _interrupted_or_error(ctx, S.MOVE_TO_MAGAZINE, f"Move to magazine group '{ctx.magazine_group}' failed")
    _logger.info("[MAGAZINE_LOAD] Moved to magazine group '%s'", ctx.magazine_group)
    return S.WAIT_CAMERA_SETTLE


def handle_wait_camera_settle(ctx: MagazineLoadContext) -> MagazineLoadState:
    started = perf_counter()
    if not ctx.service._wait(ctx.config.camera_settle_s, ctx.motion_cancel_requested):
        return _interrupted_or_error(ctx, MagazineLoadState.WAIT_CAMERA_SETTLE, "Paint process stopped")
    _logger.info(
        "[MAGAZINE_LOAD_TIMING] wait_camera_settle configured_s=%.3f elapsed_s=%.3f",
        float(ctx.config.camera_settle_s),
        perf_counter() - started,
    )
    return MagazineLoadState.CAPTURE_MAGAZINE


def handle_capture_magazine(ctx: MagazineLoadContext) -> MagazineLoadState:
    started = perf_counter()
    capture_started = perf_counter()
    ctx.snapshot = ctx.service._capture_snapshot_service.capture_snapshot(source="paint_magazine_load")
    capture_elapsed = perf_counter() - capture_started
    contour_count = len(getattr(ctx.snapshot, "contours", None) or [])
    _logger.info(
        "[MAGAZINE_LOAD] Captured magazine snapshot contours=%d",
        contour_count,
    )
    _logger.info(
        "[MAGAZINE_LOAD_TIMING] capture_snapshot elapsed_s=%.3f contours=%d frame_available=%s",
        capture_elapsed,
        contour_count,
        getattr(ctx.snapshot, "frame", None) is not None,
    )
    guard_started = perf_counter()
    interrupted = guard_control(ctx, MagazineLoadState.CAPTURE_MAGAZINE)
    guard_elapsed = perf_counter() - guard_started
    if interrupted is not None:
        return interrupted

    contour_started = perf_counter()
    ctx.contour = pick_largest_contour(getattr(ctx.snapshot, "contours", None))
    contour_elapsed = perf_counter() - contour_started
    _logger.info(
        "[MAGAZINE_LOAD_TIMING] capture_magazine guard_s=%.3f pick_largest_s=%.3f total_s=%.3f selected_points=%d",
        guard_elapsed,
        contour_elapsed,
        perf_counter() - started,
        len(ctx.contour) if ctx.contour is not None else 0,
    )
    if ctx.contour is None:
        _logger.warning(
            "[MAGAZINE_LOAD] No usable contour detected after moving to '%s'",
            ctx.magazine_group,
        )
        ctx.set_result(False, NO_WORKPIECE_AT_MAGAZINE)
        return MagazineLoadState.COMPLETED
    return MagazineLoadState.RESOLVE_PICKUP


def handle_resolve_pickup(ctx: MagazineLoadContext) -> MagazineLoadState:
    service = ctx.service
    started = perf_counter()
    magazine_pose_started = perf_counter()
    ctx.magazine_pose = service._navigation.get_group_position(ctx.magazine_group)
    magazine_pose_elapsed = perf_counter() - magazine_pose_started
    if ctx.magazine_pose is None:
        ctx.set_result(False, f"Magazine movement group '{ctx.magazine_group}' is not configured")
        return MagazineLoadState.ERROR

    release_base_started = perf_counter()
    base_release_pose = service._navigation.get_group_position(ctx.calibration_group)
    release_base_elapsed = perf_counter() - release_base_started
    if base_release_pose is None:
        ctx.set_result(False, f"Calibration movement group '{ctx.calibration_group}' is not configured")
        return MagazineLoadState.ERROR

    pickup_started = perf_counter()
    ctx.target = service._resolve_pickup_target(ctx.contour, ctx.magazine_pose)
    pickup_elapsed = perf_counter() - pickup_started
    if ctx.target is None:
        ctx.set_result(False, "Could not resolve magazine pickup target")
        return MagazineLoadState.ERROR

    release_started = perf_counter()
    ctx.release_pose = service._resolve_work_area_center_release_pose(
        base_pose=base_release_pose,
        frame=getattr(ctx.snapshot, "frame", None),
    )
    release_elapsed = perf_counter() - release_started
    if ctx.release_pose is None:
        ctx.set_result(False, f"Could not resolve {service._release_work_area_id} work area center release pose")
        return MagazineLoadState.ERROR
    _logger.info(
        "[MAGAZINE_LOAD_TIMING] resolve_pickup magazine_pose_s=%.3f release_base_pose_s=%.3f "
        "pickup_target_s=%.3f release_pose_s=%.3f total_s=%.3f",
        magazine_pose_elapsed,
        release_base_elapsed,
        pickup_elapsed,
        release_elapsed,
        perf_counter() - started,
    )
    return MagazineLoadState.EXECUTE_PICKUP_AND_RELEASE


def handle_execute_pickup_and_release(ctx: MagazineLoadContext) -> MagazineLoadState:
    service = ctx.service
    execute_transfer = getattr(service._path_executor, "execute_pickup_target_and_release_at_position", None)
    if not callable(execute_transfer):
        ctx.set_result(False, "Paint path executor does not support magazine transfer")
        return MagazineLoadState.ERROR

    ok, msg = execute_transfer(
        pickup_xy=ctx.target["pickup_xy"],
        pickup_rz=ctx.target["pickup_rz"],
        pickup_base_pose=ctx.magazine_pose,
        release_pose=ctx.release_pose,
        workpiece_height_mm=0.0,
        release_label=f"{service._release_work_area_id} work area center",
        resume_from_current_pose=ctx.consume_resume_retry(),
    )
    if not ok:
        return _interrupted_or_error(ctx, MagazineLoadState.EXECUTE_PICKUP_AND_RELEASE, f"Magazine contour: {msg}")
    ctx.set_result(True, f"Magazine contour: {msg}")
    return MagazineLoadState.MOVE_TO_CALIBRATION


def handle_move_to_calibration(ctx: MagazineLoadContext) -> MagazineLoadState:
    config = ctx.config
    ok = ctx.service._move_to_group_with_pause_resume_recovery(
        ctx,
        MagazineLoadState.MOVE_TO_CALIBRATION,
        ctx.calibration_group,
        velocity=float(config.transfer_to_calibration_vel_percent),
        acceleration=float(config.transfer_to_calibration_acc_percent),
    )
    if not ok:
        return _interrupted_or_error(
            ctx,
            MagazineLoadState.MOVE_TO_CALIBRATION,
            f"Move to calibration group '{ctx.calibration_group}' after release failed",
        )

    mark_verified = getattr(ctx.service._navigation, "mark_group_observed_area_verified", None)
    if callable(mark_verified):
        mark_verified(ctx.calibration_group)
    return MagazineLoadState.WAIT_RELEASE_SETTLE


def handle_wait_release_settle(ctx: MagazineLoadContext) -> MagazineLoadState:
    if not ctx.service._wait(ctx.config.release_settle_s, ctx.motion_cancel_requested):
        return _interrupted_or_error(ctx, MagazineLoadState.WAIT_RELEASE_SETTLE, "Paint process stopped")
    if not ctx.result_message:
        ctx.set_result(True, "Magazine contour: Workpiece transferred to paint work area center")
    return MagazineLoadState.COMPLETED


def handle_paused(ctx: MagazineLoadContext) -> MagazineLoadState:
    _logger.info("[MAGAZINE_LOAD] Paused from state %s", getattr(ctx.paused_from_state, "name", None))
    while True:
        if ctx.should_stop():
            ctx.set_result(False, "Paint process stopped")
            return MagazineLoadState.STOPPED
        if ctx.run_allowed.wait(timeout=0.05):
            ctx.mark_resuming()
            return MagazineLoadState.STARTING


def handle_completed(ctx: MagazineLoadContext) -> MagazineLoadState:
    if ctx.state_machine is not None:
        ctx.state_machine.stop_execution()
    return MagazineLoadState.IDLE


def handle_stopped(ctx: MagazineLoadContext) -> MagazineLoadState:
    ctx.set_result(False, "Paint process stopped")
    if ctx.state_machine is not None:
        ctx.state_machine.stop_execution()
    return MagazineLoadState.IDLE


def handle_error(ctx: MagazineLoadContext) -> MagazineLoadState:
    if not ctx.result_message:
        ctx.set_result(False, "Magazine load failed")
    _logger.error("[MAGAZINE_LOAD] Failed: %s", ctx.result_message)
    if ctx.state_machine is not None:
        ctx.state_machine.stop_execution()
    return MagazineLoadState.IDLE


def handle_idle(ctx: MagazineLoadContext) -> MagazineLoadState:
    if ctx.state_machine is not None:
        ctx.state_machine.stop_execution()
    return MagazineLoadState.IDLE


def _interrupted_or_error(
    ctx: MagazineLoadContext,
    state: MagazineLoadState,
    message: str,
) -> MagazineLoadState:
    interrupted = guard_control(ctx, state)
    if interrupted is not None:
        return interrupted
    ctx.set_result(False, message)
    return MagazineLoadState.ERROR
