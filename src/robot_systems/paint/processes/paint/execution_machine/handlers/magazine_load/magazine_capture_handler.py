from __future__ import annotations

import logging
from time import perf_counter

import cv2
import numpy as np

from src.engine.robot.motion_sequence import OrderedMotionType
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.config import (
    MAGAZINE_PICKUP_MODE_AUTO_DISCOVERY_SENSOR_CONTROLLED_FAST_LIN,
)
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE
from src.robot_systems.paint.processes.paint.plan import pick_largest_contour

_logger = logging.getLogger(__name__)


def handle_magazine_capture(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_CAPTURE)
    if guarded is not None:
        return guarded

    started = perf_counter()
    pickup_mode = str(ctx.magazine_config.pickup_mode or "").strip().lower()
    auto_discovery = (
        pickup_mode == MAGAZINE_PICKUP_MODE_AUTO_DISCOVERY_SENSOR_CONTROLLED_FAST_LIN
    )
    if auto_discovery and ctx.magazine_discovery_active_contour is not None:
        ctx.magazine_contour = ctx.magazine_discovery_active_contour
        _logger.info(
            "[MAGAZINE_LOAD] Reusing active auto-discovery pile; queued_piles=%d",
            len(ctx.magazine_discovery_contours),
        )
        return PaintExecutionState.MAGAZINE_PREPARE_PICKUP_RELEASE
    if auto_discovery and ctx.magazine_discovery_contours:
        ctx.magazine_discovery_active_contour = ctx.magazine_discovery_contours.pop(0)
        ctx.magazine_contour = ctx.magazine_discovery_active_contour
        _logger.info(
            "[MAGAZINE_LOAD] Advancing to next auto-discovery pile; queued_piles=%d",
            len(ctx.magazine_discovery_contours),
        )
        return PaintExecutionState.MAGAZINE_PREPARE_PICKUP_RELEASE

    load_service = ctx.production_service._magazine_load_service
    capture_pose_ok, capture_pose_error = (
        load_service._verify_current_capture_pose(
            ctx.magazine_group,
            position_tolerance_mm=2.0,
            orientation_tolerance_deg=2.0,
        )
    )
    if not capture_pose_ok and not ctx.motion_cancel_requested():
        _logger.warning(
            "[MAGAZINE_CAPTURE_POSE] Endpoint is outside capture tolerance after "
            "settling; commanding one exact correction move to '%s'",
            ctx.magazine_group,
        )
        correction_kwargs = {
            "velocity": min(50.0, float(ctx.magazine_config.move_to_magazine_vel_percent)),
            "acceleration": min(20.0, float(ctx.magazine_config.move_to_magazine_acc_percent)),
            "motion_type": OrderedMotionType.parse(
                ctx.magazine_config.move_to_magazine_motion_type,
                field_name="magazine_load.move_to_magazine_motion_type",
            ).value,
            "blendR": 0.0,
        }
        if ctx.magazine_fixed_pickup_pose is not None:
            corrected = load_service._move_to_pose_with_pause_resume_recovery(
                ctx,
                PaintExecutionState.MAGAZINE_CAPTURE,
                ctx.magazine_fixed_pickup_pose,
                ctx.magazine_group,
                **correction_kwargs,
            )
        else:
            corrected = load_service._move_to_group_with_pause_resume_recovery(
                ctx,
                PaintExecutionState.MAGAZINE_CAPTURE,
                ctx.magazine_group,
                **correction_kwargs,
            )
        if corrected and load_service._wait(0.3, ctx.motion_cancel_requested):
            capture_pose_ok, capture_pose_error = load_service._verify_current_capture_pose(
                ctx.magazine_group,
                position_tolerance_mm=2.0,
                orientation_tolerance_deg=2.0,
            )
    if not capture_pose_ok:
        _logger.error("[MAGAZINE_CAPTURE_POSE] %s", capture_pose_error)
        ctx.set_result(False, capture_pose_error)
        return PaintExecutionState.ERROR

    capture_started = perf_counter()
    ctx.magazine_snapshot = ctx.production_service._capture_snapshot_service.capture_snapshot(
        source="paint_magazine_load"
    )
    capture_elapsed = perf_counter() - capture_started
    ctx.production_service._set_dashboard_live_view_paused(
        True,
        image=getattr(ctx.magazine_snapshot, "frame", None),
        reason="magazine snapshot captured",
    )
    contour_count = len(getattr(ctx.magazine_snapshot, "contours", None) or [])
    _logger.info("[MAGAZINE_LOAD] Captured magazine snapshot contours=%d", contour_count)
    _logger.info(
        "[MAGAZINE_LOAD_TIMING] capture_snapshot elapsed_s=%.3f contours=%d frame_available=%s",
        capture_elapsed,
        contour_count,
        getattr(ctx.magazine_snapshot, "frame", None) is not None,
    )

    interrupted = guard_control(ctx, PaintExecutionState.MAGAZINE_CAPTURE)
    if interrupted is not None:
        return interrupted

    contour_started = perf_counter()
    if auto_discovery:
        ctx.magazine_discovery_contours = _ordered_contours_nearest_to_calibration(
            ctx,
            getattr(ctx.magazine_snapshot, "contours", None),
        )
        ctx.magazine_discovery_empty_capture = not ctx.magazine_discovery_contours
        if ctx.magazine_discovery_contours:
            ctx.magazine_discovery_active_contour = (
                ctx.magazine_discovery_contours.pop(0)
            )
        ctx.magazine_contour = ctx.magazine_discovery_active_contour
    else:
        ctx.magazine_contour = pick_largest_contour(
            getattr(ctx.magazine_snapshot, "contours", None)
        )
    contour_elapsed = perf_counter() - contour_started
    _logger.info(
        "[MAGAZINE_LOAD_TIMING] capture_magazine pick_largest_s=%.3f total_s=%.3f selected_points=%d",
        contour_elapsed,
        perf_counter() - started,
        len(ctx.magazine_contour) if ctx.magazine_contour is not None else 0,
    )
    if ctx.magazine_contour is None:
        _logger.warning("[MAGAZINE_LOAD] No usable contour detected after moving to '%s'", ctx.magazine_group)
        ctx.set_result(False, NO_WORKPIECE_AT_MAGAZINE)
        return PaintExecutionState.COMPLETED
    return PaintExecutionState.MAGAZINE_PREPARE_PICKUP_RELEASE


