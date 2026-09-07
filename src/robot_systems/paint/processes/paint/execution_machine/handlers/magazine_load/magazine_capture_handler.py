from __future__ import annotations

import logging
from time import perf_counter

import cv2
import numpy as np

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
    if auto_discovery and ctx.magazine_discovery_contours:
        ctx.magazine_contour = ctx.magazine_discovery_contours.pop(0)
        _logger.info(
            "[MAGAZINE_LOAD] Reusing auto-discovery capture; remaining_targets=%d",
            len(ctx.magazine_discovery_contours),
        )
        return PaintExecutionState.MAGAZINE_PREPARE_PICKUP_RELEASE

    capture_started = perf_counter()
    ctx.magazine_snapshot = ctx.production_service._capture_snapshot_service.capture_snapshot(
        source="paint_magazine_load"
    )
    capture_elapsed = perf_counter() - capture_started
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
        ctx.magazine_discovery_contours = _ordered_contours(
            getattr(ctx.magazine_snapshot, "contours", None)
        )
        ctx.magazine_contour = (
            ctx.magazine_discovery_contours.pop(0)
            if ctx.magazine_discovery_contours
            else None
        )
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
