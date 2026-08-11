from __future__ import annotations

import logging
from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE
from src.robot_systems.paint.processes.paint.plan import pick_largest_contour

_logger = logging.getLogger(__name__)


def handle_magazine_capture(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_CAPTURE)
    if guarded is not None:
        return guarded

    started = perf_counter()
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
    ctx.magazine_contour = pick_largest_contour(getattr(ctx.magazine_snapshot, "contours", None))
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