def _ordered_contours(contours) -> list:
    """Return valid discovery contours in deterministic top-to-bottom order."""
    ordered = []
    for contour in contours or ():
        try:
            points = np.asarray(contour, dtype=np.float64).reshape(-1, 2)
        except (TypeError, ValueError):
            continue
        if len(points) < 3:
            continue
        moments = cv2.moments(points.astype(np.float32))
        if abs(float(moments["m00"])) <= 1e-9:
            continue
        center_x = float(moments["m10"] / moments["m00"])
        center_y = float(moments["m01"] / moments["m00"])
        ordered.append((center_y, center_x, contour))
    ordered.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ordered]


def _ordered_contours_nearest_to_calibration(
    ctx: PaintExecutionContext,
    contours,
) -> list:
    """Order piles from the calibration-side exit inward in robot XY space."""
    ordered = _ordered_contours(contours)
    if not ordered:
        return []

    load_service = ctx.production_service._magazine_load_service
    magazine_pose = load_service._navigation.get_group_position(ctx.magazine_group)
    calibration_pose = load_service._navigation.get_group_position(ctx.calibration_group)
    if magazine_pose is None or calibration_pose is None or len(calibration_pose) < 2:
        raise RuntimeError(
            "Cannot order magazine piles by calibration distance: movement group pose is unavailable"
        )

    ranked = []
    for stable_index, contour in enumerate(ordered):
        target = load_service._resolve_pickup_target(contour, magazine_pose)
        if target is None:
            raise RuntimeError(
                "Cannot order magazine piles by calibration distance: pickup target resolution failed"
            )
        pickup_xy = target.get("pickup_xy")
        if pickup_xy is None or len(pickup_xy) < 2:
            raise RuntimeError(
                "Cannot order magazine piles by calibration distance: pickup XY is unavailable"
            )
        distance_sq = (
            (float(pickup_xy[0]) - float(calibration_pose[0])) ** 2
            + (float(pickup_xy[1]) - float(calibration_pose[1])) ** 2
        )
        ranked.append((distance_sq, stable_index, contour, pickup_xy))

    ranked.sort(key=lambda item: (item[0], item[1]))
    _logger.info(
        "[MAGAZINE_LOAD] Auto-discovery pile order nearest calibration first: %s",
        [
            {
                "pickup_xy": [round(float(item[3][0]), 3), round(float(item[3][1]), 3)],
                "distance_mm": round(float(item[0]) ** 0.5, 3),
            }
            for item in ranked
        ],
    )
    return [item[2] for item in ranked]
