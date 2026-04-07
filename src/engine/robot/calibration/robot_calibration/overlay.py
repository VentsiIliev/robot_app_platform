from src.engine.robot.calibration.robot_calibration.overlay_renderer import (
    OverlayStatus,
    OpenCvCalibrationRenderer,
    get_calibration_renderer,
)


def draw_image_center(frame) -> None:
    # Compatibility wrapper kept for existing call sites.
    OpenCvCalibrationRenderer().draw_image_center(frame)


def build_overlay_status(context, current_error_mm=None) -> dict:
    target_ids = list(context.target_plan.target_marker_ids or context.target_plan.required_ids or sorted(list(context.required_ids)))
    current_index = int(context.progress.current_marker_id)
    active_target_id = None
    active_target_px = None
    available_marker_points_px = dict(context.artifacts.available_marker_points_px or {})
    if target_ids and 0 <= current_index < len(target_ids):
        active_target_id = int(target_ids[current_index])
        point = available_marker_points_px.get(active_target_id)
        if point is not None:
            active_target_px = (float(point[0]), float(point[1]))
    progress_pct = (current_index / len(target_ids)) * 100 if target_ids else 0.0
    return {
        "state_name": context.get_current_state_name(),
        "target_ids": list(target_ids),
        "active_target_id": active_target_id,
        "active_target_px": active_target_px,
        "current_marker_index": current_index,
        "total_targets": len(target_ids),
        "iteration_count": int(context.progress.iteration_count),
        "max_iterations": int(context.progress.max_iterations),
        "alignment_threshold_mm": float(context.progress.alignment_threshold_mm),
        "current_error_mm": None if current_error_mm is None else float(current_error_mm),
        "progress_pct": float(progress_pct),
    }


def draw_live_overlay(context, frame, current_error_mm=None):
    if frame is None or not context.live_visualization:
        return frame

    overlay_payload = build_overlay_status(context, current_error_mm)
    status = OverlayStatus(
        state_name=overlay_payload["state_name"],
        target_ids=overlay_payload["target_ids"],
        current_marker_index=overlay_payload["current_marker_index"],
        iteration_count=overlay_payload["iteration_count"],
        max_iterations=overlay_payload["max_iterations"],
        alignment_threshold_mm=overlay_payload["alignment_threshold_mm"],
        current_error_mm=overlay_payload["current_error_mm"],
    )
    return get_calibration_renderer(context).render_live_overlay(frame, status)
